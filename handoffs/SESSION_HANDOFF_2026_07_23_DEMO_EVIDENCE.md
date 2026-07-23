# Session handoff — demo decision evidence — 2026-07-23

## Current state

The real read-only demo Decision Evidence Bridge is implemented, verified, and
has completed one live sanitized capture plus one separate offline Stage A
import.

- Capability commit: `6172247`.
- Focused suite: `123 passed`.
- `make check`: `1855 passed, 29 deselected`.
- Two independent final reviews: `PASS`.
- Execution authority: `NONE`.

The detailed supplemental report is:

`docs/supervisor/DEMO_DECISION_EVIDENCE_REPORT_2026-07-23.md`

## Live capture evidence

- Captured at: `2026-07-23T07:52:45Z`.
- Snapshot ID:
  `SNAP-c7d9608c3dd0912c4c5cd1a7b4c72af2a791bf779ff4de5cabbff55064f6b794`.
- Capture: `PASS`.
- Completeness: `PARTIAL_LEGACY_OPEN`.
- Consistency: `BEST_EFFORT_MULTI_FILE`.
- Position: `OPEN_INCOMPLETE`.
- Aggregate order observations: 1.
- Realized outcomes: 0.
- PnL available: `false`.
- Strategy evaluation available: `false`.
- Wallet export: `false`.
- Promotion eligible: `false`.
- Execution authority: `NONE`.

Private directories are `0700`; files are `0600`. The fixed committed snapshot
inventory is:

- `lane_state.json`
- `heartbeat.json`
- `orders.jsonl`
- `coverage.json`
- `manifest.json`

Verified sanitized outputs exclude raw wallet, action, disaster,
execution-note, rule-level, venue-order-ID, and signal-reference fields.

## Stage A committed evidence

- Generation ID: `GEN-db13fa0a6facbe27b8ff8f06c7dfb56f`.
- Manifest SHA-256:
  `10107fe01bfddb4e5b25ffb0991ddd508e3bbc8c85dad7db4eb70f3ef454fc94`.
- Export SHA-256:
  `05c983a45077f3c44f6d18c14870e47cd05ba2d5cd1827c5b1d236d6c7ffc090`.
- Projection: `OPEN_LEGACY_LIMITED`.
- Events: 2.
- Store row count / last sequence: `2 / 2`.
- Replay appended events: 0.
- Replay export: byte-identical.

The offline 513-order fixture also completed durable Stage A commit and replay:
514 events were committed and replay appended zero. This proves bounded
fixture-scale capability; it is not the current real history, which contains
one aggregate order observation.

## Runtime note

Earlier point-in-time checks confirmed:

- orchestrator not halted;
- dashboard HTTP `200`;
- demo lane fake-money, `UNVALIDATED`, non-promotable, with an active protective
  stop;
- no restart performed.

Service health does not establish profitability, strategy quality, promotion,
or future uptime.

## Authority and remaining gate

Stage B, the in-lane fail-closed evidence tap, remains `NOT AUTHORIZED`. It
requires an explicit operator security-policy decision and a controlled restart,
preferably while flat.

The current authorized workflow remains manual read-only capture followed by a
separate offline Stage A import. Do not combine the steps automatically, add an
in-process tap, restart the lane, or change order behavior.

`PROJECT_STATE.md` remains authoritative but was not edited because it is
integrity-listed and `PACKAGE_INTEGRITY_MANIFEST.md` is immutable to this agent
lane. This handoff and the supervisor report are supplemental newest evidence
until an operator-authorized state reconciliation.

## Exact next safe commands

From the repository root:

```bash
cd ~/Downloads/trading_os_project_package
git status --short
CAPTURED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
uv run python scripts/capture_demo_decision_snapshot.py \
  --captured-at "$CAPTURED_AT"
```

After inspecting the returned snapshot ID, keep the import explicit and use the
existing Stage A history's verified source label:

```bash
read -r "SNAPSHOT_ID?Snapshot ID: "
SOURCE_LABEL="active-demo-snapshot-20260723"
uv run python scripts/build_demo_decision_evidence.py \
  --lane-state "artifacts/evidence/private_demo/snapshots/${SNAPSHOT_ID}/lane_state.json" \
  --heartbeat "artifacts/evidence/private_demo/snapshots/${SNAPSHOT_ID}/heartbeat.json" \
  --orders "artifacts/evidence/private_demo/snapshots/${SNAPSHOT_ID}/orders.jsonl" \
  --source-label "$SOURCE_LABEL" \
  --captured-at "$CAPTURED_AT"
```

Do not invent a new source label to bypass a fail-closed history conflict.

## Next recommended agent work

1. Produce a review-only Stage B security-policy decision packet: tap boundary,
   fail-closed semantics, restart and rollback plan, flat-position preference,
   and prohibited capabilities.
2. Do not implement Stage B until the operator explicitly authorizes that policy
   and restart.
3. Continue operator-selected manual capture and separate Stage A import.
4. Reconcile `PROJECT_STATE.md` only through an operator-authorized integrity
   update satisfying the package-manifest rule.

## Boundaries and worktree preservation

There is no supported PnL, profit, loss, expected-return, edge, approval,
promotion, or live-trading claim.

Unrelated runtime and data dirt was preserved. It was not reverted, staged,
committed, or attributed to this work.
