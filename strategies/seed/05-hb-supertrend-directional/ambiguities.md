# Ambiguities -- SRC-HB1 (Hummingbot supertrend_v1)

1. Real controller signal is tri-state (1/0/-1 on direction CHANGE); this spec collapses it to a two-state >0/<0 rule on direction LEVEL -- a simplification, not a literal reproduction.
2. Triple-barrier risk config (SL/TP/trailing/time-limit) exists at the controller-config level in the real source but has no equivalent in this project's single stop_loss/take_profit risk block -- documented gap, not resolved.
3. Exact commit/file unverified in this pass (no fetch tool used; grounded in this project's own prior Hummingbot bakeoff research plus public knowledge of the controller family).
