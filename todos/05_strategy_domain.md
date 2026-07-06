# Initiative 05 — Strategy Domain (S1) — CRITICAL PATH

Requirement source: AD §J, type catalog §2, ingestion workflow spec. Skill: R7 (+R3 validator).

## T-005-01 Canonical spec schema + validator (executable)
- Purpose: machine-validated CanonicalStrategySpec. Requirement: REQ-011.
- Actions: implement schema (YAML), rule-tree model (`all:`/`any:` comparisons), spec hashing, validation per SKILL_CANONICAL_SPEC_VALIDATOR steps 1–2.
- Outputs: `strategy` module schema+validator+tests. Acceptance: property tests on rule trees; malformed fixtures rejected with precise errors. Complexity: M. Status: **DONE 2026-07-06**.

## T-005-02 StrategyVersion immutability
- Purpose: SV records with immutable snapshots. Requirement: REQ-012.
- Actions: SV creation, spec_hash binding, immutability enforcement + test (mutation attempt fails).
- Acceptance: immutability test green. Complexity: S. Dependencies: T-005-01. Status: **DONE 2026-07-06**.

## T-005-03 Four baseline specs (B1–B4)
- Purpose: engine-neutral baselines for bake-off (buy-and-hold, MA crossover, Bollinger mean-reversion, volatility breakout). Requirement: REQ-013.
- Actions: author canonical specs with explicit timing assumptions, warm-up, sizing; zero ambiguities allowed (we author them, so none may remain); golden-fixture expected signals on `fixtures/micro/` computed by hand.
- Outputs: 4 spec files + micro-fixture expected-signal goldens. Acceptance: validator VALID; hand-computed signals documented. Complexity: M. Dependencies: T-005-01. Status: **DONE 2026-07-06** (B3 bar-13 hand error caught+fixed by double-derivation).
