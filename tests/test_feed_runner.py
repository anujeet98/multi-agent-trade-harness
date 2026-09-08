from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from mats.core.bus import EventBus
from mats.core.clock import SimClock
from mats.core.models import FeedHealth
from mats.feeds.base import FeedRunner


class FakeSource:
    source_name = "fake"

    def __init__(self, gap_before_second: float) -> None:
        self._gap = gap_before_second

    async def stream(self, symbols: list[str]) -> AsyncIterator[object]:
        yield "msg-1"
        await asyncio.sleep(self._gap)
        yield "msg-2"


async def test_runner_flags_stale_then_recovers() -> None:
    bus = EventBus()
    clock = SimClock()
    health = bus.subscribe(FeedHealth)
    strings = bus.subscribe(str)

    src = FakeSource(gap_before_second=100.0)  # real seconds; we drive the clock separately
    runner = FeedRunner(src, bus, clock, stale_after_s=15.0, check_interval_s=5.0)
    task = asyncio.create_task(runner.run(["BTCUSDT"]))

    # first message flows
    assert await asyncio.wait_for(strings.__anext__(), 1) == "msg-1"

    # advance virtual time past the staleness threshold -> unhealthy event
    for _ in range(5):
        await clock.advance(5.0)
    ev = await asyncio.wait_for(health.__anext__(), 1)
    assert isinstance(ev, FeedHealth) and ev.healthy is False
    assert ev.last_message_age_s > 15.0

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
