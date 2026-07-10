# T-006-06 — vectorbt Accelerator Probe Conclusion

Status: **COMPLETE — SELECT AS RESEARCH ACCELERATOR, NOT PEER ENGINE**

vectorbt 1.1.0 is retained for fast, broad hypothesis falsification. It is not a
production execution engine, strategy approver, or peer in fill/P&L parity.

## Executed evidence

| Family | Trials | Bars | Elapsed | Throughput | Retained |
|---|---:|---:|---:|---:|---|
| B2 MA crossover | 34 | 577,803 | 4.572s | 4,297,079 bar-trials/s | 34/34 |
| B3 Bollinger mean reversion | 16 | 577,803 | 1.621s | 5,703,031 bar-trials/s | 16/16 |
| B4 volatility breakout | 16 | 577,803 | 1.709s | 5,408,512 bar-trials/s | 16/16 |

All 66 trials are retained in three Parquet populations and registered as 66
completed runs across three experiments in `trial_ledger.jsonl`. No winner was
selected. The ledger summary independently confirms `all_trials_registered=true`.

## Binding boundary

`OVERFIT_CONTROLS.md` requires predeclared parameter families, full-population
retention, temporal/holdout/walk-forward/cost/multiple-testing evidence, and
event-engine reproduction before any survivor can become eligible. AI cannot hide,
select, or approve trials.

The accelerator verdict is therefore positive for research throughput and negative
for direct paper/live authority. In-sample returns in these artifacts are diagnostics,
not expected-profit claims.

Evidence:

- `b2_sweep_all_trials.parquet`, `b3_sweep_all_trials.parquet`, `b4_sweep_all_trials.parquet`
- `b2_sweep_meta.json`, `b3_sweep_meta.json`, `b4_sweep_meta.json`
- `trial_ledger.jsonl`, `trial_ledger_summary.json`
- `OVERFIT_CONTROLS.md`
