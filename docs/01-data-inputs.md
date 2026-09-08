# Step 1 — Data Inputs Catalogue

Every parameter a monitor-agent could watch. Source = CoinDCX public API unless noted.
Refresh = how often it meaningfully changes / how often to poll.

## A. Price / trade tape
| # | Signal | Source | Refresh | Why it matters |
|---|--------|--------|---------|----------------|
| A1 | Last price, OHLCV candles (1s/1m/5m/15m/1h) | REST `/market_data/candles` + WS | 1s–1m | base for every indicator |
| A2 | Trade tape (individual fills, size, side) | WS trades channel | tick | aggressor flow, absorption, large prints |
| A3 | VWAP (session + rolling) | derived from A2 | 1s | fair-value anchor, mean-reversion band |
| A4 | Realized volatility (rolling stdev of returns, ATR) | derived from A1 | 1m | position sizing, stop distance |
| A5 | Price vs multi-timeframe EMA stack (9/21/50/200) | derived | 1m | trend regime filter |

## B. Order book / microstructure
| # | Signal | Source | Refresh | Why |
|---|--------|--------|---------|-----|
| B1 | L2 depth (top 20–50 levels each side) | WS depth channel | tick | supply/demand walls |
| B2 | Bid-ask spread (bps) | B1 | tick | execution cost, liquidity health; widen = danger |
| B3 | Order book imbalance = (bidVol−askVol)/(bidVol+askVol) at N levels | B1 | tick | short-term directional pressure |
| B4 | Depth slope / liquidity within ±0.5% | B1 | tick | slippage estimate for our size |
| B5 | Spoof detection: large orders appearing/vanishing without fills | B1+A2 | tick | fake walls before a move |
| B6 | Microprice = (bid·askVol + ask·bidVol)/(bidVol+askVol) | B1 | tick | better fair price than mid |

## C. Derivatives-specific
| # | Signal | Source | Refresh | Why |
|---|--------|--------|---------|-----|
| C1 | Funding rate (current + predicted next) | REST instruments | 1m / 8h cycle | crowded side; extreme funding = squeeze fuel |
| C2 | Open interest (total + delta) | REST | 1m | new money vs closing; OI up + price up = real trend |
| C3 | Basis = perp price − spot index | REST | 1s | leverage sentiment, mean-reverts |
| C4 | Liquidation feed (size, side, price) | WS liq channel (or Bybit/Coinglass proxy) | tick | cascade detection, reversal spots |
| C5 | Long/short account ratio | Coinglass/Binance proxy | 5m | positioning extremes |
| C6 | Mark price vs last price gap | REST | 1s | liquidation trigger proximity |

## D. Cross-market / context
| # | Signal | Source | Refresh | Why |
|---|--------|--------|---------|-----|
| D1 | BTC + ETH price/vol (lead the alt market) | same API | 1s | beta filter — don't fight the majors |
| D2 | Same asset price on 2–3 other exchanges | Bybit/Binance API | 1s | lead-lag arb, CoinDCX mispricing |
| D3 | Stablecoin (USDT) INR premium/discount | CoinDCX | 1m | INR-rail specific edge |
| D4 | BTC dominance, total market cap | CoinGecko | 5m | risk-on/risk-off regime |

## E. Event / sentiment (slower, gating signals)
| # | Signal | Source | Refresh | Why |
|---|--------|--------|---------|-----|
| E1 | Economic calendar (CPI, FOMC), token unlocks, listings | scraped/API | daily | stand aside or size down around these |
| E2 | Exchange announcements (new listing, delisting) | CoinDCX blog/API | hourly | listing pumps |
| E3 | Social volume spike (X/Reddit mentions) | LunarCrush/Santiment | 15m | retail-driven pump early warning |
| E4 | Large wallet / exchange inflow-outflow | Arkham/Nansen/on-chain | 15m | whale accumulation or dump prep |

## F. Account / risk state (our own)
| # | Signal | Source | Refresh | Why |
|---|--------|--------|---------|-----|
| F1 | Wallet balance, free vs used margin | REST private | on fill | can we take the trade |
| F2 | Open positions, entry, unrealized PnL, liq price | REST private | 1s | risk exposure, our own liq danger |
| F3 | Open orders status | WS private | tick | fill confirmation, stale-order cleanup |
| F4 | Day PnL, trade count, consecutive losses | derived | on fill | circuit breakers |
| F5 | API rate-limit headroom | response headers | continuous | don't get throttled mid-trade |

## Pump/dump early-warning composite (built from above)
Fires when several align in a short window:
- OI ↑ fast + price ↑ + funding spiking + spread widening + book imbalance extreme + social spike
  → **pump in progress**, late entry = bagholder. Only play the fade or stand aside.
- Sudden liq cluster (C4) against prior trend + volume climax + book thinning
  → **capitulation**, mean-reversion long candidate.

## Next step
Step 2: pick ONE strategy family to build rules for first. Candidates:
1. **Order-book imbalance + microprice scalp** (B3/B6/A2) — pure microstructure, seconds hold
2. **Funding-rate / basis mean reversion** (C1/C3) — hours hold, low trade count, fits tiny capital
3. **Liquidation-cascade fade** (C4/A4) — event-driven, few high-conviction trades/day
4. **BTC lead-lag on alts** (D1/D2) — cross-market, needs low latency
5. **VWAP mean-reversion with volatility bands** (A3/A4/B2) — classic, robust, easy to backtest
