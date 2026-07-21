# Demo Transport Security Review — Stage 2 (2026-07-19)

Authority: D-104. Completes the D-046-mandated typed adapter/reconciliation review for order
placement. Stage 1 (read-only GETs) was approved earlier tonight
(`DEMO_TRANSPORT_SECURITY_REVIEW_2026_07_19.md`).

## Design decision

The quarantine on the raw demo scripts' POST transports (`rt._post_transport`,
`demo_strategy_bot`/`demo_carry_bot`/`demo_managed_bot` order paths) is **kept permanently**.
Instead of removing the guard, order flow moves behind a single new typed adapter:
`scripts/demo_eth_lane.py`. This is the literal reading of D-046 — "a typed
adapter/reconciliation review rather than merely removing the guard".

Core `tios.trading_domain` contracts stay frozen: demo environments remain unconstructable
in the domain model (`test_demo_paper_and_other_environments_cannot_be_constructed` still
passes untouched). The lane is a bounded sidecar whose records are explicitly labeled
`VENUE_DEMO` / `real_money: false` / `UNVALIDATED`.

## Review findings (scripts/demo_eth_lane.py)

1. **Typed intents.** Every order must be a `LaneIntent`; construction rejects unknown
   sides/units, non-positive qty, and side/unit mismatches (Buy must be quote-sized).
2. **Single sanctioned POST.** `_live_post_transport` is the only live order transport in
   the codebase: https-only, demo-host-only (refuses scheme/host/suffix tricks — tested),
   10s timeout. All other POST paths still raise the quarantine error (tested).
3. **Kill switch.** Presence of `artifacts/trading_domain/demo_lane/KILL_SWITCH` refuses
   orders before any network call and records the refusal to the ledger (tested).
4. **Caps.** Buy notional ≤ 50 USDT (shared `rt.MAX_NOTIONAL`); independent sell cap
   ≤ 120 USDT valued at live ticker price (closes the stage-1 gap); sell qty quantized down
   to the instrument's `basePrecision` from live instruments-info (fallback 1e-5) (tested).
5. **Reconciliation.** Every order records wallet before/after deltas, fill price, fee, and
   order status in an append-only fsync'd ledger (`orders.jsonl`) (tested).
6. **Lane inventory isolation.** The lane sells only `lane_base` — base acquired by its own
   fills — never the demo account's pre-existing grant balances (1 ETH etc.).
7. **Signal integrity.** Signals come from the unchanged canonical spec + evaluator
   (`SV-418ab5d64825c74b`); the lane acts only on transitions newer than its persisted
   cursor, so restarts cannot re-fire old signals and only post-start transitions trade
   (prospective discipline preserved; first cycle arms the cursor and never trades — tested).
8. **No secret egress.** Keys load from git-ignored `.env` by name filter; no record, log,
   or heartbeat contains key material.

Verification: 8 new offline tests in `tests/test_demo_eth_lane.py` (incl. a synthetic
breakout driven through the real evaluator to a placed fake order); 28 demo-suite tests
green; ruff + repo mypy gate green.

## Residual limits (accepted, recorded)

- ETHUSDT only; multi-symbol needs per-symbol instrument metadata.
- Market orders only (measurement lane measures taker execution by design).
- Hourly polling loop, not a websocket feed — acceptable at 1h timeframe.
- Venue price feed is the demo venue's klines; backtest comparisons against Binance-frozen
  data must carry a feed scope note.

Status: **Stage 2 APPROVED — typed lane is the sole order path; raw-script POSTs stay
quarantined forever.**
