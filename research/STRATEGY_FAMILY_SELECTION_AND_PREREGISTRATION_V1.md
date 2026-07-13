# Strategy family selection and preregistration V1

Outcome: **NO_GO**  
Decision ID: `D-052`  
Selection cycle: `FAMILY-SELECT-V1`  
Decision time: `2026-07-13T11:42:30Z`  
Mode: bounded offline strategy/research review  
Execution authority: `NONE`  
Venue connection: `NONE`  
Promotion eligible: `false`

## Conclusion first

Do not freeze or run a new parameter campaign for any family reviewed here.

Three economically distinct families were compared:

1. delta-neutral spot/perpetual funding and basis carry;
2. long-only Spot cross-sectional momentum; and
3. volatility-managed Spot exposure.

Each has a falsifiable mechanism, but each fails at least one non-compensable admission
gate before a new search:

- funding/basis carry lacks a reproducible point-in-time contract, margin,
  liquidation, and counterparty model. The official public data closes part of the
  price/funding gap but not the dominant capital-at-risk gap;
- cross-sectional momentum lacks a point-in-time, delisting-complete universe and the
  available primary result is a broad long-short result, not proof for the proposed
  Binance Spot long-only implementation. The local family has already been searched
  on contaminated full-history inputs;
- volatility-managed exposure has the shortest technical route, but the exact family
  was already used inside local result-driven searches, its continuous sizing semantics
  are not owned by the current canonical strategy contract, and primary literature
  contains material out-of-sample and transaction-cost counterevidence.

The decision is deliberately not a weighted-score winner. A hard failure in data,
capital/risk semantics, search lineage, or canonical ownership cannot be averaged away
by implementation convenience or an attractive historical diagnostic.

This dossier is the complete output of Task 1's first bounded family-selection cycle.
Because the outcome is `NO_GO`, it creates no StrategyVersion, campaign runner,
parameter grid, dataset download, backtest, paper activation, venue selection, or
execution authority. A new bounded source-first selection cycle is required.

## Decision required

Select at most one strategy family whose mechanism, exact context, point-in-time data,
capital/cost/risk model, canonical identity, and full search hierarchy are sufficiently
specified to freeze before any parameter evaluation.

The selected context would have to be one exact:

`StrategyVersion × market × instrument × timeframe × configuration × environment`

No family name, paper result, platform result, exploratory local statistic, or prior bot
artifact can satisfy that identity.

## Authority and constraints

The following project boundaries are binding:

- D-001: preserve the Spot-before-perpetual sequence unless evidence and a later
  decision justify crossing the derivative boundary;
- D-011: external strategy claims are hypotheses, never inherited profit evidence;
- D-039/D-042: offline research direction may be decided autonomously, but HG-3,
  HG-4, and HG-5 remain human-only;
- D-043: the first lawful bot remains the dormant local synthetic simulator, after a
  matching strategy is genuinely approved and HG-3 is granted;
- D-046: authenticated venue transports remain quarantined;
- D-047/D-049: one governed metric, full hierarchy, all trials, immutable inputs,
  costs, splits, and stop rules must be frozen before substantive search;
- D-048: research-only multi-leg identity is not execution semantics;
- D-051: B2/B3/B4 expansion and result-driven rescue are closed; their prospective
  BTCUSDT holdout beginning `2026-07-14T00:00:00Z` remains sealed and may not be
  scored before `2027-01-14T00:00:00Z`.

No source or conclusion in this dossier selects Binance or any other venue for an
operator account. Official Binance material is used only because it is the repository's
current public-data reference boundary.

## Evidence classification

### Verified project facts

- `main` was clean at `60d0e96287b0a22f2bff1c7f61e09ab2a4ace445` when this
  cycle began, seven commits ahead of `origin/main`.
- Canonical V2 retained 67 B2/B3/B4 trials and closed their expansion with no
  promotable result.
- Existing funding, cross-sectional, and volatility-scaling outputs are exploratory,
  have already exposed historical result information, and are not unseen evidence.
- Funding carry is represented only by a research-only multi-leg canonical record;
  venue mapping, margin, liquidation, settlement, reconciliation, and order semantics
  are absent.
- Current canonical evaluation primarily owns single-instrument, directional rules.
  It does not yet own cross-sectional ranking or continuously variable volatility
  targeting end to end.
- No strategy is validation-approved or promotion-eligible. No paper runner, venue
  session, or execution authority exists.

### Source-backed conclusions

- Binance publishes checksum-addressable Spot and futures market archives and public
  funding/mark/index interfaces, but its current symbol and funding-parameter endpoints
  are not a historical contract-lifecycle archive.
- Binance's notional/leverage bracket interface is signed `USER_DATA`, and its response
  may include a user-specific bracket multiplier. It therefore cannot provide the
  required unauthenticated, historical, account-independent liquidation inputs for this
  offline cycle.
- Published cryptocurrency factor research supports cross-sectional momentum as a
  hypothesis, but the cited construction is weekly, broad-universe, and long-short.
  It does not validate a Binance Spot long-only subset.
- Volatility management has a published economic rationale, but later primary research
  reports that the original individual-factor approach can fail out of sample and after
  costs. The conflict must be tested, not averaged away.

### Inferences

- Spot-only families are operationally closer to a lawful synthetic bot than carry or
  long-short relative value because they avoid margin, liquidation, leg asymmetry, and
  derivative contract semantics.
- Historical archive filenames and first/last observations may help reconstruct a
  universe, but they do not by themselves prove the exact listing status, eligibility,
  filters, or delisting reason that was knowable at each decision time.
- A smooth or low-turnover return stream can still be method-invalid when the family was
  selected after prior full-history exploration.

### Unknowns

- Whether a complete official historical archive of Binance Spot and USD-M contract
  lifecycle/filter changes exists in a reproducibly enumerable form.
- Historical, account-applicable maintenance-margin tiers and every change to funding
  cap, floor, interval, liquidation, and collateral rules.
- Whether a fresh, preregistered long-only cross-sectional construction survives a
  delisting-complete universe and realistic rebalance costs.
- Whether a fresh, canonically owned volatility-managed Spot construction survives
  genuine unseen evidence and the approved cost surface.
- Current operator eligibility, fees, permissions, tax treatment, capital, and venue
  suitability. These are intentionally deferred human facts and are not needed for the
  present `NO_GO`.

## Preregistered selection procedure

This section freezes the selection logic for `FAMILY-SELECT-V1`. No strategy result was
computed during this cycle.

### Admitted roster

The complete roster is exactly:

| Candidate ID | Family | Economic mechanism | Proposed safe research context |
|---|---|---|---|
| `FAM-CARRY-01` | Funding/basis carry | Funding transfers and basis convergence may compensate a hedged short-perpetual/long-Spot position | Public-data-only USD-M/Spot research; no venue or account |
| `FAM-XSMOM-01` | Cross-sectional momentum | Relative winners may continue to outperform relative losers because information and positioning diffuse unevenly | Long-only USDT Spot rotation; cash is the only alternative leg |
| `FAM-VOLMGT-01` | Volatility-managed exposure | Expected returns may not rise proportionally with volatility, so reducing exposure in high volatility may improve risk-adjusted outcomes | Unlevered BTCUSDT/USDT Spot research |

No B2, B3, B4, generic breakout, univariate Bollinger mean reversion, moving-average
variant, parameter rescue, ML strategy, market-making strategy, option strategy, or
fourth family is admitted.

### Hard admission gates

A candidate must pass every gate. `UNKNOWN` is a failure for this decision.

| Gate | Requirement |
|---|---|
| `A1_MECHANISM` | Mechanism is explicit, economically distinct, causal enough to simulate, and falsifiable |
| `A2_SOURCE_IDENTITY` | Exact primary sources, versions/dates, scope, conflicts, and limitations are retained |
| `A3_PIT_DATA` | Authoritative point-in-time inputs, universe/lifecycle records, and exact source bytes can be snapshotted and restored without credentials |
| `A4_CAPITAL_COST_RISK` | Total deployable capital, fees, spread, slippage, impact, sizing, exits, tails, and family-specific risks can be modeled without omitting a dominant risk |
| `A5_CANONICAL_OWNERSHIP` | Current contracts express the complete strategy without semantic overloading, or only a small preregistered extension is required |
| `A6_SEARCH_LINEAGE` | Family admission, transformations, parameter population, trial count, selection metric, splits, holdout, and stop rules can be frozen before evaluation |
| `A7_SAMPLE` | Decision/event count and independent regime coverage are plausible for a decision-useful test |
| `A8_SAFE_ROUTE` | The route to synthetic paper does not require credentials, venue execution, or a human gate during offline G1-G11 work |

Decision rule:

- exactly one candidate passing `A1` through `A8` would produce `GO`;
- zero candidates passing all gates produces `NO_GO`;
- more than one complete candidate would be resolved by shortest lawful route, then
  lower venue/counterparty dependence, then lower implementation complexity;
- prior profitability, DSR proximity, headline paper returns, popularity, and platform
  availability are not tie-breakers.

### Evidence cutoff and contamination rule

- Repository evidence available at the start commit is known historical context.
- External sources were retrieved at `2026-07-13T11:42:30Z`.
- Existing local funding, cross-sectional, and volatility-targeting results are disclosed
  as seen and cannot become unseen evidence by renaming a campaign.
- No market observation or score from the V2 prospective holdout was read or computed.
- Any future campaign using previously explored historical data must label it
  `HISTORICAL_PSEUDO_OOS` unless a genuinely untouched context is proven.

### Stop rules

- Stop and issue `NO_GO` if any dominant family risk lacks authoritative semantics.
- Do not simplify away margin, liquidation, counterparty, delisting, shorting, dynamic
  sizing, or turnover merely to make a candidate fit existing code.
- Do not add candidates or parameters after viewing performance.
- Do not reuse existing exploratory best parameters as a new control.
- Do not run a backtest, download a new strategy dataset, or create an executable
  StrategyVersion before a family passes admission.
- Retain rejected families and reasons; do not silently drop them.

## Gate result

| Candidate | A1 | A2 | A3 | A4 | A5 | A6 | A7 | A8 | Decision |
|---|---|---|---|---|---|---|---|---|---|
| `FAM-CARRY-01` | PASS | PASS | **FAIL** | **FAIL** | BLOCKED | BLOCKED | PASS | BLOCKED | REJECT |
| `FAM-XSMOM-01` | PASS | PASS | **FAIL** | BLOCKED | **FAIL** | **FAIL** | PASS | PASS | REJECT |
| `FAM-VOLMGT-01` | PASS | PASS_WITH_CONFLICT | PASS | PASS_WITH_LIMITS | **FAIL** | **FAIL** | BLOCKED | PASS | REJECT |

The table is not a score. One bold hard failure is sufficient for rejection.

## Candidate review: funding and basis carry

### Mechanism and falsifiability

When a perpetual funding rate is positive, a short perpetual position may receive a
payment while a matched long Spot position offsets first-order directional exposure.
The hypothesis is false for this context if total return on total deployable capital is
not positive after basis movement, funding settlements, all entry/rehedge/unwind costs,
collateral opportunity cost, liquidation/ADL tails, and counterparty stress.

Funding is not presumed positive, persistent, or collectible. A negative rate reverses
the transfer, and a nominally delta-neutral pair still carries basis, margin,
liquidation, stablecoin, operational, and venue-default risk.

### Authoritative inputs found

- public funding history exposes symbol, rate, funding time, and the mark price
  associated with the charge;
- public funding information exposes current adjusted cap, floor, and interval for
  symbols whose settings were adjusted;
- public mark-price, index-price, premium-index, trade-price, and kline interfaces exist;
- current exchange information exposes current symbols and rules;
- Binance public-data archives offer daily/monthly files and checksum companions.

These sources materially improve the old funding-only artifact, but they do not close
historical contract semantics.

### Dominant unresolved model

The following must be point-in-time and cannot be substituted by current values:

- exact Spot/perpetual instrument identity and lifecycle;
- funding-event timestamp, entitlement boundary, rate, cap, floor, interval, and any
  subsequent correction;
- historical mark, index, premium, and executable trade prices;
- listings, suspensions, delistings, filter changes, and forced settlement;
- account-applicable initial/maintenance tiers and liquidation rules;
- deployable capital split between Spot purchase, isolated collateral, reserve, and
  transfer buffer;
- fee tier, spread, adverse slippage, impact, latency, rehedging, and unwind;
- partial fills, asymmetric legs, transfer delays, gaps, outages, ADL, and unknown fills;
- venue, stablecoin, custody, concentration, and total counterparty-loss scenarios;
- stale-data, no-trade, unwind, kill, and reconciliation conditions.

The official notional/leverage-bracket endpoint is signed `USER_DATA` and may include a
user-specific multiplier. The public exchange-information endpoint reports current
rules, not a historical account-independent tier series. The public funding-info
endpoint reports adjusted current settings rather than a complete point-in-time change
history. Therefore a historical liquidation and capital model cannot be reproduced
from the authoritative public evidence currently identified.

### Cost, capital, and risk feasibility

Status: **FAIL**.

A static fee/slippage toggle cannot bound a two-leg strategy whose loss distribution is
dominated by margin and counterparty discontinuities. Assuming “unlevered notional” does
not remove liquidation: the short perpetual still requires collateral and venue-defined
maintenance treatment. Excluding liquidation or replacing historical tiers with current
tiers would simplify away a dominant risk and violate the task rule.

### Canonical and operational fit

The repository can retain a research-only multi-leg identity and pure accounting
fixtures. It cannot yet map the identity to point-in-time contracts, collateral,
liquidation, atomic/asymmetric fills, or reconciliation. The shortest lawful route is
therefore longer than for a Spot-only candidate and additionally crosses the D-001
derivative boundary and later HG-4 venue facts.

### Family decision

`REJECT_FOR_THIS_CYCLE`.

This does not assert that carry has no economic premium. It asserts that the current
authoritative evidence cannot support the complete model required to decide whether the
premium survives its dominant risks.

## Candidate review: long-only Spot cross-sectional momentum

### Mechanism and falsifiability

The hypothesis is that assets with stronger trailing returns than contemporaneous peers
continue to outperform weaker peers over the next holding interval. It is false for the
proposed Spot context if a train-only ranking rule fails chronological validation after
turnover, delistings, cash drag, capacity, and the complete family search are included.

This is economically distinct from B2/B4: selection is relative across a contemporaneous
universe, not a single asset's moving average or breakout level.

### Primary evidence and transfer limit

Liu, Tsyvinski, and Wu document cryptocurrency market, size, and momentum factors in a
broad 2014-2018 cross-section. Their momentum construction sorts weekly into portfolios
and evaluates a winner-minus-loser long-short return. They also note shorting limitations
and stronger momentum among larger coins.

That is good hypothesis evidence and poor proof for this proposed implementation:

- the source universe is broad CoinMarketCap data, not Binance Spot listings;
- the reported construction is long-short, while the lawful early TradingOS candidate
  would be long-only with cash;
- the study period and market structure are old relative to this cycle;
- its portfolio formation, market-cap inputs, and execution costs are not inherited;
- the local exploratory implementation searched lookbacks, top-K, rebalance intervals,
  universe sizes, a cash filter, and volatility targeting on historical data already
  viewed by the project.

### Point-in-time universe and data

Binance publishes Spot trades/klines and current exchange information. The current API
can distinguish statuses such as `TRADING`, `HALT`, and `BREAK`, but current state is not
a historical lifecycle record. Archive availability alone does not establish what symbol
status, filter, or delisting information was knowable on every rebalance date.

Required before admission:

- an enumerated USDT Spot universe at every decision time;
- inclusion of later-delisted assets and explicit terminal valuation/unwind policy;
- listing, suspension, redenomination, symbol-change, filter, and data-gap records;
- causal trailing liquidity eligibility using only then-available quote volume;
- stablecoin, leveraged-token, wrapped-asset, duplicate-underlying, and anomalous-symbol
  exclusion rules frozen before ranking;
- realistic turnover, spread, slippage, impact, capacity, and minimum-notional handling;
- exact cash return assumption and opportunity-cost benchmark.

### Canonical and search fit

Current canonical rules do not own a point-in-time multi-asset ranking, top-K portfolio,
cash sleeve, rebalance turnover, or portfolio-level fill/accounting semantics. Existing
scripts are exploratory and bypass immutable end-to-end strategy ownership. Converting
their prior best configuration would inherit result-driven selection and violate D-049.

### Sample and route

Weekly decisions over roughly five years provide many cross-sectional observations but
only a modest number of independent market regimes. Spot-only operation avoids short
borrow, margin, and liquidation, so this family has a shorter operational path than
carry. The path remains blocked at data, canonical ownership, and clean search lineage.

### Family decision

`REJECT_FOR_THIS_CYCLE`.

The family is not declared dead. A later candidate needs a newly frozen point-in-time
universe and must not inherit the exploratory `0.9456`/`0.9091` diagnostics or their
selected configurations.

## Candidate review: volatility-managed Spot exposure

### Mechanism and falsifiability

The hypothesis is that expected return does not rise proportionally with realized
volatility, so reducing unlevered Spot exposure when a causally estimated volatility
forecast is high may improve risk-adjusted outcomes after turnover and cash drag.

It is false for the exact context if a predeclared estimator and sizing rule fail to
improve the governed after-cost objective against both buy-and-hold and cash under
chronological unseen evaluation, or if any improvement is an artifact of leverage,
selection, a volatility spike, or unmodeled trading costs.

### Primary evidence and conflict

Moreira and Muir report improved Sharpe ratios from volatility-managed factor exposure
and attribute the result to volatility changes not being offset by proportional expected
return changes. This is not cryptocurrency-specific proof.

DeMiguel and coauthors later report that the original individual-factor strategies fail
out of sample and after transaction costs, while proposing a different multifactor
construction. This is material counterevidence: it prevents treating volatility scaling
as a settled edge and strengthens the requirement for a small, exact, unseen test.

### Data, capital, and operational fit

For a fixed BTCUSDT Spot context, checksum-pinned daily OHLCV is already restorable.
Unlevered exposure and cash avoid margin, borrow, liquidation, and multi-leg asymmetry.
Fees, adverse slippage, cash drag, exposure caps, turnover, gaps, and stale data are
feasible to model. This is the shortest operational route of the three candidates.

### Why it still fails admission

- volatility targeting was already used as an overlay in local multi-asset searches;
  the repository has seen performance diagnostics from those searches;
- adopting a nearby standalone rule now would be a result-aware family refinement unless
  a genuinely fresh source/context and hierarchy are frozen;
- the current canonical sizing types do not express continuously variable causal
  exposure. Encoding it as `fixed_fraction` would be semantic overloading;
- reducing the family to a binary volatility threshold would be a different hypothesis
  from the primary inverse-variance construction and would require its own source and
  selection rationale;
- roughly 2,000 daily observations across only a few crypto regimes make apparent Sharpe
  improvements vulnerable to one or two crisis intervals;
- no untouched evaluation context has been identified that is both independent of the
  prior local searches and non-overlapping with the sealed V2 boundary.

### Family decision

`REJECT_FOR_THIS_CYCLE`.

Implementation simplicity cannot cure contaminated admission or missing canonical
semantics.

## Comparative operational assessment

| Dimension | Funding/basis carry | Cross-sectional momentum | Volatility-managed Spot |
|---|---|---|---|
| Primary economic exposure | funding/basis/counterparty | relative-strength and market beta | managed market beta/cash |
| Proposed instruments | Spot + perpetual | multiple Spot + cash | one Spot + cash |
| Realistic decision frequency | funding event/rebalance | weekly/biweekly | daily sizing observation |
| Sample concern | many events, few independent funding/counterparty regimes | many ranks, few independent regimes and changing universe | many days, few crisis regimes |
| Venue dependence | very high | medium | low |
| Counterparty tail | dominant | Spot custody/stablecoin | Spot custody/stablecoin |
| Capital model complexity | very high | medium | low |
| Canonical gap | execution semantics | ranking/portfolio semantics | dynamic-sizing semantics |
| Shortest lawful route | longest | medium | shortest |
| Non-compensable blocker | historical margin/liquidation/lifecycle | point-in-time universe + contaminated search | contaminated search + semantic ownership |

## Source record

All web sources below were retrieved `2026-07-13T11:42:30Z`. URLs identify the
authoritative record used; no source provides profitability or venue approval.

### `SRC-FS-01` — Binance public data

- URL: <https://github.com/binance/binance-public-data>
- Authority: official Binance GitHub repository; primary technical/data source.
- Publication/version: repository state retrieved on the timestamp above; MIT license.
- Claim supported: daily/monthly Spot and futures archives, endpoint-derived schemas,
  all-symbol support, checksum companions, and disclosed archive replacements.
- Scope: public market-data files only.
- Limitation: current-pair enumeration and archive files do not constitute a complete
  point-in-time listing/filter/contract-rule history; upstream files can be replaced.
- Confidence: high for archive interface; low for lifecycle completeness.

### `SRC-FS-02` — Binance Spot API exchange information

- URL: <https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#exchange-information>
- Authority: official Binance Spot API documentation; primary technical source.
- Publication/version: repository state retrieved on the timestamp above.
- Claim supported: `/api/v3/exchangeInfo` returns current trading rules, symbol
  information, permissions, and current `TRADING`/`HALT`/`BREAK` filters.
- Scope: current API behavior.
- Limitation: does not claim to be a historical symbol-status or filter archive.
- Confidence: high.

### `SRC-FS-03` — Binance USD-M futures market data

- URL: <https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data#get-funding-rate-history>
- Authority: official Binance developer documentation; primary technical source.
- Publication/version: page last modified `2026-07-13`; retrieved above.
- Claim supported: funding history includes symbol, funding rate/time, and associated
  mark price; funding info exposes adjusted cap/floor/interval; mark/index/trade klines
  and current exchange information are public interfaces.
- Scope: USD-M futures API.
- Limitation: current funding-info and exchange-info responses are not documented as a
  complete historical parameter-change archive.
- Confidence: high for documented fields; low for historical completeness.

### `SRC-FS-04` — Binance USD-M notional/leverage brackets

- URL: <https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/account#notional-and-leverage-brackets>
- Authority: official Binance developer documentation; primary technical source.
- Publication/version: retrieved above.
- Claim supported: `/fapi/v1/leverageBracket` is signed `USER_DATA`, requires an API
  key, and may return a user symbol bracket multiplier.
- Scope: current account-applicable USD-M bracket query.
- Limitation: no unauthenticated historical tier series is provided by this record.
- Confidence: high.

### `SRC-FS-05` — Common Risk Factors in Cryptocurrency

- URLs: <https://www.nber.org/papers/w25882> and
  <https://doi.org/10.1111/jofi.13119>
- Authority: NBER working paper and 2022 *Journal of Finance* publication; primary
  academic source.
- Publication: Liu, Tsyvinski, and Wu; working paper issued May 2019; published 2022.
- Claim supported: market, size, and momentum factors describe the studied 2014-2018
  cryptocurrency cross-section; weekly long-short momentum sorts were significant in
  that sample.
- Scope: broad CoinMarketCap universe, weekly factor portfolios, historical sample.
- Conflict/limitation: shorting and broad-universe assumptions do not transfer to a
  Binance Spot long-only candidate; results are not a current execution study.
- Confidence: high as hypothesis evidence; low as implementation proof.

### `SRC-FS-06` — Volatility-Managed Portfolios

- URL: <https://doi.org/10.1111/jofi.12513>
- Authority: 2017 *Journal of Finance* article; primary academic source.
- Publication: Moreira and Muir, volume 72, pages 1611-1644.
- Claim supported: the authors report improved risk-adjusted outcomes from reducing
  factor exposure when volatility is high and give a risk-return mechanism.
- Scope: studied factor portfolios, not a Binance BTC Spot strategy.
- Limitation: no local formula, parameter, performance, or approval is inherited.
- Confidence: high for the paper's claim; low for crypto transfer.

### `SRC-FS-07` — A Multifactor Perspective on Volatility-Managed Portfolios

- URL: <https://doi.org/10.1111/jofi.13395>
- Authority: 2024 *Journal of Finance* article; primary academic source.
- Publication: DeMiguel, Martín-Utrera, and Uppal.
- Claim supported: the authors report out-of-sample and after-cost failures for the
  original individual-factor approach and propose a different conditional multifactor
  method.
- Scope: factor portfolios, not cryptocurrency.
- Conflict: material counterevidence to treating basic volatility management as a
  settled general edge.
- Confidence: high.

### `SRC-FS-08` — Multiple-testing methods

- URLs: <https://scholarworks.wmich.edu/math_pubs/42/> and
  <https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf>
- Authority: primary PBO and DSR method papers.
- Claim supported: selection populations and non-normality/multiple testing must be
  retained and governed rather than judging one best backtest.
- Scope: validation method; does not validate any candidate.
- Confidence: high, subject to the existing mandatory stats-specialist review before a
  future G10 PASS is honored.

## Rejected assumptions

- Public funding history is not a complete carry model.
- “Delta-neutral” does not mean capital-neutral, liquidation-proof, or
  counterparty-neutral.
- A current exchange-info response is not a point-in-time universe.
- An archive ending after a delisting does not by itself encode the causal unwind that
  was possible at that time.
- A long-short academic factor result does not validate a long-only Spot adaptation.
- A low-complexity strategy is not admissible when its selection was influenced by
  already-viewed results.
- More bars or funding events do not create more independent market regimes.
- A numeric DSR close to a threshold is not evidence for selecting the family that
  produced it.
- A research-only multi-leg spec is not a bot or venue adapter.

## Required next bounded selection cycle

Task 2 must not start because no family was selected. The next safe action remains
Task 1 and is limited to source/data feasibility, not parameter evaluation.

Create `FAMILY-SELECT-V2` with no more than three fresh mechanisms and require, before
admission:

1. an exact primary hypothesis source and an explicit contradiction search;
2. a data-feasibility proof that enumerates exact source bytes, lifecycle fields,
   licensing, availability timing, and an offline restoration route;
3. a canonical-fit proof naming every required field and any minimal schema extension;
4. an exact capital/cost/risk ledger and family-specific tail scenarios;
5. a declaration of every prior local search that could contaminate the family;
6. a holdout plan that neither touches nor leaks the sealed V2 BTCUSDT interval;
7. a bounded family hierarchy and stop rule frozen before any result is computed.

A previously reviewed family may re-enter only with new evidence that directly closes
its failed gate. Prior performance cannot be that new evidence.

## Acceptance and verification

This dossier is complete when:

- exactly three distinct candidates and no hidden candidate are recorded;
- every task-requested comparison dimension is addressed;
- every material current claim has an official/primary source, retrieval time, scope,
  conflict, confidence, and limitation;
- the outcome is exactly one of `GO` or `NO_GO` and is `NO_GO` here;
- no StrategyVersion, parameter search, new campaign, bot, venue session, credential,
  order, or sealed-holdout score was created;
- repository state records agree that execution authority remains `NONE` and Task 1
  remains the active stage for a new bounded selection cycle.

## Safety statement

This work was source and repository research only. It did not request or inspect
secrets, connect to an account, enable authenticated networking, activate the local
paper simulator, place or simulate a venue order, authorize any human gate, or access
the sealed V2 prospective holdout. No profitability claim is made.
