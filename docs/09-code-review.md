# 09 — Code review

Three layers, cheapest first.

## 1. Automatic (every push / PR)
`.github/workflows/ci.yml` runs `ruff check`, `ruff format --check`, `mypy src`, `pytest -q`.
A PR must be green before merge.

## 2. Domain-aware review agent — `.claude/agents/trade-reviewer.md`
A project subagent that reviews against the trading-specific failure modes (sign errors,
look-ahead bias, fee/leverage/stop math, async races, safety-guard bypass) plus general
quality. Read-only — it never edits.

**Run it:**
- `/review` — reviews the current branch's diff vs `develop`
- `/review 15` — reviews PR #15
- `/review src/mats/feeds` — reviews a path
- Or ask directly: "use the trade-reviewer subagent on this branch"

Do this before merging every PR. Fix BLOCKER/MAJOR findings; MINORs are judgement calls.

## 3. Continuous review during a work session (loop)
While building a feature, keep a reviewer running so regressions surface early:

```
/loop 15m /review
```

Runs `/review` every 15 minutes on whatever the working branch currently is. Stop it from
`/tasks`. Useful during a long implementation session; not needed for small changes.

For a one-off deep pass, the built-in `/code-review high` (or `ultra` for the multi-agent
cloud review) complements the domain agent — run it on the epic branch before merging
`develop → main`.

## What the review agent can't catch
- Whether the *strategy* is profitable — that's the backtest (#10) and live scorecard.
- Wrong CoinDCX endpoint paths — needs the live check (#16).
- Real-money behaviour — paper mode first, always.
