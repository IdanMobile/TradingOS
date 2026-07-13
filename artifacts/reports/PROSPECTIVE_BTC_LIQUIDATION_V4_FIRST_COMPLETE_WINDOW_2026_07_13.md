# Prospective BTC Liquidation Observer V4 — First Complete Window

Date: 2026-07-13  
Run commit: `ab5a088`  
Execution authority: `NONE`

## Verified source and signal result

Observer V4 continuously covered `2026-07-13T19:59:41.581969Z` through
`20:05:00.002547Z`, fully enclosing `[20:00Z,20:05Z)`. The source published zero force-order
snapshots during the window.

- Session schema: 4
- Session SHA-256: `54ea7fae90fbcbbcbd78b0c9bc510d62eacf0bb17f3181a74a5a970842a9cdbc`
- Source status: `COMPLETE`
- `source_failure`: null
- Complete windows: one
- Gross/buy/sell snapshot notional: USD 0 / 0 / 0
- State: `WARMUP_BLOCK`
- Signal: `SIG-a512bf546de4bb5cb3c893c2`, side `FLAT`
- Independent risk decision: `BLOCK`
- Metric, scorecard, and promotion eligibility: false

This proves the V4 successful-session evidence path after the `o.st` correction. The retained V3
live message and corrected tests prove parsing of an actual `o.st: 2` record; this zero-event V4
window does not independently exercise a second live event.

Three complete windows now exist in total, but each is isolated from the others by unobserved or
failed intervals. The longest consecutive warm-up chain remains one of 8,640.

## Causal label schedule

At `2026-07-13T20:05:21.578176Z`, the label evaluator retained a nine-row snapshot. The first
window's 1h label remained `AVAILABLE_RETAIN_ONLY`; the other eight labels were
`NOT_AVAILABLE` and caused no request. Snapshot SHA-256:
`566efb7010ebb16f98dece601a743ef0016735b75078c396d88b0fad894517fc`.

No label was aggregated, interpreted, or scored.

No credential, account session, venue connection, order, fill, position, paper/demo/live state,
sealed V2 holdout access, human gate, or execution authority was activated.
