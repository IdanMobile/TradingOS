# Reproduction status -- SRC-PINE1 (Pine Bollinger Bands strategy)

**Status: REPRODUCED (mechanical, spot-checked).**

Scope of the claim: this reproduces the *canonical spec's own rule execution*
(source fidelity, warm-up, timing) against the project's 32-bar frozen micro
fixture (`fixtures/micro/bars_long.csv`, created 2026-07-11 for 20-bar-warm-up
seeds) -- it does **not** claim to replicate any historical P&L from the source
(`profit_claims_inherited: false`; the fixture is not the source's dataset).

Method: `tests/test_strategy_seed_reproduction.py::test_pine1_bb_strategy_reproduction`
independently recomputes Bollinger Bands (20, 2, population standard deviation
-- the Pine/talib default) in plain Python and evaluates this item's actual
`entry_long`/`exit_long` `RuleTree` objects (parsed from
`canonical_strategy_spec.yaml` via `tios.strategy.spec`) bar-by-bar, asserting:
warm-up silence through bar 19; lower-band entries exactly at the designed dip
(bars 21-23); upper-band exits exactly at the designed rally (bars 27-29); and
no signal on every other bar. Entry/exit bars were double-derived (designed
analytically, recomputed independently).

Result: PASS (2026-07-11). Verdict from `tios.strategy.validator.validate_yaml`:
VALID_WITH_AMBIGUITIES (2 recorded ambiguities, both justified above). The
previous deferral (16-bar fixture shorter than the 20-bar warm-up) is closed by
the longer fixture.
