"""Swing-leg structure from a 1m candle series (for the Observer's Layer 2b/2c checks).

A simple percentage zigzag: a new pivot is confirmed once price reverses `min_move_pct`
from the running extreme. From the pivots we derive how many legs the move has, how big
they are, how many pullbacks have been bought, and where the current leg stands.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from mats.core.models import Candle, Side


@dataclass(frozen=True)
class Pivot:
    ts: float
    price: float
    is_high: bool


@dataclass(frozen=True)
class LegAnalysis:
    num_directional_legs: int  # legs in the trade direction
    avg_leg_pct: float
    current_leg_pct: float  # move from the last opposing pivot to the current price
    pullback_count: int  # opposing legs since the move began
    retrace_pct_of_last_leg: float  # how far price has pulled back from the last extreme
    last_pivot_price: float


def zigzag_pivots(candles: list[Candle], min_move_pct: float) -> list[Pivot]:
    if len(candles) < 2:
        return []
    pivots: list[Pivot] = []
    ext_price = candles[0].close
    ext_ts = candles[0].open_time.timestamp()
    going_up: bool | None = None
    for c in candles[1:]:
        px = c.close
        ts = c.open_time.timestamp()
        if going_up is None:
            if abs(px - ext_price) / ext_price * 100 >= min_move_pct:
                going_up = px > ext_price
                pivots.append(Pivot(ext_ts, ext_price, is_high=not going_up))
                ext_price, ext_ts = px, ts
            continue
        if going_up:
            if px >= ext_price:
                ext_price, ext_ts = px, ts
            elif (ext_price - px) / ext_price * 100 >= min_move_pct:
                pivots.append(Pivot(ext_ts, ext_price, is_high=True))
                going_up = False
                ext_price, ext_ts = px, ts
        else:
            if px <= ext_price:
                ext_price, ext_ts = px, ts
            elif (px - ext_price) / ext_price * 100 >= min_move_pct:
                pivots.append(Pivot(ext_ts, ext_price, is_high=False))
                going_up = True
                ext_price, ext_ts = px, ts
    return pivots


def analyze_legs(candles: list[Candle], side: Side, min_move_pct: float) -> LegAnalysis | None:
    if len(candles) < 5:
        return None
    pivots = zigzag_pivots(candles, min_move_pct)
    price_now = candles[-1].close
    # a directional leg for a long runs low -> high, so it "just finished a leg and is
    # pulling back" iff the most recent pivot is a HIGH (mirror for a short).
    pullback_pivot_is_high = side is Side.LONG

    # legs = consecutive pivot pairs; a "directional" leg moves in the trade direction
    legs: list[float] = []
    pullbacks = 0
    for a, b in itertools.pairwise(pivots):
        move_pct = (b.price - a.price) / a.price * 100
        directional = (move_pct > 0) == (side is Side.LONG)
        if directional:
            legs.append(abs(move_pct))
        else:
            pullbacks += 1

    if pivots:
        last = pivots[-1]
        if last.is_high != pullback_pivot_is_high:  # fresh directional leg from the last pivot
            current_leg_pct = (price_now - last.price) / last.price * 100
            current_leg_pct = current_leg_pct if side is Side.LONG else -current_leg_pct
            retrace = 0.0
        else:  # price is pulling back from the last extreme
            current_leg_pct = legs[-1] if legs else 0.0
            prev_opposing = next(
                (p.price for p in reversed(pivots[:-1]) if p.is_high != last.is_high),
                candles[0].close,
            )
            span = abs(last.price - prev_opposing)
            retrace = abs(last.price - price_now) / span * 100 if span > 0 else 0.0
        last_pivot_price = last.price
    else:
        current_leg_pct = (price_now - candles[0].close) / candles[0].close * 100
        current_leg_pct = current_leg_pct if side is Side.LONG else -current_leg_pct
        retrace = 0.0
        last_pivot_price = candles[0].close

    return LegAnalysis(
        num_directional_legs=len(legs),
        avg_leg_pct=(sum(legs) / len(legs)) if legs else 0.0,
        current_leg_pct=current_leg_pct,
        pullback_count=pullbacks,
        retrace_pct_of_last_leg=retrace,
        last_pivot_price=last_pivot_price,
    )
