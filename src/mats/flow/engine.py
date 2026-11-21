"""Live order-flow state for one symbol: who is hitting, what the book does, who is trapped.

Pure and clock-injected (every ``on_*`` takes ``now`` in seconds), so it is unit-testable
and replayable from recorded data. The terminal view (``mats.flow.view``) only reads it.

What it tracks, and why it matters for a scalp entry:
- **Aggressive flow** (market orders): buy $ vs sell $ over 10s/30s/1m/5m and a running
  CVD. This is what actually moves price; resting orders can be faked, fills cannot.
- **Book pressure**: resting bid $ vs ask $ within ±0.25/0.5/1% of mid.
- **Walls**: unusually large resting levels, and what happened to them when price came
  close: *eaten* (price traded through: real, and now broken) or *pulled* (vanished
  before price arrived: likely a fake wall used to steer traders).
- **Absorption**: heavy market selling while price refuses to drop (a hidden buyer is
  soaking it up), or the mirror for buying. Often the best reversal-entry trigger.
- **Big prints and liquidations**: whale market orders and forced closes (squeeze fuel).
- **OI regime**: price vs open-interest change says whether new positions are opening
  or old ones are being forced out.
"""

from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass, field

WINDOWS_S = (10, 30, 60, 300)
BANDS_PCT = (0.25, 0.5, 1.0)


@dataclass
class FlowWindow:
    buy: float = 0.0
    sell: float = 0.0
    n: int = 0

    @property
    def delta(self) -> float:
        return self.buy - self.sell

    @property
    def buy_pct(self) -> float:
        tot = self.buy + self.sell
        return self.buy / tot * 100 if tot else 50.0


@dataclass
class Wall:
    side: str  # "bid" | "ask"
    price: float
    notional: float
    first_seen: float
    last_seen: float
    peak: float


@dataclass
class WallEvent:
    ts: float
    side: str
    price: float
    notional: float
    kind: str  # "pulled" | "eaten" | "new"


@dataclass
class Print:
    ts: float
    side: str  # "buy" | "sell"  (aggressor)
    price: float
    notional: float


@dataclass
class Liq:
    ts: float
    side: str  # side liquidated: "long" | "short"
    price: float
    notional: float


@dataclass
class Signal:
    level: str  # "bull" | "bear" | "warn" | "info"
    text: str


@dataclass
class FlowState:
    symbol: str
    big_print_usd: float | None = None  # None = adaptive (8x median trade, >= $2k)
    wall_mult: float = 6.0  # level >= this x median level size within 2% = wall
    wall_top_n: int = 6  # and among the N biggest levels within 2% of mid

    trades: deque[tuple[float, bool, float, float]] = field(
        default_factory=lambda: deque(maxlen=200_000)
    )  # (ts, is_buy, notional, price)
    cvd_points: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=4000))
    cvd: float = 0.0
    last_price: float = 0.0
    mark: float = 0.0
    funding_pct: float = 0.0
    bids: list[tuple[float, float]] = field(default_factory=list)  # (price, qty) best first
    asks: list[tuple[float, float]] = field(default_factory=list)
    book_ts: float = 0.0
    walls: dict[tuple[str, float], Wall] = field(default_factory=dict)
    wall_events: deque[WallEvent] = field(default_factory=lambda: deque(maxlen=50))
    prints: deque[Print] = field(default_factory=lambda: deque(maxlen=200))
    liqs: deque[Liq] = field(default_factory=lambda: deque(maxlen=200))
    oi: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=400))
    absorption: deque[tuple[float, Signal]] = field(default_factory=lambda: deque(maxlen=20))
    _last_absorb_ts: float = 0.0
    _sizes: deque[float] = field(default_factory=lambda: deque(maxlen=2000))

    # ---- ingest -----------------------------------------------------------------

    def on_trade(self, now: float, price: float, qty: float, is_buy: bool) -> None:
        notional = price * qty
        self.trades.append((now, is_buy, notional, price))
        self.cvd += notional if is_buy else -notional
        self.last_price = price
        self._sizes.append(notional)
        if not self.cvd_points or now - self.cvd_points[-1][0] >= 1.0:
            self.cvd_points.append((now, self.cvd))
        if notional >= self.big_threshold():
            self.prints.append(Print(now, "buy" if is_buy else "sell", price, notional))
        self._trim(now)

    def on_book(self, now: float, bids: list[tuple[float, float]], asks: list[tuple[float, float]]):
        self.bids = sorted(bids, key=lambda x: -x[0])
        self.asks = sorted(asks, key=lambda x: x[0])
        self.book_ts = now
        self._update_walls(now)

    def on_mark(self, mark: float, funding_pct: float) -> None:
        self.mark, self.funding_pct = mark, funding_pct

    def on_liquidation(self, now: float, side_liquidated: str, price: float, qty: float) -> None:
        self.liqs.append(Liq(now, side_liquidated, price, price * qty))

    def on_open_interest(self, now: float, oi_contracts: float) -> None:
        self.oi.append((now, oi_contracts))

    # ---- derived ----------------------------------------------------------------

    def big_threshold(self) -> float:
        if self.big_print_usd:
            return self.big_print_usd
        if len(self._sizes) < 50:
            return float("inf")
        return max(2000.0, 8 * statistics.median(self._sizes))

    def window(self, now: float, seconds: float) -> FlowWindow:
        w = FlowWindow()
        for ts, is_buy, notional, _ in reversed(self.trades):
            if now - ts > seconds:
                break
            if is_buy:
                w.buy += notional
            else:
                w.sell += notional
            w.n += 1
        return w

    def price_change_pct(self, now: float, seconds: float) -> float | None:
        first = None
        for ts, _, _, price in reversed(self.trades):
            if now - ts > seconds:
                break
            first = price
        if first is None or not self.last_price:
            return None
        return (self.last_price / first - 1) * 100

    def range_pct(self, now: float, seconds: float) -> float:
        px = [p for ts, _, _, p in self.trades if now - ts <= seconds]
        if len(px) < 2:
            return 0.0
        return (max(px) / min(px) - 1) * 100

    @property
    def mid(self) -> float:
        if self.bids and self.asks:
            return (self.bids[0][0] + self.asks[0][0]) / 2
        return self.last_price

    @property
    def spread_pct(self) -> float:
        if self.bids and self.asks and self.mid:
            return (self.asks[0][0] - self.bids[0][0]) / self.mid * 100
        return 0.0

    def band(self, pct: float) -> tuple[float, float]:
        """(bid $, ask $) resting within ±pct of mid."""
        m = self.mid
        if not m:
            return 0.0, 0.0
        lo, hi = m * (1 - pct / 100), m * (1 + pct / 100)
        b = sum(p * q for p, q in self.bids if p >= lo)
        a = sum(p * q for p, q in self.asks if p <= hi)
        return b, a

    def oi_change_pct(self, now: float, seconds: float) -> float | None:
        if len(self.oi) < 2:
            return None
        cur = self.oi[-1][1]
        past = next((v for ts, v in self.oi if now - ts <= seconds), None)
        if past is None or not past:
            return None
        return (cur / past - 1) * 100

    def oi_regime(self, now: float, seconds: float = 60) -> str | None:
        d_oi, d_px = self.oi_change_pct(now, seconds), self.price_change_pct(now, seconds)
        if d_oi is None or d_px is None or abs(d_oi) < 0.15 or abs(d_px) < 0.05:
            return None
        if d_px > 0:
            return "new longs opening" if d_oi > 0 else "shorts closing (squeeze)"
        return "new shorts opening" if d_oi > 0 else "longs closing (flush)"

    def liq_sum(self, now: float, seconds: float) -> tuple[float, float]:
        longs = sum(x.notional for x in self.liqs if now - x.ts <= seconds and x.side == "long")
        shorts = sum(x.notional for x in self.liqs if now - x.ts <= seconds and x.side == "short")
        return longs, shorts

    def nearest_walls(self) -> tuple[Wall | None, Wall | None]:
        m = self.mid
        bid = max(
            (w for w in self.walls.values() if w.side == "bid" and w.price < m),
            key=lambda w: w.price,
            default=None,
        )
        ask = min(
            (w for w in self.walls.values() if w.side == "ask" and w.price > m),
            key=lambda w: w.price,
            default=None,
        )
        return bid, ask

    # ---- walls ------------------------------------------------------------------

    def _update_walls(self, now: float) -> None:
        m = self.mid
        if not m:
            return
        near = [
            (s, p, p * q)
            for s, side in (("bid", self.bids), ("ask", self.asks))
            for p, q in side
            if abs(p / m - 1) <= 0.02
        ]
        if len(near) < 6:
            return
        med = statistics.median(n for _, _, n in near)
        b1, a1 = self.band(1.0)
        floor = max(2000.0, 0.03 * (b1 + a1))  # ignore market-maker dust on thin books
        top = sorted((n for _, _, n in near), reverse=True)[: self.wall_top_n]
        cut = top[-1] if top else float("inf")
        current = {
            (s, p): n for s, p, n in near if n >= self.wall_mult * med and n >= floor and n >= cut
        }
        for key, n in current.items():
            w = self.walls.get(key)
            if w:
                w.notional, w.last_seen, w.peak = n, now, max(w.peak, n)
            else:
                self.walls[key] = Wall(key[0], key[1], n, now, now, n)
        for key in [k for k in self.walls if k not in current]:
            w = self.walls.pop(key)
            # only meaningful if it sat there a while and price was close when it vanished
            if now - w.first_seen < 10 or abs(w.price / m - 1) > 0.006:
                continue
            crossed = (w.side == "ask" and self.last_price >= w.price) or (
                w.side == "bid" and self.last_price <= w.price
            )
            # still inside the visible book but shrunk away -> pulled; traded through -> eaten
            self.wall_events.append(
                WallEvent(now, w.side, w.price, w.peak, "eaten" if crossed else "pulled")
            )

    # ---- signals ----------------------------------------------------------------

    def detect_absorption(self, now: float) -> None:
        if now - self._last_absorb_ts < 20:
            return
        if not self.trades or now - self.trades[0][0] < 120:
            return  # need a baseline before calling anything unusual
        w = self.window(now, 30)
        tot = w.buy + w.sell
        base = self.window(now, 300)
        avg30 = (base.buy + base.sell) / 10 if base.n else 0
        if tot < max(1.5 * avg30, 3000):
            return
        move = self.price_change_pct(now, 30) or 0.0
        noise = max(self.range_pct(now, 300) * 0.12, 0.05)
        if w.sell >= 1.8 * w.buy and move > -noise:
            self.absorption.append(
                (
                    now,
                    Signal(
                        "bull",
                        f"ABSORPTION at bid ~{self.last_price:.6g}: ${w.sell:,.0f} sold in 30s "
                        f"but price only {move:+.2f}%. A buyer is soaking it up",
                    ),
                )
            )
            self._last_absorb_ts = now
        elif w.buy >= 1.8 * w.sell and move < noise:
            self.absorption.append(
                (
                    now,
                    Signal(
                        "bear",
                        f"ABSORPTION at ask ~{self.last_price:.6g}: ${w.buy:,.0f} bought in 30s "
                        f"but price only {move:+.2f}%. A seller is capping it",
                    ),
                )
            )
            self._last_absorb_ts = now

    def read(self, now: float) -> list[Signal]:
        """Plain-language read of the current state, strongest first."""
        out: list[Signal] = []
        w10, w60, w300 = self.window(now, 10), self.window(now, 60), self.window(now, 300)
        b05, a05 = self.band(0.5)
        book_bid_pct = b05 / (b05 + a05) * 100 if b05 + a05 else 50
        regime = self.oi_regime(now, 60)
        lq_l, lq_s = self.liq_sum(now, 60)

        bull = bear = 0
        if w60.buy_pct >= 58:
            bull += 1
        if w60.buy_pct <= 42:
            bear += 1
        if w10.buy_pct >= 60 and w60.buy_pct >= 52:
            bull += 1
        if w10.buy_pct <= 40 and w60.buy_pct <= 48:
            bear += 1
        if book_bid_pct >= 60:
            bull += 1
        if book_bid_pct <= 40:
            bear += 1
        if regime in ("new longs opening", "shorts closing (squeeze)"):
            bull += 1
        if regime in ("new shorts opening", "longs closing (flush)"):
            bear += 1

        if bull >= 3 and bull > bear:
            out.append(
                Signal(
                    "bull", f"BUYERS IN CONTROL ({bull}/4): flow, book and OI line up for a long"
                )
            )
        elif bear >= 3 and bear > bull:
            out.append(
                Signal(
                    "bear", f"SELLERS IN CONTROL ({bear}/4): flow, book and OI line up for a short"
                )
            )
        else:
            out.append(Signal("info", f"MIXED (bull {bull} / bear {bear}): no clean side. Wait"))

        # divergence: flow one way, price the other = absorption in slow motion
        mv5 = self.price_change_pct(now, 300)
        if mv5 is not None and w300.n > 50:
            if w300.buy_pct >= 56 and mv5 <= 0:
                out.append(
                    Signal(
                        "bear",
                        f"5m: buyers {w300.buy_pct:.0f}% but price {mv5:+.2f}%. Buying is being sold into",
                    )
                )
            elif w300.buy_pct <= 44 and mv5 >= 0:
                out.append(
                    Signal(
                        "bull",
                        f"5m: sellers {100 - w300.buy_pct:.0f}% but price {mv5:+.2f}%. Selling is being absorbed",
                    )
                )

        if regime:
            lvl = "bull" if regime in ("new longs opening", "shorts closing (squeeze)") else "bear"
            out.append(Signal(lvl, f"OI 1m: {regime}"))
        if lq_s >= 5000 and lq_s > 2 * lq_l:
            out.append(
                Signal(
                    "bull",
                    f"${lq_s:,.0f} SHORTS liquidated in 1m: squeeze fuel, don't short into it",
                )
            )
        if lq_l >= 5000 and lq_l > 2 * lq_s:
            out.append(
                Signal(
                    "bear", f"${lq_l:,.0f} LONGS liquidated in 1m: flush, don't catch the knife yet"
                )
            )
        if self.funding_pct >= 0.05:
            out.append(Signal("warn", f"funding {self.funding_pct:+.3f}%: longs crowded"))
        elif self.funding_pct <= -0.05:
            out.append(Signal("warn", f"funding {self.funding_pct:+.3f}%: shorts crowded"))

        bid_w, ask_w = self.nearest_walls()
        m = self.mid
        if bid_w and m and (m / bid_w.price - 1) * 100 <= 0.6:
            out.append(
                Signal(
                    "info",
                    f"support wall {bid_w.price:.6g} (${bid_w.notional:,.0f}, "
                    f"{(m / bid_w.price - 1) * 100:.2f}% below): long entry just above it, stop just below",
                )
            )
        if ask_w and m and (ask_w.price / m - 1) * 100 <= 0.6:
            out.append(
                Signal(
                    "info",
                    f"resistance wall {ask_w.price:.6g} (${ask_w.notional:,.0f}, "
                    f"{(ask_w.price / m - 1) * 100:.2f}% above): short entry just below it, stop just above",
                )
            )
        for ev in list(self.wall_events)[-3:]:
            if now - ev.ts <= 60 and ev.kind == "pulled":
                out.append(
                    Signal(
                        "warn",
                        f"{ev.side} wall {ev.price:.6g} (${ev.notional:,.0f}) PULLED before price got there: fake support/resistance",
                    )
                )
        out.extend(sig for ts, sig in self.absorption if now - ts <= 120)
        return out

    def _trim(self, now: float) -> None:
        horizon = max(WINDOWS_S) + 5
        while self.trades and now - self.trades[0][0] > horizon:
            self.trades.popleft()
