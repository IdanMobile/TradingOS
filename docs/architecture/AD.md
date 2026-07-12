# AD — Architecture Decisions: Trading Intelligence OS

Status: Canonical architecture document v1, S2 architecture lock applied (2026-07-10).
Maturity labels used throughout: **[APPROVED]** (backed by decision log / this planning pass with evidence), **[PROVISIONAL]** (best current direction; may change on prototype evidence), **[UNRESOLVED]** (explicitly awaiting evidence — the required proof is named).
Authority: subordinate to the SSOT (`handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md`) and `TRADING_OS_NORTH_STAR.md`. This document does not authorize implementation; it prevents rediscovery.
Evidence base: package research (2026-07-05) + refreshed web research (2026-07-06) in `research/EXISTING_CAPABILITY_REGISTRY.md` (cited as REG §n) and `research/RESEARCH_GAP_MATRIX.md` (RG-nn), plus retained S1 evidence accepted by D-036 in `decisions/PROTOTYPE_EVIDENCE_DECISION.md` (cited as S1 decision), `artifacts/reports/ENGINE_BAKEOFF_REPORT.md`, and `artifacts/reports/LINEAGE_PROTOTYPE_REPORT.md`.

---

## A. Executive architecture summary

- **Purpose**: a self-measuring machine for discovering, rejecting, validating, approving, monitoring, degrading, and retiring trading edges — measuring its own tools, models, agents, and research assets along the way (North Star §2).
- **Philosophy**: composable reuse around a custom evidence spine. Engines, trackers, indicator libraries, dashboards are replaceable commodities behind ports; the durable custom core is the Trading Evidence Registry + approval/provenance semantics (North Star §15, D-009, D-016).
- **S2 boundary**: Crypto Spot, BTCUSDT/ETHUSDT, 5m/15m/1h, historical research→validation evidence pipeline and read-only console. Paper is modeled but not activated. See `docs/product/MVP_SCOPE.md` and the S2 plan.
- **Long-term boundary**: multi-market (perps, US equities/ETFs), paper→limited-live under human gates, full 27-page console, evidence-routed AI.
- **Non-goals**: universal bot, single score, AI-in-live-path, architecture for its own sake (North Star §17).
- **Core risks**: overfitting theater, cost-model optimism, leakage, engine semantic mismatch, AI hallucination provenance, single-operator maintenance ceiling (North Star §18; red team in `audits/RED_TEAM_PLAN_REVIEW.md`).

## B. Architecture principles

1. **Reuse before build** [APPROVED, D-002] — custom code requires a failed reuse case (Custom Build Gate §AL).
2. **Modular monolith over services** [APPROVED for S2] — one local application boundary (CLI plus read-only dashboard) with ports/adapters and per-engine isolated subprocess environments. S1 completed on one operator machine without evidence requiring service boundaries; extraction requires a later measured contention or multi-host need and preserves the ports.
3. **Ports and adapters + dependency inversion** [APPROVED as design law] — MODULE_CATALOG dependency rules; enforced by architecture tests.
4. **Deterministic vs non-deterministic boundary** [APPROVED] — §H; AI never inside deterministic execution paths.
5. **Immutable evidence, append-only history** [APPROVED] — supersession over mutation for all evidence-bearing records (type catalog §0).
6. **Replaceable externals** [APPROVED] — domain stores only public stable refs to trackers/engines (lineage prototype "replaceability" gate).
7. **Idempotency & reproducibility** [APPROVED] — content-addressed inputs; jobs at-least-once + idempotent effects (type catalog §5).
8. **Point-in-time correctness** [APPROVED] — no feature availability before its timestamp; G4 gates; time-aware corpora for AI benchmarks (D-021).
9. **Fail-closed** [APPROVED for anything touching capital or approval state; fail-open permitted only for read-only views].
10. **No strategy-owned risk authority** [APPROVED, North Star §4.3]; **no hidden AI decisions** [APPROVED, §H/§T]; **no live execution without human approval** [APPROVED].

## C. System context

Actors/systems: Operator (sole human; approver of HG gates) · Coding agent (R7, SSOT-bound) · AI providers (future adapter boundary; S2 remains null/mock only) · Research/strategy sources (untrusted input; ingestion workflow) · Exchanges (public historical data only in S2; future venue candidates remain outside the boundary) · Market-data vendors (deferred tiers, D-018) · Future paper environments (not authorized) · Future live environments (S4, not authorized) · Local machine (macOS ARM; primary) · Optional cloud (none in S2) · Storage (local FS + Git + SQLite operational DB).

Trust boundaries: (1) everything fetched from the internet is untrusted data — prompt-injection surface (§AB); (2) S2 Research Lab uses null/mock AI only; any later provider API requires a separate credential intake; (3) no exchange, demo, testnet, sandbox, paper, or live credential exists in S2.

## D. Bounded contexts

Consolidated from the mandate's candidate list — merged where cohesion demands, deferred where MVP doesn't touch them. [APPROVED as boundaries; internals PROVISIONAL]

| Context | Owns | MVP | Notes on merges |
|---|---|---|---|
| **Market Data** | datasets, quality, freeze identity | thin (WS2) | "Data Center" IA page maps here |
| **Strategy** | specs, versions, families | yes | includes Strategy Definition + Versioning (split was artificial) |
| **Ingestion** | sources, licenses, extraction lifecycle | bounded S2 | primary-source registration/refresh and hypothesis proposals; claims remain untrusted inputs |
| **Experimentation** | experiments, runs, trials, lineage refs | yes | Backtesting execution lives here; engines are adapters, not a context |
| **Validation** | gates G1–G12, packages | yes | |
| **Evidence & Approval** | EV records, approval state machine, promotion governance | thin | Approval Governance + Evidence merged: approval is meaningless without evidence rows |
| **Knowledge** | dictionary concepts, research assets, ResearchSource/Hypothesis registry, ecosystem library | bounded S2 | same storage/provenance pattern; split later only if scale demands |
| **AI Measurement** | model/agent/prompt registries, benchmarks, cost, routing evidence | harness+fixtures | Task Router deferred to S2 (needs benchmark evidence first) |
| **Memory** | evidence-linked learnings | thin | |
| **Operations** | jobs, schedules, reports, dashboard | thin read-only | Reporting + Ops merged for MVP |
| Paper/Bot Operations | bot lifecycle, divergence tracking | **deferred S3** | modeled, not built |
| Live Trading, Portfolio, Risk Center | — | **execution deferred S3/S4** | S2 has inert historical projections and risk/approval preconditions only |

Prohibited responsibilities are inherited from MODULE_CATALOG (e.g., Validation never promotes; Strategy never owns risk).

## E. Module map

Canonical in `docs/architecture/MODULE_CATALOG.md` (18 modules, dependency law, tests, MVP status). [APPROVED at boundary level]

## F. Repository architecture

**[APPROVED for S2] Monorepo.** One repository contains the OS package tree, engine adapter envs, specs/docs, and artifact manifests (large artifacts outside Git; hashes inside — SSOT WS1). S1 retained all evidence and isolated engine environments without a coordination or ingestion-volume reason to split repositories. A later split must identify a measured independent lifecycle/ownership need and preserve the same ports and artifact identities.

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

## G. Application architecture [APPROVED for S2]

S2 has **one local CLI/application boundary** for research operations and **one read-only dashboard process** (API+UI). The first Research Lab runner is a bounded deterministic command in the monolith. A persisted local job table and scheduler may be added only after that same command passes the idempotency contract in §S; they are not separate services. Separate research/backtest/validation workers, ingestion services, and distributed orchestration remain rejected because S1 produced no multi-process or multi-host requirement.

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

## K. Engine adapter architecture [APPROVED for evidenced S2 roles]

Role-based composition (D-012), resolved by the S1 bake-off:

- **vectorbt — selected research accelerator** for bounded B2/B3/B4 parameter sweeps. It has no execution or approval authority; every trial is retained and binding overfit controls plus event-engine reproduction remain promotion preconditions.
- **Freqtrade — selected Crypto Spot event/reproduction lane** through CLI/subprocess only. Its B1–B4 evidence, fee audit, timing semantics, G4 warning, and slippage gap are retained; trade/dry-run and venue modes are prohibited in S2.
- **NautilusTrader — capability-supported bounded event-simulation lane** only. Deterministic, fee-audited B1–B4 evidence supports this role; full-history parity and latency/fill evidence are still gaps.
- **Hummingbot — bounded bot-operations capability/regression lane** only. BTCUSDT 30-day B1–B4 x `{F0/S0,F1/S1}` x `{run1,run2}` is normalized, fee-audited, and deterministic; full-history completion remains a throughput track, not a credential or approval blocker.
- **LEAN — bounded multi-asset portability candidate** only. Local Docker B1–B4 x `{F0/S0,F1/S1}` evidence is retained without QuantConnect cloud/account use; full-range parity remains a throughput/scope expansion.

No engine is a strategy selector, risk authority, approver, venue gateway, or universal engine. A bounded/deferred engine is invoked only for a capability-specific evidence task inside its retained scope, or after its recorded blocker is closed.
- Common contract: EngineAdapter port (type catalog §4). Semantic mismatches → CapabilityGap records + parity diagnosis (WS4).
- Version pinning: exact version/commit per run; upgrade requires golden parity rerun (type catalog §8).
- License boundary: Freqtrade GPL-3.0 → subprocess/CLI integration only, no code-linking; Nautilus LGPL-3.0 → import permissible, keep abstraction anyway; backtesting.py AGPL + Backtrader dead → rejected (REG §1).
- Exit strategy per engine: adapter deletion; normalized artifacts remain readable forever (normalization is ours).

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

Canonical in `docs/architecture/TYPE_AND_CONTRACT_CATALOG.md` §0–2. [APPROVED for S2 semantics and JSON serialization]. Key laws: decimal values cross JSON boundaries as strings, timestamps are UTC ISO-8601 with `Z`, IDs are opaque, top-level payloads carry schema versions, value objects replace primitives, and evidence is append-only.

## N. Domain models and entities

Type catalog §2 defines identity/lifecycle/invariants for DS, SRC, STRAT/SV, HYP, EXP/RUN, VAL, EV, APR, RA, CON, MDL/AGT/PRM/BMK, LRN. [APPROVED]

## O. Contract architecture

Type catalog §3–8: commands, queries, events, adapter/converter/job/artifact/API contracts + versioning rules. [APPROVED as names/semantics]

## P. Data architecture [APPROVED for S2]

- Operational DB: **SQLite** in WAL mode for registries, read models, and the optional local job table. The S1 single-operator/local-first workload produced no evidence for PostgreSQL. PostgreSQL 18 becomes a migration candidate only when a representative workload records either (a) any operational write lost or failed after the configured SQLite busy-timeout/retry budget, (b) p95 write-transaction latency above 500 ms in three consecutive complete Research Lab batches, or (c) an approved multi-host/concurrent-writer requirement. The measurements and an ADR are required before migration; repository ports and replayable append-only records are the migration seam.
- Analytical: **Parquet + DuckDB** for frozen candles, trial populations, normalized engine results, scorecard inputs, and ad-hoc analysis. Operational rows contain identities/statuses/refs, not duplicated analytical payloads.
- Artifact storage: local FS under `artifacts/` with manifests + hashes (SSOT WS1); large files gitignored.
- Raw vs normalized market data: separate trees; raw immutable (dataset spec).
- Lineage: **MLflow + DVC behind the LineageAdapter ports**, selected by the seven-gate S1 prototype. MLflow owns generic run/artifact/comparison metadata; DVC owns immutable dataset snapshot/restore references; the domain stores only stable public refs and never either tool's internal keys or schema.
- Retention: no automatic deletion. All batch manifests, trials (including failed/aborted trials), MLflow run records/artifacts, DVC snapshot refs, evidence rows, and scorecards are retained indefinitely by default. A later pruning policy cannot make a retained domain record unrestorable and requires an explicit decision plus a superseding manifest.
- Backup/restore: the SQLite operational DB, MLflow metadata/artifact root, DVC remote, and artifact manifests form one backup set copied after each completed batch and before any tool/schema migration to a separate local volume/filesystem from the primary. A clean-checkout restore and hash/replay check is required before S2 exit and after lineage-store upgrades.
- Migration/access: migrations are versioned, backup-first, and must preserve public `run_ref`/`dataset_ref` values or record an adapter-level mapping without changing domain IDs. Lineage stores and their UIs bind to loopback and are operator-only in S2; no public network, cloud account, or shared write access is authorized.
- Search: SQLite FTS5 / PG tsvector for concepts+registry text (REG §9). Vector retrieval: **rejected for MVP** — no retrieval requirement exists yet (pgvector noted as future option, REG §5).
- Time-series DB: rejected for MVP; Parquet+DuckDB suffices at two instruments × three timeframes.

## Q. Dataset architecture [APPROVED — spec exists]

`specs/CANONICAL_BAKEOFF_DATASET_V1.md` + Amendment A1 per D-029 (µs timestamps in source files dated from 2025-01-01, CG-03). Identity: dataset_id + source files + SHA-256 set + normalization commit + coverage + quality-report hash. Licensing: Binance public data — free redistribution of derived hashes/manifests, raw files re-downloadable (record source URLs, don't redistribute payloads).

## R. Event architecture [APPROVED for S2]

Append-only event rows live inside the monolith; dashboard, reporting, and memory consume them as read models. Event names/payloads follow the type catalog. There is **no broker** in S2. Idempotency keys and per-entity ordering are required; failures remain visible. Revisit a broker only after an approved second-process/multi-host boundary exists and DB polling is measured insufficient.

## S. Workflow/job architecture [APPROVED for bounded S2]

The first runner is the allowlisted, offline `ResearchLabBatch` command defined in the type catalog: one content-addressed input set, bounded trial count/resources, deterministic identity, complete failure retention, and `execution_authority=NONE`. It must prove that rerunning identical complete inputs returns the same batch/artifact refs without recomputation before any schedule is enabled. Only then may a SQLite job table and local time trigger run allowlisted research, freshness, validation, and reporting jobs with bounded concurrency and per-engine subprocess isolation. No broker, distributed executor, venue command, paper command, or live command is present. Prefect or another orchestrator is reconsidered only after sustained measured queue saturation or an approved multi-machine requirement.

## T. AI model & agent architecture [APPROVED design; execution S1+]

Registries (MDL/AGT/PRM), benchmark suite (frozen V1), controlled/best-config/longitudinal modes, cost intelligence, provenance graph — all per `specs/AI_AGENT_EVALUATION_BLUEPRINT_V1.md` + `docs/ai/AGENT_ROLES.md`. 2026-07-06 adjustments (REG §7): (1) **no provider determinism** → stability scoring is multi-sample by design; (2) provider snapshot pinning policies differ → registry stores per-provider deprecation watch; (3) OpenAI Evals platform is not a dependency; (4) model degradation/outage → fallback route required before any config becomes a task-class default. S1 proved null/mock trace plumbing only. Real-provider runs and the Task Router remain outside S2 until credential authority and real benchmark evidence exist.

## U. Research asset and source architecture [APPROVED]

The application-owned `ResearchSource` registry records bibliographic identity, canonical URL/DOI, authors/date, access/license notes, claim summary, assumptions, review time, supersession, and reproduction status. Primary-source claims create explicit `Hypothesis` records; publication or original-sample profit never counts as local evidence. The autonomous evidence flow is `ResearchSource → Hypothesis → canonical strategy spec → ResearchLabBatch/EXP/RUN → multi-dimensional Scorecard → VAL/EV`, with ambiguities, contradictions, failures, and missing dimensions retained as blockers. RA lifecycle remains creation with full provenance/cost, human review flag, freshness states, contradiction/supersession chains, and consumer tracking.

External strategy acquisition is a core lab capability, not an execution shortcut. Approved source classes include academic papers, QuantConnect/library algorithms, Freqtrade strategies, Hummingbot V2 controllers, open-source TradingView/Pine scripts, exchange-hosted bot marketplaces such as Binance Trading Bots, third-party bot platforms, public strategy leaderboards, copy-trading/copy-investing records, and online signal feeds. Every such item enters only as untrusted research/source material: the OS may extract a canonical spec, reconstruct historical signals, or build a replayable hypothesis, but it may not copy, subscribe, mirror, or execute the source's trades. Source ingestion must record platform terms, source URL, author/provider, capture time, license/usage permission, parameter visibility, signal timestamp semantics, survivorship/selection bias risks, fee/slippage assumptions, and whether the source is a strategy definition, historical signal feed, portfolio allocation record, or black-box performance claim. For open-source TradingView/Pine strategies, Strategy Tester summaries may be retained only as external comparison evidence with symbol, timeframe, date range, capital, commission, slippage, net profit, drawdown, trade count, win rate, and profit factor; protected or invite-only script code is never copied or reverse-engineered.

Copy-trading, signal providers, exchange bot marketplaces, and working bot platforms are therefore future first-class inputs to the Research Lab and demo-wallet roadmap, but never direct trading authorities. Before any such source can influence paper/demo or live operation it must pass the normal path: source verification, canonicalization or replay capture, local backtest/replay on approved data, retained trial population, validation gates including multiple-testing and cross-engine checks where applicable, paper/demo divergence tracking, risk/security review, and the required human gates. If a platform exposes only opaque performance or leaderboard data without reproducible rules/signals, it can be retained as a research asset or allocation hypothesis, not as an approvable strategy.

## V. Dictionary/ontology architecture [APPROVED direction — evidence-backed]

Plain relational concept + alias + context-variant tables with FTS; **no graph DB, no RDF** at <10k concepts (REG §9: Kuzu archived, Memgraph BSL, Neo4j overkill; rdflib/Oxigraph adopted only if external linked-data interop materializes). Seed sources: FIBO (MIT, active) legally clean; copyrighted glossaries (Investopedia) are cite-only, never scraped. Venue/market context variants are first-class rows, not merged definitions. Dictionary ≠ strategy config (North Star §9.3).

## W. Memory & learning architecture [APPROVED]

LRN records only with evidence refs (invalid otherwise — type catalog §2); categories per North Star §9.10; contradiction storage first-class; freshness/invalidation triggers mandatory; no free-floating "AI memory".

## X. Scoring architecture [APPROVED]

Separate score families exactly as North Star §8 (strategy) and §10 (AI). Hard gates dominate scores everywhere (G-gates for strategies; critical-failure rule for models). No weighted average may override a hard fail; no single global score exists anywhere in the system — enforced by the reporting module's score-view contracts.

## Y. Approval architecture [APPROVED]

Contextual identity Strategy×Market×Instrument×Timeframe×Config×Environment (risk-tier dimension reserved). States per type catalog §2 (superset harmonizing North Star §9.7 and prototype spec names; mapping table maintained in approval module spec). Machine proposes with evidence; operator decides anything in the LIVE family; every decision carries evidence package + expiry/review rule.

## Z. Risk architecture [APPROVED design; build S2/S3]

Independent risk authority (never strategy-owned): global caps (capital, daily loss, drawdown), portfolio caps (correlation, concentration) [S3], strategy budgets, market-condition blocks (stale data, exchange health), kill switches (operator-manual first; automated triggers additive, never replacing manual). S2 scope is inert `RiskDecision` records plus validation/approval preconditions only—no runtime risk engine exists because nothing trades.

## AA. Demo, paper, and live boundary [APPROVED]

S2 is historical research only: `execution_authority=NONE`, `venue_connection=NONE`, `paper_orders=DISABLED`, and `live_orders=DISABLED`. Its Market/Signal/Order/Fill/Position/Portfolio/Risk/Approval records are inert historical/read-model contracts and expose no client, route, credential, or mutation command. There is no synthetic wallet, demo/testnet/sandbox connection, Freqtrade trade/dry-run mode, credential-bearing venue adapter, order endpoint, approval-write endpoint, or real-money command.

S3/S4 control-plane records may be modeled before activation: stage-gate readiness, synthetic-local paper-lane proposals, and limited-live readiness proposals are immutable evidence/proposal records only. They validate prerequisites, human-decision evidence, and risk-limit shape while keeping `execution_authority=NONE`, `venue_connection=NONE`, and all paper/live order capabilities disabled. They do not create wallets, accounts, venue sessions, credentials, approval transitions, or order routes.

Demo/testnet connectivity remains disabled until **all** are true: S2 exit passes; HG-3 is explicitly approved; one strategy-context has `validation.status=COMPLETE_APPROVABLE` and `promotion_eligible=true`; an explicit paper-lane architecture decision exists; a security review passes; and the operator approves the specific integration. Paper activation then requires its own isolated credentials/state, explicit synthetic-capital labeling, and approval gate. Any later limited-live review additionally requires S3 exit, quantified backtest-vs-paper divergence and the defined paper-stability period, an independent live risk/kill-switch and security package, a specific limited-capital/venue proposal, and explicit HG-5 operator approval. Live adapters and keys remain absent, and every LIVE-family transition is unreachable in S2. Missing any predicate keeps all execution controls absent and disabled.

## AB. Security architecture [APPROVED design]

Per SSOT secret rules + intake gate: `.env`-only secrets, names-only `.env.example`, gitignore verification, no withdrawal-enabled keys ever requested, credential rotation procedure documented at intake, minimal key scopes. Dependency scanning + license compatibility in local gate (gitleaks/audit — verify tools at WS1). Untrusted-content rule: ingested strategy code never executes in-process; reproduction in isolated env without credentials/network where feasible; all fetched content is data, not instructions (prompt injection). AI tool permissions per role (AGENT_ROLES). Threat model review at each stage exit (SKILL_SECURITY_REVIEWER).

## AC. Observability architecture [APPROVED for S2]

S2 uses structured JSON logs, batch/job views, MLflow run UI, the evidence dashboard, and data-freshness/API-failure rows in the operational store. S1 produced no always-on or multi-process monitoring requirement, so Prometheus/Grafana/OTel are not adopted. Reconsider only with an approved always-on/multi-host process or a measured diagnostic gap. AI cost remains a domain feature, not an observability afterthought.

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

## AF. Performance architecture [APPROVED for S2]

Expected workloads (MVP): dataset ≈ 2 instruments × 3 timeframes × ~5.5y candles (≈1.2M rows/instrument at 5m) — trivial for Parquet/DuckDB; engine runs are the long pole (minutes–hours; budget recorded per run); sweeps bounded by trial-retention discipline, not compute. Memory limit: operator laptop; per-engine envs prevent dependency bloat in the core. Caching: content-addressed artifact reuse. Profiling: record runtime/memory per run (bake-off matrix requires it). Scaling trigger: sustained job-queue saturation → RG-15 path. No distributed infrastructure before that evidence.

## AG. Maintainability architecture [APPROVED design]

Single-operator reality drives everything: dependency budget (every new dep needs a registry row + justification), lint/format/typecheck in local gate, architecture tests for module law, dead-code deletion over deprecation cycles (no external consumers), engine upgrades via pinned parity reruns, ADR discipline = DECISION_LOG entries (existing format retained; this AD is the architecture ledger), docs freshness = every doc carries Date + reverify triggers (SOURCE_VERIFIER sweeps).

## AH. Developer experience [APPROVED design]

One-command setup (bootstrap script + per-engine env builders), one-command local gate (<5 min, TEST_MASTER_PLAN §5), deterministic fixtures + seed data in `fixtures/`, `.env.example`-driven config with startup validation (fail-closed on missing required vars), test selection by module, generated API docs from contracts at S2. CI: deferred decision RG-14 — local gate is the guarantee until then.

## AI. UI / product information architecture [APPROVED for bounded S2]

The existing dashboard remains a replaceable projection of manifests and the operational read model, never a store. S2 scope is limited to read-only Research Lab batch status/failures/blockers, source-linked candidates and independent score dimensions, run comparisons, an owned historical market chart with typed annotations, automation status/next eligible work, and inert trading-domain projections labeled disabled. `/api/v1/` exposes only the corresponding reads plus **exactly one audited write exception** [APPROVED, D-038]: `POST /api/v1/workspace-actions/decision`, the operator-driven workspace-decision recording route — loopback-only, payloads validated against a fixed task/option allowlist, append-only to `artifacts/human_decisions/workspace_decisions.jsonl`, test-pinned as the sole write path. It carries no order, approval-transition, job, credential, venue, paper/demo/live, or real-money mutation authority, and no AI-autonomous caller exists. All other POST/PUT/PATCH/DELETE routes remain prohibited; any expansion of this route or any additional write route requires a new decision gate. A local manual batch trigger remains CLI-only while idempotency is proven. Framework replacement, command palette, generalized 27-page CRUD, AI command center, and executable trading controls are not part of this lock.

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
| AD-01 | Modular monolith, single CLI + read-only dashboard | APPROVED S2 | S1 decision; §B2, §G | services, worker daemons | low ops burden; reversible via ports | S1 showed no extraction need | measured contention/multi-host need |
| AD-02 | Per-engine isolated environments; core never imports engines | APPROVED | REG §1 licenses + RG-04 | shared env | license safety + dep isolation; low cost | WS1 confirms | on engine change |
| AD-03 | SQLite operational state; measured PostgreSQL 18 migration trigger | APPROVED S2 | S1 decision; §P | Postgres-first | zero-ops now; ports/replay preserve migration path | S1 local workload | §P trigger |
| AD-04 | Parquet+DuckDB analytics; no TSDB; no vector DB | APPROVED S2 | S1 canonical data; REG §5, §AF | Timescale, pgvector | sufficient for retained workloads; additive later | S1 dataset/bake-off | workload shape changes |
| AD-05 | MLflow+DVC behind lineage ports | APPROVED S2 | S1 seven-gate lineage report | MLflow-only, DVC-only, Aim/ClearML | stable public refs; filesystem fallback remains | passed WS5 | restore failure/tool upgrade |
| AD-06 | Retain existing read-only dashboard projection for bounded S2 console | APPROVED S2 | S1 evidence-surface pass; §AI | replace framework now | preserves refreshability; read model remains replaceable | passed WS9 | bounded views cannot be met |
| AD-07 | Next.js+shadcn replacement | DEFERRED; not S2 scope | §AI; no S1 replacement need | Refine/react-admin | avoids unproved rewrite; contracts preserve later option | none | executable/generalized console is authorized |
| AD-08 | Relational dictionary + FTS; graph/RDF rejected for MVP | APPROVED (evidence-backed) | REG §9 | Neo4j/Kuzu/Memgraph/rdflib | laziest defensible; additive interop later | none | if interop need appears |
| AD-09 | FIBO as legal seed source; no glossary scraping | APPROVED | REG §9 | Investopedia scrape | clean licensing | none | annually |
| AD-10 | Idempotent command first; then bounded SQLite-table jobs/local scheduling; no broker | APPROVED S2 | S1 decision; §S | Prefect/Dagster/Temporal/broker now | minimal ops; scheduling gated by proved reuse | S2 first batch command | queue saturation/multi-machine need |
| AD-11 | Multi-sample AI benchmarking (no determinism assumption) | APPROVED | REG §7 (CG-07) | single-run + seed | honest variance; higher cost per benchmark | none | on provider policy change |
| AD-12 | MLflow-backed null/mock eval trace only; real-provider harness/router deferred | APPROVED S2 boundary | S1 mock-only lineage/eval evidence | paid provider/framework adoption | preserves trace contract without unsupported quality claim | passed mock plumbing | before credentials/paid runs |
| AD-13 | Venue connectivity test ranking: Kraken, Binance, OKX ↑, Coinbase ↓ (pending RG-05) | PROVISIONAL | REG §6, CG-05 | package's original ranking | Israel-fit realism; human gate unchanged | none (S1 needs no venue) | before S3 |
| AD-14 | Databento reclassified: future equities/futures only, not crypto | APPROVED | REG §6 (CG-06) | keep as crypto candidate | corrects stale assumption | none | at Phase-3 planning |
| AD-15 | backtesting.py, Backtrader, W&B, Kuzu, Memgraph, Skosify, Temporal(MVP), graph-DBs(MVP) rejected | APPROVED | REG §1–§9 | — | narrows candidate space with evidence | none | 90d registry sweep |

### Custom Build Gate (mandatory template for any Build Custom decision)

A Build Custom decision must document: (1) capability statement; (2) ≥3 reuse candidates evaluated with evidence; (3) the specific insufficiency of each; (4) the smallest custom scope that closes the gap; (5) maintenance cost acknowledgment; (6) exit strategy. Currently justified custom domains (North Star §15, re-affirmed with 2026-07-06 registry evidence — no existing tool owns these semantics): Trading Evidence Registry, Approval Engine, evidence-linked Memory, Research Asset semantics, AI↔economic-outcome linkage, canonical strategy spec + converters. Everything else defaults to reuse.

## §R Research references — strategy discovery & methodology (added 2026-07-12)

External research on how professional funds, quants, and bots discover and run
strategies is catalogued in `research/SOURCE_REGISTRY.md` → "Strategy-discovery &
methodology research" (9 sources: alpha-factor research, backtest-overfitting
validation, retail-vs-pro execution/risk, funding-rate carry, multi-timeframe &
ensemble design). These feed future research/strategy/signal features and are
indexed in graphify. They are methodology inputs only — every strategy still owes
the G1–G11 + production-G10 (DSR ≥ 0.95) gates; `execution_authority` stays NONE.
Strategic implication recorded: shift from predictive price alpha (DSR-failing here)
toward NON-predictive structural yield (delta-neutral funding carry) and ensembles.
