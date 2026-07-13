# Strategy family selection and preregistration V5

Status: **GO — `FAM-BTC-MVRV-DISLOCATION-01` admitted to data packaging only**
Decision class: constrained-S2 source/data feasibility; no family performance computed
Execution authority: `NONE`
Retrieved: 2026-07-13 UTC

## Decision

This cycle compares exactly three mechanisms that are distinct from all closed price/calendar,
carry, funding, cross-sectional, options, stablecoin, miner, and transaction-count contexts:

1. Bitcoin market-value-to-realized-value (MVRV) dislocations;
2. U.S. financial-conditions risk regimes; and
3. public Bitcoin search attention.

Only MVRV advances. It combines current market value with an on-chain last-movement cost-basis
estimate and tests whether an unusually high or low ratio precedes a short BTCUSDT Spot long/cash
pulse. It does not claim that realized capitalization is every holder's true cost basis, that last
movement is a purchase, or that the ratio is independent of Bitcoin price. No local MVRV-conditioned
return, direction, trial, trade count, Sharpe, drawdown, or equity statistic was computed before
this decision.

## Source-backed comparison

| Candidate | Mechanism | Point-in-time feasibility | Counterevidence / dominant risk | Outcome |
|---|---|---|---|---|
| `FAM-BTC-MVRV-DISLOCATION-01` | Market value far from realized value may proxy aggregate unrealized profit/loss, capitulation, or exuberance | PASS_WITH_LAG: Coin Metrics Community API exposes daily BTC `CapMVRVCur` without a key; the catalog defines it as current-supply market cap divided by realized value | Numerator contains current price; last movement is not necessarily acquisition; price methodology and historical network metrics may be revised; short-horizon valuation evidence is mixed | **GO to exact packaging** |
| `FAM-US-FINANCIAL-CONDITIONS-01` | Easier money/credit/equity conditions may support speculative demand, while tightening may suppress it | Public weekly NFCI and WALCL histories are available from Federal Reserve sources | New York Fed event evidence finds Bitcoin largely orthogonal to macro news; NBER evidence finds little exposure to common stock/macro factors; financial-stress research reports only limited medium-term directional predictability | NO_GO |
| `FAM-PUBLIC-ATTENTION-01` | Search attention may proxy new-investor demand or late-stage exuberance | Google Trends is publicly viewable, but query normalization, sampling, stitching, geography/category choices, and historical revisions prevent a stable point-in-time contract | Published results conflict: some report OOS forecast gains, while Urquhart reports attention is caused by prior volatility/volume and does not predict returns; direction is unstable | NO_GO |

## Evidence classification

### Verified facts

- Coin Metrics' catalog defines `CapMVRVCur` as the ratio of the USD value of current supply to
  the realized USD value of current supply, with daily frequency and dimensionless decimal type.
- Coin Metrics defines realized capitalization as the sum of native units valued at the USD price
  on the day each unit last moved; for Bitcoin UTXOs, last activity is output creation.
- A no-key Community API request returned 2,189 daily BTC observations from 2020-07-01 through
  2026-06-28, with unique daily UTC timestamps and no missing metric rows.
- Liu and Tsyvinski report that cryptocurrency returns have little exposure to common stock and
  macro factors, while investor-attention proxies forecast returns in their sample.
- Benigno and Rosa report Bitcoin is largely orthogonal to U.S. monetary and macro news.
- Bouri et al. report limited medium-term directional predictability from global financial stress.
- Zhu et al. report Google attention improves OOS Bitcoin-return forecasts; Urquhart reports the
  reverse direction, with volatility and volume driving attention and no return predictability.

### Inferences and hypotheses

- A two-full-UTC-day availability lag is a conservative research rule, not a provider guarantee
  about historical publication time.
- HIGH and LOW standardized MVRV dislocations are competing hypotheses; sign is not chosen after
  results.
- MVRV may describe a valuation or holder-profit regime, but a predictive association would not
  prove causality or identify investor intent.

### Unknowns retained

- The Community API does not provide a historical publication-time ledger or immutable vintage
  for each daily metric value.
- Lost coins, self-transfers, custody reshuffling, change outputs, and price-source methodology can
  alter the economic meaning of realized capitalization.
- Future Coin Metrics recalculations are excluded from the frozen campaign.

## Data contract to freeze before scoring

- Metric: Coin Metrics BTC `CapMVRVCur`, daily `1d`, exact retained response plus exact catalog
  entry. The HTTP body lacked a terminal newline; the tracked JSON adds one LF and records both the
  retrieved-body and tracked-file hashes.
- Executed instrument: retained Binance Spot `BTCUSDT` 1h, unlevered long/cash only.
- Availability: source day `D` becomes eligible at `00:00 UTC D+2`; fill is the first retained
  hourly open strictly later, normally `01:00 UTC`.
- Gaps: no interpolation. A source gap resets warm-up, expires pending entry, and exits held
  exposure when the absence becomes observable under the same lag. Spot gaps expire pending entry
  and exit held exposure at the first retained open.
- Exact retained source/catalog bytes, hashes, and request URL govern. Network access is prohibited
  during campaign execution.

## Complete frozen trial roster

Exactly 12 trials are declared:

- dislocation side: `HIGH` and `LOW`;
- prior baseline: `30`, `90`, and `180` complete consecutive daily observations; and
- pulse holding: `1` and `7` complete days.

For source day `D`, use the natural log of current MVRV. From the immediately preceding resolved
window of complete consecutive daily log-MVRV values, excluding `D`, compute the population mean
and population standard deviation. `z = (log_mvrv_D - prior_mean) / prior_population_std`.

- HIGH enters only when `z > 1`; LOW enters only when `z < -1`.
- Equality and zero prior standard deviation produce no signal.
- Signals while held do not extend or stack a pulse.
- Exit is the first hourly open at least 24 or 168 hours after entry.
- No alternative threshold, window, holding period, smoothing, MVRV variant, price filter, asset,
  timeframe, ensemble, or sizing rule may be added after scoring.

## Preregistered validation design

- Development: 2021-01-01 through 2023-12-31.
- Validation: 2024-01-01 through 2024-12-31.
- Family-unseen reserve: 2025-01-01 through 2026-06-30.
- Phase one evaluates all 12 development trials at F1/S1, writes and hashes the selected
  StrategyVersion, and computes G10. Phase two may evaluate only that version outside development.
- Selection metric: non-annualized per-1h-bar Sharpe including zero cash returns; lexical
  `(side, window, holding_days)` tie break.
- Six costs, benchmarks, PBO/DSR, drawdown, regime, one-bar delay, minimum trades, four-role parity,
  and G1-G11 remain at least as strict as the closed transaction-activity campaign.

## Stop and no-rescue rules

- Any source, metric, hash, revision, schema, timestamp, lag, roster, spec, cost, split, engine,
  selection barrier, or gate mismatch aborts.
- Any hard failure, conformance residual, zero-validation-activity failure, or sequence violation
  rejects the exact context.
- Do not reinterpret MVRV as true acquisition cost, unique holders, exchange flow, or causality.
- Do not access the sealed V2 holdout or reuse closed-family results.
- Numeric PASS cannot activate a bot, venue, credentials, paper/demo/live state, or orders.

## Exact next action

Freeze the retained MVRV response and catalog entry into an offline data package with byte/schema,
metric, ordering, density, positivity, coverage, two-day-lag, and strict-next-open verification.
Do not compute any MVRV-conditioned Spot return before that package and the full campaign are
committed cleanly.

## Sources

- Coin Metrics Community API: https://docs.coinmetrics.io/access-our-data/api
- Coin Metrics API conventions: https://docs.coinmetrics.io/api
- Coin Metrics realized capitalization definition: https://docs.coinmetrics.io/asset-metrics/market/capact1yrusd
- Coin Metrics metric endpoint: https://community-api.coinmetrics.io/v4/timeseries/asset-metrics
- NBER cryptocurrency risks and returns: https://www.nber.org/papers/w24877
- New York Fed Bitcoin–Macro Disconnect: https://www.newyorkfed.org/research/staff_reports/sr1052
- Chicago Fed NFCI: https://fred.stlouisfed.org/series/NFCI
- Financial stress and Bitcoin: https://doi.org/10.1016/j.qref.2018.04.003
- Investor attention OOS evidence: https://doi.org/10.1371/journal.pone.0246331
- Attention counterevidence: https://doi.org/10.1016/j.econlet.2018.02.017
