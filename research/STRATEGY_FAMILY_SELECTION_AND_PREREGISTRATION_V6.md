# Strategy family selection and preregistration V6

Status: **GO — `FAM-CFTC-BTC-POSITIONING-01` admitted to data packaging only**  
Decision class: constrained-S2 source/data feasibility; no family performance computed  
Execution authority: `NONE`  
Retrieved: 2026-07-13 UTC

## Decision

This cycle compares exactly three mechanisms that are distinct from the closed price, calendar,
carry, funding-pressure, cross-sectional, options, stablecoin, miner-recovery,
transaction-count, and MVRV contexts:

1. regulated CME Bitcoin-futures trader positioning reported by the CFTC;
2. Bitcoin blockspace fee pressure; and
3. dormant Bitcoin supply reactivation.

Only CFTC positioning advances. The hypothesis is that unusually one-sided reportable futures
positioning can proxy informed demand, hedging pressure, or crowded speculation and may precede a
one-week BTCUSDT Spot long/cash pulse. Both trend-aligned and contrarian signs remain in the frozen
roster because the source literature does not justify choosing direction before local evidence.
No positioning-conditioned return, direction, trade count, Sharpe, drawdown, or equity statistic
was computed before this decision.

## Source-backed comparison

| Candidate | Mechanism | Point-in-time feasibility | Counterevidence / dominant risk | Outcome |
|---|---|---|---|---|
| `FAM-CFTC-BTC-POSITIONING-01` | Reportable futures positioning may express informed demand, hedging pressure, or crowding before that information is fully reflected in Spot | PASS_WITH_RELEASE_LEDGER: CFTC publishes weekly Futures Only reports, annual compressed files, historical weekly views, a release schedule, and official exception announcements; CME Bitcoin is legacy code `133741` | Tuesday positions are normally published Friday; shutdown/cyber/holiday delays must use actual release dates; public categories are coarse, classification can change, and only about 8.5 years exist | **GO to exact packaging** |
| `FAM-BTC-BLOCKSPACE-FEE-01` | Higher fees price scarce blockspace and may proxy urgent network demand | Daily public fee/revenue metrics and Bitcoin ledger reconstruction are feasible | Fees are jointly driven by protocol capacity, batching, inscriptions, congestion, BTC price, and transaction demand; the candidate is adjacent to the rejected transaction-activity and miner contexts, and the literature establishes fee-market mechanics rather than robust return direction | NO_GO |
| `FAM-BTC-DORMANT-SUPPLY-01` | Movement of old UTXOs may proxy long-holder distribution or renewed economic activity | Coin-days/dormancy can be reconstructed from the public ledger and some public metric feeds | A movement is not a sale; self-transfers, custody reshuffles, mixers, change, lost coins, and age normalization dominate interpretation; it is adjacent to the closed MVRV holder-cost context and lacks stable causal direction | NO_GO |

## Evidence classification

### Verified facts

- CFTC says COT reports break down Tuesday open interest and are normally released Friday at
  3:30 p.m. Eastern time.
- The CFTC annual Futures Only archives include 2017 through 2026, and historical weekly pages
  explicitly label their dates as report dates rather than release dates.
- The CME full-size Bitcoin contract appears as `BITCOIN - CHICAGO MERCANTILE EXCHANGE`, legacy
  market code `133741`, with non-commercial long, short, spreading, commercial, nonreportable,
  open-interest, concentration, and trader-count fields.
- CFTC's official exception ledger records material publication delays, including the
  2018-2019 appropriations lapse, the February-March 2023 ION incident, the January 2025 day of
  mourning, and the October-November 2025 appropriations lapse.
- CFTC economists find that the composition of CME Bitcoin-futures traders changes over time and
  that the Micro Bitcoin contract has a different trader composition from the full-size contract.
- Hung, Liu, and Yang use CFTC COT data and report that trader groups contribute differently to
  Bitcoin-futures price discovery; this supports falsifiability, not a promised directional edge.
- Bitcoin fee research models transaction fees as the price of scarce blockspace, while dormancy
  research establishes what coin-days measure; neither establishes a stable Spot-return sign for
  the proposed alternatives.

### Inferences and hypotheses

- Non-commercial net position divided by open interest is a scale-normalized public proxy, not a
  direct observation of every institutional investor, motive, or trade.
- Positive and negative standardized extremes are competing hypotheses. The campaign may not
  choose the sign after observing results.
- A Spot response to futures positioning would be predictive association, not proof that futures
  traders caused the move or possessed private information.

### Unknowns retained

- Public COT categories aggregate heterogeneous traders and may not preserve a constant economic
  identity across the sample.
- Annual compressed files can reflect later corrections; they are not immutable contemporaneous
  download vintages.
- Exact release timestamps for exceptional reports must be derived only from official CFTC
  schedules/announcements. Any unresolved report is unavailable, not assigned the normal lag.
- The sample begins with CME Bitcoin futures in December 2017 and therefore spans few structural
  regimes compared with mature futures markets.

## Data contract to freeze before scoring

- Primary feature source: exact CFTC Public Reporting Environment Legacy Futures Only filtered
  CSV response and dataset metadata for `CFTC_Contract_Market_Code=133741`. The annual compressed
  archive index remains an independent availability reference; exclude Micro Bitcoin `133742`,
  CBOE, options-combined, and disaggregated/TFF mixtures.
- Required fields: market name/code, report date, open interest, non-commercial long, short and
  spreading, commercial long/short, nonreportable long/short, changes, percentages, and trader
  counts where published. Preserve every raw field even when the strategy uses fewer.
- Feature: `(noncommercial_long - noncommercial_short) / open_interest`; open interest must be
  positive. Spreading is retained but excluded from the directional numerator.
- Publication ledger: retain the ordinary release schedule and all relevant official historical
  special announcements. Ordinary availability is conservatively report date plus eight calendar
  days at `00:00 UTC`, later than the documented normal Friday release and ordinary one/two-day
  holiday delays. Shutdown, cyber, postponement, or catch-up releases use the later of that rule
  and UTC midnight after the official actual publication date. If an exact exceptional date is
  unresolved, quarantine that report and reset the consecutive-feature window.
- Executed instrument: retained Binance Spot `BTCUSDT` 1h, unlevered long/cash only. The strategy
  never opens a CME future, derivative, short, margin, or leveraged position.
- Fill: first retained hourly open strictly after feature availability. A delayed report cannot be
  backfilled to its originally scheduled date.
- Preserve exact ZIP bytes, extracted-member hashes, normalized logical hash, source URLs,
  retrieval UTC, schema, duplicates, omissions, corrections, and publication exceptions.
- Network access is prohibited during campaign execution.

## Complete trial roster to freeze

Exactly 12 trials are declared:

- positioning interpretation: `ALIGNED_HIGH` and `CONTRARIAN_LOW`;
- prior baseline: `13`, `26`, and `52` consecutive available weekly reports; and
- absolute population-z threshold: `0.5` and `1.0`.

For report `R`, compute the current normalized net-position feature. From the immediately prior
complete window, excluding `R`, compute population mean and population standard deviation.
`z_R = (feature_R - prior_mean) / prior_population_std`.

- `ALIGNED_HIGH` enters when `z_R > threshold`.
- `CONTRARIAN_LOW` enters when `z_R < -threshold`.
- Equality, zero standard deviation, a missing/late/unresolved publication, or an invalid row
  produces no signal.
- Entry creates a seven-complete-day Spot pulse. Signals while held do not stack or extend it.
- Exit is the first retained hourly open at least 168 hours after entry.
- No alternate COT report, trader-category blend, Micro contract, sign, threshold, lookback,
  holding period, price filter, smoothing, asset, timeframe, ensemble, or sizing rule may be added
  after scoring.

## Preregistered validation skeleton

- Development: 2018-01-01 through 2022-12-31.
- Validation: 2023-01-01 through 2024-12-31.
- Family-unseen reserve: 2025-01-01 through the last frozen 2026 report.
- A later campaign freeze must verify adequate usable observations after publication quarantine;
  otherwise this GO converts to operational `NO_GO` before any return is computed.
- Phase one evaluates all 12 development trials at F1/S1, writes and hashes one selected
  StrategyVersion, and computes family G10. Phase two may evaluate only that selected version
  outside development.
- Selection metric: non-annualized per-1h-bar Sharpe including zero cash returns; lexical
  `(interpretation, baseline_weeks, threshold)` tie break.
- Six cost cells, cash and buy-and-hold benchmarks, PBO/DSR, drawdown, annual/regime slices,
  one-report delay, event minima, four-role parity, G1-G11, and independent supervisor review must
  be at least as strict as the closed MVRV campaign.

## Stop and no-rescue rules

- Any source, row identity, correction, release date, timezone, schema, hash, roster, cost, split,
  selection barrier, or gate mismatch aborts.
- Any delayed report used before its actual publication time invalidates the entire campaign.
- Any hard failure, conformance residual, inadequate OOS event count, or sequence violation
  rejects the exact context.
- Do not combine full-size and Micro Bitcoin contracts or reinterpret category labels as verified
  trader intent.
- Do not access the sealed V2 holdout or reuse a closed-family result.
- Numeric PASS cannot activate a bot, venue, credentials, paper/demo/live state, or orders.

## Exact next action

Freeze the exact filtered CFTC Legacy Futures Only API response and metadata, the official
schedule/exception evidence, and the code-`133741` normalized rows into an offline data package.
Verify source bytes, schema, identities, duplicates, chronology, conservative publication
availability, exceptional delays, feature arithmetic, coverage, and strict-next-Spot-open mapping.
Do not compute a
positioning-conditioned return before that package and the full campaign are committed cleanly.

## Sources

- CFTC About the COT Reports: https://www.cftc.gov/MarketReports/CommitmentsofTraders/AbouttheCOTReports/index.htm
- CFTC Historical Compressed: https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm
- CFTC Historical Viewable: https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalViewable/index.htm
- CFTC Release Schedule: https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm
- CFTC Historical Special Announcements: https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm
- CFTC 2019 delayed-report schedule: https://www.cftc.gov/PressRoom/PressReleases/7864-19
- CFTC 2023 ION postponement: https://www.cftc.gov/PressRoom/PressReleases/8662-23
- CFTC `Who Trades Bitcoin Futures and Why?`: https://www.cftc.gov/sites/default/files/2021-11/WhoTradesBTC_V2_ada.pdf
- Bitcoin-futures price discovery: https://doi.org/10.1016/j.jempfin.2021.02.001
- Bitcoin transaction-fee market: https://doi.org/10.1016/j.intfin.2021.101282
- Bitcoin fee-market evolution: https://doi.org/10.1016/j.jfineco.2019.03.004
- Bitcoin average dormancy: https://arxiv.org/abs/1712.10287
