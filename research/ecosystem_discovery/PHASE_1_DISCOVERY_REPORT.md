# Trading OS Ecosystem & Reuse Discovery — Phase 1 Report

Checked: 2026-07-05
Status: Initial broad discovery complete; deep validation remains partial for several categories.

## Executive finding

The ecosystem is rich enough that the MVP should not be built around a single monolithic custom trading stack. The strongest current direction is a composable reuse strategy:

- execution-grade/event-driven engine candidates for deterministic simulation and live parity;
- crypto-native bot frameworks for rapid spot-market proof and reusable operational patterns;
- vectorized research accelerators for large hypothesis sweeps;
- dedicated experiment/dataset lineage tooling;
- separate AI/agent evaluation infrastructure;
- custom Trading OS domain layers only where cross-engine evidence, approvals, provenance, and memory are the differentiator.

This report does **not** approve final architecture.

## 1. Trading / execution engines

### NautilusTrader
- Category: production-grade event-driven engine.
- Official evidence: Rust-native core spanning research, deterministic simulation, portfolio/risk modeling, and live execution under one architecture.
- Current signal: official site listed v1.228.0 during this check and recent release activity.
- Reuse fit: High for event-driven simulation/live execution core candidate.
- Main caveat: integration/venue coverage and complexity must be proven in our exact Crypto Spot slice.
- Status: Validated Candidate for bake-off.
- References:
  - https://nautilustrader.io/
  - https://nautilustrader.io/docs/latest/

### LEAN / QuantConnect
- Category: open-source multi-asset engine and managed/local research platform.
- Official evidence: research, backtesting, live trading; Algorithm Framework separates Universe, Alpha, Portfolio Construction, Risk, Execution.
- Reuse fit: High for broad multi-asset architecture patterns and future portability.
- Main caveat: local/cloud boundaries, data/licensing and operational fit need exact testing.
- Status: Validated Candidate for bake-off.
- References:
  - https://www.quantconnect.com/docs/v2
  - https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/overview
  - https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/risk-management/key-concepts

### Freqtrade
- Category: crypto-native open-source trading bot.
- Official evidence: backtesting, dry-run/live bot operation, hyperopt using Optuna, lookahead-analysis, recursive-analysis, web UI/API patterns.
- Reuse fit: Very high for Crypto Spot MVP experimentation and operational prior art.
- Main caveat: not a universal multi-market core; dataframe/backtest semantics need independent validation.
- Status: Validated Candidate for Crypto Spot lab/bake-off.
- References:
  - https://www.freqtrade.io/en/stable/backtesting/
  - https://www.freqtrade.io/en/stable/hyperopt/
  - https://www.freqtrade.io/en/stable/lookahead-analysis/
  - https://www.freqtrade.io/en/stable/recursive-analysis/

### Hummingbot
- Category: crypto market-making and algorithmic bot framework.
- Official evidence: modular framework for CEX/DEX strategies, strategy controllers, bot dashboard, Quants Lab/research resources.
- Reuse fit: High for market-making, connectors, bot-fleet/dashboard prior art, crypto-native operational concepts.
- Main caveat: primary orientation differs from our evidence-first cross-strategy OS; exact spot strategy fit must be tested.
- Status: Validated Candidate for selective reuse and comparison.
- References:
  - https://hummingbot.org/docs/
  - https://hummingbot.org/dashboard/
  - https://hummingbot.org/quants-lab/

## 2. Backtesting and rapid research

### vectorbt
- Category: vectorized quantitative research/backtesting accelerator.
- Official evidence: pandas/NumPy-oriented, accelerated approach for testing many strategy configurations; integrates indicator ecosystems.
- Reuse fit: High for fast screening and parameter-surface exploration.
- Main caveat: high-throughput search increases multiple-testing/false-discovery risk; cannot be approval authority by itself.
- Status: Validated Candidate as research accelerator.
- References:
  - https://vectorbt.dev/
  - https://vectorbt.dev/getting-started/features/

### Backtrader
- Category: Python event-driven backtesting/trading framework.
- Official evidence: reusable strategies, indicators, analyzers; open source.
- Reuse fit: Medium as benchmark/reference framework and for LLM strategy-generation benchmarks.
- Main caveat: maturity/maintenance and production fit need deeper validation; should not outrank modern candidates without evidence.
- Status: Tentative Candidate / benchmark reference.
- Reference: https://www.backtrader.com/

### QuantConnect Strategy Library
- Category: reusable strategy education/implementations.
- Official evidence: tutorials based on strategies found in academic literature and implemented with LEAN.
- Reuse fit: High as a strategy-source registry seed, not as proof of profitability.
- Status: Validated Source Candidate.
- Reference: https://www.quantconnect.com/docs/v2/writing-algorithms/strategy-library

## 3. Statistical validation and anti-overfitting

### Probability of Backtest Overfitting (PBO)
- Evidence: Bailey et al. propose estimating backtest overfitting using combinatorially symmetric cross-validation.
- Reuse fit: High as a validation method candidate.
- Status: Validated Method Candidate; implementation details still need engineering review.
- Reference: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253

### Deflated Sharpe Ratio (DSR)
- Evidence: corrects for selection bias under multiple testing and non-normal returns.
- Reuse fit: High for experiment campaigns that test many variants.
- Status: Validated Method Candidate.
- Reference: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551

### Freqtrade bias diagnostics
- lookahead-analysis: detects common future-data contamination patterns.
- recursive-analysis: detects indicator warmup/recursive discrepancies between backtest and live-like data availability.
- Reuse fit: High as executable diagnostics in a Freqtrade lane and as requirements for our cross-engine validation design.
- References:
  - https://www.freqtrade.io/en/stable/lookahead-analysis/
  - https://www.freqtrade.io/en/stable/recursive-analysis/

## 4. Hyperparameter optimization

### Optuna
- Discovery finding: already used by Freqtrade hyperopt and supported in MLflow integration examples.
- Reuse fit: High for controlled optimization experiments.
- Caveat: optimizer output must never bypass multiple-testing controls or OOS gates.
- Status: Validated Candidate pending exact version check at implementation.
- References:
  - https://www.freqtrade.io/en/stable/hyperopt/
  - https://mlflow.org/docs/latest/ml/traditional-ml/tutorials/hyperparameter-tuning/notebooks/hyperparameter-tuning-with-child-runs/

## 5. Experiment lineage and reproducibility

### MLflow
- Official evidence: experiment tracking for parameters, code versions, metrics, artifacts; dataset tracking; LLM/agent evaluation and tracing capabilities.
- Reuse fit: Very high for experiment lineage and AI/agent evaluation backbone candidate.
- Caveat: our trading-specific approval/evidence ontology remains custom domain logic.
- Status: Validated Candidate.
- References:
  - https://mlflow.org/docs/latest/ml/tracking/
  - https://mlflow.org/docs/latest/ml/dataset/
  - https://mlflow.org/docs/latest/

### DVC
- Official evidence: experiment tracking with automatic bookkeeping of dependencies, code, parameters, artifacts, models, metrics; data versioning workflows.
- Reuse fit: High for dataset/artifact reproducibility, especially laptop-first/Git-oriented workflows.
- Caveat: overlap with MLflow/lakeFS must be evaluated to avoid redundant tooling.
- Status: Validated Candidate.
- Reference: https://doc.dvc.org/example-scenarios/experiment-tracking

### lakeFS
- Official evidence: data versioning with integration patterns for MLflow to preserve dataset version lineage.
- Reuse fit: Medium/High for larger object-store datasets; likely later than DVC for laptop-first MVP unless scale justifies it.
- Status: Tentative Candidate.
- Reference: https://docs.lakefs.io/integrations/mlflow/

## 6. Technical-analysis and indicator libraries

### TA-Lib
- Official evidence: open-source BSD library, ~200 indicators and candlestick pattern recognition, C/C++ core with Python/R APIs.
- Reuse fit: High as canonical indicator implementation source.
- Caveat: indicator availability is not evidence of trading edge.
- Status: Validated Candidate.
- References:
  - https://ta-lib.org/
  - https://ta-lib.org/functions/

### vectorbt indicator integration
- Official evidence: supports broad indicator ecosystems and custom indicator factories.
- Reuse fit: High for research acceleration.
- Status: Validated Candidate.
- Reference: https://vectorbt.dev/getting-started/features/

## 7. Crypto connectivity and market data

### CCXT
- Official evidence: unified exchange API and exchange-specific access.
- Reuse fit: High for normalized crypto connectivity and data access, with native exchange fallback.
- Caveat: unified API does not erase venue-specific semantics, rate limits, order behavior, or failure modes.
- Status: Validated Candidate.
- Reference: https://github.com/ccxt/ccxt/wiki/manual

### Binance official Spot API
- Official evidence: REST/WebSocket market data and order-book streams; active changelog/API evolution.
- Reuse fit: High as native-adapter reference and likely first data/execution candidate if jurisdiction/eligibility fit passes.
- Caveat: exchange decision remains unresolved; Israel operator context requires verification.
- References:
  - https://developers.binance.com/docs/binance-spot-api-docs/
  - https://developers.binance.com/docs/binance-spot-api-docs/websocket-api/market-data-requests

### Tardis.dev
- Official evidence: historical crypto market data including streamed order books reconstructed from snapshot + incremental updates; current changelog activity.
- Reuse fit: High for deep crypto tick/order-book research candidate.
- Caveat: cost and exact venue coverage need pricing/fit validation.
- Status: Validated Candidate for shortlist.
- References:
  - https://docs.tardis.dev/faq/order-books
  - https://docs.tardis.dev/changelog

### Databento
- Official evidence: live/historical market data with schemas including order book, trades, and aggregates; unified formats across venues/asset classes.
- Reuse fit: High for future multi-asset and high-quality data needs.
- Caveat: first Crypto Spot venue coverage/cost fit must be checked.
- Status: Validated Candidate for data bake-off/shortlist.
- References:
  - https://databento.com/docs
  - https://databento.com/docs/api-reference-historical

## 8. Strategy and knowledge sources

### QuantConnect Strategy Library
- Strong seed for academically referenced strategies and LEAN implementations.
- Status: Validated Source Candidate.

### Hummingbot strategy/controllers + guides
- Strong seed for crypto market-making and execution-oriented strategy patterns.
- Status: Validated Source Candidate.
- References:
  - https://hummingbot.org/docs/
  - https://hummingbot.org/guides/

### TradingView / Pine ecosystem
- Discovery: large public strategy/indicator ecosystem exists, including active GitHub collections.
- Reuse decision: treat as hypothesis/implementation source only; never import claimed profitability as evidence.
- Status: Source Category Confirmed; candidate repositories require per-repo validation.

### Curated discovery lists
- `awesome-quant` and active systematic-trading lists can accelerate discovery.
- Use only for discovery; not as primary validation.
- Status: Discovery sources only.

## 9. AI / agent evaluation and quant-specific benchmarks

### MLflow LLM/agent evaluation
- Reuse fit: High as evaluation/tracing/experiment infrastructure candidate.
- Status: Validated Candidate.

### BacktestBench (2026 research)
- Research contribution: benchmark for automated quantitative backtesting with 18,246 annotated QA pairs and multi-agent baseline.
- Reuse fit: High as benchmark-design prior art; research evidence, not production validation.
- Status: Research Candidate.
- Reference: https://arxiv.org/abs/2605.17937

### QuantEval (2026 research)
- Research contribution: benchmark across quant knowledge, mathematical reasoning, and strategy coding with deterministic backtesting configuration.
- Reuse fit: High for AI Model & Agent Benchmark Lab design.
- Status: Research Candidate.
- Reference: https://arxiv.org/abs/2601.08689

### QuantCode-Bench (2026 research)
- Research contribution: 400 strategy-generation tasks, executable backtests, trade-presence checks, semantic alignment; shows failures often come from operationalizing trading logic rather than syntax.
- Reuse fit: Very high for our task-specific AI evaluation philosophy.
- Status: Research Candidate.
- Reference: https://arxiv.org/abs/2604.15151

### FinRL-X (2026 research)
- Research contribution: modular, deployment-consistent architecture integrating rule-based and AI-driven components.
- Reuse fit: Medium/High as architecture prior art and possible ML/RL research source.
- Status: Research Candidate; not production-approved.
- Reference: https://arxiv.org/abs/2603.21330

## 10. Initial architecture consequence

The evidence currently argues against these premature choices:
- one monolithic custom engine;
- one universal backtester;
- one model score;
- one strategy repository treated as truth;
- one experiment tracker built from scratch;
- custom indicator implementations by default.

The evidence supports a **composable platform** with a custom Trading OS control/evidence plane around validated reusable engines and tools.

## Discovery saturation status

| Capability | Status | Notes |
|---|---|---|
| Execution-grade engines | Sufficient for initial shortlist | Nautilus, LEAN, Freqtrade, Hummingbot categories represented |
| Backtesting/research accelerators | Sufficient for initial shortlist | event-driven + vectorized represented |
| Anti-overfitting methods | Sufficient conceptually | implementation mapping remains |
| Experiment lineage | Sufficient for initial shortlist | MLflow/DVC/lakeFS represented |
| Indicator libraries | Sufficient for initial shortlist | TA-Lib + integrations represented |
| Crypto connectivity | Partial | need venue-specific exchange shortlist |
| Crypto historical data | Partial | Tardis/Databento/native sources; pricing and venue fit pending |
| Strategy sources | Partial | academic/QuantConnect/Hummingbot/Pine discovered; registry not built |
| Risk/portfolio | Partial | LEAN/Nautilus prior art found; broader comparison pending |
| AI eval | Partial-to-Sufficient for initial design | MLflow + 2026 quant benchmarks found; tool comparison pending |
| Dashboard/UI reuse | Insufficient | dedicated research pending |
| Job orchestration | Insufficient | dedicated research pending |
| Knowledge graph/ontology | Insufficient | dedicated research pending |
| News/sentiment/on-chain | Insufficient | later discovery pending |

## Phase 1 recommendation

Proceed to a **targeted MVP reuse deep dive**, not implementation. The next research tranche should produce:
1. Engine bake-off shortlist and executable common test matrix.
2. Crypto Spot exchange shortlist for an Israel-based operator.
3. Crypto historical data shortlist with exact cost/coverage criteria.
4. Initial Existing Strategy Registry.
5. Experiment lineage decision: MLflow vs DVC vs hybrid.
6. AI/Agent Eval Blueprint using quant-specific benchmark ideas.
