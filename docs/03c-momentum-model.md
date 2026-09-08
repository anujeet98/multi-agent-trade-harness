# 03c — Your momentum model, translated + the 2 gaps to close

## Your observations → the real concept

| What you said | The actual mechanism | How to measure it |
|---|---|---|
| "coin keeps trying higher jumps in short time" | **impulsive trend / momentum regime** — a series of up-legs with shallow pullbacks | count up-legs vs down-legs last 15m; ADX(1m) rising; higher-highs + higher-lows on 1m |
| "long orders cutting the sell" | **aggressive buyers lifting the offer faster than sellers replenish** = ask-side liquidity depleting | CVD rising; aggressor buy-ratio > 0.6; ask depth within 0.3% shrinking tick-over-tick |
| "momentum is shifting" | **order-flow imbalance flip** — delta turns positive, bids start stacking under price | CVD slope flip; bid replenishment rate > ask replenishment rate |
| "my entry triggers a reverse" | **you are taking the last of the liquidity** (liquidity exhaustion) and/or **your size is a big % of current flow** → nothing left to push price after you | your order size ÷ trailing-60s volume; book-walk slippage for your size |
| "price hits a liquidation → strong direction change" | **liquidation cascade** — forced market orders feeding on themselves until liquidity absorbs them | liq-print cluster same side + price acceleration + long wicks |

## The one correction

Momentum scalping is **not** guaranteed profit. Even clean setups fail ~35–45% of the time.
What makes it *work* is that TP1 (small, near) gets hit **more often than** the stop, and you
size so winners ≥ losers. Your recurring "my entry flipped it" experience is real and it has a
specific cause: **you keep entering at the exhaustion point of the leg** — the moment when the
move looks strongest is often when the last buyers (including you) have just finished buying.
Closing that gap is 80% of the edge. Two things do it: a **room-to-run filter** and a
**self-impact guard**.

---

## GAP 1 — "Room to run" filter (is there fuel LEFT, or is this the top of the leg?)

Enter only if MOST of these say room remains:

| Signal | Room to run (ENTER) | Exhausted (SKIP / fade) |
|---|---|---|
| CVD vs price | both making new highs together | price new high, CVD flat/lower (**divergence**) |
| Current leg size | < 1.3× the average up-leg of last 15m | > 1.8× average leg — over-extended |
| Pullbacks so far | 2–4 shallow pullbacks, each bought | 0 pullbacks, one vertical candle (parabolic) |
| Distance from anchored VWAP (move origin) | < ~1.5× ATR(1m) above it | > 3× ATR above it — stretched |
| OI | rising (new longs) | falling (short covering only) or flat |
| RSI(1m) / Stoch | < 80, or has reset on a pullback | pinned > 85 for multiple candles |
| Tape speed | accelerating or steady | decelerating while price still drifts up |
| Liquidations | small/medium shorts, *accelerating* | one giant print, then stream stops |
| Nearest resistance / liquidity magnet | clear air / a magnet ABOVE within reach | entry is right at a magnet or prior swing high |

Rule: need ≥ 6 of 9 in "room to run". A CVD divergence alone is an automatic skip for longs.

**Best entry = the shallow pullback after leg 2 or 3**, not the breakout of leg 1's high while
it's going vertical. You give up the first burst; you gain a stop that actually makes sense and
a move that isn't done.

---

## GAP 2 — Self-impact guard (will MY order flip the momentum?)

You flip the move when your order is large relative to what's flowing, or when you eat the last
resting liquidity before a wall. Checks, all must pass:

1. **Size vs flow:** your order notional ≤ **8%** of trailing-60s traded volume on that contract.
   If you'd be > 8%, you *are* the momentum — it stops when you stop. Reduce size or skip.
2. **Book-walk slippage:** simulate filling your size by walking the ask book. If it moves price
   > **0.15%**, book is too thin — skip.
3. **Liquidity between entry and TP1:** there should be resting opposing liquidity to trade
   against on the way to TP (you need other buyers too) BUT no single wall > 3× average level
   size sitting between entry and TP1 (it will cap the move exactly where you need it to go).
4. **Entry style:** prefer a **limit/post-only order that joins the bid** on a micro-pullback —
   you add liquidity, you don't consume the fuel. Only cross with a market order if (a) size is
   < 5% of 60s volume and (b) momentum is still clearly intact. Never market-buy into a vertical
   candle — that's when your fill *is* the top.
5. **After-fill check (first 10–15 s):** if price doesn't tick your way at all and CVD stalls
   right after your fill → you were the marginal buyer. Exit immediately for ~scratch, don't
   "give it room."

---

## Liquidation-impulse entries (higher R:R, higher risk — separate playbook)

Detect a cascade: ≥ 3 liquidation prints same side within ~30 s + price accelerating + wick.
Two DIFFERENT trades can follow — you must decide which:

**A) Continuation (trade WITH the cascade):**
- Only after the cascade shows its **first deceleration** (liq rate drops, one small counter-candle) — never during the vertical part.
- Entry: limit order just inside the pullback, not market into the flush.
- Thesis: forced selling isn't done, more stops below → another leg down (or up for short-liq cascade).
- Stop: back above the deceleration candle. Tight. TP1 quick.

**B) Exhaustion fade (trade AGAINST the cascade):**
- After the **single largest** liq print of the sequence + volume climax + long wick + tape dies.
- Thesis: forced flow is spent, price snaps back to VWAP.
- Entry: limit at/near the wick extreme. Stop just beyond the wick. TP = anchored VWAP.

Risk you named ("my order fills further"): in a cascade the book is *gapped* — market orders
slip badly. **Always use limit orders for liquidation trades**, accept missed fills, never chase.

---

## Folds into Rule Set v1.1

- Layer 1: add CVD-divergence as a hard reject; add "leg extension" and "pullback count" to hotness.
- Layer 2: replace generic entry with **"pullback after leg 2–3 + ≥6/9 room-to-run"**; add the
  5-point self-impact guard as a pre-fill gate; add post-fill 15-s scratch rule.
- Layer 2: split liquidation handling into cascade-continuation vs exhaustion-fade with the
  deceleration trigger; force limit orders.
- Scorecard: new columns → CVD-div (y/n), leg-extension (x avg), pullbacks-so-far, size-vs-60s-vol %.
