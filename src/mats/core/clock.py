"""Clock abstraction so live runs and deterministic replays share one code path.

Agents take a `Clock` and never call `time`/`asyncio.sleep` directly. Replay swaps in
`SimClock`, which only advances when the driver tells it to.
"""

from __future__ import annotations

import asyncio
import heapq
import time
from typing import Protocol


class Clock(Protocol):
    def now(self) -> float:
        """Unix timestamp in seconds (float)."""

    async def sleep(self, seconds: float) -> None:
        """Suspend the caller for `seconds` of clock time."""


class RealClock:
    def now(self) -> float:
        return time.time()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class SimClock:
    """Virtual clock. `now()` returns the simulated time; sleepers wake when the
    simulated time reaches their deadline. Call `advance()` from the replay driver.
    """

    def __init__(self, start: float = 0.0) -> None:
        self._now = start
        # min-heap of (deadline, seq, event) so wakeups are ordered and stable
        self._waiters: list[tuple[float, int, asyncio.Event]] = []
        self._seq = 0

    def now(self) -> float:
        return self._now

    async def sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        ev = asyncio.Event()
        self._seq += 1
        heapq.heappush(self._waiters, (self._now + seconds, self._seq, ev))
        await ev.wait()

    async def advance(self, seconds: float) -> None:
        """Move simulated time forward, releasing any sleepers whose deadline passed."""
        target = self._now + seconds
        while self._waiters and self._waiters[0][0] <= target:
            deadline, _, ev = heapq.heappop(self._waiters)
            self._now = deadline
            ev.set()
            # let woken coroutines run before continuing to advance
            await asyncio.sleep(0)
        self._now = target
        await asyncio.sleep(0)
