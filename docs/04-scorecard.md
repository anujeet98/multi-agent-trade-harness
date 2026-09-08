# Step 4 — Manual Scorecard (test Rule Set v1.1 before coding anything)

Goal: ~15 rows. Log a setup the moment it looks hot, apply Rule Set v1.1 (`05-ruleset-v1.1.md`)
by hand, then record what price actually did in the next 5 min. No agents, no API yet.
This tells us if the rules have real edge (need TP1-first ≥ 52%, target 56–62%).

## Columns
- **Time** IST · **Coin/Side**
- **L0**: E1–E7 pass? note fails
- **r5 / r15 / r1h**: % change
- **RVOL5 / RVOL15**: rough vs recent bars (1x / 3x / 5x…)
- **OI**: rising ↑ / flat → / falling ↓ over last 15m
- **CVD**: up-with-price / **DIV** (price HH, CVD not) / down
- **RS vs BTC**: coin stronger than BTC last 15m? y / n / ≈0
- **Rank**: top gainers/losers 1h rank
- **Legs**: # up-legs so far · **CurLeg**: current leg size ÷ avg leg (e.g. 1.1x)
- **Pullbacks**: how many shallow bought dips so far
- **Room score**: __ / 9 (Layer 2b)
- **Pattern**: P1 pullback / P2 breakout / none
- **Book**: imbalance side + any wall within 0.3% above
- **Size/60s**: your intended order as % of last-60s volume (S1, keep ≤8%)
- **Verdict**: ENTER L/S  |  REJECT (reason id: H#/R#/S#/room)
- **Next 5 min**: TP1 (+1.3d) or Stop (−1.0d) hit first? by how fast?
- **Real?**: traded live y/n + net PNL
- **Note**

## Rows

| # | Time | Coin/Side | L0 | r5 | r15 | r1h | RVOL5 | RVOL15 | OI | CVD | RS | Rank | Legs | CurLeg | Pullbacks | Room /9 | Pattern | Book | Size/60s | Verdict | Next 5m: TP1/Stop | Real? PNL | Note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | | | | | | | | | | | | | | | | |
| 2 | | | | | | | | | | | | | | | | | | | | | | | |
| 3 | | | | | | | | | | | | | | | | | | | | | | | |
| 4 | | | | | | | | | | | | | | | | | | | | | | | |
| 5 | | | | | | | | | | | | | | | | | | | | | | | |
| 6 | | | | | | | | | | | | | | | | | | | | | | | |
| 7 | | | | | | | | | | | | | | | | | | | | | | | |
| 8 | | | | | | | | | | | | | | | | | | | | | | | |
| 9 | | | | | | | | | | | | | | | | | | | | | | | |
| 10 | | | | | | | | | | | | | | | | | | | | | | | |
| 11 | | | | | | | | | | | | | | | | | | | | | | | |
| 12 | | | | | | | | | | | | | | | | | | | | | | | |
| 13 | | | | | | | | | | | | | | | | | | | | | | | |
| 14 | | | | | | | | | | | | | | | | | | | | | | | |
| 15 | | | | | | | | | | | | | | | | | | | | | | | |

## Tally (after 15 rows)
- ENTER verdicts: __
- TP1-first: __ / Stop-first: __ / time-stop scratch: __  → **hit rate __%** (need ≥52%)
- avg win (in R): __ · avg loss (in R): __ · expectancy per trade: __
- REJECTs that would've been winners (missed edge): __  → which filter was too strict? __
- ENTERs that lost: most common cause? __
- CVD-divergence rule: did it correctly filter losers? __
- Self-impact: any trade where your fill visibly stalled the move? __
- Parameters to change for v1.2: __
