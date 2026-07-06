# Initiative 11 — AI/Agent Benchmark Seed (S1, WS8)

Requirement source: `benchmarks/ai_agent/FROZEN_BENCHMARK_SUITE_V1.md` + `specs/AI_AGENT_EVALUATION_BLUEPRINT_V1.md`. Skills: R7 + SKILL_BENCHMARK_RUNNER. Design constraint (AD-11): multi-sample scoring, no determinism assumption.

## T-011-01 Registries (MDL/AGT/PRM)
- Purpose: model/agent/prompt records with snapshot pinning + per-provider deprecation watch fields. Requirement: REQ-042.
- Acceptance: registry round-trip tests; provider policy fields populated from REG §7. Complexity: M. Status: TODO.

## T-011-02 Frozen fixture corpus construction
- Purpose: materialize T1–T8 fixtures (12 claims, 5 strategy descriptions, etc. per suite spec) with hash manifest, publication-date records, masking where required. Requirement: REQ-043.
- Acceptance: corpus hash manifest; leakage-control checklist per suite spec satisfied. Complexity: L. Status: TODO.

## T-011-03 Harness (null-provider end-to-end)
- Purpose: run pipeline with a null provider — fixtures→prompt assembly→schema validation→scoring plumbing — zero fabricated outputs. Requirement: REQ-044.
- Acceptance: end-to-end null run green; no-network controlled-mode enforcement test. Complexity: L. Dependencies: T-011-01/02. Status: TODO.

## T-011-04 Judge calibration set
- Purpose: human-reviewed scoring samples for judge calibration (blueprint safeguard). Requirement: REQ-045.
- Human approval: **Yes (operator reviews samples)**. Acceptance: calibration set frozen + hashed. Complexity: M. Status: TODO.

## T-011-05 First real runs (≥2 configurations) — credential-gated
- Purpose: controlled-mode runs on a small subset with repeated trials. Requirement: REQ-046 (EG-6). Precondition: intake-gate credential disposition = configured; T-001-04 pricing verification.
- Acceptance: BMK records with full provenance + variance estimates; or honest BLOCKED status. Credentials: provider API keys (optional). Complexity: M. Status: TODO (conditional).

## T-011-06 Seed report
- Outputs: `artifacts/reports/AI_BENCHMARK_SEED_REPORT.md`. Requirement: REQ-047. Acceptance: scoring views emitted (never a single global score). Complexity: S. Status: TODO.
