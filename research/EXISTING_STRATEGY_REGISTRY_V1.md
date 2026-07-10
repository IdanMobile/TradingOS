# Existing Strategy Registry V1

Status: Seed batch complete (initiative 10 / WS7, T-010-02..11). Supersedes
the taxonomy-only `EXISTING_STRATEGY_REGISTRY_V0.md` with 10 concretely
ingested items, each carrying the six required per-item output files under
`strategies/seed/<NN-slug>/`. Entries are provenance-preserving hypothesis
inputs, not approved profitable strategies (D-011: no inherited profit
claims — every `source_record.yaml` sets `profit_claims_inherited: false`).

## Registry

| # | strategy_id | family | source class | license_class | reproduction status |
|---|---|---|---|---|---|
| 1 | STRAT-QC1-dual-ma-cross | trend_following | official_framework (QuantConnect/LEAN) | permissive (Apache-2.0) | REPRODUCED |
| 2 | STRAT-QC2-donchian-breakout | breakout | official_framework (QuantConnect/LEAN) | permissive (Apache-2.0) | REPRODUCED |
| 3 | STRAT-FT1-sample-strategy | mean_reversion | official_framework (freqtrade) | copyleft (GPL-3.0) | NOT_REPRODUCED (deferred — fixture too short for 20-bar warm-up) |
| 4 | STRAT-FT2-ema-cross | trend_following | official_framework (freqtrade docs) | copyleft (GPL-3.0) | NOT_REPRODUCED (deferred — no EMA primitive) |
| 5 | STRAT-HB1-supertrend-directional | trend_following | official_framework (Hummingbot V2) | permissive (Apache-2.0) | NOT_REPRODUCED (deferred — signal-level simplification) |
| 6 | STRAT-HB2-pmm-simple | market_making | official_framework (Hummingbot V2) | permissive (Apache-2.0) | NOT_REPRODUCED (not applicable — schema cannot express two-sided quoting) |
| 7 | STRAT-PINE1-bb-strategy | mean_reversion | maintained_open_source (Pine/TradingView) | copyleft (MPL-2.0) | NOT_REPRODUCED (deferred — fixture too short for 20-bar warm-up) |
| 8 | STRAT-PINE2-supertrend-strategy | trend_following | maintained_open_source (Pine/TradingView) | copyleft (MPL-2.0) | NOT_REPRODUCED (deferred — mechanically identical to item 5) |
| 9 | STRAT-PAPER1-momentum-jt1993 | trend_following | primary_academic_paper (Jegadeesh & Titman 1993) | unclear | NOT_REPRODUCED (not applicable — no per-bar result to reproduce) |
| 10 | STRAT-PAPER2-reversal-jegadeesh1990 | mean_reversion | primary_academic_paper (Jegadeesh 1990) | unclear | NOT_REPRODUCED (not applicable — no per-bar result to reproduce) |

Required slot mix (per `specs/STRATEGY_SEED_BATCH_V1.md`): 2 QuantConnect,
2 Freqtrade, 2 Hummingbot V2 controllers, 2 open-source Pine, 2 academic
papers — all filled. Selection constraints satisfied: mean-reversion present
(3, 7, 10), momentum/trend present (1, 4, 5, 8, 9), execution/market-making
present (6), no inherited profitability score on any item.

## Per-item file locations

Each row's six files live at `strategies/seed/<NN-slug>/`:
`source_record.yaml`, `license_record.yaml`, `canonical_strategy_spec.yaml`,
`ambiguities.md`, `framework_assumptions.md`, `reproduction_status.md`.

| # | Directory |
|---|---|
| 1 | `strategies/seed/01-qc-dual-ma-cross/` |
| 2 | `strategies/seed/02-qc-donchian-breakout/` |
| 3 | `strategies/seed/03-ft-sample-strategy/` |
| 4 | `strategies/seed/04-ft-ema-cross/` |
| 5 | `strategies/seed/05-hb-supertrend-directional/` |
| 6 | `strategies/seed/06-hb-pmm-simple/` |
| 7 | `strategies/seed/07-pine-bb-strategy/` |
| 8 | `strategies/seed/08-pine-supertrend-strategy/` |
| 9 | `strategies/seed/09-paper-momentum-jt1993/` |
| 10 | `strategies/seed/10-paper-reversal-jegadeesh1990/` |

## Validator verdicts

All 10 `canonical_strategy_spec.yaml` files parse and validate as
`VALID_WITH_AMBIGUITIES` under `tios.strategy.validator.validate()` — zero
`INVALID` verdicts, and no item's ambiguities list is empty (every item
records genuine, justified ambiguities per the seed spec's acceptance
criterion).

## Reproduction spot-check (task verification gate)

`tests/test_strategy_seed_reproduction.py` independently recomputes items 1
and 2 (`test_qc1_dual_ma_cross_reproduction`, `test_qc2_donchian_breakout_reproduction`)
against `fixtures/micro/bars.csv` and asserts they agree with each item's own
`RuleTree` evaluation bar-by-bar — satisfying "spot-check 2 of the 10 seed
items reproduce their stated original result within documented tolerance."
Items 3-10 are honestly recorded as `NOT_REPRODUCED` (deferred or not
applicable, with justification per item) rather than a padded reproduction
count — see each item's `reproduction_status.md` and
`artifacts/reports/STRATEGY_INGESTION_REPORT.md` for why.

## Relationship to V0

`EXISTING_STRATEGY_REGISTRY_V0.md` remains as the broader source-class
taxonomy and discovery survey; this V1 registry is the concrete seed-batch
outcome the taxonomy pointed toward. Future ingestion passes should append
rows here rather than re-deriving the taxonomy.
