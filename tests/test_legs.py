from __future__ import annotations

import itertools
from datetime import UTC, datetime

from mats.agents.legs import analyze_legs, zigzag_pivots
from mats.core.models import Candle, Side

BASE = 1_700_000_000


def _c(i: int, close: float) -> Candle:
    return Candle(
        symbol="X",
        interval="1m",
        open_time=datetime.fromtimestamp(BASE + i * 60, tz=UTC),
        open=close,
        high=close + 0.1,
        low=close - 0.1,
        close=close,
        volume=1.0,
    )


def _series(prices: list[float]) -> list[Candle]:
    return [_c(i, p) for i, p in enumerate(prices)]


def test_zigzag_finds_alternating_pivots() -> None:
    # up to 105, down to 102, up to 108
    prices = [100, 101, 103, 105, 104, 103, 102, 104, 106, 108]
    pivots = zigzag_pivots(_series(prices), min_move_pct=1.0)
    kinds = [p.is_high for p in pivots]
    # pivots alternate; first confirmed is the starting low
    assert kinds[0] is False
    for a, b in itertools.pairwise(pivots):
        assert a.is_high != b.is_high


def test_analyze_legs_counts_pullbacks_and_retrace() -> None:
    # long move: 100 ->105 (leg), ->102.5 (pullback), ->108 (leg), now pulling back to 106
    prices = (
        [100, 101, 102, 103, 104, 105] + [104, 103, 102.5] + [104, 105, 106, 107, 108] + [107, 106]
    )
    a = analyze_legs(_series(prices), Side.LONG, min_move_pct=1.0)
    assert a is not None
    assert a.num_directional_legs >= 2
    assert a.pullback_count >= 1
    # currently pulling back from the 108 high -> retrace between 0 and 100
    assert 0 < a.retrace_pct_of_last_leg < 100


def test_short_side_mirror() -> None:
    prices = [100, 99, 98, 97, 96, 95, 96, 97, 96, 94, 92, 90, 91, 92]
    a = analyze_legs(_series(prices), Side.SHORT, min_move_pct=1.0)
    assert a is not None and a.num_directional_legs >= 1
