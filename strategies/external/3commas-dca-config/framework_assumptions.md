# Framework Assumptions — STRAT-EXT-3COMMAS-DCA-CONFIG

This external replay candidate is deliberately framework-neutral:

- canonical signal timing: evaluate at bar close, execute at next bar open;
- warm-up: RSI(14) and SMA(20) must both be available before signals can appear;
- DCA add-ons are represented as local replay metadata in `position_sizing`;
- engine adapters must reject or ignore DCA add-on metadata until a dedicated replay
  implementation exists;
- all calculations use frozen OS data and declared fee/slippage assumptions;
- no 3Commas account, exchange link, API key, paper venue, demo venue, or live venue
  is present or required.

The first implementation target is local replay validation, not engine execution.
