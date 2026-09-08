# Rule Set v1.1 — Momentum Continuation Scalp (MCS)  [AUTHORITATIVE]

Supersedes 03-ruleset-v1.md. Merges the order-flow signals (03b) and the room-to-run /
self-impact model (03c). All numbers are backtest-tunable hypotheses. No trade is "guaranteed" —
the edge is: small-near TP1 hits more often than the stop, and winners are sized ≥ losers.

Direction: LONG rules below; SHORT = exact mirror (flip all signs / bid↔ask / gainer↔loser).

---

## LAYER 0 — Instrument eligibility  (Scanner, refresh 30–60 s)

TRADEABLE only if ALL true:

| ID | Rule | Default |
|----|------|---------|
| E1 | 24h quote volume ≥ V_min | ₹15 cr (~$1.8M) |
| E2 | book depth within ±0.2% of mid ≥ 10× intended position notional | ≥ ₹1.5L for a ₹15k trade |
| E3 | spread ≤ S_max | 0.15% |
| E4 | \|funding rate\| (per 8h) ≤ F_max | 0.08% |
| E5 | \|mark − last\|/last ≤ | 0.3% |
| E6 | contract age ≥ | 7 days |
| E7 | not within ±2 min of funding settlement | — |

→ `eligible_universe[]`

---

## LAYER 1 — Hotness ranking + candidate filter  (Scanner, 30–60 s)

Compute per coin: `ret_5m/15m/1h`, `RVOL_5m/15m`, `tps_ratio` (trades/min last 5m ÷ 4h baseline),
`atr_expanding`, `OI_delta_15m`, `CVD_5m` + slope, `RS_vs_BTC_15m` (coin ret − BTC ret),
top gainer/loser 1h rank, `leg_count_15m` (# of up-legs), `avg_leg_size`, `cur_leg_size`.

**LONG candidate — ALL must pass:**

| ID | Rule | Default |
|----|------|---------|
| H1 | sign(ret_5m)=sign(ret_15m)=sign(ret_1h)= + | — |
| H2 | RVOL_5m ≥ | 3.0 |
| H3 | RVOL_15m ≥ | 2.5 |
| H4 | tps_ratio ≥ | 2.0 |
| H5 | atr_expanding | true |
| H6 | ret_1h within band (not exhausted) | [+3%, +22%] |
| H7 | RSI_5m ≤ | 82 |
| H8 | **OI_delta_15m > 0** (new money, not short-covering) | > 0 |
| H9 | **CVD_5m slope > 0 AND no CVD-vs-price divergence** (price higher-high ⇒ CVD higher-high) | — |
| H10 | in top gainers 1h, rank ≤ | 20 |

Divergence (price HH, CVD not) → **hard reject**, tag `fade_watch`, no action in v1.1.

`hotness = z(RVOL_5m)+z(RVOL_15m)+z(|ret_15m|)+z(tps_ratio)+z(OI_delta_15m)+z(RS_vs_BTC_15m)`
→ pass **top 5 long + top 5 short** to Observers.

---

## LAYER 2 — Entry hunt  (Observer, one per candidate, 1–10 min)

### 2a. Momentum-alive gate (every tick; drop candidate on fail)
- price > EMA_20(1m) and EMA_20(1m) rising
- ret_5m still ≥ +0.3%
- CVD_5m still sloping up

### 2b. Room-to-run score — need ≥ 6 of 9
| # | Room to run | Exhausted |
|---|---|---|
| 1 | CVD & price new highs together | CVD divergence (→ already rejected at H9) |
| 2 | cur_leg_size < 1.3× avg_leg_size | > 1.8× avg |
| 3 | 2–4 shallow bought pullbacks so far | 0 pullbacks / parabolic |
| 4 | price < 1.5× ATR(1m) above anchored VWAP (move origin) | > 3× ATR above |
| 5 | OI still rising | OI flat/falling |
| 6 | RSI_1m < 80 or reset on last pullback | pinned > 85 multi-candle |
| 7 | tape speed steady/accelerating | decelerating while price drifts up |
| 8 | liquidations: small/med shorts, accelerating | one giant print then silence |
| 9 | clear air or a liquidity magnet ABOVE within reach | entry at a magnet / prior swing high |

### 2c. Entry pattern — take ONE
- **P1 Pullback & resume (preferred):** after leg 2 or 3, price retraces 20–50% of the last
  leg on falling volume (RVOL < 1.0), then a 1m candle closes back up with RVOL ≥ 1.5 → enter.
- **P2 Micro-breakout:** range ≤ 0.6% wide for ≥ 3 min, breaks up with breakout RVOL ≥ 3.0 → enter.
- Never enter on a vertical/parabolic candle with no pullback.

### 2d. Order-book confirmation at entry instant — ALL required
| ID | Rule | Default |
|----|------|---------|
| C1 | book imbalance top-10 levels ≥ | +0.20 |
| C2 | no opposing wall (> 3× avg level size) within | 0.3% above entry (would cap TP1) |
| C3 | CVD 5m sloping up | — |
| C4 | ask liquidity being pulled ahead of price OR a level-sweep just printed | — |

### 2e. Self-impact guard — ALL required
| ID | Rule | Default |
|----|------|---------|
| S1 | order notional ≤ X% of trailing-60s traded volume | 8% |
| S2 | book-walk slippage for our size ≤ | 0.15% |
| S3 | no wall > 3× avg level size between entry and TP1 | — |
| S4 | entry order = post-only limit joining the bid on the pullback; market cross allowed only if S1 < 5% AND momentum clearly intact | — |

### 2f. Hard rejections — skip even if everything above passes
| ID | Reject if |
|----|-----------|
| R1 | last 1m candle = climax bar (range > 3× ATR_1m, closes in unfavourable third) |
| R2 | entry within 0.4% of prior swing high / round number / 1h VWAP from wrong side |
| R3 | spread > 2× trailing 10-min median |
| R4 | single liquidation print > ₹5L against our direction in last 30 s, OR the largest liq of the sequence just printed (climax) |
| R5 | BTC 5m move > 1.5% against our direction |
| R6 | funding moved > 0.03% in last 5 min against us |
| R7 | RS_vs_BTC_15m ≈ 0 (move is pure BTC beta, no idiosyncratic driver) |

---

## LAYER 3 — Execution & management

- **Entry:** post-only limit at best bid on the pullback, 3 s fill window; re-post once if missed and setup still valid; market cross only under S4. Setup broke while waiting → cancel.
- **Post-fill 15 s check:** price hasn't ticked our way AND CVD stalled → we were the marginal buyer → exit at market for scratch. Do not "give it room."
- **Risk per trade R:** 8–12% of current capital (your aggressive choice — high variance, documented). Start **R = ₹150**.
- **Leverage hard cap 12×** — if R/d implies more, shrink size.
- **Stop-loss** (hard, exchange-native, immediate): below pullback low / range low, **max 0.8%** from entry = `d`. `position_notional = R / d`.
- **Take-profit:**
  - TP1 = 1.3 × d → close 60%, move stop to breakeven
  - TP2 = trail by EMA_20(1m) or 0.5× ATR_1m (tighter of the two)
  - runner hard exit: first 1m close below anchored VWAP (move origin)
  - never target through R2 resistance minus 0.1% buffer
- **Time stop:** TP1 not hit in 4 min AND |move since entry| < 0.2% for 2 min → market exit.
- **Momentum-death exit:** 1m close back through EMA_20(1m) against us → exit remainder now.

---

## LAYER 4 — Coordinator / Master

| ID | Rule | Default |
|----|------|---------|
| M1 | max concurrent positions | 1 (→2 above ₹10k) |
| M2 | max new trades / hour | 6 |
| M3 | 3 consecutive losses → pause | 2 h |
| M4 | daily net loss ≥ 20% of day-start capital → stop | rest of day |
| M5 | daily net profit ≥ 30% of day-start capital → stop or halve R | user call |
| M6 | no new trade if BTC 5m realized vol > 2× its 24h avg | — |
| M7 | no 2 concurrent same-direction positions, corr_1h > 0.7 | — |
| M8 | reconcile wallet vs internal ledger every 5 min; halt on mismatch | — |

---

## Liquidation-impulse sub-playbook (separate, optional, higher variance)

Trigger detect: ≥ 3 liq prints same side in ~30 s + price accelerating + wick.
Classify and take ONE:
- **Cascade continuation:** enter only AFTER first deceleration (liq rate drops / 1 counter-candle). Limit order in the pullback. Stop beyond the deceleration candle. Fast TP1.
- **Exhaustion fade:** after the single largest liq print + volume climax + long wick + tape dies. Limit near the wick extreme. Stop beyond wick. TP = anchored VWAP.
- Always limit orders. Missed fill > chased fill. Book is gapped during cascades.

---

## Expectancy check (the go/no-go after testing)

Break-even hit rate ≈ 52% (TP1 = 1.3d, stop = 1.0d, fees ≈ 0.2d).
Target with all filters: **56–62%** TP1-before-stop.
If honest scorecard/backtest `p < 52%` → edge absent → do NOT automate, revise or drop.

## Full tunable parameter list
V_min, S_max, F_max, RVOL_5m(3.0), RVOL_15m(2.5), tps_ratio(2.0), ret_1h band[3,22]%, RSI_5m cap(82),
RSI_1m cap(80/85), OI_delta gate, CVD-divergence gate, hotness weights,
retrace %(20–50), pullback-vol(<1.0), resume-RVOL(1.5), range width(0.6%), breakout RVOL(3.0),
room-to-run threshold(6/9), C1 imbalance(0.20), C2/S3 wall mult(3×), S1 size/60s-vol(8% / 5% cross),
S2 slippage(0.15%), d_max(0.8%), TP1 mult(1.3), time-stop(4 min), stall band(0.2%),
R(₹150), lev cap(12×), M2(6/h), M3(3 / 2h), M4(20%), M5(30%), M6(2×), M7(0.7).
