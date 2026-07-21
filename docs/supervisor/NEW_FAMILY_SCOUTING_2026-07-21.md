# New-family scouting — community strategy libraries (2026-07-21)

Status: **HYPOTHESIS-SOURCING ONLY.** Authorized by operator 2026-07-21 as a follow-up
to `docs/supervisor/STATISTICAL_REMEDIATION_PLAN_D112_2026-07-21.md`. No backtests, no
code changes to validation, no campaign runs, no evidence claims. Every mechanism below
is an idea to evaluate for pre-registration, not a result. Nothing here reopens a closed
family or re-parameterizes one.

## Closed families this scouting must not reproduce

Per `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V*.md`,
`docs/supervisor/STATISTICAL_REMEDIATION_PLAN_D112_2026-07-21.md`, and
`DECISION_LOG.md`, the following are **closed** (searched-and-FAILED under D-112's
corrected statistics, or COMPLETED_REJECTED at an earlier gate) and may not be
re-searched under the stop rules:

1. `FAM-VOL-CONTRACTION-BREAKOUT-V1` — single-asset low-vol-regime range breakout (trend/technical).
2. `FAM-BTC-SPOT-TAKER-IMBALANCE` — signed taker-buy/sell volume imbalance (order-flow/volume).
3. `CROSS-VENUE-BTC-PREMIUM` — same-asset price spread across venues (venue-basis).
4. `BTC-MVRV` — market-value-to-realized-value on-chain valuation ratio.
5. `CFTC-BTC-POSITIONING` — CME COT large-trader positioning.
6. `BTC-TX-ACTIVITY` — on-chain transaction-count/network-usage.
7. `FUNDING-PRESSURE-SPOT` — single-asset (BTC) time-series funding-rate directional signal.
8. `FAM-CALENDAR-UTC-01` — calendar/time-of-day/day-of-week seasonality (COMPLETED_REJECTED, D-053).

Also NO_GO at the source-feasibility gate (not evidence-closed, but not novel and blocked
on data access): exchange-flow PIT (`FAM-BTC-EXCHANGE-FLOW-PIT-01`, proprietary entity
labels), forced-liquidation stress (`FAM-BTC-FORCED-LIQUIDATION-STRESS-01`, incomplete
archive), CME curve roll (`FAM-CME-BTC-CURVE-ROLL-01`, licensed data only), perp
open-interest crowding (`FAM-PERP-OI-CROWDING-01`, only 30-day REST window), macro
dollar-liquidity (`FAM-MACRO-DOLLAR-LIQUIDITY-01`, hidden-search burden too large).

## Data the project already holds

`data/normalized_multi/` contains checksum-traceable spot klines (1h/4h/1d) for **43
symbols** (BTC, ETH, and ~41 large-cap alts: ADA, SOL, AVAX, LINK, DOT, MATIC, ATOM, NEAR,
etc.) — this is a materially larger cross-sectional universe than any of the 7 closed
BTC-only families used, and it is already sitting in the repo. This matters below:
several candidates need nothing new to download.

---

## Candidates

### 1. Cross-sectional altcoin momentum/factor

**Mechanism.** Rank the ~43-symbol universe by trailing return over a lookback (e.g.
1–4 weeks); go long top-decile, short (or underweight) bottom-decile, rebalance
periodically. A cross-sectional relative-strength factor, not a price-level timing rule.

**Distinct from.** Nearest closed family: `FAM-VOL-CONTRACTION-BREAKOUT-V1` (single-asset,
absolute price/range trigger, no ranking). Cross-sectional momentum's signal is *relative
rank across assets at a point in time*, mechanically unrelated to one asset's own
volatility regime. Also distinct from `CROSS-VENUE-BTC-PREMIUM` (same asset, different
venues) — this is different assets, same venue.

**Data.** Already held: 43-symbol spot klines in `data/normalized_multi/`. No new
download needed for a first pass; would need point-in-time listing-date handling
(new listings inflate momentum returns) — the project doesn't have a delisting-complete
universe (flagged blocked in `PROJECT_STATE.md` as SUP-009), so survivorship bias is a
known, not-fully-closeable risk with the currently held universe.

**Evidence quality.** Primary academic: Liu, Tsyvinski, Wu-style cross-sectional momentum
work and the CTREND factor paper (JFQA); Bianchi & Babiak risk-based factor model.
[A Trend Factor for the Cross-Section of Cryptocurrency Returns](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4601972) (SSRN/JFQA);
[Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf) (realistic-assumptions replication);
[Cryptocurrency momentum has (not) its moments](https://link.springer.com/article/10.1007/s11408-025-00474-9) (Springer, cautionary replication).

**Failure modes.** Survivorship/listing bias (no delisting-complete universe held);
momentum crashes on sharp reversals (documented in the literature — "a short position
inflicts a significant loss... due to large jumps"); factor decays with market-cap size;
cross-sectional rebalancing on 43 correlated large-caps may have far fewer independent
degrees of freedom than 43 looks like (most alts co-move with BTC).

**Priority: HIGH** — data already in repo, clean mechanism distinct from every closed
family, multiple independent academic replications including a skeptical one.

---

### 2. Cointegrated multi-asset stat-arb pairs

**Mechanism.** Test pairs (or small baskets) of large-cap coins for cointegration
(Engle-Granger / Johansen), trade the mean-reverting spread when it diverges from its
historical relationship, exit on reversion.

**Distinct from.** Nearest closed family: `CROSS-VENUE-BTC-PREMIUM` — that was the
*same* asset (BTC) priced on different venues; this is *different* assets on the same
venue, a genuinely different economic mechanism (relative-value comovement between
distinct tokens vs a single fungible asset's cross-market price gap).

**Data.** Already held: spot klines for BTC/ETH/BCH/LTC-equivalent large caps and more in
`data/normalized_multi/`. No new download needed for the core large-cap pairs the
published research uses.

**Evidence quality.** [Constructing cointegrated cryptocurrency portfolios for statistical arbitrage](https://ideas.repec.org/a/eme/sefpps/sef-08-2018-0264.html) (Studies in Economics and Finance / Emerald, peer-reviewed) reports Sharpe 1.58–2.45 on BTC/ETH/BCH/LTC portfolios;
a broader cross-sector cointegration study found 31 significantly cointegrated pairs;
[Statistical Arbitrage Strategies Using Cointegration Analysis in Cryptocurrency Markets](https://ijsra.net/sites/default/files/fulltext_pdf/IJSRA-2026-0283.pdf) (2026, working-paper quality — treat as secondary, not peer-reviewed).

**Failure modes.** Cointegration relationships are not stable regime-to-regime (a "hard
regime shift" — e.g., a chain fork, a de-peg event, or a listing/delisting — breaks the
relationship with no warning); classic pairs-trading overfitting risk is picking the
pair(s) post-hoc from a large combinatorial search over 43 symbols (this must be
pre-registered as a family-wide search, not "we tried pairs until one worked" — the
project's own trial-budget ledger already exists to prevent exactly this).

**Priority: HIGH** — data already in repo, strongest peer-reviewed Sharpe of the
candidates surveyed, clearly distinct mechanism, and the project's existing trial-budget
machinery (`trial_budget.py`) is a good structural fit for controlling the pair-selection
search.

---

### 3. Cross-sectional perpetual funding-rate carry basket

**Mechanism.** Across many perpetual-swap symbols simultaneously, go short (delta-hedged
or basket-net) the highest-funding perpetuals and long the lowest-funding ones — a
market-neutral cross-sectional carry factor, rebalanced periodically.

**Distinct from.** Nearest closed family: `FUNDING-PRESSURE-SPOT` — that was a
*single-asset (BTC) time-series* signal (is funding pressure on BTC alone predictive of
BTC's own next move). This candidate is a *cross-sectional relative-value* basket across
many assets simultaneously, market-neutral by construction, which is a structurally
different bet (relative funding level across the universe, not one asset's own funding
history).

**Data.** Binance funding-rate history is a public REST endpoint per symbol
(`fapi/v1/fundingRate`), free to download; the project already ingests Binance data but
does not appear to hold funding-rate history for the full 43-symbol universe (only BTC
funding was packaged for the closed family) — this candidate needs a new, otherwise
straightforward, public-data download across the held-symbol perpetual universe.

**Evidence quality.** [BIS Working Papers No 1087 — Crypto carry](https://www.bis.org/publ/work1087.pdf) (Bank for International Settlements, primary institutional research) reports a
2020–2025 annualized Sharpe of 6.45, degrading to 4.06 by 2024 and negative in 2025 —
i.e., the published edge is explicitly documented as decaying/crowded; treat the older
headline Sharpe with corresponding skepticism.
[The Crypto Carry Trade](https://www.andrew.cmu.edu/user/azj/files/CarryTrade.v1.0.pdf) (CMU working paper, secondary/academic).

**Failure modes.** BIS's own data shows the edge decaying to negative by 2025 — this is
a crowded, well-published trade, exactly the kind of thing multiple-testing/decay
concerns apply to; funding can flip sign abruptly around liquidation cascades, breaking
the market-neutral assumption; basket construction needs careful handling of the same
survivorship-bias gap noted in candidate 1.

**Priority: MEDIUM** — mechanism is genuinely distinct and cheap to source, but the best
available institutional evidence says the edge has already decayed to negative in the
most recent (2025) sample, which lowers the expected value of spending a pre-registration
slot on it right now versus candidates 1–2.

---

### 4. On-chain SOPR-based realized-profit/loss signal

**Mechanism.** Spent Output Profit Ratio — the realized-value/cost-basis ratio of coins
that moved on-chain in a period — used as a capitulation (SOPR sharply < 1, resets to
1 from below) or euphoria (SOPR persistently > 1) signal, distinct from a simple
valuation ratio.

**Distinct from.** Nearest closed family: `BTC-MVRV` — MVRV compares aggregate market
cap to aggregate realized cap (a valuation-level ratio); SOPR is a *flow* metric over
only the coins that moved in a window, weighted by their individual cost basis at
creation, capturing behavioral profit-taking/capitulation rather than the whole supply's
valuation. Also distinct from `BTC-TX-ACTIVITY` (raw count of transactions/network
usage, no profit/loss dimension at all).

**Data.** Reconstructing raw SOPR from Bitcoin Core requires tracking every UTXO's
creation-time price and matching it to its spend-time price at the individual-output
level — meaningfully heavier engineering than the already-closed on-chain families
(MVRV, tx-activity) which used simpler aggregate/public series. Vendor APIs
(CryptoQuant, Glassnode) publish SOPR directly but gate history behind paid tiers/API
keys, the same "proprietary, not reconstructible from public chain data" wall that sank
`FAM-BTC-EXCHANGE-FLOW-PIT-01`.

**Evidence quality.** Mostly practitioner/vendor sources, not peer-reviewed: [CryptoQuant SOPR guide](https://dataguide.cryptoquant.com/utxo-data-indicators/spent-output-profit-ratio-sopr), [ChainExposed SOPR](https://chainexposed.com/SOPR.html), [Bitcoin Magazine Pro SOPR chart](https://www.bitcoinmagazinepro.com/charts/sopr-spent-output-profit-ratio/) — no SSRN/academic paper found establishing
out-of-sample predictive power; every source explicitly cautions it is "a behaviour
layer, not a trade trigger," to be combined with other indicators.

**Failure modes.** Same PIT/reconstructability problem that closed the exchange-flow
candidate; weak, vendor-only evidence base (no peer-reviewed validation found); if
sourced from a paid API, look-ahead/revision risk in vendor recomputation.

**Priority: LOW** — data-access profile mirrors an already-NO_GO'd sibling, and the
evidence base is practitioner blog posts, not research.

---

### 5. Crypto options volatility risk premium (short variance)

**Mechanism.** Systematically sell 30-day at-the-money variance (via Deribit DVOL vs.
realized volatility) when implied consistently exceeds realized, harvesting the
documented variance risk premium.

**Distinct from.** No closed family touches derivatives volatility surfaces at all; the
nearest closed family by asset class is `FUNDING-PRESSURE-SPOT` (also a perp-market
signal), but the mechanism here is a volatility/options-surface premium, not a
directional or funding-flow signal — economically unrelated.

**Data.** Deribit's DVOL index is a free public index; realized volatility is
computable from klines the project already holds. However, *trading* variance requires
an options-execution and margin/greeks accounting layer the project's engines
(freqtrade/vectorbt/nautilus wiring reviewed in `research/SOURCE_REGISTRY.md`) are not
currently built for — this is an infrastructure gap, not just a data gap.

**Evidence quality.** [Deribit Insights — Bitcoin Options: Finding edge in four years of volatility regimes](https://insights.deribit.com/industry/bitcoin-options-finding-edge-in-four-years-of-volatility-regimes/) (venue-published, reports median VRP +14 IV points, contango-regime mean ~+15pts);
[The Bitcoin VIX and Its Variance Risk Premium](https://www.researchgate.net/publication/346500941_The_Bitcoin_VIX_and_Its_Variance_Risk_Premium) (peer-reviewed-adjacent, ResearchGate listing).

**Failure modes.** Short-variance strategies have a classic negatively-skewed payoff
(steady small gains, occasional large loss on vol spikes — exactly the tail risk a VRP
harvest is supposed to monetize); venue-published evidence (Deribit itself) has an
obvious incentive to show options markets as attractively mispriced; needs an options
execution/margin module the project does not have.

**Priority: LOW** — mechanism is genuinely novel and evidence is reasonable, but the
missing options-infrastructure layer means this would need an architecture change before
it could even reach pre-registration, out of proportion to a hypothesis-sourcing pass.

---

### 6. Stablecoin aggregate-supply growth as a liquidity/buying-power signal

**Mechanism.** Total on-chain supply of major stablecoins (USDT, USDC) as a leading
proxy for capital ready to deploy into risk assets; rising aggregate supply growth rate
as a bullish liquidity signal, falling/flat as a caution signal.

**Distinct from.** Nearest closed-adjacent (NO_GO, not evidence-closed) family:
`FAM-BTC-EXCHANGE-FLOW-PIT-01` (exchange-labeled netflows — blocked because entity
labels are proprietary). This candidate is different: it uses each stablecoin's total
on-chain supply (an ERC-20/TRC-20 `totalSupply()` call), which is fully public and
point-in-time reconstructible from any historical block — it does not need proprietary
exchange-address labels at all, sidestepping exactly the wall that blocked the
exchange-flow candidate.

**Data.** Public block-explorer APIs (Etherscan, Tronscan) or aggregator APIs
(DefiLlama stablecoins endpoint) expose historical total supply for free; project would
need a new small ingestion script, not a new data class.

**Evidence quality.** Mostly market-commentary/vendor sources at this pass, not
peer-reviewed academic work: [DefiLlama stablecoins](https://defillama.com/stablecoins),
[KuCoin — Stablecoin Liquidity Hits $320.6B Milestone](https://www.kucoin.com/blog/Stablecoin-Liquidity-Hits-$320B-Milestone-in-May-2026),
[Federal Reserve — Stablecoins in 2025](https://www.federalreserve.gov/econres/notes/feds-notes/stablecoins-in-2025-developments-and-financial-stability-implications-20260408.html) (Fed note, institutional but macro-descriptive,
not a strategy backtest). No SSRN/peer-reviewed paper establishing predictive power was
found in this pass — treat the "leading indicator" claims in trade-press sources as
unverified marketing framing until an in-repo test exists.

**Failure modes.** Weak evidence base (no peer-reviewed source found); stablecoin
supply growth is driven by mint/redeem decisions of a handful of issuers and can reflect
regulatory/banking events unrelated to trading demand; low signal frequency (supply
changes are lumpy, not continuous) may not produce enough independent trade
opportunities to clear a trade-level significance test.

**Priority: LOW** — genuinely novel, cheap, clean data path, but weak published
evidence and likely low signal frequency versus the project's honest-activity-floor
requirement (`min_validation_trades`).

---

### 7. Attention/sentiment proxy (Google Trends search-interest)

**Mechanism.** Use Google Trends search-interest for "Bitcoin"/coin-specific terms as a
retail-attention proxy; contrarian (fade attention spikes) or momentum (ride rising
attention) framing, tested against price.

**Distinct from.** No closed family uses any text/attention data source at all; this is
categorically different from every price-, funding-, positioning-, or on-chain-based
closed family.

**Data.** Google Trends is queryable historically via the unofficial `pytrends` library
(free, no key, but rate-limited and normalized/relative rather than absolute — Google
does not publish raw search-volume counts, only a rescaled index). Twitter/Reddit
historical mention-volume APIs have been paywalled since 2023 and are not "freely
downloadable" — excluded from this candidate's scope.

**Evidence quality.** [QuantPedia — Can Google Trends Sentiment Be Useful as a Predictor for Cryptocurrency Returns?](https://quantpedia.com/can-google-trends-sentiment-be-useful-as-a-predictor-for-cryptocurrency-returns/) (research-secondary, mixed findings);
academic literature is mixed/weak: one study found tweet *volume* beat tweet *sentiment*
as a predictor, another found momentum-strategy profitability was conditional on high
market exuberance (i.e., regime-dependent, not a standalone edge).
[Predictive role of online investor sentiment for cryptocurrency market](https://www.sciencedirect.com/science/article/abs/pii/S1059056021000083) (ScienceDirect, peer-reviewed).

**Failure modes.** Google's index is normalized/relative per query window, which makes
building a single consistent historical series non-trivial (rescaling artifacts);
weekly-to-daily granularity is coarser than the project's 1h/4h bars; published effects
are described as regime-conditional, not a standalone documented edge — high
overfitting risk if a threshold is tuned post-hoc to make it "work."

**Priority: LOW** — categorically novel data source (good for diversification of
hypothesis space), but weak/mixed evidence, coarse granularity, and real data-engineering
friction (index rescaling) make it a poor use of a scarce pre-registration slot right now.

---

## Ranked shortlist — top 3

1. **Cointegrated multi-asset stat-arb pairs** (candidate 2) — strongest peer-reviewed
   evidence (Sharpe 1.58–2.45 in a published study), data already fully held, mechanism
   cleanly distinct from the same-asset cross-venue-premium family, and the project's
   existing trial-budget ledger is a natural fit for controlling the pair-selection
   search space honestly.
2. **Cross-sectional altcoin momentum/factor** (candidate 1) — data already held across
   43 symbols, multiple independent academic replications (including a properly
   skeptical one), cleanly distinct from the single-asset breakout family; main
   open risk is the project's known missing delisting-complete universe (SUP-009).
3. **Cross-sectional perpetual funding-rate carry basket** (candidate 3) — cheapest new
   data to source and mechanically the cleanest break from the closed single-asset
   funding family, but ranked third because the best available institutional evidence
   (BIS) shows the published edge decaying to negative by 2025 — lower expected value
   of a pre-registration slot than candidates 1–2 until/unless a more current source is
   found.

## Explicit reminder

**None of the above is evidence of anything.** Every candidate is an unvalidated
hypothesis sourced from public web material, not from any backtest run in this project.
Before any of these could support a claim, each would need its own pre-registered
in-repo campaign under the corrected statistical core (trade-level significance per
D-112, DSR, and the trial-budget/PBO machinery in `src/tios/validation/`), exactly like
the seven families that were already searched and failed. Nothing in this document
changes, reopens, or weakens that record.

## Sources consulted (this scouting pass, 2026-07-21)

| Source | URL | Category | Access date |
|---|---|---|---|
| A Trend Factor for the Cross-Section of Cryptocurrency Returns | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4601972 | Academic (SSRN/JFQA) | 2026-07-21 |
| Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market | https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf | Academic | 2026-07-21 |
| Cryptocurrency momentum has (not) its moments | https://link.springer.com/article/10.1007/s11408-025-00474-9 | Academic (Springer) | 2026-07-21 |
| Constructing cointegrated cryptocurrency portfolios for statistical arbitrage | https://ideas.repec.org/a/eme/sefpps/sef-08-2018-0264.html | Academic (peer-reviewed) | 2026-07-21 |
| Statistical Arbitrage Strategies Using Cointegration Analysis in Cryptocurrency Markets | https://ijsra.net/sites/default/files/fulltext_pdf/IJSRA-2026-0283.pdf | Working paper | 2026-07-21 |
| BIS Working Papers No 1087 — Crypto carry | https://www.bis.org/publ/work1087.pdf | Institutional research | 2026-07-21 |
| The Crypto Carry Trade (CMU) | https://www.andrew.cmu.edu/user/azj/files/CarryTrade.v1.0.pdf | Academic working paper | 2026-07-21 |
| CryptoQuant — SOPR guide | https://dataguide.cryptoquant.com/utxo-data-indicators/spent-output-profit-ratio-sopr | Vendor/practitioner | 2026-07-21 |
| ChainExposed — SOPR | https://chainexposed.com/SOPR.html | Vendor/practitioner | 2026-07-21 |
| Bitcoin Magazine Pro — SOPR chart | https://www.bitcoinmagazinepro.com/charts/sopr-spent-output-profit-ratio/ | Vendor/practitioner | 2026-07-21 |
| Deribit Insights — Bitcoin Options: Finding edge in four years of volatility regimes | https://insights.deribit.com/industry/bitcoin-options-finding-edge-in-four-years-of-volatility-regimes/ | Venue-published research | 2026-07-21 |
| The Bitcoin VIX and Its Variance Risk Premium | https://www.researchgate.net/publication/346500941_The_Bitcoin_VIX_and_Its_Variance_Risk_Premium | Academic | 2026-07-21 |
| DefiLlama — Stablecoins | https://defillama.com/stablecoins | Data aggregator | 2026-07-21 |
| KuCoin — Stablecoin Liquidity Hits $320.6B Milestone | https://www.kucoin.com/blog/Stablecoin-Liquidity-Hits-$320B-Milestone-in-May-2026 | Vendor/market commentary | 2026-07-21 |
| Federal Reserve — Stablecoins in 2025 | https://www.federalreserve.gov/econres/notes/feds-notes/stablecoins-in-2025-developments-and-financial-stability-implications-20260408.html | Institutional (Fed) | 2026-07-21 |
| QuantPedia — Can Google Trends Sentiment Be Useful as a Predictor for Cryptocurrency Returns? | https://quantpedia.com/can-google-trends-sentiment-be-useful-as-a-predictor-for-cryptocurrency-returns/ | Research-secondary | 2026-07-21 |
| Predictive role of online investor sentiment for cryptocurrency market | https://www.sciencedirect.com/science/article/abs/pii/S1059056021000083 | Academic (ScienceDirect) | 2026-07-21 |
| freqtrade/freqtrade-strategies (GitHub) | https://github.com/freqtrade/freqtrade-strategies | Community code repository | 2026-07-21 |

---

## ADDENDUM (2026-07-21) — candidates 1 and 2 refuted/weakened by in-repo evidence this pass missed

**Status: this scouting pass's top-ranked candidate is refuted; do not pre-register it as
currently framed.** A subsequent evidence review (see `DECISION_LOG.md` D-114) found that this
document, in surveying external community strategy libraries, missed evidence already sitting in
this repo:

- **Candidate 1 (cointegrated multi-asset stat-arb pairs), ranked #1/HIGH above, is refuted.**
  `scripts/run_stat_arb_pro.py` → `artifacts/validation/stat_arb_pro/STAT_ARB_PRO.json`
  (2026-07-12) already ran an Engle-Granger-gated, hedge-ratio, OOS-split stat-arb campaign on 1h
  data covering this exact mechanism and asset class: 5 of 10 tested pairs cointegrated in-sample
  (including ETH/BTC and BNB/BTC), every top OOS configuration negative (best annualized −11.2%),
  DSR 0.0039 against the 0.95 threshold. The recorded root cause — cointegration decay — is a
  property of the mechanism, not of pair-vs-basket cardinality, so it does not become less true
  for a Johansen-style N-asset basket. This document's distinctness argument (different mechanism
  from the closed `CROSS-VENUE-BTC-PREMIUM` family) still holds, but distinct-from-closed is not
  the same as untested: this mechanism has already been run in this project and has already
  failed.
- **Candidate 2 (cross-sectional altcoin momentum), ranked #2/HIGH above, is partly refuted.**
  `PROJECT_STATE.md` (§Strategy research arc, 2026-07-12) already recorded cross-sectional
  momentum long-only with a dual-momentum cash filter and vol targeting reaching DSR 0.9456 at 28
  pairs — the closest of any tested implementation to the 0.95 screen — but degrading to 0.9091
  at 34 pairs, i.e. fragile to universe size. Combined with the SUP-009 survivorship gap this
  document itself flagged as an open risk for this candidate, it is a weaker opportunity than
  presented above, not a clean untested opening.
- **Candidate 3 (cross-sectional funding carry)** is unaffected by this addendum; its own
  MEDIUM ranking and stated risk (BIS-documented decay to negative by 2025) stand as written
  above.

**Recorded outcome:** no new family pre-registration this cycle; no search/trial-budget slot
spent. Full reasoning and the operator's retained governance override (a Johansen multivariate
basket may still be pre-registered on the operator's own authority, notwithstanding the evidence
above, though the evidence-based recommendation is against it) are recorded in `DECISION_LOG.md`
D-114 — that entry, not this addendum, is the authoritative record of the outcome.
