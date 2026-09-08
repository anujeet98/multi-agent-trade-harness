"""Per-symbol rolling state the Scanner maintains from the event bus.

Fed incrementally by feed events; exposes the derived quantities Rule Set v1.1 Layer 0/1
needs. Everything is time-driven (seconds) so replay is deterministic. Values are ``None``
until the relevant indicator has warmed up — callers must treat ``None`` as "not eligible".
"""

from __future__ import annotations

from collections import deque

from mats.config import StrategyParams
from mats.core.indicators import (
    ATR,
    CVD,
    RSI,
    RVOL,
    OpenInterestDelta,
    book_imbalance,
    spread_pct,
)
from mats.core.models import Candle, InstrumentStats, Liquidation, MarkPrice, OrderBook, Trade


class SymbolState:
    def __init__(self, symbol: str, params: StrategyParams) -> None:
        self.symbol = symbol
        self._p = params

        # 1m candle history: (open_time_epoch_s, close)
        self._closes: deque[tuple[float, float]] = deque(maxlen=180)  # ~3h of 1m
        self._atr = ATR(period=14)
        self._atr_hist: deque[tuple[float, float]] = deque(maxlen=180)  # (ts, atr)
        self._rsi5 = RSI(period=14)
        self._last_5m_bucket: int | None = None

        self._rvol = RVOL(short_s=300.0, long_s=params.rvol_baseline_window_s)
        self._rvol15 = RVOL(short_s=900.0, long_s=params.rvol_baseline_window_s)

        # trade-driven
        self._cvd = CVD(slope_window_s=params.cvd_window_s)
        self._trade_ts_5m: deque[float] = deque()
        self._trade_ts_4h: deque[float] = deque()
        self._cvd_samples: deque[tuple[float, float, float]] = deque(maxlen=600)  # ts, price, cvd

        # derivatives / snapshot
        self._oi = OpenInterestDelta(window_s=params.oi_delta_window_s)
        self.last_price: float | None = None
        self.mark_price: float | None = None
        self.funding_pct: float | None = None
        self.next_funding_ts: float | None = None
        self.quote_volume_24h: float | None = None
        self.age_days: float | None = None
        self.gainer_rank: int | None = None  # set by the scanner from InstrumentStats ranking

        self._book: OrderBook | None = None
        self.last_liquidation: Liquidation | None = None

    # --- ingest -------------------------------------------------------------

    def on_candle(self, c: Candle) -> None:
        if c.interval != "1m":
            return
        ts = c.open_time.timestamp()
        self._closes.append((ts, c.close))
        self._atr.update(c)
        if self._atr.value is not None:
            self._atr_hist.append((ts, self._atr.value))
        self._rvol.update(ts, c.volume)
        self._rvol15.update(ts, c.volume)
        bucket = int(ts // 300)
        if bucket != self._last_5m_bucket:
            self._rsi5.update(c.close)
            self._last_5m_bucket = bucket

    def on_trade(self, t: Trade) -> None:
        ts = t.ts.timestamp()
        self._cvd.update(t)
        self.last_price = t.price
        self._trade_ts_5m.append(ts)
        self._trade_ts_4h.append(ts)
        self._cvd_samples.append((ts, t.price, self._cvd.cumulative))
        self.tick(ts)

    def tick(self, now_ts: float) -> None:
        """Evict time-windowed data relative to `now`, not just on the next event. The
        scanner calls this before every evaluation so a coin whose tape went quiet stops
        showing a stale tps_ratio / CVD slope and correctly drops out of the candidates.
        """
        for dq, window in ((self._trade_ts_5m, 300.0), (self._trade_ts_4h, 14_400.0)):
            cutoff = now_ts - window
            while dq and dq[0] < cutoff:
                dq.popleft()
        self._cvd.tick(now_ts)
        cutoff = now_ts - 2 * self._p.cvd_window_s
        while self._cvd_samples and self._cvd_samples[0][0] < cutoff:
            self._cvd_samples.popleft()

    def on_mark(self, m: MarkPrice) -> None:
        self.mark_price = m.mark_price
        self.funding_pct = m.funding_rate_pct
        self.next_funding_ts = m.next_funding_time.timestamp() if m.next_funding_time else None

    def on_stats(self, s: InstrumentStats) -> None:
        self.last_price = s.last_price
        self.mark_price = s.mark_price
        self.funding_pct = s.funding_rate_pct
        self.quote_volume_24h = s.quote_volume_24h
        self._oi.update(s.ts.timestamp(), s.open_interest)

    def on_book(self, b: OrderBook) -> None:
        self._book = b

    def on_liquidation(self, liq: Liquidation) -> None:
        self.last_liquidation = liq

    # --- derived ----------------------------------------------------------

    def _ret_pct(self, seconds: float) -> float | None:
        if len(self._closes) < 2:
            return None
        now_ts, now_close = self._closes[-1]
        target = now_ts - seconds
        past: float | None = None
        for ts, close in self._closes:
            if ts <= target:
                past = close
            else:
                break
        if past is None or past <= 0:
            return None
        return (now_close / past - 1.0) * 100.0

    @property
    def ret_5m(self) -> float | None:
        return self._ret_pct(300.0)

    @property
    def ret_15m(self) -> float | None:
        return self._ret_pct(900.0)

    @property
    def ret_1h(self) -> float | None:
        return self._ret_pct(3600.0)

    @property
    def rvol_5m(self) -> float | None:
        return self._rvol.value

    @property
    def rvol_15m(self) -> float | None:
        return self._rvol15.value

    @property
    def tps_ratio(self) -> float | None:
        if len(self._trade_ts_4h) < 20:
            return None
        short_rate = len(self._trade_ts_5m) / 5.0
        base_rate = len(self._trade_ts_4h) / 240.0
        if base_rate <= 0:
            return None
        return short_rate / base_rate

    @property
    def atr_expanding(self) -> bool | None:
        if not self._atr_hist:
            return None
        now_ts, now_atr = self._atr_hist[-1]
        past = [a for ts, a in self._atr_hist if ts <= now_ts - 3600.0]
        if not past:
            return None
        return now_atr > past[-1]

    @property
    def oi_delta_15m(self) -> float | None:
        return self._oi.value

    @property
    def cvd_slope(self) -> float:
        return self._cvd.slope

    @property
    def cvd_divergence(self) -> bool | None:
        """price prints a higher high over the window but CVD does not (bearish for longs).

        Symmetric: mirror for shorts is a lower low in price without a lower low in CVD.
        v1: compares the latest sample to the extreme of the window's first half.
        """
        if len(self._cvd_samples) < 20:
            return None
        half = len(self._cvd_samples) // 2
        first = list(self._cvd_samples)[:half]
        _, price_now, cvd_now = self._cvd_samples[-1]
        hi_price = max(p for _, p, _ in first)
        cvd_at_hi = next(c for _, p, c in first if p == hi_price)
        lo_price = min(p for _, p, _ in first)
        cvd_at_lo = next(c for _, p, c in first if p == lo_price)
        long_div = price_now > hi_price and cvd_now <= cvd_at_hi
        short_div = price_now < lo_price and cvd_now >= cvd_at_lo
        return long_div or short_div

    @property
    def rsi_5m(self) -> float | None:
        return self._rsi5.value

    @property
    def spread_pct(self) -> float | None:
        return spread_pct(self._book) if self._book else None

    @property
    def book_imbalance(self) -> float | None:
        return book_imbalance(self._book, levels=10) if self._book else None

    @property
    def mark_last_gap_pct(self) -> float | None:
        if self.last_price and self.mark_price and self.last_price > 0:
            return abs(self.mark_price - self.last_price) / self.last_price * 100.0
        return None
