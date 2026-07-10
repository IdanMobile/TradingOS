# B2 BTC Parity Residual Report

Status: **EXPLAINED, NOT FILL-IDENTICAL**

The 77-roundtrip residual is retained as an engine-semantics result, not hidden or
converted into a P&L comparison.

## Evidence

- Full period: Freqtrade 66,385 vs Hummingbot 66,462
  roundtrips.
- Canonical BTCUSDT 5m data: 7 gap events containing
  213 missing bars; the largest gap is 56 bars.
- Before the first data gap, after shifting Hummingbot to next-open timing, the
  gap-free segment still has small localized timestamp differences. This proves
  execution/order-state behavior exists independently of the later data gaps.
- An explicit Freqtrade market-order probe still produced 66,385
  roundtrips. One retained exit is timestamped `2021-01-01 08:15:00+02` at price `29187.01000000`,
  which equals the source candle open at `2021-01-01 08:00:00+02`. The engine therefore
  carries order price and reported fill time through different state transitions.

## Interpretation

Freqtrade uses prior-bar signals, a regular synthetic backtest clock, startup
trimming, and its own order lifecycle. Hummingbot's retained controller creates
executors on current-candle signals and iterates retained timestamps. Missing
candles and delayed exit state therefore affect the two engines differently.

The engines remain useful for different roles, but this full-period context is not
a fill-parity or P&L-parity fixture. Future semantic parity must use contiguous
windows with explicit signal, decision, order, and fill timestamps.

Machine-readable evidence: `artifacts/bakeoff/parity/b2_residual_analysis.json`.
