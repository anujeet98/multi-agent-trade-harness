"""Minimal async pub/sub event bus.

Publishers call `publish(event)`. Subscribers get an independent queue per subscription
and consume with `async for`. Slow subscribers apply backpressure only to themselves
(bounded queue, oldest dropped) so one stuck agent can't stall the feed.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TypeVar

T = TypeVar("T")

_DEFAULT_MAXSIZE = 10_000


class Subscription(AsyncIterator[object]):
    def __init__(self, bus: EventBus, types: tuple[type, ...], maxsize: int) -> None:
        self._bus = bus
        self._types = types
        self._queue: asyncio.Queue[object] = asyncio.Queue(maxsize=maxsize)
        self.dropped = 0

    def _offer(self, event: object) -> None:
        if self._types and not isinstance(event, self._types):
            return
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            # drop oldest to make room; a lagging consumer loses history, not liveness
            _ = self._queue.get_nowait()
            self._queue.put_nowait(event)
            self.dropped += 1

    def __aiter__(self) -> Subscription:
        return self

    async def __anext__(self) -> object:
        return await self._queue.get()

    def close(self) -> None:
        self._bus._remove(self)


class EventBus:
    def __init__(self) -> None:
        self._subs: list[Subscription] = []

    def subscribe(self, *types: type, maxsize: int = _DEFAULT_MAXSIZE) -> Subscription:
        """Subscribe to the given event types (no types => all events)."""
        sub = Subscription(self, types, maxsize)
        self._subs.append(sub)
        return sub

    def publish(self, event: object) -> None:
        for sub in self._subs:
            sub._offer(event)

    def _remove(self, sub: Subscription) -> None:
        if sub in self._subs:
            self._subs.remove(sub)
