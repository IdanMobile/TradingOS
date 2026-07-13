# Prospective BTC Liquidation V5 Two-Window Proof

## Conclusion

The D-094 post-freeze operational proof passed. One finite process from clean commit
`474fc0c604145b7e80de21a48cacda5c6eeb8656` finalized exactly two consecutive schema-5
checkpoints on one public read-only WebSocket connection and one continuity epoch. The final
heartbeat is `COMPLETED` with no failure reference and execution authority `NONE`.

This proves bounded checkpoint continuity only. It does not validate the liquidation-stress
signal, establish edge, complete warm-up, authorize a bot, or permit paper/demo/live execution.

## Immutable source and checkpoint evidence

- Exchange-info raw hash: `96b22dc83f1bddc57f4c5325879e792f2766bd0439d51511ad64985f884d07c0`.
- Process run ID: `78c3e40115c5003ff2a23c48`.
- Connection epoch: `1` for both checkpoints.
- Continuity epoch: `1` for both checkpoints.
- Connection opened: `2026-07-13T21:08:23.304990+00:00`.
- `[2026-07-13T21:10Z,21:15Z)`: session
  `bf68af8b6b728a0b1b890472e1797a62b8a43fbb7c4e2a5fb2c4f8e1636ab40c`, source
  `COMPLETE`, zero published snapshots, `FLAT/WARMUP_BLOCK`, independent `BLOCK`.
- `[2026-07-13T21:15Z,21:20Z)`: session
  `e9daa3ac1539ba58b1d6978574ad1ab4c436673b8c3c9ae72ca605e2a7adbb16`, source
  `COMPLETE`, zero published snapshots, `FLAT/WARMUP_BLOCK`, independent `BLOCK`.
- Both checkpoints have `planned_handoff=null`; no reconnect or rotation occurred.
- All nine retained source sessions reconstruct offline.

The completed `operations/status.json` hash is
`8b1321312be4a0bc2273a28dbdec5849e83790a66f1f038241e25c19cbc925cb`. Per D-093, this
mutable operational record is liveness evidence, not the immutable historical proof; the two
content-addressed sessions are the historical proof.

After the proof, the status-verifier fixture was amended to tolerate the ignored local
`operations/` directory already existing. This is a test-harness coexistence correction only; the
observer code and clean proof commit are unchanged.

## Separate causal labels retained without analysis

At `2026-07-13T21:20:41.486823+00:00`, the unchanged label evaluator wrote snapshot
`844852d7e2291a9aca0a605454a18d30cf1846d91d6fb6d0ff9040477304b93f`. It contains 18
scheduled rows for six complete windows. Four 1h rows are causally available and retain-only; 14
rows remain `NOT_AVAILABLE`.

The two newly available 1h rows are recorded individually, without aggregation or interpretation:

- window `2026-07-13T20:00Z`: entry open `62272.00000000`, exit open `62176.01000000`, gross
  arithmetic label `-0.0015414632579650565262076053`;
- window `2026-07-13T20:10Z`: entry open `62179.98000000`, exit open `62097.29000000`, gross
  arithmetic label `-0.0013298492537308632135294994`.

All six label snapshots and exact raw bytes reconstruct offline. Warm-up analysis remains
prohibited; metric, scorecard, and promotion eligibility remain false.

## Supervisory disposition

- Total complete prospective windows: 6.
- Longest consecutive chain: 2 of 8,640 required warm-up windows.
- Signal disposition: `FLAT`.
- Independent risk disposition: `BLOCK`.
- Credentials used: false.
- Venue/account connection: `NONE`.
- Paper orders: `DISABLED`.
- Live orders: `DISABLED`.
- Execution authority: `NONE`.
- Sealed V2 holdout access: prohibited and not performed.

Status: **Operational proof PASS; strategy validation and every promotion/execution gate remain
closed.**
