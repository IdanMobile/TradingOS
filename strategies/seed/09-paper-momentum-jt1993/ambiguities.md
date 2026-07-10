# Ambiguities -- SRC-PAPER1 (Jegadeesh & Titman 1993 momentum)

See canonical_strategy_spec.yaml `ambiguities:` for the full statement. In
short: this project's spec schema can only express a single-instrument
threshold rule, so the paper's cross-sectional decile-ranking, long-short
construction, and monthly rebalance are all collapsed into "this
instrument's own trailing 12-bar return > 0, evaluated continuously." This
is the seed batch's clearest academic-paper "incompatible semantics"
finding (see STRATEGY_INGESTION_REPORT.md).
