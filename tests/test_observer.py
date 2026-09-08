from __future__ import annotations

from datetime import UTC, datetime

from mats.agents.observer import evaluate_entry, momentum_alive, room_to_run
from mats.agents.symbol_state import SymbolState
from mats.config import StrategyParams
from mats.core.models import BookLevel, Candle, InstrumentStats, OrderBook, Side, Trade

BASE = 1_700_000_000

# price path: flat warm-up, then a 3-leg up-move with 3 shallow pullbacks, ending
# mid-pullback with a green resume candle.
_PATH: list[tuple[int, int, float, float]] = [
    (0, 70, 100.0, 100.0),
    (70, 78, 100.0, 103.0),  # leg 1
    (78, 81, 103.0, 101.7),  # pullback 1
    (81, 89, 101.7, 104.8),  # leg 2
    (89, 92, 104.8, 103.5),  # pullback 2
    (92, 100, 103.5, 106.8),  # leg 3
    (100, 103, 106.8, 105.95),  # pullback 3 (~26% retrace, running low, unconfirmed)
]
LAST = 103


def _dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=UTC)


def _price(i: int) -> float:
    for s0, s1, p0, p1 in _PATH:
        if s0 <= i < s1:
            return p0 + (p1 - p0) * (i - s0) / (s1 - s0)
    return _PATH[-1][3]


def build_entry_ready_long(p: StrategyParams, symbol: str = "MOVUSDT") -> SymbolState:
    s = SymbolState(symbol, p)
    for i in range(LAST):
        px = _price(i)
        nxt = _price(i + 1)
        rng = 0.1 if i < 70 else 0.45  # ATR expands with the move
        vol = 100.0 if i < 70 else 150.0
        s.on_candle(
            Candle(
                symbol=symbol,
                interval="1m",
                open_time=_dt(BASE + i * 60),
                open=px,
                high=max(px, nxt) + rng,
                low=min(px, nxt) - rng,
                close=nxt,
                volume=vol,
            )
        )
    # green resume candle with elevated volume, ~0.1% up (no new zigzag pivot yet)
    s.on_candle(
        Candle(
            symbol=symbol,
            interval="1m",
            open_time=_dt(BASE + LAST * 60),
            open=105.95,
            high=106.2,
            low=105.85,
            close=106.05,
            volume=600.0,
        )
    )
    now = BASE + (LAST + 1) * 60
    for k in range(240):  # baseline tape across the 4h before now (tps denominator)
        s.on_trade(
            Trade(
                symbol=symbol,
                ts=_dt(now - 14_400 + k * 60),
                price=100.0,
                qty=0.1,
                is_buyer_maker=False,
            )
        )
    for k in range(60):  # older aggressive buys (CVD history / divergence window)
        s.on_trade(
            Trade(
                symbol=symbol,
                ts=_dt(now - 500 + k * 4),
                price=104.0 + k * 0.02,
                qty=1.0,
                is_buyer_maker=False,
            )
        )
    for k in range(220):  # dense aggressive buys inside the last 55s -> real 60s flow
        s.on_trade(
            Trade(
                symbol=symbol,
                ts=_dt(now - 55 + k * 0.25),
                price=105.6 + k * 0.002,
                qty=20.0,
                is_buyer_maker=False,
            )
        )
    s.on_stats(_stats(symbol, _dt(now - 800), 105.7, 1000.0))
    s.on_stats(_stats(symbol, _dt(now), 105.7, 1300.0))  # OI rising
    s.on_book(
        OrderBook(
            symbol=symbol,
            ts=_dt(now),
            bids=[BookLevel(price=105.9 - j * 0.1, qty=400.0) for j in range(20)],
            asks=[BookLevel(price=106.1 + j * 0.1, qty=120.0) for j in range(20)],
        )
    )
    s.tick(now)
    return s


def _stats(sym: str, ts: datetime, price: float, oi: float) -> InstrumentStats:
    return InstrumentStats(
        symbol=sym,
        ts=ts,
        last_price=price,
        mark_price=price,
        funding_rate_pct=0.01,
        open_interest=oi,
        quote_volume_24h=20_000_000.0,
    )


def _btc_flat(p: StrategyParams) -> SymbolState:
    b = SymbolState("BTCUSDT", p)
    for i in range(30):
        b.on_candle(
            Candle(
                symbol="BTCUSDT",
                interval="1m",
                open_time=_dt(BASE + i * 60),
                open=60000,
                high=60010,
                low=59990,
                close=60000,
                volume=1.0,
            )
        )
    return b


def test_momentum_alive_true_for_the_fixture() -> None:
    p = StrategyParams()
    s = build_entry_ready_long(p)
    ok, why = momentum_alive(s, Side.LONG, p)
    assert ok, why


def test_room_to_run_scores_well() -> None:
    p = StrategyParams()
    s = build_entry_ready_long(p)
    score, checks = room_to_run(s, Side.LONG, p)
    assert score >= p.room_to_run_min_score, checks


def test_evaluate_entry_emits_intent() -> None:
    p = StrategyParams()
    s = build_entry_ready_long(p)
    out = evaluate_entry(s, Side.LONG, _btc_flat(p), p, order_notional=15_000.0)
    assert out.stage == "ok", (out.stage, out.reason)
    assert out.intent is not None
    intent = out.intent
    assert intent.side is Side.LONG
    assert intent.stop_price < intent.entry_price < intent.tp1_price
    # TP1 is ~1.3x the stop distance
    r = intent.entry_price - intent.stop_price
    assert abs((intent.tp1_price - intent.entry_price) / r - p.tp1_r_multiple) < 0.05


def test_reject_when_order_too_big_for_flow() -> None:
    p = StrategyParams()
    s = build_entry_ready_long(p)
    out = evaluate_entry(s, Side.LONG, _btc_flat(p), p, order_notional=5_000_000.0)
    assert out.stage in {"book", "impact"}
    assert out.reason in {"S1_size_vs_flow", "S2_slippage"}


def test_reject_when_btc_dislocating_against() -> None:
    p = StrategyParams()
    s = build_entry_ready_long(p)
    btc = SymbolState("BTCUSDT", p)
    for i in range(30):
        px = 60000.0 - ((i - 23) * 400 if i >= 24 else 0)  # sharp BTC drop in the last 6 min
        btc.on_candle(
            Candle(
                symbol="BTCUSDT",
                interval="1m",
                open_time=_dt(BASE + i * 60),
                open=px,
                high=px + 5,
                low=px - 5,
                close=px,
                volume=1.0,
            )
        )
    out = evaluate_entry(s, Side.LONG, btc, p, order_notional=15_000.0)
    assert out.stage == "reject" and out.reason == "R5_btc_dislocating"
