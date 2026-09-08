# Contributing / workflow

Solo repo, but run it like a team so history stays clean.

## Branches
- `main` — protected in spirit; only PR merges, always passing CI locally (`ruff`, `mypy`, `pytest`).
- `develop` — integration branch; feature branches merge here first.
- `feat/<issue#>-slug`, `fix/<issue#>-slug`, `chore/<issue#>-slug` — one per issue.

## Cycle
1. Pick a GitHub issue. Create the branch off `develop`.
2. Small commits, imperative subject (`add coindcx rest client`), body explains *why*.
3. Open a PR into `develop`, body: `Closes #<issue>`. Run `/review` (the `trade-reviewer`
   subagent) and fix BLOCKER/MAJOR findings. Squash-merge once CI is green.
4. Periodically PR `develop` -> `main` as a release, tag `v0.x.y`.

## Standards
- Python 3.11+, `from __future__ import annotations`, full type hints.
- `ruff format` + `ruff check`; `mypy src` clean.
- Pydantic models for all external data and inter-agent messages.
- No secrets in code or committed config. `.env` only.
- Every agent has a unit test with a fake feed; no test hits the network.
- No real-order code path merges without an explicit issue and review note.

## Commit trailer
```
Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```
