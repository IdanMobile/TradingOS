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

## v8.2 — 2026-07-06 — S1 execution: initiatives 04, 05 complete; 06 started; 18 partial

- Initiative 04 DONE (EG-1): DS-CRYPTO-SPOT-BAKEOFF-V1 frozen — 396 raw files checksum-verified, 1.64M normalized rows, Amendment A1 boundary goldens, quality PASS (all checks proven failable), double-regeneration identical hashes, independent audit PASS_WITH_NOTES (zero discrepancies).
- Initiative 05 DONE: canonical spec model/validator (property-tested), immutable SV, baselines B1–B4 + double-derived micro goldens.
- Initiative 06: T-006-01 DONE (EngineAdapter port, NormalizedResult, capability gaps, mandatory fee/slippage grid, fee audit utility).
- Initiative 18: T-018-01/03 DONE (secret hygiene, license audit w/ planted-AGPL proof).
- Controlled edits: PROJECT_STATE, todos/04/05/06/18 — manifest regenerated.

## v8.3 — 2026-07-06 — S1: Freqtrade matrix + vectorbt probe evidence

- Freqtrade lane: B1–B4 × {F0/S0, F1/S1} all OK on frozen dataset; normalization to canonical decimal parquet; fee/PnL audit PASS everywhere; determinism byte-identical; lookahead flag root-caused (execution-state artifact, numeric proof); slippage CapabilityGap recorded; stake-model semantic note for parity.
- vectorbt probe: 1.31M bar-combos/s, all trials retained.
- Controlled edits: PROJECT_STATE, todos/06 — manifest regenerated.

## v8.4 — 2026-07-07 — Governance re-check (gov-02): decision-ID gate coverage fix

- `make check` re-verified green (63 tests, ruff, mypy-strict).
- Found and fixed a real gap: D-027/D-028 used `##` headings, so `tests/test_decision_ids.py`'s uniqueness regex (`### D-NNN`) silently skipped them. Normalized both to `###` (D-033); all 32 decision IDs now covered.
- Confirmed no invented decision-category labels in `DECISION_LOG.md`; confirmed PROJECT_STATE.md matches latest closed work; confirmed no stop-condition triggers worked around.
- Controlled edits: DECISION_LOG.md (D-033 + heading fix), PROJECT_STATE.md.
## v8.5 — 2026-07-10 — S1 executable evidence and HG-2 review packet

- Executed and selected the local MLflow+DVC lineage composition; retained restore,
  compare, strategy trace, mock-only AI trace, and thin domain-link evidence.
- Closed available engine parity with explained B1/B2 divergences; closed the
  Freqtrade lane with constraints and vectorbt with 66/66 retained ledgered trials.
- Kept the real Trading OS dashboard live and added explicit HG-2 readiness while
  preserving `INCOMPLETE_NOT_APPROVABLE` strategy validation and no-order boundaries.
- Added the S1 stage-exit review, D-035, and regenerated all changed controlled-input
  SHA-256 entries in `PACKAGE_INTEGRITY_MANIFEST.md`.
- Closed the S1 contextual approval, independent risk-precondition, and ingested-code
  containment tasks; Security Review #2 passes and the local gate now has 123 tests.

## v8.6 — 2026-07-10 — S2-0 governance reconciliation

- Recorded the operator's explicit HG-2 approval as D-036 and opened constrained S2
  architecture, autonomous research/test-lab, sourced-research, offline backtesting,
  retained-trial scoring, validation, and research-console work.
- Made `docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md` the active S2 execution plan
  under the existing SSOT hierarchy.
- Preserved B2 as `INCOMPLETE_NOT_APPROVABLE` and rejected for paper; no strategy,
  synthetic wallet, paper/demo/testnet venue connection, credentials, order routing,
  live trading, real money, or AI approval/trading authority was granted.
- Reconciled the prototype decision, S1 stage exit/readiness reports, project state,
  operational handoff, program/architecture task states, and execution plan. The
  integrity manifest was intentionally not edited in this reconciliation.

## v8.7 — 2026-07-10 — S2 architecture-lock governance reconciliation

- Added unique D-037 for the evidence-backed S2 architecture lock: modular monolith;
  SQLite operational state with measured PostgreSQL triggers; Parquet/DuckDB analytics;
  MLflow+DVC behind ports; and bounded scheduling only after real idempotent reuse.
- Closed T-002-01..04 against their revised, evidence-backed acceptance criteria and
  recorded engine roles. Hummingbot/LEAN deferred adapters and normalized artifacts are
  retained as evidence-only/deferred assets rather than deleting historical evidence.
- Activated only bounded S2 initiatives 13, 14, 17, and 19; full ontology initiative 12
  remains deferred. Folded former product wave 7 into the S2 console/product slice.
- Removed stale HG-2/S1-current and resolved-open-item wording while preserving B2/G4/G10
  strategy-validation gaps, engine gaps, and all paper/demo/live human gates.
- Kept the execution boundary read-only and inert. No real `LAB-*` batch, enabled
  scheduler, S2 completion, strategy approval, paper/demo connection, or live capability
  is claimed. The integrity manifest and all source/test files were intentionally left
  untouched by this reconciliation.

## v8.8 — 2026-07-10 — S2 Research Lab automation dashboard

- Finished the paused jobs/dashboard integration: read-only `build_jobs_projection(root)`,
  dashboard Automation view, and focused jobs/dashboard tests.
- Verified the real retained LAB-702 batch and persisted queue state: 2 succeeded
  `RESEARCH_LAB_V0` jobs, latest reused unchanged artifacts, recurring six-hour schedule
  next due `2026-07-11T00:00:00+00:00`, no failed/cancelled jobs.
- Ran full quality gates: Ruff, format check, strict mypy, 282 tests, and
  `make required` including `pip-audit` with no known vulnerabilities.
- Browser-tested the live dashboard at 375/768/1024/1440 px across Overview, Research
  Lab, Automation, and Market Monitor; market evidence loaded from frozen candles plus
  retained backtest fills. The page remains read-only with no POST, credential, venue,
  order, paper/demo/live, or real-money control.
- Tightened the Automation projection after independent review: retained job errors are
  redacted by default, including unlabeled secret-looking failure text.
- Refreshed the Research Lab score assessment from retained validation evidence,
  producing `LAB-799f7d81843d15aaf3b161036a4cd543ac37a709cb1e2ecc72a161f7348488fa`.
  The new batch remains `UNVALIDATED` / `NOT_ELIGIBLE`, but distinguishes negative
  completed evidence (economic, drawdown, walk-forward, robustness, baseline
  superiority) from still-blocked multiple-testing and cross-engine reproduction.
- Enqueued and executed `s2-production-offline-research-lab-v0-cycle-003`; the local
  worker reused LAB-799 and retained a third succeeded `RESEARCH_LAB_V0` job without
  enabling any paper/demo/live or order capability.

## v8.9 — 2026-07-11 — S2 decision follow-through and dashboard governance

- Added Workspace human-decision recording for gated/recurring tasks:
  `artifacts/human_decisions/workspace_decisions.jsonl` records operator choices for
  future coding agents, while all trading/job/order controls remain absent.
- Completed the authorized official-source venue recheck and S3 design-only expansion
  slices: `VENUE_ISRAEL_SOURCE_RECHECK_2026_07_11.md` and
  `FUTURE_MARKET_EXPANSION_DESIGN_REVIEW_2026_07_11.md`.
- Rechecked AI cost telemetry credentials after the operator decision; no provider
  keys are visible, so `T-017-05` remains credential-blocked with evidence in
  `AI_COST_TELEMETRY_CREDENTIAL_RECHECK_2026_07_11.md`.
- Tightened dashboard freshness and API boundaries: core data auto-refreshes,
  Market Monitor refreshes while visible, `/api/v1/*` is the only active API, and
  legacy `/api/*` paths return `410`.
- Regenerated all changed controlled-input SHA-256 entries in
  `PACKAGE_INTEGRITY_MANIFEST.md`; manifest verification passes.
