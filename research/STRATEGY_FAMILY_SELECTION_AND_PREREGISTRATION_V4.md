# Strategy family selection and preregistration V4

Status: **GO — `FAM-BTC-TX-ACTIVITY-01` admitted to data packaging only**
Decision ID: `D-060`
Decision class: constrained-S2 source/data feasibility; no family performance computed
Execution authority: `NONE`
Retrieved: 2026-07-13 UTC

## Decision

This cycle compares exactly three mechanisms that are distinct from every closed price/calendar,
carry, funding-directional, options, and cross-sectional context:

1. finalized Bitcoin L1 confirmed-transaction activity shocks;
2. aggregate fiat-backed stablecoin supply growth; and
3. Bitcoin miner hash-rate/difficulty recovery.

Only the first family advances. It uses a delayed, public blockchain-activity observation to
create a short unlevered BTCUSDT Spot long/cash pulse. It does not infer wallet identity,
exchange flows, transaction value, Lightning activity, miner profitability, or stablecoin intent.
No local activity-conditioned Spot return, direction, threshold, holding-period result, trade
count, Sharpe, drawdown, or equity statistic was computed before this decision.

## Source-backed comparison

| Candidate | Mechanism | Public point-in-time feasibility | Material counterevidence / dominant risk | Outcome |
|---|---|---|---|---|
| `FAM-BTC-TX-ACTIVITY-01` | An unusual change in confirmed L1 transaction count may precede a short change in BTC demand/attention or congestion regime | PASS_WITH_LAG: Blockchain.com's official Charts API exposes UTC daily `n-transactions`; 2,187 retained observations cover 2020-07-14 through 2026-07-12 | Koutmos (2018) reports a positive third-day return response to activity shocks, while Aalborg et al. (2019) reports that its considered variables do not predict Bitcoin returns; Lightning/off-chain migration and non-economic transfers weaken interpretation | **GO to exact packaging** |
| `FAM-STABLE-SUPPLY-01` | Growth in stablecoin supply may represent crypto purchasing capacity or, conversely, late-cycle demand for settlement liquidity | Data are publicly accessible from Coin Metrics Community API without a key, but issuer/chain aggregation, migrations, burns, and historical revisions remain material | Lyons and Viswanath-Natraj find no significant BTC/ETH price response to Tether secondary-market flows; current BIS work emphasizes severe endogeneity in naive stablecoin-flow projections | NO_GO |
| `FAM-MINER-RECOVERY-01` | Hash-rate/difficulty recovery after miner stress may signal network confidence and future BTC appreciation | Official public chart estimates exist, but historical estimate revisions and hardware/electricity economics are not point-in-time packaged | Evidence reports causality from Bitcoin price toward hash rate; economic work argues mining costs follow price rather than precede it; popular stock-to-flow/network models have limited or no OOS return prediction | NO_GO |

## Evidence classification

### Verified facts

- Blockchain.com's official Charts API documents UTC date parameters and JSON/CSV access to chart
  histories. The `n-transactions` response identifies itself as “Confirmed Transactions Per Day,”
  unit `Transactions`, period `day`.
- A source-only request retrieved 2,187 observations, with no duplicate timestamps or non-positive
  values. One discontinuity runs from 2025-11-12 to 2025-11-16; it is a data gap, not permission to
  interpolate.
- Koutmos, *Bitcoin returns and transaction activity*, Economics Letters 167 (2018), DOI
  `10.1016/j.econlet.2018.03.021`, reports that a one-standard-deviation activity shock is followed
  by a little over 0.30% return on the third day.
- Aalborg, Molnár, and de Vries, *What can explain the price, volatility and trading volume of
  Bitcoin?*, Finance Research Letters 29 (2019), DOI `10.1016/j.frl.2018.08.010`, reports that none
  of its considered variables predicts Bitcoin returns.
- Coin Metrics documents a no-key Community API for free non-commercial data.
- Lyons and Viswanath-Natraj, NBER Working Paper 27136, report no significant BTC or ETH price
  response to Tether flows to the secondary market.
- Blockchain.com's chart API also exposes estimated hash rate. This is an estimate, not direct
  observation of every miner.

### Inferences and hypotheses

- A two-full-UTC-day lag is a conservative research availability rule for a completed daily L1
  count. It reduces reorg/publication risk but is not a claim that the provider historically
  published every value at an exact guaranteed hour.
- Both high-activity continuation and low-activity/contrarian pulse mechanisms remain hypotheses.
  Source conflict prohibits choosing the sign after results.
- L1 transaction count is not a measure of unique users or economic value. The campaign can test
  predictive association only, not causal adoption.

### Unknowns retained

- The provider does not supply a historical publication-time ledger or immutable revision log for
  each chart value. Exact retained bytes plus a two-day lag are the reproduction boundary.
- The effect of Lightning, batching, inscriptions, consolidations, and exchange internalization on
  the meaning of a transaction-count shock is not separately identified.

## Data contract to freeze before scoring

- Feature source: Blockchain.com official Charts API chart `n-transactions`, exact retained JSON.
- Feature field: daily UTC timestamp `x` and confirmed transaction count `y`; no other response
  field enters the signal.
- Executed instrument: Binance Spot `BTCUSDT`, unlevered long/cash, retained 1h bars.
- Availability: count dated UTC day `D` becomes eligible at `00:00 UTC` on `D+2`.
- Fill: first retained Spot hourly open strictly later than the `D+2 00:00` decision, normally
  `01:00 UTC`; same-open fills are prohibited.
- Source gaps: never interpolate. A missing expected daily observation resets warm-up, expires any
  pending entry, and exits a held pulse at the first Spot open after the missing observation is
  detected.
- Spot gaps: pending fills expire; held exposure exits at the first observable open.
- Future API revisions cannot enter the frozen campaign. Exact retained bytes and hashes govern.
- Feature coverage used by the campaign ends no later than 2026-06-28 so its two-day lag remains
  inside the retained Spot period ending 2026-06-30.

## Complete frozen trial roster

The family has exactly 12 statistical trials:

- activity side: `HIGH` and `LOW`;
- trailing baseline window: `14`, `28`, and `56` complete daily observations; and
- pulse holding period: `1` and `3` complete days.

For UTC source day `D`, calculate the natural log of the current confirmed transaction count. From
the immediately preceding `window` complete consecutive daily log counts, excluding `D`, calculate
the population mean and population standard deviation. The shock z-score is
`(log_count_D - prior_mean) / prior_population_std`.

- `HIGH`: eligible pulse only when z-score `> 1`.
- `LOW`: eligible pulse only when z-score `< -1`.
- Equality is no signal.
- Zero prior standard deviation is no signal and is retained as a diagnostic.
- A pulse enters from cash only; signals while held do not extend or stack it.
- Exit is the first hourly open at least 24 or 72 hours after the entry fill, according to the
  resolved holding period.
- Initial and final state are cash/marked-to-final-close as applicable; no invented liquidation.
- No alternative z threshold, window, holding period, smoothing, value/address metric, price
  filter, ensemble, asset, timeframe, or sizing rule may be added after scoring.

## Preregistered validation design

- Development: 2021-01-01 through 2023-12-31.
- Validation: 2024-01-01 through 2024-12-31.
- Family-unseen reserve: 2025-01-01 through 2026-06-30.
- Phase one evaluates all 12 development trials at F1/S1, writes/hashes the selected
  StrategyVersion, and computes G10. Phase two may evaluate only that version outside development.
- Selection metric: non-annualized per-1h-bar Sharpe, zero cash returns included; lexical
  `(activity_side, window, holding_days)` tie break.
- Costs, benchmarks, PBO/DSR, drawdown, regime, timing-delay, minimum-trade, engine-parity, and
  G1-G11 standards remain at least as strict as the closed funding campaign. Exact thresholds are
  frozen in the campaign before scoring.
- Independent roles: Decimal reference, vectorbt accelerator, Freqtrade Spot signal parity, and
  Nautilus exact event-order/gap parity.

## Stop and no-rescue rules

- Any source, hash, gap, schema, timestamp, lag, spec, roster, cost, split, engine, barrier, or gate
  mismatch aborts.
- Any hard FAIL, method block, conformance residual, zero-validation-activity failure, or sequence
  violation rejects the exact context.
- Do not reinterpret transaction activity as users, value, exchange flow, or causal adoption.
- Do not add a price trend/volatility filter after results.
- Do not reuse or reinterpret calendar/funding reserves or access the sealed V2 prospective
  holdout.
- Numeric PASS cannot activate a bot, paper/demo/live state, HG-3, venue, credentials, or orders.

## Exact next action

Freeze the exact official JSON response as a content-addressed source package, retain its response
metadata and documented API semantics, and add an offline verifier for byte/schema/order/density,
the known November 2025 gap, two-day availability, and strict next-open mapping. Do not compute any
activity-conditioned Spot return before the complete canonical campaign is committed cleanly.

## Sources

- Blockchain.com Charts API: https://www.blockchain.com/explorer/api/charts_api
- Exact chart endpoint: https://api.blockchain.info/charts/n-transactions?timespan=6years&format=json&sampled=false
- Koutmos (2018): https://doi.org/10.1016/j.econlet.2018.03.021
- Aalborg et al. (2019): https://doi.org/10.1016/j.frl.2018.08.010
- Coin Metrics API: https://docs.coinmetrics.io/access-our-data/api
- Lyons and Viswanath-Natraj: https://www.nber.org/papers/w27136
- BIS stablecoin endogeneity evidence: https://www.bis.org/publ/work1270.htm
- Hash-rate/price causality: https://doi.org/10.1016/j.eneco.2020.105092
- OOS Bitcoin return-prediction counterevidence: https://doi.org/10.3390/jrfm17100443
