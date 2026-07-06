# Existing Strategy Registry V0

Status: Seed registry. Entries are discovery sources and hypothesis inputs, not approved profitable strategies.

## Source registries
| Source | Type | What can be reused | Evidence status | Import action |
|---|---|---|---|---|
| QuantConnect Strategy Library | Official tutorials + academic implementations | logic, citations, LEAN examples | Validated source candidate | ingest metadata and linked literature |
| QuantConnect Community Strategies | Community algorithms with platform tracking | implementations, live/OOS observation signals | Validated source candidate with caveats | ingest metadata, clone only under provenance |
| Freqtrade Strategies repo | Official community repository | crypto strategy implementations | Validated source candidate | import as unverified hypotheses |
| Hummingbot V2 Controllers | Official production-grade modular controllers | market making/directional/controller patterns | Validated source candidate | catalog controllers and exact configs |
| Hummingbot Gateway strategies/snippets | Official maintained examples | DEX/CEX strategy patterns | Validated source candidate | catalog and reproduce selectively |
| TradingView Community Scripts | Massive Pine ecosystem | indicators, strategies, libraries | Validated discovery source; mixed evidence | ingest only open-source/allowed metadata and provenance |
| Academic literature | Primary research | hypotheses, methods, validation designs | strongest conceptual source class | reproduce independently |
| GitHub topic/repositories | Open-source community | code and ideas | mixed | maintenance/license/evidence gate |
| Forums/social | Community claims | idea generation | weak | hypothesis only |

## Initial strategy-family taxonomy
### Directional
- Trend following
- Momentum
- Breakout
- Mean reversion
- Volatility expansion/compression

### Relative value
- Pairs trading
- Statistical arbitrage
- Cross-asset spread
- Basis/carry

### Liquidity/execution
- Pure market making
- Dynamic market making
- Cross-exchange market making
- TWAP/VWAP execution

### Crypto-specific
- Funding/basis
- Cross-exchange arbitrage
- Order-book imbalance
- Liquidation-event response
- On-chain/event signals

### Allocation
- Risk parity
- Momentum allocation
- Volatility targeting
- Rebalancing

## Seed concrete implementations discovered
### Hummingbot controllers shown in current official Dashboard configuration docs
- PMM Simple
- PMM Dynamic
- D-Man Maker V2
- Bollinger V1
- MACD BB V1
- SuperTrend V1
- XEMM Controller

### QuantConnect
- Academic-literature tutorials in Strategy Library.
- Community strategies available for learning/cloning and platform-observed behavior.

### Freqtrade
- Official `freqtrade-strategies` repository.

## Required registry fields before ingestion becomes operational
- canonical strategy ID
- name
- family
- source URL
- source class
- author
- license
- published date
- last maintained date
- market claimed
- timeframe claimed
- long/short
- entry logic
- exit logic
- TP/SL behavior
- indicators/features
- parameters
- data dependencies
- execution assumptions
- claimed metrics
- source evidence level
- internal reproduction status
- internal tests
- rejection reason
- related concepts in ontology

## Mandatory rule
`Discovered online` never means `validated`.
