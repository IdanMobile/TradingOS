# Strategy family selection and preregistration V9

Status: **NO_GO — stop autonomous public-signal mining at the current evidence boundary**  
Decision class: constrained-S2 source/data feasibility; no family performance computed  
Decision ID: `D-079`  
Execution authority: `NONE`  
Retrieved: `2026-07-13T18:21:40Z`  
Start commit: `02e546e3d9f1bac9715d5a42f7995a6bf456986c`

## Decision

This source-only cycle compares exactly three mechanisms that do not reopen a closed result:

1. point-in-time exchange-balance and exchange-flow changes;
2. forced-liquidation stress in crypto derivatives; and
3. the regulated CME Bitcoin futures curve and roll/basis.

None passes the complete admission boundary. No candidate-conditioned return, event count,
direction, Sharpe, drawdown, equity curve, or local family performance was computed. No data,
canonical StrategyVersion, or campaign may be built from this dossier.

The cumulative evidence now warrants a research stop. Eight prior bounded source cycles admitted
seven families after rejecting their peers; every completed G1-G11 campaign failed promotion, and
the remaining public candidates below each lack a required source, sample, or deployability
property before performance is considered. Starting another autonomous public-signal cycle would
increase the hidden family search and false-discovery burden faster than it increases prior
plausibility.

This is not a claim that no crypto strategy can work. It is a decision that the current public,
keyless, reproducible, Spot-compatible evidence boundary does not justify another campaign.

## Closed-context boundary

- Exchange flows are not a rebranding of transaction count, MVRV, dormant supply, or miner data;
  they require contemporaneous entity/address attribution that the raw ledger does not contain.
- Liquidation stress is not funding pressure, taker imbalance, or open-interest crowding; it uses
  forced close events. It is rejected on official archive completeness and observation semantics,
  not on a directional result.
- CME curve carry is not the rejected Binance perpetual-funding family. It uses listed expiry
  contracts and regulated settlements, but still requires complete contract, roll, capital,
  margin, and licensed point-in-time data.
- The sealed V2 price-family holdout and every previously evaluated reserve remain untouched.

## Source-backed comparison

| Candidate | Mechanism | Point-in-time feasibility | Dominant failure | Outcome |
|---|---|---|---|---|
| `FAM-BTC-EXCHANGE-FLOW-PIT-01` | Net transfers to identified exchanges may represent prospective sell-side inventory; net withdrawals may represent reduced liquid supply | PARTIAL_AUTHENTICATED: Glassnode documents append-only point-in-time exchange metrics designed for backtesting, but its API returns `401` without a key and the labels/entity clustering are proprietary rather than reconstructible from Bitcoin Core | The Bitcoin ledger exposes UTXOs and scripts, not beneficial owners or exchange intent. Glassnode says exchange labels and statistical entity information are continually updated; the required immutable PiT product is outside the current public/keyless contract | **NO_GO** |
| `FAM-BTC-FORCED-LIQUIDATION-STRESS-01` | Forced deleveraging can create temporary continuation through cascades or reversal after price-insensitive inventory is exhausted | PARTIAL_STALE: Binance's checksum-backed public archive has BTCUSD_PERP liquidation snapshots for only 472 days, 2023-06-25 through 2024-10-14; the USD-M path is empty | The official stream is a throttled snapshot that publishes only the latest liquidation for a symbol within a one-second window, so it is not a complete liquidation ledger. The archive stops well before the frozen 2026 boundary and supplies too few independent regimes for a defensible G10 hierarchy | **NO_GO** |
| `FAM-CME-BTC-CURVE-ROLL-01` | A futures premium can compensate capital/intermediation constraints; curve shape and roll may support a market-neutral carry or a directional crowding signal | SEMANTICS_PASS / DATA_AUTH_REQUIRED: CME documents contract sizes, settlement methods, price limits, historical products, and continuous series, but historical settlements/contract data are delivered through DataMine or licensed MDP access | A lawful test needs every listed contract, contemporaneous settlement/volume/OI, expiry and roll mapping, Spot reference timing, fees, margin, capital, and basis tail scenarios. DataMine API access requires an entitled API ID, and the continuous series requires a futures/options license; simplifying to the website would violate CME's reference-only warning | **NO_GO** |

One hard source, sample, or model failure rejects a candidate. This is not a weighted score and no
candidate receives credit for popularity, a platform listing, a paper result, or an attractive
economic story.

## Evidence classification

### Verified facts

- Bitcoin Core's `gettxout` returns output value, confirmations, and script information; it does
  not identify an exchange, beneficial owner, deposit, withdrawal, or economic intent.
- Glassnode's exchange-balance PiT endpoint is append-only, but the documentation returns `401` for
  a missing API key. Glassnode states that exchange metrics depend on labeled addresses,
  proprietary clustering/statistical methods, and changing information.
- A direct read-only listing of Binance's official public bucket found zero USD-M BTCUSDT
  `liquidationSnapshot` objects and 472 checksum-paired COIN-M BTCUSD_PERP daily archives from
  2023-06-25 through 2024-10-14. The first retained ZIP passed its published SHA-256 checksum.
- The sampled liquidation CSV contains repeated identical rows. Binance documents liquidation
  streams as snapshots that push only the latest liquidation order per symbol within 1,000 ms,
  which is not an exhaustive event tape.
- CME documents that Bitcoin futures historical data are available through DataMine, DataMine API
  calls require authentication with an entitled API ID, and the continuous price series requires
  an information license. CME warns that website data are reference-only and not validation data.

### Inferences and hypotheses

- Exchange-flow direction may be economically meaningful, but address attribution and intent are
  the feature. Reconstructing only raw transfers would test a different, already-adjacent network
  activity hypothesis.
- Liquidation snapshots likely undercount clustered events by construction. Treating the files as
  total liquidated notional would create false precision.
- CME curve carry has the strongest economic mechanism of these three, but architecture and
  profitability cannot compensate for absent authorized source data and a complete capital model.

### Unknowns retained

- The commercial terms, historical depth, redistribution rights, and current cost of a suitable
  Glassnode PiT entitlement were not requested or assumed.
- Binance does not state in the public archive listing why the COIN-M liquidation series starts in
  June 2023 or stops in October 2024, nor whether omitted stream events can be recovered elsewhere.
- The operator's legal/account eligibility for CME products or a broker, actual commissions,
  margin, tax, capital, and data entitlements are unknown and remain outside S2.

## Stop rule and lawful reopen conditions

Autonomous public-signal mining stops here. A new Task-1 cycle may reopen only when at least one
candidate arrives with **new exogenous evidence** that closes the current boundary before any
performance is viewed, for example:

1. an operator-supplied strategy specification with original source/version/license and an unseen
   point-in-time dataset;
2. approved access to an authoritative historical source whose license, coverage, release clock,
   and raw-byte retention can be verified without exposing credentials; or
3. genuinely prospective observations accumulated under a preregistered rule for enough time to
   support a chronological decision.

A paper, leaderboard, marketplace result, social post, copied bot, new parameter grid, alternative
sign, ensemble of rejected families, or another pass over the same historical data is not new
evidence and may not reopen research.

## Exact next action

Do not create Task-2 data packages or another autonomous family comparison. Present the operator
with the retained negative result and the three lawful reopen paths above. If the operator supplies
new authority/evidence, begin a fresh source-only dossier. Otherwise preserve the current clean S2
research system, keep the dormant synthetic-paper runtime disabled, and wait for prospective data.

No bot, venue connection, credential, order, paper/demo/live state, human gate, promotion, or
execution authority is activated by this decision.

## Sources

- Bitcoin Core `gettxout`: https://developer.bitcoin.org/reference/rpc/gettxout.html
- Glassnode point-in-time API: https://docs.glassnode.com/basic-api/endpoints/pit
- Glassnode point-in-time methodology: https://docs.glassnode.com/data/point-in-time-metrics
- Glassnode entity-adjusted metrics: https://docs.glassnode.com/guides-and-tutorials/on-chain-concepts/entity-adjusted-metrics
- Glassnode data finalization: https://docs.glassnode.com/data/general-information/data-finalization
- Binance official public data: https://github.com/binance/binance-public-data
- Binance COIN-M liquidation stream: https://developers.binance.com/docs/derivatives/coin-margined-futures/websocket-market-streams/Liquidation-Order-Streams
- Binance public archive root: https://data.binance.vision/?prefix=data/futures/cm/daily/liquidationSnapshot/BTCUSD_PERP/
- CME cryptocurrency futures FAQ: https://www.cmegroup.com/articles/faqs/frequently-asked-questions-cryptocurrency-futures.html
- CME DataMine: https://www.cmegroup.com/datamine.html
- CME DataMine API: https://www.cmegroup.com/datamine/datamine-api.html
- CME continuous price series: https://www.cmegroup.com/market-data/cme-group-continuous-price-series.html
- CME settlement-data warning: https://www.cmegroup.com/trading/about-settlements.html
