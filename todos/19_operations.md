# Initiative 19 — Operations (S1 baseline done / bounded S2 active)

Requirement source: AD §S, type catalog §5. Skill: R7.

## T-019-01 Jobs module (DB-table queue + APScheduler)
- Purpose: job model, retries, timeouts, cancellation, artifact registration (AD-10). Requirement: REQ-056.
- Acceptance: the underlying allowlisted command first proves identical-input reuse without recomputation plus failure preservation; only then may a bounded SQLite queue/local scheduler be enabled and made queryable. Complexity: M. Dependencies: Research Lab command idempotency evidence. Status: **DONE FOR BOUNDED S2 SLICE 2026-07-10** — LAB-702 completed, LAB-799 refreshed score dimensions from retained validation evidence, and both were reused by the persisted job runner; `artifacts/jobs/jobs.sqlite3` is schema v2 and mode 0600 with three succeeded `RESEARCH_LAB_V0` jobs plus a six-hour schedule. The dashboard projection is read-only and does not materialize due schedules. A continuous local worker may run only the allowlisted offline commands; no broker, venue command, paper/demo/live command, credential access, HTTP job control, or distributed orchestration is authorized.

## T-019-02 Report builders
- Purpose: mandated `artifacts/reports/*.md` generated from machine-readable inputs (reports are projections). Requirement: REQ-057.
- Acceptance: report regeneration is deterministic; every report links machine-readable siblings. Complexity: M. Status: **DONE FOR S1 2026-07-10** — bake-off, parity, validation, lineage, regime, benchmark, cost, and readiness projections are generated from retained inputs.

## T-019-03 Prototype readiness report assembly
- Purpose: `artifacts/reports/PROTOTYPE_READINESS_REPORT.md` + `decisions/PROTOTYPE_EVIDENCE_DECISION.md` inputs (EG-7). Requirement: REQ-058.
- Acceptance: every vertical-slice exit criterion mapped to evidence; every capability gets exactly one decision state (SSOT §7 list). Human approval: HG-2. Complexity: M. Dependencies: all S1 EGs. Status: **DONE 2026-07-10 — HG-2 APPROVED (D-036)**.

## Active bounded S2 slice

Allowlisted research, freshness, validation, and report jobs; read-only queue/failure
views; and failure analytics. Scheduling is bounded to the local SQLite job runner and
the recorded offline six-hour cadence. No broker, venue command, paper/demo/live
command, credential access, HTTP job control, or distributed orchestration is
authorized.
