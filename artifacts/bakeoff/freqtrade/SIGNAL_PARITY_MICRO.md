# Freqtrade signal-timestamp parity probe vs fixtures/micro/ goldens (T-006-02)

Overall: **PASS** · Tolerance: exact per-bar boolean match (0 bars), per fixtures/micro/GOLDEN_DERIVATION.md (no tolerance is defined there or in fixtures/strategies/baselines/*.yaml).

Method: the generated freqtrade strategy classes (engines/freqtrade/lane/user_data/strategies/) are applied directly to fixtures/micro/bars.csv (16 bars) via populate_indicators/populate_entry_trend/populate_exit_trend, run inside engines/freqtrade/.venv (signal_parity_worker.py, subprocess-isolated per AD-02). Output compared bar-by-bar against expected_signals_B{1-4}.csv.

| Baseline | Status | Bars compared | Mismatches |
|---|---|---|---|
| B1 | PASS | 16 | 0 |
| B2 | PASS | 16 | 0 |
| B3 | PASS | 16 | 0 |
| B4 | PASS | 16 | 0 |

