"""Shared per-symbol market state.

One store owns the `SymbolState` map and the single bus-ingest loop. The scanner and every
observer read the same warm state instead of each rebuilding indicators from cold.
"""

from __future__ import annotations

from mats.agents.symbol_state import SymbolState
from mats.config import StrategyParams
from mats.core.bus import EventBus
from mats.core.models import (
    Candle,
    InstrumentStats,
    Liquidation,
    MarkPrice,
    OrderBook,
    Trade,
)

_INGEST_TYPES = (Candle, Trade, MarkPrice, InstrumentStats, OrderBook, Liquidation)


class MarketStateStore:
    def __init__(self, bus: EventBus, params: StrategyParams) -> None:
        self._bus = bus
        self._p = params
        self._states: dict[str, SymbolState] = {}
        self._sub = bus.subscribe(*_INGEST_TYPES)

    def get(self, symbol: str) -> SymbolState | None:
        return self._states.get(symbol)

    def state(self, symbol: str) -> SymbolState:
        st = self._states.get(symbol)
        if st is None:
            st = SymbolState(symbol, self._p)
            self._states[symbol] = st
        return st

    def symbols(self) -> list[str]:
        return list(self._states)

    def ingest(self, event: object) -> None:
        if isinstance(event, Candle):
            self.state(event.symbol).on_candle(event)
        elif isinstance(event, Trade):
            self.state(event.symbol).on_trade(event)
        elif isinstance(event, MarkPrice):
            self.state(event.symbol).on_mark(event)
        elif isinstance(event, InstrumentStats):
            self.state(event.symbol).on_stats(event)
        elif isinstance(event, OrderBook):
            self.state(event.symbol).on_book(event)
        elif isinstance(event, Liquidation):
            self.state(event.symbol).on_liquidation(event)

    async def run(self) -> None:
        async for event in self._sub:
            self.ingest(event)
