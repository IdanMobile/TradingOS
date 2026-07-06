# Skill: Canonical Spec Validator (v1)

Role: R3/R9 · Cost tier: mid · Status: specified, not yet implemented

## Purpose
Validate a CanonicalStrategySpec for schema correctness, semantic completeness, and ambiguity honesty before it can become a StrategyVersion.

## Trigger conditions
Any new/edited canonical spec (ingestion output, human-authored baseline, converter output).

## Inputs
Spec YAML, source record + ambiguities file, spec schema (TYPE_AND_CONTRACT_CATALOG §2).

## Process
1. Schema validation (mechanical).
2. Completeness: every indicator has parameters; every entry has an exit path; sizing defined; timing assumption stated; warm-up stated; data requirements resolvable against a dataset schema.
3. Ambiguity honesty: cross-check spec against source — every under-specified point in the source must appear in `ambiguities`, not be silently resolved in the spec.
4. Executability preview: could a deterministic engine adapter implement this without asking questions? List every question it would have to ask.
5. Verdict: VALID / VALID_WITH_AMBIGUITIES (listed) / INVALID (reasons).

## Outputs (contract)
Validation report appended to the spec's reproduction_status file; verdict gates the lifecycle transition `SEMANTIC_EXTRACTED → CANONICAL_SPEC_CREATED`.

## Prohibited behavior
Fixing the spec itself (validator ≠ author); approving specs with silently-resolved ambiguities.

## Quality gates
Question list from step 4 is empty or fully mirrored in `ambiguities`.

## When NOT to use
Engine-specific implementation review (that is T3 / parity work).

## Model suitability
Mid tier; escalate for academic-paper-derived specs.
