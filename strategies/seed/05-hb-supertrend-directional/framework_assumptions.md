# Framework assumptions -- SRC-HB1

- Hummingbot V2 controllers compute indicators once per processed candle (`update_processed_data`) and emit executor proposals on the next controller tick -- mapped to "signal at bar close, execution at next bar open" for consistency with this project's execution model.
- Hummingbot's `DirectionalTradingControllerBase` defaults to perpetual-futures markets (per this project's own prior bakeoff-lane research); this canonical spec is market-agnostic and does not assert perpetual-specific mechanics (funding rate, leverage) since those are execution/venue concerns, not signal-rule concerns.
- Triple-barrier risk config (stop-loss/take-profit/trailing-stop/time-limit) is a controller-config concern external to the pandas_ta signal rule; left out of this spec's `risk` block (both null) per the reproduction gates table, and flagged as a semantic gap in ambiguities.md.
