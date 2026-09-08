from __future__ import annotations

from datetime import UTC, datetime

from mats.agents.scanner import Scanner, check_eligible
from mats.agents.symbol_state import SymbolState
from mats.config import StrategyParams
from mats.core.models import Candle, InstrumentStats, MarkPrice, Side, Trade

BASE = 1_700_000_000
N = 260


def _dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=UTC)


_MOVE_SEGMENTS = [  # (start_min, end_min, start_price, end_price) — up-move with pullbacks
    (200, 216, 100.0, 105.0),
    (216, 224, 105.0, 103.0),
    (224, 240, 103.0, 109.0),
    (240, 248, 109.0, 106.5),
    (248, 256, 106.5, 112.0),
    (256, N, 112.0, 111.0),
]


def _price(i: int) -> float:
    if i < 200:
        return 100.0 + (0.3 if i % 2 else -0.3)  # gentle dither so RSI has a real baseline
    for s0, s1, p0, p1 in _MOVE_SEGMENTS:
        if s0 <= i < s1:
            return p0 + (p1 - p0) * (i - s0) / (s1 - s0)
    return 111.0


def build_hot_long(params: StrategyParams, symbol: str = "HOTUSDT") -> SymbolState:
    """Synthesize a SymbolState that satisfies every Layer 0/1 long check."""
    s = SymbolState(symbol, params)

    for i in range(N):
        ts = BASE + i * 60
        price = _price(i)
        rng = 0.05 if i < 200 else 0.6
        vol = 100.0 if i < 200 else (400.0 if i >= N - 15 else 120.0)
        s.on_candle(
            Candle(
                symbol=symbol,
                interval="1m",
                open_time=_dt(ts),
                open=price,
                high=price + rng,
                low=price - rng,
                close=price,
                volume=vol,
            )
        )

    # trades: ~1/min for 4h of aggressive buys, then a 5-min burst
    for i in range(240):
        ts = BASE + i * 60
        s.on_trade(Trade(symbol=symbol, ts=_dt(ts), price=100.0, qty=1.0, is_buyer_maker=False))
    for j in range(24):
        ts = BASE + (N - 5) * 60 + j * 12
        price = 111.0 + j * 0.05
        s.on_trade(Trade(symbol=symbol, ts=_dt(ts), price=price, qty=2.0, is_buyer_maker=False))

    now = BASE + N * 60
    s.on_stats(
        InstrumentStats(
            symbol=symbol,
            ts=_dt(now - 800),
            last_price=100.0,
            mark_price=100.0,
            funding_rate_pct=0.01,
            open_interest=1000.0,
            quote_volume_24h=20_000_000.0,
        )
    )
    s.on_stats(
        InstrumentStats(
            symbol=symbol,
            ts=_dt(now),
            last_price=112.0,
            mark_price=112.0,
            funding_rate_pct=0.01,
            open_interest=1200.0,  # OI rising => H8
            quote_volume_24h=20_000_000.0,
        )
    )
    s.on_mark(MarkPrice(symbol=symbol, ts=_dt(now), mark_price=112.0, funding_rate_pct=0.01))
    return s


def test_hot_long_passes_all_checks() -> None:
    p = StrategyParams()
    s = build_hot_long(p)
    now = BASE + N * 60 + 30

    assert s.ret_5m and s.ret_5m > 0
    assert s.ret_1h and p.ret_1h_band_pct[0] <= s.ret_1h <= p.ret_1h_band_pct[1]
    assert s.rvol_5m and s.rvol_5m >= p.min_rvol_5m
    assert s.rvol_15m and s.rvol_15m >= p.min_rvol_15m
    assert s.tps_ratio and s.tps_ratio >= p.min_tps_ratio
    assert s.atr_expanding is True
    assert s.oi_delta_15m == 200.0
    assert s.cvd_divergence is False
    assert s.cvd_slope > 0

    ok, why = check_eligible(s, p, now)
    assert ok, why


def test_scanner_evaluate_emits_and_ranks() -> None:
    p = StrategyParams()
    from mats.core.bus import EventBus
    from mats.core.clock import SimClock

    sc = Scanner(EventBus(), p, SimClock())
    sc._states["HOTUSDT"] = build_hot_long(p, "HOTUSDT")
    sc._states["WARMUSDT"] = build_hot_long(p, "WARMUSDT")
    # a dead coin: low volume => never eligible
    dead = SymbolState("DEADUSDT", p)
    dead.on_stats(
        InstrumentStats(
            symbol="DEADUSDT",
            ts=_dt(BASE),
            last_price=1.0,
            mark_price=1.0,
            funding_rate_pct=0.0,
            open_interest=1.0,
            quote_volume_24h=1_000.0,
        )
    )
    sc._states["DEADUSDT"] = dead

    cands = sc.evaluate(BASE + N * 60 + 30)
    longs = [c for c in cands if c.side is Side.LONG]
    assert {c.symbol for c in longs} == {"HOTUSDT", "WARMUSDT"}
    assert all(c.symbol != "DEADUSDT" for c in cands)
    assert longs == sorted(longs, key=lambda c: c.hotness, reverse=True)


def test_short_side_is_mirror() -> None:
    p = StrategyParams()
    s = build_hot_long(p)
    from mats.agents.scanner import _directional_checks

    ok_long, _ = _directional_checks(s, p, Side.LONG, rank=1)
    ok_short, why_short = _directional_checks(s, p, Side.SHORT, rank=1)
    assert ok_long is True
    assert ok_short is False and why_short == "H1_alignment"  # an up-mover is not a short
