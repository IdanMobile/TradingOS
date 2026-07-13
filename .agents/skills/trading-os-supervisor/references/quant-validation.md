# Quantitative validation and experiment integrity

## Data integrity

Check:

- point-in-time availability;
- look-ahead and label leakage;
- survivorship and delisting bias;
- symbol changes and corporate actions;
- candle close versus intrabar availability;
- missing, duplicated, reordered, or stale records;
- timezone and session boundaries;
- exchange-specific price, mark, index, and funding definitions;
- train, validation, test, and live-shadow separation;
- dataset and feature versioning.

## Realistic simulation

Model, where relevant:

- commissions and exchange fees;
- bid-ask spread;
- slippage and market impact;
- latency and delayed data;
- partial fills and queue position;
- order rejection and cancellation;
- funding, borrow, margin, and liquidation;
- gaps, halts, outages, and disconnected feeds;
- capacity and position-size limits;
- taxes and rebalance costs when material.

## Robustness gates

Require more than one attractive backtest. Use:

- walk-forward or rolling out-of-sample testing;
- untouched holdout periods;
- multiple market regimes and assets where appropriate;
- parameter sensitivity and perturbation tests;
- bootstrap or Monte Carlo analysis;
- drawdown and recovery analysis;
- trade-count and sample-size review;
- probability-of-overfit or multiple-testing review;
- paper or shadow trading before live capital;
- live-versus-backtest drift monitoring.

## Metrics

Review net results after all modeled costs, not headline return alone:

- expectancy per trade;
- profit factor;
- win rate and payoff distribution;
- Sharpe and Sortino with stated assumptions;
- maximum drawdown and time to recovery;
- tail loss and worst streak;
- turnover and exposure;
- capacity and liquidity;
- stability by regime, asset, venue, and timeframe;
- benchmark and opportunity-cost comparison.

## Promotion lifecycle

`Hypothesis → specification → implementation → unit tests → historical research → robustness → out-of-sample → paper/shadow → limited live approval → monitored production`

Each promotion must record the evidence, decision owner, scope, limitations, and rollback or suspension condition.

## Model discipline

Do not add machine learning because the project lacks an obvious edge. First establish a deterministic baseline, a valid label, a realistic benchmark, and a reason ML can improve the decision. Separate model score from strategy score, execution score, economic score, and portfolio score.
