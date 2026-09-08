from __future__ import annotations

import pytest

from mats.config import Mode, Settings


def test_paper_is_default() -> None:
    s = Settings()
    assert s.mode is Mode.PAPER
    s.guard_live()  # must not raise


def test_live_requires_opt_in() -> None:
    s = Settings(mode=Mode.LIVE, allow_live=False)
    with pytest.raises(RuntimeError):
        s.guard_live()

    s2 = Settings(mode=Mode.LIVE, allow_live=True)
    s2.guard_live()  # must not raise


def test_strategy_defaults_present() -> None:
    s = Settings()
    assert s.strategy.tp1_r_multiple == 1.3
    assert s.strategy.max_effective_leverage == 12.0
