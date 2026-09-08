# 06 — Agent architecture

Local, single-process, asyncio. One event bus; agents are independent coroutines that
subscribe to feed events and publish their outputs.

```
                +----------------------+
  CoinDCX  ---> |  feeds/               |  REST poll + WS streams
  (REST+WS)     |  -> normalized events | Candle, Trade, OrderBook, Liquidation, InstrumentStats
                +----------+-----------+
                           | event bus (asyncio pub/sub)
      +--------------------+--------------------+-------------------+
      v                    v                    v                   v
 core/indicators      agents/scanner       agents/observer     agents/risk
 rolling RVOL, CVD,   Layer 0 + 1:         Layer 2 (spawned    Layer 3/4 guards:
 EMA, ATR, OI delta,  eligibility +        per Candidate):     sizing, stop calc,
 anchored VWAP,       hotness -> emits     room-to-run score,  leverage cap, daily
 book imbalance       Candidate            entry pattern,      loss / streak breakers
                                           self-impact guard
                                           -> emits TradeIntent
                                                    |
                                                    v
                                          agents/coordinator (master)
                                          validates intent vs portfolio + risk verdict,
                                          calls broker.open() / manages TP/SL/exits
                                                    |
                                      +-------------+-------------+
                                      v                           v
                              paper/broker (default)       feeds/coindcx live broker
                              fills, fee, funding,         (guarded; not built yet)
                              slippage model
```

## Modules / issues

| Issue | Module | Deliverable |
|------|--------|-------------|
| #2 | `core/bus.py`, `core/indicators.py` | async pub/sub bus + rolling indicator library with tests |
| #3 | `feeds/coindcx.py` | REST client (markets, candles, instruments, funding, OI) + WS (trades, depth, liquidations); emits normalized events |
| #4 | `agents/scanner.py` | Layer 0 + 1 -> `Candidate` stream |
| #5 | `agents/observer.py` | Layer 2 -> `TradeIntent`; one task per candidate, self-terminating |
| #6 | `agents/risk.py` | sizing, stop/TP math, all Layer 4 circuit breakers |
| #7 | `paper/broker.py` | simulated fills w/ fee (0.059%/side incl GST), funding accrual, book-walk slippage |
| #8 | `agents/coordinator.py` | fuse intent + risk verdict; lifecycle of open positions |
| #9 | `mats/main.py` | wire everything, run loop, structured logging, run recorder |
| #10 | `scripts/replay.py` | feed recorded events back through agents for offline eval |

## Conventions
- All inter-agent messages are Pydantic models in `core/models.py`.
- No agent calls the exchange directly except `feeds/` and the (future) live broker.
- Every agent takes its dependencies (bus, params, clock) via constructor — no globals — so tests inject fakes.
- A `Clock` abstraction (real vs simulated) so replay runs deterministically.
