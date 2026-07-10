# Freqtrade recursive analysis — B2

Status: **PASS**

The native analyzer ran over BTC/USDT 5m for 2025-01-01 through 2025-04-01
with startup windows 5, 30, and 100. It reported no recursive indicator
variance and no indicator-only lookahead bias.

This closes indicator warm-up recursion for B2; it does not erase the separately
retained execution-state warning from `LOOKAHEAD_ANALYSIS_B2.md`.

Raw log: `artifacts/bakeoff/freqtrade/recursive_probe/run.log`.
