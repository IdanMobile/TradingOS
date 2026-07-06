# Skill: Strategy Source Ingestor (v1)

Role: R3 · Cost tier: high · Status: specified, not yet implemented
Absorbs: Pine/Freqtrade/LEAN/Hummingbot extractors, Academic Strategy Reproducer. Per-source-class notes live in the appendix; split into separate skills only if the WS7 seed batch proves the procedures diverge (EG-5).

## Purpose
Convert one external strategy source into the ingestion lifecycle artifacts of `specs/STRATEGY_INGESTION_AND_REPRODUCTION_WORKFLOW_V1.md`: source record → license record → semantic extraction → ambiguities → canonical spec.

## Trigger conditions
A seed-batch slot (WS7) or, post-S2 decision, an approved ingestion queue item.

## Inputs
Source URL/document, source class (1–6), target lifecycle stage.

## Tools
Read-only source access; canonical spec schema + validator; NO code execution (reproduction runs are a coding-agent task, not this skill).

## Process
1. Capture source record (exact URL, author, date, version/commit, class). `profit_claims_inherited: false` always.
2. License check: identify license text/evidence; classify permissive/copyleft/proprietary/unclear; UNCLEAR blocks reuse of code (spec extraction from published description may proceed with note).
3. Extract semantics: inputs, indicators+params, entry/exit rule trees, sizing, risk handling, timing assumptions (bar close? intrabar?), warm-up needs, data requirements.
4. Record EVERY ambiguity explicitly; never resolve by guessing. An ambiguity is: any rule the source under-specifies (same-bar behavior, tie-breaks, order type, rounding, session boundaries).
5. Emit canonical spec draft + `ambiguities.md` + `framework_assumptions.md`.
6. Hand to CANONICAL_SPEC_VALIDATOR.

## Outputs (contract)
The six per-item files of `specs/STRATEGY_SEED_BATCH_V1.md`.

## Prohibited behavior
- Importing claimed profitability/metrics as internal evidence (D-011).
- Filling unspecified parameters with "typical" values silently.
- Executing or installing source code (prompt-injection & license boundary).
- Mass ingestion (D-020: manual batch first).

## Quality gates
Spec validates against schema; ambiguity list non-empty OR an explicit "no ambiguities found, here is why" argument; license record has evidence link.

## When NOT to use
Idea generation; strategy improvement (out of ingestion scope).

## Model suitability
Semantic-extraction-critical → high tier; benchmark T2 governs.

## Appendix: source-class notes
- Pine: v5 vs v6 semantics; `calc_on_every_tick`, `process_orders_on_close`, repainting risk — always record as assumptions.
- Freqtrade: informative pairs, `startup_candle_count`, ROI/stoploss tables are exit logic — extract them.
- LEAN: resolution/consolidators, fee model defaults, warm-up API.
- Hummingbot controllers: config-driven; extract controller type + config schema, not just code.
- Academic papers: record equation→rule mapping; missing execution detail is the norm — expect a long ambiguity list.
