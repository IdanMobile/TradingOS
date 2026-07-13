# Prospective BTC Liquidation Signal — Second Complete Window

Date: 2026-07-13  
Observer run commit: `e831172`  
Verifier V2 freeze commit: `7cc6ef0`  
Execution authority: `NONE`

## Source and signal result

One public unauthenticated BTCUSD_PERP force-order snapshot session covered
`2026-07-13T19:03:12.806244Z` through `19:10:00.018904Z`. It fully enclosed the UTC window
`[19:05Z,19:10Z)`. The source published zero snapshots during that window, which is a valid
complete zero-event observation under the frozen source semantics.

- Session SHA-256: `f1655057e707798e3d142157bdc5eb09028c25b4e89afe113c3e4f04f499f7f1`
- Gross/buy/sell snapshot notional: USD 0 / 0 / 0
- State: `WARMUP_BLOCK`
- Signal: `SIG-142d08b4d8620e0ff682d7f5`, side `FLAT`
- Independent risk decision: `BLOCK`
- Metric, scorecard, and promotion eligibility: false

Two complete windows are retained in total, but `[18:45Z,18:50Z)` and `[19:05Z,19:10Z)` are not
consecutive. The longest continuous warm-up chain is therefore still **one of 8,640**, not two.

## Label refresh and verifier correction

The first refresh attempt failed closed before output because label verifier V1 compared the older
snapshot with a source window captured later. D-086 froze V2 at commit `7cc6ef0`; V2 reconstructs
each snapshot only from windows closed by its own evaluation time. No label term changed.

The post-freeze refresh at `2026-07-13T19:13:25.479773Z` retained six explicit
`NOT_AVAILABLE` rows and no raw Spot response, price, or return. Both label snapshots reconstruct
offline. Snapshot SHA-256:
`f5453680fd3b6fbac1b86f705691da0ebde51a2e252ecea48bd169d7db3a3ccd`.

## Supervisory disposition

This extends the operational source→window→signal→risk-denial→causal-label-schedule path. It does
not establish strategy edge, consecutive warm-up, a score, or promotion. The first lawful outcome
remains the first window's 1h label at or after `2026-07-13T19:52Z`.

No credential, account session, venue connection, order, fill, position, paper/demo/live state,
sealed V2 holdout access, human gate, or execution authority was activated.
