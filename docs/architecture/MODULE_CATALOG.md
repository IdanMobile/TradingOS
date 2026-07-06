# Module Catalog — Trading Intelligence OS

Status: Planning specification v1. Module boundaries are Approved as *names and responsibilities*; internal technology remains Provisional until `decisions/PROTOTYPE_EVIDENCE_DECISION.md`.
Date: 2026-07-06
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

## Modules

### 1. `core_types`
- Responsibility: value objects, IDs, enums, decimal/money/timestamp discipline (§1 of type catalog).
- Public API: constructors + validation only. No I/O, no config.
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
- Sub-modules: `freqtrade_adapter`, `nautilus_adapter`, `lean_adapter`, `hummingbot_adapter`, `vectorbt_probe` (each independently removable).
- Forbidden deps: adapters may not import each other; parity logic lives in `parity`, not in adapters.
- Tests: per-adapter integration tests against frozen mini-fixture dataset; normalization golden tests.
- MVP: ≥2 adapters must reach working state (vertical-slice exit criterion); all 4 attempted.
- Replacement strategy: delete the directory; port stays.

### 5. `parity`
- Responsibility: cross-engine comparison — signal/trade timestamp alignment, fee comparison, warm-up, same-bar semantics, divergence diagnosis reports (WS4).
- Depends on: normalized results only (never raw engine output).
- Tests: synthetic divergence fixtures (known differences must be detected and classified).
- MVP: required.

### 6. `experiment` (Experiment Ledger)
- Responsibility: EXP/RUN records, all-trial retention, environment manifests, artifact registration.
- Public API: declare experiment, record run, list/compare, lineage queries.
- Depends on: `lineage_adapter` port for external tracker refs.
- Tests: retention invariants (winner must reference population), append-only enforcement.
- MVP: required (WS5 consumer).

### 7. `lineage_adapter`
- Responsibility: wrap MLflow/DVC (or the prototype-selected alternative) behind LineageAdapter port.
- Constraint: domain stores only public refs (replaceability gate from prototype spec).
- Tests: fresh-checkout restore test; ref-stability test.
- MVP: required in prototype form (WS5).

### 8. `validation`
- Responsibility: gates G1–G12 as composable checks; fee/slippage grid runner; OOS/walk-forward/robustness/regime report builders; hard-fail logic.
- Public API: `run_gate(g, ctx)`, `assemble_package(sv, ctx)`.
- Forbidden: no promotion authority (that is `approval`).
- Tests: each gate has a fixture that must FAIL it (leakage fixture, cost-only-profit fixture, non-reproducible fixture…) and one that passes; grid completeness test.
- MVP: required subset G1–G9+G11 (WS6).

### 9. `ingestion`
- Responsibility: source records, license records, ambiguity records, canonical-spec extraction workflow state machine (`DISCOVERED→…→VALIDATION_ELIGIBLE/REJECTED`).
- MVP: manual-assist tooling for the 10-item seed batch only (WS7). Mass automation forbidden until S2 decision.
- Tests: lifecycle transition guards; license-class gating.

### 10. `evidence` (Trading Evidence Registry)
- Responsibility: EV records; validation_state/approval_state projections; contradiction links; the queryable spine connecting everything.
- Custom-build justification: North Star §15.1; no existing tool owns these semantics (re-checked in `research/EXISTING_CAPABILITY_REGISTRY.md`).
- Tests: referential integrity across DS/SV/EXP/VAL; replaceability test (no tracker-internal keys).
- MVP: thin version required (Test C of lineage prototype).

### 11. `approval`
- Responsibility: approval identity + state machine (§2 Approval in type catalog); transition gate enforcement; human-decision records.
- MVP: state model + records only; no live states reachable (compile-time/config guard).
- Tests: forbidden-transition tests; live-state-unreachable test (security-relevant).

### 12. `knowledge` (Dictionary + Research Assets + Sources)
- Responsibility: CON/RA/SRC entities, freshness states, contradiction/supersession chains.
- MVP: minimal — entities + seed of concepts actually referenced by MVP artifacts.
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
- Responsibility: local job runner per Job contract (§5 type catalog) — queue table, retries, timeouts, artifact registration. No distributed broker in MVP.
- Tests: idempotency (rerun with same inputs), failure-preserves-artifacts.

### 16. `dashboard_api` + `dashboard_ui`
- Responsibility: read-only `/api/v1/` + the 6 MVP views (`MVP_SCOPE.md` §7).
- Forbidden: any write endpoint; any live-trading affordance.
- Tests: API contract tests; empty-state rendering.

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
| core_types, dataset, strategy, engine_adapters(≥2), parity, experiment, lineage_adapter, validation(G1–G9,G11), ingestion(manual), evidence(thin), jobs, dashboard_api/ui(read-only), reporting, security_ops | Required | S1 |
| approval (model only), knowledge (minimal), ai_eval (harness+fixtures), memory (minimal) | Required-thin | S1 |
| approval (full), knowledge (full), ai_eval (routing), paper lane, risk center, observability stack | Deferred | S2/S3 |
