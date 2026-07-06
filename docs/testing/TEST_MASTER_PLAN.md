# Test Master Plan — Trading Intelligence OS

Status: Approved planning baseline v1
Date: 2026-07-06
Rule inherited from SSOT: truth over completion theater. A test that cannot fail is not a test. Fabricated or unverifiable results are recorded as UNVERIFIED, never as PASS.

## 1. Test taxonomy and ownership

| Layer | What it proves | Owner module | When |
|---|---|---|---|
| Unit | pure logic correctness | each module | every commit |
| Property-based | invariants over generated inputs (OHLC invariants, decimal round-trips, ID parsing, rule-tree evaluation) | core_types, dataset, strategy, validation | every commit |
| Contract | ports honored (EngineAdapter, LineageAdapter, ConverterContract, dashboard API schemas) | adapter owners | every commit + on dependency upgrade |
| Adapter integration | real tool behind port produces normalized output on mini-fixture | engine_adapters, lineage_adapter | nightly/local on demand |
| Converter parity | external spec → canonical spec → engine implementation preserves semantics | ingestion, engine_adapters | per converter change |
| Golden | pinned inputs → byte/semantic-identical outputs (normalized results, validation reports, dataset hashes) | dataset, parity, validation, reporting | every commit (fast goldens), nightly (slow) |
| Deterministic replay | same run inputs ⇒ same trades/equity within documented tolerance (gate G1 as a test) | experiment, engines | per engine, per upgrade |
| Integration (workflow) | freeze→run→validate→evidence chain on fixtures | services | nightly |
| End-to-end | MVP workflows 1–8 of `MVP_SCOPE.md` §6 on fixture data through the real surfaces | program level | per stage exit |
| Engine parity | WS4 cross-engine semantic comparison suite | parity | bake-off + per engine upgrade |
| Dataset integrity | quality gates of `CANONICAL_BAKEOFF_DATASET_V1.md` as executable checks | dataset | per freeze |
| Leakage | G4 fixtures: known-leaky strategy MUST be caught; feature-availability timestamp audit | validation | every commit |
| Backtest correctness | hand-computed micro-fixtures (5–10 bars, known trades/fees/P&L) per engine adapter | engine_adapters | every commit |
| Failure injection | data gaps, corrupt files, engine crash mid-run, tracker unavailable, provider timeout | jobs, adapters | nightly |
| Security | secret-scan of artifacts/repo, dependency audit, live-state-unreachable test, sandbox policy for ingested code | security_ops | every commit + weekly audit |
| AI evaluation | benchmark harness fixture-freeze tests, no-network controlled mode, schema-validity of outputs | ai_eval | per harness change |
| Model/prompt regression | longitudinal reruns (Mode C) on frozen tasks after provider/model change | ai_eval | on model change event |
| Performance | runtime/memory budget checks for dataset ops and engine runs on reference hardware | program | per stage exit |
| Architecture | forbidden-dependency checks per MODULE_CATALOG dependency law | program | every commit |

Chaos testing: rejected for MVP (single laptop, no distributed system). Revisit at S3.

## 2. Fixtures and test datasets

- `fixtures/micro/` — 5–100 bar hand-verifiable OHLCV series with known indicator values and expected trades (source of truth: spreadsheet-style derivation checked into the fixture folder).
- `fixtures/mini/` — 1–3 months of real frozen BTCUSDT 1h data (subset of DS-CRYPTO-SPOT-BAKEOFF-V1, hash-pinned) for adapter integration.
- `fixtures/leaky/` — deliberately contaminated variants (future close in feature, shifted timestamps, forward-filled gaps) that gates MUST reject.
- `fixtures/ai_corpus/` — frozen benchmark corpus per `benchmarks/ai_agent/FROZEN_BENCHMARK_SUITE_V1.md`, hash-manifested.
- Deterministic seeds: every stochastic component takes an explicit seed; test config pins seeds; seedless randomness in domain code is an architecture-test failure.

## 3. Golden artifacts

Golden files live in `tests/golden/**` with a manifest (hash, producing commit, tolerance policy). Update procedure: regenerate → diff review → decision-log note if semantics changed. Silent golden updates are forbidden.

## 4. Environment matrix

| Env | Purpose | Gate |
|---|---|---|
| Local macOS (operator laptop, ARM) | primary dev + prototype evidence | all fast suites green |
| Local Docker (linux/amd64 or arm64) | engine isolation (LEAN/.NET, Hummingbot) + reproducibility check | adapter suites green in container |
| CI (if/when added — S2 decision) | regression safety net | fast suites + goldens |

CI provider selection is deferred to S2 (see RESEARCH_GAP_MATRIX RG-14); local one-command gate is mandatory from WS1.

## 5. Gates by stage

### Local gate (every work session, one command)
lint + typecheck + unit + property + fast goldens + architecture tests. Must run < 5 min.

### Prototype gates (S1 exit — mirror vertical-slice exit criteria)
1. Dataset double-regeneration hash equality (EG-1).
2. Per-engine deterministic rerun parity (G1) on ≥2 engines.
3. Parity suite produces semantic diagnosis for every numeric divergence.
4. Leakage fixtures rejected by G4 implementation.
5. Fee/slippage grid completeness check (all 6 mandatory scenarios present in every economic report).
6. Lineage fresh-checkout restore test.
7. AI harness fixture-freeze + null-provider end-to-end test.
8. Secret-scan clean; live-state-unreachable test green.

### MVP gates (S2 exit)
All prototype gates + E2E workflows 1–8 + API contract suite + performance budgets + docs freshness check (every doc's `Date:` vs dependency changes).

### Paper gates (S3)
Divergence tracking tests (backtest-vs-paper reconciliation on same window), operational failure drills (feed loss, engine crash, stale data), kill-switch drill (paper-level), venue contract tests.

### Live-readiness gates (S4 — NOT AUTHORIZED)
Defined only as placeholders: real-credential isolation tests, withdrawal-capability absence verification, human sign-off records. Do not implement in MVP.

## 6. Tooling candidates (Provisional — final selection at S1 WS1 with evidence)

- Python: pytest + hypothesis (property) + coverage; ruff (lint) + a type checker (mypy or pyright); pre-commit hook running the local gate. These are ecosystem-default, low-risk choices; deviation requires decision-log entry.
- Architecture tests: import-linter (or equivalent AST check) enforcing MODULE_CATALOG dependency law.
- Secret scanning: gitleaks or detect-secrets (verify maintenance at WS1).
- Container: Docker Compose for engine isolation.

## 7. AI-specific testing rules

- LLM-as-judge requires calibration set + periodic human spot review (per `specs/AI_AGENT_EVALUATION_BLUEPRINT_V1.md` safeguards); same-model self-judging insufficient for critical tasks.
- Controlled mode runs with network disabled; violation is a harness bug.
- Raw profit is never a model-skill metric (D-021).

## 8. Test-debt rule

A known-failing test is either fixed, or quarantined with an open item in `MISSING_AND_OPEN_ITEMS.md` + owner + trigger. Silent skips are forbidden; the local gate counts quarantined tests and prints them.
