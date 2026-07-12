# Strategy Ingestion Seed Batch V1

Status: Approved manifest; execution assigned to coding agent.

## Purpose

Learn the real semantic and licensing variability of external strategy sources before building automation.
The source universe explicitly includes exchange-hosted bot marketplaces, copy-trading
records, online signal feeds, and third-party bot platforms as future lab inputs.
They are hypothesis/replay sources only; they do not authorize copying trades or
subscribing the OS wallet to an external signal.

## Required mix

| Slot | Source class | Selection rule |
|---|---|---|
| 1-2 | QuantConnect Strategy Library / official tutorial | Two distinct families |
| 3-4 | Freqtrade public strategy ecosystem | Two strategies with source/license metadata |
| 5-6 | Hummingbot V2 Controllers | Two distinct controller types |
| 7-8 | Open-source TradingView/Pine | Explicit open-source publication/license evidence plus captured Strategy Tester settings/results when available |
| 9-10 | Academic papers | Full method description sufficient for canonical extraction |

Future expansion slots, after the current seed batch and under the same no-execution
rules:

| Slot | Source class | Selection rule |
|---|---|---|
| 11-12 | Exchange-hosted bot marketplace entries, e.g. Binance Trading Bots | Publicly visible strategy family/parameter/performance metadata; terms reviewed |
| 13-14 | Copy-trading/copy-investing records or leaderboards | Historical actions/allocations reconstructable without account credentials |
| 15-16 | Online signal feeds or alert sources | Timestamped historical signals available for replay; no live subscription execution |
| 17-18 | Third-party bot platforms | Strategy logic/parameters or exportable historical signals available; no black-box profit import |

## Selection constraints

- Prefer diversity over claimed performance.
- At least one mean-reversion family.
- At least one momentum/trend family.
- At least one execution/market-making family if source allows.
- No item enters with inherited profitability score.
- Record exact URL, author, date, version/commit, license, and source class.
- For bot/copy/signal sources, record platform terms, signal/action timestamp semantics,
  parameter visibility, survivorship/selection bias risks, fee/slippage assumptions,
  and whether the item is a rule definition, historical signal feed, allocation record,
  or opaque performance claim.

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
