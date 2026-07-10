# Initiative 10 — Strategy Ingestion Seed Batch (S1, WS7)

Requirement source: `specs/STRATEGY_SEED_BATCH_V1.md` + ingestion workflow spec. Skills: R3 (SKILL_STRATEGY_SOURCE_INGESTOR) + R7. Parallelizable: Yes (per item). Mass automation forbidden (D-020).

## T-010-01 Ingestion record tooling
- Purpose: minimal `ingestion` module: source/license/ambiguity records + lifecycle states. Requirement: REQ-039.
- Acceptance: lifecycle transition guards tested; license-class gating works. Complexity: M. Dependencies: T-005-01. Status: **DONE 2026-07-07**.

## T-010-02..11 Seed items 1–10 (one task each)
- Slots per spec: 2×QuantConnect library, 2×Freqtrade repo, 2×Hummingbot V2 controllers, 2×open-source Pine, 2×academic papers. Requirement: REQ-040.
- Actions per item: SKILL_STRATEGY_SOURCE_INGESTOR full process → six per-item output files; reproduction status honestly recorded (reproduction runs only where license + effort justify within S1).
- Acceptance per item: validator verdict recorded; ambiguities non-empty or justified; license evidence linked. Failure: any profit-claim import. Complexity: M each. Status: **DONE 2026-07-07** (10/10; see `artifacts/reports/STRATEGY_INGESTION_REPORT.md`).

## T-010-12 Ingestion lessons report
- Purpose: `artifacts/reports/STRATEGY_INGESTION_REPORT.md` (EG-5): recurring schema fields, ambiguity classes, license blockers, automation opportunities/hazards. Requirement: REQ-041.
- Acceptance: report answers the five completion-report questions in the seed spec. Complexity: S. Dependencies: all items. Status: **DONE 2026-07-07**.
