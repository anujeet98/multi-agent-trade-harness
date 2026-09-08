# 03b — Highest-value signals for "will this move CONTINUE in the next 1–5 min"

Ranked by signal-to-effort for a 5-min continuation scalp on CoinDCX perps.
Each: what it is · why it predicts continuation · the fade/exhaustion warning it also gives.

## TIER 1 — add these as first-class filters (not just confirmation)

### 1. Open Interest delta vs price  ⭐ the big one
- OI change over the move, aligned with price change.
- **Continuation:** price ↑ **and** OI ↑ → *new* longs entering = fresh money + conviction. Best when funding is still flat/slightly negative (crowd hasn't piled in yet).
- **Fade:** price ↑ but OI ↓ → short-covering rally, no new buyers; dies fast once shorts are done. price ↑ OI flat → weak, unsupported.
- 3-way state machine (price/OI/funding):
  | price | OI | funding | read |
  |---|---|---|---|
  | ↑ | ↑ | flat/neg | **strongest continuation** — take it |
  | ↑ | ↑ | ↑ fast | strong but crowded/late — smaller size, tight stop |
  | ↑ | ↓ | any | short covering — expect stall, don't chase |
  | ↑ | flat | any | weak — skip |

### 2. CVD / aggressor order-flow imbalance  ⭐
- Cumulative Volume Delta = Σ(market-buy volume − market-sell volume) from the trade tape.
- **Continuation:** CVD rising in step with price = buyers are *lifting offers* aggressively. Especially strong if price makes a new high AND CVD makes a new high together.
- **Fade / trap:** price makes new high but CVD does **not** (bearish divergence) → move is from sellers pulling offers, not real buying = fragile, likely to snap back. This is the #1 early reversal tell.
- Also watch **aggressor ratio** last 60s: buy-vol / total-vol ≥ ~0.6 for a long.

### 3. Liquidation flow — direction + acceleration
- Stream of forced closes (size, side, price).
- **Continuation fuel:** during an up-move, a rising stream of **short** liquidations = forced buying stacked on top of real buying → sharp continuation legs.
- **Exhaustion:** one giant liquidation spike (largest in hours) followed by the stream drying up = the fuel is spent → climax top, often the exact reversal candle. Big single print = get out / take profit, don't enter.
- Rule of thumb: *accelerating* small/medium liqs = enter; *one huge* liq = exit.

### 4. Spot-vs-perp lead & spot premium
- Compare the same coin's spot price/flow to the perp.
- **Continuation:** spot is leading perp up (spot trading at premium to perp, or spot CVD leading) → move is driven by real spot demand = more durable.
- **Fade/squeeze risk:** perp leading spot, perp premium widening, funding spiking → purely leveraged-driven, prone to a violent long-squeeze once it stalls.

## TIER 2 — high value, add as scoring inputs

### 5. Relative strength vs BTC (and vs its sector)
- Coin's return minus BTC's return over trailing 15m.
- **Continuation:** coin strongly outperforming a flat/up BTC = it's the "leader"; leaders keep leading intraday. If BTC is also up, even better (beta tailwind).
- **Fade:** the whole move is just BTC beta (coin RS ≈ 0) → no idiosyncratic driver; reverses when BTC does.

### 6. Anchored VWAP from the move's origin
- VWAP anchored to the candle where the impulse started.
- **Continuation:** price holding above the anchored VWAP on pullbacks = buyers defending average price.
- **Exit signal:** first decisive close below the anchored VWAP = the move is statistically over — hard exit for the runner.

### 7. Order-book dynamics (not the static snapshot)
- **Ask-pull vs absorption:** as price rises, are offers being *canceled ahead* of price (sellers retreating → continuation) or is a fat wall *absorbing* thousands of contracts without breaking (→ stall / reversal at that level)?
- **Sweep detection:** a single market order that clears ≥ 3–5 levels at once = a player with size and urgency → usually a continuation burst follows within seconds.
- **Bid stacking:** new large passive bids appearing just under price during the move = support building = safe to hold.

### 8. Funding rate rate-of-change (not the level)
- **Continuation OK:** funding mildly positive and stable.
- **Warning:** funding rising fast (e.g. +0.03% in 5 min) → longs crowding in → raises near-term squeeze/reversal odds; tighten stop, take TP1 sooner.

## TIER 3 — useful confirmers / context

### 9. Trade cadence & large-print acceleration
- trades/min accelerating + increasing count of above-average aggressive prints in trend direction = momentum building. Deceleration = momentum fading even if price still drifts.

### 10. 1-minute volatility squeeze before the entry leg
- Bollinger-band width or ATR contracting into a tight range, then expansion → the expansion leg has follow-through. Entering right as the squeeze releases beats chasing an extended candle.

### 11. Liquidity magnets / stop pools
- Clusters of resting liquidity and obvious stop zones (just above recent swing highs, round numbers like 0.10 / 0.15 / 1.00). Price is drawn toward them.
- **Continuation:** a clear magnet sits above entry with little liquidity in between → path of least resistance is up → good TP target.
- **Caution:** if entry is *right at* a big magnet, the move may reverse once it's tagged (stop-hunt then fade).

## How these fold into Rule Set v1

- Promote **OI-delta state machine** and **CVD-vs-price divergence** to Layer 1 hard filters.
- Add **liquidation-acceleration vs single-spike** logic to Layer 2 (fuel = allow, spike = reject R4 upgrade).
- Add **spot lead / spot premium** and **RS vs BTC** to the Layer 1 hotness score.
- Add **anchored VWAP break** as a Layer 3 runner exit.
- Add **sweep / ask-pull** to Layer 2 order-book confirmation.
→ produces Rule Set v1.1 + 3 new scorecard columns (OI-state, CVD-div, liq-type).
