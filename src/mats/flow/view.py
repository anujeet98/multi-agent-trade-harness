"""Terminal dashboard for a FlowState (rich). Read-only: never mutates the state."""

from __future__ import annotations

import time

from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mats.flow.engine import BANDS_PCT, WINDOWS_S, FlowState

SPARK = "▁▂▃▄▅▆▇█"
COLORS = {"bull": "green", "bear": "red", "warn": "yellow", "info": "cyan"}


def usd(x: float) -> str:
    a = abs(x)
    s = f"{a / 1e6:.2f}M" if a >= 1e6 else f"{a / 1e3:.1f}k" if a >= 1e3 else f"{a:.0f}"
    return ("-" if x < 0 else "") + "$" + s


def bar(pct: float, width: int = 20) -> Text:
    """Green (buy) vs red (sell) split bar for a buy share in %."""
    g = round(max(0.0, min(100.0, pct)) / 100 * width)
    return Text("█" * g, style="green") + Text("█" * (width - g), style="red")


def sparkline(values: list[float], width: int = 48) -> Text:
    if len(values) < 2:
        return Text("collecting…", style="dim")
    step = max(1, len(values) // width)
    v = values[::step][-width:]
    lo, hi = min(v), max(v)
    span = hi - lo or 1.0
    chars = "".join(SPARK[int((x - lo) / span * (len(SPARK) - 1))] for x in v)
    style = "green" if v[-1] >= v[0] else "red"
    return Text(chars, style=style)


def header(s: FlowState, now: float) -> Panel:
    ch1 = s.price_change_pct(now, 60)
    ch5 = s.price_change_pct(now, 300)
    oi1 = s.oi_change_pct(now, 60)
    oi5 = s.oi_change_pct(now, 300)
    t = Text()
    t.append(f"{s.symbol}  ", style="bold")
    t.append(f"{s.last_price:.6g}  ", style="bold white")
    for label, v in (("1m", ch1), ("5m", ch5)):
        if v is not None:
            t.append(f"{label} {v:+.2f}%  ", style="green" if v >= 0 else "red")
    t.append(f"spread {s.spread_pct:.3f}%  funding {s.funding_pct:+.4f}%  ", style="dim")
    if s.oi:
        t.append(f"OI {s.oi[-1][1]:,.0f}", style="white")
        for label, v in (("1m", oi1), ("5m", oi5)):
            if v is not None:
                t.append(f" {label} {v:+.2f}%", style="green" if v >= 0 else "red")
    t.append(f"   {time.strftime('%H:%M:%S')}", style="dim")
    return Panel(t, padding=(0, 1))


def flow_panel(s: FlowState, now: float) -> Panel:
    tb = Table.grid(padding=(0, 1))
    for _ in range(5):
        tb.add_column()
    tb.add_row(
        *(
            Text(h, style="bold dim")
            for h in ("window", "buy $", "sell $", "delta", "buyers vs sellers")
        )
    )
    for sec in WINDOWS_S:
        w = s.window(now, sec)
        label = f"{sec}s" if sec < 60 else f"{sec // 60}m"
        tb.add_row(
            label,
            Text(usd(w.buy), style="green"),
            Text(usd(w.sell), style="red"),
            Text(usd(w.delta), style="green" if w.delta >= 0 else "red"),
            bar(w.buy_pct) + Text(f" {w.buy_pct:.0f}%"),
        )
    cvd = [v for _, v in s.cvd_points if now - _ <= 300]
    body = Group(tb, Text(""), Text("CVD 5m (running buy − sell): ", style="dim") + sparkline(cvd))
    return Panel(body, title="aggressive flow (market orders)", border_style="blue")


def book_panel(s: FlowState) -> Panel:
    tb = Table.grid(padding=(0, 1))
    for _ in range(4):
        tb.add_column()
    tb.add_row(*(Text(h, style="bold dim") for h in ("band", "bids $", "asks $", "bid share")))
    for pct in BANDS_PCT:
        b, a = s.band(pct)
        share = b / (b + a) * 100 if b + a else 50
        tb.add_row(
            f"±{pct}%",
            Text(usd(b), style="green"),
            Text(usd(a), style="red"),
            bar(share, 16) + Text(f" {share:.0f}%"),
        )

    ladder = Table.grid(padding=(0, 1))
    ladder.add_column(justify="right")
    ladder.add_column()
    ladder.add_column()
    walls = {w.price for w in s.walls.values()}
    top = max([p * q for p, q in s.asks[:8] + s.bids[:8]] or [1])
    for p, q in reversed(s.asks[:8]):
        n = p * q
        mark = " ◀ WALL" if p in walls else ""
        ladder.add_row(
            Text(f"{p:.6g}", style="red"),
            Text("▇" * max(1, round(n / top * 18)), style="red"),
            Text(usd(n) + mark, style="bold red" if mark else "dim"),
        )
    ladder.add_row(
        Text(f"{s.mid:.6g}", style="bold white"), Text("── mid ──", style="dim"), Text("")
    )
    for p, q in s.bids[:8]:
        n = p * q
        mark = " ◀ WALL" if p in walls else ""
        ladder.add_row(
            Text(f"{p:.6g}", style="green"),
            Text("▇" * max(1, round(n / top * 18)), style="green"),
            Text(usd(n) + mark, style="bold green" if mark else "dim"),
        )
    return Panel(Group(tb, Text(""), ladder), title="order book (resting)", border_style="magenta")


def walls_panel(s: FlowState, now: float) -> Panel:
    m = s.mid or 1
    rows = sorted(s.walls.values(), key=lambda w: abs(w.price / m - 1))[:6]
    t = Table.grid(padding=(0, 1))
    for _ in range(4):
        t.add_column()
    for w in rows:
        dist = (w.price / m - 1) * 100
        t.add_row(
            Text(w.side, style="green" if w.side == "bid" else "red"),
            f"{w.price:.6g}",
            usd(w.notional),
            Text(f"{dist:+.2f}%  {now - w.first_seen:.0f}s old", style="dim"),
        )
    ev = Table.grid(padding=(0, 1))
    for _ in range(4):
        ev.add_column()
    for e in list(s.wall_events)[-5:][::-1]:
        style = "yellow" if e.kind == "pulled" else "white"
        ev.add_row(
            Text(time.strftime("%H:%M:%S", time.localtime(e.ts)), style="dim"),
            Text(e.kind.upper(), style=style),
            f"{e.side} {e.price:.6g}",
            usd(e.notional),
        )
    body = Group(
        t if rows else Text("no walls within 2%", style="dim"), Text("events", style="bold dim"), ev
    )
    return Panel(body, title="walls (big resting orders)", border_style="magenta")


def tape_panel(s: FlowState, now: float) -> Panel:
    t = Table.grid(padding=(0, 1))
    for _ in range(4):
        t.add_column()
    items = [
        (p.ts, "BIG " + p.side.upper(), p.price, p.notional, "green" if p.side == "buy" else "red")
        for p in s.prints
    ]
    items += [(x.ts, f"LIQ {x.side.upper()}", x.price, x.notional, "bold yellow") for x in s.liqs]
    for ts, label, px, n, style in sorted(items, reverse=True)[:10]:
        t.add_row(
            Text(time.strftime("%H:%M:%S", time.localtime(ts)), style="dim"),
            Text(label, style=style),
            f"{px:.6g}",
            usd(n),
        )
    lq_l, lq_s = s.liq_sum(now, 300)
    thr = s.big_threshold()
    foot = Text(
        f"liqs 5m: longs {usd(lq_l)} · shorts {usd(lq_s)}   big = ≥{usd(thr) if thr != float('inf') else '…'}",
        style="dim",
    )
    return Panel(
        Group(t if items else Text("waiting for big prints…", style="dim"), foot),
        title="tape: whale prints + liquidations",
        border_style="yellow",
    )


def read_panel(s: FlowState, now: float) -> Panel:
    lines = [Text("• " + sig.text, style=COLORS[sig.level]) for sig in s.read(now)[:8]]
    return Panel(
        Group(*lines),
        title="READ (context, not a trade call; stop on the exchange first)",
        border_style="white",
    )


def render(s: FlowState) -> Layout:
    now = time.time()
    root = Layout()
    root.split_column(
        Layout(header(s, now), size=3),
        Layout(name="mid", ratio=3),
        Layout(read_panel(s, now), size=11),
    )
    root["mid"].split_row(Layout(name="left"), Layout(book_panel(s), name="book"))
    root["mid"]["left"].split_column(
        Layout(flow_panel(s, now), size=10),
        Layout(walls_panel(s, now)),
        Layout(tape_panel(s, now)),
    )
    return root
