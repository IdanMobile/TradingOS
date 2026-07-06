# Engine Bake-Off Blueprint V1

Status: Draft for execution planning; no engine winner approved.
Date: 2026-07-05

## Objective
Select reusable engine roles for the Crypto Spot MVP using common executable evidence rather than marketing, popularity, or architectural preference.

## Candidates in first bake-off
1. Freqtrade — crypto-native research/backtest/dry-run/live candidate.
2. NautilusTrader — execution-grade event-driven research/backtest/live candidate.
3. LEAN — broad multi-asset research/backtest/live candidate.
4. Hummingbot — crypto-native bot operations/market-making/controller candidate.

vectorbt is evaluated separately as a research accelerator, not as a direct execution-core peer.

## Why no single winner is assumed
The candidates optimize different concerns. The bake-off must permit a role-based result such as:
- Freqtrade for rapid Crypto Spot strategy iteration and dry-run.
- NautilusTrader for execution-grade simulation/live semantics.
- Hummingbot for market-making and bot-fleet operations.
- LEAN retained for future multi-asset portability.

## Common initial market slice
- Market family: Crypto Spot.
- Instruments: BTC/USDT and ETH/USDT where venue/data support permits.
- Timeframes: 5m, 15m, 1h.
- Historical periods: multiple market regimes; exact windows depend on data completeness.
- No leverage.
- No real capital.

## Common baseline strategies
The goal is infrastructure comparison, not profit discovery.

### B1 — Buy and hold sanity baseline
Purpose: verify returns, timestamps, portfolio accounting, and data boundaries.

### B2 — Moving-average crossover
Purpose: deterministic signal parity and warm-up behavior.

### B3 — Bollinger mean-reversion baseline
Purpose: entry/exit rules, fees, staged exits, and indicator parity.

### B4 — Volatility breakout baseline
Purpose: stop/trigger semantics and regime-sensitive behavior.

## Required common inputs
- Canonical dataset manifest.
- Timezone definition.
- Candle construction rule.
- Missing-data policy.
- Fee schedule.
- Slippage assumptions.
- Starting capital.
- Order sizing rule.
- Precision/tick/lot constraints.
- Strategy code/logic specification independent of engine.

## Test matrix
| Gate | Required evidence | Pass condition |
|---|---|---|
| Installability | repeatable setup on target Mac | documented one-command or bounded setup |
| Data ingestion | same canonical input accepted or adapted | no silent row loss |
| Determinism | repeated identical run | identical trade/equity artifacts where engine is deterministic |
| Signal parity | canonical signal timestamps | discrepancies explained |
| Fee modeling | explicit fees | net results reflect configured costs |
| Slippage | configurable model | assumptions visible in artifact |
| Precision | venue constraints | invalid quantity/price behavior explicit |
| Warm-up | indicator initialization | no future leakage |
| Bias checks | lookahead/leakage tooling | native or external path documented |
| Parameter sweep | bounded search | all trials retained, not only winner |
| Artifact export | trades/equity/metrics/logs | machine-readable outputs |
| Paper path | forward/dry/paper capability | supported or explicit gap |
| Live path | same/related strategy semantics | gap documented |
| API integration | programmatic control | sufficient for OS adapter |
| Failure behavior | invalid order/data interruption | observable and recoverable |
| Maintenance | current docs/releases | active enough for candidate status |

## Freqtrade-specific probes
- Backtest same baseline.
- Run `lookahead-analysis`.
- Run recursive-analysis where applicable.
- Hyperopt bounded search with all-trial retention.
- Dry-run forwarding.
- Export trades/results for OS evidence layer.
- Document unsupported order semantics and exchange-specific constraints.

## NautilusTrader-specific probes
- Bar backtest first.
- Trade/order-book replay optional second stage.
- Fee/fill/latency model configuration.
- Same strategy configuration concept across backtest/live.
- Catalog/persistence export.
- Adapter surface for selected exchange.

## LEAN-specific probes
- Local engine setup.
- Crypto baseline backtest.
- Fill/brokerage model behavior.
- Paper/live path and local-vs-cloud dependency mapping.
- Artifact/API integration.

## Hummingbot-specific probes
- Controller configuration.
- Dashboard/API backtest path.
- Bot instance lifecycle.
- Existing controller reuse.
- Market-making relevance.
- Artifact extraction into external evidence layer.

## Scoring dimensions
No single aggregate score may hide a hard failure.

1. Backtest realism.
2. Research iteration speed.
3. Reproducibility.
4. Bias-control capability.
5. Paper/live parity.
6. Crypto Spot fit.
7. Programmatic integration.
8. Observability/artifact quality.
9. Maintenance burden.
10. Future multi-market portability.

## Hard rejection conditions
- Cannot reproduce a deterministic baseline without unexplained divergence.
- Silent data mutation/loss that cannot be controlled.
- No viable artifact extraction path.
- Critical project dependency is unmaintained or incompatible.
- Paper/live semantics are materially misleading and cannot be bounded.

## Output artifacts
- `results/<candidate>/<run-id>/manifest.json`
- canonical trades CSV/Parquet
- equity curve
- metrics JSON
- logs
- environment/version manifest
- divergence report
- pass/fail report

## Decision rule
Possible outcomes:
- Select as primary role.
- Select for specialized role.
- Retain as fallback.
- Reject.

No result is allowed to claim a strategy is profitable merely because an engine backtest is positive.
