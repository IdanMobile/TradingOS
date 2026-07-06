# AD — Architecture Decisions: Trading Intelligence OS

Status: Canonical architecture document v1 (2026-07-06).
Maturity labels used throughout: **[APPROVED]** (backed by decision log / this planning pass with evidence), **[PROVISIONAL]** (best current direction; may change on prototype evidence), **[UNRESOLVED]** (explicitly awaiting evidence — the required proof is named).
Authority: subordinate to the SSOT (`handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md`) and `TRADING_OS_NORTH_STAR.md`. This document does not authorize implementation; it prevents rediscovery.
Evidence base: package research (2026-07-05) + refreshed web research (2026-07-06) in `research/EXISTING_CAPABILITY_REGISTRY.md` (cited as REG §n) and `research/RESEARCH_GAP_MATRIX.md` (RG-nn).

---

## A. Executive architecture summary

- **Purpose**: a self-measuring machine for discovering, rejecting, validating, approving, monitoring, degrading, and retiring trading edges — measuring its own tools, models, agents, and research assets along the way (North Star §2).
- **Philosophy**: composable reuse around a custom evidence spine. Engines, trackers, indicator libraries, dashboards are replaceable commodities behind ports; the durable custom core is the Trading Evidence Registry + approval/provenance semantics (North Star §15, D-009, D-016).
- **MVP boundary**: Crypto Spot, BTCUSDT/ETHUSDT, 5m/15m/1h, research→validation→(paper) pipeline, read-only evidence dashboard. See `docs/product/MVP_SCOPE.md`.
- **Long-term boundary**: multi-market (perps, US equities/ETFs), paper→limited-live under human gates, full 27-page console, evidence-routed AI.
- **Non-goals**: universal bot, single score, AI-in-live-path, architecture for its own sake (North Star §17).
- **Core risks**: overfitting theater, cost-model optimism, leakage, engine semantic mismatch, AI hallucination provenance, single-operator maintenance ceiling (North Star §18; red team in `audits/RED_TEAM_PLAN_REVIEW.md`).

## B. Architecture principles

1. **Reuse before build** [APPROVED, D-002] — custom code requires a failed reuse case (Custom Build Gate §AL).
2. **Modular monolith over services** [PROVISIONAL] — one deployable process + per-engine isolated environments. Rationale: single operator, laptop-first, no scaling driver; services add ops burden with zero current benefit. Proof that changes it: measured resource contention in S1 (RG-15).
3. **Ports and adapters + dependency inversion** [APPROVED as design law] — MODULE_CATALOG dependency rules; enforced by architecture tests.
4. **Deterministic vs non-deterministic boundary** [APPROVED] — §H; AI never inside deterministic execution paths.
5. **Immutable evidence, append-only history** [APPROVED] — supersession over mutation for all evidence-bearing records (type catalog §0).
6. **Replaceable externals** [APPROVED] — domain stores only public stable refs to trackers/engines (lineage prototype "replaceability" gate).
7. **Idempotency & reproducibility** [APPROVED] — content-addressed inputs; jobs at-least-once + idempotent effects (type catalog §5).
8. **Point-in-time correctness** [APPROVED] — no feature availability before its timestamp; G4 gates; time-aware corpora for AI benchmarks (D-021).
9. **Fail-closed** [APPROVED for anything touching capital or approval state; fail-open permitted only for read-only views].
10. **No strategy-owned risk authority** [APPROVED, North Star §4.3]; **no hidden AI decisions** [APPROVED, §H/§T]; **no live execution without human approval** [APPROVED].

## C. System context

Actors/systems: Operator (sole human; approver of HG gates) · Coding agent (R7, SSOT-bound) · AI providers (Anthropic/OpenAI/Google — REG §7; via provider adapters only) · Research/strategy sources (untrusted input; ingestion workflow) · Exchanges (Binance/Kraken/OKX/Coinbase — data + future venue; REG §6) · Market-data vendors (deferred tiers, D-018) · Paper environments (engine dry-run/testnet/demo) · Future live environments (S4, not authorized) · Local machine (macOS ARM; primary) · Optional cloud (none in MVP) · Storage (local FS + Git + operational DB).

Trust boundaries: (1) everything fetched from the internet is untrusted data — prompt-injection surface (§AB); (2) provider APIs get keys with minimal scope, never exchange credentials; (3) exchange credentials: none in MVP beyond optional testnet/demo via intake gate.

## D. Bounded contexts

Consolidated from the mandate's candidate list — merged where cohesion demands, deferred where MVP doesn't touch them. [APPROVED as boundaries; internals PROVISIONAL]

| Context | Owns | MVP | Notes on merges |
|---|---|---|---|
| **Market Data** | datasets, quality, freeze identity | thin (WS2) | "Data Center" IA page maps here |
| **Strategy** | specs, versions, families | yes | includes Strategy Definition + Versioning (split was artificial) |
| **Ingestion** | sources, licenses, extraction lifecycle | manual batch | includes Opportunity Discovery *inputs*; discovery ranking deferred to S2+ |
| **Experimentation** | experiments, runs, trials, lineage refs | yes | Backtesting execution lives here; engines are adapters, not a context |
| **Validation** | gates G1–G12, packages | yes | |
| **Evidence & Approval** | EV records, approval state machine, promotion governance | thin | Approval Governance + Evidence merged: approval is meaningless without evidence rows |
| **Knowledge** | dictionary concepts, research assets, sources registry, ecosystem library | thin | Dictionary + Research Assets + Ecosystem Registry merged for MVP (same storage/provenance pattern); split later if scale demands |
| **AI Measurement** | model/agent/prompt registries, benchmarks, cost, routing evidence | harness+fixtures | Task Router deferred to S2 (needs benchmark evidence first) |
| **Memory** | evidence-linked learnings | thin | |
| **Operations** | jobs, schedules, reports, dashboard | thin read-only | Reporting + Ops merged for MVP |
| Paper/Bot Operations | bot lifecycle, divergence tracking | **deferred S3** | modeled, not built |
| Live Trading, Portfolio, Risk Center | — | **deferred S3/S4** | risk exists in MVP only as validation rules + approval preconditions |

Prohibited responsibilities are inherited from MODULE_CATALOG (e.g., Validation never promotes; Strategy never owns risk).

## E. Module map

Canonical in `docs/architecture/MODULE_CATALOG.md` (18 modules, dependency law, tests, MVP status). [APPROVED at boundary level]

## F. Repository architecture

**[PROVISIONAL] Monorepo.** One repository containing the OS package tree, engine adapter envs, specs/docs, and artifact manifests (large artifacts outside Git; hashes inside — SSOT WS1). Rationale: single operator, atomic cross-cutting changes, one SSOT; polyrepo coordination cost has no payer here. Hybrid (separate strategy-content repo) reconsidered at S2 if ingestion volume grows.

```text
repo/
├── (existing planning package files — unchanged locations)
├── src/tios/            # modular monolith per MODULE_CATALOG
│   ├── core_types/  dataset/  strategy/  experiment/  validation/
│   ├── evidence/  approval/  knowledge/  ai_eval/  memory/
│   ├── adapters/{freqtrade,nautilus,lean,hummingbot,vectorbt,lineage}/
│   ├── services/{jobs,ingestion,reporting,dashboard_api}/
│   └── security_ops/
├── engines/<name>/      # isolated per-engine envs (venv/Docker) — RG-04
├── data/{raw,normalized}/   # gitignored payloads, tracked manifests
├── artifacts/           # SSOT WS1 evidence tree (reports tracked; large files hashed)
├── fixtures/            # test datasets per TEST_MASTER_PLAN §2
└── tests/
```
Dependency direction: `src/tios` never imports from `engines/`; engine invocation is subprocess/CLI/API via adapters (also the GPL/AGPL license boundary — REG §1).

## G. Application architecture

MVP applications [PROVISIONAL]: **one CLI** (`tios ...`) for all workstream operations + **one read-only dashboard process** (API+UI). Workers = the jobs module inside the CLI process (no separate daemons). Rejected for MVP: separate research/backtest/validation workers, scheduler daemons, ingestion services — each is a CLI subcommand until S1 telemetry proves otherwise (RG-15). S2 candidates: persistent job worker, scheduled freshness checks.

## H. Deterministic vs non-deterministic boundary [APPROVED — mandatory]

| Class | Examples | Rules |
|---|---|---|
| Deterministic functions | normalization, gates G1–G9, fee math, parity alignment | pure; content-addressed; golden-testable |
| Stateful deterministic workflows | dataset freeze, experiment execution, approval transitions | idempotent jobs; append-only records |
| Stochastic research | parameter sweeps, walk-forward | seeded; seeds recorded; trials retained |
| AI-assisted workflows | extraction, synthesis, critique (R1–R6, R8) | outputs are *proposals* entering via intake commands with provenance; never direct writes |
| Agentic implementation | R7 coding agent | SSOT-bound; verification discipline §6 of SSOT |
| Human approvals | HG-1..5 | recorded decisions; non-delegable |

**AI is forbidden from directly controlling**: gate verdicts, approval transitions, evidence record mutation, dataset freezing, anything in a (future) order path. An AI output can *cause* those only by passing through deterministic validation + (where required) human decision. AI involvement class (North Star §11) is a mandatory field on every strategy; classes E/F are out of scope until explicitly approved (not in MVP/S2/S3).

## I. Trading lifecycle architecture [APPROVED]

State machine (entity: strategy-in-context, i.e., SV × market × instrument × timeframe × environment):

```text
IDEA → HYPOTHESIS → SPEC(canonical) → STRATEGY_VERSION → EXPERIMENT(s) → BACKTESTED
  → VALIDATION_PACKAGE → {REJECTED | PAPER_CANDIDATE}
PAPER_CANDIDATE → (HG) PAPER_APPROVED → PAPER_ACTIVE → {DEGRADED|PAUSED|...}
PAPER_ACTIVE → (S3 evidence + HG-5) LIMITED_LIVE_REVIEW → ... → RETIRED
```
Transition gates: SPEC requires validator PASS; BACKTESTED requires G1–G3; PAPER_CANDIDATE requires VAL package with zero hard-fails + red-team report; every LIVE-family transition requires human record. REJECTED/RETIRED are terminal but queryable (preserve failures, §4.4). Full gate table lives with the approval module spec (type catalog §2).

## J. Strategy architecture [APPROVED]

CanonicalStrategySpec is the framework-neutral center (type catalog §2): provenance (SRC refs, license), family, indicators, entry/exit rule trees, sizing, risk fields, execution assumptions, ambiguities, reproduction status. Engine implementations are *projections* of the spec via adapters; the spec, not any engine file, is the versioned identity. Public-source profitability never imports (D-011).

## K. Engine adapter architecture [PROVISIONAL pending WS3 evidence]

Role-based composition (D-012): candidates Freqtrade (crypto research/dry-run lane), NautilusTrader (execution-grade sim), LEAN (multi-asset portability), Hummingbot (ops/market-making), vectorbt (research accelerator behind overfit controls). All confirmed maintained 2026-07-06 (REG §1).
- Common contract: EngineAdapter port (type catalog §4). Semantic mismatches → CapabilityGap records + parity diagnosis (WS4).
- Version pinning: exact version/commit per run; upgrade requires golden parity rerun (type catalog §8).
- License boundary: Freqtrade GPL-3.0 → subprocess/CLI integration only, no code-linking; Nautilus LGPL-3.0 → import permissible, keep abstraction anyway; backtesting.py AGPL + Backtrader dead → rejected (REG §1).
- Exit strategy per engine: adapter deletion; normalized artifacts remain readable forever (normalization is ours).
- **[UNRESOLVED → WS3]**: which roles are actually selected. No winner is assumed.

## L. Converter architecture [APPROVED as design; implementations S1/S2]

| Converter | Source → Target | Lossy? | Ambiguity behavior | Validation | MVP |
|---|---|---|---|---|---|
| C1 external strategy → canonical spec | paper/Pine/Freqtrade/LEAN/Hummingbot/prose → STRAT | lossy (declared) | record in `ambiguities`, never guess | SKILL_CANONICAL_SPEC_VALIDATOR | WS7 (manual-assisted) |
| C2 canonical spec → engine config | STRAT → engine-native | lossy where engine can't express → CapabilityGap | refuse silently-approximating | parity tests | WS3 |
| C3 engine result → NormalizedResult | engine-native → canonical trades/equity/metrics | lossless target | unknown fields preserved in `semantic_notes` | golden tests + fee recomputation | WS3 |
| C4 venue symbol/timeframe → canonical | `BTCUSDT` → `BTC-USDT.BINANCE_SPOT` | lossless | unmapped → hard error | mapping-table tests | WS2 |
| C5 raw market data → canonical bars | source files → canonical schema | lossless + explicit derived versions for any fill/dedup | µs/ms timestamp-unit boundary handled explicitly (CG-03) | dataset quality gates | WS2 |
| C6 AI research output → Research Asset | agent output → RA record | lossy (curation) | contradictions preserved | human_review flag | S2 |
| C7 external glossary → concepts | FIBO/venue docs → CON | lossy | context variants kept separate | T7 benchmarks | S2 |
Each converter records: converter version, source hash, losses[], provenance (type catalog §4).

## M. Type system

Canonical in `docs/architecture/TYPE_AND_CONTRACT_CATALOG.md` §1–2. [APPROVED at semantic level; serialization PROVISIONAL until S2]. Key laws: decimal-only accounting, UTC-only, value objects over primitives, append-only evidence.

## N. Domain models and entities

Type catalog §2 defines identity/lifecycle/invariants for DS, SRC, STRAT/SV, HYP, EXP/RUN, VAL, EV, APR, RA, CON, MDL/AGT/PRM/BMK, LRN. [APPROVED]

## O. Contract architecture

Type catalog §3–8: commands, queries, events, adapter/converter/job/artifact/API contracts + versioning rules. [APPROVED as names/semantics]

## P. Data architecture [PROVISIONAL]

- Operational DB: **SQLite for S1 prototype → PostgreSQL 18 at S2** if/when concurrency or integrity needs demand (PG18 GA verified; PG14 EOL 2026-11 — REG §5). Single-writer laptop reality makes SQLite defensible now; the repository layer hides the switch.
- Analytical: Parquet artifacts + DuckDB for ad-hoc analysis (REG §5).
- Artifact storage: local FS under `artifacts/` with manifests + hashes (SSOT WS1); large files gitignored.
- Raw vs normalized market data: separate trees; raw immutable (dataset spec).
- Immutable snapshots: DVC-class references per lineage prototype [UNRESOLVED → WS5/RG-10].
- AI traces: MLflow 3.x GenAI tracing is the leading candidate (REG §2) [PROVISIONAL → WS5/WS8].
- Search: SQLite FTS5 / PG tsvector for concepts+registry text (REG §9). Vector retrieval: **rejected for MVP** — no retrieval requirement exists yet (pgvector noted as future option, REG §5).
- Time-series DB: rejected for MVP; Parquet+DuckDB suffices at two instruments × three timeframes.

## Q. Dataset architecture [APPROVED — spec exists]

`specs/CANONICAL_BAKEOFF_DATASET_V1.md` + Amendment A1 per D-029 (µs timestamps in source files dated from 2025-01-01, CG-03). Identity: dataset_id + source files + SHA-256 set + normalization commit + coverage + quality-report hash. Licensing: Binance public data — free redistribution of derived hashes/manifests, raw files re-downloadable (record source URLs, don't redistribute payloads).

## R. Event architecture [PROVISIONAL]

MVP: append-only event log table (transactional outbox pattern) inside the monolith; consumers (dashboard, reporting, memory) read it. Event names/payloads per type catalog §3. No broker — a queue product without multiple processes is decoration. Idempotency keys + per-entity ordering; dead-letter = failed-events table surfaced in ops view. Revisit only when a second process genuinely exists (S3 paper lane).

## S. Workflow/job architecture [PROVISIONAL]

Job model per type catalog §5: DB-table queue, APScheduler for time triggers (active, REG §3), cooperative cancellation, checkpoint refs for long runs (walk-forward), parent/child for sweeps. Concurrency: bounded worker pool; per-engine env isolation. Distributed execution: rejected for MVP (RG-15 names Prefect as the upgrade path with trigger: sustained queue saturation or multi-machine need).

## T. AI model & agent architecture [APPROVED design; execution S1+]

Registries (MDL/AGT/PRM), benchmark suite (frozen V1), controlled/best-config/longitudinal modes, cost intelligence, provenance graph — all per `specs/AI_AGENT_EVALUATION_BLUEPRINT_V1.md` + `docs/ai/AGENT_ROLES.md`. 2026-07-06 adjustments (REG §7): (1) **no provider determinism** → stability scoring is multi-sample by design; (2) provider snapshot pinning policies differ (Anthropic ≥60d notice; OpenAI as little as 2 weeks for previews) → registry stores per-provider deprecation watch; (3) OpenAI Evals platform EOL 2026-11-30 → not a dependency; MLflow-first harness with Inspect as design reference; (4) model degradation/outage → fallback route required before any config becomes a task-class default (benchmark suite promotion rule). Task Router: S2, only after benchmark evidence exists.

## U. Research asset architecture [APPROVED]

RA lifecycle per type catalog §2 + SKILL_RESEARCH_ASSET_SYNTHESIZER: creation with full provenance/cost, human review flag, freshness states, contradiction/supersession chains, consumer tracking for amortization (cost intelligence feeds from this).

## V. Dictionary/ontology architecture [APPROVED direction — evidence-backed]

Plain relational concept + alias + context-variant tables with FTS; **no graph DB, no RDF** at <10k concepts (REG §9: Kuzu archived, Memgraph BSL, Neo4j overkill; rdflib/Oxigraph adopted only if external linked-data interop materializes). Seed sources: FIBO (MIT, active) legally clean; copyrighted glossaries (Investopedia) are cite-only, never scraped. Venue/market context variants are first-class rows, not merged definitions. Dictionary ≠ strategy config (North Star §9.3).

## W. Memory & learning architecture [APPROVED]

LRN records only with evidence refs (invalid otherwise — type catalog §2); categories per North Star §9.10; contradiction storage first-class; freshness/invalidation triggers mandatory; no free-floating "AI memory".

## X. Scoring architecture [APPROVED]

Separate score families exactly as North Star §8 (strategy) and §10 (AI). Hard gates dominate scores everywhere (G-gates for strategies; critical-failure rule for models). No weighted average may override a hard fail; no single global score exists anywhere in the system — enforced by the reporting module's score-view contracts.

## Y. Approval architecture [APPROVED]

Contextual identity Strategy×Market×Instrument×Timeframe×Config×Environment (risk-tier dimension reserved). States per type catalog §2 (superset harmonizing North Star §9.7 and prototype spec names; mapping table maintained in approval module spec). Machine proposes with evidence; operator decides anything in the LIVE family; every decision carries evidence package + expiry/review rule.

## Z. Risk architecture [APPROVED design; build S2/S3]

Independent risk authority (never strategy-owned): global caps (capital, daily loss, drawdown), portfolio caps (correlation, concentration) [S3], strategy budgets, market-condition blocks (stale data, exchange health), kill switches (operator-manual first; automated triggers additive, never replacing manual). MVP scope: risk *rules as validation preconditions* + approval preconditions only — no runtime risk engine exists because nothing trades.

## AA. Paper vs live boundary [APPROVED]

Hard separations: credentials (different keys, different `.env` names, live keys nonexistent until S4), state (separate DBs/schemas for paper vs any future live), visual labeling (dashboard banner + color regime), order routing (live adapters not installed until S4), approval (separate states), capital accounting (paper capital explicitly synthetic), logging (environment tag on every record). MVP: live side simply does not exist; the boundary is enforced by absence + the live-state-unreachable test (MODULE_CATALOG §11).

## AB. Security architecture [APPROVED design]

Per SSOT secret rules + intake gate: `.env`-only secrets, names-only `.env.example`, gitignore verification, no withdrawal-enabled keys ever requested, credential rotation procedure documented at intake, minimal key scopes. Dependency scanning + license compatibility in local gate (gitleaks/audit — verify tools at WS1). Untrusted-content rule: ingested strategy code never executes in-process; reproduction in isolated env without credentials/network where feasible; all fetched content is data, not instructions (prompt injection). AI tool permissions per role (AGENT_ROLES). Threat model review at each stage exit (SKILL_SECURITY_REVIEWER).

## AC. Observability architecture [PROVISIONAL]

MVP: structured JSON logs + job/queue views + MLflow run UI + the evidence dashboard; data-freshness and API-failure counters as DB rows surfaced in ops view. S2: revisit Prometheus/Grafana (licenses fine for internal use — REG §4); OTel adoption only behind a thin façade (GenAI semconv still churning — REG §4). AI cost tracking is a domain feature (cost intelligence), not an observability afterthought.

## AD. Failure & fallback architecture [APPROVED design]

Per external dependency: failure mode → timeout → bounded retries w/ backoff → fallback → operator-visible state.

| Dependency | Fallback | Degradation |
|---|---|---|
| Binance public data | retry; alternate official mirror path; if exhausted → documented stop (SSOT WS2 rule) | dataset freeze blocked, everything else proceeds |
| Engine (any) | other engines continue; candidate marked blocked w/ repro evidence | role coverage shrinks; no silent skip |
| MLflow/DVC local | filesystem-manifest fallback (evidence never lost); lineage decision may become ALTERNATIVE_REQUIRED | comparison UX degrades |
| AI providers | second-provider route or deferral (never fabricate); harness marks BLOCKED | benchmarks delayed, fixtures still validated |
| Dashboard | artifacts remain browsable on FS (manifests are the truth; UI is projection) | none to evidence |
Consistency rule: crash mid-job leaves partial artifacts + FAILED status; rerun is idempotent (content-addressed inputs).

## AE. Testing architecture

Canonical in `docs/testing/TEST_MASTER_PLAN.md` (taxonomy, fixtures, goldens, env matrix, stage gates). [APPROVED]

## AF. Performance architecture [PROVISIONAL]

Expected workloads (MVP): dataset ≈ 2 instruments × 3 timeframes × ~5.5y candles (≈1.2M rows/instrument at 5m) — trivial for Parquet/DuckDB; engine runs are the long pole (minutes–hours; budget recorded per run); sweeps bounded by trial-retention discipline, not compute. Memory limit: operator laptop; per-engine envs prevent dependency bloat in the core. Caching: content-addressed artifact reuse. Profiling: record runtime/memory per run (bake-off matrix requires it). Scaling trigger: sustained job-queue saturation → RG-15 path. No distributed infrastructure before that evidence.

## AG. Maintainability architecture [APPROVED design]

Single-operator reality drives everything: dependency budget (every new dep needs a registry row + justification), lint/format/typecheck in local gate, architecture tests for module law, dead-code deletion over deprecation cycles (no external consumers), engine upgrades via pinned parity reruns, ADR discipline = DECISION_LOG entries (existing format retained; this AD is the architecture ledger), docs freshness = every doc carries Date + reverify triggers (SOURCE_VERIFIER sweeps).

## AH. Developer experience [APPROVED design]

One-command setup (bootstrap script + per-engine env builders), one-command local gate (<5 min, TEST_MASTER_PLAN §5), deterministic fixtures + seed data in `fixtures/`, `.env.example`-driven config with startup validation (fail-closed on missing required vars), test selection by module, generated API docs from contracts at S2. CI: deferred decision RG-14 — local gate is the guarantee until then.

## AI. UI / product information architecture [APPROVED for MVP; S2 direction PROVISIONAL]

MVP = six read-only evidence views (MVP_SCOPE §7) on Streamlit (REG §8 — cheapest credible; replaceable by design since dashboard is a projection of manifests/DB, never a store). S2 console: Next.js + shadcn/ui direction (console is not CRUD-shaped → Refine/react-admin rejected); progressive disclosure from the 27-page North Star IA — entity detail pages share one layout pattern (overview / evidence / lineage / history tabs); global search over registries (FTS); explicit empty states ("no validated strategies yet — here's the pipeline"); paper/live visual separation per §AA. Command palette, comparisons UI, AI command center: S2+, sequenced in TODO initiative 14.

## AJ. Deployment architecture [APPROVED for MVP]

Local-first: everything on the operator's Mac; Docker only where an engine demands it (LEAN; optionally Hummingbot). No cloud in MVP (cost, custody of evidence, no availability requirement). S3 may justify an always-on paper host (small VPS or home server) — decision deferred with trigger: paper lane needs >laptop-uptime. Managed services considered only per-component behind ports.

## AK. Migration/evolution strategy [APPROVED direction]

- **→ Crypto Perpetual Futures**: additive: instrument model gains contract fields (funding, mark price, leverage); validation gains funding-aware cost gate + liquidation-aware stress; risk gains leverage caps; engines already claim support (verify per adapter). Core spine (spec→experiment→validation→evidence→approval) unchanged — that invariance is the architecture's main bet, checked at every S2 review.
- **→ US Stocks/ETFs**: new market context: sessions/calendars, corporate actions (dataset versioning already supports corrections-as-new-versions), broker adapters replace exchange adapters behind the same ports; LEAN's multi-asset portability is the hedge (bake-off scores it).
- Anti-rewrite rule: any expansion PR touching core spine contracts requires Architecture Guardian review + decision-log entry.

## AL. Decision register (architecture-level)

Full project log remains `DECISION_LOG.md` (D-001…D-030). Architecture-specific register (this pass; all reversible unless noted):

| ID | Decision | Status | Evidence | Alternatives | Consequences / reversibility | Prototype required? | Reverify |
|---|---|---|---|---|---|---|---|
| AD-01 | Modular monolith, single CLI + read-only dashboard | PROVISIONAL | §B2, REG §3 | services, worker daemons | low ops burden; reversible via ports | RG-15 telemetry | S2 entry |
| AD-02 | Per-engine isolated environments; core never imports engines | APPROVED | REG §1 licenses + RG-04 | shared env | license safety + dep isolation; low cost | WS1 confirms | on engine change |
| AD-03 | SQLite → Postgres 18 path for operational DB | PROVISIONAL | REG §5 | Postgres-first | zero-ops start; repository layer hides switch | WS1/WS5 | S2 entry |
| AD-04 | Parquet+DuckDB analytics; no TSDB; no vector DB | PROVISIONAL | REG §5, workload §AF | Timescale, pgvector | simplicity; additive later | none | S2 |
| AD-05 | MLflow+DVC lineage hypothesis retained (strengthened) | PROVISIONAL (D-019 stands) | REG §2, CG-04 | MLflow-only, DVC-only, Aim/ClearML | WS5 decides | **yes — WS5** | at WS5 |
| AD-06 | Streamlit for WS9 evidence surface | PROVISIONAL | REG §8 | Dash/Panel/Gradio/MLflow-UI-only | throwaway-cheap; UI is projection → replaceable | WS9 is the proof | S2 |
| AD-07 | Next.js+shadcn direction for S2 console; Refine/react-admin rejected | PROVISIONAL | REG §8 | Refine/react-admin | no CRUD-framework fight; revisit if console becomes CRUD | S2 spike | S2 |
| AD-08 | Relational dictionary + FTS; graph/RDF rejected for MVP | APPROVED (evidence-backed) | REG §9 | Neo4j/Kuzu/Memgraph/rdflib | laziest defensible; additive interop later | none | if interop need appears |
| AD-09 | FIBO as legal seed source; no glossary scraping | APPROVED | REG §9 | Investopedia scrape | clean licensing | none | annually |
| AD-10 | DB-table jobs + APScheduler; Prefect named as upgrade path; Temporal/Dagster rejected | PROVISIONAL | REG §3 | Prefect/Dagster/Temporal now | minimal ops; explicit trigger to upgrade | RG-15 | S2 entry |
| AD-11 | Multi-sample AI benchmarking (no determinism assumption) | APPROVED | REG §7 (CG-07) | single-run + seed | honest variance; higher cost per benchmark | none | on provider policy change |
| AD-12 | MLflow-first eval harness; OpenAI Evals dependency rejected; Inspect as reference | PROVISIONAL | REG §7 | promptfoo/DeepEval-first | one tool serving WS5+WS8; RG-09 guard | WS8 | before paid runs |
| AD-13 | Venue connectivity test ranking: Kraken, Binance, OKX ↑, Coinbase ↓ (pending RG-05) | PROVISIONAL | REG §6, CG-05 | package's original ranking | Israel-fit realism; human gate unchanged | none (S1 needs no venue) | before S3 |
| AD-14 | Databento reclassified: future equities/futures only, not crypto | APPROVED | REG §6 (CG-06) | keep as crypto candidate | corrects stale assumption | none | at Phase-3 planning |
| AD-15 | backtesting.py, Backtrader, W&B, Kuzu, Memgraph, Skosify, Temporal(MVP), graph-DBs(MVP) rejected | APPROVED | REG §1–§9 | — | narrows candidate space with evidence | none | 90d registry sweep |

### Custom Build Gate (mandatory template for any Build Custom decision)

A Build Custom decision must document: (1) capability statement; (2) ≥3 reuse candidates evaluated with evidence; (3) the specific insufficiency of each; (4) the smallest custom scope that closes the gap; (5) maintenance cost acknowledgment; (6) exit strategy. Currently justified custom domains (North Star §15, re-affirmed with 2026-07-06 registry evidence — no existing tool owns these semantics): Trading Evidence Registry, Approval Engine, evidence-linked Memory, Research Asset semantics, AI↔economic-outcome linkage, canonical strategy spec + converters. Everything else defaults to reuse.
