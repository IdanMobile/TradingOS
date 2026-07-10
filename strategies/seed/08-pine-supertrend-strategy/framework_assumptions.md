# Framework assumptions -- SRC-PINE2

- Pine's ATR-based Supertrend indicator warms up over its window internally; mapped to an explicit warm-up assumption here, same pattern as SRC-PINE1's Bollinger warm-up.
- Pine strategies fill on the next bar's open by default -- mapped to this project's "next bar open" execution assumption without modification.
- No fee/slippage asserted by the indicator/strategy logic itself (engine/backtest-run concern).
