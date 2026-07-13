# Prospective BTC Liquidation — Second 1h Label and Additional V4 Window

Date: 2026-07-13  
Run commit: `fad9997`  
Execution authority: `NONE`

## Additional V4 source window

Observer V4 continuously covered `2026-07-13T20:08:02.267330Z` through
`20:15:00.006781Z`, fully enclosing `[20:10Z,20:15Z)`. The schema-4 session is `COMPLETE`, has
`source_failure=null`, and retained zero published snapshots.

- Session SHA-256: `a99a97c1e489c1f1af157b84d0ac61255ed11b96bc6b7718940712fd712d164d`
- Signal: `SIG-637b5e49ff85d286959af1be`, `FLAT/WARMUP_BLOCK`
- Independent risk decision: `BLOCK`
- Metric, scorecard, and promotion eligibility: false

Four complete windows now exist, but all are isolated; the longest consecutive chain remains one.

## Second causal 1h label

At `2026-07-13T20:15:16.395648Z`, the unchanged evaluator retained the second window's 1h label:

- Signal window: `[19:05Z,19:10Z)`
- Entry open at `19:11Z`: `62046.51000000`
- Exit open at `20:11Z`: `62215.86000000`
- Gross arithmetic return: `0.002729404119587064606857017`
- Status: `AVAILABLE_RETAIN_ONLY`

The 12-row snapshot contains two available 1h labels and ten `NOT_AVAILABLE` rows. Exact new raw
response hashes are `f662510c…` and `0f544328…`; snapshot SHA-256 is `0ee31a1b…`.

These two gross labels are not aggregated, compared, interpreted, cost-adjusted, scored, or used
to modify the signal. They do not establish edge or strategy validity.

No credential, account session, venue connection, order, fill, position, paper/demo/live state,
sealed V2 holdout access, human gate, or execution authority was activated.
