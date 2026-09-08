from __future__ import annotations

import asyncio
from dataclasses import dataclass

from mats.core.bus import EventBus


@dataclass
class Tick:
    n: int


@dataclass
class Note:
    text: str


async def test_type_filtered_delivery() -> None:
    bus = EventBus()
    ticks = bus.subscribe(Tick)
    everything = bus.subscribe()

    bus.publish(Tick(1))
    bus.publish(Note("hi"))
    bus.publish(Tick(2))

    assert (await asyncio.wait_for(ticks.__anext__(), 1)).n == 1
    assert (await asyncio.wait_for(ticks.__anext__(), 1)).n == 2

    got = [await asyncio.wait_for(everything.__anext__(), 1) for _ in range(3)]
    assert [type(x).__name__ for x in got] == ["Tick", "Note", "Tick"]


async def test_slow_subscriber_drops_oldest_not_newest() -> None:
    bus = EventBus()
    sub = bus.subscribe(Tick, maxsize=3)
    for i in range(5):
        bus.publish(Tick(i))
    assert sub.dropped == 2
    seen = [(await sub.__anext__()).n for _ in range(3)]
    assert seen == [2, 3, 4]


async def test_close_unsubscribes() -> None:
    bus = EventBus()
    sub = bus.subscribe(Tick)
    sub.close()
    bus.publish(Tick(1))
    assert sub._queue.empty()
