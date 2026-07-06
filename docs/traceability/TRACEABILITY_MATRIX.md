# Traceability Matrix — Trading Intelligence OS

Status: v1, 2026-07-06. Chain per row: Requirement → North Star (NS) anchor → Decision → Architecture component → TODO task(s) → Test (TEST_MASTER_PLAN layer) → Acceptance gate → Evidence artifact.
Orphan rule: no requirement without a task; no task without a requirement; no architecture component without a requirement; no test without a requirement. Verified in `audits/TODO_COMPLETENESS_AUDIT.md`.

Abbreviations: NS=TRADING_OS_NORTH_STAR.md section; VS=specs/CRYPTO_SPOT_MVP_VERTICAL_SLICE_V1.md; TMP=TEST_MASTER_PLAN layer; EG/HG=PROGRAM_PLAN gates.

| REQ | Requirement (short) | NS | Decision | Architecture | TODO | Test (TMP) | Gate | Evidence artifact |
|---|---|---|---|---|---|---|---|---|
| 001 | pre-code env/credentials intake | §4.1/§17 | D-028 | SSOT §2, intake spec | T-003-01 | security | HG-1 | PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md |
| 002 | workspace + evidence tree bootstrap | §9.11 | SSOT WS1 | AD §F | T-003-02 | architecture | — | repo tree + manifests |
| 003 | per-engine isolated envs | §4.1 | AD-02 | AD §F/§K | T-003-03 | adapter integration | — | env manifests |
| 004 | one-command local gate | §26(mandate) | AD §AH | TMP §5 | T-003-04 | all-fast | — | gate config + run log |
| 005 | security baseline at bootstrap | §18 | AD §AB | security_ops | T-003-05 | security | — | security review #1 |
| 006 | reproducible raw snapshot | §9.8-22 | D-022 | dataset module | T-004-01 | dataset integrity | — | raw manifest |
| 007 | canonical normalization (µs boundary) | §9.8-22 | D-029 | converter C5 | T-004-02 | golden | — | normalized hashes |
| 008 | executable quality gates | §9.8-22 | dataset spec | dataset module | T-004-03 | dataset integrity | — | quality report |
| 009 | frozen dataset identity + double regen | §4.2 | D-022 | AD §Q | T-004-04 | golden | EG-1 | dataset manifest + regen proof |
| 010 | independent data audit | §4.4 | skill spec | SKILL_DATA_QUALITY_AUDITOR | T-004-05 | dataset integrity | EG-1 | audit report |
| 011 | canonical strategy spec schema | §15/§16 | D-014 | AD §J, strategy module | T-005-01 | unit/property | — | schema + validator tests |
| 012 | strategy version immutability | §4.4 | type catalog | SV entity | T-005-02 | unit | — | immutability test |
| 013 | four engine-neutral baselines | VS | VS spec | AD §J | T-005-03 | golden (micro) | — | baseline specs + goldens |
| 014 | engine adapter port + normalization | §13 | D-012 | AD §K, converter C3 | T-006-01 | contract | — | port + goldens |
| 015–018 | Freqtrade/Nautilus/LEAN/Hummingbot lanes | §14 | D-012/D-013 | AD §K | T-006-02..05 | adapter integration | EG-2 | bakeoff artifacts per engine |
| 019 | vectorbt accelerator probe | §14 | D-012 | AD §K | T-006-06 | adapter integration | EG-2 | probe verdict |
| 020 | cross-engine semantic parity | §13 | SSOT WS4 | parity module | T-006-07 | engine parity | EG-2 | divergence reports |
| 021 | bake-off report + role recommendations | §20 | D-012 | AD §K | T-006-08 | — | EG-2/HG-2 | ENGINE_BAKEOFF_REPORT.md |
| 022 | MLflow run tracking proof (Test A) | §9.4-12 | D-019 | AD-05 | T-007-01 | integration | EG-3 | MLflow run evidence |
| 023 | DVC snapshot/restore proof | §4.2 | D-019 | AD-05 | T-007-02 | deterministic replay | EG-3 | restore test log |
| 024 | AI research run trace (Test B) | §12 | D-019/D-021 | AD §T | T-007-03 | AI evaluation | EG-3 | trace artifact |
| 025 | thin evidence link (Test C, replaceable refs) | §15.1 | D-016 | evidence module | T-007-04 | contract | EG-3 | EV records |
| 026 | experiment ledger, all-trial retention | §4.4/§9.4-12 | D-016 | experiment module | T-008-01 | unit + property | — | retention tests |
| 027 | idempotent run executor | §4.2 | AD-10 | jobs+experiment | T-008-02 | failure injection | — | idempotency tests |
| 028 | mandatory fee/slippage grid | §18.2 | D-023 | AD §I, validation G5 | T-008-03 | golden | — | sensitivity tables |
| 029 | (reserved) | — | — | — | — | — | — | — |
| 030 | continuous state upkeep | mandate §2 | SSOT §8 | state files | T-000-01 | — | audits | state files current |
| 031 | manifest regeneration on controlled edits | mandate §29 | D-030 | integrity manifest | T-000-02 | script | — | verification run |
| 032 | decision-ID hygiene | mandate §1 | D-027 | DECISION_LOG | T-000-03 | local gate check | — | uniqueness check |
| 033 | stage-exit gate reviews | mandate §9 | PROGRAM_PLAN | EG/HG system | T-000-04 | E2E | all | STAGE_EXIT reports |
| 034 | gates G1–G3 executable | §8 | validation spec | validation module | T-009-01 | leakage/golden | EG-4 | gate fixtures+results |
| 035 | G4 leakage detection | §18.3 | validation spec | validation module | T-009-02 | leakage | EG-4 | leaky-fixture rejections |
| 036 | G5–G9,G11 harness | §8 | validation spec | validation module | T-009-03 | integration | EG-4 | validation package |
| 037 | G10 method validation (PBO/DSR) | §18.1 | D-021 | SKILL_VALIDATION_STATS | T-009-04 | golden (known-answer) | — | method report |
| 038 | validation report + red team | §3 | skill spec | SKILL_BACKTEST_RED_TEAM | T-009-05 | — | EG-4 | BACKTEST_VALIDATION_REPORT.md |
| 039 | ingestion lifecycle tooling | §9.3-07 | D-014 | ingestion module | T-010-01 | unit | — | lifecycle tests |
| 040 | 10-item seed batch | §4.1 | D-020 | SKILL_STRATEGY_SOURCE_INGESTOR | T-010-02..11 | converter parity | EG-5 | per-item six files |
| 041 | ingestion lessons report | §4.4 | D-020 | — | T-010-12 | — | EG-5 | STRATEGY_INGESTION_REPORT.md |
| 042 | MDL/AGT/PRM registries | §9.9 | D-005 | AD §T | T-011-01 | unit | — | registry tests |
| 043 | frozen fixture corpus | §10 | D-021 | benchmark suite | T-011-02 | AI eval (hash freeze) | — | corpus manifest |
| 044 | null-provider harness E2E | §17 no-fake | D-021 | AD-11/AD-12 | T-011-03 | AI eval | EG-6 | null-run log |
| 045 | judge calibration set | §10.2 | blueprint safeguards | AD §T | T-011-04 | AI eval | — | calibration manifest |
| 046 | ≥2 real configs multi-sample runs | §10 | D-021/AD-11 | AD §T | T-011-05 | model regression | EG-6 | BMK records |
| 047 | benchmark seed report | §10 | D-021 | — | T-011-06 | — | EG-6 | AI_BENCHMARK_SEED_REPORT.md |
| 048 | read-only dashboard API | §4.9 | D-026 | dashboard_api | T-014-01 | contract | — | API contract tests |
| 049 | six-view evidence surface | §4.9 | D-026/AD-06 | AD §AI | T-014-02 | E2E | WS9 exit | browsable evidence |
| 050 | approval state machine (live unreachable) | §4.6 | North Star §9.7 | AD §Y | T-016-01 | security | — | transition tests |
| 051 | risk rules as validation preconditions | §4.3 | AD §Z | validation | T-016-02 | unit | — | rule checks in VAL |
| 052 | secret hygiene enforcement | §18 | D-028 | security_ops | T-018-01 | security | — | planted-secret test |
| 053 | ingested-code containment | §18 | AD §AB | ingestion+security | T-018-02 | security | — | containment test |
| 054 | dependency/license audit | §4.1 | AD-02 | security_ops | T-018-03 | security | — | audit runs |
| 055 | stage-exit security reviews | §18 | AD §AB | SKILL_SECURITY_REVIEWER | T-018-04 | security | stage exits | review reports |
| 056 | jobs module | §9.11-35 | AD-10 | jobs | T-019-01 | failure injection | — | queue tests |
| 057 | reports as projections | §9.11-34 | AD §AG | reporting | T-019-02 | golden | — | regeneration test |
| 058 | prototype decision assembly | §19/§20 | D-025 | PROGRAM_PLAN | T-019-03 | E2E | EG-7/HG-2 | PROTOTYPE_EVIDENCE_DECISION.md |

## Deferred-stage requirements (S2/S3 — traced, not yet tasked in detail)

| REQ | Requirement | Stage | TODO initiative |
|---|---|---|---|
| 100-series | dictionary/ontology (concept tables, FIBO seed, MVP backfill) | S2 | 12 |
| 110-series | research asset registry + backfill + amortization | S2 | 13 |
| 120-series | operator console (IA, entity pages, search, comparisons, approvals UI) | S2 | 14 (S2 backlog) |
| 130-series | observability adoption decisions | S2 | 17 |
| 140-series | paper lane, divergence model, drills, venue human gates | S3 | 15 |
| 150-series | market expansion invariance audits | S3+ | 20 |

## Reverse-check summary (no orphans)

- Every AD architecture component (§§B–AL) maps to ≥1 REQ row or an explicit deferral row — checked in `audits/ARCHITECTURE_COMPLETENESS_AUDIT.md`.
- Every TODO task carries a REQ (verified in `audits/TODO_COMPLETENESS_AUDIT.md`).
- REQ-029 is reserved (numbering gap kept stable rather than renumbering all tasks).
