from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mats.core.indicators import (
    ATR,
    CVD,
    EMA,
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


def test_cvd_sign_and_slope() -> None:
    cvd = CVD(slope_window_s=300)
    cvd.update(_trade(0, 100, 2.0, buyer_maker=False))  # aggressive buy +2
    cvd.update(_trade(10, 100, 1.0, buyer_maker=True))  # aggressive sell -1
    assert cvd.cumulative == 1.0
    cvd.update(_trade(20, 100, 3.0, buyer_maker=False))
    assert cvd.cumulative == 4.0
    assert cvd.slope > 0


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
