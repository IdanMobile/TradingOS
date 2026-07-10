# Freqtrade Lane Closure Report

Status: **COMPLETE — RETAIN AS CRYPTO SPOT RESEARCH/BACKTEST ENGINE WITH CONSTRAINTS**
Date: 2026-07-10

Integration remains CLI/subprocess-only across the GPL boundary. This report
closes the S1 probe lane; it does not authorize paper or live trading.

## Blueprint gates

| Gate | Result | Evidence / boundary |
|---|---|---|
| Installability | PASS | isolated 2026.6 environment and manifest |
| Data ingestion | PASS WITH GAP CONSTRAINT | canonical Feather conversion is row-count checked; use contiguous windows because regular-clock simulation and missing bars can diverge |
| Determinism | PASS | retained B2 run1/run2 normalized artifacts are identical |
| Signal parity | PASS | B1–B4 exact 16-bar canonical fixture match |
| Fee modeling | PASS | normalized P&L/fee recomputation audits pass |
| Slippage | CAPABILITY GAP | no native per-side bps backtest model; post-hoc grid is explicit |
| Precision | PASS WITH DECLARED LOSS | 577,803 BTC rows checked; decimal128→float64 boundary remains declared |
| Warm-up | PASS | B2 recursive analysis at 5/30/100 candles reports no variance |
| Bias checks | WARN | indicator-only lookahead passes; native full lookahead tool forces stake/portfolio settings and retains 2 execution-state flags |
| Parameter sweep | PASS | bounded eight-epoch hyperopt retained all eight trials |
| Artifact export | PASS | trades, equity, metrics, manifests, logs, raw archives |
| Paper path | PASS CAPABILITY | dry-run initialized without credentials and stopped gracefully; no strategy approved |
| Live path | NOT EXECUTED | related runtime path exists; S4 human gates prohibit current testing |
| API integration | PASS | stable CLI/subprocess adapter; no GPL imports into core |
| Failure behavior | PASS | invalid pair and missing export fail observably; success requires a new result artifact, not return code alone |
| Maintenance | PASS | current installed release and supported Binance adapter |

## Required constraints

1. Freqtrade is the primary Crypto Spot research/backtest candidate, not the OS
   approval, portfolio-risk, or execution authority.
2. Full-period data with missing candles is not a fill-parity fixture. Future engine
   parity uses contiguous windows and records signal, decision, order, and fill times.
3. Native lookahead-analysis flags remain WARN until upstream behavior allows the
   requested stake-state-independent configuration; external exact signal parity and
   recursive checks are retained alongside the warning.
4. Transaction-cost approval cannot rely on the zero-cost engine run or native
   slippage; the OS-owned cost grid and later execution model remain mandatory.
5. Dry-run capability is not paper-strategy approval and cannot bypass independent
   risk or human gates.

## Evidence index

- `artifacts/bakeoff/freqtrade/SIGNAL_PARITY_MICRO.md`
- `artifacts/bakeoff/freqtrade/RECURSIVE_ANALYSIS_B2.md`
- `artifacts/bakeoff/freqtrade/LOOKAHEAD_ANALYSIS_B2.md`
- `artifacts/bakeoff/freqtrade/lookahead_fixed_stake/REPORT.md`
- `artifacts/bakeoff/freqtrade/HYPEROPT_RETENTION_PROBE.md`
- `artifacts/bakeoff/freqtrade/DRY_RUN_PROBE.md`
- `artifacts/bakeoff/freqtrade/ADAPTER_SAFETY_PROBE.md`
- `artifacts/reports/B2_PARITY_RESIDUAL_REPORT.md`
