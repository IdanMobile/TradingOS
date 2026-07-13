# Strategy family selection and preregistration V7

Status: **GO — `FAM-BTC-SPOT-TAKER-IMBALANCE-01` admitted to data packaging only**
Decision class: constrained-S2 source/data feasibility; no family performance computed
Execution authority: `NONE`
Retrieved: 2026-07-13 UTC

## Decision

This cycle compares exactly three mechanisms that are distinct from the closed price, calendar,
carry, funding-pressure, CFTC-positioning, cross-sectional, options, stablecoin, miner-recovery,
transaction-count, MVRV, blockspace-fee, and dormant-supply contexts:

1. Binance Spot aggressive taker-flow imbalance;
2. crypto-perpetual open-interest crowding; and
3. macro dollar/liquidity pressure.

Only Spot taker-flow imbalance advances. The hypothesis is that an extreme completed-hour
imbalance between buyer-initiated and seller-initiated quote volume can contain short-lived
information or liquidity pressure that either continues or reverses after the measured hour.
Both directions remain in the frozen roster because contemporaneous price impact is not evidence
of next-hour continuation. No imbalance-conditioned return, direction, trade count, Sharpe,
drawdown, or equity statistic was computed before this decision.

## Source-backed comparison

| Candidate | Mechanism | Point-in-time feasibility | Counterevidence / dominant risk | Outcome |
|---|---|---|---|---|
| `FAM-BTC-SPOT-TAKER-IMBALANCE-01` | Aggressive signed flow may carry information or temporarily consume liquidity, producing continuation or reversal after the observed hour | PASS: official Binance monthly Spot klines expose total quote volume and taker-buy quote volume, are available with per-archive checksums, and the repository already retains exact BTCUSDT 1h bytes from 2018-04 through 2026-06 | Flow and price are mechanically related inside the same hour; exchange fragmentation, wash trading, changing fee tiers, and adverse selection can destroy out-of-sample tradability; only strictly later fills are admissible | **GO to exact packaging** |
| `FAM-PERP-OI-CROWDING-01` | Unexpected perpetual open-interest expansion may proxy leverage buildup and liquidation vulnerability | PARTIAL: official Binance REST defines historical OI periods, but the endpoint exposes only the latest 30 days; a complete checksum-pinned historical metrics contract was not established in this cycle | Adjacent to closed funding/CFTC contexts; venue-specific OI is not trader direction, and leverage, liquidations, listings, and cross-venue fragmentation dominate interpretation | NO_GO |
| `FAM-MACRO-DOLLAR-LIQUIDITY-01` | Monetary tightening and dollar/liquidity shocks may alter crypto risk appetite and required returns | PASS_WITH_VINTAGES: ALFRED/FRED supports real-time periods, vintage dates, and initial-release observations | Release clocks, revisions, mixed frequencies, event overlap, low independent sample, and choosing among many macro series create a large hidden search hierarchy; shortest lawful campaign is materially longer | NO_GO |

## Evidence classification

### Verified facts

- Binance's official public-data repository states that Spot kline archives derive from
  `/api/v3/klines`; their columns include open/close timestamps, quote asset volume, trade count,
  and taker-buy base and quote volumes.
- Binance publishes daily/monthly public files and a `.CHECKSUM` alongside each ZIP, and documents
  that archived files may later be replaced with changes recorded in its update list.
- The retained TradingOS schema already preserves `quote_volume`, `taker_buy_quote_volume`, exact
  UTC open/close timestamps, and source identity. Exact official-checksum archives cover the
  proposed period.
- Binance's official futures connector documentation says historical open-interest REST results
  are limited to the latest 30 days.
- FRED/ALFRED documentation says observation values and metadata can be revised; real-time periods,
  vintage dates, and an initial-release output type exist to reconstruct what was known.
- Primary microstructure research defines signed buyer/seller market-order flow and documents its
  relationship with Bitcoin price impact, jumps, or short-horizon prediction. It also emphasizes
  fragmentation and transaction-cost realism; it does not establish a guaranteed tradable sign.

### Inferences and hypotheses

- `2 * taker_buy_quote_volume / quote_volume - 1` is a bounded exchange-local proxy for signed
  aggressive quote flow, not a global order-flow measure and not proof of informed trading.
- Positive extremes may continue because aggressive demand carries information, or reverse because
  temporary pressure is exhausted. Both are competing hypotheses.
- A later Spot response would be predictive association, not proof that taker flow caused the move.

### Unknowns retained

- Binance's aggregation and participant mix may change without a stable contemporaneous taxonomy.
- Public klines do not expose order-book depth, spread, individual trade identities, wash-trade
  labels, or the cross-venue flow needed to measure global market impact.
- Historical archive replacement means exact retained bytes are the experiment identity; they are
  not asserted to be immutable contemporaneous download vintages.
- Fee-tier and market-impact assumptions remain stress scenarios, not an operator-specific quote.

## Data contract to freeze before scoring

- Source: exact official-checksum Binance Spot monthly `BTCUSDT` 1h kline ZIPs already retained by
  TradingOS, including the base64-reversible 2018-04 through 2020-12 extension and the canonical
  2021-01 through 2026-06 dataset.
- Required fields: open time, open/high/low/close, close time, base and quote volume, trade count,
  taker-buy base volume, taker-buy quote volume, instrument, interval, and source.
- Feature for a completed hour with positive quote volume:
  `imbalance = (2 * taker_buy_quote_volume / quote_volume) - 1`. Require `-1 <= imbalance <= 1`
  within retained Decimal precision. Zero quote volume is invalid and resets the baseline.
- Availability: the feature becomes available only after the recorded close timestamp. Entry may
  occur only at the first retained hourly open strictly later than that timestamp. No same-bar
  signal or fill is permitted.
- Gaps, duplicate opens, nonmonotonic rows, invalid volumes, taker-buy volume outside `[0,total]`,
  or checksum/schema drift fail closed. A gap resets every consecutive baseline and exits an open
  pulse at the first retained open after the break.
- Preserve exact archive/checksum bytes, decoded ZIP hashes, member hashes, logical row hash,
  source URLs, retrieval UTC, schema, timestamp-unit transition, duplicates, and gap ledger.
- Network access is prohibited during campaign execution.

## Complete trial roster to freeze

Exactly 12 trials are declared:

- interpretation: `CONTINUATION_HIGH` and `REVERSAL_LOW`;
- prior consecutive baseline: `24`, `168`, and `720` complete hours; and
- absolute population-z threshold: `1.0` and `2.0`.

For completed source hour `H`, compute its imbalance. From the immediately prior complete window,
excluding `H`, compute population mean and population standard deviation.
`z_H = (imbalance_H - prior_mean) / prior_population_std`.

- `CONTINUATION_HIGH` enters long when `z_H > threshold`.
- `REVERSAL_LOW` enters long when `z_H < -threshold`.
- Equality, zero standard deviation, a missing hour, or invalid volume produces no signal.
- Entry creates a six-complete-hour unlevered BTCUSDT Spot long/cash pulse. Signals while held do
  not stack or extend it. Exit is the first retained open at least six hours after entry.
- No alternate flow field, sign, threshold, baseline, holding period, smoothing, price filter,
  order-book feature, asset, venue, timeframe, ensemble, or sizing rule may be added after scoring.

## Preregistered validation skeleton

- Development: 2018-04-01 through 2022-12-31.
- Validation: 2023-01-01 through 2024-12-31.
- Family-unseen reserve: 2025-01-01 through 2026-06-30.
- Phase one evaluates all 12 development trials at F1/S1, writes and hashes one selected
  StrategyVersion, and computes family G10. Phase two may evaluate only that selected version
  outside development.
- Selection metric: nonannualized per-1h-bar Sharpe including zero cash returns; lexical
  `(interpretation, baseline_hours, threshold)` tie break.
- Six cost cells, cash and buy-and-hold benchmarks, PBO/DSR, drawdown, annual/regime slices,
  one-bar delay, event minima, four-role parity, G1-G11, and independent supervisor review must be
  at least as strict as the closed CFTC campaign.

## Stop and no-rescue rules

- Any source, archive, checksum, timestamp unit, row identity, schema, roster, cost, split,
  selection barrier, or gate mismatch aborts.
- Any feature or fill using data before its completed-hour close invalidates the campaign.
- Any hard failure, conformance residual, inadequate OOS event count, or sequence violation rejects
  the exact context.
- Do not infer global flow, participant identity, or intent from one exchange's taker aggregate.
- Do not access the sealed V2 holdout or reuse a closed-family result.
- Numeric PASS cannot activate a bot, venue, credentials, paper/demo/live state, or orders.

## Exact next action

Freeze a dedicated order-flow data package from the already-retained exact Binance bytes. Verify
archive/checksum identity, schema, timestamps, volume bounds, feature arithmetic, coverage, gaps,
and strict-next-open mapping offline. Do not compute an imbalance-conditioned return before that
package and the full campaign are committed cleanly.

## Sources

- Binance Public Data repository and schema: https://github.com/binance/binance-public-data
- Binance Spot API documentation: https://github.com/binance/binance-spot-api-docs
- Binance historical open-interest connector definition: https://github.com/binance/binance-futures-connector-python
- FRED/ALFRED real-time periods: https://fred.stlouisfed.org/docs/api/fred/realtime_period.html
- FRED observations and initial-release output: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- Donier and Bouchaud, Bitcoin market impact: https://arxiv.org/abs/1412.4503
- Donier and Bouchaud, Bitcoin crashes and order imbalance: https://doi.org/10.1038/srep14251
- Alexander et al., fragmented Bitcoin price formation: https://arxiv.org/abs/2108.09750
- Kitvanitphasu et al., Bitcoin order-flow toxicity and jumps: https://doi.org/10.1016/j.ribaf.2025.103163
- BIS monetary-policy and crypto-shock evidence: https://www.bis.org/publ/work1219.htm
