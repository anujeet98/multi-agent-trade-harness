"""Binance USDⓈ-M Futures market-data source (primary indicator feed).

Public endpoints only — no API key. Transport is thin; the value is in the pure
`parse_ws` / `parse_*` functions, which are fully unit-tested against recorded payloads.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import websockets

from mats.core.models import (
    BookLevel,
    Candle,
    InstrumentStats,
    Liquidation,
    MarkPrice,
    OrderBook,
    Side,
    Trade,
)

REST_BASE = "https://fapi.binance.com"
WS_BASE = "wss://fstream.binance.com/stream"

# per-symbol streams we open for each watched candidate
SYMBOL_STREAMS = ("aggTrade", "depth20@100ms", "kline_1m", "kline_5m", "markPrice@1s")
# market-wide streams opened once
GLOBAL_STREAMS = ("!forceOrder@arr",)


def _ts(ms: float) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def parse_trade(sym: str, d: dict) -> Trade:
    return Trade(
        symbol=sym,
        ts=_ts(d["T"]),
        price=float(d["p"]),
        qty=float(d["q"]),
        is_buyer_maker=bool(d["m"]),
    )


def parse_depth(sym: str, d: dict) -> OrderBook:
    bids = d.get("b") or d.get("bids") or []
    asks = d.get("a") or d.get("asks") or []
    ts_ms = d.get("T") or d.get("E")
    return OrderBook(
        symbol=sym,
        ts=_ts(ts_ms) if ts_ms else datetime.now(UTC),
        bids=[BookLevel(price=float(p), qty=float(q)) for p, q in bids],
        asks=[BookLevel(price=float(p), qty=float(q)) for p, q in asks],
    )


def parse_kline(d: dict) -> Candle | None:
    k = d["k"]
    if not k.get("x"):  # only emit closed candles
        return None
    return Candle(
        symbol=k["s"],
        interval=k["i"],
        open_time=_ts(k["t"]),
        open=float(k["o"]),
        high=float(k["h"]),
        low=float(k["l"]),
        close=float(k["c"]),
        volume=float(k["v"]),
    )


def parse_mark_price(d: dict) -> MarkPrice:
    return MarkPrice(
        symbol=d["s"],
        ts=_ts(d["E"]),
        mark_price=float(d["p"]),
        funding_rate_pct=float(d["r"]) * 100 if d.get("r") not in (None, "") else 0.0,
        next_funding_time=_ts(d["T"]) if d.get("T") else None,
    )


def parse_force_order(d: dict) -> Liquidation:
    o = d["o"]
    # S is the side of the order used to liquidate: SELL => a long was force-closed
    liquidated = Side.LONG if o["S"].upper() == "SELL" else Side.SHORT
    return Liquidation(
        symbol=o["s"],
        ts=_ts(o["T"]),
        side=liquidated,
        qty=float(o["q"]),
        price=float(o.get("ap") or o["p"]),
    )


def parse_ws(envelope: dict) -> object | None:
    """Combined-stream envelope -> a core model (or None to ignore)."""
    stream = envelope.get("stream", "")
    data = envelope.get("data", envelope)
    event = data.get("e")

    if event == "aggTrade" or stream.endswith("@aggTrade"):
        return parse_trade(data["s"], data)
    if event == "kline" or "@kline_" in stream:
        return parse_kline(data)
    if event == "markPriceUpdate" or stream.endswith("@markPrice@1s"):
        return parse_mark_price(data)
    if event == "forceOrder" or stream == "!forceOrder@arr":
        return parse_force_order(data)
    if "@depth" in stream or event == "depthUpdate" or ("b" in data and "a" in data):
        sym = data.get("s") or stream.split("@", 1)[0].upper()
        return parse_depth(sym, data)
    return None


class BinanceFuturesFeed:
    source_name = "binance"

    def __init__(self, *, http: httpx.AsyncClient | None = None) -> None:
        self._http = http or httpx.AsyncClient(base_url=REST_BASE, timeout=10.0)

    # --- REST -----------------------------------------------------------------

    async def list_symbols(self) -> set[str]:
        r = await self._http.get("/fapi/v1/exchangeInfo")
        r.raise_for_status()
        return {
            s["symbol"]
            for s in r.json()["symbols"]
            if s.get("contractType") == "PERPETUAL" and s.get("status") == "TRADING"
        }

    async def fetch_klines(self, symbol: str, interval: str, limit: int = 100) -> list[Candle]:
        r = await self._http.get(
            "/fapi/v1/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
        )
        r.raise_for_status()
        return [
            Candle(
                symbol=symbol,
                interval=interval,
                open_time=_ts(row[0]),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
            )
            for row in r.json()
        ]

    async def fetch_instrument_stats(
        self, symbols: set[str] | None = None
    ) -> list[InstrumentStats]:
        tickers, premium, oi_map = await asyncio.gather(
            self._get_json("/fapi/v1/ticker/24hr"),
            self._get_json("/fapi/v1/premiumIndex"),
            self._open_interest_map(symbols),
        )
        prem_by_sym = {p["symbol"]: p for p in premium}
        now = datetime.now(UTC)
        out: list[InstrumentStats] = []
        for t in tickers:
            sym = t["symbol"]
            if symbols is not None and sym not in symbols:
                continue
            p = prem_by_sym.get(sym, {})
            out.append(
                InstrumentStats(
                    symbol=sym,
                    ts=now,
                    last_price=float(t["lastPrice"]),
                    mark_price=float(p.get("markPrice", t["lastPrice"])),
                    funding_rate_pct=float(p.get("lastFundingRate", 0.0)) * 100,
                    open_interest=oi_map.get(sym, 0.0),
                    quote_volume_24h=float(t["quoteVolume"]),
                )
            )
        return out

    async def _get_json(self, path: str) -> list[dict]:
        r = await self._http.get(path)
        r.raise_for_status()
        return r.json()

    async def _open_interest_map(self, symbols: set[str] | None) -> dict[str, float]:
        if not symbols:
            return {}

        async def one(sym: str) -> tuple[str, float]:
            try:
                r = await self._http.get("/fapi/v1/openInterest", params={"symbol": sym})
                r.raise_for_status()
                return sym, float(r.json()["openInterest"])
            except (httpx.HTTPError, KeyError, ValueError):
                return sym, 0.0

        return dict(await asyncio.gather(*(one(s) for s in symbols)))

    # --- WebSocket ----------------------------------------------------------

    def _stream_names(self, symbols: list[str]) -> list[str]:
        names = list(GLOBAL_STREAMS)
        for sym in symbols:
            low = sym.lower()
            names += [f"{low}@{s}" for s in SYMBOL_STREAMS]
        return names

    async def stream(self, symbols: list[str]) -> AsyncIterator[object]:
        url = f"{WS_BASE}?streams={'/'.join(self._stream_names(symbols))}"
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(url, ping_interval=180, close_timeout=5) as ws:
                    backoff = 1.0
                    async for raw in ws:
                        with contextlib.suppress(json.JSONDecodeError, KeyError, ValueError):
                            event = parse_ws(json.loads(raw))
                            if event is not None:
                                yield event
            except (OSError, websockets.WebSocketException):
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def aclose(self) -> None:
        await self._http.aclose()
