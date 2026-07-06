# Type and Contract Catalog — Trading Intelligence OS

Status: Planning specification v1. Language-neutral. No technology binding is implied except where a decision is already Approved.
Date: 2026-07-06
Rule: implementation must not begin from this file alone; it binds names and semantics, not storage or wire formats. Serialization decisions land in S2 after the lineage prototype.

## 0. Conventions

- IDs are opaque, prefixed, human-scannable strings: `DS-`, `STRAT-`, `SV-`, `HYP-`, `EXP-`, `RUN-`, `VAL-`, `EV-`, `APR-`, `SRC-`, `RA-`, `CON-`, `MDL-`, `AGT-`, `PRM-`, `BMK-`, `LRN-`. IDs never encode mutable facts.
- All timestamps are UTC, explicit-offset serialized (`2026-07-06T00:00:00Z`). Naive datetimes are forbidden at every boundary.
- Money/price/quantity are **decimal** types with explicit precision; binary floats are forbidden in accounting paths (permitted inside vectorized research computation, but results crossing a contract boundary re-quantize to decimal with documented precision).
- Every entity carries `created_at`, `creator_type` (human|agent|system), and provenance links. Evidence-bearing records are append-only; corrections are new records referencing the old (supersession, never mutation).

## 1. Scalar / value types

| Type | Definition | Precision / constraints | Serialization |
|---|---|---|---|
| InstrumentId | canonical `{base}-{quote}.{venue_family}` e.g. `BTC-USDT.BINANCE_SPOT` | uppercase; mapping table to venue-native symbols | string |
| VenueSymbol | venue-native symbol e.g. `BTCUSDT` | never used as identity; always paired with venue | string |
| Timeframe | enum: `1m 5m 15m 1h 4h 1d` (extensible) | canonical seconds field | string + int seconds |
| Price | decimal | per-instrument tick size recorded; no float | string decimal |
| Quantity | decimal (base asset) | per-instrument lot/step recorded | string decimal |
| Money | decimal + currency code | quote-asset accounting in MVP | `{amount, currency}` |
| Percentage | decimal, 1.0 = 100% | document basis in field name (`fee_pct`) | string decimal |
| BasisPoints | integer/decimal bps | use for slippage scenarios | number |
| Duration | ISO-8601 duration | | string |
| Hash | SHA-256 hex | lowercase, 64 chars | string |
| Regime label | enum per G9: `vol_high vol_low trend_pos trend_neg volume_high volume_low` | descriptive ex-post only; never predictive claim | string |

Primitive-obsession rule: `market`, `venue`, `timeframe`, `instrument` are never bare strings inside domain logic — they are validated value objects constructed at boundaries.

## 2. Core entities (identity, lifecycle, invariants)

### Dataset (`DS-`)
- Fields: id, source, source_urls[], raw_file_hashes[], normalization_code_commit, normalized_hash, schema_version, coverage_start/end, instruments[], timeframes[], timezone (`UTC` invariant), missing_intervals_report_ref, quality_report_hash, license_note, created_at.
- Lifecycle: `DRAFT → FROZEN` (frozen is immutable; a fix = new dataset id + supersedes link).
- Invariant: FROZEN dataset regenerable to identical `normalized_hash` from manifest + code commit.

### Source (`SRC-`) / License record
- Fields per `specs/STRATEGY_INGESTION_AND_REPRODUCTION_WORKFLOW_V1.md` source record, plus `license_evidence_url`, `license_class` (permissive|copyleft|proprietary|unclear), `reuse_allowed` (yes|adapted|no|unclear).
- Invariant: `profit_claims_inherited = false` always.

### CanonicalStrategySpec (`STRAT-`) and StrategyVersion (`SV-`)
- Spec fields: family, inputs[], indicators[{name, params}], entry/exit rule trees (`all:`/`any:` boolean composition over comparisons), position_sizing, risk (stop/take-profit/trailing as declarative fields), assumptions[], ambiguities[], source_refs[], license_ref.
- StrategyVersion = immutable snapshot of spec + resolved parameters + spec_hash. Any change ⇒ new SV.
- Invariant: an SV referenced by any experiment is permanently immutable.

### Hypothesis (`HYP-`)
- Fields: statement, origin, source_refs[], creator (type + AGT/MDL refs if agent), prior_evidence[], contradictions[], target market/instrument/timeframe, status (`OPEN|SUPPORTED|REJECTED|SUPERSEDED`), confidence (low|med|high), linked SV/EXP ids.

### Experiment (`EXP-`) and Run (`RUN-`)
- Experiment = declared search: hypothesis_ref, SV or SV-space, dataset_ref, engine + version, parameter_space, fee/slippage scenario set, split policy ref, trial_count, selection_procedure.
- Run = one trial: params, seed, metrics, artifact refs (trades, equity, logs), runtime, environment manifest hash, status (`COMPLETED|FAILED|ABORTED`), failure_reason.
- Invariants: **all trials retained**; a "winner" must reference its search population (G10); FAILED runs are evidence, not garbage.

### ValidationPackage (`VAL-`)
- Fields: SV ref, dataset ref, gate results G1..G12 each `{status: PASS|FAIL|WARN|NOT_RUN, evidence_refs[]}`, cost grid table ref, oos/walk-forward/robustness/regime report refs, hard_fail flag.
- Invariant: any hard-fail gate ⇒ package cannot support promotion regardless of scores.

### Evidence record (`EV-`) — the Trading Evidence Registry row
- As in `specs/EXPERIMENT_LINEAGE_PROTOTYPE_SPEC_V1.md` Test C: evidence_id, hypothesis_id, strategy_version_id, market, instrument, timeframe, run_ref (external tracker id), dataset_ref, validation_state, approval_state.
- Invariant: run_ref/dataset_ref are **foreign references by stable public ID**, never by tracker-internal DB keys (replaceability gate).

### Approval (`APR-`)
- Identity: strategy × market × instrument × timeframe × config(SV) × environment (× risk tier reserved).
- States: `NOT_ELIGIBLE, RESEARCH, VALIDATION, PAPER_APPROVED, PAPER_ACTIVE, LIMITED_LIVE_REVIEW, LIMITED_LIVE_APPROVED, LIVE_APPROVED, PAUSED, DEGRADED, RETIRED` (superset of North Star §9.7 list; mapping documented in AD §Y).
- Transition rules: only via recorded gate evidence + (for any LIVE state) human decision record. Machine may propose; only operator approves LIVE-family transitions.

### ResearchAsset (`RA-`)
- Fields: title, question, creator agent/model/prompt refs, sources[], date, cost, quality score refs, human_review status, dependencies[], consumers[], freshness (`CURRENT|AGING|STALE|CONTRADICTED|SUPERSEDED`), contradiction refs, supersession chain.

### Dictionary concept (`CON-`)
- Fields: canonical name, stable id, abbreviations[], aliases[], definition, category, market_contexts[], venue_variants[], related[], sources[], examples[], evidence_status, freshness.
- Invariant: dictionary meaning ≠ strategy configuration (North Star §9.3); concepts never store strategy parameter values.

### AI entities
- ModelSnapshot (`MDL-`): provider, exact model id, snapshot/version, first_seen, status, pricing at capture.
- AgentConfiguration (`AGT-`): role, MDL ref, prompt version (`PRM-`), tools[], context package hash, reasoning settings, budget, workflow, output schema ref.
- BenchmarkRun (`BMK-`): mode (controlled|best_config|longitudinal), task id, AGT ref, corpus hash, metrics, cost, latency, raw+normalized output refs, evaluator results.

### Learning (`LRN-`)
- Fields: category, statement, evidence EXP/VAL refs[], contradiction refs[], confidence, freshness, invalidation trigger.
- Invariant: a learning with zero evidence refs is invalid at write time.

## 3. Commands, queries, events (planning contracts)

MVP is a modular monolith: "events" are transactional outbox rows / append-only log entries, not a message broker (see AD §R). Contracts below bind names and payloads, not transport.

### Commands (imperative, validated, idempotent by client key)
- `FreezeDataset{source_manifest} → DS-`
- `RegisterSource{source_record} → SRC-`
- `CreateStrategySpec{spec} → STRAT-` / `CreateStrategyVersion{strat, params} → SV-`
- `DeclareExperiment{...} → EXP-` / `ExecuteRun{exp, trial} → RUN-`
- `AssembleValidationPackage{sv, gates} → VAL-`
- `RecordEvidence{...} → EV-` / `ProposeApprovalTransition{apr, target, evidence} → pending`
- `RecordBenchmarkRun{...} → BMK-` / `WriteLearning{...} → LRN-`

### Queries (read-only, dashboard + agents)
- `GetLineage(any_id)` → full ancestry/descendants chain
- `ListRuns(filter)` / `CompareRuns(ids)` / `GetValidationStatus(sv, context)`
- `SearchConcepts(term)` / `GetResearchAssets(filter, freshness)`
- `GetEngineComparison(baseline)` / `GetOpenAmbiguities()`

### Events (append-only, consumed by dashboard/reporting/memory)
- `DatasetFrozen, RunCompleted, RunFailed, ValidationGateEvaluated, EvidenceRecorded, ApprovalTransitioned, BenchmarkCompleted, ContradictionDetected, FreshnessDegraded`
- Each: `{event_id, occurred_at, entity_ref, payload, idempotency_key}`; ordering per entity; global ordering not guaranteed.

## 4. Adapter contracts

### EngineAdapter (one per engine; the parity boundary)
```text
prepare(dataset: DS, sv: SV, scenario: FeeSlippageScenario) -> EnginePlan
run(plan) -> EngineRawResult        # engine-native
normalize(raw) -> NormalizedResult  # canonical trades/equity/metrics
capabilities() -> CapabilityReport  # what the engine cannot express (explicit gaps)
version_manifest() -> {engine, version, commit, env_hash}
```
- NormalizedResult: trades[{ts_signal, ts_order, ts_fill, side, price, qty, fee}], equity_curve[], metrics{}, warnings[], semantic_notes[].
- Unsupported feature ⇒ explicit `CapabilityGap`, never silent approximation.

### ConverterContract (per `AD.md` §L)
```text
convert(source_artifact, context) -> {target, losses[], ambiguities[], provenance}
```
- Declared lossy/lossless per converter; ambiguity behavior = record-and-surface, never guess silently; every conversion output carries source hash + converter version.

### LineageAdapter (MLflow/DVC or alternative; decided by prototype)
```text
start_run(context) -> run_ref ; log_params/metrics/artifacts ; end_run
snapshot_dataset(path) -> dataset_ref ; restore(dataset_ref) -> path
```
- Constraint: domain layer stores only public stable refs (run_ref/dataset_ref as strings).

## 5. Job contracts

`Job{job_id, type, inputs(hashes/ids only), status, attempts, max_attempts, timeout, resource_class, checkpoint_ref?, artifacts[], parent_job?}`
- Types (MVP): `dataset_freeze, engine_run, parity_compare, validation_gate, ingestion_item, benchmark_task, report_build`.
- Semantics: at-least-once execution + idempotent effects (inputs are content-addressed; a rerun with identical inputs may reuse cached artifacts). Cancellation is cooperative. Failures preserve partial artifacts + logs.

## 6. Artifact contracts

Every artifact directory contains `manifest.json`:
```json
{"artifact_id":"...","produced_by":"RUN-...|job-...","code_commit":"...",
 "input_refs":["DS-..."],"files":[{"path":"trades.parquet","sha256":"..."}],
 "created_at":"...","schema_version":1}
```
- Large binaries stay out of Git; hashes and manifests stay in.
- Report artifacts (`*.md`) always link to machine-readable siblings (`*.json`).

## 7. API contracts (dashboard, MVP)

Read-only HTTP+JSON, versioned path prefix `/api/v1/`, resources mirroring queries in §3. No write endpoints in MVP dashboard. Contract tests pin response schemas (see TEST_MASTER_PLAN §contract).

## 8. Versioning & compatibility rules

- Additive changes: allowed within a schema_version.
- Breaking changes: bump schema_version, keep a reader for N-1, record in decision log.
- Entity IDs never change meaning; supersession is the only correction mechanism for evidence-bearing records.
- External tool upgrade (engine, tracker) requires re-running one pinned golden run and comparing normalized output before adoption (parity regression test).
