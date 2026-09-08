"""Feed plumbing: a protocol for market-data sources and a runner that pumps a
source's events onto the bus while watching for staleness.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Protocol

from mats.core.bus import EventBus
from mats.core.clock import Clock
from mats.core.models import FeedHealth


class MarketDataSource(Protocol):
    source_name: str

    def stream(self, symbols: list[str]) -> AsyncIterator[object]:
        """Yield normalized core-model events (Candle, Trade, OrderBook, ...).

        Must reconnect internally on transient errors; only raise on unrecoverable
        misconfiguration.
        """


class FeedRunner:
    """Runs one `MarketDataSource`, republishes its events, and emits `FeedHealth`
    when the gap since the last message crosses `stale_after_s` (and again on recovery).
    """

    def __init__(
        self,
        source: MarketDataSource,
        bus: EventBus,
        clock: Clock,
        *,
        stale_after_s: float = 15.0,
        check_interval_s: float = 5.0,
    ) -> None:
        self._source = source
        self._bus = bus
        self._clock = clock
        self._stale_after_s = stale_after_s
        self._check_interval_s = check_interval_s
        self._last_msg_at: float | None = None
        self._healthy = True

    async def run(self, symbols: list[str]) -> None:
        watchdog = asyncio.create_task(self._watchdog())
        try:
            async for event in self._source.stream(symbols):
                self._last_msg_at = self._clock.now()
                if not self._healthy:
                    self._emit_health(True, 0.0)
                    self._healthy = True
                self._bus.publish(event)
        finally:
            watchdog.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watchdog

    async def _watchdog(self) -> None:
        while True:
            await self._clock.sleep(self._check_interval_s)
            if self._last_msg_at is None:
                continue
            age = self._clock.now() - self._last_msg_at
            if self._healthy and age > self._stale_after_s:
                self._healthy = False
                self._emit_health(False, age)

    def _emit_health(self, healthy: bool, age: float) -> None:
        self._bus.publish(
            FeedHealth(
                source=self._source.source_name,
                stream="*",
                healthy=healthy,
                last_message_age_s=age,
                ts=datetime.now(UTC),
            )
        )
