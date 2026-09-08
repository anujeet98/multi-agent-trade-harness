from __future__ import annotations

import asyncio

from mats.core.clock import SimClock


async def test_simclock_wakes_sleepers_in_order() -> None:
    clock = SimClock()
    log: list[str] = []

    async def waiter(name: str, secs: float) -> None:
        await clock.sleep(secs)
        log.append(name)

    tasks = [
        asyncio.create_task(waiter("c", 3)),
        asyncio.create_task(waiter("a", 1)),
        asyncio.create_task(waiter("b", 2)),
    ]
    await asyncio.sleep(0)
    await clock.advance(2.5)
    assert log == ["a", "b"]
    assert clock.now() == 2.5
    await clock.advance(1.0)
    await asyncio.gather(*tasks)
    assert log == ["a", "b", "c"]


async def test_simclock_zero_sleep_is_noop() -> None:
    clock = SimClock(start=100.0)
    await clock.sleep(0)
    assert clock.now() == 100.0
