# PROGRESS — running context & session handoff

Purpose: anything a fresh session (or future you) needs to continue without re-deriving.
Update this at the end of every working session. Newest status at the top.

---

## Current status (2026-09-08)

- **Phase:** building the paper-mode MVP (Epic #1). Deterministic core first.
- **Repo:** github.com/anujeet98/multi-agent-trade-harness (public). Local: `~/Desktop/multi-agent-trade-harness`.
- **Branches:** `main` (green only, PR merges), `develop` (integration). Feature: `feat/<issue#>-slug`.
- **Done:** project scaffold, config with all Rule Set v1.1 params, typed models, full strategy
  docs, architecture + LLM design, data-source design, 13 GitHub issues.
  **Issue #2** (`feat/2-core-bus-indicators`): event bus, SimClock/RealClock, indicator
  library (EMA, RollingSum, RVOL, CVD+slope, ATR, AnchoredVWAP, OI delta, book imbalance /
  microprice / spread / walk-slippage). 17 tests, ruff+mypy clean. CI workflow added. → PR open.
- **Next:** merge #2 PR into develop, then issue #3 — CoinDCX + Binance feed clients.
- **Blocked on user:** nothing. (Later: CoinDCX read-only API key for live feed test; decision
  on Binance-vs-Bybit indicator source once we hit geo/availability reality.)

## How we got here (decision trail — see DECISIONS.md for the reasoning)

1. Goal: systematic crypto perp-futures trading on **CoinDCX** (trades strictly there),
   compound a tiny account (₹1.3k now) toward ₹20–25k, then re-strategize.
2. "HFT" is not achievable on retail rails → we build **mid-frequency momentum-continuation
   scalp (MCS)**: ride an already-moving high-volume perp for a small fast TP, long & short.
3. User's real trades (2 ARX/USDT longs, +₹600 net) analysed → they were running ~11x
   leverage, ~₹300–450 real risk/trade, 2 wins = small-sample luck, not proven edge.
4. Built **Rule Set v1.1** (`05-ruleset-v1.1.md`) — the authoritative programmable spec:
   Layer 0 eligibility, Layer 1 hotness/candidate filter, Layer 2 entry hunt (room-to-run
   score + self-impact guard), Layer 3 execution, Layer 4 coordinator/circuit-breakers.
5. Key user insight captured: "my entry flips the momentum" = entering at leg exhaustion +
   order size too big vs flow → addressed by the room-to-run filter and self-impact guard
   (`03c-momentum-model.md`).
6. Architecture: **deterministic multi-agent** over an event bus. LLM is NOT in the hot path
   (latency/backtestability). LLM only on slow nodes (context/news gate, session review) via
   **Claude Agent SDK on the user's Claude Code plan**.
7. **User accepted skipping the manual scorecard** and going straight to code (their risk
   call). Scorecard (`04-scorecard.md`) still available for parallel live validation.
8. Data sources: indicators from **Binance USDⓈ-M Futures public API/WS** (richest, free),
   CoinDCX API authoritative for tradeable universe + account + order placement. MCPs not in
   the hot path (see `08-data-sources.md`).

## Parked / future

- **LLM-as-decision-brain:** revisit if we move to a longer hold window (~15–30 min). User's
  rationale: fixed rules drift as we learn; an LLM master would adapt and gives a single
  conversational control point. Plan: keep the coordinator interface able to consult an LLM
  advisor per-decision when latency budget allows.
- Multi-position concurrency (>1) once capital > ₹10k.
- Live order placement — gated, not built, separate issue, explicit review.

## Open questions to resolve later

- Binance API reachable from user's IP (India)? Fallback: Bybit or OKX as indicator source.
- Which CoinDCX perps overlap with Binance perps (symbol map) — affects tradeable universe.
- Does CoinDCX expose a liquidation stream? If not, use Binance `!forceOrder@arr` as proxy.
- CoinDCX futures fee tier confirmation (~0.05% + 18% GST assumed).
