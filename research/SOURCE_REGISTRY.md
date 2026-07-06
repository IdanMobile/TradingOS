# Source Registry

Checked: 2026-07-05

## Primary / official technical sources

| Source | Category | Use |
|---|---|---|
| NautilusTrader docs | Engine | research/simulation/live/risk architecture |
| QuantConnect docs | Engine/platform | LEAN, research pipeline, risk/portfolio/execution patterns |
| Freqtrade docs | Crypto bot | backtest, dry-run, hyperopt, bias diagnostics |
| Hummingbot docs | Crypto framework | strategies, market making, dashboard, Quants Lab |
| vectorbt docs | Research | rapid vectorized backtests and indicators |
| MLflow docs | Experiment/AI | tracking, datasets, AI/agent evaluation |
| DVC docs | Data/experiments | dataset/artifact versioning and experiment bookkeeping |
| lakeFS docs | Data versioning | object-store versioning and MLflow integration |
| TA-Lib docs | Indicators | canonical indicator/pattern implementations |
| CCXT manual | Connectivity | normalized exchange API patterns |
| Binance developer docs | Exchange | native spot API and market data semantics |
| Tardis docs | Crypto data | tick/order-book historical data semantics |
| Databento docs | Market data | historical/live schemas and data API |

## Primary research / academic sources

| Source | Use |
|---|---|
| Bailey et al., Probability of Backtest Overfitting | PBO / CSCV validation |
| Bailey & López de Prado, Deflated Sharpe Ratio | multiple-testing and non-normality correction |
| BacktestBench (2026) | AI automated backtest benchmark prior art |
| QuantEval (2026) | quant LLM benchmark prior art |
| QuantCode-Bench (2026) | executable strategy-generation benchmark prior art |
| FinRL-X (2026) | modular AI-native quant architecture prior art |

## Discovery-only sources

Curated GitHub lists and topic pages may be used to discover candidates, but never as the sole validation basis.


## Phase 2 sources added
- Freqtrade lookahead-analysis documentation — official — current 2026 docs.
- Freqtrade FAQ / FreqAI current docs — official.
- NautilusTrader official product/docs/API material — official.
- QuantConnect brokerages/pricing/strategy library/community strategies — official.
- Hummingbot Dashboard, API routers, V2 controllers, strategies — official.
- TradingView Pine Script v6 documentation and Community Scripts — official.
- Freqtrade official strategies repository — primary repository.
- QuantCode-Bench (2026) — research benchmark; research evidence, not production proof.
- Kraken regulation/region and funding support — official; insufficient alone for complete Israel venue approval.
- Coinbase prohibited-regions documentation — official; insufficient alone for complete Israel venue approval.

## Phase 3 additions — checked 2026-07-05

| Source | Category | Use | Evidence strength |
|---|---|---|---|
| https://developers.binance.com/docs/binance-spot-api-docs/ | Official venue docs | Binance Spot API/changelog | Strong |
| https://developers.binance.com/en/docs/products/spot/testnet/general-info | Official venue docs | Spot Testnet | Strong |
| https://docs.kraken.com/ | Official venue docs | Kraken REST/WS/FIX | Strong |
| https://docs.kraken.com/api/docs/guides/spot-ratelimits/ | Official venue docs | Kraken trading limits | Strong |
| https://docs.kraken.com/api/docs/guides/spot-l3-data | Official venue docs | Kraken L3 data | Strong |
| https://www.coinbase.com/developer-platform/products/advanced-trade-api | Official venue docs | Coinbase Advanced Trade API | Strong |
| https://github.com/coinbase/coinbase-advanced-py | Official SDK | Coinbase Python SDK | Strong |
| https://www.okx.com/en-eu/okx-api | Official venue docs | OKX API/demo capability | Strong |
| https://tardis.dev/ | Official provider | Tick/order-book crypto data | Strong for capability |
| https://www.coinapi.io/products/market-data-api | Official provider | Normalized crypto data | Strong for capability |
| https://docs.kaiko.com/explore-our-data/data-dictionary | Official provider docs | Crypto data products/history | Strong for capability |
| https://databento.com/docs/api-reference-historical | Official provider docs | Historical multi-asset data | Strong |
| https://mlflow.org/docs/latest/ml/tracking/ | Official docs | Experiment tracking | Strong |
| https://mlflow.org/docs/latest/ml/dataset/ | Official docs | Dataset lineage | Strong |
| https://doc.dvc.org/example-scenarios/versioning-data-and-models | Official docs | Data/artifact versioning | Strong |
| https://arxiv.org/abs/2604.15151 | Research paper | QuantCode-Bench | Primary research |
| https://arxiv.org/abs/2605.17937 | Research paper | BacktestBench | Primary research |
| https://arxiv.org/abs/2605.28359 | Research paper | KTD-Fin leakage/attribution | Primary research |
