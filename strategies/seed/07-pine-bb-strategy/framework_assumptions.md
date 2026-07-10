# Framework assumptions -- SRC-PINE1

- Pine's ta.sma/ta.stdev-based indicators warm up over their window internally (return `na` before ready); mapped to an explicit warm-up assumption here.
- Pine strategies fill on the next bar's open by default (`process_orders_on_close` off) unless explicitly configured otherwise -- mapped to this project's "next bar open" execution assumption without modification.
- No fee/slippage asserted by the indicator/strategy logic itself (Pine's `strategy()` call takes commission params separately -- an engine/backtest-run concern per the reproduction gates table).
