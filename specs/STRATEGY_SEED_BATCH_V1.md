# Strategy Ingestion Seed Batch V1

Status: Approved manifest; execution assigned to coding agent.

## Purpose

Learn the real semantic and licensing variability of external strategy sources before building automation.

## Required mix

| Slot | Source class | Selection rule |
|---|---|---|
| 1-2 | QuantConnect Strategy Library / official tutorial | Two distinct families |
| 3-4 | Freqtrade public strategy ecosystem | Two strategies with source/license metadata |
| 5-6 | Hummingbot V2 Controllers | Two distinct controller types |
| 7-8 | Open-source TradingView/Pine | Explicit open-source publication/license evidence |
| 9-10 | Academic papers | Full method description sufficient for canonical extraction |

## Selection constraints

- Prefer diversity over claimed performance.
- At least one mean-reversion family.
- At least one momentum/trend family.
- At least one execution/market-making family if source allows.
- No item enters with inherited profitability score.
- Record exact URL, author, date, version/commit, license, and source class.

## Per-item outputs

- `source_record.yaml`
- `license_record.yaml`
- `canonical_strategy_spec.yaml`
- `ambiguities.md`
- `framework_assumptions.md`
- `reproduction_status.md`

## Completion report

Summarize:
- recurring schema fields;
- ambiguous concepts;
- incompatible semantics;
- license blockers;
- automation opportunities;
- automation hazards.
