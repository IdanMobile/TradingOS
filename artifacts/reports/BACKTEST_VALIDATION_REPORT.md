# Backtest Validation Report

Status: **FOUNDATION ONLY — not a strategy approval.**

This report records the executable validation foundation and its current ceiling.
No candidate is promoted by this artifact.

## Implemented

- G1 reproducibility evidence predicate with provenance and rerun parity.
- G2 timestamp integrity, UTC, duplicates, spacing, gaps, and feature timing predicate.
- G3 canonical-vs-implementation semantic parity predicate.
- G4 temporal leakage and lookahead predicate; the fixed-stake follow-up was attempted,
  but Freqtrade forced `stake_amount=10000` and `max_open_trades=-1`, so the warning
  remains unresolved rather than being converted into a clean pass.
- G5 zero-cost-only profitability hard-fail predicate.
- G5 complete six-cell post-hoc cost sensitivity surface from canonical B2 trades.
- G11 comparison against cash and B1 buy-and-hold; B2 underperforms both in the retained run.
- G6 engine-backed development, validation, and untouched holdout runs are executed and normalized.
- G8 five neighboring parameter variants are executed on the untouched holdout; all remain negative.
- G7 all 18 planned walk-forward test windows are executed; zero are positive.
- G9 holdout trades are segmented by ex-post realized volatility, trend, and volume labels; this is descriptive evidence, not a predictive regime model.
- Deterministic planners for the mandatory six-cell cost grid, chronological split,
  walk-forward windows, parameter neighborhoods, and baseline comparison.

## Not yet executed as a full package

G10 PBO/DSR method validation is explicitly deferred as a method candidate in
`artifacts/validation/B2_F0_S0/multiple_testing_method_candidate.json`. The
red-team package is present, but its verdict is no approval while G4 remains a
warning. The current reusable code and tests are deliberately not described as
production validation.

## Next gate

Connect the remaining validation predicates to retained `RUN` artifacts, execute
walk-forward/robustness/regime evidence, then produce all required machine-readable
package outputs before any prototype decision.
