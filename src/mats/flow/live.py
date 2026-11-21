"""Feeds a FlowState from Binance USDⓈ-M futures in real time.

- WebSocket /market: aggTrade (every market order), markPrice@1s, <sym>@forceOrder.
- REST every ~1s: depth (500 levels) for book bands and walls; every 5s: open interest.
Binance hosts resolve over DoH (see mats.net.dns), so this works on Jio.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time

import httpx
import websockets

from mats.feeds.binance import REST_BASE, WS_MARKET
from mats.flow.engine import FlowState
from mats.net import dns


async def binance_has(symbol: str, http: httpx.AsyncClient) -> bool:
    r = await http.get("/fapi/v1/exchangeInfo")
    r.raise_for_status()
    return any(s["symbol"] == symbol and s.get("status") == "TRADING" for s in r.json()["symbols"])


async def _ws_loop(state: FlowState, symbol: str, stop: asyncio.Event) -> None:
    low = symbol.lower()
    url = f"{WS_MARKET}?streams={low}@aggTrade/{low}@markPrice@1s/{low}@forceOrder"
    backoff = 1.0
    while not stop.is_set():
        try:
            async with websockets.connect(url, ping_interval=180, close_timeout=3) as ws:
                backoff = 1.0
                async for raw in ws:
                    with contextlib.suppress(KeyError, ValueError, TypeError):
                        msg = json.loads(raw)
                        d = msg.get("data", msg)
                        e = d.get("e")
                        now = time.time()
                        if e == "aggTrade":
                            # m=True: buyer is the maker, so the aggressor sold
                            state.on_trade(now, float(d["p"]), float(d["q"]), not d["m"])
                        elif e == "markPriceUpdate":
                            state.on_mark(float(d["p"]), float(d.get("r") or 0) * 100)
                        elif e == "forceOrder":
                            o = d["o"]
                            side = "long" if o["S"].upper() == "SELL" else "short"
                            state.on_liquidation(
                                now, side, float(o.get("ap") or o["p"]), float(o["q"])
                            )
                    if stop.is_set():
                        return
        except (OSError, websockets.WebSocketException):
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 20.0)


async def _book_loop(
    state: FlowState, symbol: str, http: httpx.AsyncClient, stop: asyncio.Event
) -> None:
    while not stop.is_set():
        with contextlib.suppress(httpx.HTTPError, KeyError, ValueError):
            r = await http.get("/fapi/v1/depth", params={"symbol": symbol, "limit": 500})
            r.raise_for_status()
            b = r.json()
            state.on_book(
                time.time(),
                [(float(p), float(q)) for p, q in b["bids"]],
                [(float(p), float(q)) for p, q in b["asks"]],
            )
        await asyncio.sleep(1.0)


async def _oi_loop(
    state: FlowState, symbol: str, http: httpx.AsyncClient, stop: asyncio.Event
) -> None:
    while not stop.is_set():
        with contextlib.suppress(httpx.HTTPError, KeyError, ValueError):
            r = await http.get("/fapi/v1/openInterest", params={"symbol": symbol})
            r.raise_for_status()
            state.on_open_interest(time.time(), float(r.json()["openInterest"]))
        await asyncio.sleep(5.0)


async def _signal_loop(state: FlowState, stop: asyncio.Event) -> None:
    while not stop.is_set():
        state.detect_absorption(time.time())
        await asyncio.sleep(1.0)


async def run(state: FlowState, stop: asyncio.Event) -> None:
    dns.install()
    async with httpx.AsyncClient(base_url=REST_BASE, timeout=10.0) as http:
        if not await binance_has(state.symbol, http):
            raise SystemExit(f"{state.symbol} is not a Binance USDⓈ-M perp")
        tasks = [
            asyncio.create_task(_ws_loop(state, state.symbol, stop)),
            asyncio.create_task(_book_loop(state, state.symbol, http, stop)),
            asyncio.create_task(_oi_loop(state, state.symbol, http, stop)),
            asyncio.create_task(_signal_loop(state, stop)),
        ]
        try:
            await stop.wait()
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
