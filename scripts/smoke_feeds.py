"""Live smoke test: can we reach Binance futures (via DoH) and CoinDCX from here?

    .venv/bin/python scripts/smoke_feeds.py
"""

from __future__ import annotations

import asyncio
import time

from mats.feeds.binance import BinanceFuturesFeed
from mats.feeds.coindcx import CoinDCXFeed


async def main() -> None:
    bn, dx = BinanceFuturesFeed(), CoinDCXFeed()
    try:
        t = time.perf_counter()
        syms = await bn.list_symbols()
        print(f"binance REST   {len(syms)} perps ({(time.perf_counter() - t) * 1000:.0f} ms)")
        for s in ("BTCUSDT", "XAUUSDT"):
            c = (await bn.fetch_klines(s, "1m", 2))[-1]
            print(f"binance {s:8} last 1m close {c.close}")
        stats = await bn.fetch_instrument_stats({"BTCUSDT"})
        print(f"binance OI     BTCUSDT {stats[0].open_interest:,.0f} BTC, funding {stats[0].funding_rate_pct:+.4f}%")

        seen: dict[str, object] = {}
        lags: list[float] = []
        agen = bn.stream(["BTCUSDT"])
        t0 = time.time()
        async for ev in agen:
            seen.setdefault(type(ev).__name__, ev)
            if type(ev).__name__ == "Trade":
                lags.append((time.time() - ev.ts.timestamp()) * 1000)
            if {"Trade", "OrderBook", "MarkPrice"} <= seen.keys() or time.time() - t0 > 20:
                break
        await agen.aclose()
        lag = sorted(lags)[len(lags) // 2] if lags else float("nan")
        print(
            f"binance WS     got {sorted(seen)} in {time.time() - t0:.1f}s "
            f"({len(lags)} trades, median lag {lag:.0f} ms incl. clock skew)"
        )

        pairs = await dx.list_futures_pairs()
        print(f"coindcx REST   {len(pairs)} futures pairs")
        spec = await dx.fetch_instrument("B-BTC_USDT")
        print(f"coindcx spec   BTC tick {spec.tick_size} max lev {spec.max_leverage}x min qty {spec.min_quantity}")
        c = (await dx.fetch_candles("B-BTC_USDT", "1m", 3))[-1]
        print(f"coindcx candle BTC 1m close {c.close}")
        ob = await dx.fetch_orderbook("B-BTC_USDT")
        print(f"coindcx book   BTC bid {ob.bids[0].price} ask {ob.asks[0].price}")
    finally:
        await bn.aclose()
        await dx.aclose()


if __name__ == "__main__":
    asyncio.run(main())
