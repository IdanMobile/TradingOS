# Initiative 07 — Experiment Lineage Prototype (S1, WS5) — CRITICAL PATH

Requirement source: `specs/EXPERIMENT_LINEAGE_PROTOTYPE_SPEC_V1.md`. Skill: R7.

## T-007-01 MLflow local setup + Test A (deterministic strategy run)
- Purpose: run tracking against a real baseline run. Requirement: REQ-022.
- Actions: local MLflow (no paid cloud); record all Test-A fields for one B2 run on frozen dataset.
- Acceptance: Test A field checklist complete; compare-two-runs works in UI. Complexity: M. Dependencies: T-004-04, T-006-01 (any one engine runnable). Status: **DONE 2026-07-10** — two retained B2 runs logged and natively comparable; artifact restore hashes match; local UI returned HTTP 200.

## T-007-02 DVC dataset snapshot + restore
- Purpose: reproducibility layer. Requirement: REQ-023.
- Actions: DVC-track frozen dataset; fresh-checkout restore test.
- Acceptance: `Reproduce` gate (fresh checkout restores + reruns). Complexity: M. Status: **DONE 2026-07-10** — local DVC push/pull into a fresh Git clone restored the exact dataset and deterministic reproduction result.

## T-007-03 Test B (AI research run trace)
- Purpose: AI provenance through same infrastructure. Requirement: REQ-024.
- Actions: one research task with one agent config (or null-provider dry trace if no credentials — never fabricated); record model ID, prompt version, corpus hash, tokens, cost, latency.
- Acceptance: AI-trace gate; deferred-execution honesty if blocked. Credentials: optional (intake disposition). Complexity: M. Status: **DONE 2026-07-10 (MOCK-ONLY)** — exact null-provider model/prompt/corpus/config/output/evaluator trace logged; no real-model quality claim.

## T-007-04 Test C (thin Trading Evidence link)
- Purpose: domain record referencing tracker by public refs only. Requirement: REQ-025.
- Actions: implement `evidence` thin module (jsonl or SQLite table per prototype spec); link EV → run_ref/dataset_ref; replaceability check (no internal schema parsing).
- Acceptance: Domain-link + Replaceability gates. Complexity: M. Dependencies: T-007-01/02. Status: **DONE 2026-07-10** — `EV-LINEAGE-PROTOTYPE-002` links public MLflow/DVC refs; custom schema remains tool-internal-schema independent.

## T-007-05 Lineage decision report
- Purpose: exactly one verdict (MLFLOW_PLUS_DVC / MLFLOW_ONLY / DVC_ONLY / ALTERNATIVE_REQUIRED) with evidence (EG-3, RG-10).
- Outputs: `artifacts/reports/LINEAGE_PROTOTYPE_REPORT.md`. Acceptance: all 7 acceptance gates evaluated; failure conditions §spec checked. Complexity: S. Dependencies: T-007-01..04. Status: **DONE 2026-07-10** with executed `MLFLOW_PLUS_DVC_RECOMMENDED`; AI gate is explicitly mock-only.
