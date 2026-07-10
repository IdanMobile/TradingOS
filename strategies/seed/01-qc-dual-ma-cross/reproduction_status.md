# Reproduction status — SRC-QC1 (dual MA crossover)

**Status: REPRODUCED (mechanical, spot-checked).**

Scope of the claim: this reproduces the *canonical spec's own rule execution*
(source fidelity, warm-up, timing) against the project's frozen micro fixture
(`fixtures/micro/bars.csv`, 16 bars) — it does **not** claim to replicate any
historical P&L from the source, since LEAN's example algorithm carries no
profitability claim to reproduce (`profit_claims_inherited: false`) and the
16-bar fixture is not the source's own dataset.

Method: `tests/test_strategy_seed_reproduction.py::test_qc1_dual_ma_cross_reproduction`
independently recomputes SMA(3)/SMA(5) in plain Python and evaluates this
item's actual `entry_long`/`exit_long` `RuleTree` objects (parsed from
`canonical_strategy_spec.yaml` via `tios.strategy.spec`) bar-by-bar, then
asserts the two derivations agree and that the warm-up gap (bars 1-4, no
signal) and the trend-reversal crossover (signal flips as the fixture's price
path turns over at bar 11) both appear exactly where the rules imply.

Result: PASS — see test output. Verdict from `tios.strategy.validator.validate_yaml`:
VALID_WITH_AMBIGUITIES (2 recorded ambiguities, both justified above).
