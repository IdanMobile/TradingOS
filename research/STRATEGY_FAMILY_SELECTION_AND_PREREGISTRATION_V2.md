# Strategy family selection and preregistration V2

Outcome: **GO**  
Decision ID: `D-053`  
Selection cycle: `FAMILY-SELECT-V2`  
Decision time: `2026-07-13T12:18:18Z`  
Selected family: `FAM-CALENDAR-UTC-01`  
Mode: bounded offline source-first review  
Execution authority: `NONE`  
Venue connection: `NONE`  
Promotion eligible: `false`

## Conclusion first

Select a low-frequency, long-only BTCUSDT Spot **UTC weekday-conditioned exposure**
family for the next governed campaign.

This is a research admission, not a profitable result and not approval. No weekday has
been selected, no calendar return has been calculated, and no campaign has been run.
The complete first-level trial roster is frozen as the seven individual UTC weekdays;
the future campaign must retain all seven, use the same F1/S1 primary cost scenario,
and select with the one governed metric specified below.

Three economically distinct fresh families were compared:

1. UTC weekday-conditioned BTCUSDT Spot exposure;
2. fiat-backed stablecoin below-peg reversion; and
3. Bitcoin block-subsidy-halving event exposure.

The calendar family passes admission because:

- its mechanism is explicit, contested, and falsifiable;
- the required UTC timestamp and Spot OHLCV inputs already exist in a checksum-pinned,
  independently audited public dataset;
- it is unlevered, single-leg, long-only Spot with bounded and explicit turnover;
- the current canonical model needs only a narrow deterministic UTC-calendar rule;
- a repository search found no previous weekday/day-of-week strategy or score; and
- roughly 286 weekly observations per weekday across the frozen 2021-2026 historical
  window are available, while annual/regime dependence will be reported rather than
  disguised as 286 independent regimes.

The other candidates fail hard admission gates:

- stablecoin reversion depends on direct redemption eligibility, issuer/chain/legal
  state, and depeg-tail semantics that a generic secondary-market backtest cannot own;
- halving exposure has authoritative event identity but only four Bitcoin events in
  total and one inside the repository's frozen 2021-2026 dataset, which is insufficient
  for a decision-useful strategy validation.

The selected family remains `UNVALIDATED / NOT_ELIGIBLE`. The next action is to create
its immutable source/data/venue-semantics package and canonical specification without
reading the sealed V2 holdout or computing performance.

## Relationship to V1

`FAMILY-SELECT-V1` remains valid evidence for its exact roster and `NO_GO` conclusion.
It rejected funding/basis carry, cross-sectional momentum, and volatility-managed
exposure. This V2 cycle does not rescue or rename those families. It admits a fresh
roster selected without viewing local performance.

The platform validation review in
`research/PLATFORM_STRATEGY_VALIDATION_AND_SCORE_ELIGIBILITY_V1.md` is binding context:
platform metrics are evidence dimensions, not approval; TradingOS retains independent
hard gates and no blended/global score.

## Authority and safety boundaries

- D-001 keeps Spot before derivatives.
- D-011 prevents inheritance of external profit claims.
- D-039/D-042 allow autonomous offline research, not human-gate substitution.
- D-043 keeps the local synthetic simulator dormant until a matching validation-approved
  strategy exists and HG-3 is granted by the operator.
- D-046 keeps authenticated venue transports quarantined.
- D-047/D-049 require the complete hierarchy, costs, splits, metric, and stop rules to
  be frozen before search.
- D-051 closes B2/B3/B4 expansion and seals their prospective holdout from
  `2026-07-14T00:00:00Z` through the no-earlier-than evaluation date
  `2027-01-14T00:00:00Z`.
- D-052 records the first family-selection `NO_GO` and requires this bounded new cycle.

This dossier creates no account, credential, connection, order, bot, campaign result,
promotion, or execution authority.

## Evidence classification

### Verified project facts

- The canonical frozen Spot dataset contains BTCUSDT 1h from
  `2021-01-01T00:00:00Z` through `2026-06-30T23:00:00Z`, 48,154 rows, content hash
  `49981c5cf5f3376ea60e931415feefa252c5970d902732dd68d8e95c46a2a3b3`.
- Its public Binance source bytes and checksums are retained and its normalized content
  has been regenerated identically twice.
- The independent data audit records seven exchange-wide gaps and 14 expected-missing
  BTCUSDT 1h bars; gaps are retained rather than filled.
- Existing canonical evaluation supports single-instrument long-only state transitions,
  next-bar fills, Spot costs, gaps, and immutable StrategyVersion identity.
- Existing canonical indicators do not expose a UTC weekday field; a small,
  deterministic calendar-rule extension is required.
- A repository-wide code/artifact search found no prior weekday, day-of-week,
  hour-of-day, or calendar-seasonality strategy implementation or score.
- No V2 prospective-holdout observation or result was read or computed.

### Source-backed conclusions

- Peer-reviewed work reports day-of-week effects in Bitcoin returns/volatility in some
  historical samples, often with higher Monday returns.
- Another primary study reports that most cryptoassets showed no day-of-week effect and
  that most apparent Bitcoin trading profits were not significantly different from
  random results. This conflict makes the hypothesis testable; it does not establish an
  edge.
- Stablecoin peg restoration depends materially on access to primary issuance/redemption
  as well as secondary-market arbitrage.
- Current Circle and Tether terms condition direct redemption on account/verification,
  eligibility, law, fees, limits, and operational availability.
- Bitcoin's subsidy schedule is protocol-defined, but empirical studies have only a
  handful of halving events and recent papers report mixed or negative effects.

### Inferences

- A UTC weekday rule is the shortest lawful route of the fresh candidates because it
  adds no external feature feed, point-in-time universe, derivative, leverage, short,
  redemption, or multi-leg state.
- Weekly observations are serially and regime dependent; nominal trade count cannot be
  treated as the number of independent market regimes.
- A published Monday result creates a prior hypothesis but not local selection. Keeping
  all seven weekdays in the declared population prevents silently cherry-picking Monday.

### Unknowns

- Whether any UTC weekday produces positive after-cost performance in the frozen local
  sample.
- Whether a selected weekday survives the latest family-unseen chronological segment,
  annual regimes, perturbation, other instruments/venues, and prospective observation.
- Whether calendar effects have decayed as crypto participation and market structure
  evolved.
- Operator venue/account eligibility and actual fees. These are deferred human facts and
  are not necessary for offline historical validation.

## Preregistered selection procedure

No performance result was computed during this selection cycle.

### Complete admitted roster

| Candidate ID | Family | Economic mechanism | Proposed offline context |
|---|---|---|---|
| `FAM-CALENDAR-UTC-01` | UTC weekday-conditioned exposure | Periodic attention, participation, liquidity, and information arrival may create weekday-dependent BTC returns | Long-only BTCUSDT Spot, 1h, UTC, cash otherwise |
| `FAM-STABLEPEG-01` | Fiat-backed stablecoin below-peg reversion | Eligible arbitrageurs may buy below peg and redeem at par, pulling price toward the peg | Secondary-market public-data research only; no issuer or venue account |
| `FAM-HALVING-01` | Bitcoin subsidy-halving event exposure | A protocol-known reduction in new issuance may affect miner supply, attention, and price discovery | Long-only BTCUSDT Spot around protocol events |

No fourth family, B2/B3/B4 variant, volatility overlay, derivative, ML model, public bot,
or result-driven combination is admitted.

### Hard admission gates

Every gate must pass. `UNKNOWN` is a failure.

| Gate | Requirement |
|---|---|
| `A1_MECHANISM` | Explicit, economically distinct, causal enough to simulate, and falsifiable |
| `A2_SOURCE_IDENTITY` | Primary source identity, scope, conflict, and transfer limits retained |
| `A3_PIT_DATA` | Point-in-time inputs can be snapshotted, checksummed, restored, and timed causally without credentials |
| `A4_CAPITAL_COST_RISK` | Total capital, costs, sizing, exits, tails, and dominant family risks are modeled |
| `A5_CANONICAL_OWNERSHIP` | Existing contracts own the strategy or a small preregistered extension suffices |
| `A6_SEARCH_LINEAGE` | Complete family/trial hierarchy, metric, costs, splits, and stop rules can be frozen before scoring |
| `A7_SAMPLE` | Event count and independent regime coverage are plausibly decision-useful |
| `A8_SAFE_ROUTE` | Offline G1-G11 requires no credentials, venue execution, or human trading gate |

Decision rule:

- select exactly one candidate passing A1-A8;
- zero complete candidates means `NO_GO`;
- multiple complete candidates are resolved by shortest lawful route, then lower
  counterparty dependence, then lower implementation complexity; and
- no result, popularity, platform rank, or paper headline is a tie-breaker.

### Gate results

| Candidate | A1 | A2 | A3 | A4 | A5 | A6 | A7 | A8 | Decision |
|---|---|---|---|---|---|---|---|---|---|
| `FAM-CALENDAR-UTC-01` | PASS | PASS_WITH_CONFLICT | PASS | PASS_WITH_LIMITS | PASS_WITH_SMALL_EXTENSION | PASS | PASS_WITH_DEPENDENCE | PASS | **SELECT** |
| `FAM-STABLEPEG-01` | PASS | PASS | BLOCKED | **FAIL** | BLOCKED | BLOCKED | PASS | BLOCKED | REJECT |
| `FAM-HALVING-01` | PASS | PASS_WITH_CONFLICT | PASS | PASS_WITH_LIMITS | PASS_WITH_SMALL_EXTENSION | PASS | **FAIL** | PASS | REJECT |

The table is not a weighted score. One hard failure rejects a candidate.

## Selected candidate: UTC weekday-conditioned Spot exposure

### Mechanism and falsifiability

Cryptocurrency trades continuously, but human and institutional participation remains
scheduled. Attention, work weeks, fiat settlement, risk management, liquidity provision,
and information arrival may differ by UTC weekday. If those differences create a
persistent return premium, holding BTC only during one UTC weekday may outperform cash
after the two weekly trading round trips.

The hypothesis is false for this context if no weekday survives the preregistered F1/S1
costs, chronological selection, untouched family-specific evaluation, annual/regime
review, multiple-testing correction, benchmark comparison, and independent reproduction.

The hypothesis is also rejected if an apparent result depends on:

- zero costs;
- one isolated year or tail event;
- noncausal same-bar fills;
- filled or ignored data gaps;
- a weekday chosen after viewing results;
- a different timezone introduced after the run;
- a small parameter neighborhood discontinuity; or
- incomplete trial retention.

### Exact proposed context

The canonical version to freeze in Task 3 must represent exactly:

`BTCUSDT Spot × Binance-public-data reference × 1h × UTC weekday exposure × long/cash × HISTORICAL_RESEARCH`

Binance here identifies the public data source and market microstructure reference. It
does not select a future operator venue.

### First-level trial population

The complete first-level population is exactly seven trials:

| Trial | Exposed UTC interval each week |
|---|---|
| `WD-0-MON` | Monday `00:00:00` inclusive to Tuesday `00:00:00` exclusive |
| `WD-1-TUE` | Tuesday `00:00:00` inclusive to Wednesday `00:00:00` exclusive |
| `WD-2-WED` | Wednesday `00:00:00` inclusive to Thursday `00:00:00` exclusive |
| `WD-3-THU` | Thursday `00:00:00` inclusive to Friday `00:00:00` exclusive |
| `WD-4-FRI` | Friday `00:00:00` inclusive to Saturday `00:00:00` exclusive |
| `WD-5-SAT` | Saturday `00:00:00` inclusive to Sunday `00:00:00` exclusive |
| `WD-6-SUN` | Sunday `00:00:00` inclusive to Monday `00:00:00` exclusive |

No weekday pairs, subsets, hour offsets, timezone variants, stop losses, take profits,
trend filters, volatility filters, or weekday-specific parameters are admitted in V1 of
this family.

Cash-only and always-long buy-and-hold are benchmarks, not selectable trials. The seven
trials are one family for campaign-wide PBO/DSR and effective-trial accounting.

### Signal and fill semantics to freeze

- Clock: UTC only; no daylight-saving conversion.
- Observation: a 1h bar is usable only after its close.
- Entry signal: at the close of the immediately preceding 23:00 UTC bar, request long
  exposure for the next UTC day when that next day equals the trial weekday.
- Entry fill: next exactly adjacent 00:00 UTC bar open, adverse slippage applied.
- Exit signal: at the close of the exposed day's 23:00 UTC bar.
- Exit fill: next exactly adjacent 00:00 UTC bar open, adverse slippage applied.
- Position: all eligible synthetic cash, long BTC only; no leverage, borrowing, short,
  pyramiding, partial target, or overlapping exposure.
- Gap before a requested fill: expire the signal and remain in the prior safe state;
  never jump to a later bar.
- Gap while long: the exact family data contract must define fail-closed exit handling
  before the campaign; the conservative default is exit at the first observable open
  with stress slippage and flag the event.
- Final signal without next bar: no fill.
- Fees: applied on each executed side's notional.
- Interest/yield on cash: zero in primary analysis; opportunity cost reported separately.

The entry is causal because the next UTC weekday is deterministic calendar information,
not future market information.

### Cost and capital model

Reuse the governed Spot surface without optimizing by cost cell:

| Scenario | Fee per side | Adverse slippage per side | Role |
|---|---:|---:|---|
| `F0/S0` | 0 | 0 bp | diagnostic only |
| `F1/S1` | 0.10% | 1 bp | primary selection/economics |
| `F1/S2` | 0.10% | 5 bp | stress |
| `F1/S3` | 0.10% | 10 bp | stress |
| `F2/S2` | 0.15% | 5 bp | stress |
| `F2/S3` | 0.15% | 10 bp | stress |

Initial synthetic cash is 1,000 USDT. Buy fill is
`open × (1 + slippage_rate)`; sell fill is
`open × (1 - slippage_rate)`. Fees reduce cash on each side. Fractional BTC is allowed
for research math, subject to a later explicit quantity-step feasibility check.

At one entry and exit per selected week, the strategy pays about 104 sides per full
year. This makes after-cost feasibility a real gate rather than a footnote.

Spread, empirical latency, order-book impact, and capacity are not observed in 1h OHLCV.
The slippage cells are stresses, not empirical capacity proof. Promotion must remain
blocked until capacity/liquidity is decision-useful for the intended capital tier.

### Data contract

Proposed immutable base:

- dataset: `DS-CRYPTO-SPOT-BAKEOFF-V1`;
- table: `BTCUSDT_1h`;
- range: `2021-01-01T00:00:00Z` to `2026-06-30T23:00:00Z`;
- rows: 48,154;
- content SHA-256:
  `49981c5cf5f3376ea60e931415feefa252c5970d902732dd68d8e95c46a2a3b3`;
- fields: UTC open/close time, OHLC, volume, quote volume, trades, taker fields from the
  retained normalized schema; only timestamp and OHLC are required by this family;
- gaps: retain and branch through explicit gap semantics; no interpolation; and
- upstream: checksum companions from Binance public data.

Task 2 must create a family-specific derived manifest that pins the exact base manifest,
schema, calendar derivation, timezone database independence, gap rows, and restore proof.
It must not redownload or reinterpret source bytes if the existing immutable package
already satisfies the requirement.

### Canonical extension boundary

The smallest extension is a deterministic calendar rule with no numeric fitting:

- canonical input identifier: `next_bar_utc_weekday` in integer domain `0..6`;
- derivation: weekday of the next exactly adjacent bar open in UTC;
- allowed comparisons: equality to one frozen integer;
- no locale, timezone, daylight-saving, holiday, or exchange-session dependency; and
- evaluator, validator, serializer, independent reference, and fixtures must agree.

Do not generalize this into a calendar DSL, cron engine, session service, holiday
library, or arbitrary temporal expression system in this phase.

### Search lineage and historical evidence labels

The raw BTCUSDT history has been used by other strategy families, but no calendar-family
result has been computed. Therefore:

- the 2021-2024 development/selection history is known market history but
  family-unscored at freeze;
- any expanding walk-forward outputs are `HISTORICAL_PSEUDO_OOS`;
- the latest reserved family-specific evaluation interval can be labeled
  `HISTORICAL_FAMILY_UNSEEN_AT_FREEZE` only if a preflight proves no calendar output was
  created before the immutable campaign freeze; and
- it is not labeled prospective merely because the family is new.

The B2/B3/B4 prospective holdout is out of scope and remains sealed. This family may
later establish its own prospective post-freeze observation window under a distinct
identity, but it cannot borrow V2's holdout status.

### Governed selection metric and gates

The campaign's one selection metric is:

`non_annualized_per_1h_bar_Sharpe at F1/S1`

calculated on the complete causal after-cost hourly return stream, with zero returns
while in cash. This matches the existing G10 method and avoids changing metric between
selection, CSCV/PBO, DSR, and walk-forward selection.

Reporting must also include annualized return, max drawdown, exposure time, turnover,
event count, profit factor when defined, expected payoff, worst trade/week, CVaR,
buy-and-hold and cash comparisons, and all cost cells. These are independent dimensions,
not alternative selectors.

Minimum decision gates remain:

- complete provenance and deterministic restoration;
- exact micro-goldens and causal invariance;
- all seven trials retained at every cost cell and split;
- nonzero event count and at least 200 complete exposed-day events in full history;
- positive F1/S1 after-cost economics and superiority to cash after opportunity cost;
- no zero-cost-only edge;
- stable expanding walk-forward behavior with no single-year dependency;
- parameter/clock perturbation review, including ±1h entry/exit diagnostics declared
  before execution and never promoted as new trials;
- regime, tail, and gap-event review;
- family-wide `PBO <= 0.5` and corrected `DSR >= 0.95` when mathematically eligible;
- independent reference plus Freqtrade and Nautilus/LEAN-compatible semantic checks as
  applicable;
- lookahead and recursive/start-history checks;
- independent stats, risk, supervisor, and security reviews; and
- every mandatory G1-G11 gate PASS for the exact context.

No weighted score can offset a hard fail or `NOT_RUN`.

### Proposed chronological design

The final campaign file must freeze exact bar boundaries and hashes. The intended split
is:

- development/expanding selection start: `2021-01-01T00:00:00Z`;
- expanding yearly pseudo-OOS folds: 2022, 2023, and 2024;
- reserved historical family-unseen evaluation: 2025 plus 2026-H1, evaluated once only
  after a weekday is selected using data ending `2024-12-31T23:00:00Z`;
- each fold/evaluation starts flat;
- a one-bar boundary embargo forbids a signal/fill across the boundary; and
- all seven variants remain present in G10 even though only the selection-period winner
  enters the reserved evaluation.

This design yields three annual selection folds and an 18-month family-unseen test. It
does not create six independent market regimes; the limited regime count is a disclosed
constraint. If the stats specialist judges DSR/PBO or regime inference ineligible, the
result remains `METHOD_BLOCKED` regardless of returns.

### Stop and no-rescue rules

- Abort before scoring if code, spec, data, source, environment, roster, split, or cost
  hashes differ from the frozen campaign.
- Abort on a missing trial, fold, cost cell, terminal record, or required metric input.
- Never drop a zero-trade or undefined-metric trial.
- Do not inspect the reserved evaluation before selecting and freezing one weekday.
- Do not add weekday subsets, hour offsets, filters, exits, or sizing rules after results.
- Do not switch timezone, metric, benchmark, annualization, or cost cell after results.
- Do not rescue a failed weekday by combining it with B2/B3/B4 or another family.
- Any adaptation after viewing results requires a new StrategyVersion, full hierarchy,
  and new unseen evidence.
- A numerically attractive result remains non-promotional until all independent gates
  and human decisions are complete.

## Rejected candidate: stablecoin below-peg reversion

### Mechanism

When a fiat-backed stablecoin trades below one dollar, an eligible arbitrageur may buy
it in the secondary market and redeem it with the issuer at par. That flow can pull the
secondary price toward the peg.

### Hard blocker

The direct redemption leg is not a generic public-market operation. Circle's current
terms distinguish registered Circle Mint users from other holders and condition direct
redemption on account standing, eligibility, legal restrictions, fees, and service
availability. Circle also states that Mint is aimed at institutions rather than
individuals/small businesses outside specific regimes. Tether requires verified-customer
status and makes redemption subject to minimums, fees, and other requirements.

A secondary-market-only backtest that assumes par redemption would omit the mechanism's
dominant access and counterparty risk. A version that merely buys below peg and sells
later on the same exchange is unsecured issuer/venue/chain tail exposure, not the same
arbitrage.

Required unresolved semantics include issuer and chain identity, point-in-time
redemption terms, banking hours and transfer latency, KYC/jurisdiction eligibility,
fees/minimums, blocklists/freezes, chain downtime, reserve/counterparty stress,
venue-specific quotes and depth, depeg gaps, and total-loss/indefinite-suspension states.

Result: reject at A4 and do not request an account or credentials.

## Rejected candidate: Bitcoin halving exposure

### Mechanism

Bitcoin Core's consensus parameters and subsidy calculation reduce block subsidy at
fixed height intervals. The reduction in new issuance can affect miner selling,
attention, scarcity narratives, and price discovery.

### Hard blocker

Bitcoin has only four completed subsidy halvings. The frozen 2021-2026 Binance dataset
contains only the April 2024 event. Even using the complete Bitcoin price history would
provide four highly nonstationary events across radically different liquidity,
regulatory, macro, and market-structure regimes.

Recent primary literature also reports mixed or negative short-event reactions rather
than a stable bullish effect. A strategy cannot support G1-G11, DSR/PBO, neighborhood,
or regime claims from one to four dependent events.

Result: reject at A7. Retain halving as macro/regime annotation research, not a
promotable trading family.

## Source records

All new web sources were retrieved `2026-07-13T12:18:18Z`. Existing Binance/data and
multiple-testing records `SRC-FS-01`, `SRC-FS-02`, and `SRC-FS-08` from V1 remain
incorporated by reference.

### `SRC-FS2-01` — Bitcoin and the day-of-the-week effect

- URL: <https://doi.org/10.1016/j.frl.2018.12.004>
- Publication: Aharon and Qadan, *Finance Research Letters* 31, 2019.
- Primary claim: OLS/GARCH analysis of 2010-2017 daily Bitcoin data reports weekday
  effects in returns and volatility, with higher Monday return and volatility.
- Transfer limit: historical daily price samples, not Binance 1h execution or current
  after-cost evidence; Monday is a prior hypothesis, not a selected local trial.
- Confidence: high for the paper's claim, low as current profitability evidence.

### `SRC-FS2-02` — The day of the week effect in the cryptocurrency market

- URL: <https://doi.org/10.1016/j.frl.2018.11.012>
- Publication: Caporale and Plastun, *Finance Research Letters* 31, 2019; open access.
- Primary claim: most studied cryptocurrencies showed no effect; Bitcoin Monday returns
  differed, but most simulated profits were not significantly different from random.
- Conflict: directly limits a strong/exploitable interpretation of SRC-FS2-01.
- Confidence: high as mechanism/counterevidence, not implementation proof.

### `SRC-FS2-03` — Bitcoin intraday and calendar effects

- URL: <https://doi.org/10.1016/j.frl.2019.04.023>
- Publication: Kruckeberg and Scholz, *Finance Research Letters* 31, 2019.
- Primary claim: studies Bitcoin time-of-day, day-of-week, month-of-year, returns, and
  trading-volume effects.
- Transfer limit: supports calendar periodicity as a testable family, not any exact
  Binance weekday or profitable strategy.
- Confidence: high for research scope, low for transfer.

### `SRC-FS2-04` — Stablecoin peg mechanism

- URL: <https://doi.org/10.1016/j.jimonfin.2022.102777>
- Publication: Lyons and Viswanath-Natraj, *Journal of International Money and Finance*.
- Primary claim: broader arbitrage access and primary/secondary market design materially
  affect peg efficiency.
- Transfer limit: does not grant redemption access or eliminate issuer/run risk.
- Confidence: high.

### `SRC-FS2-05` — Circle USDC terms

- URL: <https://www.circle.com/legal/usdc-terms>
- Authority/version: official Circle legal terms, last updated `2025-12-12` on retrieval.
- Claim: direct redemption is conditional on a registered eligible Circle Mint account,
  compliance, law, fees, and service availability; non-Mint holders generally cannot
  redeem directly outside applicable regime-specific rights.
- Limitation: terms and operator eligibility can change and require human recheck.
- Confidence: high for current public terms.

### `SRC-FS2-06` — Tether terms

- URL: <https://tether.to/en/legal/>
- Authority/version: official Tether legal terms retrieved above.
- Claim: direct issuance/redemption requires verified-customer status and may be subject
  to minimum amounts, fees, and other requirements.
- Limitation: terms and operator eligibility can change and require human recheck.
- Confidence: high for current public terms.

### `SRC-FS2-07` — Bitcoin consensus subsidy implementation

- URLs: <https://github.com/bitcoin/bitcoin/blob/master/src/validation.cpp> and
  <https://github.com/bitcoin/bitcoin/blob/master/src/consensus/params.h>
- Authority: Bitcoin Core source repository; primary protocol implementation.
- Claim: block subsidy is calculated from consensus halving parameters and block height.
- Limitation: the immutable data package must pin a release/commit rather than `master`.
- Confidence: high for mechanism identity.

### `SRC-FS2-08` — Some stylized facts about bitcoin halving

- URL: <https://www.sciencedirect.com/science/article/pii/S1544612324012273>
- Publication: *Finance Research Letters*, 2025.
- Primary claim: studies the 2012, 2016, and 2020 halvings and reports slightly depressed
  prices, lower volatility/miner revenue, and mixed network reactions.
- Transfer limit: only three historical events in the study; not strategy validation.
- Confidence: high as sample-size/counterevidence.

### `SRC-FS2-09` — The effect of the cryptocurrency halving event

- URL: <https://doi.org/10.1016/j.pacfin.2025.102913>
- Publication: Liu, Zhao, Li, and Wang, *Pacific-Basin Finance Journal*, 2025.
- Primary claim: cross-cryptocurrency event study reports negative cumulative abnormal
  returns and post-event reversals associated with attention.
- Transfer limit: pooled cryptocurrency events are not independent Bitcoin halvings and
  do not validate a BTC strategy.
- Confidence: high as conflicting mechanism evidence.

## Exact next action

Proceed to Task 2 for `FAM-CALENDAR-UTC-01` only:

1. create a family-specific immutable data/source manifest that references the existing
   frozen BTCUSDT 1h bytes and independently verifies the calendar derivation;
2. pin every external source by version/date/hash where possible;
3. specify all gap and boundary cases with known-answer fixtures;
4. create the minimal canonical calendar-rule design; and
5. freeze a complete campaign file and StrategyVersion hashes before computing any
   weekday return.

Do not score, optimize, activate synthetic paper, connect to a venue, request secrets,
or touch the sealed V2 holdout during that work.
