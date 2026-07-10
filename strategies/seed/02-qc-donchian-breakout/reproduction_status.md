# Reproduction status — SRC-QC2 (Donchian breakout)

**Status: REPRODUCED (mechanical, spot-checked).**

Scope of the claim: this reproduces the *canonical spec's own rule
execution* (source fidelity, warm-up, timing) against the project's frozen
micro fixture (`fixtures/micro/bars.csv`, 16 bars) — it does **not** claim to
replicate any historical P&L from the source, since LEAN's example carries
no profitability claim to reproduce (`profit_claims_inherited: false`) and
the 16-bar fixture is not the source's own dataset.

Method: `tests/test_strategy_seed_reproduction.py::test_qc2_donchian_breakout_reproduction`
independently recomputes the prior-4-bar Donchian channel (excluding the
current bar) in plain Python and evaluates this item's actual
`entry_long`/`exit_long` `RuleTree` objects (parsed from
`canonical_strategy_spec.yaml` via `tios.strategy.spec`) bar-by-bar, then
asserts the two derivations agree: warm-up (bars 1-4, no signal), breakout
entries (bars 6-10), an inside-channel flat zone (bars 11-12, 15-16), and a
breakdown exit (bars 13-14) as the fixture's price path rises then reverses.

Result: PASS — see test output. Verdict from `tios.strategy.validator.validate_yaml`:
VALID_WITH_AMBIGUITIES (2 recorded ambiguities, both justified above).

This item was originally deferred (single-instrument rule mechanically
similar to QC1) but is now upgraded to REPRODUCED once the QC1 spot-check's
test harness was generalized to a second item, satisfying this seed batch's
"spot-check 2 of the 10" verification gate via QC1 + QC2 together.
