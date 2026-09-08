"""Scanner agent — Rule Set v1.1 Layer 0 (eligibility) + Layer 1 (hotness ranking).

Consumes feed events, maintains a `SymbolState` per symbol, and every `scan_interval_s`
emits the top `candidates_per_side` long and short `Candidate`s onto the bus.

E2 (book depth vs position size) is intentionally NOT checked here — it depends on the
intended order size and is enforced by the Observer's self-impact guard (S2/S3).
"""

from __future__ import annotations

import asyncio
import statistics
from datetime import UTC, datetime

from mats.agents.symbol_state import SymbolState
from mats.config import StrategyParams
from mats.core.bus import EventBus
from mats.core.clock import Clock
from mats.core.models import (
    Candidate,
    Candle,
    InstrumentStats,
    Liquidation,
    MarkPrice,
    OrderBook,
    Side,
    Trade,
)

_FUNDING_BLACKOUT_S = 120.0

_HOTNESS_FEATURES = ("rvol_5m", "rvol_15m", "abs_ret_15m", "tps_ratio", "oi_delta", "rs_vs_btc")


def check_eligible(s: SymbolState, p: StrategyParams, now_ts: float) -> tuple[bool, str]:
    """Layer 0. Fail-closed: missing data => not eligible."""
    if s.quote_volume_24h is None or s.quote_volume_24h < p.min_24h_quote_volume_inr:
        return False, "E1_volume"
    if s.spread_pct is not None and s.spread_pct > p.max_spread_pct:
        return False, "E3_spread"
    if s.funding_pct is not None and abs(s.funding_pct) > p.max_abs_funding_pct:
        return False, "E4_funding"
    if s.mark_last_gap_pct is not None and s.mark_last_gap_pct > p.max_mark_last_gap_pct:
        return False, "E5_mark_gap"
    if s.age_days is not None and s.age_days < p.min_contract_age_days:
        return False, "E6_age"
    if s.next_funding_ts is not None and abs(s.next_funding_ts - now_ts) <= _FUNDING_BLACKOUT_S:
        return False, "E7_funding_window"
    return True, "ok"


def _directional_checks(
    s: SymbolState, p: StrategyParams, side: Side, rank: int | None
) -> tuple[bool, str]:
    """Layer 1 H1-H10 for one side. LONG shown; SHORT is the mirror.

    RS-vs-BTC is a hotness input, not a hard gate in Layer 1 (it becomes reject R7 in the
    Observer's Layer 2).
    """
    sign = 1.0 if side is Side.LONG else -1.0
    r5, r15, r1h = s.ret_5m, s.ret_15m, s.ret_1h
    if r5 is None or r15 is None or r1h is None:
        return False, "H_returns_missing"
    if not (sign * r5 > 0 and sign * r15 > 0 and sign * r1h > 0):  # H1
        return False, "H1_alignment"
    if s.rvol_5m is None or s.rvol_5m < p.min_rvol_5m:  # H2
        return False, "H2_rvol_5m"
    if s.rvol_15m is None or s.rvol_15m < p.min_rvol_15m:  # H3
        return False, "H3_rvol_15m"
    if s.tps_ratio is None or s.tps_ratio < p.min_tps_ratio:  # H4
        return False, "H4_tps"
    if s.atr_expanding is not True:  # H5
        return False, "H5_atr"
    lo, hi = p.ret_1h_band_pct  # H6 (mirror band for shorts)
    if not (lo <= sign * r1h <= hi):
        return False, "H6_exhausted"
    rsi = s.rsi_5m  # H7
    if rsi is not None:
        if side is Side.LONG and rsi > p.max_rsi_5m:
            return False, "H7_rsi"
        if side is Side.SHORT and rsi < (100.0 - p.max_rsi_5m):
            return False, "H7_rsi"
    if s.oi_delta_15m is None or s.oi_delta_15m <= 0:  # H8 new money, not short-covering
        return False, "H8_oi"
    if s.cvd_divergence is not False:  # H9 (None => unknown => reject)
        return False, "H9_cvd"
    if s.cvd_slope * sign <= 0:  # H9 slope must be with the trade
        return False, "H9_cvd_slope"
    if rank is None or rank > p.top_gainer_rank_max:  # H10
        return False, "H10_rank"
    return True, "ok"


def _feature_vector(s: SymbolState, rs_vs_btc: float | None) -> dict[str, float]:
    return {
        "rvol_5m": s.rvol_5m or 0.0,
        "rvol_15m": s.rvol_15m or 0.0,
        "abs_ret_15m": abs(s.ret_15m or 0.0),
        "tps_ratio": s.tps_ratio or 0.0,
        "oi_delta": s.oi_delta_15m or 0.0,
        "rs_vs_btc": abs(rs_vs_btc or 0.0),
    }


def _zscore_hotness(
    vectors: dict[str, dict[str, float]], weights: dict[str, float]
) -> dict[str, float]:
    if not vectors:
        return {}
    out = {sym: 0.0 for sym in vectors}
    for feat in _HOTNESS_FEATURES:
        vals = [v[feat] for v in vectors.values()]
        mean = statistics.fmean(vals)
        std = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        w = weights.get(feat, 1.0)
        for sym, v in vectors.items():
            z = 0.0 if std == 0 else (v[feat] - mean) / std
            out[sym] += w * z
    return out


class Scanner:
    def __init__(self, bus: EventBus, params: StrategyParams, clock: Clock) -> None:
        self._bus = bus
        self._p = params
        self._clock = clock
        self._states: dict[str, SymbolState] = {}
        self._sub = bus.subscribe(Candle, Trade, MarkPrice, InstrumentStats, OrderBook, Liquidation)

    def _state(self, symbol: str) -> SymbolState:
        st = self._states.get(symbol)
        if st is None:
            st = SymbolState(symbol, self._p)
            self._states[symbol] = st
        return st

    def _ingest(self, event: object) -> None:
        if isinstance(event, Candle):
            self._state(event.symbol).on_candle(event)
        elif isinstance(event, Trade):
            self._state(event.symbol).on_trade(event)
        elif isinstance(event, MarkPrice):
            self._state(event.symbol).on_mark(event)
        elif isinstance(event, InstrumentStats):
            self._state(event.symbol).on_stats(event)
        elif isinstance(event, OrderBook):
            self._state(event.symbol).on_book(event)
        elif isinstance(event, Liquidation):
            self._state(event.symbol).on_liquidation(event)

    async def _consume(self) -> None:
        async for event in self._sub:
            self._ingest(event)

    async def run(self) -> None:
        consumer = asyncio.create_task(self._consume())
        try:
            while True:
                await self._clock.sleep(self._p.scan_interval_s)
                for cand in self.evaluate(self._clock.now()):
                    self._bus.publish(cand)
        finally:
            consumer.cancel()

    # --- pure evaluation (unit-tested directly) --------------------------

    def evaluate(self, now_ts: float) -> list[Candidate]:
        btc = self._states.get(self._p.btc_symbol)
        btc_ret_15m = btc.ret_15m if btc else None

        eligible: list[SymbolState] = []
        for st in self._states.values():
            ok, _ = check_eligible(st, self._p, now_ts)
            if ok:
                eligible.append(st)

        # our own top-gainers / top-losers ranking over the eligible set
        by_ret = [s for s in eligible if s.ret_1h is not None]
        long_rank = {
            s.symbol: i + 1 for i, s in enumerate(sorted(by_ret, key=_ret1h, reverse=True))
        }
        short_rank = {s.symbol: i + 1 for i, s in enumerate(sorted(by_ret, key=_ret1h))}

        out: list[Candidate] = []
        for side, ranks in ((Side.LONG, long_rank), (Side.SHORT, short_rank)):
            passing: dict[str, SymbolState] = {}
            reasons: dict[str, dict[str, float]] = {}
            for st in eligible:
                ok, _why = _directional_checks(st, self._p, side, ranks.get(st.symbol))
                if ok:
                    passing[st.symbol] = st
                    reasons[st.symbol] = _feature_vector(st, _rs_vs_btc(st, btc_ret_15m))
            hotness = _zscore_hotness(reasons, self._p.hotness_weights)
            ranked = sorted(passing.values(), key=lambda s: hotness[s.symbol], reverse=True)
            for st in ranked[: self._p.candidates_per_side]:
                out.append(
                    Candidate(
                        symbol=st.symbol,
                        side=side,
                        hotness=hotness[st.symbol],
                        reasons=reasons[st.symbol],
                        created_at=datetime.fromtimestamp(now_ts, tz=UTC),
                    )
                )
        return out


def _ret1h(s: SymbolState) -> float:
    return s.ret_1h or 0.0


def _rs_vs_btc(s: SymbolState, btc_ret_15m: float | None) -> float | None:
    if s.ret_15m is None or btc_ret_15m is None:
        return None
    return s.ret_15m - btc_ret_15m
