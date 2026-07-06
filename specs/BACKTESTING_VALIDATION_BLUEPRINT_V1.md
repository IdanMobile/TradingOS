# Backtesting Validation Blueprint V1

Status: Approved specification for prototype implementation.
Purpose: prevent historical fit from being mistaken for durable trading edge.

## Core rule

A backtest is an experiment artifact, not an approval.

## Validation ladder

```text
Hypothesis
  -> Semantic sanity
  -> Data integrity
  -> Baseline backtest
  -> Bias/leakage checks
  -> Cost stress
  -> Temporal OOS
  -> Walk-forward
  -> Parameter robustness
  -> Regime analysis
  -> Multiple-testing / overfit evidence
  -> Paper forward test
  -> Limited-live eligibility review
```

## V1 required gates

### G1 — Reproducibility
Required:
- code commit;
- dataset ID/hash;
- engine/version;
- parameters;
- fees/slippage;
- deterministic seed where applicable;
- rerun parity.

PASS: repeated run under identical inputs matches required deterministic fields and metrics within documented tolerance.

### G2 — Data and timestamp integrity
Required checks:
- monotonic timestamps;
- duplicate detection;
- missing interval report;
- timezone normalization;
- no future feature access.

### G3 — Semantic correctness
Compare:
- canonical strategy spec;
- generated/implemented engine logic;
- sample signal timestamps;
- sample order timestamps;
- same-bar assumptions.

### G4 — Lookahead/leakage
Required:
- Freqtrade `lookahead-analysis` where the strategy is represented in Freqtrade;
- equivalent temporal leakage tests for other engines;
- feature availability timestamp audit.

Any confirmed material leakage => REJECT until fixed.

### G5 — Transaction-cost stress
Run Fee/Slippage Package V1 grid.
Report:
- gross expectancy;
- net expectancy;
- turnover;
- break-even cost threshold.

### G6 — Temporal out-of-sample
Minimum design for V1:
- chronological development segment;
- chronological validation segment;
- untouched final holdout.

No random shuffle for time-series strategy approval.

The coding agent must materialize exact dates from the frozen dataset manifest and record them before parameter optimization.

### G7 — Walk-forward
At least one rolling or expanding walk-forward evaluation.
Record:
- train window;
- test window;
- step;
- retuning rules.

### G8 — Parameter robustness
Required:
- local neighborhood around chosen parameters;
- performance surface;
- parameter cliff detection.

A single isolated optimum is a warning or rejection signal.

### G9 — Regime analysis
At minimum segment by observable ex-post descriptive regimes such as:
- higher/lower realized volatility;
- positive/negative trend;
- high/low volume.

Do not claim causal regime prediction from this gate.

### G10 — Multiple-testing / overfit evidence
Track:
- number of tried configurations;
- selection procedure;
- all trials, not only winners.

Evaluate DSR/PBO-style methods as validated method candidates. Exact implementation must be verified against primary literature before production use.

Primary research references:
- Probability of Backtest Overfitting: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
- Deflated Sharpe Ratio: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551

### G11 — Benchmark comparison
Compare candidate strategy against relevant simple baselines:
- buy-and-hold;
- cash/no-trade;
- simple family baseline where appropriate.

### G12 — Paper-forward gate
Backtest survivor must enter paper/dry mode before any real-money eligibility.
Track:
- signal frequency divergence;
- fill assumption divergence;
- cost divergence;
- P&L divergence;
- operational failures.

## Required output package

Each validation run produces:
- `validation_summary.json`
- `trade_log.parquet|csv`
- `equity_curve.parquet|csv`
- `metrics.json`
- `cost_sensitivity.json`
- `oos_report.json`
- `walk_forward_report.json`
- `parameter_robustness.json`
- `regime_report.json`
- `bias_report.json`
- `provenance.json`
- charts as optional presentation artifacts

## Approval rule

No weighted average can override a hard-fail gate.

Examples of hard fail:
- material lookahead leakage;
- unreproducible result;
- profitability only under zero costs;
- final holdout used for tuning;
- unknown dataset provenance.
