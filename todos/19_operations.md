# Initiative 19 — Operations (S1 minimal / S2 fuller)

Requirement source: AD §S, type catalog §5. Skill: R7.

## T-019-01 Jobs module (DB-table queue + APScheduler)
- Purpose: job model, retries, timeouts, cancellation, artifact registration (AD-10). Requirement: REQ-056.
- Acceptance: idempotency + failure-preservation tests; queue view queryable. Complexity: M. Dependencies: T-003-02. Status: TODO.

## T-019-02 Report builders
- Purpose: mandated `artifacts/reports/*.md` generated from machine-readable inputs (reports are projections). Requirement: REQ-057.
- Acceptance: report regeneration is deterministic; every report links machine-readable siblings. Complexity: M. Status: TODO.

## T-019-03 Prototype readiness report assembly
- Purpose: `artifacts/reports/PROTOTYPE_READINESS_REPORT.md` + `decisions/PROTOTYPE_EVIDENCE_DECISION.md` inputs (EG-7). Requirement: REQ-058.
- Acceptance: every vertical-slice exit criterion mapped to evidence; every capability gets exactly one decision state (SSOT §7 list). Human approval: **HG-2 follows**. Complexity: M. Dependencies: all S1 EGs. Status: TODO.

## S2 backlog: scheduled freshness sweeps (registry expiry), ops dashboard view, failure analytics. DEFERRED-S2.
