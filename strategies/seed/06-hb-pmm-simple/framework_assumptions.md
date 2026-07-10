# Framework assumptions -- SRC-HB2

- Hummingbot's `MarketMakingControllerBase` is order-book/quote-driven (refresh timer + spread), not candle-signal-driven; this project's canonical spec is fundamentally candle/indicator-signal shaped, so this mapping is the weakest-fidelity item in the seed batch by design (chosen deliberately to test the workflow against a genuinely mismatched family, per the seed spec's "execution/market-making family if source allows" constraint).
- No fee/slippage asserted by the controller itself (exchange fee schedule is an execution/venue concern).
- No warm-up in the indicator-warmup sense; the controller can start quoting from the first available reference price.
