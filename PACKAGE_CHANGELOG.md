# Package Changelog

## v4 — 2026-07-05
- Added Phase 3 Execution Readiness Report.
- Added Crypto Spot Venue & Data Matrix V1.
- Added Experiment Lineage Executable Prototype Spec V1.
- Added Strategy Ingestion & Reproduction Workflow V1.
- Added Frozen AI & Agent Benchmark Suite V1.
- Added venue technical-shortlist vs operator-eligibility hard gate.
- Added tiered market-data acquisition policy.
- Added MLflow + DVC prototype hypothesis and acceptance gates.
- Added manual strategy-ingestion seed-batch rule.
- Updated project state, decision log, research backlog, missing items, and source registry.

## v3 — 2026-07-05
- Replaced Cursor-specific terminology with generic `coding agent` terminology.
- Added Engine Bake-Off Blueprint V1.
- Added Phase 2 Targeted Discovery Report.
- Added Existing Strategy Registry V0.
- Added AI & Agent Evaluation Blueprint V1.
- Added Experiment Lineage Blueprint V1.
- Updated project state, decision log, research backlog, missing items, source registry.
- Explicitly kept live exchange unresolved pending Israel/operator-fit verification.

## v2
- Added Phase 1 ecosystem discovery, initial reuse matrix, source registry.

## v1
- Established North Star and continuity package.

## v5 — 2026-07-05

Transitioned package from preparation to constrained coding-agent readiness.

Added:
- `research/ecosystem_discovery/PHASE_4_HANDOFF_READINESS_REPORT.md`
- `specs/CANONICAL_BAKEOFF_DATASET_V1.md`
- `specs/FEE_AND_SLIPPAGE_ASSUMPTION_PACKAGE_V1.md`
- `specs/BACKTESTING_VALIDATION_BLUEPRINT_V1.md`
- `specs/CRYPTO_SPOT_MVP_VERTICAL_SLICE_V1.md`
- `specs/STRATEGY_SEED_BATCH_V1.md`
- `decisions/CODING_AGENT_READINESS_GATE_V1.md`
- `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md`

Updated:
- `PROJECT_STATE.md`
- `DECISION_LOG.md`
- `RESEARCH_BACKLOG.md`
- `MISSING_AND_OPEN_ITEMS.md`

Key outcome:
- PASS for constrained coding-agent prototype execution.
- Still no approval for full product build, final production architecture, or real-money trading.

## v6 — SSOT + Pre-Code Environment Intake

- Promoted `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md` to explicit single operational SSOT.
- Added strict precedence/conflict-resolution hierarchy.
- Added `specs/ENVIRONMENT_AND_CREDENTIALS_INTAKE_GATE_V1.md`.
- Added hard no-code-before-intake gate.
- Added per-item `Configure now / Add later / Do not use / Not sure` choices.
- Added secret-handling rules and `.env.example` workflow.
- Updated project state, readiness gate, and decision log.


## v7 — Handoff simulation hardening

- Simulated a fresh coding agent starting with zero conversation context.
- Added explicit package integrity and input/output contract to the SSOT.
- Added `PACKAGE_INTEGRITY_MANIFEST.md`.
- Added `handoffs/HANDOFF_SIMULATION_AUDIT_V1.md`.
- Corrected ambiguous fee/slippage spec path in `DECISION_LOG.md`.
- Added explicit pre-code mutation boundary.
- Clarified that missing future reports/decision outputs are expected generated artifacts, not broken package inputs.

## v8 — 2026-07-06 — Planning system (principal-architecture mandate)

Added (planning/architecture/task/audit layer; no product code):
- `docs/architecture/AD.md`, `docs/architecture/MODULE_CATALOG.md`, `docs/architecture/TYPE_AND_CONTRACT_CATALOG.md`
- `docs/program/PROGRAM_PLAN.md`, `docs/product/MVP_SCOPE.md`, `docs/testing/TEST_MASTER_PLAN.md`
- `docs/traceability/TRACEABILITY_MATRIX.md`, `docs/ai/AGENT_ROLES.md`
- `skills/README.md` + 13 skill specifications
- `TODO.md` + `todos/00…20` (21 initiative files, REQ-traced)
- `research/EXISTING_CAPABILITY_REGISTRY.md` (full freshness re-verification dated 2026-07-06)
- `research/RESEARCH_GAP_MATRIX.md` (9 gaps closed, 16 open with owners/triggers)
- `audits/ARCHITECTURE_COMPLETENESS_AUDIT.md`, `audits/TODO_COMPLETENESS_AUDIT.md`, `audits/RED_TEAM_PLAN_REVIEW.md`, `audits/PLANNING_HANDOFF_SIMULATION.md`

Updated:
- `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md` — precedence slots for planning authorities + TODO layer; extended mandatory read order; stage/first-initiative pointer (T-003-01). Still the single controller.
- `DECISION_LOG.md` — duplicate IDs renumbered (D-027/D-028); new D-029…D-032.
- `specs/CANONICAL_BAKEOFF_DATASET_V1.md` — Amendment A1 (Binance µs timestamps from 2025-01-01 files).
- `PROJECT_STATE.md`, `MISSING_AND_OPEN_ITEMS.md`, `RESEARCH_BACKLOG.md`, `PACKAGE_README.md`.
- `PACKAGE_INTEGRITY_MANIFEST.md` — hashes regenerated; planning artifacts added as required inputs.

Key outcomes:
- Planning phase complete; S1 prototype execution remains the authorized next phase; first task T-003-01 (intake gate).
- Evidence-refresh corrections: vectorbt OSS active again; Backtrader/backtesting.py rejected; Databento reclassified; OKX↑/Coinbase↓ in connectivity ranking (live gates unchanged); MLflow/DVC hypothesis strengthened (DVC now under lakeFS stewardship); AI benchmarking must multi-sample (no provider determinism).
- Still NO approval for full product build, final architecture lock (PROVISIONAL items enumerated), or real-money trading.

## v8.1 — 2026-07-06 — S1 execution: initiative 03 complete

- HG-1 intake gate PASSED (interactive; AI provider keys deferred; MLflow/DVC fully local; zero secrets anywhere). Report: `artifacts/reports/PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md`.
- Initiative 03 DONE (T-003-01..05): git repo initialized; AD §F tree + module skeletons; idempotent bootstrap; one-command local gate (`make check`) with architecture dependency-law test, decision-ID uniqueness, secret scan — proven failable; per-engine isolated envs built and smoke-tested (freqtrade 2026.6, nautilus_trader 1.230.0, vectorbt 1.1.0, lean CLI 1.0.227, hummingbot 2.15.0 by digest); security review #1 PASS with all 6 findings fixed.
- T-001-01/RG-03 closed: vectorbt 1.1.0 license = Apache 2.0 + Commons Clause (verified from dist-info; `engines/vectorbt/LICENSE_CAPTURED.txt`). RG-04 closed via per-engine isolation. Gap matrix rows CG-10/CG-11.
- Controlled edits (manifest regenerated, 5 hashes): PROJECT_STATE.md, registry, gap matrix, todos/01, todos/03.

## v8.2 — 2026-07-06 — S1 execution: initiatives 04, 05 complete; 06 started; 18 partial

- Initiative 04 DONE (EG-1): DS-CRYPTO-SPOT-BAKEOFF-V1 frozen — 396 raw files checksum-verified, 1.64M normalized rows, Amendment A1 boundary goldens, quality PASS (all checks proven failable), double-regeneration identical hashes, independent audit PASS_WITH_NOTES (zero discrepancies).
- Initiative 05 DONE: canonical spec model/validator (property-tested), immutable SV, baselines B1–B4 + double-derived micro goldens.
- Initiative 06: T-006-01 DONE (EngineAdapter port, NormalizedResult, capability gaps, mandatory fee/slippage grid, fee audit utility).
- Initiative 18: T-018-01/03 DONE (secret hygiene, license audit w/ planted-AGPL proof).
- Controlled edits: PROJECT_STATE, todos/04/05/06/18 — manifest regenerated.

## v8.3 — 2026-07-06 — S1: Freqtrade matrix + vectorbt probe evidence

- Freqtrade lane: B1–B4 × {F0/S0, F1/S1} all OK on frozen dataset; normalization to canonical decimal parquet; fee/PnL audit PASS everywhere; determinism byte-identical; lookahead flag root-caused (execution-state artifact, numeric proof); slippage CapabilityGap recorded; stake-model semantic note for parity.
- vectorbt probe: 1.31M bar-combos/s, all trials retained.
- Controlled edits: PROJECT_STATE, todos/06 — manifest regenerated.

## v8.4 — 2026-07-07 — Governance re-check (gov-02): decision-ID gate coverage fix

- `make check` re-verified green (63 tests, ruff, mypy-strict).
- Found and fixed a real gap: D-027/D-028 used `##` headings, so `tests/test_decision_ids.py`'s uniqueness regex (`### D-NNN`) silently skipped them. Normalized both to `###` (D-033); all 32 decision IDs now covered.
- Confirmed no invented decision-category labels in `DECISION_LOG.md`; confirmed PROJECT_STATE.md matches latest closed work; confirmed no stop-condition triggers worked around.
- Controlled edits: DECISION_LOG.md (D-033 + heading fix), PROJECT_STATE.md.
## v8.5 — 2026-07-10 — S1 executable evidence and HG-2 review packet

- Executed and selected the local MLflow+DVC lineage composition; retained restore,
  compare, strategy trace, mock-only AI trace, and thin domain-link evidence.
- Closed available engine parity with explained B1/B2 divergences; closed the
  Freqtrade lane with constraints and vectorbt with 66/66 retained ledgered trials.
- Kept the real Trading OS dashboard live and added explicit HG-2 readiness while
  preserving `INCOMPLETE_NOT_APPROVABLE` strategy validation and no-order boundaries.
- Added the S1 stage-exit review, D-035, and regenerated all changed controlled-input
  SHA-256 entries in `PACKAGE_INTEGRITY_MANIFEST.md`.
- Closed the S1 contextual approval, independent risk-precondition, and ingested-code
  containment tasks; Security Review #2 passes and the local gate now has 123 tests.

## v8.6 — 2026-07-10 — S2-0 governance reconciliation

- Recorded the operator's explicit HG-2 approval as D-036 and opened constrained S2
  architecture, autonomous research/test-lab, sourced-research, offline backtesting,
  retained-trial scoring, validation, and research-console work.
- Made `docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md` the active S2 execution plan
  under the existing SSOT hierarchy.
- Preserved B2 as `INCOMPLETE_NOT_APPROVABLE` and rejected for paper; no strategy,
  synthetic wallet, paper/demo/testnet venue connection, credentials, order routing,
  live trading, real money, or AI approval/trading authority was granted.
- Reconciled the prototype decision, S1 stage exit/readiness reports, project state,
  operational handoff, program/architecture task states, and execution plan. The
  integrity manifest was intentionally not edited in this reconciliation.

## v8.7 — 2026-07-10 — S2 architecture-lock governance reconciliation

- Added unique D-037 for the evidence-backed S2 architecture lock: modular monolith;
  SQLite operational state with measured PostgreSQL triggers; Parquet/DuckDB analytics;
  MLflow+DVC behind ports; and bounded scheduling only after real idempotent reuse.
- Closed T-002-01..04 against their revised, evidence-backed acceptance criteria and
  recorded engine roles. Hummingbot/LEAN deferred adapters and normalized artifacts are
  retained as evidence-only/deferred assets rather than deleting historical evidence.
- Activated only bounded S2 initiatives 13, 14, 17, and 19; full ontology initiative 12
  remains deferred. Folded former product wave 7 into the S2 console/product slice.
- Removed stale HG-2/S1-current and resolved-open-item wording while preserving B2/G4/G10
  strategy-validation gaps, engine gaps, and all paper/demo/live human gates.
- Kept the execution boundary read-only and inert. No real `LAB-*` batch, enabled
  scheduler, S2 completion, strategy approval, paper/demo connection, or live capability
  is claimed. The integrity manifest and all source/test files were intentionally left
  untouched by this reconciliation.

## v8.8 — 2026-07-10 — S2 Research Lab automation dashboard

- Finished the paused jobs/dashboard integration: read-only `build_jobs_projection(root)`,
  dashboard Automation view, and focused jobs/dashboard tests.
- Verified the real retained LAB-702 batch and persisted queue state: 2 succeeded
  `RESEARCH_LAB_V0` jobs, latest reused unchanged artifacts, recurring six-hour schedule
  next due `2026-07-11T00:00:00+00:00`, no failed/cancelled jobs.
- Ran full quality gates: Ruff, format check, strict mypy, 282 tests, and
  `make required` including `pip-audit` with no known vulnerabilities.
- Browser-tested the live dashboard at 375/768/1024/1440 px across Overview, Research
  Lab, Automation, and Market Monitor; market evidence loaded from frozen candles plus
  retained backtest fills. The page remains read-only with no POST, credential, venue,
  order, paper/demo/live, or real-money control.
- Tightened the Automation projection after independent review: retained job errors are
  redacted by default, including unlabeled secret-looking failure text.
- Refreshed the Research Lab score assessment from retained validation evidence,
  producing `LAB-799f7d81843d15aaf3b161036a4cd543ac37a709cb1e2ecc72a161f7348488fa`.
  The new batch remains `UNVALIDATED` / `NOT_ELIGIBLE`, but distinguishes negative
  completed evidence (economic, drawdown, walk-forward, robustness, baseline
  superiority) from still-blocked multiple-testing and cross-engine reproduction.
- Enqueued and executed `s2-production-offline-research-lab-v0-cycle-003`; the local
  worker reused LAB-799 and retained a third succeeded `RESEARCH_LAB_V0` job without
  enabling any paper/demo/live or order capability.

## v8.9 — 2026-07-11 — S2 decision follow-through and dashboard governance

- Added Workspace human-decision recording for gated/recurring tasks:
  `artifacts/human_decisions/workspace_decisions.jsonl` records operator choices for
  future coding agents, while all trading/job/order controls remain absent.
- Completed the authorized official-source venue recheck and S3 design-only expansion
  slices: `VENUE_ISRAEL_SOURCE_RECHECK_2026_07_11.md` and
  `FUTURE_MARKET_EXPANSION_DESIGN_REVIEW_2026_07_11.md`.
- Rechecked AI cost telemetry credentials after the operator decision; no provider
  keys are visible, so `T-017-05` remains credential-blocked with evidence in
  `AI_COST_TELEMETRY_CREDENTIAL_RECHECK_2026_07_11.md`.
- Tightened dashboard freshness and API boundaries: core data auto-refreshes,
  Market Monitor refreshes while visible, `/api/v1/*` is the only active API, and
  legacy `/api/*` paths return `410`.
- Regenerated all changed controlled-input SHA-256 entries in
  `PACKAGE_INTEGRITY_MANIFEST.md`; manifest verification passes.

## v8.10 — 2026-07-11 — Full AD/docs/TODO/env audit pass

- Added four audit reports: `AD_IMPLEMENTATION_GAP_AUDIT_2026_07_11.md`,
  `OPEN_TASKS_AND_DOCS_AUDIT_2026_07_11.md`, `ENV_AND_CREDENTIALS_AUDIT_2026_07_11.md`,
  `WORKSPACE_TODO_API_SYNC_2026_07_11.md`.
- Added `TIOS_AI_MODE`/`TIOS_AI_PROVIDER` (names/comments only) to `.env.example`;
  verified `.env` git-ignore and zero secrets.
- Recorded the dashboard workspace-decision POST route vs AD §AI/type-catalog GET-only
  contract mismatch as a Current Implementation Gap note in AD §AI and new task
  **T-002-05 (DECISION REQUIRED)** in `todos/02_architecture_foundation.md`. Desired
  architecture was not changed; no defect was normalized into AD.
- Updated `PROJECT_STATE.md` and `MISSING_AND_OPEN_ITEMS.md`; regenerated
  `PACKAGE_INTEGRITY_MANIFEST.md` hashes for the controlled files edited in this pass.

## v8.11 — 2026-07-11 — D-038 API clarification and authorized S2 cycle

- Recorded D-038: the operator-approved clarification keeping
  `POST /api/v1/workspace-actions/decision` as the single audited, operator-driven,
  loopback, allowlist-validated, append-only write exception; AD §AI and
  `TYPE_AND_CONTRACT_CATALOG.md` §7 updated; T-002-05 marked DONE; gap note removed.
- Ran the authorized offline S2 Research Lab v0 cycle: idempotent reuse of LAB-f99d
  (66 trials, no winner, execution_authority=NONE); executed the due six-hour
  scheduled job via the local worker (succeeded, result_reused=true).
- Updated `PROJECT_STATE.md`, `MISSING_AND_OPEN_ITEMS.md`, `DECISION_LOG.md`,
  `todos/02_architecture_foundation.md`; regenerated integrity manifest hashes.

## v8.12 — 2026-07-11 — Operator access prep checklist

- Added `OPERATOR_ACCESS_PREP_CHECKLIST_2026_07_11.md` so future agents have one
  source for exchange and market-data account preparation without re-asking the
  same setup questions before every platform task.
- Reserved commented, inactive `.env.example` names for later Binance Spot Testnet,
  OKX Demo, Kraken, Coinbase CDP, CoinAPI, Kaiko, Tardis.dev, and Databento gates.
- Preserved all S2 boundaries: no credentials requested, no connections enabled, no
  paper/demo/testnet activation, no order routing, no live trading, and no real-money
  capability.
- Updated `PROJECT_STATE.md` and `MISSING_AND_OPEN_ITEMS.md`; regenerated integrity
  manifest hashes for controlled files.

## v8.12 — 2026-07-11 — Production G10 candidate integration (T-009-04 / RG-07)

- Added candidate-specific G10: `engines/vectorbt/g10_returns.py` (per-trial slice
  returns, subprocess-isolated) and `scripts/run_g10_candidate.py` (PBO/CSCV + DSR via
  the validated methods, exact parity check against the retained LAB Parquet, and an
  independent second implementation with ≤1e-9/≤1e-6 agreement).
- Retained `artifacts/validation/G10_CANDIDATE_EVIDENCE_2026_07_11.json`: all families
  FAIL (B2 PBO 0.8685, DSR≈0). B2 package gate G10 is now FAIL (was NOT_RUN);
  `multiple_testing_selection_bias_control` is FAIL (was BLOCKED) in refreshed batch
  `LAB-73ebd3a3bb3e4086b2408552559e77a26d1334ae9cc789c4459beadc27b6844a`.
- Updated validation package builder, lab score mapping, retained method-candidate and
  validation-status artifacts, tests (`tests/test_g10_candidate.py` added), RG-07 row,
  T-009-04 status, PROJECT_STATE, and MISSING_AND_OPEN_ITEMS. No strategy approved;
  no execution path enabled.

## v8.13 — 2026-07-11 — Cross-engine reproduction dimension closed

- Added three-way B2 reproduction: engine-independent core derivation,
  `engines/vectorbt/repro_b2.py` (exact signal match, one explained float tie), and a
  dedicated single-pair BTCUSDT full-history Freqtrade backtest
  (`artifacts/validation/repro/`, 66,385 trades, all exit_signal, 99.904% exact
  fill↔signal reconciliation; residuals quantified as decimal128→float64 indicator
  arithmetic). Verdict PASS_WITH_SCOPE_NOTE — fill/P&L parity NOT claimed.
- `scripts/run_cross_engine_reproduction.py` + `tests/test_cross_engine_reproduction.py`;
  lab dimension now binds to the evidence artifact (added to lab input hashes).
- Batch `LAB-c9578b6b45cdbf1f3c2f6ba1320f993f6f149fb83d17905e9070bc07079c7aea`
  retains zero BLOCKED score dimensions; candidate remains rejected; no winner,
  no execution authority. Updated state/docs/tests; manifest regenerated.

## v8.14 — 2026-07-11 — Chunking design, session handoff

- Added `specs/HUMMINGBOT_FULL_HISTORY_CHUNKING_DESIGN_V1.md` (30-day warm-up-prefixed
  windows, seam-audited stitching, per-window timeouts, operator rerun framing);
  T-006-05 throughput track now references it.
- Added `handoffs/CONTINUE_S2_2026-07-11_VALIDATION_DIMENSIONS_COMPLETE.md` — full
  continuation handoff: completed work, verification state, batch-pin mechanics,
  prioritized remaining work, and exact next action (operator research-direction
  decision). PROJECT_STATE "Exact next action" updated to match.

## v8.15 — 2026-07-11 — Seeds 03/07 reproduced; seed cycle widened to 4 candidates

- Added `fixtures/micro/bars_long.csv` (32 bars, designed dip/rally around a 20-bar
  Bollinger warm-up) and two reproduction spot-checks in
  `tests/test_strategy_seed_reproduction.py` (BB population-std + Wilder RSI,
  double-derived expected bars). Seeds 03 (STRAT-FT1-sample-strategy) and 07
  (STRAT-PINE1-bb-strategy) are REPRODUCED; registry and status docs updated.
- Extended `scripts/run_seed_research_cycle_v0.py` with PINE1 (BB window/std sweep)
  and FT1 (RSI window/threshold sweep) candidates:
  `SEEDCYCLE-9a2bc401…` retains 34 trials across 4 candidates, all ≈ −100% on the
  proxy, no winner, no execution authority. Dashboard seed-cycle pin updated.

## v8.16 — 2026-07-11 — Seed 04 reproduced (true EMA); seed cycle at 5 candidates

- Added true recursive EMA (SMA seed, talib convention) to the reproduction tests
  and the seed cycle; seed 04 (STRAT-FT2-ema-cross) is REPRODUCED — the flagged
  EMA-approximation deferral is closed. Registry and status doc updated.
- `SEEDCYCLE-25fc2ebb…` retains 43 trials across 5 reproduced candidates, all
  ≈ −100% on the proxy, no winner, no execution authority. Only agent-closable
  seeds remaining: none (05/08 await a human tri-state decision; 06/09/10 are
  not applicable).

## v8.17 — 2026-07-11 — External bot/signal source architecture

- Updated AD §U to explicitly include exchange-hosted bot marketplaces, copy-trading
  records, online signal feeds, public leaderboards, and third-party bot platforms as
  core future Research Lab source classes.
- Updated `AGENT_ROLES.md` and `STRATEGY_SEED_BATCH_V1.md` so future strategy
  extraction handles bot/copy/signal sources as hypothesis/replay inputs with
  platform terms, timestamp semantics, parameter visibility, and bias risks.
- Preserved the execution boundary: external bots/signals may inspire or replay
  candidates, but cannot directly copy trades, control the wallet, or bypass
  validation, paper/demo, risk/security, and human gates.

## v8.18 — 2026-07-11 — D-040 multi-grid seed A/B retained

- Recorded the AI-delegated D-040 offline research decision: extend the five
  reproduced seed candidates across BTCUSDT/ETHUSDT x 5m/15m/1h.
- Retained `SEEDCYCLE-9b1652…` with 258 trials, no winner, and
  `execution_authority=NONE`; `uv run python scripts/run_seed_research_cycle_v0.py`
  reuses the completed cycle.
- Added `SEED_CYCLE_MULTI_GRID_REPORT_2026_07_11.md`; lower-frequency contexts
  produced positive proxy rows led by QC2 Donchian ETHUSDT 1h window=40, but no
  candidate is validated or eligible.
- Updated project state, open items, strategy registry, and continuation handoff;
  next offline work is validation evidence for the top positive proxy contexts.

## v8.19 — 2026-07-11 — Seed positive-context validation probe

- Added `scripts/run_seed_candidate_validation_probe.py` and retained
  `artifacts/validation/seed_candidates/SEED_VALIDATION_PROBE_2026_07_11.json`.
- The probe covers the top three D-040 positive proxy contexts with chronological
  thirds, fee stress, buy-and-hold comparison, and parameter-neighborhood evidence.
- QC2 Donchian ETHUSDT 1h window=40 survives the first probe but is parameter-fragile
  and still lacks production G10, cross-engine reproduction, paper/demo divergence,
  and red-team evidence; all contexts remain `UNVALIDATED` / `NOT_ELIGIBLE`.
- Added focused tests for the retained probe artifact and updated state/open-items/
  handoff records. No execution capability was enabled.

## v8.20 — 2026-07-11 — Seed-context G10 failure retained

- Added `scripts/run_seed_candidate_g10.py` and retained
  `artifacts/validation/seed_candidates/SEED_G10_QC2_ETHUSDT_1H_2026_07_11.json`.
- The strongest D-040 seed context, QC2 ETHUSDT 1h window=40, fails G10: PBO 0.2614
  but DSR 0.7564 below the 0.95 rule. Independent recomputation agrees.
- Updated the multi-grid report, project state, open items, and continuation handoff;
  no strategy is validated or eligible.

## v8.21 — 2026-07-11 — External source-intake seed retained

- Widened `ResearchSourceRegistry` beyond primary papers to accept read-only,
  DOI-optional platform sources for exchange bot marketplaces, copy-trading
  leaderboards, online signal feeds, and third-party bot platforms.
- Added four hypothesis-only source records: Binance Trading Bots, Binance Copy
  Trading, TradingView Ideas, and 3Commas DCA Bot. All remain non-reproduced,
  non-eligible, and carry no credential, copy, venue, order, paper/demo/live, or
  real-money authority.
- Added `EXTERNAL_SOURCE_INTAKE_PLANS_V1.yaml` plus a typed validator and dashboard
  read-model counts for 4 offline capture/replay plans. Each plan must carry the full
  S2 prohibition set before it can be retained.
- Added `scripts/build_external_source_intake_snapshots.py` and retained the first
  metadata-only source-intake artifacts under `artifacts/source_intake/`.
- Added `EXTERNAL_SOURCE_PUBLIC_CAPTURE_V1.yaml` and filled first lawful public-source
  metadata fields for the four source snapshots without fetching content at runtime or
  enabling any credential/copy/order path.
- Added `EXTERNAL_REPLAY_HYPOTHESES_V1.yaml` plus typed validation for four source-linked
  replay hypotheses; all are non-eligible and `execution_authority=NONE`, with Binance
  copy trading deliberately marked non-reconstructable until historical actions exist.
- Dashboard source projection now includes replay-hypothesis counts.
- Added the first canonical non-executing external replay candidate under
  `strategies/external/3commas-dca-config/`; it validates with ambiguities but remains
  `SPECIFIED_NOT_REPRODUCED`, `UNVALIDATED`, and `execution_authority=NONE`.
- Dashboard strategy projection now includes the external replay candidate without
  marking it valid or eligible.
- Retained `artifacts/reports/EXTERNAL_SOURCE_INTAKE_SEED_2026_07_11.md` and reran
  the offline lab as
  `LAB-f04ef5d705e0de4d3fff5fe83ada90b2d91223dc89cfa35364c5fd8439ca3121`; no
  winner was selected and `execution_authority=NONE` remains binding.

## v8.22 — 2026-07-11 — External DCA local replay retained

- Added `scripts/run_external_dca_replay.py`, a local-only replay runner for the
  3Commas-style DCA hypothesis. It reads frozen candle Parquet files and writes
  evidence artifacts only; it has no account, credential, paper/demo/live, venue, or
  order-routing path.
- Retained
  `artifacts/external_replay/3commas_dca/EXTDCA-9ed0a866cc1ddb5f7f4e7a94b5c5e48b/`
  with 6 BTCUSDT/ETHUSDT x 5m/15m/1h trials and 43,738 local simulated events.
- Updated the external DCA replay candidate status to `LOCAL_REPLAY_RETAINED` while
  keeping `UNVALIDATED`, `promotion_eligible=false`, and `execution_authority=NONE`.
- Added focused replay tests and retained-artifact boundary tests; no strategy is
  validated or eligible.

## v8.23 — 2026-07-11 — Inert trading-domain dashboard surface

- Added a structured `/api/v1/dashboard` `trading_domain` projection for the S2
  product rails: order intents/states, accounts, positions, portfolio, risk decisions,
  demo wallet, and paper/live capability status.
- Added a dedicated dashboard view, "Trading Domain", that shows the future
  demo-wallet/paper rails as read-only and explicitly absent/disabled in S2.
- Pinned the contract in tests: `execution_authority=NONE`, no venue connection,
  no order endpoint, no credential access, no synthetic wallet mutation, and no
  demo/paper/live orders.
- Browser smoke passed at 375, 768, 1024, and 1440 px with no console/page errors
  or horizontal overflow.

## v8.24 — 2026-07-11 — Local registry and artifact search surface

- Added `GET /api/v1/search`, a read-only dashboard API projection over bounded
  concepts, ResearchAsset records, ResearchSource records, seed/external strategies,
  and retained Markdown reports.
- Added the dashboard Search view with local result counts, evidence paths, snippets,
  and explicit no-write/no-execution boundary text.
- Pinned focused tests for the search builder, HTTP schema/error contract, UI strings,
  and disabled writes, credentials, venue connection, order endpoint, and execution
  authority.
- Updated state/open-items/type-catalog/TODO records to mark the roadmap's bounded
  registry/report search slice complete without adding any trading capability.

## v8.25 — 2026-07-11 — Read-only comparison evidence surface

- Added `/api/v1/dashboard` `comparisons`, a local projection over retained lab
  scorecards, validation gates, production G10 evidence, seed validation probes,
  seed-context G10, cross-engine scope notes, and local evidence refs.
- Added the dashboard "Comparisons" view with candidate dimension matrix, validation
  gate table, G10 table, seed-context table, cross-engine scope notes, and artifact
  refs.
- Pinned focused tests that no winner is selected, no promotion candidate exists,
  `execution_authority=NONE`, and approval/job/credential/venue/paper/live/order
  controls remain disabled or absent.
- Updated state/open-items/TODO records to mark the bounded S2 comparison UI slice
  complete without running new strategy operations.

## v8.26 — 2026-07-11 — Demo-wallet readiness projection

- Added a design-only `trading_domain.demo_wallet_design` projection to
  `/api/v1/dashboard` with ledger, synthetic capital, mutation API, order route,
  venue connection, and execution authority all absent/disabled/NONE.
- Extended the Trading Domain dashboard view with "Demo wallet readiness" and
  "Demo wallet invariants" sections that show required future gates, allowed
  isolated-simulation scope, and must-never-include guardrails.
- Pinned focused tests that the future demo-wallet rail remains S2 design-only and
  cannot create wallet state, venue/order routing, credentials, or real-money paths.

## v8.27 — 2026-07-11 — Agent-executable completion audit

- Added `artifacts/reports/AGENT_EXECUTABLE_COMPLETION_AUDIT_2026_07_11.md` to record
  the current post-v8.26 inventory: 0 actionable open tasks, 7 gated tasks, and 4
  recurring tasks from the live workspace status API.
- Updated `PROJECT_STATE.md` and `MISSING_AND_OPEN_ITEMS.md` so the exact next action
  points to credential/S3/HG/human gates instead of implying more open S2 platform
  product work.
- Reaffirmed that no strategy is validated or promotion-eligible, `execution_authority`
  remains `NONE`, and no demo/paper/live/venue/order/credential path is enabled.

## v8.28 — 2026-07-11 — S3/S4 gate-readiness surface

- Added a read-only `trading_domain.stage_gate_readiness` projection distinguishing
  S3 paper/demo readiness from S4 live readiness.
- Added Trading Domain UI cards for "S3 paper/demo readiness" and "S4 live readiness"
  showing satisfied design evidence, blocked predicates, and next human actions.
- Pinned focused tests that both stages remain `NOT_READY`, `BLOCKED_BY_GATES`, and
  `execution_authority=NONE`; no activation, credential, venue, paper/demo/live, or
  order route was added.

## v8.29 — 2026-07-11 — Standalone stage-gates API

- Added `GET /api/v1/stage-gates`, a standalone read-only machine contract for S3/S4
  readiness. It mirrors the Trading Domain gate chain without exposing any transition
  or activation command.
- Updated the type-catalog API contract to include stage-gate readiness and explicitly
  prohibit stage-gate transitions plus demo/paper/live controls.
- Added focused tests for the builder and HTTP schema: writes disabled, credentials
  absent, order endpoint absent, S3/S4 both `NOT_READY`.
