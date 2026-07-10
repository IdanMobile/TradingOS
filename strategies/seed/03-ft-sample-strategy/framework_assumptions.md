# Framework assumptions -- SRC-FT1

- freqtrade evaluates `populate_entry_trend`/`populate_exit_trend` once per closed candle; mapped to "signal at bar close, execution at next bar open" per this project's execution model (freqtrade's own backtester fills at next-candle open by default).
- freqtrade's indicator warm-up (`startup_candle_count`) is an explicit config field in real strategies; mapped here to an explicit warm-up assumption in the canonical spec.
- No fee/slippage is asserted by the strategy class itself (freqtrade config sets these separately) -- left out of this canonical spec per the reproduction gates table (costs are an engine/backtest-run concern).
