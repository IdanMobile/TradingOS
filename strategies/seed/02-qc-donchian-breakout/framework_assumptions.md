# Framework assumptions — SRC-QC2

- LEAN's `DonchianChannel` indicator warms up internally; mapped to an explicit warm-up assumption here.
- No fee/slippage/brokerage model asserted by the strategy itself (engine-run concern, not a rule concern).
- Order timing (same-bar vs next-bar) assumed next-bar-open for consistency with this project's execution model.
