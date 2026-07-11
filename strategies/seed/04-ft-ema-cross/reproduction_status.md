# Reproduction status -- SRC-FT2 (freqtrade EMA cross)

**Status: REPRODUCED (mechanical, spot-checked).**

Scope of the claim: this reproduces the *canonical spec's own rule execution*
(source fidelity, warm-up, timing, EMA state semantics) against the project's
32-bar frozen micro fixture (`fixtures/micro/bars_long.csv`) -- it does **not**
claim to replicate any historical P&L (`profit_claims_inherited: false`).

Method: `tests/test_strategy_seed_reproduction.py::test_ft2_ema_cross_reproduction`
implements a **true recursive EMA** (talib/freqtrade convention: SMA seed of the
first `window` closes, then alpha = 2/(window+1) smoothing) in plain Python --
this closes the previously flagged "treat EMA like SMA warm-up" approximation
that caused the original deferral -- and evaluates this item's actual
`entry_long`/`exit_long` `RuleTree` objects bar-by-bar. Assertions cover all
three fixture regimes exactly: the deterministic per-bar whipsaw during the
100/101 oscillation (bars 10-20, state-based signals), sustained EXIT through
the dip (bars 21-25), and sustained ENTRY through the rally (bars 26-32),
plus the warm-up boundary at the long window.

Result: PASS (2026-07-11). Verdict from `tios.strategy.validator.validate_yaml`:
VALID_WITH_AMBIGUITIES (2 recorded ambiguities; the EMA-seeding limitation is
now addressed at spot-check level by the true recursive implementation).
The seed cycle also carries STRAT-FT2-ema-cross with a short/long window sweep
(`scripts/run_seed_research_cycle_v0.py`).
