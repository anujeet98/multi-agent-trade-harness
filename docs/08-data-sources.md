# 08 — Data sources

## Split of responsibilities

| Need | Source | Auth | Transport |
|------|--------|------|-----------|
| Indicator inputs: trades tape, L2 depth, klines, funding, open interest, liquidations | **Binance USDⓈ-M Futures** (primary) | none (public) | WebSocket + REST |
| Tradeable universe, contract specs (tick/lot/max leverage), our mark & funding | **CoinDCX** | public | REST |
| Account: balance, positions, open orders, fills | **CoinDCX** | API key (read) | REST + WS |
| **Order placement / cancel / modify** | **CoinDCX** | API key (trade) | REST |
| Cross-exchange lead-lag (bonus signal D2) | Binance vs CoinDCX price diff | — | derived |

Trades happen **only on CoinDCX**. Everything else is just data.

## Why Binance for indicators (D7)

- Deepest free futures data, no key for public market streams.
- Complete endpoint set for our catalogue (`01-data-inputs.md`):
  - `wss .../ws/<sym>@aggTrade` — tape / CVD / aggressor ratio
  - `<sym>@depth@100ms` — L2 book, imbalance, microprice, walls, slippage sim
  - `<sym>@kline_1m` / `_5m` — OHLCV, RVOL, EMA, ATR, anchored VWAP
  - `<sym>@markPrice@1s` — mark, funding rate + predicted
  - REST `/futures/data/openInterestHist`, `/fapi/v1/openInterest` — OI delta
  - `!forceOrder@arr` — market-wide liquidations (cascade detection)
  - REST `/futures/data/globalLongShortAccountRatio` — positioning
- Downsides: reachability from India can be flaky. Fallbacks in priority order: **Bybit v5**
  (`wss stream.bybit.com/v5/public/linear`), then **OKX** (`wss ws.okx.com`). Same signal set.

## MCP servers — where they fit (and don't)

- **Not in the feed layer.** MCP is a tool-call interface for LLMs; it adds a JSON-RPC hop and
  latency, and isn't built for high-rate numeric streaming. The deterministic agents use raw
  WS/REST clients.
- **OKX official MCP / CoinDCX community MCP:** usable *inside the LLM nodes* only
  (`context_llm`, `review_llm`) if it's more convenient than a REST call there — e.g. "what's
  the current funding + OI for X" as a one-off LLM tool. Optional, not a dependency.

## Symbol mapping

`feeds/symbols.py`: map each CoinDCX perp → its Binance symbol (e.g. `B-BTC_USDT` ↔ `BTCUSDT`).
- Coin on **both**: indicators from Binance, execution on CoinDCX. Preferred.
- Coin on **CoinDCX only** (small alts like ARX): indicators from CoinDCX's own market data
  (thinner — widen the eligibility filters or lower size), or Bybit if listed there.
- Coin on **Binance only**: not tradeable for us — excluded from the universe.

## Rate limits & resilience

- Binance public WS: generous; one multiplexed connection, subscribe per candidate.
- CoinDCX REST: per-endpoint throttles — the feed tracks headroom (F5 in the catalogue) and
  backs off; never let a data poll starve an order call.
- All clients: exponential-backoff reconnect, staleness watchdog (flag a feed as stale if no
  message in N seconds → coordinator halts new entries).

## Config

`.env`: `COINDCX_API_KEY` / `COINDCX_API_SECRET` (read scope for paper; trade scope only when
going live). `MATS_INDICATOR_SOURCE=binance|bybit|okx` (default `binance`).
