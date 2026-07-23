# Demo decision evidence report — 2026-07-23

## Scope and supervisory conclusion

The real read-only demo Decision Evidence Bridge completed its first live capture
and separate offline Stage A import. The capture itself passed, the committed
generation replayed idempotently, and the capability passed its code, package,
and independent-review gates.

This result is intentionally limited. It establishes a private, sanitized
evidence path over the already-running fake-money demo lane. It does not
establish complete decision history, a closed trading episode, PnL, strategy
quality, edge, profitability, approval, promotion, or live-trading authority.

`PROJECT_STATE.md` remains the project single source of truth. It is
integrity-listed, while `PACKAGE_INTEGRITY_MANIFEST.md` is immutable to this
agent lane, so this report and the corresponding handoff are supplemental
newest evidence rather than a replacement for that authority.

## Capability and verification identity

| Field | Verified value |
| --- | --- |
| Capability commit | `6172247` |
| Focused adapter/bridge suite | `123 passed` |
| Package quality gate | `make check`: `1855 passed, 29 deselected` |
| Independent final reviews | Two reviews, both `PASS` |
| Execution authority | `NONE` |

The capability is read-only with respect to the active demo lane. Capture and
Stage A import remain two explicit operations. The adapter adds no venue,
credential, network, order, restart, or lane-lock capability.

## Verified live snapshot

| Field | Verified value |
| --- | --- |
| Capture timestamp | `2026-07-23T07:52:45Z` |
| Snapshot ID | `SNAP-c7d9608c3dd0912c4c5cd1a7b4c72af2a791bf779ff4de5cabbff55064f6b794` |
| Capture status | `PASS` |
| Evidence completeness | `PARTIAL_LEGACY_OPEN` |
| Snapshot consistency | `BEST_EFFORT_MULTI_FILE` |
| Position state | `OPEN_INCOMPLETE` |
| Aggregate order observations | 1 |
| Realized outcomes | 0 |
| PnL available | `false` |
| Strategy evaluation available | `false` |
| Wallet balance exported | `false` |
| Promotion eligible | `false` |
| Execution authority | `NONE` |

The fixed snapshot inventory is:

- `lane_state.json`
- `heartbeat.json`
- `orders.jsonl`
- `coverage.json`
- `manifest.json`

The snapshot hierarchy uses `0700` directories and `0600` files.
`manifest.json` is the final commit point.

The verified sanitized outputs contained none of the prohibited raw fields:

- wallet or post-order wallet fields;
- action text;
- disaster-event or disaster-price fields;
- execution-note fields;
- rule-level fields;
- raw venue `order_id`;
- raw `signal_ref`.

Opaque venue-order and hashed signal references are retained where applicable;
the raw identifiers are not.

## Verified Stage A generation

| Field | Verified value |
| --- | --- |
| Generation ID | `GEN-db13fa0a6facbe27b8ff8f06c7dfb56f` |
| Generation manifest SHA-256 | `10107fe01bfddb4e5b25ffb0991ddd508e3bbc8c85dad7db4eb70f3ef454fc94` |
| Export SHA-256 | `05c983a45077f3c44f6d18c14870e47cd05ba2d5cd1827c5b1d236d6c7ffc090` |
| Projection status | `OPEN_LEGACY_LIMITED` |
| Event count | 2 |
| Store row count | 2 |
| Store last sequence | 2 |
| Replay appended events | 0 |
| Replay export equality | Byte-identical |

The generation is a conservative open-episode projection. Two retained events
and a two-row store do not constitute a complete trading history or a realized
outcome.

## Fixture-scale proof versus real retained history

The offline scale fixture exercised 513 order observations through capture,
durable Stage A commit, store/ledger parity, export, and replay. It committed
514 events and the replay appended zero events with identical export bytes.

That is a capability and scale proof only. The current real snapshot contains
one aggregate order observation. The 513-order fixture must not be represented
as live history, production trading volume, or evidence of strategy
performance.

## Point-in-time service state

Earlier operational verification found:

- the orchestrator was not halted;
- the dashboard returned HTTP `200`;
- the demo lane remained fake-money, `UNVALIDATED`, non-promotable, and retained
  an active protective stop;
- no service restart was required.

These are point-in-time liveness and safety observations. They do not establish
future uptime, order quality, strategy validity, or profitability.

## Governance boundary and remaining gate

Stage B—the proposed in-lane fail-closed evidence tap—remains
`NOT AUTHORIZED`. It is gated on:

1. an explicit operator security-policy decision;
2. a controlled demo-lane restart window, preferably while flat;
3. review of the exact fail-closed tap and rollback boundary before activation.

Until those conditions are met, the authorized workflow remains:

1. explicit manual read-only capture;
2. operator inspection of the capture result;
3. a separate offline Stage A import using the already-bound opaque source
   label for that Stage A history.

Do not silently combine those steps, restart the lane, or introduce an
in-process tap.

## Exact next safe commands

Run from the repository root:

```bash
cd ~/Downloads/trading_os_project_package
git status --short
CAPTURED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
uv run python scripts/capture_demo_decision_snapshot.py \
  --captured-at "$CAPTURED_AT"
```

The capture command is fixed-path and read-only against the active lane. Record
the returned snapshot ID. Keep capture and import separate. If the operator
then elects to append that snapshot to the existing Stage A history, use the
same terminal so `CAPTURED_AT` is preserved and retain the history's verified
source label:

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

An incorrect source label or inconsistent snapshot fails closed. Do not create
a replacement label to bypass a retained-history conflict.

## Next recommended agent work

1. Prepare a read-only Stage B security-policy decision packet for the operator:
   exact tap boundary, fail-closed behavior, restart/rollback plan, flat-position
   preference, and prohibited capabilities. Do not implement or activate Stage B
   without the operator decision.
2. Continue operator-selected manual captures and separate Stage A imports to
   accumulate evidence conservatively.
3. Add read-only reporting over Stage A only after a separate scoped approval,
   preserving `PARTIAL_LEGACY_OPEN` until retained evidence actually supports a
   stronger completeness state.
4. Reconcile `PROJECT_STATE.md` only through an operator-authorized integrity
   update that also satisfies the package-manifest rule.

## Non-claims and preserved worktree state

No PnL, mark-to-market result, profit, loss, expected return, edge, strategy
approval, promotion, or live-authority claim is supported by this evidence.

Unrelated runtime and data worktree changes were preserved and were not
reverted, staged, committed, or attributed to this capability.
