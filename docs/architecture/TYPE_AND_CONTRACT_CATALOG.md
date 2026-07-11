# Type and Contract Catalog — Trading Intelligence OS

Status: S2 architecture-lock specification v1. Language-neutral except for the approved JSON boundary rules below.
Date: 2026-07-10
Rule: implementation must not begin from this file alone; it binds names, semantics, and wire invariants, not concrete storage schemas.

## 0. Conventions

- IDs are opaque, prefixed, human-scannable strings: `DS-`, `STRAT-`, `SV-`, `HYP-`, `EXP-`, `RUN-`, `LAB-`, `SCORE-`, `VAL-`, `EV-`, `APR-`, `SRC-`, `RA-`, `CON-`, `MDL-`, `AGT-`, `PRM-`, `BMK-`, `LRN-`, `JOB-`, `SIG-`, `ORD-`, `FILL-`, `POS-`, `ACCT-`, `PF-`, `RISK-`, `ANN-`. IDs never encode mutable facts, storage locations, engine IDs, or tracker keys.
- All timestamps are UTC ISO-8601 and serialize with a literal `Z` (`2026-07-10T00:00:00Z`). Offsets other than `Z` and naive datetimes are rejected at JSON boundaries.
- Money/price/quantity are **decimal** types with explicit precision; binary floats are forbidden in accounting paths (permitted inside vectorized research computation, but results crossing a contract boundary re-quantize to decimal with documented precision).
- Every top-level JSON resource/event carries integer `schema_version`; schema versions are contract versions, not application versions. All decimal-valued JSON fields (including money, price, quantity, percentages, basis points, metrics, and OHLCV) are base-10 strings; JSON `NaN` and infinities are forbidden. Enums serialize as the exact uppercase tokens declared here.
- Every entity carries `created_at`, `creator_type` (`HUMAN|AGENT|SYSTEM`), provenance links, and an environment tag. Evidence-bearing records are append-only; corrections are new records referencing the old (supersession, never mutation).
- S2 accepts `environment=HISTORICAL_RESEARCH`, `execution_authority=NONE`, `venue_connection=NONE`, `paper_orders=DISABLED`, and `live_orders=DISABLED` only. `DEMO`, `PAPER`, and `LIVE` are reserved vocabulary, not reachable S2 states.

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
| BasisPoints | decimal bps | use for slippage scenarios | string decimal |
| Duration | ISO-8601 duration | | string |
| Hash | SHA-256 hex | lowercase, 64 chars | string |
| Regime label | enum per G9: `vol_high vol_low trend_pos trend_neg volume_high volume_low` | descriptive ex-post only; never predictive claim | string |

Primitive-obsession rule: `market`, `venue`, `timeframe`, `instrument` are never bare strings inside domain logic — they are validated value objects constructed at boundaries.

## 2. Core entities (identity, lifecycle, invariants)

### Dataset (`DS-`)
- Fields: id, source, source_urls[], raw_file_hashes[], normalization_code_commit, normalized_hash, schema_version, coverage_start/end, instruments[], timeframes[], timezone (`UTC` invariant), missing_intervals_report_ref, quality_report_hash, license_note, created_at.
- Lifecycle: `DRAFT → FROZEN` (frozen is immutable; a fix = new dataset id + supersedes link).
- Invariant: FROZEN dataset regenerable to identical `normalized_hash` from manifest + code commit.

### ResearchSource (`SRC-`) / License record
- Fields: id, bibliographic identity/title, source kind, canonical URL and/or DOI, publication date, authors[], access notes, license notes/evidence URL, license class (`PERMISSIVE|COPYLEFT|PROPRIETARY|UNCLEAR`), reuse allowed (`YES|ADAPTED|NO|UNCLEAR`), claim summary, hypothesis families[], implementation assumptions[], ambiguities[], reviewed_at, supersedes/superseded_by refs[], reproduction status (`UNREVIEWED|HYPOTHESIZED|SPECIFIED|REPRODUCED|FAILED|SUPERSEDED`), and provenance.
- Invariants: `profit_claims_inherited=false`; publication and original-sample performance are source claims, never local proof. Unsupported or ambiguous claims remain labeled.

### CanonicalStrategySpec (`STRAT-`) and StrategyVersion (`SV-`)
- Spec fields: family, inputs[], indicators[{name, params}], entry/exit rule trees (`all:`/`any:` boolean composition over comparisons), position_sizing, risk (stop/take-profit/trailing as declarative fields), assumptions[], ambiguities[], source_refs[], license_ref.
- StrategyVersion = immutable snapshot of spec + resolved parameters + spec_hash. Any change ⇒ new SV.
- Invariant: an SV referenced by any experiment is permanently immutable.

### Hypothesis (`HYP-`)
- Fields: id, falsifiable statement, source_refs[], claim locator/summary, creator (type + AGT/MDL refs if agent), implementation assumptions[], ambiguities[], prior evidence refs[], contradiction refs[], target market/instrument/timeframe, status (`OPEN|SPECIFIED|UNDER_TEST|SUPPORTED|REJECTED|SUPERSEDED`), reproduction status, and linked STRAT/SV/EXP/LAB ids.
- Invariant: `SUPPORTED` requires retained local evidence; source authority alone cannot advance status.

### Experiment (`EXP-`) and Run (`RUN-`)
- Experiment = declared search: hypothesis_ref, SV or SV-space, dataset_ref, engine + version, parameter_space, fee/slippage scenario set, split policy ref, trial_count, selection_procedure.
- Run = one trial: params, seed, metrics, artifact refs (trades, equity, logs), runtime, environment manifest hash, status (`COMPLETED|FAILED|ABORTED`), failure_reason.
- Invariants: **all trials retained**; a "winner" must reference its search population (G10); FAILED runs are evidence, not garbage.

### ResearchLabBatch (`LAB-`)
- Fields: id, schema_version, command/version, canonical input hash, source/hypothesis/spec/SV refs[], frozen dataset refs[], declared parameter families and trial bound, engine roles/versions, cost scenarios, split/seed policy, allowlisted steps[], status (`PENDING|RUNNING|COMPLETED|FAILED|ABORTED|REUSED`), started_at/completed_at, experiment/run refs[], scorecard refs[], artifact/manifest refs[], failure/blocker refs[], `environment=HISTORICAL_RESEARCH`, `execution_authority=NONE`, `venue_connection=NONE`, `paper_orders=DISABLED`, and `live_orders=DISABLED`.
- Identity: `LAB-<content-hash>` is derived from canonical immutable inputs; mutable runtime state is not part of identity.
- Invariants: identical complete inputs reuse the complete batch and artifact refs without recomputation; partial/failed batches remain addressable and are never overwritten; every declared trial has a retained terminal record; no automatic winner selection.

### Scorecard (`SCORE-`)
- Fields: id, subject ref (LAB/EXP/SV), dimension results[] each `{dimension, status: PASS|FAIL|WARN|NOT_RUN, value?, evidence_refs[], blockers[]}`, validation_state, promotion_eligible, created_at, provenance.
- Required dimensions: data integrity/freshness; after-cost economics; drawdown/loss severity; parameter-neighborhood robustness; temporal/walk-forward stability; regime stability; baseline superiority; multiple-testing/selection-bias control; cross-engine reproduction; operational/evidence completeness.
- Invariants: dimensions remain independent; there is no blended/global score; `NOT_RUN` is a blocker, never zero; any hard fail or missing required dimension forces `promotion_eligible=false`.

### ValidationPackage (`VAL-`)
- Fields: SV ref, dataset ref, gate results G1..G12 each `{status: PASS|FAIL|WARN|NOT_RUN, evidence_refs[]}`, cost grid table ref, oos/walk-forward/robustness/regime report refs, hard_fail flag.
- Invariant: any hard-fail gate ⇒ package cannot support promotion regardless of scores.

### Evidence record (`EV-`) — the Trading Evidence Registry row
- As in `specs/EXPERIMENT_LINEAGE_PROTOTYPE_SPEC_V1.md` Test C: evidence_id, hypothesis_id, strategy_version_id, market, instrument, timeframe, run_ref (external tracker id), dataset_ref, validation_state, approval_state.
- Invariant: run_ref/dataset_ref are **foreign references by stable public ID**, never by tracker-internal DB keys (replaceability gate).

### Approval (`APR-`)
- Identity: strategy × market × instrument × timeframe × config(SV) × environment (× risk tier reserved).
- States: `NOT_ELIGIBLE, RESEARCH, VALIDATION, PAPER_APPROVED, PAPER_ACTIVE, LIMITED_LIVE_REVIEW, LIMITED_LIVE_APPROVED, LIVE_APPROVED, PAUSED, DEGRADED, RETIRED` (superset of North Star §9.7 list; mapping documented in AD §Y).
- Record fields: id, contextual identity, current state, proposed target?, evidence/validation/risk refs[], decision (`NONE|APPROVE|REJECT`), decided_by/at?, expiry/review rule, and environment.
- Transition rules: only via recorded gate evidence + required human decision. In S2, records are inert read projections and the only reachable states are `NOT_ELIGIBLE`, `RESEARCH`, and `VALIDATION`; paper/demo/live transition commands do not exist.

### Inert trading-domain contracts

These records normalize historical engine output and power read-only charts/console projections. They are not venue models and expose no client, routing method, mutation command, credential, or executable callback.

- `Market{market, venue_family, instrument, timeframe, dataset_ref}` is the validated historical context. `MarketBar{market, open_time, close_time, open, high, low, close, volume}` and `MarketQuote{market, observed_at, bid_price, bid_quantity, ask_price, ask_quantity}` carry observations. Prices/quantities are decimal strings on JSON boundaries; time ordering, bid/ask, and OHLC invariants are validated.
- `Signal{signal_id, sv_ref, run_ref, instrument, timeframe, observed_at, side: BUY|SELL|FLAT, rationale_code, provenance}`. A signal is evidence, never an order.
- `BracketLevels{take_profit?, stop_loss?, trailing_distance?}` contains inert Price/Percentage values only.
- `Order{order_id, intent: {source_signal_ref?, run_ref, instrument, side, order_type, quantity, limit_price?, stop_price?, bracket_levels?}, observed_at, state=INERT, environment=HISTORICAL_RESEARCH, execution_authority=NONE}` holds an inert order intent and state. No venue order ID or submit/cancel operation is valid in S2.
- `Fill{fill_id, order_ref, run_ref, instrument, filled_at, price, quantity, fee: Money, liquidity_role?, provenance}` is a retained historical normalized result, not confirmation of venue activity.
- `Position{position_id, run_ref, instrument, as_of, quantity, average_price?, realized_pnl: Money, unrealized_pnl: Money, status: FLAT|OPEN|CLOSED}`, `Account{account_id, run_ref, as_of, balances: Money[], environment=HISTORICAL_RESEARCH, synthetic=false}`, and `Portfolio{portfolio_id, account_ref, run_ref, as_of, cash: Money[], positions[], equity: Money[], environment=HISTORICAL_RESEARCH}` are derived historical projections. `Account` is not a wallet and no account/portfolio mutation exists.
- `RiskDecision{risk_id, subject_ref, as_of, decision: PASS|BLOCK|NOT_EVALUATED, rule_results[], evidence_refs[], independent=true}` can block eligibility but cannot authorize execution.
- `ChartAnnotation{annotation_id, chart_ref, instrument, timeframe, timestamp, kind: SIGNAL|FILL|TAKE_PROFIT|STOP_LOSS, source_ref, price?, label?}` must point to a retained typed record; annotations cannot create or mutate trading state.

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
- `RegisterResearchSource{source_record} → SRC-`
- `CreateStrategySpec{spec} → STRAT-` / `CreateStrategyVersion{strat, params} → SV-`
- `DeclareExperiment{...} → EXP-` / `ExecuteRun{exp, trial} → RUN-` (internal bounded batch step in S2; not an HTTP or free-form CLI trigger)
- `AssembleValidationPackage{sv, gates} → VAL-`
- `RecordEvidence{...} → EV-` / `ProposeApprovalTransition{apr, target, evidence} → pending` (S2 targets are limited to `RESEARCH|VALIDATION`)
- `RecordBenchmarkRun{...} → BMK-` / `WriteLearning{...} → LRN-`
- `RunResearchLabBatch{immutable_input_refs, bounds, allowlisted_steps} → LAB-` is an offline local command. An identical completed request returns `REUSED` with the existing refs. This is the only S2 Research Lab trigger until idempotency is proven; it is not an HTTP command.
- There is no order submit/cancel/replace command, venue-connect command, portfolio mutation, approval-decision HTTP command, demo/paper/live command, or credential-bearing command in S2.

### Queries (read-only, dashboard + agents)
- `GetLineage(any_id)` → full ancestry/descendants chain
- `ListRuns(filter)` / `CompareRuns(ids)` / `GetValidationStatus(sv, context)`
- `SearchConcepts(term)` / `GetResearchAssets(filter, freshness)`
- `GetEngineComparison(baseline)` / `GetOpenAmbiguities()`
- `GetResearchLabBatch(id)` / `ListResearchLabBatches(filter)` / `GetScorecard(id)` / `ListResearchSources(filter)` / `GetCandidateEvidence(hypothesis)`
- `GetMarketWorkspace(run, instrument, timeframe)` / `GetTradingDomainProjection(run)` / `GetAutomationStatus()`

### Events (append-only, consumed by dashboard/reporting/memory)
- `DatasetFrozen, ResearchSourceRegistered, HypothesisRecorded, ResearchLabBatchStarted, ResearchLabBatchCompleted, ResearchLabBatchFailed, ResearchLabBatchReused, RunCompleted, RunFailed, ScorecardRecorded, ValidationGateEvaluated, EvidenceRecorded, ApprovalTransitioned, BenchmarkCompleted, ContradictionDetected, FreshnessDegraded`
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

### LineageAdapter (MLflow + DVC selected behind ports)
```text
start_run(context) -> run_ref ; log_params/metrics/artifacts ; end_run
snapshot_dataset(path) -> dataset_ref ; restore(dataset_ref) -> path
```
- Constraint: domain layer stores only public stable refs (run_ref/dataset_ref as strings).
- Retention/access: failed and completed refs remain restorable through S2; local stores are operator-only and loopback-only. Backup/restore and migration expectations are canonical in `AD.md` §P.

## 5. Job contracts

`Job{job_id, schema_version, type, inputs(hashes/ids only), idempotency_key, status, created_at, started_at?, completed_at?, attempts, max_attempts, timeout, resource_class, checkpoint_ref?, artifact_refs[], parent_job?, failure_ref?, environment=HISTORICAL_RESEARCH}`
- Allowlisted S2 types: `research_lab_batch, research_source_refresh, validation_gate, report_build, data_freshness`. Engine runs and parity comparisons occur only as bounded steps of an allowlisted ResearchLabBatch; no arbitrary command payload is accepted.
- Status: `PENDING|RUNNING|COMPLETED|FAILED|CANCELLED|REUSED`.
- Semantics: local DB-table jobs only after `RunResearchLabBatch` proves idempotent; at-least-once execution + idempotent effects; bounded attempts/timeouts/concurrency; cooperative cancellation; failures preserve partial artifacts + logs. No broker or distributed worker.

## 6. Artifact contracts

Every artifact directory contains `manifest.json`:
```json
{"artifact_id":"...","produced_by":"RUN-...|JOB-...|LAB-...","code_commit":"...",
 "input_refs":["DS-..."],"files":[{"path":"trades.parquet","sha256":"..."}],
 "created_at":"...","schema_version":1}
```
- Large binaries stay out of Git; hashes and manifests stay in.
- Report artifacts (`*.md`) always link to machine-readable siblings (`*.json`).

## 7. API contracts (dashboard, MVP)

Read-only HTTP+JSON, versioned path prefix `/api/v1/`, limited to the Research Lab, candidates/sources, comparisons, historical market workspace, automation status, local registry/report search, stage-gate readiness, and inert trading-domain read models in §3. Responses obey §0 serialization and carry `schema_version`. GET/HEAD/OPTIONS are the general rule, with **exactly one audited write exception per D-038**: `POST /api/v1/workspace-actions/decision` — operator-driven workspace-decision recording only, loopback-only, payload validated against a fixed task/option allowlist, append-only to `artifacts/human_decisions/workspace_decisions.jsonl`, and test-pinned as the sole write path. No other POST/PUT/PATCH/DELETE endpoint, no manual-trigger endpoint, order endpoint, approval transition endpoint, venue control, stage-gate transition, or demo/paper/live control exists; expanding the exception's payloads, write targets, or methods requires a new decision gate. Contract tests pin response schemas and prohibited methods (see TEST_MASTER_PLAN §contract).

## 8. Versioning & compatibility rules

- Additive changes: allowed within a schema_version.
- Breaking changes: bump schema_version, keep a reader for N-1, record in decision log.
- Entity IDs never change meaning; supersession is the only correction mechanism for evidence-bearing records.
- External tool upgrade (engine, tracker) requires re-running one pinned golden run and comparing normalized output before adoption (parity regression test).
