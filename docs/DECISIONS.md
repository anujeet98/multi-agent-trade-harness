# DECISIONS — architecture decision log

One entry per material decision. Append; don't rewrite history. Format: what / why /
alternatives / status.

---

## D1 — Strategy: momentum-continuation scalp (MCS), not HFT
- **What:** ride an already-moving high-volume perp for a small near TP (~1.3× stop distance),
  seconds-to-minutes hold, long & short symmetric.
- **Why:** true HFT needs colocation / sub-ms infra unavailable on retail crypto rails. Edge
  here comes from signal quality, not speed. Small-near TP hits more often than the stop.
- **Alternatives considered:** funding/basis mean-reversion (slower, fewer trades — parked as
  a later strategy), orderbook-imbalance micro-scalp (too latency-sensitive), liquidation-fade
  (kept as an optional sub-playbook).
- **Status:** active. Spec = `05-ruleset-v1.1.md`.

## D2 — Trades execute on CoinDCX only; indicator data can come from anywhere
- **Why:** user's account, INR rails, and F&O access are on CoinDCX. Data quality there is
  thinner, so we source signals from a deeper venue and only place orders on CoinDCX.
- **Status:** firm.

## D3 — Deterministic hot path; LLM only on slow, off-path nodes
- **What:** scanner / observer / risk / coordinator are pure deterministic functions over
  numbers. LLM used only for: news/announcement context (5–15 min cadence), session review,
  optional pre-trade sanity veto.
- **Why:** an LLM per tick is too slow (2–10 s), rate-limited, non-deterministic (can't
  backtest), and risky on leveraged money. The "brain" is the rule set; the coordinator just
  executes it fast.
- **Alternatives:** LLM master making each trade call — **parked**, revisit at a 15–30 min
  hold window where latency is affordable. User's rationale for wanting it: rules drift as we
  learn; an adaptive LLM master needs only one conversational control point. Mitigation: keep
  the coordinator able to consult an LLM advisor per-decision when the latency budget allows.
- **Status:** active. Design = `07-llm-integration.md`.

## D4 — LLM access via Claude Agent SDK on the user's existing Claude Code plan
- **Why:** no separate API billing; uses subscription quota; fine at 5–15 min cadence.
- **Alternative:** `ANTHROPIC_API_KEY` pay-as-you-go — kept as an optional override in the
  client abstraction for when plan limits bite.
- **Status:** active.

## D5 — Language: Python 3.11+, src-layout, ruff + mypy + pytest
- **Why:** async I/O + numpy/pandas indicators + multi-agent orchestration; doubles as the
  user's AI/ML skill-building. Rewrite only the hot execution path later if latency demands.
- **Status:** firm.

## D6 — Paper-first, live trading double-gated
- **What:** `--mode paper` is default and the only wired mode initially. `--mode live` needs
  `MATS_ALLOW_LIVE=1` + a config flag + its own reviewed issue.
- **Why:** validate expectancy on simulated fills before risking capital; fees/slippage/
  funding modelled in the paper broker.
- **Status:** firm.

## D7 — Indicator feed: Binance USDⓈ-M Futures public API/WS (primary)
- **What:** compute all indicators from Binance futures public streams (aggTrades, depth,
  klines, premiumIndex, openInterest, forceOrders). CoinDCX API is authoritative for the
  tradeable universe, contract specs, our mark/funding, account state, and order placement.
- **Why:** Binance futures data is the deepest and fully free with no auth for public market
  data; gives us cross-exchange lead-lag for free.
- **Alternatives:** OKX (has official MCP, good API — fallback), Bybit (fallback), CoinDCX
  own data (thin — used only for CoinDCX-only symbols and execution-side truth). MCPs are not
  used in the hot path — they're an LLM tool interface, extra latency/translation; may be used
  inside LLM nodes only.
- **Risk:** Binance reachability from India. If blocked → Bybit or OKX as primary.
- **Status:** active, pending reachability check (issue #3).

## D8 — Skipped the manual scorecard pre-validation
- **What:** user chose to build the harness before hand-testing the rules on 15 setups.
- **Why:** user's explicit risk acceptance; scorecard remains for parallel live validation.
- **Trade-off:** we may build agents around thresholds that don't hold — mitigated by the
  replay harness (#10) and the review LLM (#13) driving fast iteration to v1.2.
- **Status:** accepted.
