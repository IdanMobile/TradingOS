# Trading Intelligence OS — Missing and Open Items

Last updated: 2026-07-11

## Open research gaps (tracked in detail in `research/RESEARCH_GAP_MATRIX.md`)

- RG-05 public-source venue availability slice is complete for the authorized
  2026-07-11 recheck. Human/account-specific venue eligibility, permissions,
  terms, product availability, and fee-tier checks remain before S3 paper venue
  selection.
- RG-07 is closed for production activation (2026-07-11): candidate-specific G10
  PBO/DSR with independent recomputation ran on the retained trial populations and
  FAILED all families (`artifacts/validation/G10_CANDIDATE_EVIDENCE_2026_07_11.json`).
  Remaining slice: stats-specialist review before honoring any future G10 PASS.

## Current environment/coverage constraints

- BTC-only B2 Freqtrade/Hummingbot parity remains non-identical but is explained and
  retained as execution/order-state plus missing-data behavior; it is not a P&L fixture.

Docker was made available on 2026-07-11. LEAN bounded local Docker execution is
now retained for B1-B4 x `{F0/S0,F1/S1}` with one B1 F0/S0 determinism rerun.
Evidence: `artifacts/bakeoff/lean/STATUS.md`.
Hummingbot full-history follow-up is now runtime/throughput blocked: B2 BTCUSDT
F1/S1 consumed CPU but hit the lane's initial 1800 second timeout without
`raw.json`, and a cached full-history retry still hit the 3600 second timeout
while writing a clean timeout manifest and stopping the named container. Evidence:
`artifacts/reports/HUMMINGBOT_FULL_HISTORY_TIMEOUT_2026_07_11.md`.
The bounded Hummingbot capability/regression lane is now complete: BTCUSDT 30-day
B1-B4 x `{F0/S0,F1/S1}` x `{run1,run2}` completed, normalized, fee-audited, and
byte-deterministic. Evidence:
`artifacts/reports/HUMMINGBOT_PRODUCTIONIZATION_STEP_2026_07_11.md`.
NautilusTrader remains bounded-window evidence; full-history parity and latency/fill
evidence remain open. Deferred adapters and normalized artifacts are retained as
evidence-only/deferred assets under D-037.

## Resolved architecture decisions (2026-07-11)

- **T-002-05: RESOLVED by D-038.** The operator approved keeping the single audited
  loopback `POST /api/v1/workspace-actions/decision` route as a narrowly scoped
  clarification, not broad write-API approval. AD §AI and
  `docs/architecture/TYPE_AND_CONTRACT_CATALOG.md` §7 now record the exception and its
  binding constraints; any expansion requires a new decision gate. Evidence: D-038,
  `artifacts/reports/AD_IMPLEMENTATION_GAP_AUDIT_2026_07_11.md`.

## Open S2 evidence and exit items

0. Repo-wide open-marker audit is retained at
   `artifacts/reports/OPEN_MARKERS_AUDIT_2026_07_11.md`. Stale architecture/report
   wording for bounded LEAN/Hummingbot evidence was reconciled; remaining markers are
   classified as throughput/scope tracks, validation blockers, or human/credential/S3
   gates. The supervised Hummingbot full-history retry is now closed as a
   documented throughput timeout, not an active running job.
0a. Agent-executable product/platform inventory is now exhausted for the current
    constrained S2 scope. Live `/api/v1/status` projects 0 actionable open tasks,
    7 gated tasks, and 4 recurring tasks. Evidence:
    `artifacts/reports/AGENT_EXECUTABLE_COMPLETION_AUDIT_2026_07_11.md`.
1. Real retained Research Lab evidence now exists: LAB-799 completed and the persisted
   jobs/dashboard projection show three succeeded `RESEARCH_LAB_V0` jobs plus the
   six-hour offline schedule. Continue the next S2 evidence cycle from the recorded
   blockers; do not treat the batch or scheduler as strategy approval. Follow-on
   seed cycles now retain 258 trials for five reproduced seed candidates across
   BTCUSDT/ETHUSDT x 5m/15m/1h. The lower-frequency A/B produced positive proxy
   rows, led by QC2 Donchian ETHUSDT 1h window=40 (+149.1%), but no candidate is
   validated or eligible. Evidence:
   `artifacts/reports/SEED_CYCLE_MULTI_GRID_REPORT_2026_07_11.md`.
   A 2026-07-11 refresh after G10 fixture evidence
   produced `LAB-f99dcc214f377ecca4710bbb41d445c8331d2a1b06f93931ed1c88bdf3af5924`,
   again with 66 trials, no winner, and `execution_authority=NONE`.
2. Strategy validation remains `INCOMPLETE_NOT_APPROVABLE`: B2 is rejected for paper,
   G4 remains WARN, and production G10 now returns an evidence-backed **FAIL**
   (candidate-specific PBO/DSR with independent recomputation; B2 PBO 0.8685,
   DSR≈0). The multiple-testing dimension is no longer BLOCKED — it is FAIL in
   `LAB-73ebd3a3bb3e4086b2408552559e77a26d1334ae9cc789c4459beadc27b6844a`.
3. The research-lab `cross_engine_reproduction` dimension is closed
   PASS_WITH_SCOPE_NOTE (2026-07-11): three-way B2 signal reproduction with 99.904%
   event-lane reconciliation; fill/P&L parity is NOT claimed. Remaining Hummingbot
   full-history and NautilusTrader full-history/latency gaps stay open as
   throughput/scope tracks; retained two-pair order-state divergences remain
   explained parity evidence. Evidence:
   `artifacts/validation/CROSS_ENGINE_REPRODUCTION_2026_07_11.json`.
4. S2 exit/HG-3 remains blocked: the verification package is retained, but the
   requirement audit says not to prepare HG-3 because no strategy is complete,
   approvable, or promotion-eligible.
5. Seed validation-probe evidence is now retained in
   `artifacts/validation/seed_candidates/SEED_VALIDATION_PROBE_2026_07_11.json`.
   QC2 ETHUSDT 1h window=40 is the only positive proxy context that remains
   positive across chronological thirds and beats buy-and-hold under normal fees,
   but it is parameter-fragile and now fails seed-context G10
   (`SEED_G10_QC2_ETHUSDT_1H_2026_07_11.json`: PBO 0.2614, DSR 0.7564 < 0.95).
   Next agent-executable work is failure confirmation/cross-engine reproduction or a
   D-039 AI decision to move to new source-family ingestion.
6. New source-family ingestion has begun in read-only form. The primary research
   source registry now includes four external source classes — Binance Trading Bots,
   Binance Copy Trading, TradingView Ideas, and 3Commas DCA Bot — all as
   `hypothesis_only`, non-reproduced, non-eligible records with no copy/credential/
   venue/order authority. `EXTERNAL_SOURCE_INTAKE_PLANS_V1.yaml` also records one
   validated offline capture/replay plan per source and the dashboard read model
   exposes the plan counts. Metadata-only snapshots are retained under
   `artifacts/source_intake/`, with first public-source fields filled from
   `EXTERNAL_SOURCE_PUBLIC_CAPTURE_V1.yaml`. `EXTERNAL_REPLAY_HYPOTHESES_V1.yaml`
   now records four non-eligible replay hypotheses, including one copy-trading
   `non_reconstructable` row. The 3Commas DCA hypothesis is specified as the first
   canonical non-executing external replay candidate under
   `strategies/external/3commas-dca-config/`. The first local-only DCA replay is now
   retained at
   `artifacts/external_replay/3commas_dca/EXTDCA-9ed0a866cc1ddb5f7f4e7a94b5c5e48b/`
   with 6 frozen-data trials and 43,738 simulated events. It remains
   `UNVALIDATED`, non-eligible, and `execution_authority=NONE`; no platform bot,
   account, paper/demo/live venue, credential, or order route was used. Evidence:
   `artifacts/reports/EXTERNAL_SOURCE_INTAKE_SEED_2026_07_11.md`. Remaining
   agent-executable work is to open a new external source-family replay seed or build
   normal validation/cross-engine evidence only if a DCA variant survives first-pass
   replay; this is not execution.
7. TradingView public-strategy intake has advanced from metadata selection to a first
   local-only replay for the two candidates whose public pages supplied enough
   explicit rules: RSI mean reversion and Bollinger/ATR/EMA. Evidence:
   `artifacts/external_replay/tradingview_public_strategies/TVPINE-9f7d3fc15ece2785a4296e9eb3b15548/`.
   The run retained 12 frozen-data trials and 57,046 local events, but remains
   `UNVALIDATED`, non-eligible, and `execution_authority=NONE`. Remaining work is
   exact Pine source/body hash capture where lawful, complete TradingView Strategy
   Tester export capture, divergence reporting, cross-engine reproduction, and normal
   validation only if a candidate survives first-pass evidence.

## Resolved authorized decision slices (2026-07-11)

- `T-001-03` official-source Kraken/Coinbase Israel availability recheck is
  retained in `artifacts/reports/VENUE_ISRAEL_SOURCE_RECHECK_2026_07_11.md`.
  Kraken is not demoted on the checked public-source evidence; Coinbase has
  Israel identity-document support, but exact account/product/API eligibility is
  still human/S3-gated.
- `T-020-01`/`T-020-02`/`T-020-03` design-only expansion work is retained in
  `artifacts/reports/FUTURE_MARKET_EXPANSION_DESIGN_REVIEW_2026_07_11.md`.
  Implementation remains deferred to S3+.
- `T-017-05` was rechecked after an operator decision, but credentials are not
  visible in the current environment. Evidence:
  `artifacts/reports/AI_COST_TELEMETRY_CREDENTIAL_RECHECK_2026_07_11.md`.
- Future exchange/data-provider intake prep is retained in
  `artifacts/reports/OPERATOR_ACCESS_PREP_CHECKLIST_2026_07_11.md`. It reserves
  inactive `.env.example` names for candidate exchanges and market-data vendors,
  but does not request or enable any credential, connection, order route, paper/demo
  venue, live trading, or real-money capability.
- AD §U now explicitly includes exchange-hosted bot marketplaces, copy-trading/
  copy-investing records, online signal feeds, public leaderboards, and third-party
  bot platforms as future strategy/source inputs to the lab. This is a development
  requirement for the full Trading OS, not current execution authority; each source
  still enters as untrusted hypothesis/replay material.

## Resolved bounded S2 research-asset evidence

- ResearchAsset registry/backfill for the bounded S2 slice is implemented and tested:
  `research/RESEARCH_ASSETS_V1.json` contains 8 retained RA records with freshness,
  dependencies, consumers, human-review flags, reverify triggers, and existing
  source/quality evidence refs. `ResearchAssetRegistry` enforces invalid-without-evidence,
  duplicate/unknown/cyclic graph rejection, freshness filtering, and deterministic digest.
  Evidence: `src/tios/research_assets/assets.py` and `tests/test_research_assets.py`.
- RA cost amortization is queryable from the same registry via consumer counts and
  cost-per-consumer projection. Current retained local evidence has zero external cost.

## Resolved bounded S2 observability evidence

- Bounded S2 observability is complete without a general stack: JSON artifacts, SQLite
  job rows, environment mode fields, and dashboard read models are the structured
  operational records. Prometheus/Grafana and OTel are rejected for the current
  single-operator local lab; AI cost telemetry stays credential-gated. Evidence:
  `artifacts/reports/OBSERVABILITY_BOUNDARY_REPORT.md`.

## Resolved bounded S2 dictionary/ontology evidence

- Bounded dictionary/ontology seed is implemented and tested: `research/DICTIONARY_CONCEPTS_V1.json`
  contains 16 `CON-*` concepts covering S1/S2 evidence vocabulary, FIBO URI provenance
  where applicable, local project-contract definitions, and explicit gap rows for full
  FIBO import, venue-specific meanings, and scraped definitions. `ConceptRegistry`
  validates graph/source integrity, rejects embedded strategy parameter values, and
  exposes SQLite FTS5 search. Evidence: `src/tios/knowledge/concepts.py` and
  `tests/test_dictionary_concepts.py`.
- The dashboard projects the same concept registry through a read-only Dictionary view,
  closing the bounded global-search slice without adding a write path.

## Resolved bounded S2 dashboard backlog evidence

- The bounded dashboard backlog is closed for the current S2 scope: the full console
  rewrite, entity-detail layout, and richer comparisons UI are rejected until documented
  reopen triggers occur; global search is done through the Dictionary view; approvals UI
  remains human-gated and unauthorized. Evidence:
  `artifacts/reports/DASHBOARD_BOUNDARY_REPORT.md`.
- The inert trading-domain product surface is now projected in the dashboard:
  orders, positions, portfolio, risk, and the future demo-wallet rail are visible as
  read-only contracts, while all execution/account/synthetic-wallet capabilities are
  absent or disabled. This closes the agent-executable S2 UI slice for typed trading
  projections without crossing into S3 paper/demo implementation.
- The future demo-wallet rail now includes a design-only readiness projection:
  no ledger, no synthetic capital, no mutation API, no order route, no venue
  connection, and `execution_authority=NONE`. It lists the required future gates,
  allowed isolated-simulation scope, and prohibited credential/venue/real-money
  ingredients so future agents can continue from the decision record without
  activating demo/paper infrastructure in S2.
- S3/S4 gate readiness is now projected as read-only Trading Domain evidence:
  S3 paper/demo and S4 live are both `NOT_READY`, with blocked predicates and next
  human actions visible. This is product continuity only; it does not authorize or
  implement paper/demo/live execution.
- `GET /api/v1/stage-gates` now exposes the same blocked S3/S4 gate chain as a
  standalone read-only machine contract. It has no write, transition, order, venue,
  credential, demo/paper, or live control.
- S3/S4 inert control-plane contracts are implemented and tested in
  `tios.trading_domain`: stage-gate readiness records, requirement rows, synthetic-local
  paper-lane proposals, backtest-versus-paper divergence reports, and limited-live
  readiness proposals. They are future evidence records only; venue demo/testnet
  proposal construction is rejected before credential gates, and all records retain
  `execution_authority=NONE` with paper/live orders disabled. The dashboard shows the
  contracts as `MODELED_INERT` and active record counts remain zero.
- The S3/S4 control-plane readiness artifact is retained at
  `artifacts/reports/S3_S4_CONTROL_PLANE_READINESS_2026_07_11.{json,md}`. It validates
  probe-only S3/S4 records and exposes the remaining blockers to the dashboard without
  creating active stage-gate, paper-lane, divergence, or live-readiness records.
- S3/S4 operational-drill records are implemented as inert contracts for feed loss,
  stale data, engine crash, manual kill switch, and credential revocation. The retained
  readiness artifact includes PASS/BLOCKED probe rows, but no active drill record or
  execution control exists before S3/S4 gates.
- Synthetic demo-ledger contracts are implemented for future mock-money wallet
  accounting. The retained readiness artifact includes a probe ledger with initial
  capital and fee debit, but no active synthetic ledger, wallet mutation, order route,
  venue connection, or real-money capability exists before S3 gates.
- Synthetic paper-fill policy contracts are implemented for future local demo/paper
  reconciliation. The retained readiness artifact includes a deterministic fill-policy
  probe, but no active paper fill policy, fill engine, wallet mutation, order route,
  venue connection, or real-money capability exists before S3 gates.
- Synthetic account/portfolio snapshot contracts are implemented for future
  mock-money demo projections. The retained readiness artifact includes probe account
  and portfolio snapshots linked to the synthetic ledger, but no active synthetic
  account, portfolio, wallet mutation, order route, venue connection, or real-money
  capability exists before S3 gates.
- Synthetic runtime-risk policy contracts are implemented for future demo/paper
  limits. The retained readiness artifact includes a probe policy for capital,
  position, daily-loss, drawdown, and kill-switch mode, but no active risk engine,
  wallet mutation, order route, venue connection, or real-money capability exists
  before S3 gates.
- Synthetic portfolio-risk policy contracts are implemented for future demo/paper
  caps. The retained readiness artifact includes a probe policy for symbol
  concentration, correlated exposure, strategy budget, and open-position count, but
  no active risk engine, wallet mutation, order route, venue connection, or
  real-money capability exists before S3 gates.
- Synthetic per-strategy budget and market-condition guard contracts plus a pure
  independent risk evaluator are implemented. The evaluator can only produce
  evidence-backed PASS/BLOCK records; it checks capital, notional, daily loss,
  drawdown, exposure, strategy allocation, stale data, spread, venue health,
  timestamp order, and kill-switch state without routing or mutating anything.
  Synthetic ledger snapshots now enforce arithmetic conservation and reject
  overdrafts. Active risk policies and ledgers remain zero before S3 gates.
- Pure synthetic execution reducers are implemented for deterministic fill pricing,
  fee/slippage treatment, idempotent ledger replay, insufficient-funds rejection,
  fee-aware long-only position P&L, and ledger-backed account/portfolio equity.
  Canonical rule/signal evaluation emits transition-only evidence and now implements
  the distinct TradingView and pandas-ta/Hummingbot Supertrend direction conventions,
  including Hummingbot's proximity gate. Independent external known-answer comparison
  remains evidence work, not a semantic or implementation blocker. No reducer exposes
  an order route or state-mutation API.
- Signed P&L, computed divergence/stability, limited-live cross-record validation,
  and operational incident lifecycle are implemented. Losing positions retain signed
  realized/unrealized values without weakening nonnegative cash/fee/limit contracts.
  Paper stability is derived from heartbeat cadence, incidents, duration, and
  divergence; future limited-live readiness resolves all linked policies and drills.
  Incident records require ownership, ordered acknowledgement/resolution, and
  post-incident evidence. All remain inactive before gates.
- Paper-stability PASS records now require the declared observation duration, full
  recorded uptime, and zero incidents/missed heartbeats. S4 readiness records require
  the complete named prerequisite chain, and the dashboard fails closed when the
  retained readiness artifact hash is invalid.
- Restricted credential boundary contracts are implemented for future S4 scope
  control without secret material. The retained readiness artifact includes a probe
  policy with funds movement forbidden, but no active credential policy, credential
  value, venue connection, order route, or real-money capability exists before gates.
- Paper operations runbook contracts are implemented for future S3 paper/demo
  operational discipline. The retained readiness artifact includes a probe runbook
  for heartbeat cadence, timeout, log retention, and intervention mode, but no active
  runbook, venue connection, order route, or real-money capability exists before gates.
- Paper operations event-log contracts are implemented for future S3 paper/demo
  evidence rows. The retained readiness artifact includes a heartbeat event probe,
  but no active operations event log, venue connection, order route, or real-money
  capability exists before gates.
- Paper stability report contracts are implemented for future S3 exit evidence. The
  retained readiness artifact includes a blocked stability-window probe, but no active
  paper stability report, venue connection, order route, or real-money capability
  exists before gates.
- Limited live risk-package contracts are implemented for future S4 readiness. The
  retained readiness artifact includes a blocked package probe linked to paper
  stability, credential policy, operations runbook, and runtime risk policy, but no
  active live risk package, venue connection, order route, or real-money capability
  exists before gates.
- Live operations runbook contracts are implemented for future S4 operational
  discipline. The retained readiness artifact includes a probe runbook for heartbeat,
  incident response, log retention, and escalation mode, but no active live runbook,
  venue connection, order route, or real-money capability exists before gates.
- Live operations event-log contracts are implemented for future S4 operational
  evidence. The retained readiness artifact includes a heartbeat probe linked to the
  live runbook and limited-live risk package, but no active live event log,
  credential access, venue connection, order route, or real-money capability exists
  before gates.
- TradingView open-source public strategies and Strategy Tester summaries are now a
  first-class external-source intake lane, separate from prose TradingView Ideas:
  the registry captures license/attribution, source visibility, parameters, tester
  assumptions, and metrics as external comparison evidence only. Local OS reproduction,
  divergence analysis, G10, and normal validation gates remain mandatory before S3.
- The first TradingView public-strategy candidate batch is selected and retained with
  eight metadata-only URLs/families. Remaining executable work is per-candidate
  capture of Pine source hashes, license/attribution notes, Strategy Tester settings
  and metrics, followed by local OS reproduction; the retained selection itself
  does not validate or approve any strategy.
- The broader local discovery surface is now projected in the dashboard:
  `GET /api/v1/search` and the Search view cover concepts, research assets, source
  records, strategies, and retained reports. This closes the roadmap's bounded
  registry/report search slice as a read-only projection; no write, credential, venue,
  order, or execution capability is exposed.
- The bounded comparison surface is now projected in the dashboard:
  retained lab scorecards, validation gates, production G10 rows, seed probe evidence,
  seed G10, cross-engine scope notes, and evidence refs are visible side by side. This
  closes the agent-executable S2 comparison UI slice without selecting a winner or
  exposing approval, job, credential, venue, paper/demo/live, or order controls.

## Resolved AI provider source re-check evidence

- RG-08 is closed for pre-paid-benchmark planning: official OpenAI and Google AI
  Developers sources now capture GPT-5.6 pricing, Gemini 3.x context/pricing, and Google
  model deprecation handling. Real-provider runs remain credential/spend/human-review
  gated. Evidence: `artifacts/reports/AI_PROVIDER_SOURCE_RECHECK_2026_07_10.md`.

## Resolved S2 verification evidence

- Clean-checkout/restore/replay evidence now passes for DVC fresh-checkout replay,
  MLflow artifact restore, SQLite jobs DB logical backup/restore, retained artifact
  hash restore, LAB-799 no-winner status, and validation non-approvability. Evidence:
  `artifacts/reports/S2_RESTORE_REPLAY_REPORT.md` and
  `artifacts/quality/s2_restore_replay.json`.
- S2 live-unreachability evidence passes. Evidence:
  `artifacts/reports/S2_LIVE_UNREACHABILITY_REPORT.md`.
- S2 requirement audit is complete and blocks exit/HG-3 on evidence grounds. Evidence:
  `artifacts/reports/S2_REQUIREMENT_AUDIT.md`.
- Durable local evidence retention and gated approval history are implemented but
  inactive. The confined append-only SQLite store provides canonical hashes,
  idempotency, concurrent-writer serialization, bounded reads, and integrity checks;
  typed human decisions expire and exact S3/S4 predicates are enforced. Active
  evidence/approval counts remain zero and no scheduler, HTTP mutation, credential,
  venue, wallet, or order route is enabled.

## Human-only before live trading

1. Exact Israel/operator account eligibility for selected venue.
2. Exact product availability in operator account.
3. API trading permissions.
4. Current automated-trading terms.
5. Current fee tier.
6. Funding/deposit/withdrawal path.
7. Credential isolation and revocation process.
8. Capital amount and maximum acceptable drawdown.
9. Tax/accounting workflow.
10. Final human approval.

## Deferred until justified

- paid tick/order-book data purchase;
- perpetual futures;
- leverage;
- US stocks/ETFs;
- on-chain data;
- social sentiment;
- news vendor selection;
- portfolio optimizer;
- full risk engine;
- mass strategy scraping;
- production deployment;
- autonomous AI trade path;
- full ontology ingestion;
- final 27-page dashboard implementation.

## Credential- and human-gated AI work

- T-011-05 (AI benchmark first real runs) is deferred: no `ANTHROPIC_API_KEY` /
  `OPENAI_API_KEY` / `GOOGLE_API_KEY` is configured in this environment
  (rechecked 2026-07-11 without printing values; intake gate's "add later" AI-key
  disposition still holds). T-011-01..04 and
  T-011-06 are complete on the null provider; see
  `artifacts/reports/AI_BENCHMARK_SEED_REPORT.md`. Unblock by configuring one
  provider credential, then run controlled-mode Mode A per
  `benchmarks/ai_agent/FROZEN_BENCHMARK_SUITE_V1.md`.
- Judge calibration set (`benchmarks/ai_agent/calibration/calibration_set.json`)
  is frozen but `review_status: PENDING_HUMAN_REVIEW` — needs an operator to
  review samples and record `reviewer`/`reviewed_at` (T-011-04 human-approval
  requirement).

## Current non-recurring blocked task inventory

- Credential-gated: `T-011-05` first real AI benchmark runs; `T-017-05` AI cost
  telemetry.
- S3-gated: `T-015-01` paper-lane architecture decision, `T-015-02` paper deployment,
  `T-015-03` backtest-vs-paper divergence tracking, `T-015-04` operational drills.
- S4/human-gated: `T-015-05` human-only venue gates package.

## Re-verification required

Before S3/S4 implementation or live use recheck:
- exchange APIs and changelogs;
- provider model versions/pricing;
- data provider pricing/licensing;
- engine versions/deprecations;
- venue fees;
- account eligibility.
