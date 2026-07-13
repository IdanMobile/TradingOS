# Strategy family selection and preregistration V8

Status: **GO — `FAM-CROSS-VENUE-USD-PREMIUM-01` admitted to data packaging only**
Decision class: constrained-S2 source/data feasibility; no family performance computed
Decision ID: `D-075`
Execution authority: `NONE`
Retrieved: `2026-07-13T17:44:14Z`
Start commit: `f88c7aa2e74f5710e9144f15614c3e15f91c2ab6`

## Decision

This source-only cycle compares exactly three mechanisms that do not reopen a closed result:

1. a quote-normalized Coinbase-versus-Binance BTC Spot premium;
2. U.S. Spot Bitcoin ETP primary-market flow; and
3. USDt peg-stress conditioning.

Only the cross-venue premium advances. The falsifiable hypothesis is that an extreme completed-hour
Coinbase BTC-USD price relative to Binance BTC-USDT, after independently converting USDt into USD,
contains venue-segmented demand or liquidity information that may continue or reverse after the
measured hour. Both interpretations remain in the frozen roster because the sources do not establish
a deployable sign at this horizon.

No candidate-conditioned return, event count, direction, Sharpe, drawdown, equity curve, or local
family performance was computed before this decision. The small public-endpoint probes established
only that `BTC-USD` and `USDT-USD` product identities exist and that hourly historical responses are
available without credentials. Those probes are not a dataset and are not performance evidence.

## Closed-context boundary

- This is not B2/B3/B4, a univariate price threshold, or a rescue of their sealed V2 context.
- It is not the rejected small-alt minute lead/lag hypothesis: it uses two liquid BTC venues and a
  separately observed quote conversion, not ex-post-selected thin altcoins.
- It is not the rejected single-venue taker-imbalance family: no taker-volume field enters the signal.
- It is not executable cross-venue arbitrage: TradingOS will simulate only unlevered Binance
  BTCUSDT Spot long/cash after a strictly later open; it will not trade Coinbase, transfer funds,
  short, use margin, or assume simultaneous fills.
- It does not reopen stablecoin-supply growth. Coinbase `USDT-USD` is a quote-normalization input;
  peg stress is separately reviewed and rejected below as a standalone strategy.

## Source-backed comparison

| Candidate | Mechanism | Point-in-time feasibility | Counterevidence / dominant risk | Outcome |
|---|---|---|---|---|
| `FAM-CROSS-VENUE-USD-PREMIUM-01` | Venue segmentation and heterogeneous USD demand can create a temporary quote-normalized BTC premium whose later response may continue or mean-revert | PASS_WITH_LIMITS: Coinbase Exchange exposes public `BTC-USD` and `USDT-USD` product/candle endpoints; Binance official-checksum BTCUSDT bytes are already retained; all source responses can be content-addressed locally | Coinbase warns historical rates may be incomplete and omits no-tick buckets; academic price-formation evidence is strongest below one second and does not prove an hourly edge; synchronization, quote conversion, gaps, fees, and one-venue execution must be explicit | **GO to exact packaging** |
| `FAM-US-SPOT-BTC-ETP-FLOW-01` | Net creations/redemptions may transmit regulated-investor demand into Spot Bitcoin | PARTIAL: SEC filings and issuer pages establish product and creation/redemption mechanics, but no uniform official daily aggregate flow archive was identified across every product | U.S. Spot Bitcoin ETPs began in January 2024, leaving few independent regimes; issuer fields and timestamps differ, later in-kind changes alter the mechanism, and Form N-PORT public data is delayed rather than a daily decision feed | NO_GO |
| `FAM-USDT-PEG-STRESS-01` | A USDt discount may identify redemption/counterparty stress and a different BTC liquidity regime | PASS_WITH_LIMITS: Coinbase `USDT-USD` hourly candles are public from May 2021 and Tether publishes current redemption terms | Few independent depeg episodes, changing issuer/redemption terms, a current USD 100,000 direct-redemption minimum, and ambiguity between alpha and quote-asset risk make a standalone G10 hierarchy decision-poor | NO_GO; retain as a future risk-state hypothesis only |

One hard source, sample, or model failure is sufficient for rejection; this is not a weighted-score
contest. Prior profitability, popularity, platform listings, and marketing claims are excluded.

## Evidence classification

### Verified facts

- Coinbase Exchange documents an unauthenticated product-candle endpoint with hourly granularity,
  a 300-candle response limit, possible extra buckets before `start`, omitted no-tick intervals, and
  explicitly incomplete historical-rate coverage.
- Direct public probes on 2026-07-13 returned online product identities for Coinbase `BTC-USD` and
  `USDT-USD`; `USDT-USD` returned hourly data on 2021-05-05 but none on 2021-05-01.
- TradingOS already retains content-addressed, official-checksum Binance BTCUSDT hourly source data
  through 2026-06. It remains historical reconstructed evidence, not a prospective holdout.
- Makarov and Schoar document recurrent cross-exchange price deviations and relate idiosyncratic
  venue order flow to arbitrage spreads. Their evidence does not specify this rule or horizon.
- Albers et al. study fragmented Bitcoin price formation at sub-second horizons and show that fee
  regimes and transaction costs materially affect leader/lagger results. This is transfer-risk
  evidence, not validation of an hourly strategy.
- The SEC approved U.S. Spot Bitcoin ETP listings on 2024-01-10. Public Form N-PORT information is
  delayed, and the 2024 amendments apply on staged dates rather than creating a January-2024 daily
  point-in-time aggregate.
- Tether's current public terms require verified customers for direct redemption. Its current fee
  page states a USD 100,000 minimum and the greater of USD 1,000 or 0.1% redemption fee.

### Inferences and hypotheses

- Dividing Coinbase BTC-USD by Coinbase USDT-USD converts the Coinbase BTC quote into an implied
  BTC-USDT price and removes first-order USDt/USD denomination drift.
- A positive normalized premium may reflect U.S.-venue demand and later continuation, or a temporary
  venue dislocation and later reversal. Both are hypotheses; neither sign is inherited.
- A later Binance Spot response would be predictive association, not proof of causal order flow.

### Unknowns retained

- Coinbase does not promise that historical candle responses are immutable or complete.
- Product-status history, maintenance incidents, and historical API corrections are not supplied by
  the candle endpoint and must remain explicit gaps rather than silently filled observations.
- Hourly candles do not expose spread, depth, latency, or sub-hour path, so they cannot establish an
  executable cross-venue arbitrage or simultaneous fill.
- Current operator venue eligibility, fees, tax treatment, account permissions, and capital remain
  human facts deferred beyond offline G1-G11.

## Data contract to freeze before scoring

- Feature sources: public Coinbase Exchange `BTC-USD` and `USDT-USD` one-hour candles.
- Executed/marked source: retained Binance Spot `BTCUSDT` one-hour official-checksum archives.
- Earliest candidate boundary: the first hour for which all three products have valid completed
  candles; no forward/back fill is allowed. Expected practical start is May 2021 and must be proven
  by the package rather than assumed.
- Retain every raw HTTP response with URL/query, request and response UTC, status, headers needed for
  provenance, SHA-256, pagination window, and parser version. Normalize only after exact raw bytes
  are frozen.
- Require unique UTC bucket starts, positive OHLC/volume, internally valid OHLC bounds, deterministic
  overlap reconciliation, and identical duplicate buckets. Conflicting duplicates fail closed.
- Coinbase responses may include buckets before the requested start; retain the raw response but
  include only buckets inside the declared window after deterministic deduplication.
- Missing/no-tick Coinbase hours are gaps, never zero returns or carried prices. A gap resets the
  trailing baseline and exits an open pulse at the first retained Binance open after the break.
- For completed hour `H`, define
  `implied_cb_btcusdt_H = cb_btcusd_close_H / cb_usdtusd_close_H` and
  `premium_H = ln(implied_cb_btcusdt_H / binance_btcusdt_close_H)` using Decimal inputs and a
  documented deterministic logarithm implementation/tolerance.
- The feature becomes available only after the latest recorded close boundary among all three
  source candles. A fill may occur only at the first retained Binance open strictly later than that
  boundary. No same-hour fill is permitted.
- Network access is prohibited during campaign execution. A clean checkout must restore the exact
  normalized logical hash from retained raw bytes and deliberately fail on one-byte drift.

## Complete trial roster to freeze

Exactly 12 trials are declared:

- interpretation: `CONTINUATION_POSITIVE` and `REVERSAL_NEGATIVE`;
- immediately prior consecutive baseline: `168`, `720`, and `2160` complete hours; and
- absolute population-z threshold: `1.0` and `2.0`.

For completed source hour `H`, calculate `premium_H`. From the immediately prior complete baseline,
excluding `H`, calculate the population mean and population standard deviation, then
`z_H = (premium_H - prior_mean) / prior_population_std`.

- `CONTINUATION_POSITIVE` enters long when `z_H > threshold`.
- `REVERSAL_NEGATIVE` enters long when `z_H < -threshold`.
- Equality, zero standard deviation, a missing hour, a source-status ambiguity, or invalid input
  produces no signal.
- Entry creates one six-complete-hour unlevered Binance BTCUSDT Spot long/cash pulse. Signals while
  held do not stack or extend the pulse. Exit is the first retained Binance open at least six hours
  after entry.
- No alternate venue, quote conversion, sign, baseline, threshold, holding period, smoothing, price
  filter, order-flow field, asset, timeframe, ensemble, leverage, short, or sizing rule may be added
  after scoring.

## Preregistered validation skeleton

- Development: first eligible hour through 2023-12-31.
- Validation: 2024-01-01 through 2024-12-31.
- Family-unseen reserve: 2025-01-01 through 2026-06-30.
- Phase one evaluates all 12 development trials at F1/S1, writes and hashes one selected
  StrategyVersion, and computes family G10. Phase two may evaluate only that selected version
  outside development.
- Selection metric: nonannualized per-1h-bar Sharpe including zero cash returns; lexical
  `(interpretation, baseline_hours, threshold)` tie break.
- Six cost cells, cash and costed buy-and-hold benchmarks, PBO/DSR, drawdown, annual/regime slices,
  one-bar delay, event minima, source-gap sensitivity, four-role parity, G1-G11, and independent
  supervisor review must be at least as strict as the closed taker-imbalance campaign.
- Data packaging must prove enough eligible development, validation, and reserve events before the
  campaign is frozen; otherwise this GO converts to operational `NO_GO` without scoring.

## Stop and no-rescue rules

- Abort on any source, response, product identity, hash, timestamp, candle, overlap, gap, formula,
  roster, cost, split, barrier, engine, or gate mismatch.
- Any feature or fill using an incomplete source hour, a carried Coinbase price, or a Binance open
  not strictly later than the latest source close invalidates the campaign.
- Any hard failure, conformance residual, insufficient OOS events, or selection-barrier violation
  rejects the exact context.
- Do not reinterpret this as simultaneous arbitrage, Coinbase execution, institutional flow, or
  causal proof.
- Do not access the sealed V2 holdout or reuse any closed-family result.
- Numeric PASS cannot activate a bot, venue, credentials, paper/demo/live state, human gate, or
  order authority.

## Exact next action

Freeze the exact Coinbase product responses and complete hourly `BTC-USD`/`USDT-USD` paginated
responses through 2026-06-30, retain request/response provenance, and normalize them against the
already-retained Binance BTCUSDT boundary. Verify bytes, products, schemas, overlaps, gaps,
coverage, quote conversion, feature arithmetic, and strict-next-open mappings offline. Do not
compute a premium-conditioned return before the data package and full campaign are committed.

## Sources

- Coinbase Exchange product candles: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles
- Coinbase Exchange products: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-all-known-trading-pairs
- Coinbase public API product identities: https://api.exchange.coinbase.com/products/BTC-USD and https://api.exchange.coinbase.com/products/USDT-USD
- Binance public data: https://github.com/binance/binance-public-data
- Makarov and Schoar, *Trading and Arbitrage in Cryptocurrency Markets*: https://doi.org/10.1016/j.jfineco.2019.07.001
- Albers et al., *Fragmentation, Price Formation, and Cross-Impact in Bitcoin Markets*: https://arxiv.org/abs/2108.09750
- SEC statement on Spot Bitcoin ETP approval: https://www.sec.gov/newsroom/speeches-statements/gensler-statement-spot-bitcoin-011023
- SEC Form N-PORT/N-CEN compliance guide: https://www.sec.gov/files/rules/final/2024/small-entity-guide-form-n-port-n-cen.pdf
- iShares IBIT official product/holdings page: https://www.ishares.com/us/products/333011/ishares-bitcoin-trust-etf
- Tether token terms: https://tether.to/en/legal/
- Tether current fees: https://tether.to/en/fees/
