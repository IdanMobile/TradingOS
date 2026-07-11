# Reproduction status -- SRC-FT1 (freqtrade SampleStrategy)

**Status: REPRODUCED (mechanical, spot-checked).**

Scope of the claim: this reproduces the *canonical spec's own rule execution*
(source fidelity, warm-up, timing, RSI guard, mid-band exit convention) against
the project's 32-bar frozen micro fixture (`fixtures/micro/bars_long.csv`,
created 2026-07-11) -- it does **not** claim to replicate any historical P&L
(`profit_claims_inherited: false`).

Method: `tests/test_strategy_seed_reproduction.py::test_ft1_sample_strategy_reproduction`
independently recomputes Bollinger Bands (20, 2, population standard deviation)
and Wilder-smoothed RSI(14) (the talib/freqtrade convention; the spec's `rsi`
indicator does not pin a smoothing convention -- Wilder is used as the source
framework's actual behavior) in plain Python and evaluates this item's actual
`entry_long`/`exit_long` `RuleTree` objects bar-by-bar, asserting: the RSI<30
guard admits only the deepest dip bar (23) while the band-only PINE1 variant
enters on all three dip bars; the mid-band exit fires from bar 25 onward
(earlier than PINE1's upper-band exit at 27-29); and no signal fires anywhere
else. Entry/exit bars were double-derived.

Result: PASS (2026-07-11). Verdict from `tios.strategy.validator.validate_yaml`:
VALID_WITH_AMBIGUITIES (2 recorded ambiguities, both justified above). The
previous deferral (16-bar fixture shorter than the 20-bar warm-up) is closed by
the longer fixture.
