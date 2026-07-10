# Module Catalog — Trading Intelligence OS

Status: S2 architecture-lock specification v1. Boundaries and selected S2 technologies are approved by retained S1 evidence and D-036.
Date: 2026-07-10
Companion: `docs/architecture/AD.md` §E (module map), `TYPE_AND_CONTRACT_CATALOG.md` (types).

## Dependency law

```text
core_types ← everything
domain modules (strategy, experiment, validation, evidence, approval, knowledge, ai_eval, memory)
    may depend on: core_types, storage ports. NEVER on adapters, engines, UI, jobs.
adapters (engines, lineage, data_sources, ai_providers)
    may depend on: core_types, the port they implement. NEVER on each other or domain internals.
services (jobs, ingestion, reporting, dashboard_api)
    may depend on: domain modules + ports. UI depends only on dashboard_api.
```
Arrows point inward (ports & adapters). A dependency in the forbidden direction is an architecture-test failure (see TEST_MASTER_PLAN).

S2 infrastructure allocation: SQLite owns operational rows and read models; Parquet + DuckDB own analytical payloads; MLflow + DVC sit only behind lineage ports. No module may introduce a broker, PostgreSQL dependency before the measured `AD.md` §P trigger, or a second source of truth for retained artifacts.

## Modules

### 1. `core_types`
- Responsibility: value objects, IDs, enums, decimal/money/timestamp discipline, and inert Market/Signal/Order/Fill/Position/Account/Portfolio/Risk/Approval/ChartAnnotation records (§0–2 of type catalog).
- Public API: constructors + validation only. No I/O, no config.
- S2 boundary: trading-domain records normalize historical evidence/read models only; they expose no venue client, mutation method, account state, or execution authority.
- Forbidden deps: everything else.
- Tests: property-based validation tests; serialization round-trips.
- MVP: required first. Replacement strategy: none (foundational).

### 2. `dataset` (Data Foundation)
- Responsibility: raw snapshot download, normalization, quality checks, freezing, manifests (implements `specs/CANONICAL_BAKEOFF_DATASET_V1.md`).
- Public API: `freeze_dataset`, `verify_dataset`, `load_frozen(ds_id)`.
- Owned state: `data/raw/**` (immutable), `data/normalized/**`, dataset manifests.
- Storage: filesystem + manifests; registry row in operational DB.
- Tests: quality-gate unit tests, double-regeneration hash test (golden), missing-interval report test.
- MVP: required (WS2).

### 3. `strategy` (Strategy Domain)
- Responsibility: canonical strategy spec model, versioning, spec hashing, spec validation.
- Public API: parse/validate spec, create version, diff versions.
- Forbidden: any engine-specific code (that lives in adapters/converters).
- Tests: spec schema validation, immutability tests, golden specs for the 4 baselines.
- MVP: required (WS3 prerequisite).

### 4. `engine_adapters`
- Responsibility: one adapter per engine implementing EngineAdapter port; result normalization; capability reports.
- S2 roles: `vectorbt_probe` is the selected bounded research accelerator; `freqtrade_adapter` is the selected Crypto Spot event/reproduction lane; `nautilus_adapter` is limited to its evidenced bounded event-simulation capability; `hummingbot_adapter` and `lean_adapter` remain deferred capability candidates until their recorded gaps close. Each is independently removable.
- Invocation: isolated subprocess/CLI environments only for S2 Research Lab work; adapters receive allowlisted plans and return normalized results. Freqtrade trade/dry-run, testnet/sandbox, venue, paper, and live modes are rejected.
- Forbidden deps: adapters may not import each other; parity logic lives in `parity`, not in adapters.
- Tests: per-adapter integration tests against frozen mini-fixture dataset; normalization golden tests.
- S2: vectorbt acceleration plus Freqtrade reproduction are required; other lanes run only where retained capability evidence supports the task.
- Replacement strategy: delete the directory; port stays.

### 5. `parity`
- Responsibility: cross-engine comparison — signal/trade timestamp alignment, fee comparison, warm-up, same-bar semantics, divergence diagnosis reports (WS4).
- Depends on: normalized results only (never raw engine output).
- Tests: synthetic divergence fixtures (known differences must be detected and classified).
- MVP: required.

### 6. `experiment` (Experiment Ledger)
- Responsibility: EXP/RUN, ResearchLabBatch, and Scorecard records; all-trial retention; environment manifests; artifact registration; independent score dimensions and blockers.
- Public API: declare experiment, record run/batch/scorecard, list/compare, lineage queries.
- Depends on: `lineage_adapter` port for external tracker refs.
- Tests: retention invariants (winner must reference population), append-only enforcement.
- MVP: required (WS5 consumer).

### 7. `lineage_adapter`
- Responsibility: wrap the S1-selected MLflow run/artifact service and DVC dataset snapshot/restore service behind LineageAdapter ports.
- Constraint: domain stores only public refs (replaceability gate from prototype spec).
- Operations: retain completed and failed lineage indefinitely by default; operator/loopback-only access; backup, restore, upgrade, and migration follow `AD.md` §P.
- Tests: fresh-checkout restore/hash-replay test; ref-stability test; backup-set restore after tool upgrade.
- S2: approved from the seven-gate S1 prototype; filesystem manifests remain the failure fallback.

### 8. `validation`
- Responsibility: gates G1–G12 as composable checks; fee/slippage grid runner; OOS/walk-forward/robustness/regime report builders; hard-fail logic.
- Public API: `run_gate(g, ctx)`, `assemble_package(sv, ctx)`.
- Forbidden: no promotion authority (that is `approval`).
- Tests: each gate has a fixture that must FAIL it (leakage fixture, cost-only-profit fixture, non-reproducible fixture…) and one that passes; grid completeness test.
- MVP: required subset G1–G9+G11 (WS6).

### 9. `ingestion`
- Responsibility: acquire untrusted research inputs, validate `ResearchSource`/license/ambiguity records, and translate source claims into proposed Hypothesis/canonical-spec inputs.
- S2: bounded primary-source registration and refresh are allowed; source text is data, publication is not proof, and only the deterministic provenance flow may write domain records. Mass unsourced discovery remains forbidden.
- Tests: lifecycle transition guards; license-class gating.

### 10. `evidence` (Trading Evidence Registry)
- Responsibility: EV records; validation_state/approval_state projections; contradiction links; the queryable spine `ResearchSource → Hypothesis → STRAT/SV → LAB/EXP/RUN → Scorecard → VAL/EV`.
- Custom-build justification: North Star §15.1; no existing tool owns these semantics (re-checked in `research/EXISTING_CAPABILITY_REGISTRY.md`).
- Tests: referential integrity across DS/SV/EXP/VAL; replaceability test (no tracker-internal keys).
- MVP: thin version required (Test C of lineage prototype).

### 11. `approval`
- Responsibility: approval identity + state machine (§2 Approval in type catalog); transition gate enforcement; human-decision records.
- S2: inert state records/read projections only. `NOT_ELIGIBLE`, `RESEARCH`, and `VALIDATION` are reachable; demo/paper/live decisions and all LIVE-family states are unreachable.
- Tests: forbidden-transition tests; demo/paper/live-unreachable tests (security-relevant).

### 12. `knowledge` (Dictionary + Research Assets + Sources)
- Responsibility: CON/RA/ResearchSource/Hypothesis entities, bibliographic/provenance identity, freshness/reproduction states, and contradiction/supersession chains.
- S2: primary-source registry and hypothesis families needed by the autonomous evidence flow; no claim is labeled proven without retained local reproduction evidence.
- Tests: freshness transitions; supersession chain integrity.

### 13. `ai_eval`
- Responsibility: benchmark harness (modes A/B/C), frozen fixtures, AGT/MDL/PRM/BMK records, scoring views, cost capture.
- Constraint: harness must run fixture pipeline end-to-end with a `null` provider (no credentials) — WS8 requirement.
- Tests: fixture hash freeze test; no-network controlled-mode test; provider-failure handling.
- MVP: harness + fixtures required; live model runs optional.

### 14. `memory`
- Responsibility: LRN records, evidence-link enforcement, invalidation triggers.
- MVP: minimal write path + list view.

### 15. `jobs`
- Responsibility: first expose one bounded deterministic ResearchLabBatch CLI command; after its idempotency proof, optionally run the allowlisted Job contract (§5 type catalog) from a local SQLite table with bounded retries/timeouts/concurrency and artifact registration.
- Allowlist: research batches, research-source refresh, data freshness, validation, and reports only. Engine/parity steps occur inside a bounded batch; arbitrary shell/venue/order commands are invalid.
- Forbidden: scheduling before identical-input reuse passes; distributed workers; broker; demo/testnet/sandbox, paper, live, venue, credential, order, and approval-transition commands.
- Tests: identical complete input returns the same batch/artifact refs without recomputation; partial/failure preservation; command allowlist; prohibited execution boundaries.

### 16. `dashboard_api` + `dashboard_ui`
- Responsibility: read-only `/api/v1/` and bounded S2 views for Research Lab batches, source-linked candidates, independent score comparisons, historical market/chart annotations, automation status, and inert trading-domain projections.
- Read model: manifests + operational projections only; UI is never a source of truth. Local batch triggering remains CLI-only throughout S2; persisted scheduling is the only trigger added after the jobs idempotency gate passes.
- Forbidden: POST/PUT/PATCH/DELETE, trigger/order/approval endpoints, synthetic wallet or account mutation, venue credentials/clients, and demo/paper/live controls or affordances.
- Tests: JSON serialization/schema contracts; prohibited HTTP methods; disabled execution flags; empty-state rendering.

### 17. `reporting`
- Responsibility: build the mandated `artifacts/reports/*.md` from machine-readable inputs (reports are projections, never hand-maintained truth).

### 18. `security_ops` (cross-cutting, thin)
- Responsibility: `.env` loading/validation, secret-absence linting in artifacts, gitignore verification, dependency audit wiring.
- Tests: secret-scan test on artifact tree; env validation test.

## Ownership & lifecycle

Single operator owns everything; "ownership" columns therefore denote *replacement blast radius*: adapters (small), services (medium), domain (large), core_types (foundational). Deprecation: a module is retired by (1) decision-log entry, (2) port left in place one stage, (3) deletion with changelog note.

## MVP status summary

| Module | MVP | Stage |
|---|---|---|
| core_types (including inert trading contracts), dataset, strategy, engine_adapters (vectorbt accelerator + Freqtrade reproduction), parity, experiment (LAB/SCORE), lineage_adapter (MLflow+DVC), validation, ingestion (bounded sources), evidence, jobs (command first), dashboard_api/ui (read-only), reporting, security_ops | Active bounded scope | S2 |
| approval (inert model only), knowledge (ResearchSource/Hypothesis), ai_eval (mock/null only), memory (evidence-linked) | Active bounded scope | S2 |
| persisted scheduling | Conditional: only after first batch command proves idempotent | S2 |
| real-provider AI, demo/testnet/sandbox or paper lane, synthetic wallet/account mutation, venue/order routing, live-family approval, live trading, risk execution center, broker/distributed orchestration | Prohibited or deferred | Post-S2 gates / S3–S4 |
