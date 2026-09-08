# Crypto F&O Systematic Trading — Scope & Step 0

Date started: 2026-09-08

## Reality check (before any rules)
- **True HFT is not possible on CoinDCX.** HFT = colocated servers, FPGA/C++, sub-millisecond
  latency, exchange matching-engine proximity, maker rebates. Retail crypto exchanges give you
  REST + WebSocket with 50–300 ms round trip and rate limits (CoinDCX: ~ per-endpoint
  throttles). Anything you build here is **mid-frequency systematic trading**: holding seconds
  to hours, 5–200 trades/day, edge from signal quality not speed.
- "Minimal margin of error" + "perfect trades" does not exist. Every real system loses 35–55%
  of trades and is net profitable via expectancy: `E = W·avgWin − L·avgLoss − fees − funding − slippage`.
  The whole game is keeping E positive after costs.
- Costs that kill retail F&O edge: taker fees (~0.05–0.07% per side on CoinDCX futures),
  funding every 8h, slippage on market orders, and in India 1% TDS on spot (not futures) +
  30% flat tax on crypto gains + no loss offset. Futures P&L tax treatment is still grey —
  flag for the ITR skill later.

## The build order (we do ONE at a time)
0. **Scope lock** ← you are here
1. Data inputs catalogue — every parameter an agent could watch, with source + refresh rate
2. Strategy family pick — choose 1 of ~5 edges to build first
3. Rule set v1 for that edge — fully programmable, no discretion
4. Backtest harness + walk-forward test on historical data
5. Paper-trade live (CoinDCX testnet / dry-run) for N days
6. Agent architecture — one monitor per unit, one coordinator
7. Live with tiny size, scale only on proven expectancy

## Open questions for you
- Capital earmarked for this (decides position sizing + whether fees even leave room)?
- CoinDCX specifically, or open to Bybit/Binance for better API + deeper books?
- Are you okay with fully-automated order placement, or human-in-loop confirm at first?
