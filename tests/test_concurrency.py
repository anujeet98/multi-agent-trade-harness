from __future__ import annotations

import asyncio

from mats.core.concurrency import gather_limited


async def test_gather_limited_caps_concurrency() -> None:
    active = 0
    peak = 0

    async def task(i: int) -> int:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return i

    results = await gather_limited((task(i) for i in range(20)), limit=4)
    assert sorted(results) == list(range(20))
    assert peak <= 4
