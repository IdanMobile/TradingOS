# Phase 3 — Execution Readiness Research Report

Date checked: 2026-07-05
Status: Targeted discovery complete for this tranche; implementation architecture remains unapproved.

## Scope
This tranche focused on five preparation areas:
1. Crypto Spot venue/API matrix.
2. Historical market-data matrix.
3. Experiment-lineage executable prototype design.
4. Strategy ingestion and reproduction workflow.
5. Frozen AI/agent benchmark suite design.

## Executive findings

### F1 — Venue capability and operator eligibility must be separate decisions
A venue can have excellent REST/WebSocket/FIX APIs and still be unsuitable for the operator because of account, jurisdiction, product, funding, or terms constraints. Therefore the project must maintain two independent states:
- `TECHNICALLY_SHORTLISTED`
- `OPERATOR_ELIGIBLE`

No venue may become `LIVE_APPROVED` until both are satisfied.

### F2 — Current technically serious venue candidates
The current API-capability shortlist is:
- Binance Spot
- Kraken Spot
- Coinbase Advanced Trade / Exchange APIs
- OKX Spot

This is not a live-exchange recommendation.

Evidence highlights:
- Binance publishes current Spot REST/WebSocket documentation, Spot Testnet documentation, filters/trading rules, changelogs, and low-latency SBE guidance.
- Kraken publishes Spot REST/WebSocket/FIX documentation, trading rate limits, L3 market-data guidance, and automated-trading material.
- Coinbase publishes Advanced Trade API, WebSocket feeds, and an official Python SDK.
- OKX publishes V5 API materials, REST/WebSocket trading support, and demo API-key capability.

### F3 — The MVP should use data tiers, not one universal provider
Recommended research-data tiers:

Tier 0 — free/native discovery data
- Exchange candles/trades where sufficient.
- Purpose: basic deterministic baselines, infrastructure bake-off, early hypothesis screening.

Tier 1 — normalized historical crypto data
- Candidates: CoinAPI, Kaiko and similar providers.
- Purpose: broader multi-venue normalized research.

Tier 2 — tick/order-book microstructure data
- Leading candidate: Tardis.dev for crypto-native granular replay.
- Purpose: execution realism, order-book features, microstructure strategies.

Tier 3 — future multi-asset data
- Leading candidate: Databento for equities/futures/options expansion.
- Purpose: later cross-market portability, not initial Crypto Spot requirement.

Hard rule: do not buy Tier 2/3 data merely because it is more sophisticated. A strategy or validation requirement must justify it.

### F4 — MLflow and DVC currently look complementary, not mutually exclusive
Primary-source evidence shows:
- MLflow tracks parameters, code versions, metrics, artifacts, datasets, models, and increasingly LLM/agent traces/evaluation.
- DVC versions data/model artifacts through Git-tracked metafiles and supports restoration/reproduction of snapshots.

The strongest current prototype hypothesis is:
- MLflow for run/metric/artifact/AI trace tracking.
- DVC for reproducible dataset and large-artifact versioning.
- Custom Trading Evidence Registry above both.

This remains a hypothesis until the local mini-prototype passes acceptance tests.

### F5 — Existing strategy ingestion needs provenance and semantic reproduction gates
Public strategy code is not directly importable as trusted knowledge. The workflow must preserve:
- source
- license
- source class
- exact version/commit
- original language/framework
- extracted rules
- ambiguities
- hidden assumptions
- market/timeframe assumptions
- converted canonical strategy specification
- reproduction result
- internal validation state

### F6 — AI/agent benchmarking must include leakage controls
Recent 2026 research materially strengthens this requirement:
- QuantCode-Bench tests executable strategy generation and semantic alignment.
- BacktestBench evaluates automated quantitative backtesting workflows.
- KTD-Fin explicitly controls for model memory/leakage and decomposes returns to distinguish passive exposure from stock-selection skill.

Therefore our frozen benchmark suite must include:
- frozen corpora
- time-aware source boundaries
- masked identifiers where appropriate
- no-network controlled mode
- economic-outcome evaluation only when attribution is interpretable

## Venue API capability matrix

| Venue | Spot REST | WebSocket market data | WebSocket/private trading | FIX | Test/demo environment | Current technical status | Operator eligibility |
|---|---|---|---|---|---|---|---|
| Binance | Yes | Yes | Yes / API-dependent | Available in platform docs | Spot Testnet | Strong candidate | Unresolved |
| Kraken | Yes | Yes | Yes | Yes | UAT/testing references exist | Strong candidate | Unresolved |
| Coinbase | Yes | Yes | Yes via Advanced Trade flows | Exchange API supports FIX | Sandbox/testing details require exact workflow verification | Candidate | Unresolved |
| OKX | Yes | Yes | Yes | Not required for MVP | Demo trading API keys documented | Candidate | Unresolved |

### Venue matrix caveats
- `Testnet` does not prove realistic liquidity or fills.
- Fee tiers are account/volume dependent and must be captured at execution time.
- Product availability can differ by jurisdiction and account.
- API docs and behavior change; all selected adapters require changelog monitoring and contract tests.

## Historical data matrix

| Candidate | Primary strength | Crypto-native | OHLCV | Trades | Order book | Tick replay | Multi-asset | MVP role |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Native exchange APIs | Cheapest first step | Yes | Yes | Usually | Live depth; historical varies | Limited | No | Tier 0 baseline |
| Tardis.dev | Granular crypto history/replay | Yes | Derived/available | Yes | Yes | Yes | No | Tier 2 specialist |
| CoinAPI | Broad normalized crypto coverage | Yes | Yes | Yes | Yes per product docs | Provider-dependent | No | Tier 1 candidate |
| Kaiko | Institutional crypto data/analytics | Yes | Yes | Yes | Yes | Product-dependent | No | Tier 1 candidate |
| Databento | Direct multi-asset market data | Limited crypto fit | Yes | Yes | Yes | Yes by schema/venue | Yes | Future expansion |

### Data decision rule
Choose the cheapest tier that can falsify the hypothesis. Escalate only when lower-resolution data cannot answer the research question.

## Recommended immediate experiments
1. Run the engine bake-off first on Tier 0 candles for BTC/USDT and ETH/USDT.
2. Add trade-level replay only after candle-level parity is established.
3. Introduce order-book data only for strategies whose logic explicitly depends on microstructure or execution queue/depth.
4. Prototype MLflow + DVC with one strategy run and one AI research run.
5. Ingest and reproduce a small cross-source strategy sample before automating large-scale import.

## Sources checked
Primary / official sources:
- Binance Spot API docs and changelog: https://developers.binance.com/docs/binance-spot-api-docs/
- Binance Spot Testnet: https://developers.binance.com/en/docs/products/spot/testnet/general-info
- Kraken API Center: https://docs.kraken.com/
- Kraken Spot limits: https://docs.kraken.com/api/docs/guides/spot-ratelimits/
- Kraken L3 data: https://docs.kraken.com/api/docs/guides/spot-l3-data
- Coinbase Advanced Trade API: https://www.coinbase.com/developer-platform/products/advanced-trade-api
- Coinbase official Python SDK: https://github.com/coinbase/coinbase-advanced-py
- OKX API: https://www.okx.com/en-eu/okx-api
- Tardis.dev: https://tardis.dev/
- Databento historical API: https://databento.com/docs/api-reference-historical
- CoinAPI market data: https://www.coinapi.io/products/market-data-api
- Kaiko data dictionary: https://docs.kaiko.com/explore-our-data/data-dictionary
- MLflow Tracking: https://mlflow.org/docs/latest/ml/tracking/
- MLflow Dataset Tracking: https://mlflow.org/docs/latest/ml/dataset/
- DVC data/model versioning: https://doc.dvc.org/example-scenarios/versioning-data-and-models
- QuantConnect Strategy Library: https://www.quantconnect.com/docs/v2/writing-algorithms/strategy-library
- Hummingbot Controllers: https://hummingbot.org/strategies/v2-strategies/controllers/
- Freqtrade Strategy Quickstart: https://www.freqtrade.io/en/stable/strategy-101/

Research prior art:
- QuantCode-Bench: https://arxiv.org/abs/2604.15151
- BacktestBench: https://arxiv.org/abs/2605.17937
- KTD-Fin: https://arxiv.org/abs/2605.28359

## Saturation assessment
| Capability | Status | Remaining gap |
|---|---|---|
| Venue API capability | Partial-to-sufficient for shortlist | Israel/account eligibility and exact fee/product matrix |
| Crypto historical data | Partial | Exact pricing, pair coverage, retention, licensing |
| Experiment lineage | Sufficient for prototype hypothesis | Local executable proof |
| Strategy ingestion | Sufficient for workflow design | License automation and parser prototypes |
| AI benchmark prior art | Sufficient for V1 suite design | Frozen corpus construction and execution |
