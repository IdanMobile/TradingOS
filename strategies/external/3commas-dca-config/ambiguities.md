# Ambiguities — STRAT-EXT-3COMMAS-DCA-CONFIG

Status: **VALIDATION CANDIDATE ONLY / NOT APPROVED**.

This strategy is a local DCA hypothesis derived from public 3Commas DCA product
concepts. It is not a copy of a 3Commas bot configuration and does not inherit any
platform result.

Open ambiguities:

- public 3Commas pages do not define one canonical entry trigger;
- safety-order spacing and sizing are configurable, not uniquely specified;
- take-profit, stop-loss, exchange fee, and execution behavior are account/platform
  dependent;
- canonical spec support for staged DCA add-ons is metadata-only today, not an engine
  execution primitive;
- no source page provides BTCUSDT/ETHUSDT timeframe-specific parameters for this OS.

This item may advance only through local replay tooling, retained trial populations,
and normal validation gates. It cannot directly create platform bots, exchange orders,
paper orders, demo trades, live trades, or real-money actions.
