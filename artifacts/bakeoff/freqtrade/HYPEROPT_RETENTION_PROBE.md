# Freqtrade bounded hyperopt + all-trial-retention probe (T-006-02)

Strategy: B2MaCrossover · Timerange: 20250101-20250401 (bounded, probe speed) · Epochs requested: 8 · Spaces: roi, stoploss · Loss: SharpeHyperOptLoss

Hyperopt run exit code: 0

Retention check: **PASS**
- requested epochs: 8
- epochs retained in results store (via `freqtrade hyperopt-list --export-csv`): 8
- results store copy: `artifacts/bakeoff/freqtrade/hyperopt_probe/strategy_B2MaCrossover_2026-07-07_16-43-41.fthypt`

Evidence: `hyperopt_stdout.log`, `hyperopt_stderr.log`, `hyperopt_list_stdout.log` under `artifacts/bakeoff/freqtrade/hyperopt_probe/`.
