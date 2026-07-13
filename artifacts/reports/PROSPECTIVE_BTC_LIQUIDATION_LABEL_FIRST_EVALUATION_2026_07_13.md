# Prospective BTC Liquidation Label — First Evaluation

Date: 2026-07-13  
Freeze commit: `a09d308`  
Label contract: `PROSPECTIVE-BTC-LIQUIDATION-LABELS-V1`  
Execution authority: `NONE`

## Result

The first evaluation ran at `2026-07-13T19:00:07.914601Z`, after the causal label contract was
committed. It evaluated the one retained complete signal window `[18:45Z,18:50Z)`.

| Horizon | Entry open time | Exit open time | Available at | Status |
|---|---:|---:|---:|---|
| 1h | 18:51Z | 19:51Z | 19:52Z | `NOT_AVAILABLE` |
| 6h | 18:51Z | 00:51Z on July 14 | 00:52Z on July 14 | `NOT_AVAILABLE` |
| 24h | 18:51Z | 18:51Z on July 14 | 18:52Z on July 14 | `NOT_AVAILABLE` |

Because the evaluation preceded every `available_at`, it made no Spot kline request and retained
no raw kline bytes, prices, or returns. This is the required fail-closed outcome, not missing data.

The content-addressed snapshot is
`label_snapshot_7d96d32adadbc259372d645a59727656ea3292b4fdd68c3904557db3d45d8836.json`.
Offline verification reconstructs the source session, complete window, contract hash, all three
timing rows, ineligibility fields, and the unchanged authority boundary.

## Supervisory disposition

- Verified fact: causal label scheduling and `NOT_AVAILABLE` enforcement work end to end.
- Verified fact: metric, scorecard, and promotion eligibility remain false.
- Unknown: every future return and every question of signal usefulness.
- Prohibited during warm-up: aggregation, interpretation, scoring, tuning, or rule change.
- Next lawful evaluation: at or after `2026-07-13T19:52:00Z` for the 1h label.

No credential, account session, venue connection, order, fill, position, paper/demo/live state,
sealed V2 holdout access, human gate, or execution authority was activated.
