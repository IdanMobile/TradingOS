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

## 2026-07-11 — API contract clarification

### D-038 — Single audited operator workspace-decision route (AD §AI / type catalog §7 clarification)
Decision: the operator approves keeping `POST /api/v1/workspace-actions/decision` and
clarifies the intended "no write route" rule. The desired architecture is: no
unrestricted POST/write routes; no AI-autonomous mutation routes; no hidden write
paths; no trading/order-routing writes; no credential, broker, exchange,
paper/demo/live, or real-money mutation through this route. Exactly one narrowly
scoped exception exists: operator-confirmed workspace decisions may use this audited
POST route. Constraints (binding): explicitly operator-driven; payloads validated
against a fixed task/option allowlist; writes limited to appending workspace
decision/task state (`artifacts/human_decisions/workspace_decisions.jsonl`);
append-only logged/audited; loopback-only; test-covered
(`tests/test_dashboard.py` pins it as the only allowed write path and rejects all
other POST targets). Any future expansion of this route — new payloads, new write
targets, new methods, or any additional write route — requires a new decision gate.
This is an architecture clarification, not broad approval for write APIs.
Evidence: `artifacts/reports/AD_IMPLEMENTATION_GAP_AUDIT_2026_07_11.md` (T-002-05),
`artifacts/human_decisions/workspace_decisions.jsonl`, operator approval message of
2026-07-11.
Status: **Approved.** Resolves T-002-05; supersedes the blanket GET-only wording in
AD §AI and TYPE_AND_CONTRACT_CATALOG §7 with the scoped rule above.

### D-039 — Delegation of research-direction and reviewer-class decisions to AI
Decision: the operator's 2026-07-11 message delegates to the AI agent the classes of
decision previously flagged as operator-owned where they concern offline research
judgment: research direction/prioritization, seed-reproduction scope rulings (e.g.
accepting or properly modeling the 05/08 tri-state supertrend semantics), evidence
A/B comparisons (timeframe/instrument/fee sensitivity), and analogous
reviewer-class calls. Each AI-made decision of these classes must still be recorded
(decision log or evidence artifact) with rationale and remain reversible.
Human-only actions remain exactly: placing credentials/configuration values into
`.env` (keys, provider/venue config) and starting any wallet-bearing run — demo/
testnet/paper or real money. All existing evidence predicates and gates are
unchanged and still binding: AD §AA's paper/demo/live predicate chain, D-036/D-037
boundaries, the no-real-money rule, and the requirement that no strategy is
promoted without complete approvable validation. Delegation lets the AI *choose
among authorized offline research work*; it does not unlock execution, credentials,
or capital.
Evidence: operator chat message of 2026-07-11 ("human actions are mainly update
values in .env like keys and configurations, and starting real runs with wallet").
Status: **Approved (operator-granted delegation).**

### D-040 — AI-decided research direction: multi-timeframe/instrument seed comparison
Decision (made under D-039): the next offline evidence cycle extends the five
reproduced seed candidates across the full frozen dataset grid — BTCUSDT and
ETHUSDT × 5m/15m/1h — instead of ingesting new sources first. Rationale: the
retained 5m evidence shows uniform ≈ −100% outcomes dominated by fee churn
(tens of thousands of round trips at 20 bps round-trip); the frozen dataset
already contains the lower-frequency tables, so testing whether any reproduced
family survives reduced trading frequency is the cheapest decisive experiment
(an A/B across timeframes with identical rules, fees, and execution model), and
it reuses only already-authorized data and candidates. New-source ingestion
(D-020, manual) remains the follow-up if lower frequencies also fail.
Status: **Approved (AI decision under D-039); evidence cycle recorded in the seed
cycle artifacts.**

### D-041 — Second audited console write: the data-refresh trigger
Decision (operator-requested, 2026-07-12): the local dashboard gains a second write
action beyond D-038's decision route — `POST /api/v1/workspace-actions/data-update`,
which launches ONLY the local `tios.dataset.daily_update` module (a fixed argv; no
parameters, no arbitrary command, no venue/order/credential/money path). It is
loopback-bound like the rest of the console, appends an audit line to
`artifacts/operations/data_update_triggers.jsonl`, and returns immediately. Rationale:
the operator wants to refresh the frozen dataset on demand and see the last-update
timestamp on the console; the action is a bounded, offline data refresh whose only
effect is appending newer bars to the frozen parquet (deterministic from source, so
reproducibility holds). The paired read view `GET /api/v1/operations` (data freshness
+ per-strategy results and last-tested time) writes nothing. Any wider console action
(anything touching venues, orders, credentials, or non-`daily_update` commands)
requires its own decision gate.
Status: **Approved (operator); implemented in `dashboard_api/operations.py` +
`dashboard_ui/server.py`, gate-verified.**

### D-042 — Operator authority-transfer to the AI is DECLINED (gates stay human)
Decision (2026-07-12): the operator, citing "you have more knowledge than me," offered to
let the AI self-authorize (a) the S3 paper-lane activation / HG-3, (b) the S4 perp/margin
capability, and (c) venue selection + paid order-book data procurement. This is DECLINED and
cannot be accepted. Rationale: HG-3/HG-4 and the S3→S4 progression are human-only gates by
D-036/D-037/AD §AA — their entire purpose is that no automated agent can advance itself toward
real-money capability; an AI flipping its own gates voids the guarantee precisely when capital
is at stake. Separately, venue account creation, credential entry, and payment are prohibited
agent actions regardless of authorization. Delegation of *research-direction* decisions (D-039)
does NOT extend to *live-capability* gates. The AI's role stops at producing decision-ready
evidence for a human to act on: the carry robustness + counterparty-stress sweep
(`run_funding_carry_robustness.py`) is that evidence — and it shows the carry is regime-inflated
(8.4%/yr is mostly the 2021 bull; ~break-even in bear/chop) with an unrecoverable 100%
counterparty tail, which strengthens, not weakens, the case for a deliberate human decision.
`execution_authority=NONE` unchanged; no venue, no orders, no credentials.
Status: **Held (AI); no gate crossed. Awaiting explicit human action on S3/S4/venue if desired.**

### D-043 — Paper-lane architecture: local synthetic simulator first, venue testnet after HG-4
Decision (AI reviewer-class under D-039, 2026-07-12; T-015-01 preparation): the S3 paper lane
uses the local `SYNTHETIC_LOCAL_SIMULATOR` (the confined runtime in
`src/tios/services/paper/`) as the first and only lane until HG-4 resolves venue eligibility,
then optionally graduates to a
venue testnet/demo adapter behind the same paper contracts. The locked lane uses Binance public
data-only market observations, synthetic USDT, and local simulated fills only; it has no API
keys, account endpoint, credential, or venue order route. Rationale: a venue testnet requires
account eligibility + API permissions, which are HG-4 human-only facts; until then the local
simulator (no venue, no credentials, synthetic USDT, conservative immutable risk caps) is the
only lawful paper path. T-015-03 pure divergence computation and T-015-04 lifecycle/drill
validation machinery are preparation evidence only; real paper observations and operational
drills remain deferred until gate-approved activation. Evidence: OKX demo confirmed
(REG §6); Binance testnet/demo unconfirmed (post-HG-4 recheck). This is a recommendation
prepared ahead of the gate. The operator's 2026-07-12 implementation direction adopts and locks
this architecture without approving HG-3 or activating any bot; activation still requires both
HG-3 and a validation-approved strategy context. `SIG-VOLUME-BREAKOUT` remains research-only.
Full readiness assessment: `docs/program/S3_READINESS_PACKAGE.md`.
Status: **Architecture approved and locked (operator, 2026-07-12); S3 entry and bot activation
remain pending HG-3 plus a validation-approved strategy context. No authenticated venue/account
connection, no exchange orders, and no credentials; `execution_authority=NONE`,
`venue_connection=NONE`, `paper_orders=DISABLED`, `live_orders=DISABLED`.**

### D-044 — Bounded audited paper-cockpit action route
Decision (operator-requested, 2026-07-12): approve exactly one additional console write route,
`POST /api/v1/cockpit-actions`, for the humanized paper-first cockpit. Its exact action allowlist
is `ACKNOWLEDGE`, `PAUSE_PAPER_ENTRIES`, `RESUME_PAPER_ENTRIES`,
`PAUSE_RESEARCH_SCHEDULE`, and `RESUME_RESEARCH_SCHEDULE`. Acknowledgement is limited to a
known informational or warning item. Pausing paper entries blocks only new local synthetic
entries; existing synthetic positions continue through their governed exit/risk rules. Research
schedule pause/resume changes only future materialization and does not interrupt running work.

The route is loopback-only and accepts same-origin JSON with a strict subject/action allowlist
and required idempotency key. Every accepted action is retained append-only in
`artifacts/human_decisions/cockpit_actions.jsonl`; duplicate keys are idempotent and conflicting
reuse is rejected. This approval adds no force entry, close-position, cancel-order, stop-all,
credential, stage-gate/approval transition, venue, exchange-order, or live-control action. It
does not approve HG-3 or activate a bot, and it preserves `execution_authority=NONE`,
`venue_connection=NONE`, `paper_orders=DISABLED`, and `live_orders=DISABLED`.
Status: **Approved (operator); implemented as the third bounded audited POST route.**

## 2026-07-13 — Supervisory corrective decisions

### D-045 — Correct the production DSR equation and supersede affected numeric evidence
Decision: the DSR non-normality adjustment must use the selected strategy's observed
Sharpe ratio, not the expected maximum noise threshold. The shared implementation and
both comparison implementations are corrected from the primary Bailey/López de Prado
formula. Every dependent DSR artifact must be recomputed or explicitly superseded.

Consequence: prior FAIL decisions remain non-approvable, but their numeric DSR values
are not inherited. No current or future PASS may count toward promotion until the
effective-independent-trial and selection-procedure gaps receive the existing
validation-stats-specialist review.

Evidence: `docs/supervisor/SUPERVISORY_BASELINE_2026-07-13.md`,
`src/tios/validation/multiple_testing.py`, corrected method fixtures, and the
author-hosted primary paper recorded under `SRC-DSR-2014`.
Status: **Approved corrective implementation decision; grants no strategy or execution authority.**

### D-046 — Quarantine unapproved authenticated Bybit demo tooling
Decision: the retained Bybit demo order activity is historical venue-demo evidence,
not an approved S3 qualification run. No durable HG-3, HG-4, validation approval,
security-review approval, or Bybit-specific integration approval exists. The two
authenticated network transports are therefore fail-closed and quarantined before
network access. Injected offline transports remain available for tests.

This correction enforces D-036/D-037/D-042/D-043 and AD §AA; it does not create a new
human approval, discard historical evidence, or imply real-money activity. Any future
reactivation requires the complete matching predicate and a typed adapter/reconciliation
review rather than merely removing the guard.

Evidence: `docs/supervisor/SUPERVISORY_BASELINE_2026-07-13.md` and
`docs/supervisor/IMPROVEMENT_PLAN_2026-07-13.md` (SUP-001/SUP-003).
Status: **Quarantined; current safe stage remains constrained offline S2.**

### D-047 — Govern G10 with one Sharpe metric and explicit hierarchical blocking
Decision: non-annualized per-bar Sharpe is the single governed metric for retained-family
candidate selection, both CSCV/PBO halves, and DSR. Slice sufficient statistics must reproduce
that metric exactly. Raw trials and effective independent trials are separate fields;
family-scope effective trials may use the DSR paper's Appendix-3 average-return-correlation
interpolation only when the complete family return population is retained and correlations are
defined.

This does not complete G10. The pre-lab hypothesis/family, dataset, engine, scenario, and
transformation search was not retained, so no hierarchy-wide dependence estimate exists. B2
and B4 are numeric FAIL diagnostics, B3 is method-blocked, and the overall gate remains
`METHOD_BLOCKED`. No family-scope estimate can stand in for missing hierarchy evidence.

Evidence: `artifacts/validation/G10_CANDIDATE_EVIDENCE_2026_07_13.json`,
`artifacts/validation/seed_candidates/SEED_G10_QC2_ETHUSDT_1H_2026_07_13.json`,
the DSR author paper, and the PBO primary paper recorded in the source registry.
Status: **Approved offline validation contract; no strategy or execution authority.**

### D-048 — Research-only multi-leg identity has no execution semantics
Decision: `CanonicalStrategySpec` may carry an optional research-only multi-leg block with
shared eligibility and typed leg descriptions (instrument kind, `LONG|SHORT`, unique role,
positive notional fraction, and explicit execution assumptions). It requires
`execution_authority=NONE`, cannot coexist with directional long-only entry/exit rules, and is
rejected by the long-only evaluator. Legacy specs preserve their canonical hashes.

This records hypothesis identity only. It creates no paired-order atomicity, venue mapping,
credential, collateral, margin, funding-settlement, liquidation, reconciliation, or order
route. Pure carry-accounting primitives are calculation fixtures, not an active portfolio,
risk engine, backtest verdict, or G12 evidence.

Evidence: `strategies/research/funding-carry-basis-delta-neutral/`,
`src/tios/strategy/spec.py`, and `src/tios/validation/carry_accounting.py`.
Status: **Approved constrained-S2 research representation; execution remains unreachable.**

### D-049 — Future substantive research requires preregistration and complete metadata
Decision: a future substantive strategy campaign must freeze its admitted roster, immutable
data, specs, engines, scenarios, transformations, parameter grids, derived raw-trial count,
selection metric, split/holdout policy, effective-trial evidence policy, and stop rules before
execution. Results must declare full code/data/manifest/spec/campaign/cost/split/all-trial/output
lineage through the fail-closed substantive-research metadata contract.

The first retained instance is the bounded 66-trial B2/B3/B4 reproduction campaign. It does
not recover the historical process that admitted those families and cannot create promotion
evidence. Contract validation checks declarations only and always requires
`execution_authority=NONE` and `promotion_eligible=false`.

Evidence: `research/BASELINE_G10_SEARCH_CAMPAIGN_V1.yaml` and
`src/tios/evidence/provenance.py`.
Status: **Approved future offline-research contract; campaign not run and no authority granted.**

### D-050 — First preregistered G10 campaign completes without a promotable result
Decision: `SEARCH-BASELINE-G10-REPRO-V1` ran from clean commit `7782752` through an
offline runner with no network, venue, credential, or order path. Its declared 66-trial scope is
complete and every family result has immutable all-trial inputs, output hashes, and validated
metadata. B2 and B4
numerically fail; B3 is method-blocked because constant/no-trade trials make correlations and
effective trials undefined. The overall gate remains `METHOD_BLOCKED` because upstream family
admission is unavailable.

The run is a legacy accelerator-proxy reproduction, not canonical strategy conformance:
current-close fills differ from the specs' next-bar-open timing, B2 uses a crossover event rather
than its declared eligible state, and F1/S0 omits slippage. No further parameter expansion of
this proxy population is justified. Any canonical follow-up requires a new preregistration and
F1/S1-or-stricter costs.

Evidence: `artifacts/reports/G10_PREREGISTERED_CAMPAIGN_REPORT_2026_07_13.md` and the
content-addressed index under `artifacts/validation/campaigns/SEARCH-BASELINE-G10-REPRO-V1/`.
Status: **Completed diagnostic; no strategy, promotion, venue, or execution authority.**

### D-051 — Canonical baseline V2 closes B2/B3/B4 expansion and seals future evidence
Decision: `SEARCH-CANONICAL-BASELINE-G10-V2` formally ran from clean commit `6bac8bf`
with no network, venue, credential, or order path. It retained all 67 canonical-rule trials,
the six approved fee/slippage cells, five expanding historical pseudo-OOS folds, family and
campaign-wide PBO/DSR inputs, per-trial turnover, validated provenance sidecars, and a
content-addressed index. A second full computation reproduced every input JSON byte-for-byte.

The corrected economics are decisively negative. B2 fails with PBO 0.5066 and DSR 0; its selected
trial is +3.54% only at F0/S0 and effectively loses all capital at F1/S1. B4 fails with PBO 0.3739
and DSR 0 and is already -96.99% at F0/S0. B3 and the campaign-wide scope select a retained
mathematically inert zero-trade variant; their undefined correlations correctly withhold DSR and
keep them method-blocked. Chronological folds do not rescue B2/B4. No parameter expansion or
result-driven “rescue” of these grids is justified.

The pre-commit implementation smoke that touched full historical data is disclosed in the frozen
contract. V2 is therefore historical reproducibility, conformance, cost-sensitivity, and method
evidence—not an unseen confirmatory result. The only genuinely prospective evidence is sealed from
2026-07-14T00:00:00Z for one evaluation no earlier than 2027-01-14T00:00:00Z; any adaptation after
viewing it requires V3 and a new holdout. The 66 official Binance source archives are portable and
checksum-pinned, and deterministically rebuild the exact retained Parquet.

Evidence: `research/CANONICAL_BASELINE_G10_CAMPAIGN_V2.yaml`,
`artifacts/reports/CANONICAL_BASELINE_CAMPAIGN_V2_REPORT_2026_07_13.md`, and the immutable index
under `artifacts/validation/campaigns/SEARCH-CANONICAL-BASELINE-G10-V2/`.
Status: **Completed negative diagnostic; B2/B3/B4 expansion closed. G10 remains METHOD_BLOCKED;
promotion, venue, order, and execution authority remain absent.**

### D-052 — First source-backed post-V2 family-selection cycle is NO_GO

Decision: `FAMILY-SELECT-V1` compared exactly three economically distinct families before any
new parameter evaluation: delta-neutral funding/basis carry, long-only Spot cross-sectional
momentum, and volatility-managed Spot exposure. None passes every hard admission gate for
mechanism, primary-source identity, point-in-time data, complete capital/cost/risk semantics,
canonical ownership, clean search lineage, adequate sample, and a safe offline route.

Funding/basis carry is rejected for this cycle because public funding, mark, index, and trade
data do not reconstruct historical account-applicable maintenance tiers, liquidation rules,
contract changes, or the complete counterparty/capital model. Cross-sectional momentum is
rejected because a current symbol view is not a delisting-complete point-in-time universe, the
primary evidence is broad-universe long-short rather than Binance Spot long-only proof, and the
local family was already searched on exposed history. Volatility-managed Spot exposure is
rejected because the family already influenced local searches, continuously variable sizing is
not canonically owned, primary literature contains material OOS/cost counterevidence, and no
clean holdout independent of both prior exploration and the V2 seal was identified.

Consequence: the outcome is exactly `NO_GO`. No StrategyVersion, campaign, parameter grid,
dataset acquisition, implementation, bot, venue, order, or authority is created. Task 1 remains
active for a new bounded source/data-feasibility selection cycle. A rejected family may re-enter
only with evidence that directly closes its failed gate; prior performance is not new evidence.

Evidence: `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V1.md`.
Status: **Approved offline research-direction decision under D-039; execution authority remains
NONE and the V2 prospective holdout remains sealed.**

### D-053 — Fresh UTC-weekday family admitted to a frozen offline campaign

Decision: `FAMILY-SELECT-V2` compared exactly three fresh mechanisms without computing local
family performance: BTCUSDT Spot UTC-weekday exposure, fiat-backed stablecoin below-peg
reversion, and Bitcoin-halving exposure. Stablecoin reversion is rejected because redemption,
account, counterparty, and lifecycle semantics dominate the public-price signal. Halving
exposure is rejected because only four historical events exist and the retained dataset contains
one. `FAM-CALENDAR-UTC-01` alone passes the source/data/canonical-feasibility admission gate.

The admitted family is not a validated strategy. Its complete seven-weekday roster, six cost
cells, development/validation/reserved chronology, clock stresses, benchmarks, PBO/DSR method,
hard thresholds, gap exits, stop rules, Decimal reference, and vectorbt accelerator are frozen in
`CALENDAR-UTC-G1-G11-V1` before scoring. Ordinary signals fill only at the exactly adjacent next
open; pending fills expire across gaps and held exposure exits at the first observable open.
The campaign has no network, credential, venue, order, paper, demo, live, or promotion authority
and may not access the sealed V2 prospective holdout.

Evidence: `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V2.md`,
`research/CALENDAR_UTC_DATA_PACKAGE_V1.json`, and
`research/CALENDAR_UTC_G1_G11_CAMPAIGN_V1.yaml`.
Status: **Approved constrained-S2 offline campaign freeze; preregistered and not run.**

### D-054 — UTC-weekday campaign is rejected without rescue

Decision: `CALENDAR-UTC-G1-G11-V1` executed once from clean commit `ecdfb3b` and a second
complete computation reproduced its preregistration, Decimal results, and vectorbt results
byte-for-byte. Development selected Wednesday (`SV-c79226c64f6259c5`). Decimal/vectorbt parity
passed, and the 2024 and nominal 2025–2026H1 segments were positive, but four frozen hard gates
failed: hard-stress economics, absolute drawdown, benchmark superiority, and G10. PBO is 0.7594,
DSR is 0.3012, F2/S3 return is -40.74%, and F1/S1 max drawdown is -41.29%.

The supervisor also found that the runner computed reserve metrics before development selection,
contrary to the frozen select-before-read sequence. Although selection consumed only development
values, the reserve is not operationally untouched. Required Freqtrade/Nautilus conformance was
also absent. These findings reinforce rejection; they cannot be repaired after results.

Consequence: the exact family/context is closed `REJECTED_NOT_PROMOTION_ELIGIBLE`. No alternate
weekday, combination, hour, filter, exit, sizing, cost, threshold, or reserve reinterpretation is
allowed. No bot or human gate is activated.

Evidence: `artifacts/reports/CALENDAR_UTC_VALIDATION_AND_SUPERVISOR_REVIEW_2026_07_13.md` and
the content-addressed campaign directory under
`artifacts/validation/campaigns/CALENDAR-UTC-G1-G11-V1/`.
Status: **Completed negative campaign; execution authority remains NONE.**

### D-075 — Quote-normalized cross-venue BTC premium admitted without scoring

Decision: `FAMILY-SELECT-V8` compared exactly three new mechanisms without computing local family
performance: a quote-normalized Coinbase-versus-Binance BTC Spot premium, U.S. Spot Bitcoin ETP
primary-market flow, and USDt peg-stress conditioning. ETP flow is rejected because the uniform
official point-in-time daily aggregate and independent regime sample are insufficient. USDt peg
stress is rejected as a standalone alpha family because independent stress episodes are sparse and
current issuer/redemption terms make it primarily a changing quote-asset risk state.

`FAM-CROSS-VENUE-USD-PREMIUM-01` alone advances to exact data packaging. It uses completed Coinbase
`BTC-USD` and `USDT-USD` hourly closes to construct a quote-normalized premium versus retained
Binance `BTCUSDT`, then permits only a strictly later unlevered Binance Spot long/cash pulse. The
two-interpretation, three-baseline, two-threshold population is frozen at 12 trials. It is not
simultaneous arbitrage, Coinbase execution, carry, margin, a transfer strategy, or a rescue of any
closed price/order-flow context.

Consequence: exact public Coinbase bytes, provenance, gaps, normalization, and mappings may be
packaged offline before scoring. No premium-conditioned return may be computed until the data and
campaign freeze are committed. No bot, venue session, credential, order, paper/demo/live state,
human gate, sealed V2 holdout access, promotion, or execution authority is activated.

Evidence: `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V8.md`.
Status: **Approved constrained-S2 data build; performance unobserved and authority NONE.**

### D-076 — Cross-venue premium source and normalized data frozen offline

Decision: exact public Coinbase Exchange source bytes are frozen for two official documentation
pages, the online `BTC-USD` and `USDT-USD` product identities, and 378 bounded hourly candle
responses covering the preregistered 2021-05-01 through 2026-06-30 query boundary. Every response
retains URL/query, request/receipt UTC, response date/type, byte count, SHA-256, and original body.
No key, authenticated endpoint, account, or trading session was used.

The deterministic normalizer aligns Coinbase BTC-USD, Coinbase USDT-USD, and the already-retained
Binance BTCUSDT hourly source into 45,193 observations from 2021-05-04T01:00Z through
2026-06-30T23:00Z. It preserves six combined-source gaps, quote-normalizes BTC-USD through the
independent USDt/USD close, calculates only the preregistered contemporaneous log-premium feature,
and proves 45,192 strictly later Binance-open mappings. Rebuilding the normalized Parquet and
package is byte-identical. Offline verification and deliberate raw-byte, logical-hash, and mapping
drift tests pass.

Consequence: minimal canonical roles and an immutable G1-G11 campaign may now be built without
scoring. No premium-conditioned future return has been computed. No bot, credential, venue trading
session, order, paper/demo/live state, sealed V2 holdout access, promotion, human gate, or execution
authority is activated.

Evidence: `research/CROSS_VENUE_BTC_PREMIUM_DATA_PACKAGE_V1.json`, retained raw/normalized data,
`scripts/verify_cross_venue_premium_data.py`, and `tests/test_cross_venue_premium_data.py`.
Status: **Verified offline data package; performance unobserved and authority NONE.**

### D-077 — Cross-venue premium canonical campaign frozen behind selection barrier

Decision: `CROSS-VENUE-BTC-PREMIUM-G1-G11-V1` is fully specified before any
premium-conditioned future return is computed. Twelve content-derived StrategyVersions exhaust the
two-interpretation, three-baseline, two-threshold roster. Canonical Decimal timing and an independent
Decimal ledger are paired with isolated vectorbt, Freqtrade-environment dataframe, and
Nautilus-environment event-order roles. Causal micro-goldens cover strict-later fills, polarity,
zero variance, gap reset, non-extending six-hour exits, and two-sided cost accounting.

The runner freezes six cost cells, development/validation/reserve chronology, six period slices,
trade minima, one-bar delay, benchmark, drawdown, PBO/DSR, parity, and G1-G11 thresholds. Phase one
may evaluate all 12 trials on development only and must write a content-addressed selected-version
artifact. Phase two refuses validation, reserve, full-history, or period evaluation without that
verified artifact. Offline preflight, data verification, focused tests, strict mypy, and isolated
engine import checks pass.

Consequence: one clean-commit offline historical run is authorized. Numeric output cannot
self-promote and G11 remains an independent supervisory decision. No bot, credential, venue trading
session, order, paper/demo/live state, HG-3, sealed V2 holdout access, closed-family reuse, or
execution authority is authorized.

Evidence: `research/CROSS_VENUE_BTC_PREMIUM_G1_G11_CAMPAIGN_V1.yaml`, canonical/engine roles, and
focused tests under `tests/test_cross_venue_premium_*`.
Status: **Approved constrained-S2 immutable offline campaign; preregistered and not run.**

### D-078 — Cross-venue premium campaign rejected without rescue

Decision: the clean run from `2cb84c8` preserved the hashed development-selection barrier and
selected continuation-positive / 168 hours / 2.0 z. Development lost 56.08%, validation lost 8.29%,
reserve lost 24.12%, full primary lost 69.44%, full stress lost 96.50%, and a one-bar delay lost
72.99%. Zero of six periods is positive; full drawdown is 73.45%. Four-role parity passes, and PBO
passes at 0.1003, but DSR is 0.00000395 and G5-G10 fail.

Consequence: G11 rejects the exact quote-normalized cross-venue premium context without tuning,
reinterpretation, or migration to sub-hour/arbitrage execution. It is not validation-approved or
promotion eligible. No bot, credential, venue trading session, order, paper/demo/live state, human
gate, sealed V2 holdout, closed-family context, or execution authority was activated.

Evidence: `artifacts/reports/CROSS_VENUE_BTC_PREMIUM_VALIDATION_AND_SUPERVISOR_REVIEW_2026_07_13.md`.
Status: **Completed negative campaign; execution authority remains NONE.**

### D-079 — Current autonomous public-signal mining boundary closed NO_GO

Decision: `FAMILY-SELECT-V9` compared exactly three unclosed mechanisms without computing local
family performance: point-in-time exchange flows, forced-liquidation stress, and the regulated CME
Bitcoin futures curve. Exchange-flow labels require an authenticated proprietary PiT product and
cannot be reconstructed from ownerless UTXOs. Binance's official BTC liquidation snapshots are a
throttled, non-exhaustive series covering only 472 days from 2023-06-25 through 2024-10-14. CME
curve semantics are authoritative, but complete historical contract/settlement data require an
entitled DataMine or licensed MDP source plus a derivative capital model.

Consequence: all three are `NO_GO` at the current public, keyless, reproducible, Spot-compatible
boundary. After eight bounded source cycles, seven admissions, and no promotion-eligible completed
campaign, autonomous public-signal mining stops rather than increasing the hidden family-search
burden. Research may reopen only for new exogenous evidence: an operator-supplied fully sourced
strategy and unseen data, approved authoritative data access, or genuinely prospective evidence
collected under preregistration. Another public-family sweep, copied result, rejected-family
ensemble, or same-history parameter search is not authorized.

No Task-2 build, bot, credential, venue session, order, paper/demo/live state, human gate, sealed
holdout access, promotion, or execution authority is activated.

Evidence: `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V9.md`.
Status: **NO_GO; autonomous public-signal mining paused at evidence boundary; authority NONE.**

### D-080 — Prospective BTC liquidation-stress risk signal frozen before observation

Decision: D-079's prospective-evidence reopen condition is used without reopening historical
performance. `PROSPECTIVE-BTC-LIQUIDATION-STRESS-V1` observes the public unauthenticated Binance
BTCUSD_PERP forced-order snapshot stream in UTC-aligned five-minute windows. It retains exact
messages and exchange-info bytes, validates the active instrument and USD 100 contract size, uses
accumulated filled contracts, deduplicates an exact event identity, and explicitly labels the
source as a throttled latest-one-per-second snapshot rather than a complete liquidation tape.

The single frozen risk hypothesis uses 8,640 consecutive complete prospective windows as a
30-day baseline. Gross snapshot notional must strictly exceed its prior nearest-rank 99th
percentile and one side must represent at least 80%. Sell-dominant stress is a block-new-long risk
state; buy-dominant stress and normal states are observation-only. Source gaps and warm-up are
`FLAT/BLOCK`. Independently, every state remains action-blocked while
`promotion_eligible=false`.

Consequence: a bounded keyless public-market-data observer may run only after this freeze is
committed. The first statistical review is no earlier than both 180 calendar days and 50
sell-dominant stress events, after complete warm-up and source-gap evidence. No historical archive
backfill, rule change, score, order proposal, synthetic paper state, venue session, credential,
human gate, or execution authority is created.

Evidence: `research/PROSPECTIVE_BTC_LIQUIDATION_STRESS_SIGNAL_V1.yaml`,
`src/tios/strategy/liquidation_stress.py`, and
`scripts/run_prospective_liquidation_observer.py`.
Status: **Prospective signal preregistered; observation not started; authority NONE.**

### D-081 — First prospective signal session retained FLAT and blocked

Decision: after D-080 was committed at `2e385a8`, one fixed-endpoint, unauthenticated 30-second
BTCUSD_PERP public-market-data session completed. The exact exchange-info response confirms the
active perpetual identity and USD 100 contract size. No forced-order snapshot arrived; under the
official publication semantics this is a valid zero-event interval, not a zero-liquidation market
claim. The content-addressed session emits deterministic signal
`SIG-495ecfb03d8003161565ea47` as `FLAT / PROSPECTIVE_SOURCE_WINDOW_INCOMPLETE`.

Consequence: the prospective boundary is now active, but no complete five-minute window, warm-up,
label, metric, scorecard, or promotion evidence exists. Independent risk remains `BLOCK` because
the window is incomplete and promotion is false. Exact session/raw hashes verify; no account,
credential, order, fill, position, paper runtime, authenticated venue session, human gate, or
execution authority changed.

Evidence: `artifacts/reports/PROSPECTIVE_BTC_LIQUIDATION_STRESS_FIRST_SESSION_2026_07_13.md`
and the content-addressed files under
`artifacts/prospective/BTC-LIQUIDATION-STRESS-V1/`.
Status: **Prospective observation started; warm-up incomplete; FLAT/BLOCK; authority NONE.**

### D-082 — Prospective observer V2 frozen for complete-window evidence

Decision: the D-081 short-session result exposed an operational evidence gap, not a signal result:
V1 retained a valid incomplete interval but could not assemble fully covered five-minute windows.
Observer V2 inherits the exact D-080 signal specification hash and changes no source, feature,
threshold, baseline, state, label, review, or promotion term. It separately records WebSocket
coverage, admits only fully enclosed UTC windows, preserves valid zero-event windows, requires an
immediately consecutive 8,640-window baseline, and reconstructs every session/raw/window/signal/
risk/authority hash offline.

The verifier passes the retained V1 session and deliberately rejects both a one-byte mutation and
a rehashed semantic mutation that enables paper orders. Overlapping windows, failed/disconnected
sessions, source drift, and incomplete coverage fail closed.

Consequence: after this operational-only freeze is committed, one bounded public session may wait
for and retain exactly one complete five-minute window. It must remain warm-up `FLAT/BLOCK`; no
metric or score is authorized. No credentials, account session, order, paper/demo/live state,
human gate, promotion, or execution authority is created.

Evidence: `research/PROSPECTIVE_BTC_LIQUIDATION_OBSERVER_V2.yaml`, updated observer/parser, and
`tests/test_prospective_liquidation_observer.py`.
Status: **Observer V2 frozen and unrun; signal rule unchanged; authority NONE.**

### D-083 — First complete prospective risk-signal window retained

Decision: one `--complete-windows 1` session ran only after observer V2 was frozen at `eaf2604`.
Continuous public WebSocket coverage enclosed `[2026-07-13T18:45:00Z,
2026-07-13T18:50:00Z)`. The source published zero BTCUSD_PERP forced-order snapshots; V2 correctly
retains this as one complete zero-event window while preserving the source's throttled-snapshot
limitation. Both retained sessions reconstruct offline.

The deterministic result is `SIG-54b9c184a05a3a037df6495d`, `FLAT`, and `WARMUP_BLOCK`. The
required 8,640-window baseline is absent. Independent risk is `BLOCK`; metric, scorecard, and
promotion eligibility remain false.

Consequence: the prospective source→window→signal→risk-denial path is now operationally proven for
one complete window. This is not strategy validation or paper activation. Future-label semantics
and ongoing append-only coverage are next; no scoring is allowed during warm-up. No credential,
account session, order, fill, position, paper/demo/live state, human gate, promotion, or execution
authority was activated.

Evidence: `artifacts/reports/PROSPECTIVE_BTC_LIQUIDATION_STRESS_FIRST_COMPLETE_WINDOW_2026_07_13.md`
and content-addressed session `2f582162…`.
Status: **One complete prospective window; warm-up FLAT/BLOCK; authority NONE.**

### D-084 — Causal prospective Spot label contract frozen before evaluation

Decision: future labels for every retained complete liquidation-signal window are fixed before
their values are evaluated. The source is the unauthenticated Binance Spot `BTCUSDT` one-minute
kline endpoint. Entry is the open at window close plus one minute; exits are the opens exactly
1h, 6h, and 24h after entry. A label is `NOT_AVAILABLE` and triggers no request until the exit bar
has completed one minute later. Exact response bytes, timestamps, prices, returns, session links,
contract hash, and authority boundary must reconstruct offline.

Consequence: one first causal label evaluation may run only from the clean freeze commit. During
the 8,640-window warm-up, available returns are retained but may not be aggregated, analyzed,
scored, or used to change the signal. Early labels, absent exact candles, byte drift, and rehashed
future-time or authority drift fail closed. No historical backfill, V2 holdout access, bot, venue
connection, credential, order, paper/demo/live state, promotion, or execution authority is
authorized.

Evidence: `research/PROSPECTIVE_BTC_LIQUIDATION_LABEL_CONTRACT_V1.yaml`,
`scripts/run_prospective_liquidation_labels.py`, and focused causal/drift tests.
Status: **Label contract frozen, not yet evaluated; authority NONE.**

### D-085 — First causal label evaluation retained without future leakage

Decision: the first evaluator run began from clean freeze commit `a09d308` at
`2026-07-13T19:00:07.914601Z`. The 1h, 6h, and 24h labels for the retained complete signal window
were all before their frozen availability times, so the evaluator retained three explicit
`NOT_AVAILABLE` rows and made no Spot kline request. The content-addressed snapshot reconstructs
offline with metric, scorecard, and promotion eligibility false.

Consequence: the prospective source→window→signal→risk-denial→causal-label-scheduling path is
proven, but no outcome or strategy edge exists. The first lawful outcome request is the 1h label
at or after `2026-07-13T19:52:00Z`. Warm-up analysis, backfill, tuning, and scoring remain
prohibited. No credential, venue connection, order, paper/demo/live state, human gate, promotion,
sealed V2 holdout access, or execution authority was activated.

Evidence: `artifacts/reports/PROSPECTIVE_BTC_LIQUIDATION_LABEL_FIRST_EVALUATION_2026_07_13.md`
and content-addressed label snapshot `7d96d32a…`.
Status: **First label schedule retained; all outcomes NOT_AVAILABLE; authority NONE.**

### D-086 — Append-only label verifier correction frozen before refresh

Decision: after a later complete source window was retained, the unchanged label evaluator failed
closed before writing output because V1 compared the older `19:00:07Z` snapshot with all source
windows currently present, including a window that closed at `19:10Z`. This is an operational
reconstruction defect: append-only future evidence must not retroactively make a valid historical
snapshot incomplete.

Verifier V2 reconstructs each immutable snapshot against only complete windows whose close is no
later than that snapshot's own `evaluated_at`. The frozen source, entry, horizon, availability,
return, warm-up, and authority rules are unchanged. A regression test proves an older snapshot
remains valid after a later window is added; all early-label and authority drift tests remain.

Consequence: after this correction is committed, the failed refresh may be rerun. It created no
snapshot and exposed no future label. No backfill, analysis, score, strategy change, credential,
venue connection, order, paper/demo/live state, promotion, or execution authority is authorized.

Evidence: `research/PROSPECTIVE_BTC_LIQUIDATION_LABEL_VERIFIER_V2.yaml`, updated verifier, and
`tests/test_prospective_liquidation_labels.py`.
Status: **Operational verifier correction frozen and unrun; label contract unchanged.**

### D-087 — Second complete window retained; continuity not overstated

Decision: a public session from run commit `e831172` continuously enclosed
`[2026-07-13T19:05Z,19:10Z)` and retained a second valid zero-event complete window. It emitted
`SIG-142d08b4d8620e0ff682d7f5`, `FLAT`, `WARMUP_BLOCK`, and independent `BLOCK`. Because the prior
complete window ended at `18:50Z`, the two observations are not consecutive; the longest valid
warm-up chain remains one window.

The first label refresh failed closed without output, D-086 was committed at `7cc6ef0`, and the
post-freeze refresh then retained six `NOT_AVAILABLE` rows for the two windows. Both old and new
label snapshots reconstruct offline, proving append-only snapshot-relative verification. No raw
Spot response, price, or return was requested because every horizon was still future.

Consequence: continuous prospective collection—not the total number of isolated windows—must build
the 8,640-window baseline. The first lawful 1h outcome remains due after `19:52Z`. No analysis,
score, rule change, credential, venue connection, order, paper/demo/live state, promotion, or
execution authority is authorized.

Evidence: `artifacts/reports/PROSPECTIVE_BTC_LIQUIDATION_SECOND_COMPLETE_WINDOW_2026_07_13.md`,
session `f1655057…`, and label snapshot `f5453680…`.
Status: **Two complete windows total; longest consecutive chain one; authority NONE.**

### D-088 — Opaque continuity failure retained; observer V3 diagnostics frozen

Decision: the bounded seven-window session from commit `0febd4e` covered
`19:16:06Z` through `19:42:55Z` but ended `FAILED_LiquidationStressError`. V2 correctly admitted
zero complete windows from the failed source and emitted deterministic
`FLAT/SOURCE_WINDOW_INCOMPLETE/BLOCK`. The attempted continuity run therefore adds no warm-up
credit.

The underlying cause is unknown: V2 retained only the exception class and discarded the exact
error text and rejected public message. Observer V3 changes only failure evidence, retaining and
offline-reconstructing exception type, message, rejected message, and receipt time. All source,
signal, window, baseline, risk, label, eligibility, and authority semantics remain unchanged.

Consequence: another capture may begin only after V3 is committed. No failed interval may be
partially rescued. No analysis, score, strategy change, credential, venue connection, order,
paper/demo/live state, promotion, or execution authority is authorized.

Evidence: `artifacts/reports/PROSPECTIVE_BTC_LIQUIDATION_CONTINUITY_SESSION_FAILURE_2026_07_13.md`,
session `78e77d1f…`, `research/PROSPECTIVE_BTC_LIQUIDATION_OBSERVER_V3.yaml`, and focused tests.
Status: **Failed continuity session retained with zero windows; V3 frozen and unrun.**

### D-089 — Live force-order schema defect diagnosed; observer V4 frozen

Decision: the first V3 retry failed before a complete window, but V3 retained the rejected public
message and exact error. The message proves the parser defect: live `st: 2` is inside the order
object `o`, while the parser and synthetic fixture incorrectly expected top-level `st`. Binance's
current liquidation-stream documentation likewise nests documented order fields under `o`.

V4 reads `o.st`, corrects the fixture, and versions new sessions as schema 4. The immutable V3
failure remains verifiable as the exact known pre-fix defect. No signal formula, event notional,
window, baseline, label, risk, eligibility, or authority term changes.

Consequence: a clean V4 source retry is authorized only after this commit. Both failed attempts
retain zero windows. No backfill, analysis, score, strategy change, credential, venue connection,
order, paper/demo/live state, promotion, or execution authority is authorized.

Evidence: `artifacts/reports/PROSPECTIVE_BTC_LIQUIDATION_V3_PARSER_FAILURE_2026_07_13.md`, session
`d4278c9b…`, `research/PROSPECTIVE_BTC_LIQUIDATION_OBSERVER_V4.yaml`, official Binance stream
documentation, and corrected tests.
Status: **Parser defect proven and corrected; V4 frozen and unrun; authority NONE.**

### D-090 — First causal 1h label retained without analysis

Decision: from clean commit `e8805cc`, the unchanged evaluator ran after the first window's frozen
`19:52Z` availability boundary. It retained exact BTCUSDT Spot 1m entry/exit response bytes,
opens `62012` and `62196`, and gross arithmetic return `0.002967167644971940914661678`. The other
five scheduled labels remained `NOT_AVAILABLE` and caused no request. All three label snapshots
reconstruct offline.

Consequence: the prospective source→window→signal→risk-denial→causal-outcome path is now proven
for one label. It is one warm-up observation, not a trade, edge, score, strategy validation, or
promotion input. The frozen contract prohibits aggregation or interpretation. No credential,
venue connection, order, paper/demo/live state, holdout access, promotion, or execution authority
was activated.

Evidence: `artifacts/reports/PROSPECTIVE_BTC_LIQUIDATION_FIRST_AVAILABLE_1H_LABEL_2026_07_13.md`,
label snapshot `3a713180…`, and exact raw response hashes `48c1eb72…` / `61e24812…`.
Status: **One causal label retained for warm-up only; eligibility false; authority NONE.**

### D-091 — V4 successful complete window and nine-row label schedule retained

Decision: from clean commit `ab5a088`, observer V4 continuously enclosed
`[2026-07-13T20:00Z,20:05Z)` and retained a schema-4 successful session with
`source_failure=null`. The source published zero snapshots; the deterministic result is
`SIG-a512bf546de4bb5cb3c893c2`, `FLAT`, `WARMUP_BLOCK`, and independent `BLOCK`. This proves the
post-correction success path; the prior exact live record and tests prove `o.st` parsing.

The refreshed label snapshot contains nine rows: the first 1h label remains retain-only and the
other eight are causally unavailable. Three complete windows exist in total, but none form a
multi-window consecutive chain, so warm-up remains 1/8,640.

Consequence: V4 is operational for bounded prospective observation, not validated for persistent
30-day collection or signal usefulness. No analysis, score, strategy approval, credential, venue
connection, order, paper/demo/live state, promotion, or execution authority is authorized.

Evidence: `artifacts/reports/PROSPECTIVE_BTC_LIQUIDATION_V4_FIRST_COMPLETE_WINDOW_2026_07_13.md`,
session `54ea7fae…`, and label snapshot `566efb70…`.
Status: **V4 complete-window path proven; longest chain one; authority NONE.**

### D-092 — Second causal 1h label and additional V4 window retained

Decision: a second successful V4 session from clean commit `fad9997` enclosed
`[2026-07-13T20:10Z,20:15Z)`, retained zero events, set `source_failure=null`, and emitted
`SIG-637b5e49ff85d286959af1be`, `FLAT/WARMUP_BLOCK`, and independent `BLOCK`. Four complete windows
now exist but remain isolated, so the longest warm-up chain is still one.

After the second historical window's frozen availability time, the unchanged evaluator retained
exact Spot opens `62046.51` and `62215.86` and gross arithmetic label
`0.002729404119587064606857017`. The 12-row snapshot now holds two available 1h labels and ten
unavailable labels. No aggregation or interpretation occurred.

Consequence: repeated source/signal/risk/label operation is proven in bounded sessions, but
persistent continuity, adequate sample, strategy edge, score, and promotion are unproven. No
credential, venue connection, order, paper/demo/live state, holdout access, promotion, or execution
authority was activated.

Evidence: `artifacts/reports/PROSPECTIVE_BTC_LIQUIDATION_SECOND_1H_LABEL_AND_V4_WINDOW_2026_07_13.md`,
session `a99a97c1…`, label snapshot `0ee31a1b…`, and exact raw bytes.
Status: **Two causal labels retained without analysis; longest chain one; authority NONE.**

### D-093 — Checkpointed persistent-observation contract frozen before implementation

Decision: repeatedly launching the bounded one-window observer cannot build the frozen 8,640-window
baseline because every process reconnect omits at least one aligned window. Binance also documents
that a COIN-M market-stream connection is valid for only 24 hours. A valid 30-day chain therefore
requires per-window atomic checkpoints plus planned overlapping connection rotation before the
24-hour disconnect.

The V1 operations contract freezes finite runs of at most 8,640 checkpoints, 30-second mutable
heartbeats, one immutable checkpoint per fully enclosed window, overlap-proven rotation at 23h30m,
bounded reconnect backoff, and continuity-epoch reset after any unplanned gap. A disconnect may
discard only its current partial window; checkpoints finalized before it remain immutable. Labels
stay a separate causal process and warm-up analysis remains prohibited.

Consequence: V5 checkpoint implementation and synthetic failure/rotation tests may proceed. No
daemon framework, account session, credential, venue connection, order, paper/demo/live state,
score, promotion, or execution authority is authorized.

Evidence: `research/PROSPECTIVE_BTC_LIQUIDATION_PERSISTENT_OBSERVATION_V1.yaml` and official Binance
COIN-M WebSocket connection documentation retrieved 2026-07-13.
Status: **Persistent-observation contract frozen and unrun; authority NONE.**

### D-094 — Checkpoint observer V5 frozen before public continuity proof

Decision: the D-093 operating contract is implemented as one finite public-data process with one
schema-5 immutable checkpoint per fully enclosed UTC five-minute window and one atomic mutable
heartbeat. Previously finalized checkpoints survive later source failure. An unplanned gap
discards only the partial window and increments continuity epoch; a planned connection rotation
may preserve continuity only when replacement coverage overlaps the handoff boundary.

Offline tests prove two consecutive checkpoints on one synthetic connection, checkpoint
preservation and continuity reset after a synthetic mid-window disconnect, continuity preservation
through a synthetic overlapping rotation, schema-5 reconstruction, and heartbeat authority-drift
rejection. The exact implementation and test hashes are frozen before observing a public result.

Consequence: one clean-commit run requesting exactly two public read-only checkpoint windows is
authorized as operational evidence. It may retain source/checkpoint/heartbeat evidence only. It
cannot aggregate labels, score a signal, validate a strategy, activate a bot, connect an account,
use credentials, create an order, enter paper/demo/live state, access the sealed V2 holdout, or
grant execution authority.

Evidence: `research/PROSPECTIVE_BTC_LIQUIDATION_CHECKPOINT_OBSERVER_V5.yaml`, the V5 scripts, and
focused prospective/safety tests.
Status: **V5 frozen and unrun; first two-window public proof authorized; authority NONE.**

### D-095 — V5 consecutive public checkpoints retained; long warm-up run authorized

Decision: one finite V5 process from clean commit `474fc0c` finalized exactly two consecutive
schema-5 windows, `[2026-07-13T21:10Z,21:15Z)` and `[21:15Z,21:20Z)`. Both share run ID
`78c3e40115c5003ff2a23c48`, connection epoch 1, continuity epoch 1, and the same connection-open
timestamp. Both sources are `COMPLETE`; no failure, reconnect, or planned handoff occurred. Each
retains zero published snapshots, `FLAT/WARMUP_BLOCK`, and independent `BLOCK`.

The unchanged causal evaluator separately retained two newly available 1h rows from exact public
Spot bytes. The six-window schedule now contains four available retain-only 1h rows and 14
unavailable rows. No label was aggregated, interpreted, scored, or used to change the signal.
Mutable `operations/status.json` is excluded from Git because it is operational liveness only; its
completed hash is retained in the report while content-addressed sessions remain historical proof.
A post-proof fixture-only amendment allows the status-verifier test to coexist with that local
runtime directory; the frozen observer and the proof commit are unchanged.

Consequence: V5's minimum public continuity proof passes and one finite 8,640-checkpoint warm-up
run may begin from the clean D-095 evidence commit. Any gap resets continuity and cannot be
backfilled or rescued. This does not validate a strategy, authorize analysis during warm-up, or
activate a bot, account connection, credential, order, paper/demo/live state, sealed holdout,
promotion, or execution authority.

Evidence: `artifacts/reports/PROSPECTIVE_BTC_LIQUIDATION_V5_TWO_WINDOW_PROOF_2026_07_13.md`,
sessions `bf68af8b…` and `e9daa3ac…`, and label snapshot `844852d7…`.
Status: **Operational continuity proof PASS; longest chain 2/8,640; authority NONE.**

### D-096 — Managed public observation is separated from the offline jobs worker

Decision: the prospective checkpoint observer will become a first-class
`tios.services.observations` flow with content-addressed run intent, deterministic status and
checkpoint projection, stale-heartbeat detection, and read-only dashboard visibility. The current
D-095 8,640-window process may be explicitly adopted without changing its already-running process,
heartbeat, continuity epoch, or immutable checkpoint bytes. Future runs must predeclare the exact
commit, operations-contract hash, checkpoint target, and authority before process start.

Extending the existing `services.jobs` worker is rejected. That worker is intentionally offline,
network-sandboxed, and capped at 24-hour jobs, while this public-source observation requires one
continuous process for up to 30 days. Per-window jobs would reconnect and invalidate the very
continuity being measured. The managed observation flow accepts no arbitrary command, path, URL,
credential, or dashboard process-control request and never auto-restarts, backfills, or rescues a
broken continuity epoch.

Consequence: the bounded observation service, CLI, projection, and tests may be implemented while
the frozen observer continues unchanged. No existing JobStore schema or semantics may change. No
strategy validation, analysis during warm-up, bot, account connection, credential, order,
paper/demo/live state, promotion, or execution authority is activated.

Evidence: `research/PROSPECTIVE_OBSERVATION_MANAGED_FLOW_V1.yaml`, D-093 through D-095, and the
existing jobs architecture in `docs/architecture/AD.md` and `TYPE_AND_CONTRACT_CATALOG.md`.
Status: **Managed-flow contract frozen; implementation authorized; authority NONE.**

### D-097 — Managed observation implementation frozen before current-run adoption

Decision: D-096 is implemented as a new `tios.services.observations` package plus one fixed CLI.
It writes canonical content-addressed `PREDECLARED` or `ADOPTED` intents; validates exact flow and
operations contracts, commit, authority, status counters, checkpoint bytes, finalized counts, and
continuity; derives fresh/delayed/stale/terminal states; and projects the active observation into
both TradingOS status and dashboard evidence surfaces. The dashboard gains no process-control
write. The fixed launcher accepts only `checkpoint_windows` in `[1,8640]` and refuses a second
fresh active observer.

The existing jobs schema, worker, network sandbox, schedules, and projections are unchanged.
Static gates and 104 focused architecture/dashboard/safety/prospective tests pass; the live
projection independently reconstructs the active D-095 run and correctly reports missing intent
before adoption. Exact implementation hashes are frozen before writing that intent.

Consequence: after this implementation is committed, the current process may be adopted with
target 8,640 without restart or byte changes. Future observation runs may use the managed fixed
launcher. No auto-restart, backfill, warm-up analysis, strategy validation, bot, credential,
account/venue connection, order, paper/demo/live state, promotion, or execution authority exists.

Evidence: `research/PROSPECTIVE_OBSERVATION_MANAGED_FLOW_IMPLEMENTATION_V1.yaml`, package/CLI
sources, dashboard projection, and `tests/test_observation_flow.py`.
Status: **Implementation frozen and tested; current-run adoption pending; authority NONE.**

### D-098 — Active prospective observer adopted into the managed flow

Decision: after committing D-097 as `d81dd47`, the already-running D-095 process was bound to one
content-addressed `ADOPTED` intent with target 8,640. Adoption did not restart or alter the process
or its evidence. The independent managed verifier reported `MANAGED / OBSERVING / FRESH`, no
blockers, three finalized consecutive checkpoints, connection and continuity epoch 2, and 8,637
remaining at the adoption instant.

Consequence: TradingOS now deterministically supervises the prospective evidence-collection flow
through fixed intent, status, checkpoint, freshness, continuity, contract, commit, and authority
checks. It deliberately does not auto-restart or backfill a broken epoch. This is not strategy
validation or execution authorization; warm-up analysis, scoring, promotion, paper/demo/live,
credentials, accounts, venues, orders, and the sealed V2 holdout remain blocked.

Evidence: `artifacts/reports/PROSPECTIVE_OBSERVATION_MANAGED_ADOPTION_2026_07_14.md`, adopted intent
`intent_ee043ada0ec765d75152f77e1cbf49fb42a6bdd6a7062e020e5f4dfde9abbc8d.json`, and its first three
continuous schema-5 checkpoints.
Status: **Managed observation active; warm-up evidence collection only; authority NONE.**

### D-099 — Strategy eligibility is a three-layer fail-closed contract

Decision: the official-platform review is refreshed and extended with QuantConnect's documented
community score and Darwinex Zero's calibration, risk-normalization, and DarwinIA allocation
rating. Platform diagnostics, optimization objectives, leaderboards, and allocation thresholds are
different objects; none becomes TradingOS approval authority.

TradingOS now implements separate metric, governed-scorecard, and promotion eligibility. Promotion
requires `COMPLETE_APPROVABLE`, no hard fail, the exact evidence-backed G1-G11 set all `PASS`, all
ten scorecard dimensions `PASS`, and independent statistical, risk, supervisor, and security
reviews all `PASS`. The existing risk precondition defect that omitted G10 is corrected. G12
remains the later paper-forward gate.

Consequence: an unavailable metric stays blocked rather than becoming zero; a structurally complete
scorecard may truthfully record failures without implying promotion; and no platform score or
weighted blend can bypass a hard gate. The active prospective signal remains ineligible during its
preregistered warm-up. Its read-only status/dashboard projection exposes the exact blocker classes
without adding a control. No bot, paper/demo/live state, credential, venue, order, or execution
authority is created.

Evidence: `research/PLATFORM_STRATEGY_VALIDATION_AND_SCORE_ELIGIBILITY_V2.md`,
`research/STRATEGY_ELIGIBILITY_CONTRACT_V1.yaml`, `src/tios/validation/eligibility.py`, and focused
eligibility/risk tests.
Status: **Eligibility contract implemented, tested, and projected; current signal warm-up blocked.**

### D-100 — Prospective signal blockers map to explicit evidence producers

Decision: every current eligibility blocker for `PROSPECTIVE-BTC-LIQUIDATION-STRESS-V1` is mapped
to its owning producer, verifier, earliest lawful evaluation point, release condition, and affected
gate/dimension. The map explicitly corrects a semantic ambiguity: 8,640 five-minute windows are
prospective samples, not optimization trials. The signal has no declared score-campaign trial
population and is not a StrategyVersion.

The current lane may mature into an immutable RiskSignalVersion only after the frozen first-review
minima and a supervisor admission decision. Even a validated risk signal cannot manufacture alpha,
create an order, or support a bot without a separately validated exact StrategyVersion context.

Consequence: future agents have a deterministic evidence path and cannot fill missing fields with
platform scores, zeros, window counts mislabeled as trials, early labels, or inferred approvals.
The next safe offline step is to preregister the future association/overlay campaign before any
lawful metric calculation. No warm-up analysis, sealed-holdout access, credential, venue, paper,
demo, live, or execution authority is created.

Evidence: `research/PROSPECTIVE_SIGNAL_EVIDENCE_PRODUCER_MAP_V1.yaml`, current eligibility
projection, and `tests/test_prospective_signal_evidence_map.py`.
Status: **Blocker ownership frozen; signal remains observation-only and not eligible.**

### D-101 — Prospective checkpoint-to-risk-decision slice is deterministic and order-inert

Decision: the managed observation evidence now feeds one typed TradingOS vertical slice:
content-addressed finalized checkpoint → `RiskStateSignalEvent` → independent `RiskDecision` →
read-only status/dashboard and fixed offline verifier. The existing strategy-bound `SignalEvent`
remains unchanged because the liquidation-stress lane is not a StrategyVersion or alpha.

The risk-state type structurally rejects metric, scorecard, or promotion eligibility and rejects
any venue, paper, live, or order capability. The adapter verifies the checkpoint hash, location,
five-minute coverage, public-source semantics, frozen authority, `FLAT` warm-up signal, and
independent `BLOCK`; any semantic drift returns an error projection with order creation disabled.

Consequence: the current flow is deterministic inside TradingOS and independently verifiable, but
ends at a risk block. It proves system plumbing, not predictive value. A separately validated exact
StrategyVersion remains mandatory before any later bot or paper proposal.

Evidence: `src/tios/services/observations/risk_signal.py`,
`scripts/verify_prospective_risk_signal_flow.py`, read-only dashboard projection, and
`tests/test_risk_signal_flow.py`.
Status: **Offline vertical slice available and fail-closed; strategy/paper/live authority NONE.**

### D-102 — Prospective association and strategy-overlay questions are separated before scoring

Decision: the liquidation-stress lane now has an immutable, executable parent preregistration
frozen before any warm-up aggregation. It declares exactly three association trials (`1H`, `6H`,
`24H`), with `6H` as the sole governed primary endpoint and the other horizons unable to rescue
it. Independent 24-hour-cooldown episode onsets are compared with four deterministic same-UTC-time
`NORMAL` controls. The primary requires an exact one-sided sign test, a 22-basis-point median
materiality hurdle, negative event median, minimum sample, chronological-half, leave-one-month-out,
and concentration gates.

Association and overlay are separate. Even a supported association cannot evaluate or approve an
execution overlay. A child campaign remains structurally blocked until one exact, independently
promotion-eligible alpha StrategyVersion is pinned; it must compare that strategy unchanged with
the same strategy plus six-hour suppression of new long entries, retaining every missed profitable
entry as opportunity cost.

Consequence: V1 has no outcome-conditioned horizon, threshold, subgroup, control, or extra-time
rescue. Its executable preflight verifies frozen hashes and the current observation count while
reading zero label files and computing zero metrics during warm-up. Current result is `WAITING`.
No risk-signal or alpha conclusion, bot, order, paper/demo/live state, or authority is created.

Evidence: `research/PROSPECTIVE_BTC_LIQUIDATION_ASSOCIATION_OVERLAY_CAMPAIGN_V1.yaml`,
`scripts/verify_prospective_association_campaign.py`, and focused campaign tests.
Status: **Parent campaign frozen and preflight-verifiable; metrics and overlay blocked.**

### D-103 — ETH volume-breakout admitted as one prospective alpha candidate

Decision: the exposed `SIG-VOLUME-BREAKOUT` ETHUSDT Spot 1h screen is admitted only as the
mechanism and exact parameter source for a new immutable prospective candidate. Its historical
result remains discovery evidence: the old screen is `NOT_ELIGIBLE`, its global selection lineage
is incomplete, and adjacent technical research contains thousands of additional exposures.

The exact candidate is `SV-418ab5d64825c74b`: prior-40-bar Donchian entry/exit with entry also
requiring current base volume above 1.5 times the current-inclusive 40-bar base-volume mean.
Canonical evaluation over the frozen 48,154-row ETHUSDT 1h dataset reproduces the old 511 signal
transitions exactly. This proves semantic parity, not alpha. A new ETH-only prospective boundary
starts at `2026-07-14T00:00:00Z`; no parameters, asset, timeframe, or early performance read may
rescue it.

Consequence: TradingOS now has a deterministic strategy-bound vertical slice from frozen bars to
typed `SignalEvent` and independent `BLOCK`. Promotion remains false until the preregistered
prospective minimum and independent review pass. No sealed BTC V2 holdout, bot, order, paper/demo/
live state, credential, venue, or execution authority is activated.

Evidence: `research/ETH_VOLUME_BREAKOUT_PROSPECTIVE_CANDIDATE_V1.yaml`, canonical spec,
`scripts/verify_eth_volume_breakout_flow.py`, and focused tests.
Status: **Prospective candidate and signal flow available; validation incomplete and risk BLOCK.**

### D-066 — CFTC Bitcoin-futures positioning admitted to data packaging

Decision: a new source-only cycle compared exactly three distinct mechanisms without computing
local family performance: regulated CME Bitcoin-futures positioning, Bitcoin blockspace fee
pressure, and dormant-supply reactivation. Fee pressure is rejected as endogenous, mechanically
confounded, and adjacent to closed transaction/miner contexts. Dormant supply is rejected because
on-chain movement is not a sale, transfer intent is unresolved, and the mechanism is adjacent to
the closed MVRV holder context.

Only `FAM-CFTC-BTC-POSITIONING-01` advances to data packaging. It uses the exact filtered CFTC
Public Reporting Environment Legacy Futures Only response for full-size CME Bitcoin row `133741`,
excludes the Micro contract, normalizes non-commercial net position by open interest, and retains
both aligned-high and contrarian-low interpretations. The 12-trial roster and conservative
publication rule are frozen in the dossier. Official shutdown, cyber, postponement, and catch-up
dates must override the ordinary lag when later; unresolved releases are quarantined. The executed
instrument remains unlevered BTCUSDT Spot.

Consequence: exact CFTC archives, official publication-exception evidence, normalized rows, and
strict next-Spot-open mappings may be packaged offline. No conditioned return may be computed
before a clean data/campaign freeze. No future, bot, venue, credential, order, paper/demo/live
state, human gate, sealed V2 holdout, or execution authority is activated.

Evidence: `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V6.md`.
Status: **Approved constrained-S2 data build; performance unobserved and authority NONE.**

### D-067 — CFTC positioning data and causal publication package frozen offline

Decision: the admitted D-066 family now has an immutable, no-key source package without computing
conditioned returns. Exact base64-reversible source bytes retain the filtered 133-column CFTC CSV,
dataset metadata, release schedule, historical special announcements, and 2019/2023 delay records.
The package contains 431 unique full-size code-`133741` weekly reports from 2018-04-10 through
2026-07-07 and an explicit 30-report exception ledger. Normal availability is conservatively
report date plus eight calendar days at UTC midnight; exceptional reports use the later of that
rule and UTC midnight after official publication.

Because the prior canonical Spot package began in 2021, 33 exact Binance monthly BTCUSDT 1h
archives from 2018-04 through 2020-12 were added with their official CHECKSUM responses. They join
the retained 2021-2026 dataset into 72,225 bars. All 25 real gaps are hashed and retained; no
interpolation is allowed. Exactly 428 CFTC reports map to a strictly later retained Spot open; the
three reports whose availability falls after Spot coverage remain explicitly unmapped.

Consequence: canonical strategy semantics, independent implementations, and a fully frozen G1-G11
campaign may now be built. No positioning-conditioned return may be computed until that complete
campaign is committed cleanly. No derivative, bot, venue, credential, order, paper/demo/live
state, sealed V2 holdout, human gate, or execution authority is activated.

Evidence: `research/CFTC_BTC_POSITIONING_DATA_PACKAGE_V1.json`,
`scripts/verify_cftc_btc_positioning_data.py`, and focused fail-closed tests.
Status: **Verified offline data boundary; performance unobserved and authority NONE.**

### D-068 — CFTC positioning campaign frozen behind the development selection barrier

Decision: `CFTC-BTC-POSITIONING-SPOT-G1-G11-V1` is fully specified before scoring. Twelve
content-derived StrategyVersions exhaust aligned-high/contrarian-low × 13/26/52-week baseline ×
0.5/1.0 strict-z thresholds. Every pulse is unlevered BTCUSDT Spot long/cash for seven complete
days, never stacks or extends, and exits on observable source/Spot gaps. Catch-up reports mapping
to one open use only the newest report. The ordinary eight-day conservative availability and 30
official exception mappings remain immutable.

The implementation has four roles: canonical point-in-time semantics, an independent Decimal
ledger, a vectorbt retained-trial accelerator, and separate Freqtrade/Nautilus environment signal
and event-order conformance roles. Micro-goldens cover strict-later fills, high/low polarity, zero
variance, non-extension, exact cost accounting, invalid inputs, and future-append causality. A
two-phase runner requires a content-addressed development selection before any 2023-2026 OOS
evaluation. It freezes six costs, full/stress/delay tests, seven regime periods, benchmark,
drawdown, event minima, PBO/DSR, and G1-G11 thresholds.

One pre-freeze worker-import smoke used only 2018-04 through 2018-06, structurally shorter than the
minimum 13-report warm-up; it could not form any eligible trial signal or performance observation.
No family-conditioned eligible return or selected direction was observed. The complete campaign
remains unrun.

Consequence: one clean-commit offline campaign run is authorized. Numeric output cannot
self-promote. No bot, derivative, venue, credential, order, paper/demo/live state, human gate,
sealed V2 holdout, or execution authority is authorized.

Evidence: `research/CFTC_BTC_POSITIONING_SPOT_G1_G11_CAMPAIGN_V1.yaml`, canonical/role modules,
and focused tests under `tests/test_cftc_positioning_*`.
Status: **Approved constrained-S2 immutable offline campaign; preregistered and not run.**

### D-069 — CFTC positioning Spot campaign rejected without rescue

Decision: the frozen campaign completed from clean commit `b3bc024` with its development-only
selection barrier intact. It selected `CONTRARIAN_LOW` / 52 reports / 1.0 z. Four-role parity
passed with no mismatches, but validation lost 2.50%; development and reserve completed only 27
and 6 trades; full drawdown was 63.35%; only four of seven periods were positive; strategy Sharpe
trailed buy-and-hold; PBO was 0.5578; and DSR was 0.3493. G5/G6/G7/G8/G9/G10 fail.

Consequence: G11 rejects the exact CFTC positioning-pulse context without tuning, filtering, or
reinterpretation. It is not promotion eligible. No bot, venue, credential, order,
paper/demo/live state, human gate, sealed V2 holdout, closed-family context, or execution
authority was activated.

Evidence: `artifacts/reports/CFTC_BTC_POSITIONING_SPOT_VALIDATION_AND_SUPERVISOR_REVIEW_2026_07_13.md`.
Status: **Completed negative campaign; execution authority remains NONE.**

### D-070 — Binance Spot taker imbalance admitted to data packaging

Decision: `FAMILY-SELECT-V7` compared exactly three new mechanisms without computing local
candidate performance: Spot aggressive taker-flow imbalance, perpetual open-interest crowding,
and macro dollar/liquidity pressure. Perpetual OI is rejected because the official historical REST
contract exposes only 30 days and venue-local OI is directionless and adjacent to closed
derivatives contexts. Macro liquidity is rejected because release clocks, revisions, mixed
frequencies, event overlap, and a large hidden series hierarchy make the bounded campaign
inadequate.

`FAM-BTC-SPOT-TAKER-IMBALANCE-01` alone advances. It uses only completed-hour Binance Spot kline
quote volume and taker-buy quote volume, with entry strictly after the source-hour close. The exact
12-trial interpretation/baseline/threshold roster, fixed six-hour nonextending pulse, chronology,
costs, gates, no-rescue rules, and selection barrier are preregistered. Both continuation and
reversal signs remain because contemporaneous price impact does not determine the later sign.

Consequence: exact offline data packaging and canonical/campaign construction may proceed. No
imbalance-conditioned return may be computed before a clean freeze. No bot, venue, credential,
order, paper/demo/live state, promotion, human gate, sealed V2 holdout, or execution authority is
activated.

Evidence: `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V7.md`.
Status: **Approved constrained-S2 data/canonical build; performance unobserved and authority NONE.**

### D-071 — Spot taker-imbalance exact data boundary frozen

Decision: the dedicated package retains the exact official-checksum BTCUSDT Spot 1h archives and
canonical normalized data covering 2018-04-01 through 2026-06-30. Offline reconstruction verifies
72,225 rows, 25 gaps, and the completed-hour feature fields. Exactly four zero-volume or
invalid-clock rows are quarantined and reset the consecutive baseline; 72,221 feature rows are
valid and 72,220 map to a strictly later retained open. The package pins archive/checksum bytes,
decoded hashes, schema, timestamp-unit handling, logical feature content, gaps, invalid rows, and
mapping counts.

Consequence: canonical/reference/worker implementations and an immutable two-phase campaign may
be built. No imbalance-conditioned return has been computed. No bot, venue, credential, order,
paper/demo/live state, human gate, sealed V2 holdout, or execution authority is activated.

Evidence: `research/BTC_SPOT_TAKER_IMBALANCE_DATA_PACKAGE_V1.json`,
`scripts/verify_btc_spot_taker_imbalance_data.py`, and focused fail-closed tests.
Status: **Verified offline data boundary; performance unobserved and authority NONE.**

### D-072 — Spot taker-imbalance campaign frozen behind the development selection barrier

Decision: `BTC-SPOT-TAKER-IMBALANCE-G1-G11-V1` is fully specified before scoring. Twelve
StrategyVersions exhaust continuation-high/reversal-low × 24/168/720-hour prior baseline ×
1.0/2.0 strict-z thresholds. Every entry is strictly after the measured source-hour close and
creates an unlevered six-hour BTCUSDT Spot long/cash pulse that never stacks or extends. Invalid
volume/clock rows and gaps reset warm-up and exit held exposure at the first observable open.

The implementation has canonical point-in-time semantics, an independent Decimal ledger, a
vectorbt retained-trial accelerator, and separate Freqtrade/Nautilus environment conformance roles.
Causal goldens cover strict-later fill, polarity, zero variance, nonextension, exact costs,
invalid-row reset, invalid inputs, and future-append causality. The runner requires a hashed
development selection before 2023-2026 evaluation and freezes six costs, seven periods,
stress/delay/benchmark tests, sample/drawdown/PBO/DSR thresholds, and G1-G11.

A pre-freeze worker smoke used only the first 12 source hours, structurally shorter than the
minimum 24-hour prior baseline. It produced zero signals in every role and could not reveal an
eligible return or direction. The complete campaign remains unrun.

Consequence: one clean-commit offline campaign run is authorized. Numeric output cannot
self-promote. No bot, venue, credential, order, paper/demo/live state, human gate, sealed V2
holdout, closed-family context, or execution authority is authorized.

Evidence: `research/BTC_SPOT_TAKER_IMBALANCE_G1_G11_CAMPAIGN_V1.yaml`, canonical/role modules,
and focused tests under `tests/test_taker_imbalance_*`.
Status: **Approved constrained-S2 immutable offline campaign; preregistered and not run.**

### D-073 — Taker-imbalance V1 pre-selection runtime abort closed; computation-only V2 authorized

Decision: V1 began from clean commit `79b5fa3` and remained in phase-one reference development
computation. Its independent ledger rescanned up to 720 prior rows for every bar and regenerated
cost-independent events in every cost cell. After sustained full-CPU execution it was interrupted
before phase-one completion. No selection artifact, worker output, validation, reserve,
full-history, period, or final campaign artifact existed; temporary state was removed.

V2 inherits V1's full strategy/statistical/safety contract by hash. Its only changes use
mathematically equivalent prefix moments for the prior-window population variance and cache exact
event flags across cost cells. Canonical/reference micro-goldens and the full 12-hour sub-warm-up
worker parity remain intact. No strategy or gate term changes.

Evidence: `artifacts/reports/BTC_SPOT_TAKER_IMBALANCE_V1_OPERATIONAL_ABORT_2026_07_13.md` and
`research/BTC_SPOT_TAKER_IMBALANCE_G1_G11_CAMPAIGN_V2.yaml`.
Status: **V1 aborted pre-selection; V2 immutable offline rerun authorized; authority NONE.**

### D-074 — Spot taker-imbalance campaign rejected without rescue

Decision: V2 completed from clean commit `eba18df` with its development selection barrier intact
and selected continuation-high / 168 hours / 2.0 z. Development lost 74.26%, validation lost
11.37%, reserve lost 57.15%, and full primary lost 90.23% with 90.37% drawdown. Stress lost 99.78%,
the one-bar delay lost 90.90%, only one of seven periods was positive, selected Sharpe trailed
buy-and-hold, and DSR was 0.0000208. PBO alone passed at 0.2799. Selected-trial phase-two parity
passed, but two nonselected 24-hour/1.0 development trials retained vectorbt residuals. G4-G10 fail.

Consequence: G11 rejects the exact completed-hour Spot taker-imbalance family without tuning,
filtering, or reinterpretation. It is not promotion eligible. No bot, venue, credential, order,
paper/demo/live state, human gate, sealed V2 holdout, closed-family context, or execution authority
was activated.

Evidence: `artifacts/reports/BTC_SPOT_TAKER_IMBALANCE_VALIDATION_AND_SUPERVISOR_REVIEW_2026_07_13.md`.
Status: **Completed negative campaign; execution authority remains NONE.**

### D-063 — Bitcoin MVRV dislocation family admitted to data/canonical construction

Decision: a source-only cycle compared exactly three new mechanisms without computing local family
performance: Bitcoin MVRV holder-cost-basis dislocations, U.S. financial-conditions regimes, and
public search attention. Financial conditions are rejected for limited and conflicting Bitcoin
directional evidence. Search attention is rejected because published direction conflicts and
Google Trends sampling, normalization, stitching, and revisions prevent an immutable point-in-time
contract.

`FAM-BTC-MVRV-DISLOCATION-01` alone advances. Coin Metrics' no-key Community API and catalog define
and expose daily BTC `CapMVRVCur`; 2,189 observations plus the exact catalog entry are retained.
The package records the original HTTP-body hash and the tracked one-LF archival transform, verifies
no gaps, freezes a two-day lag and strict later Spot mapping, and declares exactly 12 HIGH/LOW,
30/90/180-day, 1/7-day pulse trials without scoring.

Consequence: canonical and campaign construction may proceed offline. MVRV must not be represented
as true acquisition cost, unique holders, exchange flow, or causality. No bot, venue, credential,
order, paper/demo/live state, holdout access, or execution authority is activated.

Evidence: `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V5.md` and
`research/BTC_MVRV_DATA_PACKAGE_V1.json`.
Status: **Approved constrained-S2 data/canonical build; performance unobserved and authority NONE.**

### D-064 — Bitcoin MVRV campaign frozen behind a development selection barrier

Decision: the D-063 family is fully specified before scoring as `BTC-MVRV-SPOT-G1-G11-V1`.
Twelve content-derived StrategyVersions exhaust the HIGH/LOW, 30/90/180-day prior-window, and
1/7-day holding roster. Canonical exact-Decimal semantics are paired with an independent Decimal
ledger, vectorbt accelerator, Freqtrade-environment signal harness, and Nautilus-environment event
harness. Focused causal tests, worker import preflights, offline data verification, and a deliberate
phase-two-without-selection failure pass.

The runner evaluates development first and must write a content-addressed selection artifact
before validation/reserve/full/period access. Six cost cells, chronology, trade minima, benchmark,
drawdown, one-bar delay, PBO/DSR, parity, G1-G11, no-rescue rules, and exact data/code hashes are
frozen.

Consequence: one clean-commit offline run is authorized. Numeric output cannot self-promote and
G11 remains independent. No bot, venue, credential, order, paper/demo/live state, human gate,
holdout access, closed-family context, or execution authority is authorized.

Evidence: `research/BTC_MVRV_SPOT_G1_G11_CAMPAIGN_V1.yaml` and focused tests under
`tests/test_mvrv_*`.
Status: **Approved constrained-S2 immutable offline campaign; preregistered and not run.**

### D-065 — Bitcoin MVRV dislocation campaign rejected without rescue

Decision: the campaign selected HIGH/180/1-day from development. Development returned +44.50%,
but validation returned -21.00%, reserve -10.42%, full stress -45.53%, and one-bar delay -20.08%.
Reserve had 10 completed trades versus 12 required, only one of six periods was positive, full
drawdown was -36.51%, PBO was 0.5895, and DSR was 0.4632. Four-role parity passed without mismatch,
but G5/G6/G7/G8/G9/G10 fail.

Consequence: G11 rejects the exact MVRV pulse family without tuning or reinterpretation. It is not
promotion eligible. No bot, venue, credential, order, paper/demo/live state, human gate, holdout,
closed-family context, or execution authority was activated.

Evidence: `artifacts/reports/BTC_MVRV_SPOT_VALIDATION_AND_SUPERVISOR_REVIEW_2026_07_13.md`.
Status: **Completed negative campaign; execution authority remains NONE.**

### D-060 — Finalized Bitcoin transaction-activity family admitted to canonical construction

Decision: the fourth bounded source cycle compared exactly finalized Bitcoin L1 confirmed-
transaction shocks, stablecoin-supply growth, and miner hash-rate/difficulty recovery without
computing local family performance. Stablecoin supply is rejected on direct null price evidence,
endogeneity, aggregation, migration, and revision risk. Miner recovery is rejected because price
materially drives hash rate/mining economics and OOS return evidence is weak.

`FAM-BTC-TX-ACTIVITY-01` alone advances as a short unlevered BTCUSDT Spot long/cash pulse. The
official `n-transactions` response is frozen at 2,187 observations; 2,004 enter the campaign after
coverage limits. A two-full-day availability lag, strict later 01:00 UTC fill, one known source
gap, exact byte/logical hashes, and no-interpolation behavior pass offline drift tests. The exact
12-trial activity-side/window/holding roster is preregistered.

Consequence: canonical and campaign construction may proceed without scoring. Transaction count
must not be represented as unique users, economic value, exchange flow, or causal adoption. No
bot, venue, credential, order, paper/demo/live state, holdout reuse, or authority is activated.

Evidence: `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V4.md` and
`research/BTC_TX_ACTIVITY_DATA_PACKAGE_V1.json`.
Status: **Approved constrained-S2 data/canonical build; performance unobserved and authority NONE.**

### D-061 — Bitcoin transaction-activity campaign frozen behind a selection barrier

Decision: the D-060 family is specified as `BTC-TX-ACTIVITY-SPOT-G1-G11-V1` before any
activity-conditioned return is computed. Twelve content-derived StrategyVersions exhaust the
two-side, three-window, two-holding-period roster. The canonical implementation and independent
Decimal, vectorbt, Freqtrade-environment, and Nautilus-environment roles freeze strict prior-window
population z-scores, the two-day availability lag, next-open fills, non-extending pulses, and
fail-closed source/Spot gaps. Focused causal tests and worker import preflights pass.

The offline runner evaluates all 12 trials on development first, writes and verifies a hashed
selection artifact, and refuses validation/reserve access without it. Six cost cells, chronological
splits, trade minima, timing delay, benchmark, drawdown, period, PBO/DSR, parity, G1-G11, and
no-rescue rules are immutable.

Consequence: one clean-commit offline historical run is authorized. Numeric output cannot
self-promote. No bot, venue, credential, order, paper/demo/live state, human gate, sealed V2
holdout access, closed-family reuse, or execution authority is authorized.

Evidence: `research/BTC_TX_ACTIVITY_SPOT_G1_G11_CAMPAIGN_V1.yaml` and focused tests under
`tests/test_transaction_activity_*`.
Status: **Approved constrained-S2 immutable offline campaign; preregistered and not run.**

### D-062 — Bitcoin transaction-activity pulse campaign rejected without rescue

Decision: the campaign selected HIGH/56/1-day from development. Validation returned -1.57%,
reserve returned -22.22%, full F1/S1 returned -3.02%, full F2/S3 stress returned -51.98%, and the
one-bar delay returned -21.41%. Only two of six periods were positive, full drawdown was -38.49%,
and DSR was 0.3422. Four-role parity passed without mismatches and PBO passed at 0.2965, but those
facts cannot override G5/G6/G7/G8/G9/G10 failures.

Consequence: G11 rejects the exact transaction-count shock family without tuning, filtering, or
reinterpretation. It is not promotion eligible. No bot, venue, credential, order, paper/demo/live
state, human gate, sealed V2 holdout, closed-family context, or execution authority was activated.

Evidence: `artifacts/reports/BTC_TX_ACTIVITY_SPOT_VALIDATION_AND_SUPERVISOR_REVIEW_2026_07_13.md`.
Status: **Completed negative campaign; execution authority remains NONE.**

### D-055 — Funding-pressure Spot family admitted to canonical campaign construction

Decision: `FAMILY-SELECT-V3` compared exactly three distinct mechanisms without computing local
family performance: perpetual-funding pressure as an exogenous BTC Spot signal, BTC-to-small-alt
minute-scale lead/lag, and crypto-options variance-risk-premium harvesting. Small-alt lead/lag is
rejected because its cited edge depends on thin, ex-post-selected names and minute-scale
microstructure that OHLCV cannot validate. Options VRP is rejected because historical surface,
contract lifecycle, settlement, margin, and short-convexity ownership are absent.

`FAM-FUNDING-PRESSURE-SPOT-01` alone advances. Funding is a timestamped feature only: the strategy
may hold unlevered BTCUSDT Spot or cash and never opens a perpetual, short, margin, carry, or
funding-payment position. The complete 12-trial polarity/lookback/threshold roster, chronology,
costs, gates, no-rescue rules, and mandatory select-before-reserve barrier are preregistered.
The 66 retained official monthly funding archives and 48,154 Spot bars are content-addressed and
pass archive-byte, schema, timestamp, ordering, and strictly-later-open checks offline.

Consequence: canonical spec, independent implementations, and an unrun immutable campaign may be
built. No family-conditioned return may be computed before the clean campaign freeze. The sealed
V2 holdout and rejected calendar reserve may not be used. No bot, venue, credential, order,
paper/demo/live state, promotion, human gate, or execution authority is activated.

Evidence: `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V3.md` and
`research/FUNDING_PRESSURE_SPOT_DATA_PACKAGE_V1.json`.
Status: **Approved constrained-S2 data/canonical build; performance unobserved and authority NONE.**

### D-056 — Funding-pressure Spot campaign frozen behind a selection artifact barrier

Decision: the admitted D-055 family is fully specified before scoring as
`FUNDING-PRESSURE-SPOT-G1-G11-V1`. Twelve content-derived StrategyVersions exhaust the declared
two-polarity, three-lookback, two-threshold roster. Exact Decimal accounting is paired with
vectorbt acceleration, a Freqtrade-environment dataframe signal harness, and a
Nautilus-environment event-order/gap harness. Synthetic causal goldens and offline preflight pass.

The runner has two physically gated phases. Phase one may evaluate all 12 trials on development
only and must write a content-addressed selected-StrategyVersion artifact. Phase two refuses to
evaluate validation, reserve, full-history, or period metrics unless that file exists and its hash
verifies. A deliberate early phase-two test raises. The campaign freezes six cost cells, next-open
and gap semantics, chronology, trade minima, benchmark, drawdown, one-bar delay, PBO/DSR, all
G1-G11 thresholds, no-rescue rules, and exact code/data/environment hashes.

Consequence: one clean-commit offline historical run is authorized. Numeric output cannot
self-promote and G11 still requires independent supervisor review. No bot, venue, credential,
order, paper/demo/live state, HG-3, or execution authority is authorized; the sealed V2 holdout
and rejected calendar reserve remain prohibited.

Evidence: `research/FUNDING_PRESSURE_SPOT_G1_G11_CAMPAIGN_V1.yaml` and focused tests under
`tests/test_funding_pressure_*`.
Status: **Approved constrained-S2 immutable offline campaign; preregistered and not run.**

### D-057 — V1 operational abort closed; import-bootstrap-only V2 authorized

Decision: V1 began from clean commit `528f8a5` but aborted during the first external worker start
because that process could not import the repository-local `engines` package. Development Decimal
computation had begun in memory, but no selection artifact, campaign output, validation, reserve,
full-history, or period evaluation was created. V1 is closed without a strategy verdict.

V2 inherits the complete V1 strategy/statistical/safety contract by content hash. Its only change
prepends the repository root to each external worker's Python import path before loading the
shared read-only data parser. Worker import smoke and V2 offline preflight pass. No rule,
StrategyVersion, polarity, lookback, threshold, cost, split, gate, or result changed.

Evidence: `artifacts/reports/FUNDING_PRESSURE_SPOT_V1_OPERATIONAL_ABORT_2026_07_13.md` and
`research/FUNDING_PRESSURE_SPOT_G1_G11_CAMPAIGN_V2.yaml`.
Status: **V1 aborted pre-selection; V2 immutable offline rerun authorized; authority NONE.**

### D-058 — V2 timezone-boundary abort closed; UTC-normalization-only V3 authorized

Decision: V2's import repair passed, then its first vectorbt worker aborted because pandas 3
rejected mixed naive/UTC-aware frozen segment bounds. No selection artifact, post-selection
evaluation, or output was created. V3 inherits V1's complete contract by hash and changes only
external-worker parsing of those same strings into explicit UTC timestamps. No statistical or
strategy term changed; validation and reserve remain untouched.

Evidence: `artifacts/reports/FUNDING_PRESSURE_SPOT_V2_OPERATIONAL_ABORT_2026_07_13.md` and
`research/FUNDING_PRESSURE_SPOT_G1_G11_CAMPAIGN_V3.yaml`.
Status: **V2 aborted pre-selection; V3 immutable offline rerun authorized; authority NONE.**

### D-059 — Funding-pressure directional Spot campaign rejected without rescue

Decision: V3 completed with its selection barrier intact and selected contrarian/3/0.0001.
Validation had zero trades and zero return; reserve had two trades and lost 2.52%. DSR was 0.8235,
and one non-selected development trial failed Nautilus parity. G4/G5/G6/G7/G8/G10 fail. The
full-history +51.58% is concentrated in 2021–2022 and cannot override frozen OOS gates.

Consequence: the exact funding-pressure directional long/cash family is closed without tuning or
reinterpretation. G11 rejects it as not validated and not promotion eligible. No bot, venue,
credential, order, paper/demo/live state, human gate, or authority is activated.

Evidence: `artifacts/reports/FUNDING_PRESSURE_SPOT_VALIDATION_AND_SUPERVISOR_REVIEW_2026_07_13.md`.
Status: **Completed negative campaign; execution authority remains NONE.**

### D-104 — Operator authorizes S3 demo lane in execution-measurement mode

Decision: the operator (2026-07-19, recorded from an interactive session) authorizes entering
the S3 paper/demo lane in **execution-measurement mode**: a venue demo account trading
synthetic/demo funds only, running an explicitly `UNVALIDATED` / `NOT_ELIGIBLE` candidate, for
the sole purpose of collecting real execution evidence (fills, fees, slippage, divergence,
operational stability). This amends the D-036 precondition that a `COMPLETE_APPROVABLE`
validated strategy must exist before any paper/demo activation — for this measurement lane only.

Rationale: the retained evidence contains a circular dependency. The surviving candidates'
remaining validation gaps are execution-level (PROJECT_STATE 2026-07-12: funding carry's
"remaining validation is EXECUTION-level — needs S3 paper trading to measure real fills/
slippage"), while S3 itself was gated on completed validation. Demo trading commits no real
money; withholding it blocked the only evidence that could complete validation.

Boundaries preserved, not weakened:
- No live path: S4, real credentials with trading/withdrawal power, and real-money authority
  remain locked behind their existing gates. Live states must remain unreachable in code.
- Demo credentials are operator-created, demo-scoped, and live only in the git-ignored `.env`;
  no agent requests, reads, or handles them in conversation.
- The D-046 quarantine is NOT removed by this decision. Reactivation of authenticated demo
  transports still requires the security review and typed adapter/reconciliation review that
  D-046 demands; this decision supplies the missing operator approval, not a bypass.
- Demo results are execution evidence only. Demo P&L cannot validate, promote, or approve a
  strategy; candidates remain `NOT_ELIGIBLE` until the normal validation gates pass.
- Kill-switch, runbook, heartbeat, and divergence-report contracts (already modeled inert)
  must be active in the lane before the first demo order.

Venue: Bybit demo (operator demo account already exists; quarantined transports already
implement it), with OKX demo as the recorded fallback for Israel availability.

Consequence: T-015-01 (paper-lane architecture) is decided as "venue demo, execution-
measurement mode". Next work: security + adapter/reconciliation review of the quarantined
transports, scoped un-quarantine for demo endpoints, lane wiring, then a 30-day stability and
divergence window.

Evidence: operator selection recorded in-session 2026-07-19; deadlock analysis from
`PROJECT_STATE.md` (2026-07-12 carry S3-paper entry) and `docs/supervisor/IMPROVEMENT_PLAN_2026-07-13.md`.
Status: **Approved; demo lane unlocked pending D-046-mandated security review.**

### D-105 — Typed demo lane approved as the sole order path (stage 2 complete)

Decision: the D-046-mandated typed adapter/reconciliation review is complete and recorded at
`artifacts/reports/DEMO_TRANSPORT_SECURITY_REVIEW_STAGE2_2026_07_19.md`. Order capability on
the Bybit demo account exists exclusively through `scripts/demo_eth_lane.py`: typed
`LaneIntent` orders, kill-switch gate, 50-USDT buy cap, independent 120-USDT sell cap,
instrument-step quantization, wallet reconciliation, and an append-only fsync'd ledger. The
raw demo scripts' POST transports remain quarantined permanently — the guard is not removed;
the sanctioned path goes around it, exactly as D-046 required.

Core `tios.trading_domain` contracts are unchanged: demo/paper/live environments remain
unconstructable in the domain model, and all existing unreachability tests pass untouched.
Lane records are explicitly `VENUE_DEMO` / `real_money: false` / `UNVALIDATED`.

The lane runs the D-103 canonical candidate through the unchanged spec + evaluator
(`SV-418ab5d64825c74b`) over demo-venue 1h klines and trades only signal transitions newer
than its persisted cursor: restarts cannot re-fire history, and only post-start transitions
execute. Demo fills are execution-measurement evidence (G12-class); they cannot validate,
promote, or approve any strategy. S4/live gates are untouched.

Evidence: stage-2 review artifact; `tests/test_demo_eth_lane.py` (8 tests incl. canonical-
evaluator breakout-to-order); demo suite 28 green; ruff + mypy gates green.
Status: **Demo order lane ACTIVE in execution-measurement mode under D-104.**

### D-106 — Dashboard gains a second audited write surface: demo lane start/stop

Decision: the local loopback dashboard may start and stop the D-105 demo lane from
Wallets → Demo. This is a deliberate, recorded expansion of the write boundary set by D-038
(which admitted exactly one write route, the workspace decision). It is not a general
write-API approval.

Scope: `GET /api/v1/demo-lane` (read-only projection) and `POST /api/v1/demo-lane-actions`
with a closed allowlist of exactly three actions — `START`, `STOP`, `RUN_ONCE`. The payload
accepts only `action` and `idempotency_key`; any other key is rejected. No symbol, size,
price, side, venue, or credential is expressible through this route, so no free-form input
reaches the spawned command. The subprocess argv is fixed (`sys.executable`, the lane script,
one internal literal flag), `shell=False`.

The dashboard gains NO trading capability of its own: it never reads a credential, signs a
request, or places an order. Every safety rail stays where D-105 put it — inside the lane
process (demo-host lock, 50/120 USDT caps, quantization, kill switch, reconciliation,
append-only ledger). The dashboard only starts or stops that process.

Supporting controls: same-origin/`Sec-Fetch-Site` guards and loopback-only binding already
applied to the existing POST routes cover this one; every action appends an operator record
to `artifacts/human_decisions/demo_lane_actions.jsonl`; STOP writes the kill switch (which
refuses orders immediately) before signalling the process, so a wedged process still cannot
trade; START and RUN_ONCE refuse with 409 while a lane holds the advisory lock, so the
dashboard cannot create a second lane racing the first on cursor/inventory state.

Related fix: `scripts/demo_eth_lane.py` now takes an exclusive `flock` for its lifetime.
Two concurrent lanes could previously have raced the cursor and double-traded from the
terminal as well; single-lane exclusivity is now enforced for every launch path.

Evidence: `tests/test_demo_lane_api.py` (12 tests incl. allowlist closure, lock-based
refusal, stop-flag audit); `src/tios/services/dashboard_api/demo_lane.py`; ruff + mypy green.
Status: **Approved; demo lane controllable from the dashboard, live gates untouched.**

### D-107 — Autonomous orchestration substrate: trial budget, attestation, self-modification bounds

Decision: the project gains an autonomous orchestration layer whose authority is
deliberately asymmetric. The orchestrator may freely do anything that *adds* evidence and
may do nothing that *weakens* a conclusion. The bounds are enforced in code, not policy.

Rationale: an orchestrator that can rewrite its own success criteria has no success
criteria. Under sustained optimisation pressure, relaxing a threshold is always cheaper
than meeting it, and nothing in an objective function marks that as cheating. Every
constraint below exists because its absence makes the system's output unverifiable rather
than merely risky.

Components:

1. **Global trial budget** (`src/tios/validation/trial_budget.py`). `ScorecardEvidence`
   previously proved only that a scorecard agreed with itself: `declared_trial_count ==
   terminal_trial_count` is self-reported, so a search over three thousand parameter sets
   could declare three and satisfy every other check. Families now pre-register their search
   space before running, every evaluated trial appends to a persistent ledger, and declared
   counts are verified against it. Unregistered searches cannot be scored at all. This is the
   precondition for safe parallel search: false-discovery rate scales with automation, and
   deflation thresholds are meaningless against a trial count that does not reflect the
   actual search. Wired into `evaluate_strategy_eligibility` as a fail-closed blocker —
   omitting the verification is `TRIAL_BUDGET_NOT_VERIFIED`, never a default pass.

2. **Operator attestation** (`src/tios/approval/attestation.py`). The ten human-only facts
   in `MISSING_AND_OPEN_ITEMS.md` become one signed, expiring attestation the engine enforces
   predicates against automatically, replacing per-decision approval for everything except
   real-money commitment. The file holds no credentials — only assertions about them.
   Attestations expire (90 days default) because venue terms, fee tiers, and product
   availability drift; a stale attestation reads as absent, not as continuing consent. Live
   authority is a separate explicit opt-in that a demo attestation never escalates into.

3. **Self-modification bounds** (`src/tios/ops/self_modification.py`). Every orchestrator
   code change lands on a branch, passes the full local gate, and auto-reverts on failure;
   `main` is never edited directly and never left red. An immutable-path guard rejects any
   diff touching the eligibility contract, the trial budget, the attestation module, the
   integrity manifest, or sealed holdout directories. The immutable check runs *before* the
   gate: a constraint edit that passes the suite is more dangerous, not less. Arguments for
   revising a constraint are recorded for operator review rather than acted on.

4. **Evidence-producer driver** (`src/tios/ops/driver.py`). D-100 already mapped every
   blocker to its owning producer, verifier, release condition, and earliest lawful
   evaluation point — a dependency graph with executable nodes that was never wired to a
   scheduler. The driver walks it. Verifiers are allowlisted to `scripts/*.py` and never
   shell-executed, because an autonomous process reading instructions from a config file is
   exactly where command injection matters. Declared `semantic_boundaries` prohibitions
   withhold all dispatch. Verifiers naming future work report PENDING and are never invented
   as evidence.

5. **Orchestrator** (`src/tios/ops/orchestrator.py`, `make orchestrator`). Observes
   constraint integrity, statistical health, evidence freshness, strategy coverage, blocker
   movement, execution envelope, and parked work. Halts on any ESCALATE rather than
   continuing past something it cannot explain. Read-only dashboard projection at
   Operations → Orchestrator; the view exposes no control.

Objective: trustworthy verdicts per unit time, never the rate of positive verdicts. An
honest FAIL counts as progress; a PASS obtained by weakening a gate is a critical incident.

Supporting corrective work: SUP-007's achievable half is closed — `src/tios/evidence/
staleness.py` re-hashes every module an artifact names and classifies it CURRENT / STALE /
BROKEN, making artifact-code drift visible and failing on one byte of change. All six shipped
G10 campaign artifacts verify CURRENT. SUP-008 is closed structurally rather than by
convention — `src/tios/validation/splits.py` makes holdout leakage impossible: validation is
unavailable until selection is frozen, holdout is unreachable as an attribute, opening it
requires a recorded reason, respects the seal date, and may happen exactly once. SUP-010 is
closed for coverage — all 20 canonical specs now hold content-addressed immutable
`StrategyVersion` identities, and artifacts citing an unregistered strategy are blocked.

Parked as genuinely unrecoverable (`artifacts/driver/parked_items.jsonl`): historical REST
payload reconstruction and original run identity (bytes never retained); hierarchy-wide
effective trial accounting for the pre-V2 search (upstream hierarchy not retained).
Resolution for the latter is a new pre-registered family with complete accounting from the
start, not recovery of the old one.

No credential, venue, order, paper, demo, or live authority is created. The sealed holdout
remains sealed until at least 2027-01-14 and every component treats reading it as prohibited.

Evidence: 115 new tests across `tests/test_trial_budget.py`,
`tests/test_operator_attestation.py`, `tests/test_self_modification.py`,
`tests/test_driver.py`, `tests/test_artifact_staleness.py`, `tests/test_temporal_splits.py`,
`tests/test_strategy_registry.py`, `tests/test_orchestrator.py`,
`tests/test_orchestrator_view.py`; ruff, ruff format, and mypy green across 115 source files.
Status: **Substrate implemented and tested; no promotion, venue, or execution authority created.**

### D-108 — Family admission is budgeted, and the gate is split by what it verifies

Decision: two changes that together let the orchestrator choose strategy families itself.

**Family selection becomes the orchestrator's, because it is now budgeted.** D-107 counted
trials *within* a family. That leaves the outer search uncounted: an agent free to spawn a new
family whenever the last one failed is searching over families, and fifty families of twenty
trials each would each be deflated against twenty while the ecosystem actually searched a
thousand. The winner is then noise that survived a search nobody counted — SUP-005's defect
one level up.

`trial_budget.family_count`, `families`, and `effective_trials_hierarchy_wide` now expose the
outer search, and `campaign.run_campaign` deflates against the hierarchy-wide trial count
rather than the per-family one. Admitting a family therefore raises the bar every subsequent
family must clear. The correction is structural: no human has to decide when to say enough,
because searching more costs more automatically. Campaign artifacts report `hierarchy_trials`
and `admitted_families` so the correction is auditable rather than merely applied.

This supersedes the D-107-era position that family choice was reserved to a supervisor. That
framing described a statistical problem as a governance one. D-052/D-053 remain the record of
how families were selected historically; future admission is delegated, budgeted, and logged.

**The gate is split by what it verifies.** Ten data-package byte-integrity tests were 94% of
suite runtime (1753s of 1865s). They verify that retained archives still hash correctly — they
change when DATA changes, not when code does, so gating every code edit on them was checking
the wrong thing frequently, and a 31-minute gate made autonomous self-modification impractical.

`make check` now excludes them (1:29, 1081 tests) and is what the orchestrator gates on.
`make check-full` runs everything and is what `required` depends on. The artifact records
`gate` and `includes_slow_data_tests` at `schema_version: 3`, and the dashboard reads the gate
name from the payload — a fast-gate PASS must not be readable as though it verified data
integrity. A schema-2 artifact no longer satisfies the check and fails closed to `UNKNOWN`.

Considered and rejected: caching decoded archives (a cache sits directly in front of tests
whose purpose is detecting byte drift) and `pytest-xdist` (new dependency, gains capped by
core count, and it would not change what is being verified).

Evidence: `tests/test_campaign.py::test_spawning_a_family_raises_the_bar_for_every_family`,
`tests/test_trial_budget.py` hierarchy tests, `tests/test_check_artifact.py` both-gate
artifacts, `tests/test_dashboard.py` gate-coverage projection. `make check` PASS in 1:29.
Status: **Family admission delegated under budget; gate split by verification target.**

### D-109 — First campaign executed through the substrate: FAM-VOL-CONTRACTION-BREAKOUT-V1 rejected

Decision: `FAM-VOL-CONTRACTION-BREAKOUT-V1` was admitted by the orchestrator under the D-108
hierarchy-wide budget, executed end to end through the D-107 substrate, and is rejected. No
rescue, no reparameterisation.

Family rationale: enter long only after a preceding low-volatility regime resolves upward
through its own range; exit on a trailing low. Distinct from the retained Donchian baseline
(B2) in the claim it tests — a plain N-bar-high breakout fires in any regime, whereas this is
armed only after realised range contracts, so it tests whether contraction precedes
directional resolution rather than reparameterising a family already closed under D-054.

Execution: 48,614 real BTCUSDT 1h bars, chronological 60/20/20 split with 96-bar boundary gaps
(>= the longest lookback, so no indicator window straddles a boundary). 36 pre-registered
parameter sets, every one recorded to the ledger as evaluated. Selection ran on training data
only; validation was unreadable until selection froze and was then read exactly once. F1/S1
costs, next-open fills with adverse slippage on both sides.

Result: selected `contraction_window=24, breakout_window=48, exit_window=24, quantile=0.3`
with train per-bar Sharpe **+0.0411** and validation per-bar Sharpe **-0.0807**. The sign
inversion between selection and validation is the textbook overfitting signature: the winner
was the best of 36 on the training window and reversed out of sample. Deflated against the
hierarchy-wide ledger (36 trials, noise threshold 0.0642), z = -14.19 and **DSR = 0.000**.

Consequence: the family is closed. The negative result is genuine evidence — it was produced
under pre-registration, leak-proof splits, complete trial accounting, and a correct deflation,
which is precisely what the retained B2/B3/B4 and MTF results could not claim. The sealed
holdout was never touched (`holdout_sealed: true`) and remains sealed to at least 2027-01-14.

This is also the substrate's first end-to-end proof on real data: pre-registration, train-only
search, per-trial ledger, single validation read, hierarchy-wide deflation, and an untouched
holdout all held under a live run rather than a fixture.

Evidence: `artifacts/validation/campaigns/PREREG-4305189f44984fe1af6979379028d653.json`,
`scripts/run_first_budgeted_campaign.py`, ledger at `artifacts/validation/trial_budget/`.
Status: **Family rejected; substrate proven end to end. No promotion, venue, or execution authority.**

### D-110 — Campaigns #2 and #3: taker imbalance rejected decisively; MVRV dislocation is the first promising negative

Decision: two further families ran end to end through the D-107/D-108 substrate against
frozen in-repo data. Both FAIL their pre-registered thresholds; both are closed without
rescue. The hierarchy ledger now holds 108 trials across 3 admitted families, and every
future campaign deflates against all of them.

**FAM-TAKER-IMBALANCE-V1 — decisive FAIL.** 36 trials over baseline {24,168,720}h x
z {1.0,1.5,2.0} x hold {6,24}h x {continuation, reversal}, on 48,154 normalized BTCUSDT 1h
bars with gap/validity resets per the canonical spec. The best-of-36 was negative on its own
training data (-0.0021 per-bar Sharpe) and worse on validation (-0.0254). When even
selection bias cannot manufacture an in-sample edge, the family carries nothing at F1/S1
costs on this data. Closed.

**FAM-MVRV-DISLOCATION-V1 — FAIL, and the first promising negative.** 36 trials over
window {20,30,45}d x z {1.0,1.5,2.0} x side {HIGH,LOW} x hold {24,168}h, with the metric's
publication lag enforced structurally: each hourly row carries only the daily value already
released under the spec's D+3 availability rule, so no evaluation could touch an
unpublished value. Selected: buy when log-MVRV sits 2 sigma below its 30-day norm, hold
24h. Train +0.0451, validation +0.0548 — the first family in three campaigns whose
validation score *exceeded* training (no overfitting signature; campaign #1 inverted sign).
DSR 0.7585 against the 0.95 pre-registered threshold with a hierarchy-wide noise bar of
0.0472: the edge clears the raw bar but not with promotable confidence after deflating
against 108 trials.

Consequence: the exact searched context is closed — no re-parameterisation, per the frozen
stop rules; a re-run with tweaks is precisely the rescue the rules exist to forbid. Two
legitimate future paths remain, both forward-looking rather than backward-mining:
(1) the campaign artifact freezes the selected variant, and one untouched holdout read
after 2027-01-14 is lawful under the seal protocol; (2) a new preregistered *prospective*
observation of the frozen rule (D-103-style) may collect genuinely unseen evidence going
forward. Either produces new information; neither reopens the search.

Evidence: `artifacts/validation/campaigns/PREREG-111ee260c67cd6765c7c0bbe58dc0a48.json`,
`artifacts/validation/campaigns/PREREG-ca9c9e0891ca05f357757943eba8c79a.json`,
`scripts/run_family_campaigns_v2.py`, trial ledger at `artifacts/validation/trial_budget/`.
Status: **Both families closed honestly. No promotion, venue, or execution authority.**

### D-111 — Campaigns #4–#7 complete the family sweep; CFTC positioning is the first family to clear the deflated bar; two prospective lanes opened

Decision: the remaining four data-backed families ran end to end through the same
substrate (`scripts/run_family_campaigns_v3.py`), each with its availability lag enforced
structurally at data-join time. The hierarchy ledger now holds 234 trials across 7
admitted families; every number below is deflated against that full history.

**FAM-TX-ACTIVITY-V1 — FAIL.** 36 trials (window {7,14,30}d x z {1,1.5,2} x side x hold
{24,168}h), daily on-chain tx count under the spec's D+3 availability. Best-of-36 train
+0.0199, validation −0.0059, DSR 0. Overfit signature; closed.

**FAM-CROSS-VENUE-PREMIUM-V1 — FAIL.** 36 trials on the Coinbase-implied vs Binance
hourly log premium, fills at `binance_btcusdt_open`. Best-of-36 was *negative* in-sample
(−0.0044) with validation +0.0250 — noise, not signal. DSR 0.0004; closed.

**FAM-FUNDING-PRESSURE-V1 — FAIL.** 18 trials on the last-N funding-observation mean
regime rule (exact calc-time availability). The selected contrarian variant showed the
sweep's largest in-sample score (+0.1903) and produced *zero* validation trades — a
textbook regime-mined artifact. DSR 0; closed.

**FAM-CFTC-POSITIONING-V1 — first PASS-ELIGIBLE.** 36 trials (baseline {13,26,52}w x
z {0.5,1.0,1.5} x side x hold {168,672}h) on the weekly noncommercial net position share
of open interest, availability enforced at report date + 8 calendar days 00:00 UTC.
Selected: buy when net share sits 1.5 sigma below its 26-week norm, hold 168h. Train
+0.0243, validation +0.0772, DSR 0.9996 against the 0.95 threshold with a 216-trial
hierarchy noise bar of 0.0391. Honest caveats recorded now, before anyone is tempted to
forget them: validation exceeding train 3x warrants suspicion of a favorable validation
window rather than celebration; the signal fires from only ~431 weekly observations; and
weekly-cadence pulses mean few independent bets. Clearing the statistical bar creates NO
promotion, paper, demo, or live authority — G1-G11, independent specialist review, and
prospective evidence all still stand between this rule and any capital.

**Two prospective observation lanes opened (D-103-style), boundaries frozen today:**
(1) `research/PROSPECTIVE_MVRV_DISLOCATION_V1.yaml` + `scripts/run_prospective_mvrv_observer.py`
for the D-110 frozen MVRV variant — the observer fetched live public CoinMetrics data and
recorded its first honest row (source day 2026-07-18 under D+3, z +1.41, FLAT);
(2) `research/PROSPECTIVE_CFTC_POSITIONING_V1.yaml` for the frozen CFTC variant —
boundary frozen at the 2026-07-14 report; the weekly fetcher is flagged NOT_YET_BUILT and
loses nothing before the next report's availability date. Both lanes record signal state
only; outcome reads are prohibited until first-review minima (180 prospective days / 26
weeks, independent reviewer, no tuning).

Consequence: the searchable in-repo family backlog is exhausted — all seven data-backed
families have now been searched once under pre-registration and closed or frozen. Further
in-sample searching of these families is forbidden by their stop rules; new information
can only come from prospective observation, the sealed holdout reads lawful after
2027-01-14, or a *new* family backed by new data.

Evidence: `artifacts/validation/campaigns/PREREG-{19b3b09af958a19525446b3e635402e7,
a02a77353d87d56814709d13fc3d636e,83b7575e59ee7983f56b24a45a58e55d,
90ff157e14b32e0f3bbdd27aa3cff355}.json`, `scripts/run_family_campaigns_v3.py`,
`artifacts/prospective/MVRV-DISLOCATION-V1/observations.jsonl`, trial ledger at
`artifacts/validation/trial_budget/`.
Status: **Three families closed honestly; one frozen pending G1-G11 + specialist review + prospective evidence. No promotion, venue, or execution authority.**

### D-112 — Methodology audit retracts the CFTC PASS-ELIGIBLE; validation scoring corrected to trade-level significance for all future campaigns

Decision: an independent Opus red-team audit of the campaign scoring core, confirmed by a
bit-for-bit verification recompute, found the deflated-Sharpe verdict on the recorded campaign
path (`src/tios/validation/campaign.py::run_campaign`) was computed on a count inconsistent with
the series it scored. The affected verdicts have been corrected, the one optimistic verdict
formally retracted, and the scoring math fixed so the defect cannot recur.

**Findings (each with file reference):**
- **F1 — sample-count mismatch.** `run_campaign` computed a per-bar Sharpe over only in-position
  bars (the evaluators append a 0.0 mark bar while held and a realized return on exit, never a
  cash bar) but passed `sample_count=len(split.validation)` — the *total* validation bars — to
  the DSR (`campaign.py:192`, old). This inflated `z` by `1/sqrt(in-position fraction)`.
- **F2 — serial correlation.** The 0.0 mark-bar runs (168h/672h holds) are not independent
  observations; the honest `n` is the number of completed, non-overlapping trades, not the bar
  count (evaluators in `scripts/run_family_campaigns_v3.py`, `_v2.py`).
- **F3a — declared-but-unenforced PBO.** `thresholds` pre-registered `pbo_max=0.5` in every
  campaign, yet PBO was never computed on this path (the verdict step checked only `dsr>=0.95`
  and `validation>0`).
- **F3b — no correlation haircut.** `independent_trials` passed the raw hierarchy count while
  `multiple_testing.py::implied_independent_trials` sat unused.
- **F4 — dead nested folds.** `walk_forward_folds` were computed and `fold_scores` stored, but
  `fold.test` was never scored and `fold_scores` fed nothing (`gap_bars=0`).
- **F5 — no minimum-activity guard.** A family producing zero/one validation trade still received
  a Sharpe-of-0.0 → guaranteed hollow FAIL, with no distinct "insufficient activity" outcome.
- **F6 — inconsistent variance.** `_per_bar_sharpe` used population variance (÷n) while
  `sharpe_variance_from_trials` used sample variance (÷n-1).

**Verification (FAM-CFTC-POSITIONING-V1, artifact `PREREG-83b7575e59ee7983f56b24a45a58e55d.json`):**
reproduced train 0.024257871728695 and validation 0.077151674981046 exactly, DSR block bit-for-bit.
The recorded PASS-ELIGIBLE (DSR 0.999551, z 3.3208, hierarchy 216 trials) rested on **169 in-position
bars out of 7,630 validation bars (2.21%)** and exactly **one completed validation trade**. Under the
corrected count (sample_count = trade count = 1), no trade-level Sharpe is even computable
(`z 3.32 → n/a`, `DSR 0.9996 → n/a`); the variant is **INSUFFICIENT_ACTIVITY**, not a pass.

**RETRACTION.** FAM-CFTC-POSITIONING-V1's PASS-ELIGIBLE (D-111) is formally **retracted**. Its
corrected verdict is INSUFFICIENT_ACTIVITY (one completed trade, below the pre-registered floor of
10). It was never a statistically supported result; the single-trade window produced no computable
trade-level significance. There was and is **no promotion, paper, demo, venue, or execution
authority** attached to it — the retraction removes an inflated confidence number, nothing more.

**Corrected methodology now in force** (`src/tios/validation/campaign.py`, all future campaigns):
significance is built on per-completed-trade returns with `sample_count == len(trade returns)`,
enforced by a fail-closed invariant (F1/F2); a pre-registered `min_validation_trades` floor (default
10) yields INSUFFICIENT_ACTIVITY rather than a claimed DSR, and `n<2` never attempts a Sharpe (F5);
`pbo_max` is removed from the schema and the module documents that PBO is not computed on this path,
since a declared-but-unenforced control is worse than an honestly absent one (F3a); `independent_trials`
now routes through `implied_independent_trials`, haircutting the (still hierarchy-wide) trial count
for cross-trial correlation (F3b); the dead nested-fold scoring is deleted (F4); and the DSR-path
Sharpe uses sample variance (÷n-1), consistent with `sharpe_variance_from_trials` (F6).

**The six other FAIL verdicts stand.** Re-scored under the corrected statistics
(`scripts/rescore_frozen_campaigns.py`, correction artifacts under
`artifacts/validation/campaigns/corrections/`), every one remains a rejection — the original bias
was optimistic, so they fail *a fortiori*: TX-ACTIVITY FAIL (53 trades, z −2.36), CROSS-VENUE-PREMIUM
FAIL (213 trades, z −0.05, DSR 0.48 < 0.95), TAKER-IMBALANCE FAIL (115 trades, z −2.35),
MVRV-DISLOCATION FAIL (16 trades, z −0.10, DSR 0.46), FUNDING-PRESSURE INSUFFICIENT_ACTIVITY (0
trades), VOL-CONTRACTION-BREAKOUT INSUFFICIENT_ACTIVITY (7 trades < 10; its `normalized_multi` input
has since drifted under parallel work, so re-scored on committed data — the decisive FAIL/z −14.2 is
invariant to the drift). No family flips toward a pass under the correction.

**Both prospective observation lanes continue unchanged.** Signal-state observation records what the
signal *did*, which the scoring math does not touch, so the MVRV and CFTC lanes keep recording. Their
first reviews (2027) must apply these corrected statistics. The CFTC lane's founding premise is
*weakened* by this retraction: it is now **hypothesis-generating, not confirmation** of a prior in-repo
pass, and its first-review threshold should reflect that — a prospective pass would be the first real
evidence for the family, not corroboration of one.

Evidence: `src/tios/validation/campaign.py`, `scripts/rescore_frozen_campaigns.py`,
`artifacts/validation/campaigns/corrections/PREREG-83b7575e59ee7983f56b24a45a58e55d_corrected.json`
(and the six siblings), verification recompute reproduced train/validation bit-for-bit.
Status: **CFTC PASS-ELIGIBLE retracted (INSUFFICIENT_ACTIVITY); six FAILs stand; corrected scoring in
force. No promotion, venue, or execution authority anywhere. No trial-ledger writes, holdout unread.**

### D-113 — Operator decisions recorded: security-test sign-off, scouting scope, demo disaster-stop, and v8.119–v8.122 tree; four items stay deferred

Decision: the operator, in an interactive session on 2026-07-21 (evening), made five decisions:

(a) **APPROVED** the strengthened `test_live_unreachable.py` security-boundary assertion flagged
    for human review under D-104's stage-1 un-quarantine (`artifacts/driver/parked_items.jsonl`,
    phase "cross-cutting / stale security test"). Human sign-off obtained; the fix (no write verb,
    no order/position/withdraw/transfer endpoint, mutation-tested) stands as reviewed and accepted.
(b) **APPROVED** new-family scouting from community strategy libraries as hypothesis-sourcing
    only — ideas, not evidence; every candidate still requires an in-repo pre-registered campaign
    before any pass/fail claim. Executed: `docs/supervisor/NEW_FAMILY_SCOUTING_2026-07-21.md`
    (top-3 shortlist: cointegrated stat-arb baskets, cross-sectional altcoin momentum,
    cross-sectional funding carry). Pre-registration of any shortlisted family is a separate,
    not-yet-made decision.
(c) **APPROVED** the demo-lane −15% disaster-stop plus a Bybit V5 venue-resting stop order
    (`DEMO_DISASTER_STOP_PCT`). Implemented in `scripts/demo_eth_lane.py`;
    `tests/test_demo_disaster_stop.py` (new) and `tests/test_demo_eth_lane.py` cover it.
(d) **APPROVED** committing the v8.119–v8.122 working tree. Done, commit `0b183ea`.
(e) **DEFERRED**, no action taken this cycle: operator attestation fill
    (`ops/OPERATOR_ATTESTATION.example.json` — a project-knowledge pre-draft is being prepared),
    D-099 independent review, SUP-009 paid universe feed, and SUP-006(a) venue account
    semantics. All four stay parked until demo profitability evidence or further operator action;
    none is newly blocked or newly unblocked by this decision.

Evidence: operator session directives 2026-07-21 (evening); `artifacts/driver/parked_items.jsonl`
(item (a), phase "cross-cutting / stale security test", resolved with operator sign-off this
decision); `docs/supervisor/NEW_FAMILY_SCOUTING_2026-07-21.md`; `scripts/demo_eth_lane.py` +
`tests/test_demo_disaster_stop.py`; commit `0b183ea`.
Status: **(a)–(d) approved and executed/recorded; (e) remains deferred/parked, no change to its
blockers. No promotion, venue, or live-execution authority anywhere.**

### D-114 — New-family pre-registration go/no-go: delegated to project evidence, resolved NO-GO, no search slot spent

Decision: the operator delegated the go/no-go on pre-registering any of the
`NEW_FAMILY_SCOUTING_2026-07-21.md` shortlist (left open by D-113) to whatever the project's own
evidence showed, rather than deciding blind. A review turned up in-repo evidence the scouting doc
had missed for its top two candidates, so the delegated outcome is **no new family
pre-registration at this time; no search slot spent.**

Candidate 1, cointegrated stat-arb baskets (the scouting doc's #1-ranked, highest-priority pick),
is **refuted** by an existing in-repo campaign the scouting pass did not surface:
`scripts/run_stat_arb_pro.py` → `artifacts/validation/stat_arb_pro/STAT_ARB_PRO.json`
(2026-07-12) already ran an Engle-Granger-gated, hedge-ratio, OOS-split stat-arb campaign on 1h
data. 5 of 10 tested pairs were cointegrated in-sample, including ETH/BTC and BNB/BTC — the exact
mechanism and asset class the scouting doc proposed searching. Every top OOS configuration came
back negative (best annualized −11.2%), DSR 0.0039 against the 0.95 threshold. The recorded root
cause, cointegration decay (the in-sample relationship does not survive out-of-sample), is a
property of the pairwise/basket cointegration mechanism itself and is invariant to basket
cardinality — it does not become less true for a 3-asset or N-asset Johansen basket than it was
for a pair. The scouting doc's distinctness argument (this is a different mechanism from the
closed `CROSS-VENUE-BTC-PREMIUM` family) is correct, but distinctness from a *closed* family is
not the same as being *untested*: this mechanism has already been run and has already failed.

Candidate 2, cross-sectional altcoin momentum, is **partly refuted**, not cleanly open: per
`PROJECT_STATE.md` (§Strategy research arc, 2026-07-12), cross-sectional momentum long-only with
a dual-momentum cash filter and vol targeting already reached DSR 0.9456 at 28 pairs — the closest
any tested implementation came to the 0.95 screen — but degrades to 0.9091 at 34 pairs, i.e. the
result is fragile to universe size rather than a stable pass. Combined with the SUP-009
survivorship/delisting-complete-universe gap the scouting doc itself flagged as an open risk for
this candidate, a fresh pre-registration slot would be spent re-treading ground already shown to
be fragile, not opening new territory.

Candidate 3 (cross-sectional funding carry) was already ranked third/MEDIUM priority by the
scouting doc on independent grounds (BIS-documented edge decay to negative by 2025) and is not
separately re-litigated here.

Outcome: **no new family is pre-registered; no search/trial-budget slot is spent this cycle.**
This is a resolution of the delegated question, not a new prohibition — nothing here forecloses a
better-evidenced future candidate. The operator retains a standing **governance override**: a
multivariate/Johansen-basket variant of stat-arb (rather than pairwise Engle-Granger) could still
be pre-registered on the operator's own authority notwithstanding this evidence review, since
cardinality was the one dimension the STAT_ARB_PRO.json campaign did not itself test — but this
is recorded here as an override option for the operator to invoke, not a recommendation; the
evidence-based recommendation from this review is **against** spending a slot on it, since the
recorded failure mechanism (cointegration decay) is not expected to depend on basket size.

Evidence: `docs/supervisor/NEW_FAMILY_SCOUTING_2026-07-21.md` (candidates 1–3 and their addendum);
`scripts/run_stat_arb_pro.py`, `artifacts/validation/stat_arb_pro/STAT_ARB_PRO.json`
(2026-07-12); `PROJECT_STATE.md` §Strategy research arc, 2026-07-12 (DSR 0.9456 at 28 pairs,
0.9091 at 34 pairs); D-113 (delegated the open question this decision resolves).
Status: **NO-GO on all three shortlisted candidates this cycle; no pre-registration; no
search/trial-budget slot spent. Operator governance override for a Johansen multivariate basket
remains available but is recommended against. No promotion, venue, or execution authority
anywhere.**

### D-115 — One-time integrity reconciliation authorized; root-owned external trust boundary selected

Decision: the operator authorizes exactly one controlled integrity reconciliation for v8.127.
For this reconciliation only, `PACKAGE_INTEGRITY_MANIFEST.md` may be edited solely to update its
package-version line and the existing hash rows for intentionally changed manifest-listed
governance files. The manifest remains in `IMMUTABLE_PATHS`; this exception neither changes that
policy nor authorizes edits to `src/tios/ops/self_modification.py`, `Makefile`, thresholds,
sealed/holdout/prospective paths, or any other immutable path. No manifest row or immutable path
may be added or removed. The changelog and the full local gate are required in the same change.
The operator subsequently extended this same one-time reconciliation solely to remove one
pre-existing extra trailing `f` from the malformed manifest digest for the unchanged
`src/tios/services/observations/__init__.py`, and to add a non-manifest regression test that
prevents broad Path/SHA rows from being silently skipped by the strict verifier. No other
manifest row or source file is covered by that extension.

The operator also selects the Phase-2b external trust ownership boundary. Repository source and
setup code plus public metadata may remain in the repository. The installed production
verifier/helper, all private signing keys and credential/revocation material, the authoritative
append-only intake-decision history, and its monotonic checkpoint must be root-owned outside the
repository and unavailable to repository-writing agents. This is a composition/ownership
selection, not proof that the external components exist, are installed, or are trustworthy.

Independent reviewer setup and credential lifecycle remain pending, as do the typed independent
evidence resolver, trusted-time and current trust/revocation evidence, frozen activation
interfaces and integrity evidence, and independent security review. Until those artifacts are
actually supplied, verified, frozen, and independently reviewed, the Phase-2b scaffold remains
limited to external-activation-pending states with authority `NONE`; Phases 3 and 4 remain
blocked. Phase 5 cannot substitute for admission authority.

Evidence: explicit operator authorization for this one-time reconciliation on 2026-07-22;
`docs/supervisor/AUTONOMOUS_RESEARCH_FACTORY_AND_OPERATIONS_PLAN_2026-07-21.md` Phase 2b;
`src/tios/approval/intake_admission.py`; `src/tios/research_assets/admission.py`;
`PACKAGE_INTEGRITY_MANIFEST.md`; `src/tios/ops/self_modification.py`.
Status: **Integrity exception bounded to v8.127 reconciliation; external trust ownership selected,
activation and independent reviewer evidence still pending. No candidate admission, strategy
promotion, production venue, live order, or real-money authority granted.**

### D-116 — One-time v8.134 integrity reconciliation authorized for reviewed dashboard navigation

Decision: the operator authorizes exactly one controlled integrity reconciliation for v8.134 to
integrate the current reviewed diffs in `src/tios/services/dashboard_ui/dashboard.html` and
`tests/test_dashboard.py`. For this reconciliation only, `PACKAGE_INTEGRITY_MANIFEST.md` may be
edited solely to update its package-version line, both existing duplicate hash rows for
`src/tios/services/dashboard_ui/dashboard.html`, both existing duplicate hash rows for
`tests/test_dashboard.py`, and the existing hash row for `DECISION_LOG.md`. No manifest row may be
added or removed. The changelog must record the same bounded change. This exception is exhausted
when that reconciliation is complete and grants no continuing manifest-edit authority.

The dashboard change adds a read-only link to the full external TradingView chart and governed
navigation from the embedded-chart context to the OS metrics and OS strategies views. The UI
states that the embedded selector is indicator-only, retains TradingView as external visual
context rather than OS evidence, and creates no order surface. The focused test change pins those
labels, links, navigation hooks, and boundaries. The existing optional
`docs/supervisor/TRADINGVIEW_STRATEGY_INDICATOR_PATTERN_CATALOG_PLAN_2026-07-23.md` remains a
proposed research/catalog plan with execution authority `NONE`; its presence does not authorize
implementation, research trials, strategy admission, promotion, venue connection, paper/live
trading, or real-money activity.

`PACKAGE_INTEGRITY_MANIFEST.md` remains in `IMMUTABLE_PATHS`. This exception does not authorize any
edit to `src/tios/ops/self_modification.py`, `Makefile`, thresholds, prospective, holdout, sealed,
runtime, data, or any other immutable or manifest-listed path. It changes no research protocol,
outcome evidence, approval criterion, or authority boundary.

Evidence: explicit operator authorization on 2026-07-23; reviewed diffs for
`src/tios/services/dashboard_ui/dashboard.html` and `tests/test_dashboard.py`;
`docs/supervisor/TRADINGVIEW_STRATEGY_INDICATOR_PATTERN_CATALOG_PLAN_2026-07-23.md`;
`PACKAGE_INTEGRITY_MANIFEST.md`; `src/tios/ops/self_modification.py`.
Status: **One-time exception limited to the v8.134 package-version line and five existing hash-row
occurrences: dashboard HTML ×2, dashboard test ×2, and decision log ×1. Authority remains `NONE`;
no admission, promotion, venue, order, live, or real-money authority is granted.**

### D-117 — Stage B demo-evidence v2 implemented (default-disabled, activation-gated); one-time v8.146 integrity/decision-log exception

Decision: the operator authorizes Option A of the 2026-07-23 Stage B demo-evidence security
decision packet — full evidence-first Stage B — for implementation and testing only, plus the
separate one-time `STAGE-B-DEMO-EVIDENCE-ONLY` integrity/decision-log exception for v8.146. This
records that the capability is now implemented, default-disabled, and `NOT_ACTIVATED`.

Exact scope: a new append-only decision-evidence chain with schema
`tios.demo_decision_evidence.v2`, written by one fixed, non-pluggable, sanitized sink invoked only
under the existing exclusive lane lock in the fake-money Bybit venue-demo lane. It is offline and
default-disabled: the complete runtime root `artifacts/evidence/private_demo/stage_b_v2/` is absent
during implementation and tests, and absence means `NOT_ACTIVATED` — it never silently falls back
to enabled behavior. The v2 chain is separate from and does not upgrade, append, or reuse the
unchanged Stage A v1 evidence.

Implemented across Waves 1–3: commit `cbd2196` (Wave 1) the offline v2 event/state-machine
contract, content-addressed manifest-last storage, sanitizer, 513-frame scale, and 30-episode
cohort projection; commit `06a6185` (Wave 2) default-disabled venue-demo integration with
validated `orderLinkId` client-key correlation, persist-before-POST durability, execution
reconciliation, exact-execution `lane_base`, and the entry-block/risk-reducing-bypass protocol;
commit `56e9e1a` (Wave 3, current HEAD) the aggregate-only redacted dashboard projection over the
unchanged `/api/v1/demo-lane` route. Wave 4 is this governance and manifest reconciliation.

Evidence behavior: generations are append-only and content-addressed with the manifest written
last as the sole commit point; a risk-increasing submission is blocked until its pre-submission
evidence (including the reserved client idempotency key) is durably committed and `fsync`-verified;
a risk-reducing exit, protective-stop create/replace/cleanup, cancel, kill-switch, or
reconciliation is never blocked by an evidence-store failure; disclosure is aggregate-only in
fixed, non-overlapping 30-episode cohorts, with the aggregate `null` until a cohort is complete;
evidence degradation fails closed to `EVIDENCE_DEGRADED` + `ENTRY_BLOCK` (exit-only) and does not
auto-clear on restart or the next successful write.

Non-authority: `execution_authority=NONE` and `real_money=false` throughout. Stage B cannot
create, size, route, retry, cancel, or approve an order; cannot validate, promote, admit, or
auto-tune a strategy; cannot connect a production venue or authorize live/real-money activity; and
adds no dashboard mutation surface.

Activation is separately gated (Rollout 5) and is **not** authorized by this decision. It
additionally requires a verified-flat lane with no unresolved submission/order, a controlled
Makefile-target restart, `0700`/`0600` raw-lane and private-evidence mode hardening, activation
receipt and private alias material creation, recorded rollback identity, independent security
review binding the exact commit/diff/hashes/schema/tests, and the operator's separate exact
activation statement from the packet.

Explicit pre-activation debt: a deterministic pre-send metadata/parse error on the active exit
path freezes the lane into a `POST_UNKNOWN` fail-safe (query/recovery-only, no automatic create
replay); this is documented and test-pinned and must be resolved before any activation.

For this reconciliation only, `PACKAGE_INTEGRITY_MANIFEST.md` may be edited solely to update its
package-version line to v8.146 and the SHA-256 value in these existing rows: `PROJECT_STATE.md`
(one), `DECISION_LOG.md` (one), `docs/architecture/AD.md` (one),
`src/tios/services/dashboard_ui/dashboard.html` (two duplicate rows), and
`tests/test_dashboard.py` (two duplicate rows). No manifest row may be added, removed, reordered,
or otherwise changed. `PACKAGE_CHANGELOG.md` records the same bounded change. This exception is
exhausted when the v8.146 reconciliation is complete and grants no continuing manifest-edit
authority. It authorizes no other `IMMUTABLE_PATHS`, threshold, research protocol, prospective,
holdout, or sealed change. D-115 and D-116 are exhausted and confer no Stage B authority.

Evidence: operator authorization for Option A implementation/testing and the separate
`STAGE-B-DEMO-EVIDENCE-ONLY` v8.146 integrity/decision-log exception, granted per the 2026-07-23
security decision packet and stated by the operator in the 2026-07-24 implementation session
(which also confirmed this reconciliation);
`docs/supervisor/STAGE_B_DEMO_EVIDENCE_SECURITY_DECISION_PACKET_2026-07-23.md`;
`docs/supervisor/STAGE_B_IMPLEMENTATION_SCOPE_AND_INTEGRITY_EXCEPTION_2026-07-23.md`; the three
Wave commits `cbd2196`, `06a6185`, and `56e9e1a`; `PACKAGE_INTEGRITY_MANIFEST.md`;
`PACKAGE_CHANGELOG.md`; `src/tios/ops/self_modification.py`.
Status: **Stage B demo-evidence v2 IMPLEMENTED, default-disabled, `NOT_ACTIVATED`; activation
separately gated. One-time exception limited to the v8.146 package-version line and six existing
hash-row occurrences: project state ×1, decision log ×1, architecture doc ×1, dashboard HTML ×2,
and dashboard test ×2. Authority remains `NONE`; no admission, promotion, venue, order, live, or
real-money authority is granted.**

### D-118 — Operator-directed dashboard control panel + live auto-refresh; audited spawn surface extended with START_ACTIVITY; confluence lane tuned for demo traffic

Decision: on operator direction (2026-07-26) to stop driving the demo lanes from the terminal and
control them from the dashboard, the D-106 audited spawn surface is extended with one new
allowlisted action, `START_ACTIVITY`, and an overview-page control panel (Start Activity Lane,
Start ETH Lane, Run Once, Stop). `START_ACTIVITY` spawns the fixed argv
`[sys.executable, scripts/demo_eth_lane.py, --activity, --loop, --interval, 5m]` via the same
`_spawn` mechanism as the existing actions: allowlist-gated (exact `ACTIONS` membership, mutated
strings rejected and never reflected), fixed argv built only from module constants (`shell=False`,
no request/free-form input reaches the command), refused with 409 when a lane already holds
`lane.lock` (with the lane's own `exclusive_lane_lock` exit-3 as a second anti-double-spawn layer),
audited to `artifacts/human_decisions/demo_lane_actions.jsonl`, and halted by the existing `STOP`
kill switch (the activity lane checks `lane.kill_switch_active()` on the same `KILL_SWITCH` path
each cycle). The dashboard demo-lane view also gains a ~5s read-only auto-refresh (GET of
`/api/v1/demo-lane`, in-flight-guarded, paused when the tab is hidden). Separately, the confluence
activity lane is tuned for demo VISIBILITY, not edge: the 4h timeframe is dropped
(`{5m,15m,1h}`) and `ENTRY_THRESHOLD` lowered `0.25 → 0.15` so the lane produces frequent visible
demo trades; this widens the entry gate for traffic and is explicitly NOT a claim of predictive
edge. Execution remains human-initiated: the operator clicks Start; the assistant does not run the
order-placing lane. This is a normal package reconciliation (v8.149) under the D-030/T-000-02
regeneration rule — the edited manifest-tracked files (`dashboard.html` ×2, `tests/test_dashboard.py`
×2, this decision log ×1) are rehashed; it is NOT an integrity exception and grants no manifest-edit
authority beyond rehashing edited files.

Evidence: operator direction in the 2026-07-26 session (dashboard buttons for all runnable
commands, a live non-reloading dashboard, and ≥5 demo trades / 30 min); an independent read-only
market-data frequency probe (37/40 coins, no orders) establishing that `{5m,15m,1h}` at entry 0.15
yields a cold-start burst well above 5 trades and ~4–5/30 min sustained; an independent adversarial
security review of the spawn-surface extension returning GO / PASS with no blocking findings
(command-injection, allowlist, double-spawn, kill-switch, audit, and frontend surfaces all verified
against source); `PACKAGE_INTEGRITY_MANIFEST.md`; `PACKAGE_CHANGELOG.md`.
Status: **Dashboard demo-lane control panel + live auto-refresh SHIPPED; confluence lane tuned for
demo traffic. Fake-money demo only; execution authority `NONE`; nothing validated or promoted;
demo P&L remains non-evidence. Execution stays human-initiated (operator clicks Start). No venue,
order, live, or real-money authority is granted.**

### D-119 — Dashboard control center: START_MULTI + START_RESEARCH spawn actions, read-only report views; research-guard hardened, TOCTOU ceiling deferred to operator

Decision: on operator direction (2026-07-26, "add everything we can"), the dashboard becomes an
operator control center with three labeled sections. ACTIONS (allowlisted + fixed-argv + audited,
the D-106 pattern) gain two entries: `START_MULTI` (order-path, spawns `demo_eth_lane.py --multi`,
lane.lock-gated 409, audited, STOP kill switch halts it) and `START_RESEARCH` (research-only, NO
orders, authority NONE — spawns `run_universe_search.py`, not lane-lock-gated, guarded by a separate
PID-liveness research lock, detached, audited; missing script → 503). VIEWS (read-only GET, NO
subprocess): `/api/v1/demo-trades`, `/api/v1/demo-status`, `/api/v1/research-findings`, each a
library call into the existing report modules returning `schema_version 1` and failing closed to
`{available:false, report:null}`; the research view preserves the honest LEADS-not-edges /
multiple-testing / cross-coin-correlation / UNVALIDATED framing. Pre-existing four actions are
byte-identical. An independent adversarial security review returned PASS (no blocking findings):
argv integrity, allowlist, START_MULTI double-spawn, the read-only/fixed-name-import/no-path-traversal
view surface, and escaped rendering all verified against source. Two non-blocking research-guard
findings: (A) `_research_running` could crash on a hostile/huge pid — FIXED (guard now rejects
bool/non-positive pids and treats any liveness-probe failure as not-running, fail-closed, + a
parametrized hostile-lock test); (B) a check-then-spawn TOCTOU could let a concurrent burst /
double-click launch >1 research process (the script has no self-lock) — NOT fixed; deferred to the
operator as a documented ceiling (research-only, no orders; the clean fix is giving
run_universe_search.py the same flock/exit-3 self-lock the trading lanes have). Normal package
reconciliation (v8.150) under D-030/T-000-02: edited manifest-tracked files
(`dashboard_ui/server.py`, `dashboard.html` ×2, `tests/test_dashboard.py` ×2, this decision log ×1)
rehashed; NOT an integrity exception.

Evidence: operator direction in the 2026-07-26 session ("add everything we can … I will decide what
runs manually, automatically, or by AI"); the independent security review (PASS with two non-blocking
notes, Finding A fixed, Finding B deferred); `PACKAGE_INTEGRITY_MANIFEST.md`; `PACKAGE_CHANGELOG.md`.
Status: **Control center SHIPPED (5 lane/research actions + 3 read-only views). Fake-money demo only;
research is offline/no-orders; execution authority `NONE`; nothing validated or promoted; demo P&L
and research leads remain non-evidence. Execution stays human-initiated. Known non-blocking research
double-spawn ceiling flagged for operator decision. No venue, order, live, or real-money authority is
granted.**

### D-120 — Watch/Lab dashboard split + Live cockpit; two P&L reporting defects found by live multi-coin execution and fixed; duplicate round-trip folder deleted

Decision: on operator direction (2026-07-26, "organize and improve the frontend … more understandable
and fun to watch … a lot of things are redundant for a user"), the dashboard is split into a
user-facing **Watch** mode (`Live`, `Wallet`) and a collapsed-by-default **Lab ▸** group holding the
ten pre-existing developer/governance pages (Overview, Signals, Trading, Testing, Research,
Operations, Library, Skills, TODO, Settings). NO page is deleted or made unreachable; `Live` becomes
the landing view. The new `Live` page answers four questions in order — what it is doing now (event
feed), what is closest to firing (agreement leaderboard), what it holds (position cards), how it has
gone (equity sparkline) — fed by two NEW read-only GET endpoints, `/api/v1/live-feed` (events derived
from `orders.jsonl` + activity heartbeats: ENTER/EXIT/STOP_ARMED/SCAN/REJECT with reasons, lane
status, scan cadence) and `/api/v1/equity-curve` (cumulative realised P&L over closed round trips).
Both are pure projections: GET only, no subprocess, no writes, fixed paths, `schema_version 1`,
fail-closed, with rejection detail drawn from a closed allowlist so venue error text, order ids,
wallet balances, paths and pids can never reach a client. The Live page's lane controls REUSE the
existing allowlisted `START_ACTIVITY`/`START`/`STOP` actions through the existing audited POST path —
no new command surface. Stage B remains aggregate-only and outside these endpoints.

**Honest-labelling decision (doctrine, binding on future UI work):** a more engaging dashboard makes
an UNVALIDATED fake-money lane easier to mistake for a validated edge, so the framing is part of the
design, not a disclaimer bolted on. The confluence score is labelled **"agreement"** and never
"confidence" or anything implying probability of profit — it is weighted agreement among strategies
that are heavily correlated with each other, on a gate deliberately loosened to 0.15 for traffic
(D-118). The equity curve is labelled **"execution measurement — not edge"** and renders the
endpoint's disclaimer verbatim. Fake-money / authority-NONE / UNVALIDATED badges stay pinned.

**Two P&L reporting defects, found only because the lane ran for real, now fixed.** The operator
started the confluence lane; it opened **12 positions in 90 seconds** (AAVE, APT, AXS, BCH, BNB, BTC,
ETH, LINK, RUNE, SOL, TIA, UNI, all filled) and the shared total-capital cap bound at exactly
12 × $25 = $300, correctly refusing further entries — the cap's first real multi-coin exercise, and it
held. That live state exposed: (a) `scripts/report_demo_trades.py::round_trips` held a SINGLE global
entry slot, so it reported "1 open" while 12 positions were live, silently discarding 11 entries, and
could pair one coin's exit against another coin's entry (wrong realised P&L). Entries are now keyed
per `(symbol, strategy)`, so concurrent positions all surface and the breakout and confluence lanes
can never cross-pair on a shared symbol; untagged legacy records key `(None, None)` so an ETH-only
ledger folds byte-identically. (b) `_order_money` read a hardcoded `reconcile["ETH_delta"]`, reporting
`size_base = 0` for every non-ETH position; size now derives from the traded coin's own
`<BASE>_delta`. P&L was unaffected by (b) (it uses `USDT_delta`). Trip rows now carry `symbol` and
`strategy`, and the report table gained a Coin column — a 12-row multi-coin report was unreadable
without it. Three regression tests pin the behaviour, including one proving ETHUSDT in two lanes never
cross-pairs; an independent reviewer confirmed by hand that they fail against the pre-fix code.
Additionally the dashboard's private duplicate `_round_trips` (single-slot, hardcoded `ETHUSDT` — the
same defect class, zero callers) was DELETED rather than left as a landmine; `report_demo_trades` is
now the repo's only round-trip folder.

Evidence: operator direction in the 2026-07-26 session; the live `orders.jsonl` burst of 12 filled
ACTIVITY-CONFLUENCE entries 14:53:02–14:54:32Z with the $300 cap binding; an independent adversarial
review returning GO/PASS on all three parts, which traced the money-pairing fix by hand, confirmed
the legacy fold is byte-identical, verified the new tests distinguish old from new behaviour, and
verified no-leak / fail-closed / escaping / no-new-command-surface (its non-blocking notes — orphan-sell
and scale-in silently losing cost basis, both pre-existing; a SCAN-clustering heuristic that may split
a slow cycle cosmetically; an unlogged `_base_delta` fallback — are recorded, not fixed);
`PACKAGE_INTEGRITY_MANIFEST.md`; `PACKAGE_CHANGELOG.md`. Normal package reconciliation (v8.151) under
D-030/T-000-02 — manifest-tracked `dashboard_ui/server.py`, `dashboard.html` ×2,
`tests/test_dashboard.py` ×2 and this decision log ×1 rehashed; NOT an integrity exception.
Status: **Watch/Lab dashboard + Live cockpit SHIPPED; two P&L reporting defects FIXED; duplicate
round-trip folder DELETED. Fake-money demo only; execution authority `NONE`; nothing validated or
promoted. Demo P&L is execution measurement and remains NON-EVIDENCE of edge; "agreement" is not a
probability of profit. Execution stays human-initiated. No venue, order, live, or real-money authority
is granted.**

### D-121 — Integration completion: scale-in/orphan-fill money gaps closed, research self-lock (Finding B) closed, honest Watch status + Automation control map; "money printer" framing rejected on the evidence

Decision: the operator asked to finish the app and reach "a money printer like you said". That framing is
REJECTED and corrected on the record: the assistant's statement was the OPPOSITE — a warning that a
livelier dashboard is how an UNVALIDATED fake-money lane starts *feeling* like a money printer. The
project's own evidence stands: 20+ public strategies × 40 coins → **0 validated**; all 7 families
searched → ALL FAIL; a prior CFTC "PASS" was RETRACTED for a sample-count inflation bug; the confluence
lane passed nothing and its gate was deliberately loosened to 0.15 for traffic (D-118); the closed record
is n=1. What was delivered is a fully integrated, continuously running **measurement instrument**, not a
profit machine, and no real-money or advisory step is authorized or taken.

Measured structural finding (recorded because it bounds the operator's stated goal of "a trade every few
minutes"): trade frequency is bounded by capital ÷ position size, then by turnover — NOT by the number of
strategies, coins or timeframes scanned. The lane opened 12 positions in 90 seconds (the cold-start burst
filling empty slots), deployed 12 × $25 = $300 = the entire shared cap, and then correctly idled: as of
the same session all 12 held coins still showed agreement +0.25..+1.00 (none near the 0.05 exit gate)
while 7 unheld coins were entry-ready but unfundable. At the observed 0.1% per-fill fee (~0.2% round
trip), churning all 12 slots every 30 minutes would burn ~$28.80/day ≈ **~10% of a $300 account per day
in fees alone**, requiring >0.2% reliable edge per round trip merely to break even — against a signal
with none demonstrated. Higher churn on a zero-edge signal is a fee pump, not a printer. Levers that
raise visible activity (smaller position size, tighter exit gate, adding the short side) are therefore
recorded as ACTIVITY levers only; none creates edge and each increases fee drag.

Changes, all fake-money / read-only / authority NONE, verified by an independent adversarial review
returning GO with no blocking findings:
- **Money-correctness (`scripts/report_demo_trades.py`).** `round_trips` became `fold_fills(filled) ->
  (trips, unmatched)`, with `round_trips()` kept as a thin wrapper so `build_equity_curve`'s library
  contract and `summarize(trips)`'s arity are untouched. (a) A repeat Buy on an already-open
  `(symbol, strategy)` key now AGGREGATES cost basis (summed spend/size/fees, size-weighted entry price)
  instead of overwriting it; the pre-fix overwrite dropped the first buy and OVER-reported that trip
  (+35 where the truth is +10 — the failure direction that flatters the account). Cost-basis aggregation
  (not FIFO) was chosen and the justification was independently verified against the lane code: an entry
  fires only when the per-key position is flat and every exit path (EXIT_LONG, disaster stop, venue
  resting stop) sells the WHOLE `lane_base`, so no partial exit or per-lot matching exists and FIFO would
  actively over-report. (b) A Sell with no open entry, or a fill with an unrecognised side, is now
  surfaced as an UNMATCHED fill (`unmatched_fills` in report and summary, `unmatched_fees_usd`, a
  markdown section only when non-zero) — never dropped, never given a fabricated P&L. `total_fees_usd`
  keeps its exact prior definition; `summarize(trips)` without the new list reports `None`, not a false
  `0`. The legacy untagged `(None, None)` ETH-only fold is byte-identical, pinned by an exact-trip-list
  test. NOTE: both new paths are currently unreachable by lane design (it only buys when flat; zero
  orphan sells exist) — this is hardening, not a correction of numbers already read.
- **Research self-lock, closing D-119's deferred Finding B (`scripts/run_universe_search.py`).** The
  script now acquires its own non-blocking `fcntl.flock` and returns exit code **3** on contention before
  any output work, never truncating a live holder's record and never partially writing the report,
  releasing on every path including exceptions — the same `exclusive_lane_lock`/exit-3 pattern the trading
  lanes use. The dashboard's PID-liveness probe is retained as fast 409 feedback but is no longer the
  guarantee; `demo_lane.py`'s change is comments/docstrings ONLY (zero executable lines) and the
  allowlist, fixed argv, audit write and 409/503 status codes are untouched. Single-run output path
  (filename, JSON format, stdout) byte-identical.
- **Honest Watch status + Automation control map (`dashboard.html`).** Root cause of the alarming global
  "Some sources unavailable" banner: `build_cockpit`'s freshness array contains NO demo-lane entry at all,
  so the banner could never describe the only subsystem the Watch pages depend on. Watch pages now derive
  status from `/api/v1/demo-lane` and go green ONLY when a heartbeat is genuinely fresh, degrading
  distinctly for stale heartbeats / stopped lane / missing payload / fetch failure / schema mismatch; Lab
  keeps the full raw detail byte-for-byte, and each source chip gained a plain-language explainer.
  Investigation confirmed nothing is broken: PAPER_RUNTIME is permanently unavailable by design (it needs
  an approved strategy and there are none), COINDESK_DATA_NEWS is unconfigured by choice, RESEARCH_DATA
  "Delayed" only means >15 min since refresh. One pre-existing over-generous label is now stated honestly
  rather than papered over: RESEARCH_JOBS "Live" means only that the jobs store is readable. A new
  read-only Lab page **Automation** inventories all capabilities with their real commands/endpoints,
  grouped deterministic-zero-AI / judgement-AI-assisted / human-gated-execution, guarded by an
  anti-fiction test that checks every cited route against the server, every `make` target against the
  Makefile and every script path against disk. It adds NO input, POST path, action name or scheduler.
- **Execution boundary reaffirmed and made explicit in the product:** order-placing lanes are
  **human-armed only**. No scheduler, cron, timer or background job in this system can start an
  order-placing lane, and none was added. Automating the deterministic half (reports, screens, research,
  gates) is free; starting the money side stays an explicit human click. Any future auto-arming of
  trading must be designed deliberately (explicit armed state + expiry), never introduced incidentally.

Parked (recorded, NOT fixed — each needs its own reviewed change): (1) `load_filled()` admits only
`order_status == "Filled"`, so a `PartiallyFilledCanceled` row — a terminal status the lane defines —
would be filtered out BEFORE the fold and appear as neither a trip nor an unmatched fill despite real
wallet movement; the new "nothing vanishes" guarantee is scoped to the fold loop, not the whole
ledger→report pipeline (zero such rows exist today). (2) No test locks 3+ successive scale-ins for
bounded rounding drift. (3) The exit-3 contention path is hand-verified but not test-locked in
`tests/test_universe_search.py`. (4) An orphan sell followed by a fresh buy+close on the same key is
traced correct but not test-locked.

Evidence: operator direction in the 2026-07-26 session; the live `orders.jsonl` (12 filled
ACTIVITY-CONFLUENCE entries 14:53:02–14:54:32Z, $300 cap bound, 0 exits) and the 37 activity heartbeats
read read-only at 15:44Z for the agreement spread; the independent review (GO, no blocking findings) which
hand-verified the aggregation arithmetic, traced the no-partial-exit invariant through
`demo_eth_lane.run_cycle`/disaster stop/resting stop and `demo_activity_lane`, empirically confirmed
exit-3 leaves the report untouched, and independently spot-checked the Automation page's citations rather
than trusting its own anti-fiction test; `PACKAGE_INTEGRITY_MANIFEST.md`; `PACKAGE_CHANGELOG.md`. Normal
package reconciliation (v8.152) under D-030/T-000-02 — manifest-tracked `dashboard.html` ×2,
`tests/test_dashboard.py` ×2 and this decision log ×1 rehashed; NOT an integrity exception.
Status: **Integration COMPLETE as a measurement instrument: money-correctness gaps closed, Finding B
closed, Watch status honest, Automation map shipped. "Money printer" framing REJECTED — 0 validated
strategies, demo P&L is NON-EVIDENCE, and high-frequency churn on an unvalidated signal is fee-negative
(~10%/day of a $300 account at 30-minute full turnover). Fake-money demo only; execution authority
`NONE`; order-placing stays HUMAN-ARMED ONLY; no scheduler may start a lane. Four items parked. No venue,
order, live, or real-money authority is granted, and no investment advice is given.**

### D-122 — Wallet page answers the money questions; venue holdings deliberately subordinated to lane budget so a pre-funded demo balance can never read as performance

Decision: the operator reported that the Watch split was still unintelligible — "what is the difference
between live and wallet? … i dont know how much money my wallet holds, how much was spent, how much we
can spend for a single trade, positions list, graphs, real charts". The diagnosis was accepted as a real
product defect and partly a naming error introduced in D-120: `Wallet` was a RELABELLED LEGACY per-coin
page that never showed a balance, budget, free capital or per-trade size. Each WATCH page now carries a
one-line subtitle that distinguishes it (`Live` = what the system is doing right now; `Wallet` = the
money), and a new read-only `GET /api/v1/wallet` endpoint plus a rebuilt Wallet page answer each question
directly: venue balances, lane cap, deployed, free, per-trade size, slot count, the full open-position
table (size, entry, mark, value, unrealised $/%, time held, stop, distance-to-stop), realised/unrealised
totals, and two honest inline-SVG charts (equity sparkline reused from the Live page — one shared
implementation, not a copy — plus a deployed-vs-free allocation bar).

**Framing decision (binding, extends D-120's honest-labelling doctrine).** The venue demo wallet holds
~$99.7k of PRE-FUNDED fake money (seeded ~1 BTC, ~1 ETH, 50k USDC, ~50k USDT before any trading). That
total is NOT performance and NOT operator funds, and the lane never touches more than its $300 cap. The
API therefore keeps `venue.*` and `budget.*`/`realised.*` as separate blocks that are NEVER summed and
exposes no derived field mixing them; a test asserts the combined `99673` figure never appears in the
response body at all. On the page the LANE BUDGET is the headline with big-number styling ($300 cap /
$300 deployed / $0 free / $25 per position / 12-of-12 slots, plus a plain-language line explaining that
no new position can open until one exits — the answer to "why is nothing happening"), while the venue
balance list renders LAST, visually secondary, with no big-number styling and led by a "read this first"
note. Rationale: a pre-funded balance presented as a headline would read as "I have $99.7k and the bot
earned it", and both halves of that are false.

**No fabricated data.** The operator asked for "real charts"; only charts backed by payload data were
drawn. No price/candlestick chart exists because no endpoint in this view carries OHLC history — the page
states "no price history in this view" rather than inventing a series. Real price charts remain an
unbuilt feature requiring kline fetch/storage. Null marks render as em dashes, never invented zeros.

Measured state at build time (read-only, from the live artifacts): budget cap $300, deployed $300, free
$0, 12/12 slots, per-trade $25, disaster stop −15%; realised +$0.5379 (1 closed, 1W/0L), fees $0.3506,
unrealised +$1.6267 across 12 open positions held ~135 min. Recorded with the standing caveat that this
is ~4 hours of n=12 noise and that the 12 positions are NOT independent bets — all are long, all crypto,
all opened within 90 seconds on strategies that agree largely because they are correlated, so the
multi-coin spread reads as diversification while behaving as a single directional exposure.

Evidence: operator's 2026-07-26 message; the live `orders.jsonl` `wallet_after` snapshot (14 balances)
and the lane constants `TOTAL_DEMO_CAPITAL_USDT=300` / `BUY_QUOTE_USDT=25` / `DEMO_DISASTER_STOP_PCT=0.15`;
an independent review returning GO with no blocking findings, which hash-verified all five files,
live-called `build_wallet(Path('.'))` and inspected the projection field by field, and confirmed the
venue/lane separation, single-source-of-truth reuse (`report_demo_trades` fold + the existing
`_position_projection`/`_protection_projection`, no second mark or P&L formula), leak-freedom,
fail-closed identical key sets, and the shared equity renderer. Non-blocking notes recorded: the lane
capital constants are mirrored rather than imported (matching the file's existing convention for
`DEMO_DISASTER_STOP_PCT`) and so could desync if the lane's cap changes; `orders.jsonl` is read twice per
request; a ledger of only non-filled records yields `available:true` with empty balances.
`PACKAGE_INTEGRITY_MANIFEST.md`; `PACKAGE_CHANGELOG.md`. Normal reconciliation (v8.153) under
D-030/T-000-02 — `dashboard.html` ×2, `tests/test_dashboard.py` ×2 and this decision log ×1 rehashed;
NOT an integrity exception.
Status: **Wallet page SHIPPED and answers the operator's money questions on one surface. Venue holdings
are structurally subordinated to lane budget and can never be summed with or presented as performance.
Fake-money demo only; execution authority `NONE`; 0 validated strategies; demo P&L remains NON-EVIDENCE.
No price chart is drawn because no price history exists in this view. No venue, order, live, or
real-money authority is granted, and no investment advice is given.**

### D-123 — Four D-121 parked items cleared; lane captures the bars it already fetches so real price charts exist; first live turnover confirms the fee-drag arithmetic

Decision: on operator instruction ("complete them") the four items parked in D-121 were cleared and the
price-chart gap left open in D-122 was closed honestly.

**Parked item 1 (money visibility, the only logic change).** `load_filled()` admitted only
`ok is True and order_status == "Filled"`, so a `PartiallyFilledCanceled` row — a terminal status the lane
defines, where part of the order genuinely filled and the remainder was cancelled, carrying a REAL
reconciled wallet delta — was filtered out before the fold and appeared as neither a trip nor an unmatched
fill. It is now admitted **only** when `order_status == "PartiallyFilledCanceled"` AND the reconciled delta
is non-zero, and is surfaced as an unmatched fill with `reason: "partial_fill_cancelled"` — never folded
into a trip, never priced. Folding it was rejected on evidence from the lane itself: `run_cycle` credits
`lane_base` only under `if action.get("ok")` and `entry_price_from_ledger` likewise gates on `ok`, so the
lane never treats a partial fill as a position; folding it would invent a position no exit could ever
close, or book a whole cost basis against partial proceeds — a fabricated P&L in the flattering direction.
The other `ok: False` write sites (`kill_switch`, `price_unavailable`, `qty_below_step`, `place` failure)
carry no `reconcile` block at all, and `Cancelled`/`Rejected` fail the exact status match, so no rejected
order can become a trade or move the win rate. `total_fees_usd` keeps its prior trips-only meaning with
partial-fill fees isolated in `unmatched_fees_usd`; all public signatures and existing keys are unchanged
for the `build_equity_curve`/`build_wallet` library callers. Verified byte-identical on the real ledger via
a frozen snapshot (the live ledger is being appended to by a running lane): today's 16 rows are all
`Filled`, so nothing changed.
**Parked items 2–4 (tests only).** 3+ successive scale-ins now pin exact money and a bounded weighted-entry
drift; the research self-lock's exit-3 contention path is test-locked (flock held on a second in-process
FD, `build_report` monkeypatched to fail, pre-seeded report asserted byte-identical, no real search run);
an orphan sell followed by a fresh buy+close on the same key is proven not to corrupt the later trip.

**Price history (order-path change, reviewed as such).** The lane already FETCHES a window of closed bars
every cycle and discarded them. It now persists them to
`artifacts/trading_domain/demo_lane/price_history_<SYMBOL>.json` (bounded 288 points, deduped by bar close
time, atomic tmp+replace, interval-guarded) with **ZERO new venue calls** — `scripts/demo_activity_lane.py`
needed no edit because its prefetched reference bars already flow through `run_cycle`. The diff to the
order-path file is **83 insertions, 0 deletions**: the write sits after the durable `final_state` write and
immediately before the existing heartbeat write, with no order submission, kill-switch check or state
transition below it, and the `try` wraps the whole call expression so even argument evaluation cannot
escape the guard. **The binding invariant — a price-history failure must never block or delay a
risk-reducing order — is test-locked for both an entry and a −15% disaster-stop sell with the writer forced
to raise.** Because the lane seeds from the window it already holds, real history exists from the first
cycle rather than accumulating from zero.

**Charts (read-only).** New `GET /api/v1/price-history` (no query parameters, no request-derived path,
symbol regex-gated before any filename is built) emits a series only for coins the lane currently HOLDS,
with the held set, ordering and `entry_price`/`stop_price`/`mark_price` all reused verbatim from
`build_wallet` — no second mark, stop precedence or held-set derivation. Missing/malformed files degrade
per series; the fail-closed shape keeps an identical key set. The Wallet page draws each position's price
path with its entry and stop levels marked. Honest-framing decisions: `interval` returns `null` rather than
a guessed cadence when no file exists; coins still collecting are NAMED rather than silently dropped;
0/1/flat-point series render a note, a single dot, or a midline rather than a fabricated or broken line;
and every chart is captioned as a CAPPED, lane-captured RECORD — explicitly not a full exchange chart, not
a forecast, not a signal. This closes D-122's "no price chart" gap without inventing data: the research
parquets were rejected as a source (~13h stale, 15 of 40 coins at 1h) because stale prices beside live
marks would mislead.

**Measured during this change — the fee-drag arithmetic of D-121 confirmed in production.** The lane
completed its first turnover: APTUSDT's agreement fell below the exit gate and it sold at 17:16:52Z
(entry 0.6293 → exit 0.6289), freeing a slot that ADAUSDT took ~6 minutes later. The price moved **−0.064%**
but the round trip realised **−0.28% (−$0.0702)** — fees (~$0.05) were roughly **3× the price move**. A trade
essentially flat on the market still lost money. Realised fell $0.5379 → $0.4677 and the win rate moved
from a meaningless 100% (n=1) to 50% (1W/1L). This is direct evidence for D-121's conclusion that
high-frequency churn on an unvalidated signal is fee-negative, and that every round trip must clear a
~0.2% hurdle merely to break even.

Evidence: operator instruction 2026-07-26; the live `orders.jsonl` (APT exit + ADA entry, 2 closed / 12
open, realised $0.4677, fees $0.4006) read read-only; an independent adversarial review returning GO with
no blocking findings across all three parts, which hash-verified 11 files, walked `run_cycle` top to bottom
to confirm nothing order-related executes after the new write, traced every `ok: False` ledger-write site to
confirm no rejected order can be admitted, and checked the real ledger for partial-fill rows (none).
Non-blocking notes recorded: `except Exception` does not catch `KeyboardInterrupt`/`SystemExit` (would skip
one heartbeat write, no order impact); price-history files are keyed by symbol not lane, so alternating
`--multi` and `--activity` on a shared coin restarts that chart series (continuity only); dedup keyed on bar
timestamp would keep a stale close if a venue ever revised a closed kline. `PACKAGE_INTEGRITY_MANIFEST.md`;
`PACKAGE_CHANGELOG.md`. Normal reconciliation (v8.154) under D-030/T-000-02 — `dashboard_ui/server.py`,
`dashboard.html` ×2, `tests/test_dashboard.py` ×2 and this decision log ×1 rehashed; NOT an integrity
exception.
Status: **All four D-121 parked items CLEARED; price capture and real position charts SHIPPED. The
risk-reducing-order invariant is preserved and test-locked. Fake-money demo only; execution authority
`NONE`; 0 validated strategies; demo P&L remains NON-EVIDENCE and charts are a record, never a forecast.
The running lane must be restarted to begin capturing price history. No venue, order, live, or real-money
authority is granted, and no investment advice is given.**

### D-124 — SSOT resync after eight versions of documentation drift; two undocumented POST write routes found; fee drag confirmed in production at 101.8% of gross

Decision: the operator asked whether the architecture and state documents had been updated. They had NOT.
`DECISION_LOG.md`, `PACKAGE_CHANGELOG.md` and `PACKAGE_INTEGRITY_MANIFEST.md` were kept current through
every release, but `docs/architecture/AD.md` and `PROJECT_STATE.md` were last touched at v8.146
(commit 77235d9, 2026-07-25) and were therefore **eight versions stale** while the package reached v8.154.
Because `PROJECT_STATE.md` is the project's single authoritative task/state entry point, this was an SSOT
integrity defect, not a cosmetic one. Root cause worth recording: the integrity gate hash-verifies these
files but cannot detect that their CONTENT has stopped describing the system, so nothing failed while they
rotted — the drift was caught by the operator, not by tooling. Both documents are now resynced to v8.154
from the changelog and decision log, with every statement verified against the code (code wins on conflict).

`AD.md` gains: the confluence activity lane (roster, `{5m,15m,1h}` weights, hysteresis 0.15/0.05, per-coin
state, shared lock/kill-switch/cap); the capital model (`$300` cap, `$25`/position → 12 slots, −15% stop)
and the finding that trade frequency is bounded by capital ÷ position size then turnover; price-history
capture with its exact position in `run_cycle` (below every order path) and the risk-reducing-order
invariant; the verified read-only GET surface and the six allowlisted fixed-argv audited actions; the
Watch/Lab split and the poller/`schema_version === 1` contract; `report_demo_trades` as the repo's only
round-trip folder; the research self-lock. Five new architecture-register rows (AD-18…AD-22) record the
human-armed-only execution boundary, price capture strictly below the order path, the single round-trip
folder, and — as an architectural constraint on the UI layer, not merely a decision-log note — the binding
honest-labelling doctrine. `PROJECT_STATE.md` gains a per-version shipped summary, closes D-119's Finding B
and all four D-121 parked items (each against its verifying test), opens the three D-123 non-blocking
notes, and leads with the operator actions still required.

**Governance finding (pre-existing, NOT introduced by v8.147–v8.154, and NOT self-authorized here).**
`AD.md` §AI claimed three bounded audited POST routes; `server.py` actually serves **six**:
`workspace-actions/decision`, `workspace-actions/data-update`, `cockpit-actions`, `demo-lane-actions`,
`signals/ingest`, `signals/poll`. **`POST /api/v1/signals/ingest` and `POST /api/v1/signals/poll` have no
`DECISION_LOG` entry authorizing them.** They are write surfaces on the local dashboard with no recorded
authorization. This is recorded as an OPEN governance item in `PROJECT_STATE.md`; no authorization is
invented for them here, and their scope/audit posture should be reviewed and either recorded or removed.

**Fee drag confirmed in production (the empirical answer to the "money printer" framing rejected in
D-121).** Read-only over the live ledger on 2026-07-27, ~24h after the confluence lane started:
**8 closed, 3W/5L, win rate 37.5%, realised NET −$0.0115, fees $0.6503, 10 open.** Gross P&L before fees was
therefore ≈ **+$0.6388** — the signal did pick net-positive price moves — but **fees consumed 101.8% of
gross**, turning a small gross gain into a net loss. The win rate decayed 100% (n=1, D-118) → 50% (n=2,
D-123) → 37.5% (n=8) as the sample grew, exactly as expected when n stops being 1. This is direct
production confirmation of D-121's arithmetic: on an UNVALIDATED signal, every round trip must clear a
~0.2% fee hurdle, and churn is fee-negative. Recorded as a dated point-in-time observation; demo P&L
remains NON-EVIDENCE of edge in either direction.

Also verified by observation: the running lane has **NOT** been restarted — 0 `price_history_*.json` files
against 37 activity heartbeats — so v8.154's price capture is not yet active. The operator restart is a
verified fact, not a caution. Remaining documentation staleness found but deliberately not edited in this
pass (recorded for a later sweep): `TODO.md` initiative 14 still claims the console has "no write
controls", false since D-038/D-041/D-044/D-106 and badly so since v8.149–v8.150;
`docs/architecture/MODULE_CATALOG.md` unread and may not reflect the seven new endpoints;
`MISSING_AND_OPEN_ITEMS.md`, `README-dev.md`, `PACKAGE_README.md`, `TRADING_OS_NORTH_STAR.md`,
`RESEARCH_BACKLOG.md`, `docs/supervisor/*` and `docs/program/DEMO_LANE_PLAN.md` not inspected.

Evidence: operator's 2026-07-27 question; `git log` showing both documents last touched at 77235d9;
`PACKAGE_CHANGELOG.md` v8.147–v8.154 and `DECISION_LOG.md` D-118–D-123 cross-checked against
`server.py`, `dashboard_api/demo_lane.py`, `dashboard.html`, `demo_activity_lane.py`, `demo_eth_lane.py`,
`report_demo_trades.py` and `run_universe_search.py`; a read-only `report_demo_trades` run over the live
ledger for the P&L figures; a directory listing for the price-history absence. Documentation-only change —
no source edited; ruff and mypy re-confirmed green. Normal reconciliation (v8.155) under D-030/T-000-02:
`PROJECT_STATE.md` ×1, `docs/architecture/AD.md` ×1 and this decision log ×1 rehashed; NOT an integrity
exception.
Status: **SSOT resynced to v8.154; architecture and state documents now describe the running system. Two
undocumented POST write routes recorded as an OPEN governance item, not authorized. Fee drag confirmed at
101.8% of gross with realised P&L now NEGATIVE. Fake-money demo only; execution authority `NONE`; 0
validated strategies; demo P&L remains NON-EVIDENCE. Price capture inactive until the operator restarts the
lane. No venue, order, live, or real-money authority is granted, and no investment advice is given.**

### D-125 — BOUNDARY CHANGE: order-placing lanes may now start unattended via an opt-in supervisor; three rails, two of them fail-closed; lane resilience; venue identity and cash surfaced

Decision: **this entry reverses part of D-121/D-123.** Those recorded that order-placing lanes were
HUMAN-ARMED ONLY and that "no scheduler, cron, timer or background job in this system can start an
order-placing lane". On explicit operator instruction ("those things should be running automatically
without me needing to manually trigger it" → "yes do it"), an OPT-IN launchd supervisor may now start the
confluence activity lane unattended. The prior stance is superseded, not quietly contradicted: the false
statements were removed from the Automation page in the same change (see below), because a stale safety
promise is more dangerous than no promise — an operator would read it and believe nothing could trade
without them.

**Trigger.** The lane died silently after ~4.5h and sat dead ~12h. Root cause was NOT a crash: DNS/network
loss (laptop sleep) failed every coin (`nodename nor servname provided`), and the process ended with the
machine. Two real defects surfaced in the same log: `EOSUSDT: list index out of range` every cycle
(EOS/FTM/MATIC are delisted on Bybit demo and return empty klines), and ~37 identical error lines per
cycle during the outage. Positions were NOT unprotected during the dead period — all 10 held coins had
live venue-side resting stop orders with real Bybit order IDs, which is the architecture working as
designed: the stop lives at the exchange, so it survives our process dying.

**The supervisor** (`scripts/supervise_demo_lane.py`, new; `ops/com.tios.demo-lane.plist`, new; four
`make lane-supervise-*` targets). Deliberate design: the lane is reviewed order-path code and was NOT
touched (`scripts/demo_eth_lane.py` has a 0-line diff); every supervision concern lives in one small
auditable wrapper that launchd invokes and that `os.execv`s into the lane with a fixed argv of module
constants. Rails:
1. **KILL_SWITCH is absolute.** Refuses before anything else and exits 0; the plist's
   `KeepAlive={SuccessfulExit:false}` means a clean exit is launchd's signal to STAY DOWN. This holds
   transitively — the lane also returns 0 on the kill switch mid-loop and `execv` propagates it, so a
   dashboard STOP *ends* supervision rather than fighting it. A reboot/login re-runs the supervisor, which
   re-checks the on-disk switch and refuses again: re-checking, not resurrecting. The residual TOCTOU
   (switch created between the check and the launch) is closed by the lane's own layered checks —
   `run_activity_cycle` checks first thing and `place()` re-checks immediately before any order send.
2. **Crash-loop guard.** Bounded start history (atomic tmp+replace, capped at 20). >5 starts in 10 minutes
   refuses; `ThrottleInterval=60` is the second layer. A refusal never appends to history, so repeated
   operator stops cannot wedge the guard; a corrupt history fails OPEN to one start rather than blocking
   forever. **Worst case, verified by review: exactly 5 lane starts in any window, then permanent
   stand-down.** Blast radius if the operator leaves for a week: trading stays inside the existing $300
   cap / $25 per position / 12 slots / −15% stop invariants, or the agent quietly stands down. The
   realistic failure is "stops measuring", not "trades out of control".
3. **Every supervised start is audited** to `artifacts/human_decisions/demo_lane_actions.jsonl` in the
   dashboard's existing record shape, marked `source: launchd_supervisor`.
**Two fail-closed hardenings added after review.** The reviewer found that a failed audit write was
swallowed while the launch proceeded, making the operator-facing claim "an unattended start is never
invisible" best-effort rather than a guarantee — and that a `_write_history` failure crashed before launch
but was never counted, so a disk-full condition would relaunch every 60s unbounded. Both now REFUSE: a
start that cannot be counted or cannot be audited does not happen. Refusals stay best-effort because they
launch nothing.

**Lane resilience** (`scripts/demo_activity_lane.py` only; the order-path file untouched). The
`list index out of range` was traced to `_true_range` indexing `high[0]` on an empty series via the
roster's first strategy. Now gated on the DATA (`MIN_ROSTER_BARS = 41`, the roster's longest lookback plus
the evaluated bar), never on a symbol list, so a future delisting behaves identically; warned once per run
instead of once per cycle. A cycle in which EVERY evaluated coin fails on transport (`OSError` and
subclasses) is recognised as one connectivity outage, logged once, and backed off with capped doubling
(≤900s), never faster than cadence — with the wait sliced so the kill switch is honoured during backoff
rather than 900s later. CADENCE AND LOGGING ONLY: no order decision, sizing, threshold, stop, cap or
kill-switch check changed, and a test asserts an entry AND a disaster-stop exit both fire on the first
healthy cycle after an outage. A skipped thin-data coin is excluded from `evaluated`, so it can never be
miscounted as an outage.

**UI honesty corrections.** (a) The venue was not identifiable: `build_wallet`'s `venue` object carried no
identity at all, and the "Bybit" chip the operator remembered lived on the legacy card demoted into a
collapsed section in v8.153 — a regression introduced by that change. `venue` now carries `name`,
`environment_label`, `api_host` (mirrored from the VERIFIED `demo_preflight.DEMO_HOST`) and a fixed
`url`; a clickable chip renders near the top. Bybit's own help centre confirms Demo Trading is a MODE on
bybit.com reached from the profile menu (not a separate subdomain, and explicitly not testnet), so
`https://www.bybit.com` is the honest destination and no demo subdomain was invented. (b) Cash was
unanswerable: the quote balances existed but were rendered last, dimmed and untotalled — an
over-correction made to stop the pre-funded balance reading as profit, taken so far that "how much is in
my account?" could not be answered. **Hiding a number the operator is asking for is its own dishonesty.**
`cash_total_usdt` (quote-only, coins excluded) is now shown plainly with the pre-funded framing as a
LABEL. The $300 lane budget remains the performance headline; cash and budget are never summed and tests
forbid any cash+budget, cash+P&L or cash+coins composite anywhere in the payload or the rendered page.

**Nav and verdict line.** WATCH (Live, Wallet) / EVIDENCE (Research, Testing, Signals) / MACHINE (the
rest) replaces the WATCH-vs-Lab split, because "Lab" was a leftover bin holding three unrelated purposes;
all thirteen pages remain reachable and per-group collapse state migrates cleanly off the old key. A
persistent verdict line now sits ABOVE the activity on both Watch pages — busy on-screen activity reads as
productive earning, and the first thing read should be what is actually established. It is DERIVED, never
hardcoded: the validated count comes from `/api/v1/dashboard` `candidate_rows[].validation_state ==
"VALIDATED"` (the research-lab scorecard registry, where validation is actually decided — the demo-lane
`validation_state` field was explicitly rejected as a hardcoded literal), and net-after-fees from
`/api/v1/equity-curve`. Tests prove 1 and 2 validated render correctly, so it cannot be a disguised
constant; an unreadable source renders "validation state unavailable" and never a reassuring default.

Parked / recorded, NOT fixed: **arm-expiry — an unattended start currently never expires; this MUST exist
before the supervision pattern is used with real money** (stated in the supervisor's own docstring and on
the Automation page). `_TRANSPORT_ERRORS = (OSError,)` can misclassify a local disk error as a
connectivity outage (cadence/log only, no order impact). A coin delisted while holding an open position
loses its per-cycle software disaster-stop evaluation — unchanged from prior behaviour, with the
venue-side resting stop remaining the protection. Supervisor logs have no rotation.

Evidence: operator instruction 2026-07-27; `artifacts/trading_domain/demo_lane/lane.log` (DNS failures,
the recurring EOS IndexError); the live heartbeats showing all 10 held coins carrying venue resting stop
order IDs; Bybit's Demo Trading help centre (retrieved 2026-07-27) for the mode-not-subdomain fact; an
independent adversarial review returning GO with no blocking findings, which hash-verified 11 files,
traced every kill-switch path hunting for resurrection, quantified the crash-loop bound, and confirmed the
governance text is corrected rather than softened. 402 tests pass; ruff and mypy clean. Normal
reconciliation (v8.156) under D-030/T-000-02 — `dashboard.html` ×2, `tests/test_dashboard.py` ×2 and this
decision log ×1 rehashed; NOT an integrity exception.
Status: **Opt-in supervised auto-start SHIPPED and INACTIVE until the operator runs
`make lane-supervise-install`. D-121/D-123's human-armed-only stance is SUPERSEDED for the activity lane
and the false claims are removed from the product. KILL_SWITCH remains absolute; unattended starts are
bounded at 5 per window and fail closed when they cannot be counted or audited. Fake-money demo only;
execution authority `NONE`; 0 validated strategies; demo P&L remains NON-EVIDENCE — supervision increases
measurement UPTIME only and cannot improve results. Arm-expiry is a hard precondition for any real-money
use. No venue, order, live, or real-money authority is granted, and no investment advice is given.**

### D-126 — "Agreement" does not predict forward returns: NULL result, pre-registered; NO agreement-scaled position sizing, and the only detectable relationship runs the wrong way

Decision: the operator asked to make the confluence score drive protection/sizing ("so it can be moved up
or down a bit for certain cases"). Before changing any level, a pre-registered offline study asked the
prerequisite question nobody had ever asked: **does agreement predict anything?** Answer: **no.** The
requested change is therefore NOT made — no agreement-scaled position size, and no agreement-scaled stop.

Method (read-only, offline, no orders, nothing in the repo modified; scripts and outputs under the session
scratchpad `agreement_study/`). Pre-specification was frozen in `PRESPEC.md` BEFORE any result was
computed: five fixed agreement buckets, primary horizon H=24 bars with H=6/H=72 declared
non-decision-bearing in advance, 0.2% flat round-trip fee, non-overlapping stride-H sampling, moving-block
bootstrap (30-day blocks, coins travelling together, 2000 resamples), and a three-part decision rule
(top-bucket net > 0 with CI excluding 0, AND monotone non-decreasing, AND top−reference > 0.20%). The
deployed scoring path was IMPORTED, not reimplemented (`ROSTER`, `TIMEFRAME_WEIGHTS`, `roster_signals`,
`confluence_score`, `candles_from_bars`, `MIN_ROSTER_BARS`). Universe: the 14 coins holding both 1h and 4h
bars, 2021-01-01→2026-07-27, 664,198 scored bars, 27,665 non-overlapping observations, **effective sample
68 blocks — not 27,665 rows**, because agreement is highly persistent (mean run 16.3 bars, max 178) and 14
majors co-move.

Integrity: look-ahead causality ENFORCED, not assumed — 4,900 prefix-vs-full-series comparisons, zero
mismatches. Higher-timeframe alignment asserted bar-by-bar on explicit close timestamps (the classic leak).
Negative control PASSED on 200 permutations.

Result: **NULL on the primary analysis.** Top bucket (≥0.25) mean net **+0.084%, CI [−0.219%, +0.386%]**;
top−reference **+0.206%, CI [−0.066%, +0.485%]**, permutation p=0.070 — the permutation null itself reaches
+0.230%, so **the observed spread is inside what pure noise produces**. Bucket means are NOT monotone. The
one relationship that IS statistically detectable runs the **wrong way**: Spearman **−0.0285, CI
[−0.0522, −0.0060]** (excludes zero, negative), with median net return and win rate BOTH declining
monotonically as agreement rises (win rate 49.1% → 45.9% → 43.6% → 45.3% → 44.3%). What increases with
agreement is right-skew, not expectation. Therefore agreement-scaled sizing would put MORE capital into the
states with the LOWEST median outcome and LOWEST hit rate — measurably worse than sizing at random.

Two findings that bear on decisions already taken:
- **The D-118 gate loosening (0.25 → 0.15) bought almost nothing and changed nothing measurable.** The
  score is coarse and bimodal (denominator fixed at 35, so values are k/35); `[0.15,0.25)` is reachable by
  only 3 of 71 possible values, so loosening widened coverage from 29.22% to 31.88% of bars — **+2.66
  points** — and the two gates are statistically indistinguishable (b3−b4 = +0.039%, CI [−0.346%, +0.437%],
  sign flipping across horizons). The loosening remains recorded as activity tuning; it is now also
  recorded as having produced no measurable performance change in either direction.
- **The roster may add nothing over a single trend filter.** Roster signals are state, not transition, so
  agreement behaves largely as a trend-state flag; this study cannot separate "7-strategy × multi-timeframe
  vote" from "one trend indicator". That the ensemble earns its complexity is UNDEMONSTRATED.

A H=72h cut showed top-bucket net +1.119% with a CI excluding zero and clearing the fee. It is recorded and
DISMISSED as noise, deliberately: it is not the primary horizon (named non-decision-bearing in advance
precisely to prevent this promotion — this is the exact move that produced the retracted CFTC PASS),
monotonicity fails badly so the effect sits in one bucket, its Spearman CI includes zero, it contradicts
H=6 and H=24 where the rank correlation is significantly negative, and three horizons were examined with no
multiplicity correction. Promoting it would repeat a known failure of this project.

Limitations, stated rather than buried: the live lane scores `{5m,15m,1h}@{1,1,2}` but only 1h/4h/1d are
stored, so the study used `{1h,4h}@{2,3}` — a structural ANALOGUE, not the deployed configuration, and the
live config is untestable until 5m/15m bars accumulate (the v8.154 price capture begins that). Universe is
14 large-cap survivors of 40 (survivorship; dead coins absent; MATIC ends 2024-09-10); one macro path;
Binance data vs Bybit execution; costs modelled optimistically at a flat 20bps with no slippage or impact,
so net figures are UPPER bounds; and the study measures bucket forward returns, not the lane's actual P&L
path (no hysteresis hold, no −15% stop, no capital cap). Fifteen confounders are enumerated in the study
report.

Evidence: operator instruction 2026-07-27; the pre-registered study (`PRESPEC.md`, `extract.py`,
`analyze.py`, `results.md`, 664,198 scored bars) in the session scratchpad; the imported deployed scoring
path; the passing causality and negative-control checks. Documentation-only decision — no code changed by
this entry.
Status: **NULL RESULT ACCEPTED. Agreement is NOT demonstrated to predict forward returns; the only
detectable relationship is negative. NO agreement-scaled position sizing and NO agreement-scaled stops are
adopted — doing so would fit noise and would over-allocate to the worst-median states. "Agreement" remains
what the code already calls it: an activity and inspectability device, NOT measured edge. The −15% tail
stop and the 0.05 exit gate are unchanged. 0 validated strategies; demo P&L remains NON-EVIDENCE. No venue,
order, live, or real-money authority is granted, and no investment advice is given.**

### D-127 — Perp SHORT side shipped DEFAULT-OFF; a structural ledger corruption and a state-zeroing defect caught before enable; position cards; wallet scope stated

Decision: the operator asked for "full activity" first, improve later. The lane is long-only on SPOT while
its own roster reads 35 of 37 coins as SELL — every one un-actionable — so it sat idle holding one
position. The operator chose the short side on perpetuals at **1x, no leverage, tight caps**. It ships
**DEFAULT OFF** (`SHORTS_ENABLED = False`; `--shorts` is the only way on, verified un-overridable by env or
config) and the operator enables it as a separate deliberate act. An independent order-path review returned
**GO for shipping default-off** with one must-fix-before-enable finding, now fixed.

**Two ledger defects found, both of which would have silently corrupted reported money.**
(a) STRUCTURAL: a short entry is `side: "Sell"`, which `report_demo_trades.fold_fills` reads as the EXIT of
a long — it would have paired a perp short against a real SPOT long on the same `(symbol, strategy)` key and
booked a fabricated P&L, or emitted a bogus unmatched fill. (b) Perp fills do not move the wallet by
notional at all (margin is reserved, P&L and funding settle separately) and a perp position is not a wallet
coin balance, so the `USDT_delta`/`<BASE>_delta` reconciliation the fold depends on does not apply. Funding
compounds it: it settles every 8h attached to NO order and would land inside some trade's before/after
window. FIX BY CONSTRUCTION, not by argument: perp records go to their own append-only `perp_orders.jsonl`,
carry NO `reconcile` key, and are labelled `wallet_delta_attributable: false` with an explicit funding note.
`load_filled` reads `orders.jsonl` only, so the spot report is *provably* untouched. Funding is also a real
recurring cost the spot lane never had (~±0.01%/8h ≈ 11%/yr on notional, paid or received by sign).

**Blocking defect found in review and FIXED before enable.** Three call sites in `run_short_cycle` zeroed
the local short state UNCONDITIONALLY after a force-close, without checking `closed["ok"]`. A rejected or
unconfirmed reduce-only close would therefore leave the state file claiming flat while the venue still held
the short. Two consumers read that file and would both have been wrong in the dangerous direction:
`short_exposure` would under-count the shared $300 cap, and the long/short mutual-exclusion gate
(`short_open`) would stop withholding the spot BUY — so **a real long could open against a still-live
short on the same coin**, breaking the never-both-sides invariant. Fixed via `_settle_short_close`, which
zeroes only on a confirmed close; staying "short" until the venue says otherwise is the conservative
direction and is self-correcting, since the cycle re-reads the live position row before any signal. The
test venue could not previously make a close fail; a `cover_fails` mode plus two regression tests were
added, and the fix was verified by temporarily reverting it and confirming the test fails.

Rails verified against code by the review, not taken from docstrings: leverage 1x and isolated margin are
SET-then-READ-BACK and gate entries only (six refusal paths each proven to send no order); hedge mode is
detected via the one-way `positionIdx == 0` row; `reduceOnly` is hardcoded inside `force_close_short` so no
caller can flip it; the mirrored stop fires ABOVE entry, quantizes DOWN (tightening, mirroring the long
side's round-up) and derives from the SAME `DEMO_DISASTER_STOP_PCT`/`ENTRY_THRESHOLD`/`EXIT_THRESHOLD`
constants so the sides cannot drift; one $300 cap covers both sides at $25 a slot, with covers, stops and
unprotected-closes never budget-gated; the kill switch halts both sides. At 1x isolated, liquidation sits
near +99% against a stop at +15% — roughly 6.6x closer — and isolated margin bounds a crash-window loss to
one slot.

**Operator-facing scope stated rather than inferred.** `build_wallet` derives from the SPOT ledger and has
no knowledge of `perp_orders.jsonl`, so once shorts are enabled the wallet page and its deployed/free
figures would silently understate real exposure. The positions panel now says so explicitly. Making the
wallet perp-aware is deferred, recorded, and should precede any heavy use of the short side.

Also shipped: **one card per open position** replacing the wide table plus a detached chart strip — each
card carries all eleven former columns with its own price chart (entry and stop lines), with unrealised %
and distance-to-stop given the visual weight. A direction chip is wired but renders ONLY if the payload
carries a `side` field; it does not today, and no `LONG` was invented from `size_base > 0`.

**BEFORE THE OPERATOR ENABLES `--shorts`** (recorded, not yet done): run a single-symbol, single-cycle
non-loop smoke test against the real demo host. Two venue shapes cannot be validated offline — (i) on a
UNIFIED/UTA account, per-symbol isolation may be unsupported (isolated is account-level), in which case
every symbol is refused and **the short side is simply inert**, which is fail-closed and expected, not a
bug; and (ii) if the `tpslMode: "Full"` payload shape is wrong, a short opens, fails to confirm its stop and
force-closes immediately — safe, but it burns two taker fees per attempt until fixed. Watch for
open-then-instant-close on the first run and stop if seen.

Evidence: operator instruction 2026-07-27; the live heartbeats showing 35 of 37 coins at or below a −0.15
short gate against 1 clearing the long gate; the independent order-path review (GO default-off, one
must-fix, five verified claims, four open questions assessed as fail-closed); 468 tests pass with ruff and
mypy clean. Standing: fake money, execution authority NONE, 0 validated strategies, demo P&L NON-EVIDENCE.
Shorts increase the tradeable surface roughly 35x in a market like today's — that improves the INSTRUMENT,
not the signal, which measured no predictive content (D-126) and 21.4% live.
Status: **Perp short side SHIPPED and DEFAULT-OFF; inert until the operator passes `--shorts`. Spot report
provably uncorrupted; the never-both-sides and shared-cap invariants restored by the state fix. Wallet page
states its SPOT-only scope. A live single-symbol smoke test is a PRECONDITION of enabling. No venue, order,
live, or real-money authority is granted, and no investment advice is given.**
