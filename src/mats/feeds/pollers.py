"""Periodic REST pollers that publish snapshot events the WS streams don't carry.

The scanner needs `InstrumentStats` (24h volume, open interest, funding) refreshed on a
cadence; Binance's markPrice WS gives live mark + funding but not volume or OI.
"""

from __future__ import annotations

import contextlib

import httpx

from mats.core.bus import EventBus
from mats.core.clock import Clock
from mats.feeds.binance import BinanceFuturesFeed


class InstrumentStatsPoller:
    def __init__(
        self,
        feed: BinanceFuturesFeed,
        bus: EventBus,
        clock: Clock,
        *,
        interval_s: float = 60.0,
    ) -> None:
        self._feed = feed
        self._bus = bus
        self._clock = clock
        self._interval_s = interval_s

    async def run(self, symbols: set[str]) -> None:
        while True:
            with contextlib.suppress(httpx.HTTPError, KeyError, ValueError):
                for stats in await self._feed.fetch_instrument_stats(symbols):
                    self._bus.publish(stats)
            await self._clock.sleep(self._interval_s)
