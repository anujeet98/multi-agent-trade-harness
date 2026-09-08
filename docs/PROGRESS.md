# PROGRESS — running context & session handoff

Purpose: anything a fresh session (or future you) needs to continue without re-deriving.
Update this at the end of every working session. Newest status at the top.

---

## Current status (as of 2026-09-09, end of session)

- **Phase:** building the paper-mode MVP (Epic #1). Deterministic core first.
- **Repo:** github.com/anujeet98/multi-agent-trade-harness (public). Local: `~/Desktop/multi-agent-trade-harness`.
  Python venv at `.venv` (python 3.12). Verify with `ruff check src tests && mypy src && pytest -q`.
- **Branches:** `main` (green, PR merges only), `develop` (integration), `feat/<issue#>-slug` per issue.
- **Merged into `develop`:** scaffold, #2 (bus/clock/indicators), #3 (feeds), #4 (scanner),
  #17 (trade-reviewer subagent), #18 (OKX-rejected doc).
- **OPEN — pick up here:** **PR #21** (`feat/5-observer`, issue #5) — observer / Layer 2.
  56 tests green, ruff+mypy clean. Awaiting user review + merge. Self-review notes + the
  `momentum_alive` spec deviation are in the PR body. Follow-up issue #22 tracks 4 approximated
  Layer 2 signals (C4, room #7/#8, R6).
- **Workflow each issue:** branch off develop → implement + tests → `ruff`/`mypy`/`pytest` →
  push → open PR `Closes #n` → user runs `/code-review <PR#>` → fix findings → user merges.
  (The project `trade-reviewer` subagent only loads on a fresh Claude Code start.)

## Tomorrow — start here

1. If PR #21 not yet merged: wait for user, apply any `/code-review 21` findings.
2. Once #21 is in: **Issue #6 — risk agent** (`agents/risk.py`). Layer 3 sizing
   (`position_notional = risk / stop_distance`, effective-leverage cap ≤12×, stop/TP1/TP2
   math, time-stop, momentum-death exit) + Layer 4 circuit breakers M1–M8 (concurrency,
   trades/hr, loss streak, daily loss/profit, BTC-vol halt, correlation, ledger reconcile).
   All params already in `config.StrategyParams`. Consumes `TradeIntent`, emits a sized/vetoed
   decision for the coordinator (#8).
3. Then #7 paper broker, #8 coordinator, #9 wiring/logging, #10 replay.

- **Blocked on user:** nothing. (Later: CoinDCX read-only API key for live feed test;
  Binance-vs-Bybit reachability check; CoinDCX endpoint verification = issue #16.)

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

- Binance API reachable from user's IP (India)? Fallback: **Bybit v5** (OKX rejected — exited
  India, see DECISIONS D7a).
- Which CoinDCX perps overlap with Binance perps (symbol map) — affects tradeable universe.
- Does CoinDCX expose a liquidation stream? If not, use Binance `!forceOrder@arr` as proxy.
- CoinDCX futures fee tier confirmation (~0.05% + 18% GST assumed).
