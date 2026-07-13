# Prospective BTC Liquidation Signal — First Available 1h Label

Date: 2026-07-13  
Evaluator run commit: `e8805cc`  
Execution authority: `NONE`

## Causal observation

The unchanged evaluator ran at `2026-07-13T19:55:45.620441Z`, after the first window's frozen
1h availability boundary of `19:52Z`.

- Signal window: `[2026-07-13T18:45Z,18:50Z)`
- Entry candle: BTCUSDT Spot 1m open at `18:51Z`
- Entry open: `62012.00000000`
- Exit candle: BTCUSDT Spot 1m open at `19:51Z`
- Exit open: `62196.00000000`
- Gross arithmetic return: `0.002967167644971940914661678`
- Status: `AVAILABLE_RETAIN_ONLY`

Exact Binance Spot response bytes are content-addressed as:

- entry SHA-256 `48c1eb72292b32174fd2eb1f1da3b89f97e406d2a3985ffe84e31a9aa80d907d`;
- exit SHA-256 `61e24812bf8ab198488fd1c61cfe21d7037e2a0dd9cb13317103b32b05ca58f8`.

The 6h and 24h labels for the first window and every label for the second window remained
`NOT_AVAILABLE`; no request was made for them. Snapshot SHA-256:
`3a71318025765aadeb4f95109f5cfbb98a4138acc0226c709621fd493ce577de`.

## Supervisory disposition

This is one prospective gross label for a warm-up `FLAT/BLOCK` risk signal. It is not a trade,
strategy return, cost-adjusted result, sample, edge estimate, score, validation gate, or promotion
input. The frozen contract explicitly prohibits aggregation or interpretation during warm-up.

All three label snapshots, five source sessions, exact raw bytes, label timing, return arithmetic,
eligibility fields, and authority reconstruct offline.

No credential, account session, venue connection, order, fill, position, paper/demo/live state,
sealed V2 holdout access, human gate, or execution authority was activated.
