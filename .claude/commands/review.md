---
description: Run the domain-aware trade-reviewer on the current branch (or a given PR/branch/path)
---

Use the Agent tool with `subagent_type: "trade-reviewer"` to review $ARGUMENTS
(default: the current branch's diff vs `develop`).

Relay the reviewer's findings to me verbatim, most-severe first, with its verdict.
Do not apply fixes unless I ask.
