from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mats.core.indicators import (
    ATR,
    CVD,
    EMA,
    RSI,
    RVOL,
    AnchoredVWAP,
    OpenInterestDelta,
    book_imbalance,
    book_walk_slippage_pct,
    microprice,
    spread_pct,
)
from mats.core.models import BookLevel, Candle, OrderBook, Side, Trade

T0 = datetime(2026, 9, 8, 0, 0, tzinfo=UTC)


def _trade(secs: float, price: float, qty: float, buyer_maker: bool) -> Trade:
    return Trade(
        symbol="X",
        ts=T0 + timedelta(seconds=secs),
        price=price,
        qty=qty,
        is_buyer_maker=buyer_maker,
    )


def _candle(o: float, h: float, low: float, c: float, v: float = 1.0) -> Candle:
    return Candle(
        symbol="X", interval="1m", open_time=T0, open=o, high=h, low=low, close=c, volume=v
    )


def test_ema_converges() -> None:
    ema = EMA(period=3)
    for _ in range(50):
        ema.update(10.0)
    assert ema.value is not None and abs(ema.value - 10.0) < 1e-6


def test_rvol_flags_a_burst() -> None:
    rvol = RVOL(short_s=60, long_s=600)
    for i in range(600):
        rvol.update(float(i), 1.0)  # steady 1/sec
    for i in range(600, 660):
        rvol.update(float(i), 5.0)  # 5x burst
    assert rvol.value is not None and rvol.value > 3.0


def test_rvol_is_none_during_warmup() -> None:
    rvol = RVOL(short_s=60, long_s=600)  # warmup ~540s
    for i in range(120):  # only 2 minutes of history
        rvol.update(float(i), 1.0)
    assert rvol.value is None  # not enough long-window history to trust the baseline
    for i in range(120, 560):
        rvol.update(float(i), 1.0)
    # flat volume => near 1.0 (a small window-boundary bias remains; the point is it is
    # not the ~10x it read before the warm-up guard was added)
    assert rvol.value is not None and abs(rvol.value - 1.0) < 0.2


def test_cvd_sign_and_slope() -> None:
    cvd = CVD(slope_window_s=300)
    cvd.update(_trade(0, 100, 2.0, buyer_maker=False))  # aggressive buy +2
    cvd.update(_trade(10, 100, 1.0, buyer_maker=True))  # aggressive sell -1
    assert cvd.cumulative == 1.0
    cvd.update(_trade(20, 100, 3.0, buyer_maker=False))
    assert cvd.cumulative == 4.0
    assert cvd.slope > 0


def test_rsi_bounds_and_warmup() -> None:
    rsi = RSI(period=14)
    assert rsi.value is None
    for p in [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]:
        rsi.update(float(p))
    assert rsi.value == 100.0  # only gains
    rsi2 = RSI(period=14)
    for p in range(30, 10, -1):  # only losses
        rsi2.update(float(p))
    assert rsi2.value is not None and rsi2.value < 5.0


def test_rsi_sma_seed_matches_wilder_reference() -> None:
    # classic textbook series; RSI(14) after the 15th close ~ 70.53
    closes = [
        44.34,
        44.09,
        44.15,
        43.61,
        44.33,
        44.83,
        45.10,
        45.42,
        45.84,
        46.08,
        45.89,
        46.03,
        45.61,
        46.28,
        46.28,
    ]
    rsi = RSI(period=14)
    for c in closes[:-1]:
        rsi.update(c)
    assert rsi.value is None  # 13 changes, not warm
    rsi.update(closes[-1])
    assert rsi.value is not None and abs(rsi.value - 70.53) < 0.5


def test_cvd_tick_decays_slope_when_tape_quiet() -> None:
    cvd = CVD(slope_window_s=300)
    for i in range(10):
        cvd.update(_trade(i * 10, 100, 1.0, buyer_maker=False))
    assert cvd.slope > 0
    cvd.tick(T0.timestamp() + 100_000)  # long after every point aged out
    assert cvd.slope == 0.0


def test_atr_true_range() -> None:
    atr = ATR(period=2)
    atr.update(_candle(10, 12, 9, 11))  # tr = 3
    atr.update(_candle(11, 15, 11, 14))  # tr = max(4, 4, 0) = 4
    assert atr.value == 3.5


def test_anchored_vwap() -> None:
    v = AnchoredVWAP()
    v.update(10.0, 1.0)
    v.update(20.0, 3.0)
    assert v.value == (10 + 60) / 4


def test_oi_delta() -> None:
    oi = OpenInterestDelta(window_s=900)
    oi.update(0.0, 1000.0)
    oi.update(600.0, 1300.0)
    assert oi.value == 300.0


def test_book_math() -> None:
    book = OrderBook(
        symbol="X",
        ts=T0,
        bids=[BookLevel(price=99, qty=8), BookLevel(price=98, qty=5)],
        asks=[BookLevel(price=101, qty=2), BookLevel(price=102, qty=5)],
    )
    imb = book_imbalance(book, levels=2)
    assert imb is not None and imb > 0  # bid-heavy
    mp = microprice(book)
    assert mp is not None and 99 < mp < 101
    sp = spread_pct(book)
    assert sp is not None and abs(sp - 2.0) < 1e-6


def test_book_walk_slippage_thin_book_returns_none() -> None:
    book = OrderBook(
        symbol="X",
        ts=T0,
        bids=[BookLevel(price=99, qty=1)],
        asks=[BookLevel(price=101, qty=1)],  # only 101 notional available
    )
    assert book_walk_slippage_pct(book, Side.LONG, notional=10_000) is None


def test_book_walk_slippage_value() -> None:
    book = OrderBook(
        symbol="X",
        ts=T0,
        bids=[],
        asks=[BookLevel(price=100, qty=1), BookLevel(price=110, qty=100)],
    )
    # buy 200 notional: 100 at price 100 (1 unit), 100 at price 110 (~0.909 units)
    slip = book_walk_slippage_pct(book, Side.LONG, notional=200)
    assert slip is not None and slip > 0
