# Freqtrade lookahead follow-up — requested fixed stake

Date: 2026-07-10 · Strategy: B2MaCrossover · Window: 2025-01-01→2025-04-01

## Requested configuration

The command explicitly supplied `--stake-amount 1000`, `--max-open-trades 1`,
and `--dry-run-wallet 1000`.

## Observed tool behavior

The Freqtrade lookahead analyzer overrode the requested values. Its log records:

- `stake_amount: 10000`
- `max_open_trades: -1`
- `Found 5829 trades, calculating 20 trades`

The result still reported `has_bias=True`, with 2 biased entry signals and 0
biased exits/indicators. This reproduces the original warning and means the
fixed-stake follow-up could not be performed through this tool invocation.

## Disposition

G4 remains **WARN / unresolved tool limitation**. The signal math remains
independently verified as trailing-only, but the analyzer result cannot be
used as a clean pass until a stake-state-independent bias check is run outside
the tool's forced configuration or the tool behavior is otherwise resolved.

Raw log: `artifacts/bakeoff/freqtrade/lookahead_fixed_stake/run.log`  
CSV: `artifacts/bakeoff/freqtrade/lookahead_fixed_stake/results.csv`
