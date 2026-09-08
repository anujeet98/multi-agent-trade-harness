# Trade Log & Analysis

## Session 1 — 2026-09-08, ~22:00 IST, ARX/USDT (long x2)
Capital at start: ~₹1,300. Manual, discretionary.

| # | Open | Close | Hold | Gross PNL | Fees (both sides, incl 18% GST) | Net PNL |
|---|------|-------|------|-----------|-------------------------------|---------|
| 1 | 22:00:30 | 22:09:30 | 9 min | +₹442.92 | ₹8.76 + ₹9.02 = ₹17.78 | **+₹425.14** |
| 2 | 22:13:03 | 22:15:28 | 2 min | +₹293.52 | ₹11.25 + ₹11.42 = ₹22.67 | **+₹259.42** |
| | | | | **+₹736.44** | **₹40.45** | **+₹684.56** |

(User reports ~+₹600 net after rounding/slippage. Small diffs = market slippage vs displayed price.)

### Reverse-engineered mechanics
- CoinDCX futures taker fee ≈ 0.05% × 1.18 GST ≈ **0.059% per side (~0.12% round-trip)**.
- Position notional ≈ open_fee ÷ 0.00059:
  - Trade 1: ₹8.76 / 0.00059 ≈ **₹14,850 notional** on ₹1,300 → **~11x effective leverage**
  - Trade 2: ₹11.25 / 0.00059 ≈ **₹19,100 notional** on ~₹1,725 → **~11x effective leverage**
- Gross price move captured: Trade 1 ≈ +3.0%, Trade 2 ≈ +1.5% (displayed 0.15→0.16 is rounding).
- Fee drag was only ~0.12% of notional per trade because holds were short and moves were large. Fees are NOT the problem when the move is 1.5–3%. Fees kill you when the move is 0.3%.

### What actually happened (honest read)
- **You ran ~11x leverage, not 3x.** At 11x, a 3% move against you = **−33% of account ≈ −₹450** on ONE trade. You took that downside risk twice and both went your way.
- **Risk per trade was ~₹300–450 (23–35% of account), not ₹75.** My ₹75 figure was a *max-loss budget* (1.5% of a ₹5k account). You're playing 4–5x more aggressively.
- **n = 2. This is not edge yet.** Two wins on a momentum move in a thin alt (ARX @ 0.15 USDT) is a coin landing heads twice. The same setup with an 11x position and a 5% adverse spike = account gone.
- **ARX is illiquid.** Thin book → you can get filled far from displayed price on exit, or not be able to exit during a dump. Tonight the liquidity was with you.
- The **−₹11,43,236 "Net PNL" header** is a display/ledger artifact (lifetime INR asset field or a UI bug) — not your real balance. Verify actual wallet balance separately.

### Verdict
Good result, high-variance process. The profit came from **correctly reading momentum on a thin alt + aggressive leverage + luck on the tail**. Repeat this 20 times and the leverage math says one bad spike erases many wins. To make this systematic we need: entry rule, stop rule (hard), size rule, and an instrument-liquidity filter.

## Next step
Reconstruct these 2 trades as rules: what did you actually see that made you enter ARX at 22:00 and 22:13? (price action, volume, a Telegram call, book, funding — whatever it was.) That's the raw material for the rule set.
