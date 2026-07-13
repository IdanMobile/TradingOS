# Trading Intelligence OS — Missing and Open Items

Last updated: 2026-07-13

## Supervisory corrective items (2026-07-13)

The authoritative finding register and acceptance criteria are in
`docs/supervisor/IMPROVEMENT_PLAN_2026-07-13.md`. The highest-priority open work is:

- **SUP-001 / SUP-003 — CRITICAL:** authenticated Bybit demo scripts were used without
  the recorded HG-3, HG-4, security, validation, and venue approvals required by the
  locked architecture. All outbound transports are now quarantined under D-046;
  historical demo records are evidence of an out-of-architecture governance probe,
  not current execution capability or approval.
- **SUP-002 / SUP-005 — HIGH:** DSR was corrected under D-045 and affected evidence
  was regenerated. Per-bar Sharpe is aligned across selection/PBO/DSR and family-scope
  effective trials use retained correlations where defined. Canonical V2 now retains all
  67 B2/B3/B4 trials, six cost cells, five chronological folds, and campaign-wide inputs,
  but upstream selection hierarchy and hierarchy-wide dependence evidence were not retained.
  No G10 PASS is promotion-eligible until the complete hierarchy is defensible.
- **SUP-004 — HIGH:** funding/carry evidence lacks a complete capital, collateral,
  re-hedging, settlement, liquidation, missing-data, and survivorship model. Static
  fee/slippage stress is not empirical paper divergence and does not satisfy G12.
- **SUP-006 through SUP-010 — HIGH/MEDIUM:** expanded-data provenance, immutable
  manifests, public-strategy holdout discipline, stat-arb methodology, canonical-spec
  coverage, survivor/cost controls, and research-source claim strength remain open.

Bounded corrective progress: future raw/REST provenance and a deterministic current
normalized snapshot are implemented; future public/signal/universe searches select on train
only; and funding carry has a pinned non-executable canonical registration. Historical REST
payloads/original normalization identity, exact public-source/spec identity, one globally
frozen candidate, hierarchy-wide effective trials, schema support for ranking/MTF/composition,
and a complete integrated funding lifecycle/risk model remain open. Research-only multi-leg
identity and deterministic open/settle/rehedge/close accounting fixtures now exist but create
no execution path. The bounded 66-trial baseline G10 reproduction completed under the
fail-closed provenance contract: B2/B4 fail, B3 is method-blocked, and no result is promotable.
The separate canonical V2 campaign also completed: exact next-open semantics and realistic
costs make B2/B4 decisive failures, while B3/campaign-wide select an inert zero-trade variant
and remain method-blocked. Its 66-source portable data restoration and byte-identical rerun
pass. A pre-freeze implementation smoke is disclosed; the only prospective evidence is the
sealed 2026-07-14 through at-least-2027-01-14 holdout.

These corrective items supersede any earlier statement that all agent-executable work
is exhausted. They grant no credential, venue, order, paper, demo, or live authority.

## Post-V2 family-selection and campaign gate (D-052/D-053)

`FAMILY-SELECT-V1` ended `NO_GO` after comparing exactly funding/basis carry,
long-only Spot cross-sectional momentum, and volatility-managed Spot exposure. Carry
still lacks authoritative historical margin/liquidation/contract/counterparty semantics;
cross-sectional momentum lacks a delisting-complete point-in-time universe, canonical
ranking/portfolio ownership, and clean search lineage; volatility management lacks clean
lineage and canonical dynamic-sizing ownership and has material primary-literature
OOS/cost counterevidence. Evidence:
`research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V1.md`.

`FAMILY-SELECT-V2` then compared UTC-weekday exposure, stablecoin below-peg reversion,
and Bitcoin-halving exposure. D-053 admits only `FAM-CALENDAR-UTC-01` to the frozen,
unrun `CALENDAR-UTC-G1-G11-V1` offline campaign. Its exact data package, seven immutable
weekday versions, Decimal reference, vectorbt accelerator, costs, chronology, thresholds,
and stop rules are preregistered. This closes the Task 1/2 admission and data-package gaps;
it does not close G1-G11, cross-engine certification, specialist review, promotion, or any
bot/venue/authority gate.

The frozen campaign has now completed and is rejected under D-054. Wednesday was positive at
F1/S1 in 2024 and the nominal reserve, but failed hard-stress economics, drawdown, benchmark,
and G10 gates. The reserve computation order violated its select-before-read protocol, and full
Freqtrade/Nautilus conformance was not run. The exact calendar family/context is closed without
rescue. A new distinct-family cycle and genuinely unseen evidence are required before another
StrategyVersion can seek validation.

D-055 completes that new source/data admission cycle without observing family performance.
Funding pressure advances only as a timestamped exogenous feature for unlevered BTCUSDT Spot
long/cash. Its 66 funding archives and exact Spot package are frozen and verified offline. The
canonical strategy, independent engines, explicit selection-artifact barrier, campaign freeze,
and all G1-G11 outcomes remain open; the family is not validated or promotion-eligible.

D-056 closes the canonical/implementation/freeze portion: the exact 12-version campaign passes
offline preflight and synthetic causal/parity goldens, and phase two fails without a hashed
development selection artifact. Historical scoring and independent G11 review remain open. The
family is still unvalidated and no bot, paper/demo/live state, or venue authority exists.

V1 then aborted operationally before selection because an external worker lacked the repository
root on its import path. D-057 closes V1 without a strategy verdict and freezes V2 with only that
bootstrap repaired. Validation/reserve remain untouched; V2 execution and G1-G11 remain open.

V3 subsequently completed and is rejected under D-059. The verified selection barrier does not
rescue zero validation trades, a losing two-trade reserve, failed DSR, or the Nautilus parity
residual. The exact directional funding-pressure context is closed; a distinct family and new
unseen evidence are required.

D-060 completes a new source/data admission cycle without scoring. Finalized Bitcoin L1
transaction-count shocks advance with exact retained bytes, a two-day lag, gap quarantine, and a
12-trial pulse roster. Canonical implementations, the two-phase campaign, all G1-G11 outcomes,
and independent supervision remain open; no strategy is yet validated.

D-061 and D-062 close that work. The immutable campaign selected HIGH/56/1-day in development,
four-role parity passed, and the selection barrier held, but validation, reserve, full, stress,
delay, regime, drawdown, benchmark, and DSR evidence failed. The exact family is rejected without
rescue. A new distinct source-only family cycle is required; no strategy is validated and no bot,
paper/demo/live state, venue, or execution authority exists.

D-063 admits a distinct Bitcoin MVRV dislocation family without scoring. The official no-key
metric/catalog snapshot, original-body and tracked archival hashes, 2,189 positive daily values,
zero gaps, two-day lag, strict Spot mapping, and 12-trial roster pass offline verification.
Canonical implementations, immutable campaign, G1-G11 evidence, and independent supervision
remain open; no strategy is validated.

D-064 closes canonical/campaign construction. All 12 immutable versions, four roles, cost cells,
selection barrier, gates, and safety constraints pass offline preflight. The single governed
historical run and independent G11 disposition remain open; no strategy is validated.

D-065 closes the campaign negative. The selection barrier and four-role parity passed, but both
OOS segments, stress, delay, reserve trade count, regime, drawdown, benchmark, PBO, and DSR gates
failed. The exact MVRV pulse family is rejected without rescue; a genuinely distinct mechanism is
required and no strategy is validated.

D-066 and D-067 admit and freeze a genuinely distinct regulated-futures-positioning family without
scoring. Exact CFTC API/metadata/schedule bytes, full-size Bitcoin row identity, 30 publication
exceptions, 33 official-checksum early Spot archives, 72,225 combined bars, 25 retained gaps, and
428 strict-later mappings pass offline verification. Canonical implementations, campaign freeze,
G1-G11 evidence, and supervision remain open; no strategy or bot is approved.

D-068 closes canonical/campaign construction. All 12 immutable StrategyVersions, four roles, six
cost cells, seven regime periods, strict development-selection barrier, G1-G11 thresholds, and
no-rescue constraints pass offline preflight. The single clean historical run and independent G11
disposition remain open; no strategy or bot is approved.

D-069 closes the CFTC positioning family after the clean campaign run. G1-G4 pass, but negative
validation, insufficient development/reserve sample, 63.35% drawdown, four-of-seven positive
periods, inferior benchmark Sharpe, PBO 0.5578, and DSR 0.3493 cause G5-G11 rejection. No strategy
or bot is approved; the next distinct family comparison remains open.

D-070 admits only Binance Spot completed-hour taker imbalance from a source-only comparison of
three new mechanisms. The exact 12-trial roster and causal boundary are preregistered without local
performance. Dedicated data verification, canonical roles, campaign freeze, G1-G11 evidence, and
supervision remain open; no strategy or bot is approved.

D-071 closes the exact data boundary: 72,225 rows, 72,221 valid features, four quarantined rows, 25
gaps, and 72,220 strict post-close mappings pass offline verification. Canonical roles, campaign
freeze, G1-G11 evidence, and supervision remain open; no strategy or bot is approved.

D-072 closes canonical/campaign construction. All 12 immutable StrategyVersions, four roles, six
cost cells, seven periods, causal goldens, strict development-selection barrier, and G1-G11
thresholds pass offline preflight. The single clean historical run and independent G11 disposition
remain open; no strategy or bot is approved.

D-073 closes V1 without a strategy verdict after a pre-selection CPU-bound runtime abort. V2
changes only mathematically equivalent reference computation and cost-independent event caching;
the clean V2 run and independent G11 disposition remain open. No strategy or bot is approved.

D-074 closes the Spot taker-imbalance family. Development, validation, reserve, stress, delay,
regime, drawdown, benchmark, DSR, and full-parity evidence fail; G11 rejects promotion without
rescue. No strategy or bot is approved; the next distinct family comparison remains open.

D-075 admits only a quote-normalized Coinbase-versus-Binance BTC premium from a source-only
comparison with U.S. Spot Bitcoin ETP flow and USDt peg stress. The exact 12-trial roster, causal
boundary, quote conversion, gaps, and no-rescue rules are preregistered without local performance.
Exact Coinbase data packaging, offline restoration, canonical roles, campaign freeze, G1-G11
evidence, and supervision remain open; no strategy or bot is approved.

D-076 closes the exact data boundary. A 10 MB content-addressed raw bundle preserves 382 public
Coinbase documentation/product/candle responses, and deterministic normalization yields 45,193
aligned rows, six gap events, and 45,192 strict-later mappings. Byte-identical rebuild and three
deliberate drift classes pass offline. Canonical roles, campaign freeze, G1-G11 evidence, and
supervision remain open; no strategy or bot is approved.

D-077 closes canonical/campaign construction. All 12 immutable StrategyVersions, four roles, six
cost cells, six period slices, causal goldens, strict development-selection barrier, and G1-G11
thresholds pass offline preflight. The single clean historical run and independent G11 disposition
remain open; no strategy or bot is approved.

D-078 closes the cross-venue premium family. Development, validation, reserve, stress, delay, all
six periods, drawdown, benchmark, and DSR evidence fail despite complete four-role parity. G11
rejects promotion without rescue. No strategy or bot is approved; a new distinct source-only family
comparison is required before another campaign.

D-079 completes that bounded comparison with `NO_GO`. Point-in-time exchange flows require
authenticated proprietary labels, the official BTC liquidation-snapshot archive is throttled and
stale, and complete CME curve data require entitlement plus derivative capital semantics. After
eight bounded selection cycles and no promotion-eligible completed campaign, another autonomous
public-family sweep is not an open task. Strategy validation remains open only to new exogenous
evidence: an operator-supplied fully sourced specification and unseen data, approved authoritative
data access, or genuinely prospective preregistered observations. No strategy or bot is approved.

D-080 opens only the prospective-evidence path. The BTCUSD_PERP liquidation-stress risk signal is
frozen before observation with a 30-day complete-window warm-up and a first-review boundary of at
least 180 days plus 50 sell-dominant stress events. Source continuity, future Spot labels, costs,
G1-G11, independent review, promotion, and every paper/demo/live gate remain open. The observer is
public-data-only and every emitted state is independently action-blocked.

D-081 starts the prospective boundary from frozen commit `2e385a8`. The first 30-second source
session completed with zero published snapshots and emitted deterministic `FLAT/BLOCK` signal
`SIG-495ecfb03d8003161565ea47`; both raw exchange info and the session are content-addressed. No
complete five-minute window exists yet. Deterministic aligned-window assembly/verification,
continuous coverage, warm-up, labels, statistical gates, and promotion remain open.

D-082 closes the aligned-window assembly/verifier implementation gap without changing the signal.
The retained V1 session reconstructs offline; byte drift and rehashed authority drift fail. One
complete-window public session is authorized only after the V2 freeze commit. Warm-up, labels,
review minima, G1-G11, promotion, and all execution gates remain open.

D-083 retains the first complete UTC five-minute window from frozen observer commit `eaf2604`.
Continuous coverage produced a valid zero-event window, deterministic
`SIG-54b9c184a05a3a037df6495d`, `FLAT`, and independent `BLOCK`; both sessions reconstruct offline.
Only 1 of 8,640 warm-up windows exists. Strictly-later Spot label capture, ongoing coverage, review
minima, scoring, G1-G11, and promotion remain open.

D-084 freezes the future-label boundary before evaluation. BTCUSDT Spot one-minute opens are
fixed at window-close-plus-one-minute entry and 1h/6h/24h exits; no request is allowed until each
exit candle completes. Exact raw bytes and derived labels must reconstruct, and deliberate
future-time and authority drift fail closed. The first causal evaluation, continued prospective
coverage, 8,639 warm-up windows, review minima, costs, G1-G11, and promotion remain open.

D-085 retains the first causal label snapshot from the clean D-084 freeze. All three horizons were
correctly `NOT_AVAILABLE`, so no kline request, price, or return exists. The 1h outcome first
becomes lawful at `2026-07-13T19:52Z`; 6h and 24h remain later. Causal outcome capture, continued
prospective coverage, warm-up, review minima, costs, G1-G11, and promotion remain open.

D-086 records a fail-closed label-refresh attempt after a later source window was added. No output
or future value was written. V2 fixes only snapshot-relative reconstruction so later append-only
windows cannot invalidate an older snapshot; every label and safety term is unchanged. A clean
post-freeze refresh, first available outcome, continuous warm-up, and all validation gates remain
open.

D-087 retains a second complete zero-event source window and a post-V2 six-row causal label
schedule. The two complete windows are separated by three unobserved windows, so the consecutive
warm-up chain remains one. Continuous capture, the first 1h outcome after `19:52Z`, 8,639 further
consecutive windows, review minima, costs, G1-G11, and promotion remain open.

D-088 retains a failed seven-window continuity attempt with zero admitted windows. The root cause
is unknown because V2 preserved only `LiquidationStressError`, not its message or rejected source
record. V3 freezes exact failure evidence and reconstruction without changing the signal. A clean
V3 capture, continuous warm-up, first available label, and every validation gate remain open.

D-089 uses V3 evidence to diagnose the source failure: the parser/fixture expected top-level `st`,
but the actual stream publishes `o.st`. V4 corrects only that schema path and preserves the V3
failure immutably. A clean V4 complete window, continuity, causal labels, warm-up, and all
validation/promotion gates remain open.

D-090 retains the first causally available 1h Spot label with exact raw bytes and arithmetic
reconstruction. It is one gross warm-up observation and is prohibited from aggregation,
interpretation, scoring, or promotion. A clean V4 complete source window, continuous warm-up,
remaining label horizons, review minima, costs, G1-G11, and strategy validation remain open.

D-091 retains a successful schema-4 complete window with `source_failure=null`, deterministic
`FLAT/BLOCK`, and a nine-row causal label schedule. Three complete windows exist but are isolated,
so continuous-operation evidence and warm-up remain open. The second window's 1h label first
becomes available at `2026-07-13T20:12Z`; all analysis and promotion gates remain closed.

D-092 retains another successful V4 window and the second causal 1h label. Four complete windows
remain isolated; two gross labels remain retain-only and unanalysed. Persistent continuity, 8,639
further consecutive windows, remaining horizons, review minima, costs, G1-G11, strategy approval,
and every bot/paper gate remain open.

D-093 freezes the only operating shape capable of building the consecutive baseline: atomic
per-window checkpoints on one continuous connection plus overlap-proven rotation before Binance's
documented 24-hour disconnect. V5 implementation, synthetic rotation/failure tests, a two-window
post-freeze run, 8,639 further consecutive windows, and all validation/promotion gates remain open.

D-094 freezes V5 after offline tests prove atomic multi-window checkpoints, preservation across a
mid-window disconnect, continuity reset after a gap, overlap-preserving planned rotation, heartbeat
authority rejection, and schema-5 reconstruction. The post-freeze two-window public proof, 8,638
additional consecutive warm-up windows after that proof, causal label maturity, review minima,
costs, G1-G11, strategy approval, and every bot/paper gate remain open.

D-095 passes the exact two-window public proof from the clean D-094 commit. Six complete windows
exist in total and the longest consecutive chain is two. Four 1h labels are retain-only and 14
scheduled rows are unavailable; none has been aggregated or interpreted. A fresh single-process
8,640-window warm-up run, actual planned 24-hour rotations, label maturity, review minima, costs,
G1-G11, strategy approval, and every bot/paper gate remain open.

D-096 freezes a TradingOS-native managed-observation boundary without weakening the offline jobs
worker. D-097 implements its immutable intent, fixed command, freshness/continuity projection,
dashboard visibility, and drift/failure tests; D-098 adopts the active run without restart.

D-097 implements and tests the managed service, fixed launcher, immutable intent, fail-closed
projection, and dashboard visibility. D-098 adopts the current D-095 process without restart and
verifies it `MANAGED / OBSERVING / FRESH` with no blockers or authority. Warm-up completion, real
rotation evidence, causal label maturity, statistical validation, and every promotion/paper gate
remain open.

D-099 implements the previously missing three-layer eligibility decision and corrects the risk
precondition's omission of G10. Read-only status/dashboard now projects the decision and exact
blocker classes. The current signal still lacks warm-up completion, eligible metrics, a governed
scorecard, G1-G11 evidence, and independent reviews; no platform score can substitute for those
facts.

D-100 maps every remaining prospective-signal blocker to an evidence producer and prevents the
8,640 observation samples from being mislabeled as trials. The association/overlay campaign's exact
metric conventions, declared comparison population, benchmarks, cost/opportunity model, and
selection rule remain to be preregistered before any lawful first-review calculation.

D-101 closes the system-plumbing gap from finalized checkpoint through a dedicated typed risk-state
signal and independently derived blocking risk decision to the verifier/dashboard. That slice is
deterministic and order-inert. It does not close the evidence gap: predictive association, eligible
metrics, campaign trials, G1-G11, independent reviews, and a separately validated alpha
StrategyVersion remain missing.

## Open research gaps (tracked in detail in `research/RESEARCH_GAP_MATRIX.md`)

- RG-05 public-source venue availability slice is complete for the authorized
  2026-07-11 recheck. Human/account-specific venue eligibility, permissions,
  terms, product availability, and fee-tier checks remain before S3 paper venue
  selection.
- RG-07 remains **METHOD_BLOCKED** (2026-07-13): candidate-specific G10 PBO/DSR
  was corrected and independently recomputed on retained family populations. B2/B4
  numerically fail, B3 cannot define trial correlations, and no family result can
  clear the gate because the upstream search hierarchy was not retained. The completed
  preregistered reproduction additionally proves the declared 66-trial scope but exposes
  legacy current-close/canonical-next-open semantic divergence. Evidence:
  `artifacts/reports/G10_PREREGISTERED_CAMPAIGN_REPORT_2026_07_13.md`. Future campaigns
  now fail closed on provenance; stats-specialist review remains required
  before any future G10 PASS can support promotion.
  Canonical V2 adds complete declared-scope family and 67-trial diagnostics, but does not
  recover omitted upstream admission: B2 PBO 0.5066/DSR 0 fails, B4 PBO 0.3739/DSR 0 fails,
  and B3/campaign-wide DSR are withheld for undefined zero-variance correlations. Evidence:
  `artifacts/reports/CANONICAL_BASELINE_CAMPAIGN_V2_REPORT_2026_07_13.md`.

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
   G4 remains WARN, and aligned v2 PBO/DSR diagnostics numerically fail B2 (PBO 0.2960,
   DSR≈0). Production G10 remains `METHOD_BLOCKED` because the complete upstream
   search hierarchy and hierarchy-wide effective-trial evidence are unresolved.
   The historical LAB FAIL projection is retained but cannot establish method completion.
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
   (`SEED_G10_QC2_ETHUSDT_1H_2026_07_13.json`: aligned numeric PBO 0.2662 and
   DSR 0.8548 < 0.95; hierarchy method status remains blocked).
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
- The 2026-07-10 S2 live-unreachability report is superseded historical evidence:
  authenticated Bybit demo scripts were added and used after its review window.
  Current repository safety comes from D-046 transport quarantine plus
  `tests/test_live_unreachable.py` and the demo-script fail-closed tests. A refreshed
  formal stage-exit security report remains required before HG-3/S3.
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
