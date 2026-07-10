# Trading Intelligence OS — Decision Log

## 2026-07-05

### D-001 — Market sequence
Decision: Crypto Spot -> Crypto Perpetual Futures -> US Stocks/ETFs.
Reason: best current fit for proof-first MVP, frequent/intraday strategies, and strong reuse ecosystem; leverage/derivatives deferred until base validation machinery is proven.
Status: Approved.

### D-002 — Reuse before build
Decision: no meaningful custom capability may be approved until existing implementations, tools, libraries, APIs, frameworks, academic methods, reference projects, and adjacent solutions are researched.
Status: Approved hard rule.

### D-003 — Dashboard as operating system
Decision: dashboard is the primary project control surface for markets, ideas, knowledge, strategies, research, tests, approvals, paper/live trading, risk, data, tools, AI, and memory.
Status: Approved.

### D-004 — Dictionary & Concepts
Decision: create a first-class trading/markets/investment dictionary plus semantic ontology; terms are context-aware and source-aware.
Status: Approved.

### D-005 — AI Model & Agent Intelligence
Decision: benchmark models and agent configurations by task, cost, latency, quality, stability, downstream value, and economic contribution. Track exact versions and provenance.
Status: Approved.

### D-006 — Research Assets
Decision: reusable high-value AI research outputs become durable, freshness-tracked assets used across the OS.
Status: Approved.

### D-007 — Architecture timing
Decision: no final implementation architecture before deep discovery and evidence-backed bake-off.
Status: Approved.

### D-008 — Coding-agent handoff timing
Decision: do not hand current North Star to a coding agent with an open-ended build mandate. First complete ecosystem/reuse discovery and bake-off blueprints.
Status: Approved.

### D-009 — Composable reuse direction
Decision: do not seek one monolithic engine for the whole OS. Separate execution-grade engines, rapid research accelerators, crypto-native frameworks, experiment lineage, and AI evaluation concerns; compose only after bake-off evidence.
Status: Approved planning direction; exact architecture unresolved.

### D-010 — Experiment lineage should reuse existing infrastructure
Decision: MLflow and DVC/lakeFS-class tools must be evaluated before any custom experiment/data lineage system is built.
Status: Approved reuse gate.

### D-011 — Strategy sources are hypothesis sources, not profit evidence
Decision: academic libraries, GitHub, Pine/TradingView, Hummingbot, QuantConnect and public strategy repositories may seed hypotheses and implementations, but claimed profitability never transfers into our evidence score.
Status: Approved hard rule.


### D-012 — Use role-based engine bake-off
Decision: first bake-off compares Freqtrade, NautilusTrader, LEAN, and Hummingbot under a common matrix while allowing specialized-role outcomes; vectorbt is evaluated separately as a research accelerator.
Status: Approved planning decision; execution pending.

### D-013 — Freqtrade promoted to first-tier Crypto Spot candidate
Decision: Freqtrade receives first-tier bake-off status because current official tooling includes backtesting, dry-run, hyperoptimization, lookahead analysis, and recursive analysis relevant to the MVP.
Status: Approved candidate promotion, not final selection.

### D-014 — Existing Strategy Registry
Decision: create a persistent registry that ingests academic, official framework, open-source, TradingView/Pine, community and other strategy sources with provenance and source class; every entry starts unvalidated internally.
Status: Approved.

### D-015 — Exchange remains unresolved
Decision: no live Crypto Spot exchange is approved until Israel eligibility, API access, fees, products, automated-trading terms, operational reliability, and account-level availability are verified.
Status: Approved gate.

### D-016 — Generic MLOps below custom evidence semantics
Decision: evaluate MLflow/DVC-class tooling for generic run/data lineage; keep strategy-market-timeframe approval, contradiction, promotion, paper/live divergence and Research Asset reuse in a custom Trading Evidence Registry.
Status: Approved design direction; exact tool selection pending executable prototype.


### D-017 — Separate technical venue shortlist from operator eligibility
Decision: venue API capability may be shortlisted before account eligibility, but no venue becomes live-approved until Israel/operator/account/product eligibility is directly verified.
Status: Approved hard gate.

### D-018 — Tiered market-data acquisition
Decision: use the cheapest data tier capable of falsifying a hypothesis; Tier 0 native/basic data first, normalized multi-venue data when needed, tick/order-book data only for justified microstructure/execution questions, and future multi-asset providers later.
Status: Approved.

### D-019 — MLflow + DVC prototype hypothesis
Decision: prototype MLflow for run/metric/artifact/AI trace tracking and DVC for dataset/large-artifact reproducibility beneath a custom Trading Evidence Registry. No final selection until executable acceptance gates pass.
Status: Approved prototype direction.

### D-020 — Manual strategy ingestion before mass automation
Decision: run a mixed 10-item manual seed batch across academic, official framework, open-source and Pine sources before building large-scale strategy ingestion/scraping.
Status: Approved.

### D-021 — Frozen AI benchmark suite with leakage controls
Decision: AI/agent evaluation V1 uses frozen corpora, controlled and best-configuration modes, longitudinal reruns, and masking/time-aware leakage controls where appropriate. Raw trading profit is not sufficient evidence of model skill.
Status: Approved.

### D-022 — Public canonical data for first bake-off
Decision: use official Binance public Spot data as the first canonical reproducible dataset source for BTCUSDT/ETHUSDT candle-level engine parity tests; paid microstructure data remains deferred until justified.
Status: Approved for prototype.

### D-023 — Scenario-based fee/slippage validation
Decision: prohibit single optimistic transaction-cost assumptions; use diagnostic zero-cost plus baseline and stress fee/slippage grids defined in `specs/FEE_AND_SLIPPAGE_ASSUMPTION_PACKAGE_V1.md`.
Status: Approved hard rule.

### D-024 — Live venue approval is not a prototype blocker
Decision: exact operator/account/product eligibility remains a mandatory human gate before live use, but does not block no-money engine/data/lineage prototypes.
Status: Approved.

### D-025 — Coding-agent readiness
Decision: preparation is sufficient for constrained coding-agent prototype execution because remaining major uncertainties are executable rather than desk-research questions.
Status: Approved. See `decisions/CODING_AGENT_READINESS_GATE_V1.md`.

### D-026 — Minimal evidence dashboard before full product UI
Decision: next phase may build only a minimal read-only evidence/control surface; full product information architecture implementation remains deferred until prototype decisions.
Status: Approved.

### D-027 — Single operational SSOT for coding agent

*(Renumbered from a duplicate "D-022" on 2026-07-06; see D-031. Content unchanged.)*

**Decision:** `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md` is the sole operational controller/source of truth for coding-agent execution. All other project files are subordinate according to its explicit precedence hierarchy.

**Reason:** Prevent authority drift and conflicting interpretations across North Star, state, decisions, specs, and research notes.

**Status:** Approved.

### D-028 — Mandatory pre-code environment and credentials intake

*(Renumbered from a duplicate "D-023" on 2026-07-06; see D-031. Content unchanged.)*

**Decision:** Before any implementation code, scaffolding, or install-driven execution begins, the coding agent must run `specs/ENVIRONMENT_AND_CREDENTIALS_INTAKE_GATE_V1.md`. Every anticipated credential/config item must independently allow `Configure now`, `Add later`, `Do not use`, or `Not sure — recommend`.

**Secret rule:** Secret values are never pasted into chat or committed; they are configured locally in ignored environment files or an approved secret store.

**Scope rule:** No live-trading or withdrawal-enabled keys may be requested during the current no-money prototype phase.

**Status:** Approved.

## 2026-07-06 — Planning-mandate pass

### D-029 — Canonical dataset amendment: Binance timestamp unit boundary
Decision: `specs/CANONICAL_BAKEOFF_DATASET_V1.md` is amended (Amendment A1 in the spec): Binance Spot public data files switched timestamps from milliseconds to microseconds starting with files dated 2025-01-01; normalization (converter C5) must detect units explicitly and a golden test must cover the boundary window.
Evidence: official binance-public-data repository, checked 2026-07-06 (`research/EXISTING_CAPABILITY_REGISTRY.md` §6, CG-03).
Status: Approved.

### D-030 — Planning system adopted as subordinate authority layer
Decision: the planning artifacts created 2026-07-06 (`docs/architecture/AD.md`, `docs/architecture/MODULE_CATALOG.md`, `docs/architecture/TYPE_AND_CONTRACT_CATALOG.md`, `docs/program/PROGRAM_PLAN.md`, `docs/product/MVP_SCOPE.md`, `docs/testing/TEST_MASTER_PLAN.md`, `docs/traceability/TRACEABILITY_MATRIX.md`, `docs/ai/AGENT_ROLES.md`, `skills/`, `TODO.md` + `todos/`, `research/EXISTING_CAPABILITY_REGISTRY.md`, `research/RESEARCH_GAP_MATRIX.md`, `audits/`) are subordinate planning authorities under the existing SSOT precedence (slotting with specs/decisions per the SSOT §0 update of the same date). They do not create a competing controller. Maturity labels inside AD.md (APPROVED/PROVISIONAL/UNRESOLVED) are binding.
Status: Approved.

### D-031 — Decision-log ID hygiene correction
Decision: duplicate IDs "D-022"/"D-023" (second occurrences, SSOT + intake-gate decisions) renumbered to D-027/D-028 with content unchanged; original D-022 (public canonical data) and D-023 (scenario-based fee/slippage) retain their IDs. Future entries take the next free ID; amendments must reference the amended ID. A uniqueness check joins the local gate (REQ-032).
Status: Approved.

### D-032 — Registry-driven candidate adjustments (evidence-refreshed 2026-07-06)
Decision, per `research/EXISTING_CAPABILITY_REGISTRY.md`:
1. vectorbt OSS reactivation (v1.x, 2026) reverses the "PRO likely required" assumption; the accelerator probe targets OSS first (license text verification RG-03 gates the lane).
2. Backtrader (abandoned 2023) and backtesting.py (stalled, AGPL) are Rejected as platform components.
3. Databento is reclassified: future multi-asset (equities/futures) candidate only; not a crypto-spot data candidate.
4. Venue connectivity-test ranking provisionally adjusted: OKX promoted (Israel explicitly supported + demo environment), Coinbase demoted pending RG-05 verification; Kraken/Binance unchanged. Live-venue approval gates are untouched (D-015/D-017 stand).
5. W&B rejected for lineage (self-host licensing conflicts with local-first); MLflow+DVC hypothesis retained and strengthened (MLflow 3.x GenAI tracing; DVC stewardship moved to lakeFS 2025-11 — reverify trigger set at S2).
Status: Approved as registry/planning adjustments; none of these are final architecture selections (prototype evidence still governs — D-007, D-019, D-025).

## 2026-07-07 — Governance re-check

### D-033 — Decision-ID uniqueness gate coverage fix
Decision: D-027 and D-028 used `##` headings instead of `###`, so `tests/test_decision_ids.py` (regex `^### (D-\d{3})`) silently excluded them from the uniqueness check. Normalized both to `###` to match convention; no content change. All 32 decision IDs are now covered by the gate.
Status: Approved (governance fix, gov-02 task).

## 2026-07-10 — Product integration direction

### D-034 — Staged TradingView and market-workspace integration
Decision: use an attributed TradingView Widget for the immediate S1 read-only market monitor; prefer TradingView Lightweight Charts plus the OS-owned datafeed for S2 strategy/evidence overlays; evaluate TradingView Trading Platform and Broker API only as a restricted S4 option after access, licensing, venue, risk, and human approval gates. Do not treat any TradingView library as a market-data entitlement or allow chart UI to bypass the OS risk/approval backend.
Evidence: official TradingView Widget, Advanced Charts/Datafeed, Trading Platform/Broker API, bracket-order documentation, and Lightweight Charts Apache-2.0 repository reviewed 2026-07-10; see `docs/product/TRADING_OS_PRODUCT_ROADMAP.md`.
Alternatives: immediate full Trading Platform integration (blocked by access/licensing and premature for S1); custom chart from scratch (unnecessary); third-party chart library (less aligned with existing TradingView direction).
Status: Approved staged direction; S1 widget implementation is read-only, Lightweight Charts and Trading Platform remain conditional on their stage gates.

### D-035 — Local lineage composition selected from executable prototype
Decision: reuse MLflow for local run/metric/artifact/AI-trace tracking and native comparison, reuse DVC for dataset snapshot/restoration, and keep trading approval semantics in the thin custom Trading Evidence Registry. The tools remain adapter-isolated from the product runtime. Test B proves mock-provider trace plumbing only; real-model quality remains credential- and evaluation-gated.
Evidence: `artifacts/lineage/prototype/prototype_result.json` and `artifacts/reports/LINEAGE_PROTOTYPE_REPORT.md`; all seven prototype gates evaluated on 2026-07-10. The S2 retention, backup/restore, migration, and loopback/operator-only access policy is now locked in AD §P / D-037.
Status: Approved for S1/S2 architecture input; S2 policy resolved by D-037. Clean-checkout restore/replay remains an S2 exit verification item, not an unresolved architecture decision.

### D-036 — HG-2 approved for constrained S2 autonomous research-lab entry
Decision: the operator's 2026-07-10 message explicitly approves HG-2 and authorizes
constrained S2 architecture and research-console work for the autonomous research/test
lab: sourced strategy research, reproducible offline backtesting, retained-trial scoring,
validation, and preparation for a possible later demo. Execution follows
`docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md`.

Boundaries: this decision approves no strategy. B2 remains
`INCOMPLETE_NOT_APPROVABLE` and rejected for paper. It activates no synthetic wallet,
paper/demo/testnet venue connection, credentials, order routing, live trading, or
real-money capability. AI may support research but cannot approve a strategy, authorize
an execution state, or trade. Any later demo activation requires the S2 exit predicate,
HG-3, complete validation and risk evidence, a security pass, and a new operator approval
for the specific integration.

Status: **HG-2 APPROVED — constrained S2 entry authorized.**

### D-037 — S2 architecture lock
Decision: lock S2 to a local-first modular monolith with ports/adapters, one CLI
application boundary, and a read-only console. Use SQLite in WAL mode for operational
state; PostgreSQL 18 is only a measured migration candidate after a write loss/failure
beyond the SQLite retry budget, p95 write latency above 500 ms in three consecutive
complete batches, or an approved multi-host/concurrent-writer requirement (AD §P).
Keep analytical data in Parquet queried with DuckDB. Keep MLflow
and DVC behind lineage ports, with the custom Trading Evidence Registry storing only
stable public references.

Jobs begin as bounded, deterministic, allowlisted commands. No persisted schedule is
enabled until the identical command has demonstrated real idempotent reuse with
failure preservation; any later local scheduler remains bounded and SQLite-backed.
Engine roles are: vectorbt research accelerator; Freqtrade isolated Crypto Spot
event/reproduction lane; NautilusTrader bounded event-simulation lane; Hummingbot
deferred bot-operations/market-making candidate; and LEAN deferred multi-asset
portability candidate. Deferred adapters and normalized artifacts are retained as
evidence-only/deferred assets rather than deleted; they have no general S2 execution
authority.

The S2 product boundary is the existing replaceable read-only console plus inert typed
trading-domain contracts. There is no HTTP mutation route, venue client, credential,
synthetic wallet, paper/demo/testnet connection, order-routing path, live command, or
real-money capability. This lock activates only initiatives 13, 14, 17, and 19 for
their bounded S2 slices; initiative 12 remains deferred because full ontology work is
not required by this architecture.

Evidence: retained S1 engine, lineage, data, dashboard, validation, and stage-exit
evidence; the completed five-track S2 architecture audit; `docs/architecture/AD.md` and
`docs/architecture/TYPE_AND_CONTRACT_CATALOG.md` as locked on 2026-07-10.
Status: **APPROVED FOR S2.** This closes the architecture-lock decision. Later retained
S2 evidence includes real LAB-702/LAB-799 research batches and persisted read-only jobs,
but strategy validation remains incomplete/not approvable and S2 has not exited.
