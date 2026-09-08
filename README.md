# Multi-Agent Trade Harness (MATS)

Local-run research harness for a **momentum-continuation scalp** strategy on CoinDCX perpetual
futures. Multiple monitor agents each track one class of signal; a coordinator agent fuses their
output into trade decisions. **Paper-trading only by default** — no real orders until explicitly
enabled and the strategy has proven positive expectancy.

> Status: pre-alpha scaffold. Not financial advice. Crypto F&O is high-risk; you can lose the
> full account. See `docs/00-scope.md`.

## Design

```
feeds/        CoinDCX REST + WebSocket clients -> normalized market events
core/         event bus, data models, rolling indicators
agents/
  scanner     Layer 0/1  - eligibility + hotness ranking -> candidate list
  observer    Layer 2    - one per candidate, hunts a valid entry
  risk        Layer 3/4  - sizing, stops, circuit breakers
  coordinator master     - fuses signals, opens/closes via broker
paper/        simulated broker (fills, fees, funding, slippage model)
```

Rule set the agents implement: `docs/05-ruleset-v1.1.md` (authoritative).

## Workflow

- `main` — always green, tagged releases only via PR
- `develop` — integration branch
- `feat/<issue#>-slug` — one branch per GitHub issue, PR into `develop`
- Tasks tracked as GitHub issues; every PR references its issue and is squash-merged.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add CoinDCX API keys (read-only key is enough for paper mode)
python -m mats.main --mode paper
```

## Safety rails

- `--mode paper` is the default and the only mode wired up initially.
- `--mode live` requires `MATS_ALLOW_LIVE=1` in the environment AND a config flag.
- Risk agent enforces per-trade risk, max leverage, and daily loss circuit breakers
  regardless of what the coordinator requests.
