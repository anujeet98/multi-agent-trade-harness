"""CoinDCX futures data source.

CoinDCX is the *execution* venue: this client is the source of truth for the tradeable
universe, contract specs, and CoinDCX-side price/book (used for execution checks and for
symbols with no Binance listing). Account + order streams live with the broker (#7/#8).

NOTE: CoinDCX's public futures API is thinly documented. Endpoint paths and payload keys
below are marked VERIFY and must be checked against the live API before the first live run
(tracked in issue #3 follow-up). Parsing is isolated in pure functions so a key rename is a
one-line fix.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx

from mats.core.models import BookLevel, Candle, ContractSpec, OrderBook
from mats.feeds.symbols import coindcx_to_canonical

PUBLIC_BASE = "https://public.coindcx.com"
API_BASE = "https://api.coindcx.com"

# VERIFY against live API:
EP_ACTIVE_INSTRUMENTS = "/exchange/v1/derivatives/futures/data/active_instruments"
EP_INSTRUMENT = "/exchange/v1/derivatives/futures/data/instrument"
EP_CANDLES = "/market_data/candlesticks"
EP_ORDERBOOK = "/market_data/v3/orderbook"

_RESOLUTION = {"1m": "1", "5m": "5", "15m": "15", "1h": "60"}


def parse_candles(pair: str, interval: str, payload: dict | list) -> list[Candle]:
    rows = payload["data"] if isinstance(payload, dict) else payload
    sym = coindcx_to_canonical(pair) or pair
    out: list[Candle] = []
    for row in rows:
        out.append(
            Candle(
                symbol=sym,
                interval=interval,
                open_time=datetime.fromtimestamp(int(row["time"]) / 1000, tz=UTC),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
        )
    return out


def parse_orderbook(pair: str, payload: dict) -> OrderBook:
    sym = coindcx_to_canonical(pair) or pair
    bids = payload.get("bids", {})
    asks = payload.get("asks", {})
    return OrderBook(
        symbol=sym,
        ts=datetime.now(UTC),
        bids=sorted(
            (BookLevel(price=float(p), qty=float(q)) for p, q in bids.items()),
            key=lambda lvl: lvl.price,
            reverse=True,
        ),
        asks=sorted(
            (BookLevel(price=float(p), qty=float(q)) for p, q in asks.items()),
            key=lambda lvl: lvl.price,
        ),
    )


def parse_instrument(payload: dict) -> ContractSpec:
    d = payload.get("instrument", payload)
    pair = d["pair"]
    return ContractSpec(
        symbol=coindcx_to_canonical(pair) or pair,
        coindcx_pair=pair,
        tick_size=float(d.get("price_increment", d.get("tick_size", 0.0)) or 0.0),
        step_size=float(d.get("quantity_increment", d.get("step_size", 0.0)) or 0.0),
        min_quantity=float(d.get("min_quantity", 0.0) or 0.0),
        max_leverage=float(d.get("max_leverage", 0.0) or 0.0),
        maker_fee_pct=float(d.get("maker_fee", 0.0) or 0.0),
        taker_fee_pct=float(d.get("taker_fee", 0.0) or 0.0),
    )


class CoinDCXFeed:
    source_name = "coindcx"

    def __init__(self, *, http: httpx.AsyncClient | None = None) -> None:
        self._http = http or httpx.AsyncClient(timeout=10.0)

    async def list_futures_pairs(self) -> set[str]:
        r = await self._http.get(f"{API_BASE}{EP_ACTIVE_INSTRUMENTS}")
        r.raise_for_status()
        body = r.json()
        pairs = body if isinstance(body, list) else body.get("instruments", [])
        return {p if isinstance(p, str) else p["pair"] for p in pairs}

    async def fetch_instrument(self, pair: str) -> ContractSpec:
        r = await self._http.get(
            f"{API_BASE}{EP_INSTRUMENT}",
            params={"pair": pair, "margin_currency_short_name": "USDT"},
        )
        r.raise_for_status()
        return parse_instrument(r.json())

    async def fetch_candles(self, pair: str, interval: str, limit: int = 100) -> list[Candle]:
        r = await self._http.get(
            f"{PUBLIC_BASE}{EP_CANDLES}",
            params={
                "pair": pair,
                "resolution": _RESOLUTION.get(interval, "1"),
                "pcode": "f",
                "limit": limit,
            },
        )
        r.raise_for_status()
        return parse_candles(pair, interval, r.json())

    async def fetch_orderbook(self, pair: str, depth: int = 50) -> OrderBook:
        r = await self._http.get(f"{PUBLIC_BASE}{EP_ORDERBOOK}/{pair}-futures/{depth}")
        r.raise_for_status()
        return parse_orderbook(pair, r.json())

    async def build_contract_specs(self, pairs: set[str]) -> dict[str, ContractSpec]:
        async def one(pair: str) -> ContractSpec | None:
            with contextlib.suppress(httpx.HTTPError, KeyError, ValueError):
                return await self.fetch_instrument(pair)
            return None

        specs = await asyncio.gather(*(one(p) for p in pairs))
        return {s.symbol: s for s in specs if s is not None}

    async def stream(self, symbols: list[str]) -> AsyncIterator[object]:
        """Polling fallback stream: CoinDCX public book/candle polling for symbols with no
        Binance data. Binance is the primary WS feed; this keeps CoinDCX-only alts covered.
        """
        from mats.feeds.symbols import canonical_to_coindcx

        while True:
            for sym in symbols:
                pair = canonical_to_coindcx(sym)
                if not pair:
                    continue
                with contextlib.suppress(httpx.HTTPError, KeyError, ValueError):
                    yield await self.fetch_orderbook(pair)
            await asyncio.sleep(2.0)

    async def aclose(self) -> None:
        await self._http.aclose()
