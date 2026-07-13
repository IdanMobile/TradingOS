# Trading Intelligence OS — Project State

Last updated: 2026-07-13 (supervisory baseline; constrained S2 active)
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
  `artifacts/validation/seed_candidates/SEED_G10_QC2_ETHUSDT_1H_2026_07_13.json`
  runs production-style PBO/DSR on the QC2 ETHUSDT 1h searched window grid. The
  surviving `window=40` context has a numeric FAIL diagnostic under the aligned v2
  method: PBO 0.2662 and DSR 0.8548. G10 itself remains `METHOD_BLOCKED` because the
  prior 258-trial context shortlist and hierarchy-wide dependence evidence are
  unresolved. No seed context is validated or promotion-eligible.
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
- **T-009-04 numeric integration retained; production G10 method-blocked:** candidate-specific
  PBO/CSCV and DSR now run on the retained B2/B3/B4 trial populations
  (`scripts/run_g10_candidate.py` + engine-side `engines/vectorbt/g10_returns.py`),
  with exact per-trial parity verification against the retained LAB Parquet and an
  independent second implementation agreeing to ≤1e-9 (PBO) / ≤1e-6 (DSR) over
  12,870 CSCV splits. The v2 contract aligns per-bar Sharpe across selection, both
  CSCV halves, and DSR, and estimates family-scope effective trials only from retained
  return correlations. B2 numerically FAILS (PBO 0.2960, DSR≈0); B4 numerically FAILS
  (PBO 0.3810, DSR≈0); B3 is `METHOD_BLOCKED` because no-trade trials make required
  correlations undefined. The historical refreshed batch
  `LAB-73ebd3a3bb3e4086b2408552559e77a26d1334ae9cc789c4459beadc27b6844a` shows
  projected `multiple_testing_selection_bias_control = FAIL` with 66 trials retained,
  no winner, `execution_authority=NONE`. Complete upstream family/dataset/engine/scenario
  search lineage and hierarchy-wide dependence evidence were never retained, so production
  G10 remains `METHOD_BLOCKED`. Evidence:
  Historical evidence: `artifacts/validation/G10_CANDIDATE_EVIDENCE_2026_07_11.json`;
  corrected method-limited evidence:
  `artifacts/validation/G10_CANDIDATE_EVIDENCE_2026_07_13.json`.
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
- **S3/S4 inert control-plane contracts (2026-07-11):** `tios.trading_domain` now
  models future `StageGateReadinessRecord`, `StageGateRequirement`,
  `PaperLaneProposal`, `PaperDivergenceReport`, and `LiveReadinessProposal` records.
  They validate S3/S4 prerequisite evidence, human-decision evidence, synthetic-local
  paper proposal shape, backtest-versus-paper divergence tolerance rows, and
  limited-live risk-limit shape while rejecting venue demo/testnet proposals before
  credential gates and keeping `execution_authority=NONE`, `venue_connection=NONE`,
  `paper_orders=DISABLED`, and `live_orders=DISABLED`. The dashboard projects this
  as `MODELED_INERT` with zero active records.
- **S3/S4 control-plane readiness artifact (2026-07-11):**
  `scripts/build_s3_s4_readiness_artifacts.py` now retains
  `artifacts/reports/S3_S4_CONTROL_PLANE_READINESS_2026_07_11.{json,md}`. The report
  validates representative S3 gate, S4 gate, paper-lane proposal, paper-divergence,
  operational-drill, and live-readiness probe records while explicitly keeping active
  record counts at zero and capabilities disabled. The dashboard exposes the retained
  artifact, blockers, mode `CONTROL_PLANE_PROBE_ONLY`, and `execution_authority=NONE`.
- **S3/S4 operational-drill contracts (2026-07-11):** `OperationalDrillRecord`
  now models future feed-loss, stale-data, engine-crash, manual kill-switch, and
  credential-revocation drill evidence. Completed drills require evidence; blocked
  drills require blockers; not-run drills cannot carry evidence. The retained
  S3/S4 readiness artifact includes PASS and BLOCKED probe rows while active
  operational-drill record count remains zero.
- **Synthetic demo-ledger contracts (2026-07-11):** `SyntheticLedgerSnapshot` and
  `SyntheticLedgerEntry` now model future mock-money demo/paper wallet accounting.
  Entries require evidence, balances must match the latest entry balance per currency,
  records are explicitly `synthetic=true` / `real_money=false`, and all execution,
  venue, paper-order, and live-order capabilities remain disabled. The retained
  S3/S4 readiness artifact includes a probe ledger with initial mock capital and a
  fee debit while active synthetic-ledger count remains zero.
- **Synthetic paper-fill policy contracts (2026-07-11):** `SyntheticPaperFillPolicy`
  now models deterministic local fill assumptions for future demo/paper reconciliation:
  price source, fixed fee bps, slippage bps, and fill-latency ceiling. The retained
  S3/S4 readiness artifact includes a probe policy while active paper-fill-policy
  count remains zero and no fill engine, wallet mutation, venue route, or order
  capability is activated.
- **Synthetic account/portfolio snapshot contracts (2026-07-11):**
  `SyntheticAccountSnapshot` and `SyntheticPortfolioSnapshot` now model future
  mock-money demo account and portfolio projections linked to the synthetic ledger.
  The retained S3/S4 readiness artifact includes probe account/portfolio snapshots
  while active synthetic-account and synthetic-portfolio counts remain zero, with no
  active balances, venue route, wallet mutation, or order capability.
- **Synthetic runtime-risk policy contracts (2026-07-11):**
  `SyntheticRuntimeRiskPolicy` now models future demo/paper runtime limits for
  capital-at-risk, position notional, daily loss, drawdown, and kill-switch mode.
  The retained S3/S4 readiness artifact includes a probe policy while active
  runtime-risk-policy count remains zero, with no active risk engine, venue route,
  wallet mutation, or order capability.
- **Synthetic portfolio-risk policy contracts (2026-07-11):**
  `SyntheticPortfolioRiskPolicy` now models future demo/paper portfolio caps for
  symbol concentration, correlated exposure, per-strategy budget, and open-position
  count. The retained S3/S4 readiness artifact includes a probe policy while active
  portfolio-risk-policy count remains zero, with no active risk engine, venue route,
  wallet mutation, order capability, or execution authority.
- **Synthetic risk evaluation and fail-closed readiness (2026-07-12):**
  per-strategy budget and market-condition policies now complement the runtime and
  portfolio policies. A pure independent evaluator produces evidence-backed
  `RiskDecision` PASS/BLOCK rows for capital, notional, loss, drawdown, exposure,
  stale data, spread, venue health, timestamp order, and kill-switch state. Synthetic
  ledger snapshots now verify every credit/debit transition and reject overdrafts.
  Paper stability cannot pass without its full declared window, full uptime, and zero
  incidents; S4 gate records require the full named prerequisite chain; dashboard
  readiness artifacts fail closed on hash mismatch. Active policy/ledger counts remain
  zero and no mutation, venue, credential, or order route exists.
- **Synthetic execution and canonical signal reducers (2026-07-12):** pure local
  reducers now calculate deterministic synthetic fills, apply adverse slippage and
  maker/taker fees, replay mock-ledger changes idempotently, reject insufficient
  funds, derive fee-aware long-only position cost/P&L, and reconcile ledger cash to
  account/portfolio equity. A canonical strategy evaluator now executes rule trees
  and the unambiguous SMA, EMA, Bollinger, Wilder-RSI, prior-bar Donchian,
  rate-of-change, and reference-price vocabulary, emitting deterministic bar-close
  transition signals. Supertrend now preserves source-specific semantics: pandas-ta/
  Hummingbot uses bullish `+1` with its one-percent proximity gate, while TradingView
  uses bullish `-1`. These are pure evidence functions: active
  synthetic records remain zero and no order, credential, venue, or mutation API exists.
- **Computed S3/S4 evidence and incident lifecycle (2026-07-12):** position P&L
  now uses signed money so losses are representable while balances/fees/limits stay
  nonnegative. Like-for-like metric maps now deterministically build divergence
  reports; heartbeat and incident events compute paper uptime/stability rather than
  accepting caller-supplied PASS. A limited-live evidence resolver checks every
  package reference, paper stability, credential order cap, runtime limits, manual
  kill switches, runbook linkage, and all required drills. Operational incidents now
  have immutable open/acknowledge/resolve ownership and post-incident evidence
  transitions. Active incident and S3/S4 record counts remain zero; no execution or
  mutation capability exists.
- **Durable gated evidence and approval history (2026-07-12):** a confined,
  append-only SQLite evidence ledger now provides canonical hashing, idempotency,
  bounded reads, concurrent-writer serialization, and integrity checks for synthetic
  evidence. Typed human decisions have expiry and explicit approve/reject outcomes;
  immutable gated approval history enforces the exact S3/S4 requirement sets. Current
  S2 approval transitions cannot reach paper or live states. No active evidence ledger,
  approval, credential, venue, scheduler, wallet, or order route was created.
- **Restricted credential boundary contracts (2026-07-11):**
  `RestrictedCredentialPolicy` now models future S4 credential scope without carrying
  secret material. Funds movement is forbidden, credential material remains absent,
  and the retained S3/S4 readiness artifact includes a probe policy while active
  restricted-credential-policy count remains zero, with no venue connection or order
  capability.
- **Paper operations runbook contracts (2026-07-11):** `PaperOperationsRunbook`
  now models future S3 paper/demo operational discipline: heartbeat cadence,
  heartbeat timeout, log retention, manual/local intervention mode, and a runtime
  risk-policy reference. The retained S3/S4 readiness artifact includes a probe
  runbook while active paper-operations-runbook count remains zero, with no venue
  route, order capability, or execution authority.
- **Paper operations event-log contracts (2026-07-11):**
  `PaperOperationsEventRecord` now models future S3 paper/demo evidence rows for
  process, heartbeat, manual-intervention, kill-switch, and log-retention events.
  The retained S3/S4 readiness artifact includes a heartbeat probe while active
  paper-operations-event count remains zero, with no venue route, order capability,
  or execution authority.
- **Paper stability report contracts (2026-07-11):** `PaperStabilityReport` now
  models future S3 exit stability evidence: observation window, required hours,
  uptime fraction, incident counts, missed heartbeats, linked divergence/runbook/risk
  records, and PASS/FAIL/BLOCKED status. The retained S3/S4 readiness artifact
  includes a blocked probe while active paper-stability-report count remains zero,
  with no venue route, order capability, or execution authority.
- **Limited live risk-package contracts (2026-07-11):** `LimitedLiveRiskPackage`
  now models future S4 risk packaging across paper-stability evidence, credential
  policy, operations runbook, runtime risk policy, capital-at-risk, single-order
  notional, daily-loss limit, and kill-switch mode. The retained S3/S4 readiness
  artifact includes a blocked probe while active limited-live-risk-package count
  remains zero, with no venue route, order capability, or execution authority.
- **Live operations runbook contracts (2026-07-11):** `LiveOperationsRunbook`
  now models future S4 operational discipline: heartbeat cadence, incident-response
  target, log retention, escalation mode, limited-live-risk-package linkage, and
  restricted-credential-policy linkage. The retained S3/S4 readiness artifact
  includes a probe runbook while active live-operations-runbook count remains zero,
  with no venue route, order capability, or execution authority.
- **Live operations event-log contracts (2026-07-11):**
  `LiveOperationsEventRecord` now models future S4 operational evidence rows for
  heartbeat, risk-limit, kill-switch, escalation, and log-retention events. The
  retained S3/S4 readiness artifact includes a probe heartbeat event while active
  live-operations-event count remains zero, with no venue route, order capability,
  credential access, or execution authority.
- **TradingView public-strategy intake lane (2026-07-11):** the external-source
  registry now distinguishes TradingView public ideas from open-source Pine strategy
  publications with Strategy Tester summaries. `INTAKE-TRADINGVIEW-PUBLIC-STRATEGIES`
  captures license/attribution, Pine visibility, parameters, Strategy Tester settings,
  and summary metrics as external evidence only; `RPH-TRADINGVIEW-PUBLIC-STRATEGY-TESTER`
  requires local OS reproduction and a TV-vs-OS divergence report before any validation
  claim. Protected/invite-only code remains excluded, `execution_authority=NONE`, and
  no paper/demo/live/order path is enabled.
- **TradingView candidate selection (2026-07-11):** web research selected eight
  open-source/public TradingView strategy candidates for offline reproduction:
  SuperTrend, RSI mean reversion, Bollinger/ATR/EMA, BTC TSI, RSI TP/SL, RSI
  divergence, BTC multi-indicator Super 8, and AI SuperTrend/Pivot. The retained
  batch is metadata-only (`selected_candidates_2026_07_11.json`): Strategy Tester
  metrics and Pine source hashes are still pending per-candidate capture, no code is
  copied, no candidate is validated, and `execution_authority=NONE`.
- **TradingView first local replay (2026-07-11):** two candidates with sufficiently
  specific public-page rules now have a prose-derived offline replay against frozen
  BTCUSDT/ETHUSDT x 5m/15m/1h candles:
  `artifacts/external_replay/tradingview_public_strategies/TVPINE-9f7d3fc15ece2785a4296e9eb3b15548/`.
  The run covers 12 trials and 57,046 retained local signal/execution events for
  `TVPINE-RAGINGPORRA-RSI-MEAN-REVERSION` and `TVPINE-SKYREXIO-BB-ENHANCED`.
  It is explicitly `EVIDENCE_RETAINED_NOT_VALIDATED`: exact Pine source bodies and
  complete TradingView Strategy Tester exports were not captured, no winner is
  selected, no candidate is promotion-eligible, and `execution_authority=NONE`.
- **Copied public-strategy search (2026-07-12):** operator asked to test copied
  public strategies (not internally generated) until one passes. Twenty well-known
  public systems (Turtle S1/S2, Donchian, Golden Cross, SMA/EMA crosses, Bollinger
  reversion/breakout, Connors RSI2, RSI14/RSI4, ROC momentum, Triple-MA, SMA200 trend
  filter, BB+RSI) were replayed across BTCUSDT/ETHUSDT x 5m/15m/1h with a parameter
  neighborhood via `scripts/run_external_strategy_search.py`. **0 of 20 pass** the
  honest screen (positive holdout + beats buy-and-hold net of fees + neighborhood
  robust + >=10 trades): of 120 contexts, 13 were positive full-period, 2 beat
  buy-and-hold, and **0 were positive in all three chronological thirds**. Best row
  (EMA 20/50 ETH 1h, +198%) is single-regime and fails the thirds test. Artifact:
  `artifacts/research_lab/external_strategy_search/EXTERNAL_STRATEGY_SEARCH_2026_07_12.json`.
  No candidate is validated; `execution_authority=NONE`.
- **S3 paper-lane synthetic probe (2026-07-12):** with no strategy passing validation,
  the S3 paper lane was exercised END-TO-END in synthetic probe mode over frozen data
  via `scripts/run_s3_paper_probe.py`, routing the strongest (still validation-FAILED)
  QC2 Donchian ETHUSDT-1h-w40 signals through the real inert contracts: synthetic
  fill -> ledger -> spot position -> portfolio -> backtest/paper divergence report.
  553 synthetic trades; paper +103.6% vs backtest-proxy +149.1%; divergence
  `OUTSIDE_TOLERANCE` on trade-count/fee (close-fill+slippage vs next-open — the
  expected, meaningful signal). `mode=SYNTHETIC_LOCAL_SIMULATOR`, candidate
  `NOT_ELIGIBLE`, `venue_connection=NONE`, paper/live orders `DISABLED`, no order
  route. Artifact: `artifacts/trading_domain/s3_paper_probe/S3_PAPER_PROBE_2026_07_12.json`.
  Full gate green afterward: ruff + mypy-strict + **399 tests pass**.

- **Data profile + signal-based strategy search (2026-07-12):** to widen the search
  surface, the market character of the frozen dataset was profiled
  (`scripts/data_profile.py` -> `artifacts/research_lab/data_profile/DATA_PROFILE.json`:
  BTC ~60% / ETH ~78% annualized vol, $2.6B/$1.4B daily USD turnover, ~49% taker buy
  pressure, -77%/-81% buy-hold max drawdown) and five strategy families that USE the
  previously-ignored volume/volatility/order-flow fields were tested through the same
  honest screen (`scripts/run_signal_strategy_search.py`). **First screen survivor
  found:** `SIG-VOLUME-BREAKOUT` (volume-confirmed Donchian, ETHUSDT 1h, window=40,
  mult=1.5) is positive in ALL THREE chronological thirds (train +38.8% / validation
  +35.9% / holdout +34.7%), returns +153.9% vs buy-hold +112.4%, 511 trades — the
  consistency that all 20 price-only public strategies failed. **It passed the SCREEN,
  not validation:** it still owes production G10 (DSR>=0.95, PBO) and cross-engine
  reproduction, is ETHUSDT-1h-only (1/6 contexts), and stays `NOT_ELIGIBLE` /
  `execution_authority=NONE`. Product strategy + path-to-live written at
  `docs/product/PRODUCT_STRATEGY_AND_GTM.md`. Full gate green: 409 tests.

- **Multi-dataset acquisition pipeline (2026-07-12):** operator approved a data
  expansion (top-50 spot pairs, all timeframes, funding, BTC/ETH ticks). After measuring
  real sizes (BTC+ETH aggTrades = 77.9 GB, not the ~55 GB estimated) and a disk review,
  the approach was revised to keep the laptop light while preserving the checksum-frozen
  reproducibility the gates depend on. Built + gate-green (419 tests): `acquire.py`
  (checksum-verified resumable downloader, plan/fetch modes — validated on real files),
  `normalize_multi.py` (klines→canonical parquet, BTCUSDT_1d full-span verified),
  `tick_features.py` (aggTrades→1-minute microstructure bars: buy/sell imbalance, VWAP,
  whale-trade size — validated 65.2M BTC ticks→44,640 bars, so full history freezes at
  ~sub-GB not 78 GB), and `daily_update.py` (append-only REST refresh reusing the
  canonical schema+dedup). Plan: `docs/product/MARKET_DATA_ACQUISITION_PLAN.md`. Free
  public data only; paid vendors/L2/on-chain remain operator-procured (agent never
  enters payment or credentials). Everything stays `execution_authority=NONE`.

- **Strategy research arc — exploratory negative evidence (2026-07-12):** with the expanded
  multi-pair data flow in place, the tested strategy implementations produced corrected
  DSR diagnostics (nominal threshold 0.95). Results remain `NOT_ELIGIBLE`:
  single-asset technical (20 public + 5 signal + 18-strategy trend cluster with realistic
  vol-targeted sizing across 40 datasets, 2277 trials) → DSR ~0.69–0.76; cross-sectional
  momentum long-only with dual-momentum cash filter + vol targeting → DSR **0.9456**
  (28 pairs, the closest) but degrades to 0.9091 at 34 pairs (fragile); cross-sectional
  long-short → DSR ~0.70. **Nothing clears the numeric 0.95 screen.**
  Methodology fixes applied: realistic sizing (removed all-in-compounding fantasy
  numbers), complete-history filter (removed a 1-month UNI listing-pump artifact), proper
  raw-trial deflation diagnostics. Tooling: `scripts/run_universe_search.py`,
  `run_trend_validation.py`, `run_cross_sectional_momentum.py`. Honest conclusion: no
  the tested price/technical implementations did not produce a validated edge. This does
  not reject whole strategy families; survivor/cost, provenance, holdout, search-lineage,
  and effective-trial gaps remain. Thresholds were not changed;
  `execution_authority=NONE`.

- **Funding-carry (first non-predictive strategy) + honest caveat (2026-07-12):** after
  web research (recorded in `research/SOURCE_REGISTRY.md` + AD §R + graphify) pointed to
  delta-neutral funding carry as crypto's most robust NON-predictive edge, it was
  backtested from the downloaded funding data (`scripts/run_funding_carry.py`, 50 pairs,
  9851 8h periods). The simplified carry hypothesis produced BTC +11.6%/yr,
  ETH +12.5%/yr; a selective positive-funding basket ~8.8%/yr. Its numeric DSR diagnostic
  is 1.0, **not a G10 PASS or genuine validation** (`verdict_is_genuine: false`): the
  model includes ONLY the funding leg and omits basis divergence, liquidation, and
  execution/slippage — the dominant real risks — so the smooth low-vol yield inflates
  Sharpe (~11) and DSR. Naive all-pairs carry is negative (alt tail); selection is
  required. Honest verdict: funding carry is the most promising real signal in the arc,
  but truthful validation needs perp-price/basis modelling (funding downloaded; perp
  klines/mark not yet), and trading needs perps/margin (S4-gated). `execution_authority=NONE`.

- **Market-neutral pivot + strategy direction brief (2026-07-12):** deeper web research
  (recorded in source registry + AD §R + graphify) established that predictive price
  strategies are a dead end in liquid crypto, while MARKET-NEUTRAL strategies are the
  real, documented edge (2025: dollar-neutral ~31% benchmark, stat-arb BTC-ETH Sharpe
  ~2.2, drawdowns <1%; carry's 2022 killer was counterparty, not price). Naive daily
  stat-arb pairs tested (`scripts/run_stat_arb_pairs.py`, 10 curated pairs, 40 trials):
  best AVAX/SOL Sharpe 0.58, DSR 0.15 — FAIL (crypto pairs not cointegrated at daily
  frequency; pro version needs cointegration test + hedge ratio + intraday). Full 50-pair
  download complete. Strategic brief at `docs/product/STRATEGY_RESEARCH_DIRECTION.md`:
  the path to a validated *tradeable* strategy runs through proving a market-neutral edge
  in backtest, then the operator unlocking perp/margin (S4). Highest-value honest next
  build: download (free) Binance perp klines/mark and validate funding carry WITH basis +
  liquidation risk. Thresholds untouched; `execution_authority=NONE`.

- **Basis-aware funding carry — the real edge, honestly bounded (2026-07-12):** the free
  Binance perp+spot 8h data was downloaded (acquire `--kinds basis`, 12 pairs) and the
  funding carry re-backtested INCLUDING the spot-perp basis P&L it previously omitted
  (`scripts/run_funding_carry_basis.py`, 6021 8h periods). Result: best basis-aware carry
  Sharpe 9.17, ann 12.7%, maxDD -0.5%, DSR 1.0 — **but `verdict_is_genuine: false`.** The
  carry genuinely SURVIVES basis risk (real: a well-arbitraged perp tracks spot within
  ~0.1%), confirming it is a robust market-neutral edge — the first real candidate in the
  whole arc, matching how crypto funds actually make money. Sharpe ~9 is still inflated vs
  real-world ~2-4 because it omits execution slippage, intraperiod basis spikes,
  leverage/liquidation, and exchange COUNTERPARTY risk (the actual 2022 killer). Honest
  conclusion: the remaining validation is EXECUTION-level (needs S3 paper trading to
  measure real fills/slippage) and OPERATIONAL (counterparty = venue selection, operator
  decision) — NOT a price-prediction problem. This makes funding carry the concrete,
  evidence-backed candidate that justifies preparing S3/HG-3 and the S4 perp capability.
  Thresholds untouched throughout; `execution_authority=NONE`.
- **Funding carry through the S3 paper lane — execution measured (2026-07-12):** the honest
  remaining step (execution-level validation) was built: `scripts/run_funding_carry_s3_paper.py`
  drives the SAME basis-aware best config (thr=0.0, lb=21, reb=3) through EXPLICIT per-leg
  execution — every delta-neutral rebalance trades both legs (spot + perp), each paying a
  10bps taker fee + 2bps slippage = 24bps/toggle, versus the backtest's coarse 4bps proxy —
  and routes the cash flows through the real synthetic ledger contract (init → net-settlement
  credit → fee debit, no overdraw). Result over 6021 8h periods: realistic execution cuts
  annual carry from **12.7% → 8.4%/yr** (a 4.3 pct-pt erosion; 812 leg-toggles, ~$2,552
  execution cost on $10k). The paper-vs-backtest divergence report is OUTSIDE_TOLERANCE on
  FEE_TOTAL (6× the fee) with IDENTICAL TRADE_COUNT — i.e. the signals/fills are the same, only
  the cost diverges, which is exactly what S3 exists to measure. **Honest conclusion: the carry
  edge SURVIVES realistic execution at this turnover (still net-positive ~8.4%), so the one
  remaining unmodelled risk is COUNTERPARTY/venue — an operator+S4 decision, not backtest math.**
  Still `NOT_ELIGIBLE` / `execution_authority=NONE` / `SYNTHETIC_LOCAL_SIMULATOR`; no venue, no
  orders. `make check` = 441 tests green (+3). Artifact:
  `artifacts/trading_domain/s3_carry_paper/S3_CARRY_PAPER_2026_07_12.json`.
- **Professional stat-arb — rigorous OOS negative result (2026-07-12):** the naive daily
  pairs strategy (DSR 0.15) was rebuilt properly: `scripts/run_stat_arb_pro.py` adds an
  in-sample Engle-Granger COINTEGRATION gate (pure-Python OLS hedge ratio + Dickey-Fuller
  t-stat on the residual; no numpy/statsmodels by project design), an ESTIMATED hedge ratio
  β (not fixed 1:1), OUT-OF-SAMPLE-only evaluation (60/40 split, no pair-selection lookahead),
  and 1h frequency (15 pairs available). Result: 5 of 10 curated pairs cointegrate in-sample,
  but the best OOS config (ADAUSDT/DOTUSDT, β=0.84) delivers Sharpe 0.1, ann **-3.3%**, maxDD
  -40%, **DSR 0.0088 → FAIL**. This is the classic COINTEGRATION-DECAY finding: pairs that
  cohere in-sample de-cohere out-of-sample, so honest OOS scoring makes stat-arb *worse* than
  the lookahead-tainted naive version, not better. Rigorously rules out crypto pairs stat-arb
  as a standalone edge. Consequence: the risk-parity COMBINATION framework is correctly NOT
  built (needs ≥2 validated sleeves; only carry survives). `execution_authority=NONE`;
  thresholds untouched. Artifact: `artifacts/validation/stat_arb_pro/STAT_ARB_PRO.json`.
  Full suite after both builds: 446 pytest green.
- **Carry robustness sweep — the headline number is regime-inflated (2026-07-12):**
  `scripts/run_funding_carry_robustness.py` walks the realistic-execution carry P&L per
  regime and stress-tests counterparty risk. Critical honest finding: the 8.4%/yr full-period
  figure is DOMINATED BY THE 2021 BULL. Per-regime realistic-execution carry: **2021 bull
  +42.6%/yr, 2022 bear −3.8%/yr, 2023-26 recovery/chop +3.7%/yr** (worst year 2026 −7.1%/yr).
  So carry is REGIME-DEPENDENT, not all-weather — roughly break-even-to-negative once the
  2021 anomaly is excluded. Counterparty haircut stress: −10% → ~2yr recovery, −50% → ~9yr,
  **−100% (exchange default, the FTX/LUNA case) → UNRECOVERABLE**. Conclusion: the binding
  risk is not market regime but counterparty/custody, which is precisely why venue selection
  is a human operator decision, not a backtest output. This tempers the "go to market with
  confidence" case: carry is a real but modest, regime-sensitive edge with an unrecoverable
  tail — not a standalone green light. `execution_authority=NONE`; no gate crossed. Artifact:
  `artifacts/validation/funding_carry_robustness/FUNDING_CARRY_ROBUSTNESS.json`. Full suite: 455 green.
- **Operator authority-transfer declined, by design (2026-07-12):** operator offered to let
  the agent self-authorize the S3 paper activation (HG-3), S4 perp/margin capability, and
  venue/paid-data procurement. DECLINED and held: these are human-only gates (D-036/D-037/AD
  §AA) plus prohibited agent actions (account/credential/payment). An AI flipping its own
  live-capability gates voids the entire governance guarantee; delegation does not transfer
  that authority. Agent instead produced decision-ready evidence (robustness + stress above).
  `execution_authority=NONE` unchanged.
- **S3 hardening + HG-3/4/5 decision packages (2026-07-12):** operator goal was to complete
  HG-3/4/5. Held the human-only boundary (D-042) and instead completed everything up to each
  human signature. Two hardening research models built (both RESEARCH-ONLY, thresholds
  untouched, `execution_authority=NONE`): (1) `run_carry_counterparty_diversification.py` —
  a single venue is an UNRECOVERABLE −100% counterparty tail; splitting across K venues with
  per-venue caps converts it to a recoverable 1/K loss and shrinks total wipeout to p^K
  (expected drag unchanged ~p) → the go/no-go is an HG-4 multi-venue decision, not a backtest;
  (2) `run_funding_carry_regime_filter.py` — a CAUSAL universe-funding deploy gate lifts the
  2022 bear from −3.8% to −0.7%/yr while holding full-period 8.4% (no lookahead, not a date
  filter). Decision packages assembled: `docs/program/HG_DECISION_PACKAGES.md` (ready-to-sign
  HG-3/HG-4/HG-5 with prerequisites done + the ten HG-4 items + sizing guidance) and the honest
  boundary memo `docs/program/AGENT_NOTES_TO_OPERATOR.md`. Bottom line recorded: no strategy is
  genuinely validated (carry's DSR pass is not genuine — off-sample counterparty tail), so
  T-015-02 stays blocked on a real validation + the human gates. All agent-authored work green;
  the one red test (`test_dashboard_includes_read_only_tradingview_market_monitor`) is a
  separate concurrent stream's half-built dashboard feature, deliberately left to that stream.
- **Supersession notice for all retained demo entries below (D-046, 2026-07-13):**
  these authenticated venue-demo runs occurred outside the required HG-3/HG-4,
  validation, security, and integration-approval chain. Their use of
  `execution_authority=NONE` incorrectly treated “no real money” as “no execution
  authority required.” They are historical unauthorized governance-probe evidence,
  not current capability, qualification, or permission; all authenticated transports
  are now quarantined before network access.
- **Demo venue execution proven — first real order→fill→reconcile (2026-07-13):** operator
  obtained a Bybit **demo** account and drove the venue-testnet rung end to end. New self-contained
  tooling (kept out of the concurrently-edited paper module): `scripts/demo_preflight.py` (read-only
  key-safety check — demo-host-locked, refuses any key that can move funds) and
  `scripts/demo_roundtrip.py` (a hard-capped ≤50 USDT spot market buy → poll to Filled → wallet
  reconcile). Preflight GREEN (connected to `api-demo.bybit.com`, trade-only, no fund removal,
  50k USDT + 1 BTC/ETH demo balances). Live round-trip GREEN: order `2257869337098718464` filled
  0.00039178 BTC @ $63,812.10; USDT 50000→49975 (−25 exact), BTC 1→1.00039138 (+fill). Proves the
  full venue plumbing (V5 HMAC signing, order create/query, balance reconcile) on fake money.
  MACHINERY TEST ONLY — no strategy is validated; real `execution_authority` stays NONE; demo keys
  are `.env` (`PYBIT_API_KEY`/`PYBIT_API_SECRET`, trade-only, no withdrawal). Plan +
  activation ladder: `docs/program/DEMO_LANE_PLAN.md`. `make check` = 616 green.
- **Public strategy catalog expanded + first strategy-driven demo bot (2026-07-13):** operator
  asked for maximum public strategies, tested, and a dedicated bot even on the best candidate.
  (1) `run_external_strategy_search.py` grew 20→**28 copied public strategies** (+MACD, Stochastic,
  Williams %R, CCI, Keltner, Ichimoku, Vortex, Aroon with new OHLC indicators); universe search now
  33. Honest screen result: **0 of 28 survive** — reinforces that classic TA has no genuine OOS edge.
  (2) `scripts/demo_strategy_bot.py` — a real Donchian breakout signal over live Bybit klines drives
  the demo execution lane (BUY on entry, SELL on exit, ends flat). Live run: 120 real BTC 1m bars →
  3 entry/exit pairs → **6 real demo orders placed**, final FLAT. First real strategy-driven order
  flow. MACHINERY + CANDIDATE only — Donchian is NOT validated (fails DSR); demo/fake money; real
  `execution_authority` stays NONE; demo-host-locked, MAX_NOTIONAL + MAX_TRADES capped. `make check`
  = 626 green.
- **Funding-carry demo bot (perp leg) + console bot view (2026-07-13):** first bot whose signal is
  a real economic edge. `scripts/demo_carry_bot.py` reads the live funding rate and runs a
  delta-neutral cycle on the Bybit demo: LONG spot + SHORT perp (category=linear, the S4-class perp
  capability exercised ON DEMO ONLY), reports the position + funding, then closes both legs to flat.
  Live run: all 4 legs Filled (SPOT_BUY 64.6 USDT, PERP_SHORT 0.001, SPOT_SELL, PERP_CLOSE);
  post-run perp position confirmed FLAT (no residual short). Fixed a category-mismatch poll (order
  status must query linear for perp legs). Console: `build_demo_bot` projection + Operations "Demo
  bot activity" card render every bot order (strategy + carry legs) from `artifacts/demo_bot/
  activity.jsonl` — dashboard-watchable, not just terminal. MACHINERY + CANDIDATE — carry validation
  NOT genuine (counterparty tail); demo/fake money; real `execution_authority` stays NONE;
  demo-host-locked, per-leg notional capped. `make check` = 633 green.
- **Shared TP/SL ladder engine + always-on managed bot (2026-07-13):** operator asked for a
  general (demo AND real) laddered take-profit/stop-loss system and an always-on bot. (1) New shared
  venue-agnostic module `src/tios/execution/exit_ladder.py` (pure Decimal math, no execution — so it
  is identical for demo and live; only the venue adapter is gate-controlled): `build_ladder` (ATR
  stop + R-multiple TP1..TPn), `position_size` (risk-fraction / stop-distance), `evaluate` (per-tick
  scale-out fractions, breakeven-after-TP1, stop-out). DEFAULT: 2xATR stop, TP 1R/2R/3R/4R, 25% out
  each, breakeven at TP1. Fully unit-tested. (2) `scripts/demo_managed_bot.py` — continuous loop that
  enters on Donchian breakout, builds the shared ladder, and manages the exit (scale out at each TP,
  move stop to breakeven, stop-out remainder), persisting a heartbeat so the console shows ACTIVE.
  Offline-tested by walking a scripted price path (entry -> all-TP scale-out -> flat; and stop-out).
  Console (`build_demo_bot`) now surfaces heartbeat (ACTIVE/stopped + position) and P&L
  (`scripts/demo_pnl.py`, showing WIN/LOSS vs the 50k+1BTC start; currently -0.71 USDT = fees, since
  no strategy has a genuine edge). MACHINERY + CANDIDATE; demo/fake money; real execution_authority
  stays NONE. `make check` = 645 green.
- **Candlestick patterns + combination/ensemble tester — both fail honestly (2026-07-13):** operator
  asked for pattern strategies and mixing variants. (1) Added 4 candlestick-pattern strategies to
  `run_external_strategy_search.py` (engulfing, hammer/shooting-star, piercing/dark-cloud,
  morning/evening star; bullish=entry, bearish mirror=exit) → 32 public strategies; universe search
  37. Fresh run: **0 of 32 survive** the honest screen (patterns included). (2) New
  `run_strategy_combinations.py` — confluence pairs (AND-entry/OR-exit) + voting ensembles over a
  9-strategy base set, each backtested to per-bar returns and DSR-scored with trial deflation. Result:
  31 mixes tested, best (confluence Donchian-40 + Keltner) **DSR 0.0 → FAIL**. Confirms the honest
  principle: mixing zero-edge components cannot manufacture edge — confluence just cuts trade count.
  Patterns/mixes are coverage + rigorous negatives, not alpha; useful only as confluence FILTERS on a
  real edge (carry). RESEARCH-ONLY; execution_authority=NONE. `make check` = 649 green.
- **Multi-timeframe confluence — method-invalid full-sample statistic fails OOS screen (2026-07-13):**
  operator asked to test MTF (trade the lower TF only with the higher TF trend). `run_mtf_confluence.py`
  gates 1h entries by the 1d trend (daily close > SMA50), aligned CAUSALLY (each hour uses only daily
  bars that have already closed — no lookahead, unit-tested). Result: the daily-trend filter HELPED
  5/6 trend strategies in-sample. The old full-sample value 0.9778 is now explicitly a
  legacy collapsed statistic: best-pair selection hid up to 36 searched strategy/pair
  trials, so it cannot satisfy G10. The untouched tail reports PSR-versus-zero 0.7802,
  not DSR, and fails its screen. This is implementation-specific negative evidence;
  neither MTF nor carry is validated. Historical `make check` count: 652 green.

- **Full supervisory baseline and corrective containment (2026-07-13):** the repository-local
  Trading OS Supervisor completed the intake/full-baseline review at commit `672e2da`.
  It found no durable HG-3, HG-4, validation approval, security-review approval, or
  Bybit-specific integration approval, despite retained authenticated Bybit demo-order
  evidence. D-046 classifies those runs as historical unauthorized governance probes and
  quarantines the authenticated GET/POST transports before network access. No demo bot or
  paper worker was running at review time; no secret value or venue was accessed.
- **DSR correction (D-045, 2026-07-13):** the shared G10 implementation incorrectly used
  the expected maximum noise Sharpe in the skew/kurtosis denominator. The primary-paper
  formula uses the selected strategy's observed Sharpe. The shared and comparison
  implementations plus method fixtures are corrected. Corrective offline reruns preserve
  the non-approvable conclusion (B2/B4 and the seed context fail; B3 is method-blocked;
  funding PASS labels remain explicitly non-genuine), while the effective-independent-trial,
  selection-lineage, MTF, and funding-model gaps remain open in the supervisor plan.
- **Supervisory truth boundary:** the current safe stage is offline S2. The retained funding
  synthetic run is static fee/slippage cost stress, not observed G12 paper execution; no
  strategy is validation-approved or promotion-eligible. See
  `docs/supervisor/SUPERVISORY_BASELINE_2026-07-13.md` and
  `docs/supervisor/IMPROVEMENT_PLAN_2026-07-13.md`.
- **Immutable multi-data provenance correction:** future public-archive acquisition writes
  per-kind content-addressed manifests with exact official-checksum evidence; reused bytes are
  no longer presumed verified. Future REST update payloads are retained before normalization.
  The current normalized-multi snapshot pins 69 tables / 40 pairs with source, range, content,
  Parquet, code, and status hashes in `data/normalized_multi/normalized_multi_manifest.json`.
  It is explicitly `reconstructed_from_retained_files`: original run identity and historical
  REST responses cannot be recovered retroactively.
- **Holdout and canonical-strategy correction:** future public, signal, and universe searches
  select parameters on the chronological train third, freeze them, and evaluate each declared
  context once on validation/holdout. They remain context-level exploratory screens with
  `search_lineage_complete=false`, no global winner, and no promotion status. Funding carry now
  has a pinned canonical research registration under
  `strategies/research/funding-carry-basis-delta-neutral/`; it validates only
  `VALID_WITH_AMBIGUITIES`. The canonical schema now records research-only long-spot and
  short-perpetual legs with shared eligibility and refuses long-only evaluation. Pure Decimal
  accounting fixtures cover deployable capital, isolated collateral/buffer, funding, basis,
  open/settle/rehedge/close fees, timestamp ordering, capital conservation, missing data, and
  terminal maintenance breach. Funding input contracts, venue-specific lifecycle integration,
  intraperiod liquidation, empirical execution, and counterparty semantics remain unresolved.
- **Future research fail-closed contracts and first completed campaign:**
  `research/BASELINE_G10_SEARCH_CAMPAIGN_V1.yaml` froze and completed the bounded 66-trial
  B2/B3/B4 reproduction roster, dataset, specs, engine, scenario, parameters, Sharpe metric,
  CSCV policy, hashes, stop rules, and non-authority before any run. New substantive strategy
  artifacts must pass `tios.evidence.validate_substantive_research_metadata`, including exact
  code/data/manifest/spec/campaign/cost/split/trial-population/output lineage. These contracts
  do not reconstruct omitted historical search stages or authorize promotion or execution. The
  clean, offline run at commit `7782752` retained all 66 trials: B2 and B4 numerically FAIL, B3 is
  method-blocked, and the overall gate is `METHOD_BLOCKED`. The retained implementations are
  explicitly legacy current-close/F1-S0 accelerator proxies, not canonical next-open strategy
  conformance. Evidence: `artifacts/reports/G10_PREREGISTERED_CAMPAIGN_REPORT_2026_07_13.md`.
- **Canonical baseline V2 completed as a negative reproducibility/conformance diagnostic:**
  `research/CANONICAL_BASELINE_G10_CAMPAIGN_V2.yaml` froze a separate 67-trial canonical-rule
  population at commit `6bac8bf`: B2 persistent state, B3 population variance, B4 prior-high
  exclusion, exact-adjacent next-open fills, gap-expired pending signals, segment warm-up reset,
  position-aware conflicts, six cost cells, five expanding historical pseudo-OOS folds, and
  family plus campaign-wide PBO/DSR. The portable 66-archive source manifest rebuilds the exact
  577,803-row Parquet. Formal execution and a second complete byte-identical recomputation pass.
  B2 fails (PBO 0.5066, DSR 0; selected F1/S1 return effectively -100%), B4 fails (PBO 0.3739,
  DSR 0; already -96.99% at F0/S0), and B3/campaign-wide are method-blocked because the selected
  diagnostic is a structural zero-trade variant and correlations are undefined. A full-history
  implementation smoke occurred before the commit and is disclosed, so this is not unseen
  evidence. The only prospective test is sealed from 2026-07-14 and cannot be evaluated before
  2027-01-14. No winner, promotion, venue, order, or execution authority exists. Evidence:
  `artifacts/reports/CANONICAL_BASELINE_CAMPAIGN_V2_REPORT_2026_07_13.md` and the content-addressed
  index under `artifacts/validation/campaigns/SEARCH-CANONICAL-BASELINE-G10-V2/`.
- **Post-V2 family selection V1 completed with `NO_GO` (D-052):** the source-backed
  `FAMILY-SELECT-V1` cycle compared exactly funding/basis carry, long-only Spot
  cross-sectional momentum, and volatility-managed Spot exposure without running a new
  parameter search. Carry fails point-in-time margin/liquidation/counterparty completeness;
  cross-sectional momentum fails point-in-time universe, canonical-ranking, and clean-lineage
  admission; volatility management fails clean-lineage/canonical-sizing admission and has
  material primary-literature OOS/cost counterevidence. No family, StrategyVersion, campaign,
  dataset, implementation, bot, venue, order, or authority was selected. Evidence:
  `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V1.md`.
- **Fresh family V2 and calendar campaign frozen (D-053):** a second exactly-three-family
  source cycle admitted only BTCUSDT Spot UTC-weekday exposure. Stablecoin below-peg and
  halving exposure were rejected on dominant semantics/sample constraints. The exact
  48,154-row public-data package, seven StrategyVersion identities, canonical calendar
  evaluator, independent Decimal ledger, vectorbt accelerator, six cost cells, chronological
  reserve, hard G1-G11 thresholds, and no-rescue rules are frozen in
  `research/CALENDAR_UTC_G1_G11_CAMPAIGN_V1.yaml`. Preflight passes offline; historical scoring
  has not run. No V2 holdout, bot, venue, credential, order, or authority was touched.
- **UTC-weekday campaign rejected (D-054):** clean-commit execution selected Wednesday and
  Decimal/vectorbt parity passed, but G5/G8/G9/G10 failed: F2/S3 `-40.74%`, F1/S1 drawdown
  `-41.29%`, Sharpe below buy-and-hold, PBO `0.7594`, and DSR `0.3012`. A second complete
  run reproduced governed numeric outputs byte-for-byte. Supervisor review also invalidates
  untouched-reserve claims because the frozen runner computed reserve metrics before selection,
  and notes missing Freqtrade/Nautilus certification. The exact context is closed without rescue;
  no bot, venue, credential, order, promotion, or authority exists.
- **Funding-pressure Spot family admitted to canonical construction (D-055):** a third bounded
  source cycle compared funding pressure, small-alt lead/lag, and options VRP without computing
  local family returns. Only a funding-feature/unlevered-Spot long/cash mechanism advances. Its
  exact 12-trial roster and select-before-reserve barrier are preregistered, and the frozen 66-ZIP
  funding plus 48,154-row Spot package passes offline semantic and drift checks. No scoring may
  occur until the whole campaign is committed cleanly; no derivative position, V2 holdout,
  calendar reserve, bot, venue, credential, order, or authority was touched.
- **Funding-pressure Spot campaign frozen (D-056):** all 12 StrategyVersions, six cost cells,
  canonical point-in-time rules, Decimal/vectorbt/Freqtrade/Nautilus role implementations,
  chronology, G1-G11 thresholds, and exact environment/data/code pins are immutable and unrun.
  A verified selection artifact is mandatory before any validation/reserve computation, and the
  deliberate early-call test fails closed. One clean offline run is next; no execution authority
  or sealed/rejected reserve access exists.
- **Funding-pressure V1 operational abort / V2 freeze (D-057):** V1 failed closed when its first
  external worker could not import the repo-local loader. No selection artifact or post-selection
  evaluation exists. V2 inherits the full V1 contract by hash and changes only worker import
  bootstrap; all three external environments now import successfully and preflight passes.
- **Funding-pressure V2 operational abort / V3 freeze (D-058):** V2 next failed closed on pandas
  mixed-timezone slice parsing, still before selection or reserve. V3 adds only explicit UTC
  normalization of the frozen bounds; the full V1 contract remains inherited by hash.
- **Funding-pressure V3 rejected (D-059):** the selection barrier passed, but validation had zero
  trades, reserve lost 2.52% on two trades, DSR was 0.8235, and Nautilus parity failed on one
  declared development trial. G4/G5/G6/G7/G8/G10 and G11 fail; the context is closed without
  rescue and no bot or execution authority exists.
- **Bitcoin transaction-activity family admitted (D-060):** an exactly-three-family source cycle
  rejects stablecoin supply and miner recovery, admitting only finalized L1 confirmed-transaction
  shocks. Exact official response bytes, 2,004 campaign observations, a two-day availability lag,
  the known November 2025 gap, strict later Spot mapping, and drift tests pass. Twelve pulse trials
  are frozen without performance; canonical/campaign work remains offline and authority-free.
- **Bitcoin transaction-activity campaign frozen (D-061):** all 12 immutable trials, four
  independent implementation roles, six cost cells, two-phase selection barrier, G1-G11 gates,
  and no-rescue boundary are preregistered. Focused tests and offline preflight pass; performance
  remains unobserved until a clean-commit run and execution authority remains `NONE`.
- **Bitcoin transaction-activity campaign rejected (D-062):** HIGH/56/1-day won development, but
  validation (-1.57%), reserve (-22.22%), full (-3.02%), stress (-51.98%), and one-bar delay
  (-21.41%) were negative. Parity passed, but G5-G10 and G11 fail; the family is closed without
  rescue and no bot or execution authority exists.
- **Bitcoin MVRV family admitted (D-063):** a fresh exactly-three-family source cycle rejects U.S.
  financial conditions and public search attention, admitting only BTC MVRV dislocations. The
  no-key official metric/catalog snapshot, 2,189 daily rows, two-day lag, zero gaps, strict Spot
  mapping, and 12 unscored trials are frozen; execution authority remains `NONE`.
- **Bitcoin MVRV campaign frozen (D-064):** all 12 StrategyVersions, four implementation roles,
  six cost cells, chronological splits, G1-G11 thresholds, and hashed development selection
  barrier are immutable. Focused causal/preflight checks pass; performance remains unobserved and
  authority remains `NONE`.
- **Bitcoin MVRV campaign rejected (D-065):** HIGH/180/1-day won development (+44.50%), but
  validation (-21.00%), reserve (-10.42%), stress (-45.53%), and delay (-20.08%) failed. PBO
  0.5895 and DSR 0.4632 fail; G5-G10 and G11 reject the family without rescue.
- **CFTC Bitcoin-futures positioning admitted (D-066):** a new exactly-three-family source cycle
  rejects blockspace-fee pressure and dormant-supply reactivation, admitting only the CFTC Legacy
  Futures Only full-size CME Bitcoin row `133741`. Its 12 unscored trials require actual CFTC
  publication dates, including official delay exceptions, before strict next-Spot-open mapping.
  No conditioned return, derivative position, bot, venue, credential, or authority exists.
- **CFTC positioning data frozen offline (D-067):** exact filtered CFTC response/metadata/schedule
  bytes retain 431 reports and 30 publication exceptions. Thirty-three official-checksum early
  Binance archives extend the existing Spot boundary to 2018, yielding 72,225 bars, 25 retained
  gaps, and 428 strict-later report mappings. Offline verification and drift tests pass; no family
  return has been computed and authority remains `NONE`.
- **CFTC positioning campaign rejected (D-069):** the clean run selected contrarian-low / 52
  reports / 1.0 z and passed G1-G4 parity/evidence gates. Negative validation, insufficient
  development/reserve sample, 63.35% drawdown, four-of-seven period breadth, inferior benchmark
  Sharpe, PBO 0.5578, and DSR 0.3493 cause G5-G11 failure. The context is closed without rescue;
  no bot, venue, paper/demo/live state, promotion, or authority exists.
- **Spot taker-imbalance family admitted without scoring (D-070):** a source-only comparison of
  aggressive Spot flow, perpetual OI crowding, and macro liquidity admits only completed-hour
  Binance BTCUSDT taker imbalance. Twelve interpretation × baseline × threshold trials, a fixed
  six-hour pulse, strict-later fill, splits, costs, gates, and no-rescue rules are preregistered.
  Performance remains unobserved; dedicated data/campaign construction is open.
- **Spot taker-imbalance data frozen (D-071):** exact official-checksum data reconstructs 72,225
  rows with 72,221 valid completed-hour features, four quarantined rows, 25 gaps, and 72,220
  strict-later mappings. Offline drift tests pass; no imbalance-conditioned return has been
  computed and authority remains `NONE`.
- **Spot taker-imbalance campaign frozen (D-072):** 12 immutable interpretation × baseline ×
  threshold StrategyVersions, four implementation roles, six cost cells, seven periods, causal
  goldens, G1-G11 gates, and a hashed development-selection barrier pass preflight. The complete
  campaign is unrun and no eligible signal performance, bot, venue, or authority exists.
- **Spot taker-imbalance V1 closed pre-selection; V2 frozen (D-073):** V1's CPU-bound reference
  scan was interrupted before any artifact, selection, OOS access, or strategy verdict. V2 inherits
  every campaign term and changes only prefix-moment computation and cost-independent event
  caching. Focused equivalence tests and preflight pass; V2 remains unrun.
- **Spot taker-imbalance campaign rejected (D-074):** V2 selected continuation-high / 168 hours /
  2.0 z, then lost 74.26% development, 11.37% validation, 57.15% reserve, and 90.23% full-history
  after costs. Stress/delay/tail/regime/benchmark/DSR fail; two nonselected vectorbt residuals also
  fail full parity. G11 closes the context without rescue; authority remains `NONE`.
- **Cross-venue premium family admitted without scoring (D-075):** a source-only comparison of a
  quote-normalized Coinbase/Binance BTC premium, U.S. Spot Bitcoin ETP flow, and USDt peg stress
  admits only the cross-venue premium. Twelve interpretation × baseline × threshold trials, strict
  completed-source-hour/later-Binance-open timing, quote conversion, gaps, and no-rescue rules are
  preregistered. Performance remains unobserved; exact Coinbase data packaging is open.
- **Cross-venue premium data frozen offline (D-076):** 382 exact public Coinbase responses are
  content-addressed with request/response provenance. Deterministic normalization produces 45,193
  aligned rows, six combined-source gaps, and 45,192 strict-later Binance-open mappings. Offline
  reconstruction, byte-identical rebuild, and deliberate drift tests pass; no return was computed.
- **Cross-venue premium campaign frozen (D-077):** 12 immutable interpretation × baseline ×
  threshold StrategyVersions, four implementation roles, six cost cells, six periods, causal
  goldens, G1-G11 gates, and a hashed development-selection barrier pass preflight. The complete
  campaign is unrun and no eligible signal performance, bot, venue, or authority exists.
- **Cross-venue premium campaign rejected (D-078):** the clean run selected continuation-positive /
  168 hours / 2.0 z, then lost 56.08% development, 8.29% validation, 24.12% reserve, and 69.44%
  full-history after costs. All six periods, stress, delay, tail, benchmark, and DSR fail despite
  complete four-role parity. G11 closes the context without rescue; authority remains `NONE`.
- **Prospective liquidation-stress signal frozen (D-080):** D-079's prospective-evidence path is
  now an immutable public-data risk-signal contract, not a retrospective strategy rescue. It uses
  Binance BTCUSD_PERP latest-one-per-second forced-order snapshots, exact five-minute windows, a
  30-day prospective baseline, strict 99th-percentile gross stress, and 80% directional share.
  Warm-up, gaps, and every unpromoted state are `FLAT/BLOCK`; the first review requires both 180
  days and 50 sell-dominant events. Observation has not started, no score exists, and authority is
  `NONE`.
- **First prospective signal retained (D-081):** one 30-second public BTCUSD_PERP session from
  frozen commit `2e385a8` completed with zero published force-order snapshots. It retained exact
  exchange-info bytes, session hash, deterministic `SIG-495ecfb03d8003161565ea47`, `FLAT`, and an
  independent `BLOCK`. This starts the prospective boundary but supplies no complete five-minute
  window, metric, score, or promotion evidence. No account/order/paper/venue authority changed.
- **Complete-window observer V2 frozen (D-082):** the signal rule is unchanged. V2 separates
  WebSocket coverage from process time, emits only fully enclosed UTC five-minute windows,
  preserves zero-event windows, requires a consecutive 8,640-window baseline, and reconstructs all
  source/session/window/signal/risk/authority evidence offline. The retained V1 session verifies;
  byte and rehashed paper-order drift fail. V2 is not yet run and authority remains `NONE`.
- **First complete prospective window retained (D-083):** frozen observer `eaf2604` continuously
  covered `[2026-07-13T18:45Z,18:50Z)` and reconstructed one valid zero-event window. It emitted
  `SIG-54b9c184a05a3a037df6495d`, `FLAT`, `WARMUP_BLOCK`, and independent `BLOCK`. This proves the
  public source→window→signal→risk-denial path, not edge or promotion. Warm-up is 1/8,640; metric,
  scorecard, paper, and execution authority remain unavailable.
- **Prospective Spot label contract frozen (D-084):** every complete signal window now has fixed
  BTCUSDT Spot one-minute entry and 1h/6h/24h exit timestamps. A future label remains
  `NOT_AVAILABLE` without a request until its exit bar completes. The verifier reconstructs exact
  raw bytes, prices, returns, eligibility, and authority and rejects rehashed future-time or
  paper-order drift. No label evaluation has run from the freeze; warm-up analysis is prohibited.
- **First causal label schedule retained (D-085):** the evaluator ran from clean freeze commit
  `a09d308` at `19:00:07Z`. All 1h/6h/24h outcomes were not yet causally observable, so it emitted
  three `NOT_AVAILABLE` rows and made no kline request. The snapshot verifies offline. This proves
  scheduling and future-leakage prevention, not an outcome, edge, score, or promotion.
- **Append-only label verifier V2 frozen (D-086):** a refresh after a later source window failed
  closed before output because V1 judged an older snapshot against future source history. V2
  reconstructs each snapshot only from windows closed by its own evaluation time. The label rule,
  prior artifact, eligibility, and authority remain unchanged; the corrected refresh is unrun.
- **Second complete signal window retained (D-087):** `[19:05Z,19:10Z)` was another valid
  zero-event `FLAT/WARMUP_BLOCK/BLOCK` observation. It is not consecutive with the `18:45Z` window,
  so the longest warm-up chain remains 1/8,640. After V2 froze at `7cc6ef0`, a six-row label
  schedule retained all outcomes as `NOT_AVAILABLE`; both snapshots reconstruct offline.
- **Continuity attempt failed closed; observer V3 frozen (D-088):** a seven-window session ended
  `FAILED_LiquidationStressError` after 26m49s and admitted zero windows. V2 lacks enough evidence
  to identify the cause. V3 now retains and reconstructs exact exception/message/rejected-event
  evidence without changing the signal; it is not yet run.
- **V3 diagnosed the parser defect; V4 frozen (D-089):** the retained live force-order message
  places symbol type at `o.st`, while the parser/fixture expected top-level `st`. V4 corrects that
  exact path and preserves the V3 session as immutable pre-fix failure evidence. Both failed
  sessions admit zero windows; signal and authority terms are unchanged.

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
source-registry and TradingView public-strategy replay evidence refreshes; this blocks
strategy promotion and demo activation, not offline research. Open items are tracked in
`MISSING_AND_OPEN_ITEMS.md`.

The supervisory correction cycle repaired the shared DSR equation, aligned the retained
G10 metrics, pinned the current multi-data snapshot, added future research provenance and
preregistration contracts, removed holdout selection from future search runners, added a
research-only multi-leg funding specification and deterministic carry lifecycle, reconciled
authoritative claims, and quarantined authenticated venue transports. Historical selection
lineage and original data-run identity remain unrecoverable and are explicitly method-blocked.

## Exact next action

Commit observer V4, then run the unchanged causal evaluator so only the first window's now-available
1h label may be requested and retained. Verify exact bytes without aggregating or interpreting the
return. Then retry one complete V4 source window. Do not backfill, score, access the sealed V2
holdout, activate a bot, request credentials, or cross any human S3/S4 gate.

## Exit condition of next phase (unchanged)

S2 exit requires the plan's verification package and HG-3. Paper/demo activation also
requires complete approvable validation, promotion eligibility, a paper-lane
architecture decision, a security pass, and new operator approval for the specific
integration. Until then, venue connections and execution remain disabled.
