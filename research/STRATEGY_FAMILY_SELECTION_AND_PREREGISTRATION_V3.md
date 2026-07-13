# Strategy family selection and preregistration V3

Status: **GO — `FAM-FUNDING-PRESSURE-SPOT-01` campaign frozen, not run**
Decision ID: `D-055`  
Decision class: constrained-S2 source/data feasibility; no performance computed  
Execution authority: `NONE`  
Local family-return observations before this decision: `NONE`

## Decision

This cycle compares exactly three economically distinct mechanisms:

1. perpetual-funding pressure as a directional Spot long/cash signal;
2. BTC-to-small-altcoin high-frequency price-transmission lag; and
3. crypto-options variance-risk-premium harvesting.

Only the first family passes admission. It uses the BTCUSDT perpetual funding record as a
public positioning/expected-return state variable but executes only unlevered BTCUSDT Spot.
It does **not** hold, short, margin, or collect payments from a perpetual. This is materially
different from the rejected delta-neutral carry family and removes its paired-fill,
collateral, maintenance-margin, liquidation, transfer, and funding-receipt dependencies.

No local funding-conditioned Spot return, threshold, direction, Sharpe, trade count, or
equity statistic was computed while making this decision.

## Hard admission comparison

| Candidate | Mechanism | Point-in-time public data | Dominant modeled risk | Canonical/operational fit | Outcome |
|---|---|---|---|---|---|
| `FAM-FUNDING-PRESSURE-SPOT-01` | Perpetual funding reflects leveraged speculative demand, positioning pressure, and the premium mechanism; its sign/level may forecast Spot risk or returns | PASS: 66 retained monthly official Binance BTCUSDT funding archives plus exact Spot 1h bars, 2021-01 through 2026-06 | Spot price, turnover/cost, model instability, signal polarity; no derivative position | PASS: timestamped exogenous feature, long/cash Spot, next-open execution, existing Freqtrade/Nautilus roles | **GO** |
| `FAM-BTC-ALTLAG-01` | Lower-liquidity altcoins can react to BTC shocks with a minute-scale delay | FAIL for decision-useful execution: source study selects low-trade assets ex post and the edge lives at one-minute latency in thin names | spread, impact, queue/latency, delisting, point-in-time universe, venue dependence | FAIL: OHLCV cannot validate the dominant microstructure risks | NO_GO |
| `FAM-OPTIONS-VRP-01` | Option sellers may earn compensation for implied variance exceeding realized variance | Public trades/instruments may be obtainable, but historical surfaces, mark methodology, settlement, and complete contract lifecycle are not packaged | short-convexity tail, margin/liquidation, smile/term structure, exercise/settlement, impact | FAIL: no canonical option/inventory/margin ownership and not a short lawful route to Spot paper | NO_GO |

## Selected mechanism and source conflict

The mechanism is falsifiable: a funding observation available at time `t` defines a state;
the strategy can hold BTC Spot or cash only after the first hourly open strictly later than
`t`. If after-cost future Spot returns do not remain positive and robust under one frozen
polarity/threshold/lookback, the family fails.

Primary and authoritative sources do not imply one guaranteed sign:

- Gorton et al., *Leverage and Stablecoin Pegs*, NBER Working Paper 30796,
  DOI `10.3386/w30796`, uses Binance BTCUSDT perpetual funding as a proxy for speculative
  demand/expected crypto returns and reports strong cross-market linkage.
- Nimmagadda and Ammanamanchi, *BitMEX Funding Correlation with Bitcoin Exchange Rate*,
  arXiv `1912.03270`, discusses funding as a market-trend indicator but does not establish a
  universal deployable Spot rule.
- Tran et al. (2026), DOI `10.51505/IJEBMR.2026.10315`, reports cumulative funding among
  leverage indicators that predict extreme crypto declines. This is mechanism conflict, not
  permission to choose a direction after results.
- Binance's official funding explanation states that positive funding transfers from longs
  to shorts, negative funding reverses the transfer, and interval/rate mechanics can change.
  The retained archive's own `calc_time`, `funding_interval_hours`, and
  `last_funding_rate` fields remain the point-in-time numerical authority.
- Binance's official public-data repository documents public monthly archives, checksums,
  later archive corrections, and the Spot kline schema. Exact retained bytes, not future
  upstream availability, govern reproduction.

Because the literature supports both speculative-demand continuation and crowded-position
crash risk, the full statistical roster freezes both polarities. Polarity is a declared
trial dimension, never a post-result story.

## Data contract to freeze before scoring

- Funding instrument: Binance USD-M `BTCUSDT` perpetual, feature source only.
- Executed instrument: Binance Spot `BTCUSDT`, long/cash only.
- Funding fields: `calc_time`, `funding_interval_hours`, `last_funding_rate` exactly as
  retained in each official monthly archive.
- Coverage: 2021-01-01 through 2026-06-30; all 66 monthly funding archives retained.
- Feature availability: a record is unavailable before its exact millisecond `calc_time`.
- Decision: update state at `calc_time`; never round backward to the apparent funding hour.
- Fill: first retained Spot 1h open strictly later than `calc_time`; no same-open fill.
- Gap: a pending state change expires if its expected next hourly open is absent; an existing
  Spot position exits at the first observable open after a data gap.
- Interval changes: retain `funding_interval_hours`; lookbacks count observations, not assumed
  eight-hour blocks.
- Duplicate/non-monotone observations, unknown intervals, missing months, or a funding record
  beyond Spot coverage fail closed.
- No mark, index, or perpetual price enters the signal. This family claims positioning
  information, not executable derivative carry or basis convergence.

## Complete frozen trial roster

The family has exactly 12 statistical trials:

- polarity: `CONTINUATION` and `CONTRARIAN`;
- trailing funding observation count: `3`, `9`, `21`; and
- absolute mean-rate threshold: `0` and `0.0001`.

At each observed funding record, calculate the mean of the latest complete `lookback`
`last_funding_rate` values, including the current record.

- `CONTINUATION`: long-eligible when mean `> threshold`; cash-eligible otherwise.
- `CONTRARIAN`: long-eligible when mean `< -threshold`; cash-eligible otherwise.
- Equality is cash.
- State persists until a later funding observation changes it.
- Flat enters and held exits only through next-open actions defined above.
- Initial state is flat; final held exposure is marked to final Spot close without invented
  liquidation, and separately reported.

No other lookback, threshold, normalization, price filter, funding transformation, ensemble,
instrument, timeframe, or polarity may be added after scoring.

## Preregistered validation design

- Development/search: 2021-01-01 through 2023-12-31.
- Validation: 2024-01-01 through 2024-12-31.
- Family-unseen reserve: 2025-01-01 through 2026-06-30.
- Operational sequence: compute all 12 development trials, write and hash the selected
  StrategyVersion, then and only then compute validation and reserve for that one version.
- Selection metric: non-annualized per-1h-bar Sharpe at F1/S1, zero cash returns included.
- Tie break: lexical `(polarity, lookback, threshold)` order.
- Costs: the existing six F0/S0 through F2/S3 Spot cells; F1/S1 selection; F2/S3 hard stress.
- Benchmarks: cash and costed BTCUSDT buy-and-hold.
- G10: 16-slice development CSCV/PBO across all 12 trials; corrected DSR with complete
  trial-return correlation evidence; PBO `<=0.5`, DSR `>=0.95`.
- Minimum completed trades: development 30, validation 8, reserve 12.
- After-cost gate: positive full, validation, and reserve F1/S1 returns and positive full
  F2/S3 return.
- Tail gate: F1/S1 max drawdown no worse than `-25%`.
- Regime gate: positive in at least four of six year/H1 segments, including validation and
  reserve in aggregate.
- Benchmark gate: F1/S1 Sharpe above costed buy-and-hold and smaller drawdown.
- Timing perturbations: fill one hourly bar later and require positive full F1/S1 return;
  never fill earlier because that would violate availability.
- Cross-engine: independent Decimal reference, vectorbt acceleration, Freqtrade Spot signal
  parity, and Nautilus event-order/gap parity before G4 can pass.

The runner must implement an explicit two-phase barrier. Merely loading reserve bytes is
permitted for hash verification; computing a reserve signal, return, or metric before the
selection artifact exists is prohibited. A sequencing test must deliberately fail a runner
that calls reserve evaluation early.

## Stop and no-rescue rules

- Abort on any source, archive, checksum, schema, timestamp, Spot data, code, environment,
  spec, roster, cost, split, or threshold mismatch.
- Retain every development trial, including zero-trade and undefined-correlation trials.
- Any hard FAIL, method block, cross-engine residual, or sequence violation rejects the exact
  context.
- Do not reinterpret funding sign after results.
- Do not convert this into carry, a perpetual trade, leverage, or a short position.
- Do not reuse the calendar reserve or sealed V2 prospective holdout.
- Any adaptation requires a new family/version and new unseen evidence.
- Numeric PASS cannot activate paper/demo/live; G11 and HG-3 remain separate.

## Exact next action

The content-addressed data package, canonical spec, 12 StrategyVersions, four independent role
implementations, explicit selection-artifact barrier, and immutable campaign are frozen as
`research/FUNDING_PRESSURE_SPOT_G1_G11_CAMPAIGN_V1.yaml`. Commit the complete freeze cleanly,
then execute it once offline. The runner must reject any validation/reserve call made before the
hashed development selection artifact exists.

## Sources

- NBER: https://www.nber.org/papers/w30796
- BitMEX funding paper: https://arxiv.org/abs/1912.03270
- Leverage/crash study: https://doi.org/10.51505/IJEBMR.2026.10315
- Binance public data: https://github.com/binance/binance-public-data
- Binance funding explanation: https://academy.binance.com/en/articles/what-are-funding-rates-in-crypto-markets
- Small-alt lead/lag: https://doi.org/10.1007/s10690-026-09589-z
- Seesaw counterpoint/cost evidence: https://doi.org/10.1016/j.jempfin.2023.101428
