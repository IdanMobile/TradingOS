# Session handoff — Stage B implementation scope — 2026-07-23

## Outcome and review remediation

The bounded Option A implementation plan and exact one-time integrity exception
are now documented at:

`docs/supervisor/STAGE_B_IMPLEMENTATION_SCOPE_AND_INTEGRITY_EXCEPTION_2026-07-23.md`

This is planning evidence only. No Stage B source, runtime, activation receipt,
private alias material, service, order, or authority changed.

An independent review returned `NO-GO` on the earlier underspecified draft. The
same plan now resolves all ten findings with normative contracts:

1. Appendix A: exact runtime inventory, permissions, generation commit point,
   non-authoritative `HEAD`, quarantine/recovery, and activated latch fields.
2. Appendix B: deny-unknown envelopes and per-event payloads, 64 KiB frames,
   4,096 events/generation, 100×50 page bounds, and 513-frame support.
3. Appendix C: exact manifest, `HEAD`, reducer, global API, series, cohort, and
   aggregate schemas with no selective subgroup query.
4. Appendix D: exact activation receipt, its complete 15-file hash map,
   staleness/restart checks, and activation-private paths.
5. Appendix D: 32-byte operator-user-owned alias material, full
   domain-separated HMACs, contradiction checks, and flat-only rotation.
6. Appendix E: exact recovery approval, CLI, record, lane-owned unlatch
   sequence, state transitions, and record-only/reconciliation-only refusal.
7. Appendix C: global removal of legacy dashboard details in active and
   inactive states.
8. Appendix B/client-key contract: one create attempt only, then
   query/reconciliation/cancel and never create replay.
9. Appendix F: exact fee/quantity formulas and permanent
   third-currency-fee ineligibility without replacement.
10. Appendix G: activation, recovery, concurrency, ordinal, version, cohort,
    dashboard-action, alias, boundary, and fault tests.

These are design remediations, not an implementation approval. Independent
architecture/security review of the remediated contract ultimately returned
`GO` for seeking the two exact approvals. Independent review of the eventual
exact implementation is still required.

A second independent review then identified additional P0/P1/P2 crash,
activation-authority, projection, and venue-limit gaps. The same normative
appendices now also bind:

- lane-state-owned `pending_risk_reduction` with intent-derived deterministic
  exit/stop keys, pre-POST `POST_UNKNOWN`, exactly one create, query-only
  ambiguity, and original-correlation cancel safety;
- fixed canonical CONFIG, independent-review, flat-reconciliation, and rollback
  files plus receipt digests; these same-user records are procedural evidence,
  not cryptographic identity proof;
- immutable first-activation receipt consumption through `ACTIVATION_BOUND`,
  manifest-pinned hashes/commit/config/restart ID, crash reconstruction, and
  pinned same-epoch restart reconciliation;
- final-directory data writes and atomic `.manifest.json.tmp` rename as the
  sole commit point, with partial-dir demotion and exact idempotent/conflict
  behavior;
- separate private public-projection schema, 256 MiB/32 MiB/4 MiB generation
  bounds, 4,096 total cohorts, and no private aliases;
- exact four-field demo-lane action response and disk-only audit detail;
- canonical full quarantine inventory hashing;
- official Bybit 50-row realtime/history and 100-row execution maxima, with a
  deliberate stricter Stage B 50-row cap for all endpoints.

After the final two wording/contract corrections, focused independent review
returned `GO` for seeking the approvals without expanding the file inventory
or integrity exception.

`PROJECT_STATE.md` remains the live SSOT. Stage B remains `NOT_ACTIVATED`;
execution authority remains `NONE`; Phases 3 and 4 remain separately blocked.

## Exact implementation scope

New:

- `src/tios/evidence/demo_decision_evidence_v2.py`;
- `tests/test_demo_decision_evidence_v2.py`.

Modified after approval:

- `scripts/demo_roundtrip.py`;
- `scripts/demo_eth_lane.py`;
- `src/tios/services/dashboard_api/demo_lane.py`;
- their three corresponding test files;
- `src/tios/services/dashboard_ui/dashboard.html`;
- `tests/test_dashboard.py`;
- `PROJECT_STATE.md`;
- `DECISION_LOG.md`;
- `docs/architecture/AD.md`;
- `PACKAGE_CHANGELOG.md`;
- `PACKAGE_INTEGRITY_MANIFEST.md` within the exact one-time exception.

The existing `/api/v1/demo-lane` route is sufficient. Dashboard `server.py`,
status modules, full-demo readiness modules, Stage A v1 files, `Makefile`, every
other immutable path, holdout, sealed, and prospective outcomes stay unchanged.

## Design decisions bound

- v2 is default-disabled and separate from unchanged Stage A v1.
- The fixed sanitized sink runs only under the lane lock.
- A unique Bybit `orderLinkId` is persisted and `fsync`ed before risk-increasing
  POST; it is correlation, not an exactly-once guarantee.
- Create/cancel acknowledgements are asynchronous.
- Unknown attempts reconcile by client key across realtime, order history, and
  execution history.
- Execution rows deduplicate by `execId`.
- `PartiallyFilledCanceled` is terminal with economic effect.
- Exact execution/fee cashflows replace rounded wallet deltas as the owner of
  `lane_base`.
- Evidence-store failure latches `ENTRY_BLOCK`/exit-only but cannot block the
  first risk-reducing sell/exit, protective-stop create/replace/cleanup,
  cancel, kill-switch, or reconciliation attempt. An unresolved
  `POST_UNKNOWN` create remains query/operator-recovery-only and never
  authorizes an automatic duplicate.
- Dashboard output is aggregate-only: incomplete exact 30-episode cohorts are
  `aggregate=null`.
- The API/HTML globally remove legacy heartbeat timestamps, PID, cursor, wallet,
  positions, order rows, signals, per-trade PnL, and window PnL in inactive and
  active states. This is an intentional operator-diagnostic tradeoff.
- The raw client key retained privately for exact reconciliation is the only
  raw correlation exception; no raw venue order/execution ID is retained.
- Every invocation has one create attempt. Ambiguity permits query,
  reconciliation, or cancel by the original key, never create replay.
- Risk-reducing create durability is independent of the evidence store:
  deterministic keys derive from the already committed risk-increasing intent,
  and the existing lane state owns crash recovery.
- The activated receipt is consumed once through the first committed
  `ACTIVATION_BOUND` event; later same-epoch process restarts reuse its pinned
  hashes after startup reconciliation.
- The action API exposes only schema version, boolean result, action enum, and
  state enum; no operational detail or free text.

Official Bybit sources and the exact 513-frame/fault/redaction test matrix are
recorded in the implementation plan.

## Activated runtime and recovery boundary

The complete repository path below remains absent throughout implementation:

```text
artifacts/evidence/private_demo/stage_b_v2/
```

The future fixed inventory includes the activation receipt, canonical CONFIG,
review, flat-reconciliation and rollback files, 32-byte private alias key,
manifest-addressed generations, validated convenience `HEAD`, quarantine, and
create-only recovery records. Its exact tree is in Appendix A.
Absence means `NOT_ACTIVATED`. Later creation requires `0700` directories,
`0600` files, a verified-flat separate activation, controlled restart,
independent review, and rollback evidence.

Recovery is owned by the same new module:

```bash
uv run python -m tios.evidence.demo_decision_evidence_v2 recover \
  --approval <absolute-json> \
  --expected-head <64hex> \
  --expected-incident <64hex> \
  --expected-reconciliation <evt_alias> \
  --expected-quarantine <64hex>
```

It writes only one recovery record and never clears the latch. The lane under
its lock clears only after that valid record, fresh exact-key terminal/flat/
stop-clear reconciliation, and a durable `RECOVERY_COMMITTED` event.
Reconciliation alone or record alone never clears.

## Exact next operator action

The earlier generic “yes do it” is insufficient. Before source work, the
operator must paste both exact statements from the implementation plan:

1. “Approval 1 — Option A implementation only”; and
2. “Approval 2 — one-time integrity/decision-log exception.”

The second statement names the only permitted manifest changes:

- `PROJECT_STATE.md` ×1;
- `DECISION_LOG.md` ×1;
- `docs/architecture/AD.md` ×1;
- `src/tios/services/dashboard_ui/dashboard.html` ×2;
- `tests/test_dashboard.py` ×2;
- manifest package-version text to v8.146;
- `PACKAGE_CHANGELOG.md` v8.146 in the same change.

No row add/remove/reorder and no other immutable edit is authorized.

After both approvals, execute waves sequentially: offline v2 contract;
default-disabled lane integration; dashboard/readiness/redaction; independent
review and v8.146 reconciliation; sequential focused tests; final `make check`.
Stop before activation.
