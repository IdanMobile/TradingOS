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
