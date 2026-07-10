# Framework assumptions — SRC-QC1

- LEAN's `SimpleMovingAverage` indicator warms up internally (`IsReady` false until the window is full); mapped here to an explicit `warm-up` assumption in the canonical spec rather than LEAN's runtime `IsReady` flag.
- LEAN algorithms commonly issue orders inside `OnData`, evaluated once per consolidated bar — mapped to "signal at bar close, execution at next bar open" for consistency with this project's execution model (LEAN itself supports same-bar market orders; not assumed here).
- No fee/slippage model is specified by the algorithm itself (LEAN applies a configurable brokerage model) — left out of this canonical spec; costs are an engine/backtest-run concern, not a strategy-rule concern, per the workflow's reproduction gates table.
