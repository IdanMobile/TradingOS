# Ambiguities -- SRC-HB1 (Hummingbot supertrend_v1)

1. The current official controller signal is tri-state: pandas-ta direction level `+1/-1` is admitted only when close is within the configured one-percent distance from the Supertrend line; otherwise it emits `0`. This is now represented literally rather than as a direction-change rule.
2. Triple-barrier risk config (SL/TP/trailing/time-limit) exists at the controller-config level in the real source but has no equivalent in this project's single stop_loss/take_profit risk block -- documented gap, not resolved.
3. Exact pandas-ta parity still requires an independent known-answer comparison; the local implementation follows the published ATR/RMA and recursive-band definition.
