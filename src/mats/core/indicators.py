"""Rolling indicators for Rule Set v1.1.

Stateful incremental estimators (`update(...)` then read a property) plus pure functions
for order-book math. Time is passed in explicitly (seconds) so replay is deterministic.
"""

from __future__ import annotations

from collections import deque

from mats.core.models import Candle, OrderBook, Side, Trade


class EMA:
    def __init__(self, period: int) -> None:
        self.alpha = 2.0 / (period + 1)
        self.value: float | None = None

    def update(self, x: float) -> float:
        self.value = x if self.value is None else self.alpha * x + (1 - self.alpha) * self.value
        return self.value


class RollingSum:
    """Sum of (value) over a trailing time window, keyed by timestamp in seconds."""

    def __init__(self, window_s: float) -> None:
        self.window_s = window_s
        self._items: deque[tuple[float, float]] = deque()
        self.total = 0.0

    def update(self, ts: float, value: float) -> None:
        self._items.append((ts, value))
        self.total += value
        self._evict(ts)

    def _evict(self, now: float) -> None:
        cutoff = now - self.window_s
        while self._items and self._items[0][0] < cutoff:
            _, v = self._items.popleft()
            self.total -= v

    def __len__(self) -> int:
        return len(self._items)


class RVOL:
    """Relative volume: volume in the trailing `short_s` vs the average `short_s` block
    over the trailing `long_s`. >1 means unusually active.
    """

    def __init__(self, short_s: float, long_s: float, warmup_frac: float = 0.9) -> None:
        self.short = RollingSum(short_s)
        self.long = RollingSum(long_s)
        self._short_s = short_s
        self._long_s = long_s
        self._warmup_s = long_s * warmup_frac
        self._first_ts: float | None = None
        self._last_ts: float | None = None

    def update(self, ts: float, volume: float) -> None:
        if self._first_ts is None:
            self._first_ts = ts
        self._last_ts = ts
        self.short.update(ts, volume)
        self.long.update(ts, volume)

    @property
    def value(self) -> float | None:
        # Until the long window has actually accumulated ~long_s of history, its total
        # under-represents the true baseline and RVOL reads several-x too high.
        if self._first_ts is None or self._last_ts is None:
            return None
        if self._last_ts - self._first_ts < self._warmup_s:
            return None
        blocks = self._long_s / self._short_s
        baseline = self.long.total / blocks
        if baseline <= 0:
            return None
        return self.short.total / baseline


class CVD:
    """Cumulative volume delta from the trade tape, with a trailing-window slope.

    delta = aggressive-buy volume - aggressive-sell volume.
    A Trade with is_buyer_maker=True means the aggressor was a seller.
    """

    def __init__(self, slope_window_s: float = 300.0) -> None:
        self.cumulative = 0.0
        self._window_s = slope_window_s
        self._points: deque[tuple[float, float]] = deque()

    def update(self, trade: Trade) -> None:
        signed = trade.qty if not trade.is_buyer_maker else -trade.qty
        self.cumulative += signed
        ts = trade.ts.timestamp()
        self._points.append((ts, self.cumulative))
        cutoff = ts - self._window_s
        while len(self._points) > 2 and self._points[0][0] < cutoff:
            self._points.popleft()

    @property
    def slope(self) -> float:
        """Change in cumulative delta per second over the trailing window."""
        if len(self._points) < 2:
            return 0.0
        (t0, v0), (t1, v1) = self._points[0], self._points[-1]
        dt = t1 - t0
        return (v1 - v0) / dt if dt > 0 else 0.0


class RSI:
    """Wilder's RSI over `period` closes. `value` is None until warmed up."""

    def __init__(self, period: int = 14) -> None:
        self.period = period
        self._prev: float | None = None
        self._avg_gain: float | None = None
        self._avg_loss: float | None = None
        self._count = 0

    def update(self, close: float) -> None:
        if self._prev is None:
            self._prev = close
            return
        change = close - self._prev
        self._prev = close
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        self._count += 1
        if self._avg_gain is None or self._avg_loss is None:
            # simple average seed over the first `period` changes
            g = self._avg_gain or 0.0
            n = self._avg_loss or 0.0
            self._avg_gain = g + gain / self.period
            self._avg_loss = n + loss / self.period
        else:
            self._avg_gain = (self._avg_gain * (self.period - 1) + gain) / self.period
            self._avg_loss = (self._avg_loss * (self.period - 1) + loss) / self.period

    @property
    def value(self) -> float | None:
        if self._count < self.period or self._avg_gain is None or self._avg_loss is None:
            return None
        if self._avg_loss == 0:
            return 100.0
        rs = self._avg_gain / self._avg_loss
        return 100.0 - 100.0 / (1.0 + rs)


class ATR:
    """Average true range over the last `period` completed candles."""

    def __init__(self, period: int = 14) -> None:
        self.period = period
        self._trs: deque[float] = deque(maxlen=period)
        self._prev_close: float | None = None

    def update(self, c: Candle) -> None:
        if self._prev_close is None:
            tr = c.high - c.low
        else:
            tr = max(c.high - c.low, abs(c.high - self._prev_close), abs(c.low - self._prev_close))
        self._trs.append(tr)
        self._prev_close = c.close

    @property
    def value(self) -> float | None:
        if not self._trs:
            return None
        return sum(self._trs) / len(self._trs)


class AnchoredVWAP:
    """Volume-weighted average price since an explicit anchor (e.g. the candle a move began)."""

    def __init__(self) -> None:
        self._pv = 0.0
        self._v = 0.0

    def reset(self) -> None:
        self._pv = 0.0
        self._v = 0.0

    def update(self, price: float, volume: float) -> None:
        self._pv += price * volume
        self._v += volume

    @property
    def value(self) -> float | None:
        return self._pv / self._v if self._v > 0 else None


class OpenInterestDelta:
    """Signed change in open interest over a trailing window."""

    def __init__(self, window_s: float = 900.0) -> None:
        self.window_s = window_s
        self._points: deque[tuple[float, float]] = deque()

    def update(self, ts: float, oi: float) -> None:
        self._points.append((ts, oi))
        cutoff = ts - self.window_s
        while len(self._points) > 1 and self._points[0][0] < cutoff:
            self._points.popleft()

    @property
    def value(self) -> float | None:
        if len(self._points) < 2:
            return None
        return self._points[-1][1] - self._points[0][1]


# --- pure order-book functions -------------------------------------------------


def book_imbalance(book: OrderBook, levels: int = 10) -> float | None:
    """(bidVol - askVol) / (bidVol + askVol) over the top `levels`. Range [-1, 1]."""
    bid = sum(lvl.qty for lvl in book.bids[:levels])
    ask = sum(lvl.qty for lvl in book.asks[:levels])
    total = bid + ask
    if total <= 0:
        return None
    return (bid - ask) / total


def microprice(book: OrderBook) -> float | None:
    """Best-bid/ask weighted by the opposite side's size — a fairer mid."""
    if not book.bids or not book.asks:
        return None
    bid, ask = book.bids[0], book.asks[0]
    denom = bid.qty + ask.qty
    if denom <= 0:
        return None
    return (bid.price * ask.qty + ask.price * bid.qty) / denom


def spread_pct(book: OrderBook) -> float | None:
    if not book.bids or not book.asks:
        return None
    bid, ask = book.bids[0].price, book.asks[0].price
    mid = (bid + ask) / 2
    return (ask - bid) / mid * 100 if mid > 0 else None


def book_walk_slippage_pct(book: OrderBook, side: Side, notional: float) -> float | None:
    """Simulate a market order for `notional` (quote) and return the % the average fill
    price sits away from the touch. Used by the self-impact guard (S2).
    """
    levels = book.asks if side is Side.LONG else book.bids
    if not levels:
        return None
    touch = levels[0].price
    remaining = notional
    spent = 0.0
    filled_base = 0.0
    for lvl in levels:
        lvl_notional = lvl.price * lvl.qty
        take = min(remaining, lvl_notional)
        base = take / lvl.price
        spent += take
        filled_base += base
        remaining -= take
        if remaining <= 0:
            break
    if remaining > 0 or filled_base <= 0:
        return None  # book too thin to fill the order
    avg = spent / filled_base
    return abs(avg - touch) / touch * 100
