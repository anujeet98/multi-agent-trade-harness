# 07 — How the LLM connects (and where it does NOT)

## Key decision: most "agents" here are NOT LLM agents

The scanner / observer / risk agents are **deterministic functions over numbers** — RVOL,
CVD slope, book imbalance, OI delta, threshold checks. They must run every 1–60 s, be
back-testable, and give the same output for the same input. An LLM in that loop would be:
slow (seconds/call), rate-limited, non-deterministic (can't backtest), and costly.

So: **the hot path has no LLM.** "Multi-agent" here = multiple concurrent deterministic
monitors + a coordinator, coordinated over an event bus. This is a feature, not a limitation.

## Where an LLM *is* useful (slow cadence, off the hot path)

| Node | Cadence | Job |
|------|---------|-----|
| `agents/context_llm` | every 5–15 min | read exchange announcements / news / social feeds (E-tier signals), output a structured `MarketContext` (risk-on/off, event-imminent, listing-pump watch) that the coordinator uses as a gate |
| `agents/review_llm` | end of session / on demand | read the run log + scorecard, summarize what worked, propose parameter changes for v1.2 |
| `agents/intent_sanity_llm` (optional) | per TradeIntent | a final natural-language sanity check on an ambiguous setup before the coordinator acts — veto only, never creates trades |

All three consume already-computed numbers/text. None places orders. The coordinator can run
fully without them.

## Connecting to Claude on your existing Claude Code plan

Use the **Claude Agent SDK** (`pip install claude-agent-sdk`) — this is Claude Code packaged
as a library. It authenticates the same way the Claude Code CLI does: if you're logged in
(`claude` CLI / `claude setup-token`), the SDK uses your **existing subscription quota**, no
separate API key, no extra billing.

```python
# src/mats/llm/client.py  (sketch — not committed yet)
from claude_agent_sdk import query, ClaudeAgentOptions

async def ask_context(feed_digest: str) -> str:
    opts = ClaudeAgentOptions(system_prompt=CONTEXT_PROMPT, max_turns=1)
    out = []
    async for msg in query(prompt=feed_digest, options=opts):
        out.append(msg)
    return _extract_text(out)
```

Trade-offs to accept:
- Subject to Claude Code plan usage limits / throttling — fine at 5–15 min cadence, not fine
  per-tick (another reason the hot path stays LLM-free).
- Not for latency-critical decisions.
- Fallback: an `ANTHROPIC_API_KEY` (pay-as-you-go) can be set to bypass plan limits later;
  the client abstraction supports both.

Alternative if we ever want a hosted/scheduled LLM node: Anthropic API + Tool Runner, or
Managed Agents — but that's paid API billing, deferred.

## What to build (issues)

| Issue | Deliverable |
|------|-------------|
| #11 | `llm/client.py` — thin async wrapper over Claude Agent SDK, config-driven (plan auth default, API key optional), returns structured Pydantic models, times out fast, degrades gracefully when unavailable |
| #12 | `agents/context_llm.py` — feed digest → `MarketContext`; coordinator gate |
| #13 | `agents/review_llm.py` — session log → review + param proposals |

> LLM nodes land AFTER the deterministic core (#2–#9) is running in paper mode. They are
> enhancers, not blockers.
