# Program Plan — Trading Intelligence OS

Status: Approved planning baseline v1
Date: 2026-07-06
Authority: subordinate to `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md` (SSOT). This file organizes work; it does not authorize work the SSOT forbids.

## 1. Program stages (hard-gated)

The program distinguishes five stages. Each has entry criteria, exit criteria, and a human gate. **No stage may begin before its predecessor's exit gate passes.**

```text
S0 Planning Completion  → S1 Prototype Execution → S2 MVP Implementation
→ S3 Paper-Trading Qualification → S4 Live-Readiness (NOT AUTHORIZED)
```

### S0 — Planning completion (current stage)

- Entry: v7 package + this planning mandate.
- Work: architecture decision doc, TODO system, research gap closure, audits, SSOT update.
- Exit: `audits/PLANNING_HANDOFF_SIMULATION.md` = PASS; `PROJECT_STATE.md` updated; SSOT points to planning system.
- Human gate: operator reads final report; no approval needed to proceed to S1 (S1 was already authorized by `decisions/CODING_AGENT_READINESS_GATE_V1.md`).

### S1 — Prototype execution (first coding initiative)

- Entry: S0 exit + Pre-Code Environment & Credentials Intake Gate (`specs/ENVIRONMENT_AND_CREDENTIALS_INTAKE_GATE_V1.md`) passes.
- Work: SSOT workstreams WS1–WS9 (repo bootstrap, canonical dataset, engine bake-off, parity, lineage prototype, validation harness, seed ingestion, AI benchmark seed, minimal evidence surface).
- Exit: all `specs/CRYPTO_SPOT_MVP_VERTICAL_SLICE_V1.md` exit criteria; `decisions/PROTOTYPE_EVIDENCE_DECISION.md` created.
- Human gate: operator approves the prototype evidence decision (reuse selections, architecture consequences).

### S2 — MVP implementation

- Entry: S1 exit + operator approval of prototype decisions + `docs/architecture/AD.md` provisional sections resolved to Approved for chosen components.
- Work: initiatives 02–17 in `TODO.md` (domain layer, evidence registry, validation productionization, dashboard MVP pages, paper-lane readiness).
- Exit: `docs/product/MVP_SCOPE.md` §9 success criteria met in the product (not just prototype scripts).
- Human gate: operator MVP acceptance review.

### S3 — Paper-trading qualification

- Entry: S2 exit; ≥1 strategy passing validation gates.
- Work: paper deployment, backtest-vs-paper divergence tracking, operational monitoring, kill-switch drills (paper-level).
- Exit: divergence model quantified; paper stability period defined and met; human-only venue gates (MISSING_AND_OPEN_ITEMS §"Human-only") resolved.
- Human gate: explicit limited-live review. **This gate cannot be delegated to any agent.**

### S4 — Live-readiness

- NOT AUTHORIZED. Requires everything in S3 plus the ten human-only items in `MISSING_AND_OPEN_ITEMS.md`. Kept in the plan only so the path is explicit.

## 2. Initiatives and dependency graph

Initiative IDs match `todos/` directories.

```text
S0: 00 Program governance ──────────────────────────────┐
S1: 01 Research completion (parallel, non-blocking) ────┤
S1: 03 Repository foundation ──► 04 Data foundation ──► 06 Engine bake-off ──► 07 Experiment lineage
                                        │                        │                      │
                                        ▼                        ▼                      ▼
S1:                              08 Backtesting ────────► 09 Validation ◄── 05 Strategy domain (spec format)
                                        │                        │
S1: 10 Strategy ingestion (needs 05) ───┘                        ▼
S1: 11 AI/agent eval seed (independent after 03) ────► 14 Evidence dashboard (needs any producer)
S2: 02 Architecture foundation (consumes S1 evidence) ─► 12 Dictionary/ontology, 13 Research assets,
                                                          15 Paper trading, 16 Risk & approvals,
                                                          17 Observability, 18 Security hardening, 19 Operations
S3+: 20 Future market expansion (design-only until S3)
```

Critical path (S1): 03 → 04 → 06 → 09 → prototype decision. Parallelizable off-path: 05, 07 (after 04), 10 (after 05), 11 (after 03), 14 (after first artifacts exist).

## 3. Evidence gates (non-human)

| Gate | After | Evidence artifact | Blocking |
|---|---|---|---|
| EG-1 Dataset frozen | 04 | dataset manifest + double-regeneration hash match | 06, 08, 09 |
| EG-2 Engines scored | 06 | `artifacts/reports/ENGINE_BAKEOFF_REPORT.md` | prototype decision |
| EG-3 Lineage decided | 07 | `artifacts/reports/LINEAGE_PROTOTYPE_REPORT.md` with one of 4 verdicts | S2 architecture lock |
| EG-4 Validation exercised | 09 | `artifacts/reports/BACKTEST_VALIDATION_REPORT.md` | prototype decision |
| EG-5 Ingestion lessons | 10 | `artifacts/reports/STRATEGY_INGESTION_REPORT.md` | automation decisions (S2) |
| EG-6 AI harness real | 11 | `artifacts/reports/AI_BENCHMARK_SEED_REPORT.md` (execution may be deferred w/o credentials) | AI routing decisions (S2) |
| EG-7 Prototype decision | all S1 | `decisions/PROTOTYPE_EVIDENCE_DECISION.md` | S2 entry |

## 4. Human gates

| Gate | When | Decision owner | Cannot be skipped because |
|---|---|---|---|
| HG-1 Env/credentials intake | S1 entry | Operator | secrets and provider choices are operator-only |
| HG-2 Prototype evidence approval | S1 exit | Operator | architecture lock follows from it |
| HG-3 MVP acceptance | S2 exit | Operator | defines paper-phase entry |
| HG-4 Venue/operator eligibility | before S3 exit | Operator | account-level facts are unknowable to agents |
| HG-5 Limited-live review | S3 exit | Operator | real capital |

## 5. Stop / change-direction rules

Stop the program stage and escalate to the operator when:

1. An EG gate fails twice with different approaches (record both attempts as evidence).
2. Prototype evidence contradicts an Approved decision in `DECISION_LOG.md` (e.g., all four engines fail hard-rejection conditions) — requires a decision-log amendment, not silent workaround.
3. A dependency (exchange API, data source, tool) materially changes licensing/availability mid-stage.
4. Any action would cross the no-real-money boundary.
5. Two compaction/handoff cycles fail to preserve continuity (rebuild from `PROJECT_STATE.md` + SSOT).

Change direction (without stopping) when a cheaper route produces the same evidence — record it in the decision log with the evidence link.

## 6. Parallelization policy

Single operator + single coding agent is the default. Parallel agent fan-out is justified only inside bounded, read-only research or independent per-engine bake-off lanes; never for state-mutating work on the same artifacts. This mirrors the SSOT's evidence discipline: parallel lanes must write to disjoint artifact directories.
