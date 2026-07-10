# Framework assumptions -- SRC-FT2

- Same freqtrade bar-close-eval / next-bar-open-execution mapping as SRC-FT1.
- EMA is documented here as a standard trend indicator; this project's canonical spec has no distinct EMA-warm-up primitive, so EMA seeding is approximated as SMA-style warm-up (see ambiguities.md) -- a project-side modeling limitation, not a freqtrade semantic.
- No fee/slippage asserted by the example itself (engine/backtest-run concern).
