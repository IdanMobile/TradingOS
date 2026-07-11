# Trading Intelligence OS — Project State

Last updated: 2026-07-11 (HG-2 approved; constrained S2 active)
Package version: v8 (planning system) + S1 evidence + S2 governance entry
Status: **S2 AUTONOMOUS RESEARCH LAB ACTIVE (CONSTRAINED).** No strategy, venue connection, or real-money trading is approved.

## Current phase

S0 finished 2026-07-06. S1 evidence execution is complete and **HG-2 was approved by
the operator on 2026-07-10 (D-036)**. Constrained S2 work now follows
`docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md`. Retained S1 evidence and constraints:

- **HG-1 intake gate: PASSED** — `artifacts/reports/PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md` (AI keys: add later ×3; MLflow/DVC: fully local).
- **Initiative 03 (repository foundation): DONE** — T-003-01..05 all complete. Git repo live; AD §F tree + module skeletons; idempotent `scripts/bootstrap.py`; one-command local gate (`make check`: ruff+mypy-strict+pytest incl. architecture dependency-law test, decision-ID uniqueness, secret scan — proven failable); 5 engine envs built+smoke-tested (freqtrade 2026.6, nautilus 1.230.0, vectorbt 1.1.0, lean CLI 1.0.227, hummingbot 2.15.0 digest-pinned); security review #1 PASS (0 secrets, 0 blocking, 6 findings fixed) at `artifacts/reports/SECURITY_REVIEW_01.md`; pre-commit secret-scan hook auto-installed; pip-audit clean.
- **T-001-01 / RG-03: CLOSED** — vectorbt 1.1.0 license verified from installed dist-info: Apache 2.0 + Commons Clause (internal use OK). Evidence `engines/vectorbt/LICENSE_CAPTURED.txt`. RG-04 closed via per-engine isolation (CG-10/CG-11 in gap matrix).
- **Initiative 04 (data foundation): DONE — EG-1 evidence complete.** DS-CRYPTO-SPOT-BAKEOFF-V1 frozen: 396 raw files (all official-checksum-verified), 1,637,118 normalized rows across 6 tables (BTCUSDT/ETHUSDT × 5m/15m/1h, 2021-01-01→2026-06-30), decimal128 precision, Amendment A1 µs/ms detection (48 ms + 18 µs files per table, boundary goldens on real rows), quality PASS, double-regeneration identical hashes, independent audit PASS_WITH_NOTES zero discrepancies. Artifacts: `artifacts/datasets/` (frozen manifest, quality report, audit).
- **Initiative 05 (strategy domain): DONE.** Canonical spec model + validator (property-tested), immutable StrategyVersion, baselines B1–B4 VALID with hand-derived + independently recomputed micro-fixture goldens (`fixtures/strategies/baselines/`, `fixtures/micro/`).
- **Initiative 18: T-018-01/03 DONE** (secret hygiene incl. artifacts; license audit — core venv copyleft-free, planted AGPL flagged); T-018-02 awaits T-010-01; T-018-04 recurring.
- **Initiative 06 (bake-off): T-006-01 DONE** (EngineAdapter port, NormalizedResult, CapabilityReport, mandatory F/S grid, fee recomputation audit). Freqtrade, Nautilus, and bounded LEAN have B1–B4 evidence; Hummingbot retains explicit full-history runtime gaps.
- **T-006-02 Freqtrade lane DONE WITH CONSTRAINTS**: full matrix B1–B4 × {F0/S0, F1/S1}, exact micro signal parity, determinism, recursive analysis, bounded hyperopt retention, dry-run, precision/failure probes, fee audits, and export pass. Native lookahead forced-state behavior and slippage remain explicit WARN/capability gaps.
- **T-006-06 vectorbt probe DONE**: B2/B3/B4 ran 66 trials over 577,803 bars; all 66 are retained in Parquet and the append-only ledger, no winner selected, and binding overfit controls keep vectorbt an accelerator only.
- **T-006-03 Nautilus lane:** bounded B1–B4 × {F0/S0, F1/S1} × {run1,run2} is now physically present; all 16 runs are byte-deterministic across normalized trade/equity/metric artifacts and all fee audits pass.
- **Cross-engine parity:** three full-period BTC contexts are comparable with zero unexplained available-lane residuals. B1 timing differences and B2 execution/order-state plus missing-data behavior are retained; B2 is not fill/P&L parity.
- **Initiative 07 (lineage): DONE.** Local MLflow 3.14.0 + DVC 3.66.1 Tests A/B/C pass reproduce, compare, trace, domain-link, local-first, and replaceability gates; AI trace is explicitly null-provider/mock-only. The fresh clone restored the exact 577,803-row BTC dataset and matched deterministic reproduction output. Decision D-035 selects the composition for S2 architecture input.
- **S1 approval/risk/security closure:** contextual approval transitions require evidence, paper states require a human decision, and all live states are unreachable; every validation package now carries independent no-live/cost-grid/drawdown-tail/promotion preconditions; external ingested code is subprocess-contained with no inherited secrets or network. Security Review #2 passes with zero blockers.
- **S2 entry:** architecture/research-console work, sourced strategy research, offline backtesting, retained-trial scoring, validation, and eventual demo preparation are active. LEAN's bounded Docker matrix is now retained; Hummingbot missing full-history runs remain runtime/throughput constrained.
- **Governance re-check (gov-02, 2026-07-07): PASS.** `make check` green (63 tests, ruff, mypy-strict). Fixed a real gate gap: D-027/D-028 used `##` headings, exempting them from the decision-ID uniqueness regex (`### D-NNN` only) — normalized to `###` (D-033); all 32 IDs now covered. No invented decision-category labels found in `DECISION_LOG.md` (the 7-label taxonomy from SSOT §7 applies to the `decisions/`/`research/`/`artifacts/reports/` decision artifacts, most of which are correctly not-yet-created since bake-off (initiative 06) is still in progress). No stop-condition triggers pending or worked around.
- **S1 execution closure (2026-07-10):** live Trading OS evidence dashboard is operational with an attributed TradingView Market Monitor plus an OS-owned canonical-candle chart and retained B2 markers; read-only APIs explicitly disable paper/live orders; staged TradingView direction is D-034; offline-first AI/provider gates are implemented; local MLflow+DVC lineage is selected in D-035; Freqtrade and vectorbt lanes are closed with constraints; bake-off contains 30 normalized runs plus 66 ledgered accelerator trials. B2 remains `INCOMPLETE_NOT_APPROVABLE`, G4 WARN, G10 deferred, and rejected for paper. Full local gate: 123 tests, ruff, format, mypy-strict.
- **D-036 boundaries:** no strategy approval; no synthetic wallet activation; no paper/demo/testnet venue connection; no credentials, order routing, live trading, or real-money authorization. AI cannot approve or trade.
- **S2 Research Lab v0 and automation evidence (2026-07-10):** latest real retained
  batch `LAB-799f7d81843d15aaf3b161036a4cd543ac37a709cb1e2ecc72a161f7348488fa`
  completed 3 experiments / 66 trials with 66 evidence rows, all marked
  `UNVALIDATED` / `NOT_ELIGIBLE`; no winner is selected. Score dimensions now bind to
  retained validation evidence: economic performance, drawdown severity, parameter
  neighborhood, walk-forward, and baseline superiority are negative/failing; regime is
  descriptive-only; multiple-testing and cross-engine reproduction remain blockers.
  The local SQLite jobs DB has three succeeded `RESEARCH_LAB_V0` records; the latest
  persisted job reused the unchanged LAB-799 artifacts, and a six-hour recurring
  offline schedule is visible with next due `2026-07-11T00:00:00+00:00`. The Automation
  dashboard is read-only/browser-verified at 375/768/1024/1440 px with no POST, queue
  mutation, credential, venue, paper/demo/live, or order control.
- **S2 verification package (2026-07-10):** restore/replay verification PASS
  (`artifacts/reports/S2_RESTORE_REPLAY_REPORT.md`), live-unreachability PASS
  (`artifacts/reports/S2_LIVE_UNREACHABILITY_REPORT.md`), and requirement audit BLOCKED
  before S2 exit (`artifacts/reports/S2_REQUIREMENT_AUDIT.md`) because no candidate is
  `COMPLETE_APPROVABLE` or promotion-eligible.
- **S2 seed-candidate cycle (2026-07-10):**
  `SEEDCYCLE-5bd3faa48ad47e23f0af45e12c0e613c843215fda324b3821b58b35d53da5c1a`
  retained 16 offline trials across the two seed strategies already marked
  `REPRODUCED` (`STRAT-QC1-dual-ma-cross`, `STRAT-QC2-donchian-breakout`). The cycle
  reused idempotently, selected no winner, and kept both candidates `UNVALIDATED` /
  `NOT_ELIGIBLE`; the simple next-open all-in proxy is strongly negative and does not
  change S2 exit status.
- **S2 ResearchAsset registry/backfill (2026-07-10):** `research/RESEARCH_ASSETS_V1.json`
  now backfills 8 retained RA records from S0/S1/S2 evidence. `ResearchAssetRegistry`
  enforces source-or-quality evidence, freshness states, dependency/supersession graph
  validity, consumers, human-review flags, deterministic digest, and cost amortization;
  focused tests prove the retained refs exist and invalid assets fail closed.
- **S2 observability boundary (2026-07-10):** bounded observability uses JSON artifacts,
  SQLite job rows, environment mode fields, and dashboard read models. Prometheus/Grafana
  and OTel are rejected for the current single-operator local lab until documented reopen
  triggers occur; AI cost telemetry remains credential-gated.
- **S2 dictionary/ontology seed (2026-07-10):** `research/DICTIONARY_CONCEPTS_V1.json`
  now covers 16 bounded S1/S2 concepts with aliases, contexts, related links, source refs,
  FIBO URI provenance where applicable, and explicit full-ontology gap rows. `ConceptRegistry`
  validates the graph and exposes SQLite FTS5 search; tests prevent scraped-definition and
  strategy-parameter drift.
- **S2 dashboard dictionary/global search (2026-07-10):** the live read-only dashboard now
  projects the bounded concept registry and explicit ontology gaps. This closes the safe
  FTS/global-search slice while leaving approvals UI and write paths disabled.
- **S2 dashboard backlog boundary (2026-07-10):** the full console rewrite, entity-detail
  layout, and richer comparisons UI are rejected for bounded S2 until documented reopen
  triggers occur. Existing read-only dashboard views and artifact links remain sufficient;
  approvals UI remains human-gated and unauthorized.
- **AI provider source re-check (2026-07-10):** RG-08 is closed for planning. Official
  OpenAI and Google AI Developers pages now provide GPT-5.6 pricing and Gemini 3.x
  context/pricing/deprecation evidence. Real-provider benchmark execution remains blocked
  on credentials, spend authority, and human review.
- **LEAN/Hummingbot Docker recheck (2026-07-11):** Docker 29.0.1 was available.
  LEAN B1-B4 x `{F0/S0,F1/S1}` run1 completed locally with custom data and no
  cloud/account path; B1 F0/S0 run2 matched run1 fills. Hummingbot B2 BTCUSDT
  F1/S1 full-history follow-up consumed CPU but hit the 1800 second lane timeout
  before `raw.json`; the orphaned container was stopped. A cached full-history
  retry later hit the 3600 second timeout but wrote a clean timeout manifest and
  stopped its named container.
- **Hummingbot productionization step (2026-07-11):** the container lane now has
  explicit window/timeout controls and stops named containers on timeout. Bounded
  BTCUSDT 30-day B1-B4 x `{F0/S0,F1/S1}` x `{run1,run2}` completed, normalized,
  fee-audited, and byte-deterministic. Feature caching reduced a bounded B2 F1/S1
  probe to about 32 seconds, but full-history Hummingbot remains a throughput/
  chunking track, not a credential or approval blocker.
- **G10 method fixtures (2026-07-11):** local PBO/CSCV and DSR arithmetic now has
  synthetic known-answer fixtures in `tests/test_multiple_testing_methods.py` and
  retained evidence in `artifacts/validation/G10_METHOD_FIXTURES_2026_07_11.json`.
  Production G10 remains inactive: candidate-specific estimator integration and
  independent recomputation are still required before any G10 PASS claim.
- **S2 evidence-cycle refresh (2026-07-11):**
  `LAB-f99dcc214f377ecca4710bbb41d445c8331d2a1b06f93931ed1c88bdf3af5924`
  completed after the validation evidence changed. It retained 3 experiments / 66
  trials, selected no winner, kept `execution_authority=NONE`, and preserved the
  blockers: negative economics, material drawdown, failed walk-forward/robustness/
  baseline superiority, incomplete production multiple-testing integration, and
  incomplete cross-engine reproduction.
- **Open-marker audit (2026-07-11):** repo-wide TODO/FIXME/TBD/PROVISIONAL/
  BLOCKED/DEFERRED/WARN/NOT_RUN marker sweep is retained in
  `artifacts/reports/OPEN_MARKERS_AUDIT_2026_07_11.md`. Stale architecture/report
  wording for bounded LEAN/Hummingbot evidence was reconciled. Remaining markers are
  Hummingbot full-history throughput/chunking work, Nautilus/Hummingbot scope expansions,
  G4/G10 validation blockers, human/credential/S3 gates, recurring governance, or
  retained historical evidence.
- **Seed reproduction widened + extended seed cycle (2026-07-11):** seeds 03
  (STRAT-FT1-sample-strategy, BB(20,2)+Wilder-RSI(14)<30, mid-band exit), 07
  (STRAT-PINE1-bb-strategy, BB(20,2) band strategy), and 04
  (STRAT-FT2-ema-cross, true recursive EMA with SMA seed — closing the flagged
  EMA-approximation deferral) are now **REPRODUCED (mechanical, spot-checked)**
  against the new 32-bar `fixtures/micro/bars_long.csv` (20-bar warm-up completes;
  entry/exit bars double-derived; tests in
  `tests/test_strategy_seed_reproduction.py`). The offline seed cycle now covers
  **5 reproduced candidates**:
  `SEEDCYCLE-25fc2ebb9059701791a121b3cebd621e1874408f388a3b1ce371804ef16356e2`
  retained 43 trials (QC1 12, QC2 4, PINE1 9, FT1 9, FT2 9) — **every candidate's
  best total return is ≈ −100%** under the next-open all-in fee-aware proxy; no
  winner, all `UNVALIDATED`/`NOT_ELIGIBLE`, `execution_authority=NONE`. Remaining
  seeds: 05/08 need a tri-state supertrend reviewer decision (human gate);
  06/09/10 are not applicable (market-making / cross-sectional papers).
- **D-040 multi-timeframe/instrument seed A/B (2026-07-11):** under the delegated
  offline research authority in D-039, the five reproduced seed candidates were run
  across BTCUSDT/ETHUSDT x 5m/15m/1h:
  `SEEDCYCLE-9b1652a62996fda4b753c6695f43569ab860acd8decb48c9c5994566f4a6488f`
  retained 258 trials, 5 evidence rows, no winner, and `execution_authority=NONE`.
  Unlike the 5m-only cycle, the lower-frequency A/B produced positive proxy rows:
  QC2 Donchian ETHUSDT 1h window=40 (+149.1%), QC2 BTCUSDT 1h window=80 (+20.7%),
  and FT1 ETHUSDT 15m RSI(21)<20 (+19.4%). Evidence:
  `artifacts/reports/SEED_CYCLE_MULTI_GRID_REPORT_2026_07_11.md`. These are
  `UNVALIDATED` research signals only; no candidate is promotion-eligible.
- **Seed validation-probe follow-through (2026-07-11):**
  `artifacts/validation/seed_candidates/SEED_VALIDATION_PROBE_2026_07_11.json`
  retains temporal split, cost-stress, buy-and-hold, and parameter-neighborhood
  evidence for the three positive D-040 proxy contexts. QC2 Donchian ETHUSDT 1h
  window=40 is the only context positive in all thirds and above buy-and-hold at
  normal fees, but its immediate parameter neighborhood is mostly negative and it
  lacks cross-engine, production G10, and paper/demo divergence evidence. All rows
  remain `UNVALIDATED` / `NOT_ELIGIBLE`, with `execution_authority=NONE`.
- **Seed-context G10 follow-through (2026-07-11):**
  `artifacts/validation/seed_candidates/SEED_G10_QC2_ETHUSDT_1H_2026_07_11.json`
  runs production-style PBO/DSR on the QC2 ETHUSDT 1h searched window grid. The
  surviving `window=40` context **FAILS G10**: PBO 0.2614 is below the overfit
  threshold, but DSR 0.7564 is below the 0.95 rule. No seed context is validated or
  promotion-eligible.
- **Cross-engine reproduction dimension closed (2026-07-11):** the canonical B2
  candidate now has three-way reproduction evidence
  (`artifacts/validation/CROSS_ENGINE_REPRODUCTION_2026_07_11.json`): an
  engine-independent core derivation, the vectorbt accelerator (exact signal-bar
  match, one float-tie displacement explained), and a dedicated single-pair BTCUSDT
  full-history Freqtrade backtest (66,385 trades, all exits `exit_signal`,
  **99.904% exact fill↔signal reconciliation**; ~0.3% residuals are quantified
  indicator-arithmetic differences from the decimal128→float64 converter loss, not
  strategy semantics; the retained two-pair S1 run remains explained by order-slot
  contention). Verdict: **PASS_WITH_SCOPE_NOTE** — fill/P&L parity is NOT claimed.
  Batch `LAB-c9578b6b45cdbf1f3c2f6ba1320f993f6f149fb83d17905e9070bc07079c7aea` now
  shows **zero BLOCKED score dimensions**: every dimension has a definite
  evidence-backed state and the candidate remains rejected on economics, drawdown,
  walk-forward, robustness, baseline, and G10 grounds. No winner; no authority.
- **T-009-04 completed / production G10 active (2026-07-11):** candidate-specific
  PBO/CSCV and DSR now run on the retained B2/B3/B4 trial populations
  (`scripts/run_g10_candidate.py` + engine-side `engines/vectorbt/g10_returns.py`),
  with exact per-trial parity verification against the retained LAB Parquet and an
  independent second implementation agreeing to ≤1e-9 (PBO) / ≤1e-6 (DSR) over
  12,870 CSCV splits. **All families FAIL** (B2: PBO 0.8685, DSR≈0, z −18.6; B3:
  selected trial has zero trades; B4: PBO 1.0). The B2 validation package gate G10
  is now an evidence-backed FAIL (was NOT_RUN), and the refreshed batch
  `LAB-73ebd3a3bb3e4086b2408552559e77a26d1334ae9cc789c4459beadc27b6844a` shows
  `multiple_testing_selection_bias_control = FAIL` (no longer BLOCKED) with 66
  trials retained, no winner, `execution_authority=NONE`. RG-07 is closed for
  production activation; a stats-specialist review gate remains before any future
  G10 PASS may count toward promotion. Evidence:
  `artifacts/validation/G10_CANDIDATE_EVIDENCE_2026_07_11.json`.
- **T-002-05 resolved / D-038 API contract clarification (2026-07-11):** the operator
  approved keeping `POST /api/v1/workspace-actions/decision` as the single audited,
  operator-driven, loopback, allowlist-validated, append-only write exception. AD §AI
  and `TYPE_AND_CONTRACT_CATALOG.md` §7 now record the scoped rule; the Current
  Implementation Gap note is removed. No trading/order/credential/paper/demo/live
  mutation authority exists on the route; any expansion requires a new decision gate.
  This is a clarification, not broad write-API approval.
- **S2 offline evidence cycle (2026-07-11, post-D-038):** the authorized Research Lab
  v0 cycle ran and idempotently reused
  `LAB-f99dcc214f377ecca4710bbb41d445c8331d2a1b06f93931ed1c88bdf3af5924` (identical
  content-addressed inputs; `reused: true`; 66 trials retained; no winner;
  `execution_authority=NONE`). The due six-hour scheduled job executed via the local
  worker and succeeded with reuse (jobs DB now shows the 2026-07-11 run,
  `result_reused: true`). Score-dimension blockers are unchanged: negative economics,
  drawdown severity, walk-forward/robustness/baseline-superiority failures,
  multiple-testing and cross-engine reproduction BLOCKED. S2 exit remains blocked.
- **AD/docs/TODO/env full audit (2026-07-11):** desired-AD vs implementation gap audit,
  open-tasks/docs audit, env/credentials audit, and workspace TODO API sync report are
  retained at `artifacts/reports/AD_IMPLEMENTATION_GAP_AUDIT_2026_07_11.md`,
  `OPEN_TASKS_AND_DOCS_AUDIT_2026_07_11.md`, `ENV_AND_CREDENTIALS_AUDIT_2026_07_11.md`,
  and `WORKSPACE_TODO_API_SYNC_2026_07_11.md`. Findings: no unhandled open marker beyond
  known gates; `.env` git-ignore verified; `TIOS_AI_MODE`/`TIOS_AI_PROVIDER` added to
  `.env.example` (names/comments only); one contract mismatch found — the dashboard's
  loopback workspace-decision POST route vs the AD §AI/type-catalog GET-only lock —
  recorded as Current Implementation Gap in AD §AI and tasked as **T-002-05
  (DECISION REQUIRED)**. The T-017-05 `credentials_configured` operator decision remains
  reconciled to DEFERRED-CREDENTIALS (no key visible). No readiness claim changed:
  S2 exit, promotion, paper/demo, and live remain blocked by their gates.
- **Operator-decision follow-through (2026-07-11):** dashboard-recorded decisions
  authorized a limited venue source recheck and S3 design-only expansion reviews.
  `VENUE_ISRAEL_SOURCE_RECHECK_2026_07_11.md` completes the public-source slice for
  Kraken/Coinbase Israel availability while preserving human account checks.
  `FUTURE_MARKET_EXPANSION_DESIGN_REVIEW_2026_07_11.md` completes perps/equities/
  core-spine design-only review without implementation. AI cost telemetry remains
  credential-blocked after `AI_COST_TELEMETRY_CREDENTIAL_RECHECK_2026_07_11.md`.
- **Operator access prep (2026-07-11):** future exchange and data-provider intake is
  consolidated in `artifacts/reports/OPERATOR_ACCESS_PREP_CHECKLIST_2026_07_11.md`.
  `.env.example` now reserves commented, inactive names for later Binance Spot
  Testnet, OKX Demo, Kraken, Coinbase CDP, CoinAPI, Kaiko, Tardis.dev, and Databento
  gates. No credential is requested, read, enabled, or authorized; all venue/data
  connections remain S3+/human-gated.
- **External strategy/source acquisition architecture (2026-07-11):** AD §U now
  explicitly treats exchange bot marketplaces, copy-trading/copy-investing records,
  online signal feeds, public leaderboards, and third-party bot platforms as core
  future Research Lab inputs. They are hypothesis/replay sources only until they pass
  source verification, canonicalization or replay capture, validation, paper/demo
  divergence tracking, risk/security review, and human gates; no copied signal or bot
  can directly trade.
- **External source-intake seed (2026-07-11):** the `ResearchSourceRegistry` now
  accepts non-paper source classes and retains four read-only hypothesis sources:
  Binance Trading Bots, Binance Copy Trading, TradingView Ideas, and 3Commas DCA Bot.
  They are machine-validated as `hypothesis_only`, non-reproduced, non-eligible, and
  DOI-optional platform records. `EXTERNAL_SOURCE_INTAKE_PLANS_V1.yaml` adds one
  offline capture/replay plan per source and the dashboard read model projects 4
  intake plans (3 ready, 1 design-only). Metadata-only snapshot artifacts are retained
  under `artifacts/source_intake/` with lawful public-source fields from
  `EXTERNAL_SOURCE_PUBLIC_CAPTURE_V1.yaml`, remaining pending-capture fields, and the
  full S2 prohibition set. `EXTERNAL_REPLAY_HYPOTHESES_V1.yaml` now translates those
  sources into four non-eligible offline replay hypotheses: Binance spot-grid config,
  Binance copy-trading opaque/non-reconstructable metadata, TradingView ruled-signal
  replay, and 3Commas DCA config. The 3Commas DCA hypothesis now has the first
  canonical non-executing external replay spec under
  `strategies/external/3commas-dca-config/`; it validates with ambiguities but remains
  `SPECIFIED_NOT_REPRODUCED`, `UNVALIDATED`, and `execution_authority=NONE`. No
  credential, subscription, account connection, copy action, order route,
  paper/demo/live venue, or real-money path is enabled. Evidence:
  `artifacts/reports/EXTERNAL_SOURCE_INTAKE_SEED_2026_07_11.md`.
- **External DCA local replay retained (2026-07-11):**
  `scripts/run_external_dca_replay.py` replays the 3Commas-style DCA hypothesis
  against frozen BTCUSDT/ETHUSDT x 5m/15m/1h candles. The retained run
  `EXTDCA-9ed0a866cc1ddb5f7f4e7a94b5c5e48b` covers 6 trials and 43,738 local
  entry/add/exit events. This is offline research evidence only:
  `validation_state=UNVALIDATED`, `promotion_eligible=false`,
  `execution_authority=NONE`, no platform bot, account, credential, paper/demo/live
  venue, or order route.
- **Trading-domain product surface (2026-07-11):** the dashboard now projects the
  inert S2 trading-domain read model (`orders`, `positions`, `portfolio`, `risk`,
  and future demo-wallet rail) from `/api/v1/dashboard`. It shows retained historical
  fill counts where evidence exists, but every mutable capability remains absent or
  disabled: no credential access, no order endpoint, no synthetic wallet mutation,
  no account mutation, no demo/paper/live order, no venue route, and no real money.
  Browser smoke at 375/768/1024/1440 passed with the new view.
- **Registry/report search product surface (2026-07-11):** `GET /api/v1/search`
  and the dashboard Search view now provide local read-only discovery across bounded
  concepts, ResearchAsset records, ResearchSource records, seed/external strategies,
  and retained Markdown reports. The endpoint is a projection only: writes,
  credential access, order endpoints, venue connection, and execution authority are
  explicitly disabled/absent/NONE.
- **Comparison product surface (2026-07-11):** `/api/v1/dashboard` now projects
  retained comparison evidence and the dashboard includes a "Comparisons" view:
  candidate dimension scorecards, validation gates, production G10 rows, seed
  positive-context probes, seed G10, cross-engine scope notes, and evidence refs.
  It selects no winner and exposes no approval, job, credential, venue, paper/demo/live,
  or order control.
- **Demo-wallet readiness projection (2026-07-11):** the Trading Domain API/UI now
  exposes a design-only future demo-wallet readiness record: ledger absent,
  synthetic capital not created, mutation API absent, order route absent, venue
  connection `NONE`, and `execution_authority=NONE`. The view lists the S2/HG/S3
  predicates, future isolated-simulation scope, and must-never-include guardrails
  without adding any activation control or wallet state.
- **S3/S4 gate-readiness projection (2026-07-11):** the Trading Domain API/UI now
  separates S3 paper/demo readiness from S4 live readiness. Both are `NOT_READY` and
  `BLOCKED_BY_GATES`; the projection lists satisfied design evidence, missing gates,
  and next human actions while keeping `execution_authority=NONE` and exposing no
  activation, venue, credential, order, paper/demo, or live control.
- **Stage-gates API projection (2026-07-11):** `GET /api/v1/stage-gates` exposes the
  same S3/S4 readiness contract as a standalone read-only API. Capabilities explicitly
  report writes disabled, credential access absent, order endpoint absent, venue
  connection `NONE`, and demo/paper/live controls absent.

## Operational SSOT (unchanged)

`handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md` remains the single operational source of truth for coding-agent execution (D-027). It was updated 2026-07-06 to reference the planning system (D-030); no competing controller exists.

## Coding authorization status (explicit, per planning mandate §25)

- Planning Complete? **YES** (this pass; see audits).
- Research Complete Enough? **YES for constrained S2 entry** — S2 sourced research remains hypothesis input, not inherited proof or strategy approval.
- Architecture Approved? **YES for constrained S2.** Boundaries, contracts, principles, lifecycle, and rejections are APPROVED by D-037; later paper/live architecture remains gate-controlled.
- Prototype Execution Authorized? **YES** (D-025 + readiness gate PASS; entry condition: HG-1 intake gate).
- Constrained S2 Architecture/Research Lab Authorized? **YES** — D-036; scope is `docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md`.
- MVP Build Authorized? **NO beyond the constrained S2 research-lab/research-console scope.**
- Live Trading Authorized? **NO** — S4; human-only gates untouched.

## What was added 2026-07-06 (planning pass)

- Architecture: `docs/architecture/AD.md` (§A–§AL), `MODULE_CATALOG.md`, `TYPE_AND_CONTRACT_CATALOG.md`.
- Program/product: `docs/program/PROGRAM_PLAN.md` (stages S0–S4, EG/HG gates), `docs/product/MVP_SCOPE.md`.
- Tasks: `TODO.md` + 21 initiative files under `todos/` (REQ-traced, acceptance-gated).
- Testing: `docs/testing/TEST_MASTER_PLAN.md`.
- Traceability: `docs/traceability/TRACEABILITY_MATRIX.md` (REQ-001…058 + deferred series).
- AI: `docs/ai/AGENT_ROLES.md` (R1–R9), `skills/` (README + 13 skill specs).
- Research: `research/EXISTING_CAPABILITY_REGISTRY.md` (evidence refreshed 2026-07-06), `research/RESEARCH_GAP_MATRIX.md` (9 gaps closed, 16 open with owners).
- Audits: `audits/ARCHITECTURE_COMPLETENESS_AUDIT.md`, `audits/TODO_COMPLETENESS_AUDIT.md`, `audits/RED_TEAM_PLAN_REVIEW.md`, `audits/PLANNING_HANDOFF_SIMULATION.md`.
- Decisions: D-029 (dataset µs amendment), D-030 (planning layer), D-031 (ID hygiene fix), D-032 (registry-driven candidate adjustments). Duplicate IDs renumbered to D-027/D-028.

## Material evidence updates folded in (2026-07-06)

- Binance public Spot data: timestamps microseconds from files dated 2025-01-01 → dataset spec Amendment A1.
- vectorbt OSS reactivated (v1.1.0) → probe OSS first; Backtrader/backtesting.py rejected.
- All four first-tier engines confirmed actively maintained; license boundaries recorded (Freqtrade GPL-3.0 → subprocess integration).
- MLflow 3.14 GenAI tracing mature; DVC now stewarded by lakeFS (active) → D-019 hypothesis retained/strengthened.
- Venue notes: OKX Israel-supported + demo env; Kraken not demoted for Israel availability
  on the 2026-07-11 official-source slice; Coinbase has Israel identity-document
  support but retail/product/API eligibility remains human/account-gated; live-venue
  human gates unchanged.
- AI providers: no determinism guarantees → multi-sample benchmarking (AD-11); OpenAI Evals platform EOL → not a dependency.

## Unresolved blockers

No blocker prevents continuing constrained S2 evidence operations. LEAN's bounded
Docker evidence is retained; missing Hummingbot full-history runs are runtime/throughput
blocked after the 2026-07-11 B2 F1/S1 timeout. B2 and the current S2 hypothesis
population remain incomplete and not approvable, including the fresh
`LAB-f04ef5d705e0de4d3fff5fe83ada90b2d91223dc89cfa35364c5fd8439ca3121`
source-registry evidence refresh; this blocks strategy promotion and demo activation, not
offline research. Open items are tracked in `MISSING_AND_OPEN_ITEMS.md`.

## Exact next action

The current AD/roadmap/TODO inventory has **zero actionable open agent-executable
tasks** in the live workspace status projection (`/api/v1/status`: 88 total, 74 done,
0 open, 7 gated, 4 recurring). The completion audit is retained at
`artifacts/reports/AGENT_EXECUTABLE_COMPLETION_AUDIT_2026_07_11.md`.
Do not manufacture strategy-operation work as a substitute for product development:
additional replays should run only when needed to verify a new application feature or
after an explicit research-direction decision changes inputs. The next finite work is
human/credential/S3 gated: AI provider key + spend for T-011-05/T-017-05, or S2 exit/
HG-3/paper-demo preparation after a future complete approvable strategy exists. The
live progress surface remains `make dashboard` at `http://127.0.0.1:8765`, including
read-only Automation, Search, Comparisons, and Trading Domain/demo-wallet readiness.

## Exit condition of next phase (unchanged)

S2 exit requires the plan's verification package and HG-3. Paper/demo activation also
requires complete approvable validation, promotion eligibility, a paper-lane
architecture decision, a security pass, and new operator approval for the specific
integration. Until then, venue connections and execution remain disabled.
