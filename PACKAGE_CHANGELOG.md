# Package Changelog

## v4 — 2026-07-05
- Added Phase 3 Execution Readiness Report.
- Added Crypto Spot Venue & Data Matrix V1.
- Added Experiment Lineage Executable Prototype Spec V1.
- Added Strategy Ingestion & Reproduction Workflow V1.
- Added Frozen AI & Agent Benchmark Suite V1.
- Added venue technical-shortlist vs operator-eligibility hard gate.
- Added tiered market-data acquisition policy.
- Added MLflow + DVC prototype hypothesis and acceptance gates.
- Added manual strategy-ingestion seed-batch rule.
- Updated project state, decision log, research backlog, missing items, and source registry.

## v3 — 2026-07-05
- Replaced Cursor-specific terminology with generic `coding agent` terminology.
- Added Engine Bake-Off Blueprint V1.
- Added Phase 2 Targeted Discovery Report.
- Added Existing Strategy Registry V0.
- Added AI & Agent Evaluation Blueprint V1.
- Added Experiment Lineage Blueprint V1.
- Updated project state, decision log, research backlog, missing items, source registry.
- Explicitly kept live exchange unresolved pending Israel/operator-fit verification.

## v2
- Added Phase 1 ecosystem discovery, initial reuse matrix, source registry.

## v1
- Established North Star and continuity package.

## v5 — 2026-07-05

Transitioned package from preparation to constrained coding-agent readiness.

Added:
- `research/ecosystem_discovery/PHASE_4_HANDOFF_READINESS_REPORT.md`
- `specs/CANONICAL_BAKEOFF_DATASET_V1.md`
- `specs/FEE_AND_SLIPPAGE_ASSUMPTION_PACKAGE_V1.md`
- `specs/BACKTESTING_VALIDATION_BLUEPRINT_V1.md`
- `specs/CRYPTO_SPOT_MVP_VERTICAL_SLICE_V1.md`
- `specs/STRATEGY_SEED_BATCH_V1.md`
- `decisions/CODING_AGENT_READINESS_GATE_V1.md`
- `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md`

Updated:
- `PROJECT_STATE.md`
- `DECISION_LOG.md`
- `RESEARCH_BACKLOG.md`
- `MISSING_AND_OPEN_ITEMS.md`

Key outcome:
- PASS for constrained coding-agent prototype execution.
- Still no approval for full product build, final production architecture, or real-money trading.

## v6 — SSOT + Pre-Code Environment Intake

- Promoted `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md` to explicit single operational SSOT.
- Added strict precedence/conflict-resolution hierarchy.
- Added `specs/ENVIRONMENT_AND_CREDENTIALS_INTAKE_GATE_V1.md`.
- Added hard no-code-before-intake gate.
- Added per-item `Configure now / Add later / Do not use / Not sure` choices.
- Added secret-handling rules and `.env.example` workflow.
- Updated project state, readiness gate, and decision log.


## v7 — Handoff simulation hardening

- Simulated a fresh coding agent starting with zero conversation context.
- Added explicit package integrity and input/output contract to the SSOT.
- Added `PACKAGE_INTEGRITY_MANIFEST.md`.
- Added `handoffs/HANDOFF_SIMULATION_AUDIT_V1.md`.
- Corrected ambiguous fee/slippage spec path in `DECISION_LOG.md`.
- Added explicit pre-code mutation boundary.
- Clarified that missing future reports/decision outputs are expected generated artifacts, not broken package inputs.

## v8 — 2026-07-06 — Planning system (principal-architecture mandate)

Added (planning/architecture/task/audit layer; no product code):
- `docs/architecture/AD.md`, `docs/architecture/MODULE_CATALOG.md`, `docs/architecture/TYPE_AND_CONTRACT_CATALOG.md`
- `docs/program/PROGRAM_PLAN.md`, `docs/product/MVP_SCOPE.md`, `docs/testing/TEST_MASTER_PLAN.md`
- `docs/traceability/TRACEABILITY_MATRIX.md`, `docs/ai/AGENT_ROLES.md`
- `skills/README.md` + 13 skill specifications
- `TODO.md` + `todos/00…20` (21 initiative files, REQ-traced)
- `research/EXISTING_CAPABILITY_REGISTRY.md` (full freshness re-verification dated 2026-07-06)
- `research/RESEARCH_GAP_MATRIX.md` (9 gaps closed, 16 open with owners/triggers)
- `audits/ARCHITECTURE_COMPLETENESS_AUDIT.md`, `audits/TODO_COMPLETENESS_AUDIT.md`, `audits/RED_TEAM_PLAN_REVIEW.md`, `audits/PLANNING_HANDOFF_SIMULATION.md`

Updated:
- `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md` — precedence slots for planning authorities + TODO layer; extended mandatory read order; stage/first-initiative pointer (T-003-01). Still the single controller.
- `DECISION_LOG.md` — duplicate IDs renumbered (D-027/D-028); new D-029…D-032.
- `specs/CANONICAL_BAKEOFF_DATASET_V1.md` — Amendment A1 (Binance µs timestamps from 2025-01-01 files).
- `PROJECT_STATE.md`, `MISSING_AND_OPEN_ITEMS.md`, `RESEARCH_BACKLOG.md`, `PACKAGE_README.md`.
- `PACKAGE_INTEGRITY_MANIFEST.md` — hashes regenerated; planning artifacts added as required inputs.

Key outcomes:
- Planning phase complete; S1 prototype execution remains the authorized next phase; first task T-003-01 (intake gate).
- Evidence-refresh corrections: vectorbt OSS active again; Backtrader/backtesting.py rejected; Databento reclassified; OKX↑/Coinbase↓ in connectivity ranking (live gates unchanged); MLflow/DVC hypothesis strengthened (DVC now under lakeFS stewardship); AI benchmarking must multi-sample (no provider determinism).
- Still NO approval for full product build, final architecture lock (PROVISIONAL items enumerated), or real-money trading.

## v8.1 — 2026-07-06 — S1 execution: initiative 03 complete

- HG-1 intake gate PASSED (interactive; AI provider keys deferred; MLflow/DVC fully local; zero secrets anywhere). Report: `artifacts/reports/PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md`.
- Initiative 03 DONE (T-003-01..05): git repo initialized; AD §F tree + module skeletons; idempotent bootstrap; one-command local gate (`make check`) with architecture dependency-law test, decision-ID uniqueness, secret scan — proven failable; per-engine isolated envs built and smoke-tested (freqtrade 2026.6, nautilus_trader 1.230.0, vectorbt 1.1.0, lean CLI 1.0.227, hummingbot 2.15.0 by digest); security review #1 PASS with all 6 findings fixed.
- T-001-01/RG-03 closed: vectorbt 1.1.0 license = Apache 2.0 + Commons Clause (verified from dist-info; `engines/vectorbt/LICENSE_CAPTURED.txt`). RG-04 closed via per-engine isolation. Gap matrix rows CG-10/CG-11.
- Controlled edits (manifest regenerated, 5 hashes): PROJECT_STATE.md, registry, gap matrix, todos/01, todos/03.
