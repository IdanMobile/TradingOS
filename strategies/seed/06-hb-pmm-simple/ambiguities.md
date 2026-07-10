# Ambiguities -- SRC-HB2 (Hummingbot pmm_simple)

See canonical_strategy_spec.yaml `ambiguities:` -- the core finding is a
schema-level incompatibility: this project's `CanonicalStrategySpec` has no
native representation for continuous two-sided quoting (bid + ask around a
reference price), only single-sided entry/exit signal rules. `always_in_market: true`
plus a pseudo-indicator carrying the spread/refresh config is a workaround,
not a faithful reproduction. This is the seed batch's clearest example of an
"incompatible semantics" finding (see STRATEGY_INGESTION_REPORT.md).
