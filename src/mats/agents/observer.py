"""Observer agent — Rule Set v1.1 Layer 2 (entry hunt).

One `ObserverTask` per `Candidate`. It watches the shared `SymbolState` and, when a clean
entry appears that passes every gate, emits a `TradeIntent`. It gives up after
`observer_watch_seconds` or as soon as the momentum-alive gate fails.

`evaluate_entry` is pure and unit-tested directly; the async class is a thin wrapper.

Simplifications flagged for a follow-up (see PR): C4 "ask-pull / sweep", room-to-run
checks 7 (tape acceleration) and 8 (liquidation character), and R6 (funding rate-of-change)
are approximated or conservatively skipped — the data plumbing for them lands later.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from mats.agents.legs import analyze_legs
from mats.agents.market_state import MarketStateStore
from mats.agents.symbol_state import SymbolState
from mats.config import StrategyParams
from mats.core.bus import EventBus
from mats.core.clock import Clock
from mats.core.indicators import book_imbalance, book_walk_slippage_pct
from mats.core.models import Candidate, OrderBook, Side, TradeIntent


@dataclass
class EntryOutcome:
    stage: str  # momentum | room | pattern | book | impact | reject | ok
    reason: str
    room_score: int = 0
    intent: TradeIntent | None = None
    notes: dict[str, str] = field(default_factory=dict)


def _sign(side: Side) -> float:
    return 1.0 if side is Side.LONG else -1.0


# --- Layer 2a: momentum still alive -----------------------------------------


def momentum_alive(st: SymbolState, side: Side, p: StrategyParams) -> tuple[bool, str]:
    s = _sign(side)
    close, ema = st.close_1m, st.ema20_1m
    if close is None or ema is None or st.ema20_1m_rising is None:
        return False, "warming"
    if s * (close - ema) <= 0:
        return False, "price_lost_ema20"
    if side is Side.LONG and not st.ema20_1m_rising:
        return False, "ema20_not_rising"
    if side is Side.SHORT and st.ema20_1m_rising:
        return False, "ema20_not_falling"
    # Regime intact on the 15m return; the 5m return may dip during a P1 pullback but a
    # deep 5m reversal means the move is done.
    r15, r5 = st.ret_15m, st.ret_5m
    if r15 is None or s * r15 < 0.3:
        return False, "ret_15m_faded"
    if r5 is not None and s * r5 < -0.6:
        return False, "ret_5m_reversed"
    if s * st.cvd_slope <= 0:
        return False, "cvd_slope_against"
    return True, "ok"


# --- Layer 2b: room to run (need >= room_to_run_min_score of 9) --------------


def room_to_run(st: SymbolState, side: Side, p: StrategyParams) -> tuple[int, dict[str, bool]]:
    s = _sign(side)
    legs = analyze_legs(st.recent_candles_1m(90), side, p.zigzag_min_move_pct)
    atr = st.atr_1m or 0.0
    close = st.close_1m or 0.0
    vwap = st.vwap_15m

    checks: dict[str, bool] = {}
    checks["1_cvd_confirms"] = st.cvd_divergence is False
    checks["2_leg_not_extended"] = bool(
        legs
        and legs.avg_leg_pct > 0
        and legs.current_leg_pct < p.leg_extension_max_mult * legs.avg_leg_pct
    )
    checks["3_pullbacks_bought"] = bool(legs and 2 <= legs.pullback_count <= 4)
    checks["4_not_stretched_from_vwap"] = bool(
        vwap and atr > 0 and s * (close - vwap) < p.max_atr_above_vwap_mult * atr
    )
    checks["5_oi_rising"] = (st.oi_delta_15m or 0.0) > 0
    rsi = st.rsi_1m
    checks["6_rsi_not_pinned"] = rsi is not None and (
        rsi < p.rsi_1m_room_cap if side is Side.LONG else rsi > 100 - p.rsi_1m_room_cap
    )
    checks["7_tape_not_decelerating"] = (st.tps_ratio or 0.0) >= 1.0  # approx (see module doc)
    liq = st.last_liquidation
    checks["8_liq_not_climax"] = liq is None or liq.side is not side  # a same-side giant = climax
    checks["9_clear_air"] = bool(
        legs and abs(close - legs.last_pivot_price) / close * 100 > p.resistance_proximity_pct
    )
    return sum(checks.values()), checks


# --- Layer 2c: entry pattern ----------------------------------------------


def _entry_pattern(st: SymbolState, side: Side, p: StrategyParams) -> tuple[str, float] | None:
    """Returns (pattern, stop_price) or None. LONG logic; SHORT mirrors."""
    s = _sign(side)
    candles = st.recent_candles_1m(20)
    if len(candles) < 5:
        return None
    last = candles[-1]
    legs = analyze_legs(st.recent_candles_1m(90), side, p.zigzag_min_move_pct)

    # P1: pullback & resume
    if legs is not None:
        lo, hi = p.retrace_pct_range
        pulled = lo <= legs.retrace_pct_of_last_leg <= hi
        resumed = s * (last.close - last.open) > 0
        prior_vol = sum(c.volume for c in candles[-4:-1]) / 3 or 1.0
        resume_rvol = last.volume / prior_vol
        if pulled and resumed and resume_rvol >= p.resume_candle_min_rvol:
            stop = (
                min(c.low for c in candles[-8:])
                if side is Side.LONG
                else max(c.high for c in candles[-8:])
            )
            return "P1_pullback", stop

    # P2: micro-breakout of a tight range
    win = candles[-(p.consolidation_min_minutes + 1) :]
    highs = [c.high for c in win[:-1]]
    lows = [c.low for c in win[:-1]]
    if highs and lows:
        mid = (max(highs) + min(lows)) / 2
        width_pct = (max(highs) - min(lows)) / mid * 100 if mid > 0 else 999
        broke = (last.close > max(highs)) if side is Side.LONG else (last.close < min(lows))
        prior_vol = sum(c.volume for c in win[:-1]) / max(1, len(win) - 1) or 1.0
        if (
            width_pct <= p.consolidation_max_width_pct
            and broke
            and last.volume / prior_vol >= p.breakout_min_rvol
        ):
            return "P2_breakout", (min(lows) if side is Side.LONG else max(highs))
    return None


# --- Layer 2d/2e: book confirmation + self-impact -------------------------


def _book_and_impact(
    st: SymbolState, side: Side, p: StrategyParams, entry: float, tp1: float, order_notional: float
) -> tuple[bool, str]:
    book = st.order_book
    if book is None:
        return False, "no_book"
    s = _sign(side)
    imb = book_imbalance(book, levels=10)
    if imb is None or s * imb < p.min_book_imbalance:  # C1
        return False, "C1_imbalance"
    if s * st.cvd_slope <= 0:  # C3
        return False, "C3_cvd"
    if _wall_between(book, side, entry, tp1, p):  # C2 / S3
        return False, "C2_wall_to_tp1"

    vol_60s = st.traded_notional_60s
    if vol_60s > 0 and order_notional / vol_60s * 100 > p.max_size_pct_of_60s_vol:  # S1
        return False, "S1_size_vs_flow"
    slip = book_walk_slippage_pct(book, side, order_notional)  # S2
    if slip is None or slip > p.max_book_walk_slippage_pct:
        return False, "S2_slippage"
    return True, "ok"


def _wall_between(book: OrderBook, side: Side, entry: float, tp1: float, p: StrategyParams) -> bool:
    levels = book.asks if side is Side.LONG else book.bids
    if not levels:
        return False
    avg = sum(lvl.qty for lvl in levels) / len(levels)
    lo, hi = min(entry, tp1), max(entry, tp1)
    return any(lo <= lvl.price <= hi and lvl.qty > p.wall_size_mult * avg for lvl in levels)


# --- Layer 2f: hard rejections ------------------------------------------


def hard_rejections(
    st: SymbolState, side: Side, btc: SymbolState | None, p: StrategyParams, entry: float
) -> str | None:
    s = _sign(side)
    candles = st.recent_candles_1m(2)
    atr = st.atr_1m or 0.0
    if candles and atr > 0:  # R1 climax bar
        last = candles[-1]
        rng = last.high - last.low
        closes_weak = (
            (
                (last.close - last.low) / rng < 1 / 3
                if side is Side.LONG
                else (last.high - last.close) / rng < 1 / 3
            )
            if rng > 0
            else False
        )
        if rng > p.climax_bar_atr_mult * atr and closes_weak:
            return "R1_climax_bar"

    legs = analyze_legs(st.recent_candles_1m(90), side, p.zigzag_min_move_pct)
    if (
        legs
        and abs(entry - legs.last_pivot_price) / entry * 100 < p.resistance_proximity_pct
        and (legs.last_pivot_price > entry) == (side is Side.LONG)
    ):
        return "R2_at_resistance"  # entering right into the last swing extreme

    med = st.spread_median()
    if st.spread_pct is not None and med is not None and st.spread_pct > 2 * med:  # R3
        return "R3_spread_blown_out"

    liq = st.last_liquidation
    if liq is not None and liq.side is side and liq.qty * (st.close_1m or 0) >= 500_000:  # R4
        return "R4_liq_against"

    if btc is not None:
        b5 = btc.ret_5m
        if b5 is not None and s * b5 < -p.btc_5m_move_reject_pct:  # R5
            return "R5_btc_dislocating"
        rs = _rs_vs_btc(st, btc)
        if rs is not None and abs(rs) < p.min_rs_vs_btc_pct:  # R7
            return "R7_pure_beta"
    return None


def _rs_vs_btc(st: SymbolState, btc: SymbolState) -> float | None:
    if st.ret_15m is None or btc.ret_15m is None:
        return None
    return st.ret_15m - btc.ret_15m


# --- top-level pure evaluation -----------------------------------------


def evaluate_entry(
    st: SymbolState,
    side: Side,
    btc: SymbolState | None,
    p: StrategyParams,
    order_notional: float,
) -> EntryOutcome:
    ok, why = momentum_alive(st, side, p)
    if not ok:
        return EntryOutcome("momentum", why)

    score, checks = room_to_run(st, side, p)
    if score < p.room_to_run_min_score:
        failed = ",".join(k for k, v in checks.items() if not v)
        return EntryOutcome("room", f"score_{score}<{p.room_to_run_min_score}:{failed}", score)

    pattern = _entry_pattern(st, side, p)
    if pattern is None:
        return EntryOutcome("pattern", "no_entry_pattern", score)
    pat_name, stop_price = pattern

    close = st.close_1m
    assert close is not None
    s = _sign(side)
    stop_dist_pct = s * (close - stop_price) / close * 100
    if stop_dist_pct <= 0:
        return EntryOutcome("pattern", "stop_wrong_side", score)
    stop_dist_pct = min(stop_dist_pct, p.max_stop_distance_pct)
    stop_price = close * (1 - s * stop_dist_pct / 100)
    tp1 = close * (1 + s * stop_dist_pct * p.tp1_r_multiple / 100)

    ok, why = _book_and_impact(st, side, p, close, tp1, order_notional)
    if not ok:
        return EntryOutcome("book" if why.startswith("C") else "impact", why, score)

    rej = hard_rejections(st, side, btc, p, close)
    if rej is not None:
        return EntryOutcome("reject", rej, score)

    intent = TradeIntent(
        symbol=st.symbol,
        side=side,
        entry_price=close,
        stop_price=stop_price,
        tp1_price=tp1,
        room_to_run_score=score,
        notes={"pattern": pat_name, "stop_dist_pct": f"{stop_dist_pct:.3f}"},
        created_at=datetime.now(UTC),
    )
    return EntryOutcome("ok", "entry", score, intent=intent)


# --- async orchestration ---------------------------------------------


class ObserverTask:
    def __init__(
        self,
        cand: Candidate,
        store: MarketStateStore,
        bus: EventBus,
        clock: Clock,
        params: StrategyParams,
        order_notional: float,
    ) -> None:
        self._c = cand
        self._store = store
        self._bus = bus
        self._clock = clock
        self._p = params
        self._notional = order_notional

    async def run(self) -> EntryOutcome:
        deadline = self._clock.now() + self._p.observer_watch_seconds
        while self._clock.now() < deadline:
            st = self._store.get(self._c.symbol)
            if st is not None:
                st.tick(self._clock.now())
                btc = self._store.get(self._p.btc_symbol)
                out = evaluate_entry(st, self._c.side, btc, self._p, self._notional)
                if out.stage == "ok" and out.intent is not None:
                    self._bus.publish(out.intent)
                    return out
                if out.stage == "momentum":
                    return out  # momentum died -> abandon this candidate
            await self._clock.sleep(2.0)
        return EntryOutcome("timeout", "watch_expired")


class Observer:
    """Spawns one ObserverTask per Candidate, deduped by symbol."""

    def __init__(
        self,
        store: MarketStateStore,
        bus: EventBus,
        clock: Clock,
        params: StrategyParams,
        order_notional: float,
    ) -> None:
        self._store = store
        self._bus = bus
        self._clock = clock
        self._p = params
        self._notional = order_notional
        self._sub = bus.subscribe(Candidate)
        self._active: dict[str, asyncio.Task[EntryOutcome]] = {}

    async def run(self) -> None:
        async for event in self._sub:
            assert isinstance(event, Candidate)
            key = f"{event.symbol}:{event.side.value}"
            if key in self._active and not self._active[key].done():
                continue
            task = ObserverTask(event, self._store, self._bus, self._clock, self._p, self._notional)
            self._active[key] = asyncio.create_task(task.run())
            self._active = {k: t for k, t in self._active.items() if not t.done()}
