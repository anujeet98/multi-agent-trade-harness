"""Small async helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Iterable
from typing import TypeVar

T = TypeVar("T")


async def gather_limited(aws: Iterable[Awaitable[T]], limit: int) -> list[T]:
    """Like ``asyncio.gather`` but at most ``limit`` awaitables run at once.

    Used for fan-out REST calls so a universe-wide refresh doesn't burst past an
    exchange's request-weight limit and trigger a timed IP ban.
    """
    sem = asyncio.Semaphore(max(1, limit))

    async def _run(aw: Awaitable[T]) -> T:
        async with sem:
            return await aw

    return await asyncio.gather(*(_run(aw) for aw in aws))
