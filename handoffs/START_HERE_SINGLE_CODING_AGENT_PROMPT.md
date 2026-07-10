# START HERE — Single Coding Agent Source of Truth

## EXECUTE, DO NOT SUMMARIZE

You are the coding agent for the Trading Intelligence OS project.

This file is the **single operational source of truth (SSOT) for coding-agent execution**.

You must start here. Do not treat any other file as an independent controller prompt.

The repository contains supporting authority, decisions, specifications, research, and state. Those files are subordinate to this SSOT according to the precedence rules below.

---

# 0. Authority and precedence — mandatory

When instructions conflict, use this exact order:

1. Higher-priority platform/system/safety instructions.
2. **This file:** `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md`.
3. `TRADING_OS_NORTH_STAR.md` for immutable product intent, approved principles, and strategic boundaries.
4. `DECISION_LOG.md` and files under `decisions/` for approved scoped decisions.
5. Files under `specs/` and `benchmarks/` for executable requirements and acceptance gates, and `docs/` planning authorities (`docs/architecture/AD.md`, `docs/architecture/MODULE_CATALOG.md`, `docs/architecture/TYPE_AND_CONTRACT_CATALOG.md`, `docs/program/PROGRAM_PLAN.md`, `docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md`, `docs/product/MVP_SCOPE.md`, `docs/testing/TEST_MASTER_PLAN.md`, `docs/traceability/TRACEABILITY_MATRIX.md`, `docs/ai/AGENT_ROLES.md`, `skills/`) for architecture, scope, and task design (D-030/D-036). Maturity labels inside AD.md (APPROVED/PROVISIONAL/UNRESOLVED) are binding: PROVISIONAL/UNRESOLVED items may not be treated as final selections.
6. `TODO.md` + `todos/` for task ordering *within* the phase this file authorizes. TODO never expands authorized scope.
7. `PROJECT_STATE.md` for current phase/status only.
8. `MISSING_AND_OPEN_ITEMS.md`, `RESEARCH_BACKLOG.md`, and `research/RESEARCH_GAP_MATRIX.md` for unresolved/deferred work.
9. Files under `research/` and `audits/` as evidence and review records, not controller instructions.
10. `PACKAGE_CHANGELOG.md` and `PACKAGE_README.md` as historical/navigation aids only.

## Conflict rule

If two subordinate files conflict:

- do not choose silently;
- follow the higher-precedence file;
- record the conflict in `MISSING_AND_OPEN_ITEMS.md`;
- add a decision-log entry if the resolution changes implementation behavior;
- stop only when the conflict cannot be resolved from this hierarchy without changing the North Star or an approved decision.

## No authority drift

You may update project state and evidence files as required, but you may **not** silently rewrite this SSOT, weaken the North Star, or promote a provisional research note into an approved decision.

---


# 0.1 Package integrity and input/output contract — mandatory before intake

Before the pre-code intake, perform a read-only package self-check.

## Must-exist input files

Every path listed in Section 1 (Mandatory read order) must already exist. If any is missing or unreadable:

- do not code;
- do not invent its contents;
- record the exact missing path;
- stop and ask for a corrected package.

## Expected generated artifacts

The following paths are outputs to be created during authorized execution and are **not** evidence of an incomplete package when absent at handoff time:

- `artifacts/reports/PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md`
- `decisions/PROTOTYPE_EVIDENCE_DECISION.md`
- `research/TOOL_AND_ENGINE_REGISTRY_V1.md`
- `research/EXISTING_STRATEGY_REGISTRY_V1.md`
- `artifacts/reports/ENGINE_BAKEOFF_REPORT.md`
- `artifacts/reports/LINEAGE_PROTOTYPE_REPORT.md`
- `artifacts/reports/BACKTEST_VALIDATION_REPORT.md`
- `artifacts/reports/STRATEGY_INGESTION_REPORT.md`
- `artifacts/reports/AI_BENCHMARK_SEED_REPORT.md`
- `artifacts/reports/PROTOTYPE_READINESS_REPORT.md`

## Integrity manifest

Read `PACKAGE_INTEGRITY_MANIFEST.md`. Verify that all required handoff inputs listed there exist. Hash verification is recommended when practical; a path mismatch is a hard blocker.

## No premature mutation

Until the Pre-Code Environment & Credentials Intake Gate passes, the only project-file mutations allowed are:

- the intake report;
- `.env.example`;
- `.gitignore`;
- state/open-item records strictly required to record intake choices or blockers.

Do not scaffold application code, install project dependencies, generate a framework app, or run implementation code before the gate passes.

---

# 1. Mandatory read order

Before asking the pre-code intake questions, read these in order:

1. `TRADING_OS_NORTH_STAR.md`
2. `PROJECT_STATE.md`
3. `DECISION_LOG.md`
4. `decisions/CODING_AGENT_READINESS_GATE_V1.md`
5. `decisions/INITIAL_REUSE_MATRIX.md`
6. `decisions/CRYPTO_SPOT_VENUE_AND_DATA_MATRIX_V1.md`
7. `specs/CRYPTO_SPOT_MVP_VERTICAL_SLICE_V1.md`
8. `specs/ENGINE_BAKEOFF_BLUEPRINT_V1.md`
9. `specs/CANONICAL_BAKEOFF_DATASET_V1.md`
10. `specs/FEE_AND_SLIPPAGE_ASSUMPTION_PACKAGE_V1.md`
11. `specs/BACKTESTING_VALIDATION_BLUEPRINT_V1.md`
12. `specs/EXPERIMENT_LINEAGE_PROTOTYPE_SPEC_V1.md`
13. `specs/STRATEGY_INGESTION_AND_REPRODUCTION_WORKFLOW_V1.md`
14. `specs/STRATEGY_SEED_BATCH_V1.md`
15. `specs/AI_AGENT_EVALUATION_BLUEPRINT_V1.md`
16. `benchmarks/ai_agent/FROZEN_BENCHMARK_SUITE_V1.md`
17. `specs/ENVIRONMENT_AND_CREDENTIALS_INTAKE_GATE_V1.md`
18. `RESEARCH_BACKLOG.md`
19. `MISSING_AND_OPEN_ITEMS.md`
20. `docs/product/MVP_SCOPE.md`
21. `docs/program/PROGRAM_PLAN.md`
22. `docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md`
23. `docs/architecture/AD.md` (note its maturity labels)
24. `docs/architecture/MODULE_CATALOG.md`
25. `docs/architecture/TYPE_AND_CONTRACT_CATALOG.md`
26. `docs/testing/TEST_MASTER_PLAN.md`
27. `TODO.md` (then the `todos/` initiative files for the current stage)
28. `research/EXISTING_CAPABILITY_REGISTRY.md` and `research/RESEARCH_GAP_MATRIX.md` (evidence freshness as of 2026-07-06; respect reverify triggers)

Do not merely acknowledge reading.

After reading, execute the **Pre-Code Environment & Credentials Intake Gate** below.

---

# 2. HARD GATE — Pre-Code Environment & Credentials Intake

## No code before this gate

Before creating, editing, generating, scaffolding, installing, or running implementation code, you must complete the interactive environment/configuration intake defined in:

`specs/ENVIRONMENT_AND_CREDENTIALS_INTAKE_GATE_V1.md`

This includes:

- required local runtime/tooling prerequisites;
- optional provider accounts;
- API credentials;
- model-provider credentials;
- data-provider credentials;
- storage/experiment-tracking credentials if applicable;
- exchange sandbox/test credentials if a later test actually requires them;
- every anticipated `.env` variable currently known from the approved prototype plan.

## Mandatory behavior for every item

For **each** requested account, key, token, endpoint, project ID, or configuration value, present:

- what it is;
- why it may be needed;
- whether it is `Required now`, `Optional now`, or `Deferred until a later gate`;
- exact official platform/service name;
- where it will be used in the prototype;
- safe local `.env` variable name;
- one of these choices:
  - **A. Configure now**
  - **B. Add later**
  - **C. Do not use this integration**
  - **D. Not sure — recommend**

The user must always be allowed to choose **Add later** independently for every item.

## Secret-handling rule

Never ask the user to paste secret values into chat, reports, Markdown, Git, commits, screenshots, logs, or issue trackers.

When the user chooses **Configure now**:

1. create or update `.env.example` with variable names only;
2. create/verify `.gitignore` excludes `.env`, `.env.*` secret variants, credential files, and local secret stores;
3. instruct the user to place the secret locally in the appropriate ignored `.env` file or approved secret store;
4. verify only presence/format where possible — never echo the secret value;
5. redact secrets from process output and reports.

## Deferred credentials

If the user chooses **Add later**:

- record the item in `MISSING_AND_OPEN_ITEMS.md`;
- mark its blocking phase/workstream;
- continue all work that does not require it;
- when the project reaches the first point where it is genuinely required, ask again using the same A/B/C/D choices;
- never fabricate or substitute credentials.

## Important current scope constraint

The current phase is constrained, no-money S2 autonomous research-lab execution.
Therefore:

- do **not** request live trading keys;
- do **not** request withdrawal-enabled exchange keys;
- do **not** request real-money brokerage credentials;
- do **not** require paid data accounts when free/public data is sufficient for the current test;
- do **not** request provider or venue credentials in the current S2 scope;
- do **not** connect to a paper, demo, sandbox, or testnet venue.

## Gate completion artifact

Before code starts, create:

`artifacts/reports/PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md`

It must contain no secret values and must list:

- all items presented;
- user choice per item;
- required-now blockers;
- deferred items;
- integrations disabled by choice;
- generated `.env.example` variables;
- confirmation that secret files are ignored by Git.

Only after this artifact exists may implementation begin.

---

# 3. Immutable operating rules

### Reuse before build
Before creating a meaningful custom capability, prove that existing validated options are insufficient. Use existing engines, libraries, APIs, frameworks, reference implementations, and standards where they fit.

### No real money
Do not enable real-money trading. Do not request, store, or use live exchange API keys.

### No final architecture by preference
Architecture decisions must follow executable evidence. Do not select a framework because it is familiar or popular.

### Preserve all failures
Failed installs, failed runs, semantic mismatches, and rejected candidates are evidence. Record them.

### No regression by omission
Do not silently skip a first-tier candidate. A candidate can be marked blocked only with reproducible evidence and attempted official installation path.

### Truth over completion theater
If something cannot be verified, mark it unverified. Do not fabricate benchmark results, model results, costs, or compatibility.

### Exact provenance
Every run must record code commit, data identity, engine/tool version, parameters, cost assumptions, and artifacts.

---

# 4. Current authorized phase

Execute only the constrained S2 architecture and autonomous research-lab scope defined in:

`docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md`

S1 evidence in `specs/CRYPTO_SPOT_MVP_VERTICAL_SLICE_V1.md` remains the retained input.
The active goal is autonomous evidence operations: sourced hypotheses, reproducible
offline research/backtests, retained trials, independent scoring, validation, and a
read-only research console.

## Stage and first initiative (2026-07-10 HG-2 decision)

- Program stage: **S2 — constrained autonomous research lab** (HG-2 approved in D-036).
- **Exact first initiative:** `todos/02_architecture_foundation.md`, T-002-01 through
  T-002-04, followed by the S2 delivery waves in
  `docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md`.
- S1 workstreams WS1–WS9 in §5 are completed evidence inputs, not instructions to
  rerun or expand the prototype.
- Implementation must respect module boundaries and test gates. S2 may resolve
  PROVISIONAL architecture items only from retained evidence and recorded decisions.
- No strategy approval, synthetic wallet activation, paper/demo/testnet connection,
  credential use, order routing, live trading, or real-money capability follows from
  S2 entry. B2 remains `INCOMPLETE_NOT_APPROVABLE` and rejected for paper. AI cannot
  approve or trade.

---

# 5. Required workstreams

### WS1 — Repository bootstrap and evidence structure
Create a maintainable monorepo or equivalent workspace only as needed for the prototype.

Minimum evidence directories:

```text
artifacts/
  datasets/
  bakeoff/
  lineage/
  validation/
  strategy_ingestion/
  ai_benchmarks/
  reports/
```

Create machine-readable manifests. Keep generated large artifacts out of Git where appropriate, but preserve hashes and references.

### WS2 — Canonical frozen dataset
Implement `specs/CANONICAL_BAKEOFF_DATASET_V1.md`.

Required:
- BTCUSDT and ETHUSDT;
- 5m, 15m, 1h;
- official Binance public Spot data;
- raw hashes;
- normalized dataset;
- quality report;
- reproducible regeneration;
- frozen dataset ID.

Stop only if the official data source is unreachable after documented retries/alternatives.

### WS3 — Engine bake-off
Evaluate:
- Freqtrade
- NautilusTrader
- LEAN
- Hummingbot

Separate accelerator probe:
- vectorbt

Use the common baseline strategies and assumptions already defined.

Do not force one winner. Score role fit.

Record:
- exact version/commit;
- install path;
- environment;
- run commands;
- runtime;
- memory where practical;
- determinism;
- metrics;
- trades;
- artifact export;
- semantic differences;
- blockers.

### WS4 — Cross-engine parity
For baselines implemented in multiple engines:
- compare signal timestamps;
- compare trade timestamps;
- compare fees;
- compare warm-up;
- compare same-bar behavior;
- explain differences.

A numeric P&L difference without semantic diagnosis is insufficient.

### WS5 — Experiment lineage prototype
Execute `specs/EXPERIMENT_LINEAGE_PROTOTYPE_SPEC_V1.md`.

Prototype:
- MLflow
- DVC
- thin Trading Evidence link

Return one decision:
- `MLFLOW_PLUS_DVC_RECOMMENDED`
- `MLFLOW_ONLY_RECOMMENDED`
- `DVC_ONLY_RECOMMENDED`
- `ALTERNATIVE_REQUIRED`

with evidence.

### WS6 — Backtesting validation harness
Implement enough of `specs/BACKTESTING_VALIDATION_BLUEPRINT_V1.md` to exercise at least one baseline strategy.

Mandatory prototype gates:
- reproducibility;
- timestamp/data integrity;
- semantic review;
- leakage check;
- fee/slippage grid;
- temporal OOS;
- one walk-forward run;
- parameter-neighborhood robustness.

Do not claim full production validation if PBO/DSR or other advanced methods are not yet implemented.

### WS7 — Strategy ingestion seed batch
Complete the 10-item batch from `specs/STRATEGY_SEED_BATCH_V1.md`.

Do not mass scrape.

Record licensing and semantic ambiguity.

### WS8 — AI/Agent benchmark seed
Build the harness and frozen fixtures for the V1 suite.

The S1 intake deferred model-provider credentials. Constrained S2 remains null/mock-only:
do not request or use provider credentials, and do not fabricate model outputs. Any
future real-provider evaluation requires separate authority beyond D-036.

### WS9 — Minimal evidence control surface
Build only a minimal read-only dashboard/control surface showing:
- datasets;
- runs;
- strategies;
- engine comparison;
- validation status;
- evidence links.

Do not expand into the final product IA.

---

# 6. Verification discipline

For every workstream:
1. implement the smallest useful slice;
2. test;
3. record evidence;
4. update state;
5. continue unless a genuine blocker exists.

Required automated checks where applicable:
- unit tests;
- type checks;
- lint;
- build;
- deterministic smoke tests;
- data manifest validation.

Use the repository's actual stack once established; do not invent fake commands in reports.

---

# 7. Decision artifacts — mandatory

Create/update:

```text
decisions/PROTOTYPE_EVIDENCE_DECISION.md
research/TOOL_AND_ENGINE_REGISTRY_V1.md
research/EXISTING_STRATEGY_REGISTRY_V1.md
artifacts/reports/PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md
artifacts/reports/ENGINE_BAKEOFF_REPORT.md
artifacts/reports/LINEAGE_PROTOTYPE_REPORT.md
artifacts/reports/BACKTEST_VALIDATION_REPORT.md
artifacts/reports/STRATEGY_INGESTION_REPORT.md
artifacts/reports/AI_BENCHMARK_SEED_REPORT.md
artifacts/reports/PROTOTYPE_READINESS_REPORT.md
```

For each major capability use exactly one decision state:
- Reuse Existing
- Reuse + Adapter
- Hybrid
- Build Custom
- Defer
- Rejected
- Unresolved

Every recommendation must link to evidence.

---

# 8. State management

Continuously update:
- `PROJECT_STATE.md`
- `DECISION_LOG.md`
- `RESEARCH_BACKLOG.md`
- `MISSING_AND_OPEN_ITEMS.md`
- `PACKAGE_CHANGELOG.md`

Do not let these drift behind implementation.

---

# 9. Stop conditions

Do not stop for normal engineering choices that can be resolved through evidence.

Stop only for:
- a human-only credential/account action that is **required now** and cannot be deferred;
- a request that would cross into real-money/live-trading scope;
- a conflict that cannot be resolved through the SSOT precedence hierarchy;
- a destructive or irreversible action requiring human approval;
- a genuine external blocker after documented alternatives are exhausted.

Otherwise continue the authorized phase.
