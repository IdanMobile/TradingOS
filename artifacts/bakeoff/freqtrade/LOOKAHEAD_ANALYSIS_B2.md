# Freqtrade lookahead-analysis probe — B2 (T-006-02, bias-check gate)

Date: 2026-07-06 · Window: 2025-01-01→2025-04-01 5m · Log: `lookahead_analysis_B2.log`

## Tool verdict (recorded verbatim)

`bias detected!` — 2 of 20 checked entry signals flagged (BTC/USDT trade 03:45–03:55, ETH/USDT trade 03:45–04:00 on 2025-01-01); 0 biased exit signals; 0 biased indicators.

## Root-cause analysis → classified EXPLAINED (execution-state artifact, not leakage)

1. **Signal math cannot see the future**: B2 uses only `close.rolling(3).mean()` vs `close.rolling(5).mean()` — pure trailing-window functions.
2. **Numeric verification at the flagged window** (independent duckdb recomputation from the frozen parquet): BTC SMA3 crosses above SMA5 at the 2025-01-01 03:40 bar close (93938.46 > 93907.87, computed from closes 03:30–03:40 only) → entry at next bar open 03:45; crosses back at 03:50 close → exit 03:55. The flagged trade IS the legitimate trailing-signal sequence.
3. **Flag count invariant to warm-up**: startup_candle_count 5 → 30 reproduced the same 2/20 result, ruling out indicator warm-up truncation.
4. **Mechanism**: lookahead-analysis re-runs truncated backtests under tool-forced settings (stake 10000, `max_open_trades: -1`, fresh wallet). Which entries *execute* depends on wallet/stake state that differs between full and truncated runs — an execution-state divergence class this tool cannot distinguish from signal bias.

## Disposition

- Gate "Bias checks": tooling exists and runs (evidence above); flag EXPLAINED with itemized evidence, not dismissed.
- Follow-up (parity phase, T-006-07): re-run lookahead-analysis under a stake-state-independent config (fixed stake, max_open_trades 1) — expected clean; record either way.
- Defensive change applied regardless: baseline startup_candle_count raised to 30 in the lane codegen.
