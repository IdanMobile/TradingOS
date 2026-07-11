# Reproduction Status — STRAT-EXT-3COMMAS-DCA-CONFIG

Status: **LOCAL_REPLAY_RETAINED / UNVALIDATED / NOT_ELIGIBLE**.

The canonical strategy spec parses and is expected to validate with ambiguities. It
has now been replayed by the OS-local DCA add-on runner against the frozen
BTCUSDT/ETHUSDT x 5m/15m/1h candles. It has not been platform-reproduced,
cross-engine checked, G10-tested, or risk approved.

Retained evidence:

- runner: `scripts/run_external_dca_replay.py`;
- replay: `artifacts/external_replay/3commas_dca/EXTDCA-9ed0a866cc1ddb5f7f4e7a94b5c5e48b/replay_run.json`;
- scorecard: `artifacts/external_replay/3commas_dca/EXTDCA-9ed0a866cc1ddb5f7f4e7a94b5c5e48b/scorecard.json`;
- scope: 6 frozen-data trials and 43,738 local simulated entry/add/exit events.

Boundaries:

- `execution_authority=NONE`;
- no platform bot execution;
- no exchange, paper/demo, live, or real-money path;
- no inherited profit/performance claim;
- no promotion or HG-3 readiness.

Next local-only step:

Treat this as retained research evidence only. If a future DCA variant survives
first-pass replay, build normal temporal/G10/cross-engine validation before any
promotion discussion. Until then this candidate remains `UNVALIDATED` and
`NOT_ELIGIBLE`.
