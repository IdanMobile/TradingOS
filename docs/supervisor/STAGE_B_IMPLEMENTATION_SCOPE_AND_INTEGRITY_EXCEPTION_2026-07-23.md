# Stage B implementation scope and integrity exception — 2026-07-23

## Status and purpose

This is the bounded implementation plan for Option A in
`STAGE_B_DEMO_EVIDENCE_SECURITY_DECISION_PACKET_2026-07-23.md`.

The proposed capability is:

- default-disabled;
- fixed to the existing fake-money Bybit demo lane;
- schema-separated as `tios.demo_decision_evidence.v2`;
- unable to approve, size, route, or originate an order;
- unable to read or expose credentials, wallets, raw venue IDs, or raw signals;
- diagnostic only, with execution authority `NONE`.

Implementation does not activate the capability. It does not restart a service,
create an activation receipt, create private alias material, submit an order,
validate or promote a strategy, auto-tune anything, connect a production venue,
or authorize live/real-money activity.

`PROJECT_STATE.md` remains the live SSOT. This plan and its handoff are
supplemental review artifacts and alter no project authority.

## Approval state

The operator's generic “yes do it” does **not** satisfy the security packet's
two exact approvals. Before source edits, the operator must provide both exact
statements at the end of this document:

1. Option A implementation approval; and
2. the separate one-time `STAGE-B-DEMO-EVIDENCE-ONLY`
   integrity/decision-log exception.

D-115 and D-116 are exhausted. They grant no authority for this work.
The first independent review returned `NO-GO` because the draft omitted exact
runtime/schema/recovery contracts. Appendices A–G remediate those findings.
After two further focused remediation passes, independent architecture/security
review returned `GO` for seeking both exact approvals. Implementation and
activation remain separately gated; activation remains `NO-GO`.

## Fixed activation boundary

The implementation recognizes the fixed runtime inventory defined in Appendix
A. Its two activation-private inputs are:

```text
artifacts/evidence/private_demo/stage_b_v2/activation/ACTIVATION_RECEIPT.json
artifacts/evidence/private_demo/stage_b_v2/private/install_alias.key
```

The complete repository runtime root
`artifacts/evidence/private_demo/stage_b_v2/` must be absent during
implementation and tests. Tests use temporary directories only. Absence means
`NOT_ACTIVATED`; it must never silently fall back to enabled behavior. The
existing lane state gains the Appendix A latch fields only after activation.

A later activation ceremony must create all ancestors as `0700`, both files as
`0600`, reject symlinks/hard links/ownership or mode drift, and bind the receipt
to the independently reviewed code/configuration hashes. The alias material is
operator-user-owned private installation material. Neither its bytes nor a
derived secret may enter Git, logs, the dashboard, reports, or prompts.

Activation is separately gated on a verified-flat lane with no unresolved
submission/order, a controlled restart, raw-lane mode hardening, rollback
identity, and independent security review.

## Exact phased file inventory

No file outside this inventory may change. Any newly discovered dependency is a
stop condition requiring a revised scope and operator review.

### Wave 1 — offline v2 contract

New:

- `src/tios/evidence/demo_decision_evidence_v2.py`
  - typed v2 events and state machine;
  - fixed non-pluggable sanitized sink;
  - content-addressed, append-only, manifest-last generations;
  - exact decimal execution/fee/cashflow accounting;
  - entry-block/degraded latch and terminal reconciliation;
  - fixed 30-episode aggregate projection;
  - fixed activation-path reader, default-disabled.
  - the `python -m tios.evidence.demo_decision_evidence_v2 recover` CLI from
    Appendix E; no separate CLI source file.
- `tests/test_demo_decision_evidence_v2.py`
  - all v2 contract, storage, sanitization, cohort, scale, and fault fixtures.

No persistent fixture file is added. Official-shaped frames are constructed by
bounded test factories in the new test file so raw-looking identifiers cannot
escape test temporaries.

### Wave 2 — default-disabled venue-demo integration

Modified:

- `scripts/demo_roundtrip.py`
  - add validated `orderLinkId` support;
  - add realtime, history, and execution reconciliation by client key;
  - deduplicate execution rows by `execId`;
  - treat create/cancel acknowledgements as asynchronous;
  - preserve cancel and stop safety.
- `scripts/demo_eth_lane.py`
  - invoke the fixed sink only while holding `exclusive_lane_lock`;
  - reserve and durably persist the client key before risk-increasing POST;
  - use that key on the venue request;
  - reconcile unknown attempts by key before another entry;
  - derive `lane_base` from exact executions, not rounded wallet deltas;
  - latch `ENTRY_BLOCK`/exit-only on evidence failure;
  - never let evidence-store failure block the first risk-reducing sell/exit,
    protective-stop create/replace/cleanup, cancel, kill-switch, or
    reconciliation attempt; unresolved `POST_UNKNOWN` ambiguity still blocks
    an automatic duplicate create pending operator-reviewed reconciliation.
- `tests/test_demo_roundtrip.py`
  - official Bybit request/response, pagination, async, execution, and client-key
    adapter tests.
- `tests/test_demo_eth_lane.py`
  - lane-lock, persistence-before-POST, partial-fill economics, restart,
    entry-block, and risk-reducing bypass tests.

Exact integration hooks in the current source:

- `scripts/demo_eth_lane.py`: `LANE_DIR`/`LANE_STATE`/`LANE_LOCK`,
  `exclusive_lane_lock`, `_append_ledger`, `place`, `place_stop_order`,
  `cancel_stop_order`, `stop_order_status`, and `run_cycle`;
- `scripts/demo_roundtrip.py`: `_order_create`, `place_stop`, `cancel_order`,
  `order_status`, and `_poll_filled`.

### Wave 3 — aggregate readiness and redacted dashboard projection

Modified:

- `src/tios/services/dashboard_api/demo_lane.py`
  - globally replace the legacy projection with the Appendix C allowlist;
  - read the fixed v2 public projection through bounded, fail-closed parsing;
  - expose operational status plus Stage B readiness and completed exact
    30-assignment aggregates only;
  - remove legacy heartbeat timestamps, PID, cursor, wallet, positions, order
    rows, signals, per-trade PnL, and window PnL whether Stage B is inactive or
    active.
- `tests/test_demo_lane_api.py`
  - absent/default-disabled, malformed, incomplete, complete, permission,
    redaction, and aggregate-only projection tests.
- `src/tios/services/dashboard_ui/dashboard.html`
  - add a useful read-only Stage B status and aggregate card;
  - remove every legacy field forbidden by the global API allowlist;
  - render `aggregate=null` until an exact cohort is complete;
  - retain fake-money, diagnostic-only, no-promotion, authority-`NONE` labels.
- `tests/test_dashboard.py`
  - pin the Stage B labels, null behavior, aggregate fields, redaction, route,
    and no-authority boundary.

The existing `/api/v1/demo-lane` route already calls `build_demo_lane`, so these
files remain unchanged and out of scope:

- `src/tios/services/dashboard_ui/server.py`;
- every dashboard `status.py` module;
- `src/tios/ops/demo_readiness.py`;
- `scripts/check_full_demo_readiness.py`;
- `tests/test_demo_readiness.py`.

Stage B readiness is a field in the existing demo-lane projection; it is not a
new HTTP route and does not weaken the full-demo `AUTHORITY_GATED` result.
The global legacy-field removal is an intentional operator-diagnostic tradeoff,
not merely a nested Stage B redaction.

### Wave 4 — governance and package reconciliation

Modified:

- `PROJECT_STATE.md` — add Stage B as implemented/default-disabled and
  activation-gated; retain Phase 2b/3/4 and authority boundaries.
- `DECISION_LOG.md` — one new decision recording exact scope, default-disabled
  state, evidence behavior, non-authority, and activation gate.
- `docs/architecture/AD.md` — record the v2 sink boundary, Stage A separation,
  order-correlation/reconciliation semantics, exit-only behavior, and dashboard
  projection.
- `PACKAGE_CHANGELOG.md` — add the v8.146 entry in the same change.
- `PACKAGE_INTEGRITY_MANIFEST.md` — update only its package-version text and
  the exact existing hash-row occurrences authorized below.

New:

- `docs/supervisor/STAGE_B_IMPLEMENTATION_SCOPE_AND_INTEGRITY_EXCEPTION_2026-07-23.md`;
- `handoffs/SESSION_HANDOFF_2026_07_23_STAGE_B_IMPLEMENTATION_SCOPE.md`.

### Explicitly unchanged

- `src/tios/evidence/demo_decision_bridge.py`;
- `src/tios/evidence/demo_snapshot_adapter.py`;
- `scripts/build_demo_decision_evidence.py`;
- `scripts/capture_demo_decision_snapshot.py`;
- `tests/test_demo_decision_bridge.py`;
- `tests/test_demo_snapshot_adapter.py`;
- all Stage A v1 evidence and histories;
- `Makefile`;
- `src/tios/ops/self_modification.py`;
- every other `IMMUTABLE_PATHS` entry;
- everything under `artifacts/holdout/` and `artifacts/sealed/`;
- all preregistered prospective outcomes.

## Exact integrity exception

`PACKAGE_INTEGRITY_MANIFEST.md` is immutable. Source implementation may not
start until the operator grants one exact, one-time exception named
`STAGE-B-DEMO-EVIDENCE-ONLY`.

The exception permits `PACKAGE_INTEGRITY_MANIFEST.md` to change only:

- the package-version line to v8.146; and
- the SHA-256 value in these existing rows, with exact occurrence counts:
  - `PROJECT_STATE.md` — 1 row;
  - `DECISION_LOG.md` — 1 row;
  - `docs/architecture/AD.md` — 1 row;
  - `src/tios/services/dashboard_ui/dashboard.html` — 2 duplicate rows;
  - `tests/test_dashboard.py` — 2 duplicate rows.

It also permits the corresponding listed files to receive only the Stage B
changes described above and requires `PACKAGE_CHANGELOG.md` v8.146 in the same
change.

The exception:

- permits no manifest row addition, removal, reordering, or unrelated edit;
- permits no other `IMMUTABLE_PATHS` edit;
- permits no threshold, research protocol, prospective, holdout, or sealed
  change;
- expires after the v8.146 reconciliation;
- grants no activation, restart, venue, order, promotion, auto-tuning, live,
  real-money, or continuing manifest authority.

Before completion, the strict manifest verifier must confirm all rows, including
both duplicate dashboard/test occurrences.

## Bybit V5 semantics bound to the design

Retrieved from official Bybit documentation on 2026-07-23:

1. `orderLinkId` is the venue-supported client correlation field. For Spot it
   is optional at the API level but must be unique; its maximum length is 36,
   and allowed characters are letters, digits, hyphens, and underscores.
   Stage B makes it mandatory and validates `^[A-Za-z0-9_-]{1,36}$`.
2. Bybit does not document `orderLinkId` as exactly-once delivery. Stage B
   therefore treats it as correlation, not a guarantee: persist before POST,
   reuse for the same logical attempt, never blindly resubmit, and reconcile.
3. A successful create acknowledgement means the request was accepted, not that
   the order is filled or terminal. Confirmation is asynchronous.
4. Reconciliation must query `/v5/order/realtime` by `orderLinkId`, fall back to
   `/v5/order/history` for durable closed history, and collect
   `/v5/execution/list` by the same key for economic facts.
5. One order may have multiple execution rows. Deduplicate identical rows by
   `execId`; a conflicting duplicate is a fail-closed incident. Equal
   `execTime` rows require deterministic ordering using the documented
   `execId+orderId+leavesQty` guidance before raw IDs are sanitized.
6. `PartiallyFilledCanceled` is a closed Spot status. It is terminal but has
   economic effect; its execution rows must update position/cashflow/fees and
   cannot be treated as an unfilled failure.
7. Cancel acknowledgements are also asynchronous. Query to confirm terminal
   state. If a create result is unknown, query by the already-persisted client
   key before any further action; the create request is never replayed.

Official sources:

- [Place Order](https://bybit-exchange.github.io/docs/v5/order/create-order)
- [Get Open & Closed Orders](https://bybit-exchange.github.io/docs/v5/order/open-order)
- [Get Order History](https://bybit-exchange.github.io/docs/v5/order/order-list)
- [Get Trade History](https://bybit-exchange.github.io/docs/v5/order/execution)
- [Cancel Order](https://bybit-exchange.github.io/docs/v5/order/cancel-order)
- [Enums Definitions](https://bybit-exchange.github.io/docs/v5/enum)

These sources establish venue semantics, not strategy quality or profitability.

## Current correctness gap to close

Current `scripts/demo_eth_lane.py::place` marks an order successful only when
the polled status is `Filled`; `run_cycle` changes `lane_base` only when that
flag is true. The current record also uses rounded wallet deltas. A Spot
`PartiallyFilledCanceled` order can therefore have real demo executions while
`lane_base` remains unchanged, diverging local risk state from venue state.

The scoped fix is:

- derive exact base and quote effects from complete deduplicated execution rows;
- retain exact `execQty`, `execPrice`, `execValue`, `execFee`, and
  `feeCurrency` decimals;
- bind terminal order, position, and protective-stop reconciliation;
- never infer exact economics from wallet or rounded balance deltas;
- block new entries on unresolved divergence while preserving exits/stops,
  cancel, kill-switch, and reconciliation.

## Client-key contract

The implementation generates one key per logical submission using a fixed
`tios2_` prefix plus a collision-checked random token, staying within 36
allowed characters. The key:

- contains no raw signal, strategy, symbol, wallet, or timestamp;
- is persisted and directory-`fsync`ed in the v2 intent generation before POST;
- is sent exactly as persisted in `orderLinkId`;
- is reused for query/reconciliation/cancel, never for another create call;
- is never displayed or exported;
- cannot be replaced because an acknowledgement was lost.

A persistence failure means no risk-increasing POST. Every create invocation
consumes the logical submission's one permitted create attempt. Timeout,
disconnect, malformed response, or ambiguity means query/reconcile only: there
is **never an automatic create replay**, even with the same key. A new create is
allowed only after terminal closure and a genuinely new logical submission with
a newly persisted key. An uncertain attempt means `ENTRY_BLOCK` until
realtime/history/execution reconciliation by the original key is terminal. The
client key does not make POST exactly-once.

Risk-reducing actions do not depend on an evidence-store write. Their create
intent, deterministic key, exact payload, and POST phase are owned by the
lane-state protocol in Appendix B and are anchored to the already committed
risk-increasing `SUBMISSION_INTENT_COMMITTED` event. Cancel never derives a
new key; it targets the original order correlation. The lane retains no raw
derived create key, and evidence observes these actions best-effort. An
evidence outage therefore cannot obstruct this path. A failure of the lane
owner's own state durability is a separate pre-existing execution-safety
failure and is not reclassified as an evidence failure.

## Query, cancel, and protective-stop safety

- Realtime miss is not “no order”; history and executions must also be checked.
- Pagination is exhausted within reviewed frame/page limits; cursor loops,
  truncation, or limit exhaustion are unresolved, not empty.
- Cancel/create acknowledgements never clear state without confirmed query.
- A partially filled cancellation updates economics before terminal closure.
- Protective-stop create/replace/cleanup uses its own client key where the venue
  supports it, but evidence-storage failure may not prevent risk reduction.
- Under `EVIDENCE_DEGRADED`, the lane is `ENTRY_BLOCK`/exit-only. Verified
  first risk-reducing sells, protective-stop create/replace/cleanup, cancels,
  kill-switch actions, and reconciliation remain callable. An unresolved
  attempted create remains query/recovery-only; “exit-only” never means
  permission to issue a duplicate create.
- Unknown or conflicting stop state keeps entry blocked. No blind duplicate
  stop creation or cancel retry is permitted.

## Exact test matrix

All venue frames are offline fixtures; no test may use network or credentials.

### V2 storage and event-chain tests

- absent activation receipt and alias material => `NOT_ACTIVATED`;
- schema/version mismatch, unknown event, unknown field, malformed decimal;
- empty, 1, 2, 29, 30, 31, and 513 ordered frames;
- 513 distinct execution frames survive commit/replay with byte-identical
  aggregate projection;
- duplicate identical event replay is idempotent; conflicting duplicate fails;
- out-of-order parent/sequence, missing parent, wrong chain head, truncation;
- crash/failure at data write, file `fsync`, rename, directory `fsync`,
  manifest write, manifest `fsync`, and commit-pointer update;
- disk-full/write error, permission drift, symlink, hard link, path escape,
  unexpected file, oversize file/frame/page;
- sanitizer attacks in every string field: raw venue ID, signal, wallet,
  credential-like text, URL, header, free text, control characters, Unicode
  confusable, and nested unknown object;
- exact `0700`/`0600` checks in temp roots;
- 29 episodes => `aggregate=null`; episode 30 releases only cohort 1; episode
  31 cannot alter cohort 1 and starts cohort 2;
- only closed/positive/negative/flat counts and exact aggregate entry, exit,
  gross, fees-by-currency, and net totals are disclosed.

### Bybit adapter frame tests

- `orderLinkId` lengths 1 and 36 accepted; 0/37 and characters outside
  `[A-Za-z0-9_-]` rejected;
- collision rejected; persisted key exactly equals posted key;
- persistence failure proves POST call count remains zero;
- create `retCode=0` is `ACKNOWLEDGED_PENDING`, never `FILLED`;
- realtime hit/miss/delay, history fallback, execution fallback;
- one execution, multiple partial executions, 513 execution frames, multiple
  pages, same-`execTime` ordering, empty final page;
- duplicate `execId` identical dedupe; conflicting duplicate fail closed;
- cursor loop, missing cursor, repeated page, oversized page, timeout,
  malformed row, missing fee currency, non-finite/negative decimal;
- `Filled`, `Cancelled`, `Rejected`, and `PartiallyFilledCanceled`;
- cancel acknowledgement followed by active, partial, and terminal queries;
- unknown create result reconciles by the original client key and never emits a
  second create POST.
- recovery CLI positive/negative fixtures, including approval/reconciliation
  alone and recovery-record alone;

### Lane and risk tests

- fixed sink is invoked only under the held lane lock;
- default-disabled code preserves no Stage B runtime files and no authority;
- risk-increasing intent generation is durable before POST;
- entry evidence failure latches `EVIDENCE_DEGRADED` + `ENTRY_BLOCK`;
- restart loads the reserved key and reconciles rather than reposting;
- unresolved attempts block fresh signals;
- exact `lane_base` for partial Buy/Sell executions with fees in base, quote,
  and a third fee currency;
- `PartiallyFilledCanceled` changes `lane_base` and remains terminal;
- wallet delta disagreement is diagnostic and cannot overwrite executions;
- evidence-store failure alone leaves the first kill-switch action,
  risk-reducing sell, local exit, protective-stop create/replace/cleanup,
  cancel, and reconciliation attempt available; unresolved attempted creates
  remain query/recovery-only;
- stop ambiguity and client-key query failure keep entries blocked;
- concurrent closes serialize under the lane lock; restart preserves ordinals;
- interleaved immutable series and version changes never pool cohorts;
- an assigned-then-ineligible episode is never replaced or refilled;
- outage/correction episodes are excluded without changing their ordinal;
- dashboard `START`/`RUN_ONCE` cannot clear a latch;
- no live host, production URL, free-form action, or new order surface.

### Dashboard/readiness/redaction tests

- existing `/api/v1/demo-lane` route remains the only route;
- absent receipt => `NOT_ACTIVATED`, authority `NONE`;
- malformed/unsafe/private projection => unavailable and fail closed;
- incomplete cohort renders no PnL values;
- complete cohort renders only approved totals/counts;
- raw order/client/execution IDs, timestamps, episode rows, signal refs,
  wallets, free text, best/worst, streak, curve, and private path never appear in
  API or HTML;
- fake-money, diagnostic-only, no-promotion, no-auto-tune, and authority-`NONE`
  labels remain visible;
- server/status/readiness modules remain unchanged.
- no request parameter can select a series, cohort, time window, subgroup, or
  outcome; every immutable series is returned in order.

### Stage A and repository regressions

- existing Stage A v1 bridge tests stay byte-compatible;
- existing 513-order snapshot/Stage A/replay fixture stays green;
- existing demo lane, stop, roundtrip, projection, dashboard, architecture,
  secret, and immutable-path gates stay green;
- no prospective, holdout, or sealed outcome is opened.

Run pytest suites sequentially; never run two concurrently:

```bash
uv run pytest -q tests/test_demo_decision_evidence_v2.py
uv run pytest -q tests/test_demo_roundtrip.py tests/test_demo_eth_lane.py
uv run pytest -q tests/test_demo_lane_api.py tests/test_dashboard.py
uv run pytest -q tests/test_demo_snapshot_adapter.py tests/test_demo_decision_bridge.py
make check
```

The final quality gate is `make check`.

## Rollout and stop gates

### Rollout 1 — offline contract

Implement Wave 1 only. Stop if the v2 chain, sanitizer, 513-frame scale,
manifest-last crash behavior, or 30-episode disclosure contract fails.

### Rollout 2 — default-disabled integration

Implement Wave 2 with activation paths absent. No restart. Stop if persistence
does not precede POST, client-key reconciliation can duplicate a request,
`lane_base` can diverge on partial fills, or evidence-store failure can
obstruct the first risk-reducing attempt. An unresolved attempted create is
expected to remain query/recovery-only.

### Rollout 3 — dashboard/readiness/redaction

Implement Wave 3 over the unchanged route. Stop on any individual-derived,
identifier, signal, wallet, timestamp, free-text, or private-path disclosure.

### Rollout 4 — independent review and package gate

Complete independent architecture/security review, the v8.146 governance and
manifest reconciliation, sequential focused tests, and full `make check`.
Review binds exact commit, diff, file inventory, hashes, schema, and test output.
Implementation ends here with `NOT_ACTIVATED` and authority `NONE`.

### Rollout 5 — separate future activation

Not authorized by this plan. It requires the packet's separate exact activation
statement, a verified-flat lane with no unresolved order/submission, a
controlled Makefile-target restart, `0700`/`0600` mode hardening, receipt and
alias-material creation, smoke checks, rollback identity, and independent
review. Any failed check rolls back entry enablement while preserving
risk-reducing actions and evidence.

## Exact approvals required before implementation

### Approval 1 — Option A implementation only

> I approve Option A, full evidence-first Stage B, for implementation and
> testing in the fake-money demo lane only under the 2026-07-23 Stage B
> demo-evidence security decision packet. I do not authorize activation,
> restart, live trading, real money, strategy approval, promotion, auto-tuning,
> or any authority beyond NONE. Before edits, provide the exact proposed
> STAGE-B-DEMO-EVIDENCE-ONLY integrity and decision-log exception scope for my
> separate approval.

### Approval 2 — one-time integrity/decision-log exception

> I approve the one-time STAGE-B-DEMO-EVIDENCE-ONLY integrity and decision-log
> exception for v8.146. It permits PACKAGE_INTEGRITY_MANIFEST.md to change only
> its package-version line and the existing hash rows for PROJECT_STATE.md
> (one), DECISION_LOG.md (one), docs/architecture/AD.md (one),
> src/tios/services/dashboard_ui/dashboard.html (two duplicate rows), and
> tests/test_dashboard.py (two duplicate rows), with a PACKAGE_CHANGELOG.md
> v8.146 entry in the same change. No manifest row may be added, removed,
> reordered, or otherwise changed. No other IMMUTABLE_PATHS, research protocol,
> prospective, holdout, or sealed path is authorized. This exception expires
> after the v8.146 reconciliation and does not authorize activation, restart,
> live trading, real money, strategy approval, promotion, auto-tuning, or any
> authority beyond NONE.

Only both exact approvals authorize source implementation. Neither authorizes
Rollout 5 activation.

## Normative appendices

These appendices are the implementation contract. If an earlier descriptive
sentence conflicts with an appendix, the appendix fails closed and controls.

### Appendix A — persistent runtime inventory and permissions

When and only when a later activation is approved, the complete allowed
inventory below is:

```text
artifacts/evidence/private_demo/stage_b_v2/                         0700
├── activation/                                                    0700
│   ├── ACTIVATION_RECEIPT.json                                    0600
│   ├── CONFIG.json                                                0600
│   ├── INDEPENDENT_REVIEW.json                                    0600
│   ├── FLAT_RECONCILIATION.json                                   0600
│   └── ROLLBACK_CONFIG.json                                       0600
├── private/                                                       0700
│   └── install_alias.key                                          0600
├── store/                                                         0700
│   ├── generations/                                               0700
│   │   └── G-<sha256>/                                            0700
│   │       ├── events.jsonl                                       0600
│   │       ├── reducer_state.json                                 0600
│   │       ├── public_projection.json                             0600
│   │       └── manifest.json                                      0600
│   └── HEAD.json                                                  0600
├── quarantine/                                                    0700
│   └── U-<uuid>/                                                  0700
└── recovery/                                                      0700
    └── RECOVERY-<sha256>.json                                     0600
```

`<sha256>` is 64 lowercase hexadecimal characters. `<uuid>` is canonical
lowercase UUID text. Every ancestor created by Stage B is `0700`; every file is
single-link, user-owned, regular, non-symlink `0600`. Unknown entries, hard
links, symlinks, owner/mode drift, device changes during a read, or path escape
fail activation or latch `ENTRY_BLOCK`.

`manifest.json` is created by the exact Appendix C rename protocol and is the
only generation commit point. `HEAD.json` is written afterward as a validated
convenience pointer. Missing, stale, corrupt, or mismatching `HEAD.json` never
invalidates a committed generation and is never a commit point; readers recover
the unique valid chain by manifests.

`quarantine/U-<uuid>/` contains only the interrupted generation's
`events.jsonl`, `reducer_state.json`, `public_projection.json`, and
`.manifest.json.tmp` entries that happen to exist after atomic demotion, or one
orphan `HEAD.json.tmp` atomically demoted from `store/` after a crash. A valid
`manifest.json` is never demoted. Quarantine is never executed, auto-promoted,
deleted, or treated as committed. `recovery/` contains only the recovery
records defined in Appendix E.

The only activated Stage B fields in the existing
`artifacts/trading_domain/demo_lane/lane_state.json` are:

```json
{
  "stage_b_v2": {
    "schema": "tios.demo_decision_evidence.lane_latch.v1",
    "activation_epoch": "act_<64hex>",
    "activation_receipt_sha256": "<64hex>",
    "controlled_restart_id": "restart_<allowed>",
    "repo_commit": "<40-lowercase-hex>",
    "config_sha256": "<64hex>",
    "evidence_state": "READY|ENTRY_BLOCK|RECOVERY_AUTHORIZED|RECONCILED_PENDING_COMMIT",
    "head_sha256": "<64hex>",
    "incident_sha256": "<64hex-or-null>",
    "unresolved_order_alias": "ord_<64hex>-or-null",
    "recovery_sha256": "<64hex-or-null>",
    "open_episode_event_id": "evt_<64hex>-or-null",
    "risk_reduction_sequence": 0,
    "pending_risk_reduction": null
  }
}
```

Unknown Stage B latch fields fail closed. The raw client key is not copied to
lane state. `risk_reduction_sequence` is 0..2^63-1. During implementation and
tests, the repository runtime root and these latch fields remain absent.

When non-null, `pending_risk_reduction` contains exactly:

```json
{
  "schema": "tios.demo_decision_evidence.pending_risk_reduction.v1",
  "action_id": "rr_<64hex>",
  "subject_intent_event_id": "evt_<64hex>",
  "action_kind": "EXIT_CREATE|STOP_CREATE|STOP_REPLACE_CREATE|CANCEL_TARGET",
  "sequence": 1,
  "payload": {
    "side": "SELL",
    "order_type": "MARKET|STOP_MARKET",
    "qty": "<exact-decimal>",
    "quantity_unit": "BASE",
    "trigger_price": "<exact-decimal-or-null>",
    "order_filter": "Order|StopOrder",
    "target_order_alias": "ord_<64hex>-or-null"
  },
  "payload_sha256": "<64hex>",
  "client_key_sha256": "<64hex-or-null>",
  "phase": "RESERVED|POST_UNKNOWN|ACK_PENDING|TERMINAL",
  "terminal_status": "FILLED|CANCELLED|REJECTED|PARTIALLY_FILLED_CANCELED-or-null"
}
```

`sequence` is 1..2^63-1 and monotonically increases per subject intent.
`action_id` is `rr_` plus SHA-256 of the canonical object with `action_id`,
`phase`, and `terminal_status` omitted. `EXIT_CREATE` and `STOP_CREATE` require
null `target_order_alias`; `STOP_REPLACE_CREATE` and `CANCEL_TARGET` require
the exact tracked target alias. `CANCEL_TARGET` uses `order_type=MARKET`,
`qty=0`, `quantity_unit=BASE`, and null trigger solely as a typed non-create
placeholder. Unknown fields or inconsistent combinations fail closed.

### Appendix B — canonical event contract

All JSON is UTF-8, duplicate-key rejecting, lexicographically key-sorted
canonical JSON with no insignificant whitespace and one LF per JSONL frame.
Unknown fields and unknown enum values are rejected. One frame is at most
64 KiB including LF; one generation contains at most 4,096 events.

Official Bybit maxima are 50 rows/page for realtime and order history and 100
rows/page for execution history. Stage B deliberately applies the stricter
internal cap of 50 rows/page to **all** three endpoints and at most 100 pages
per endpoint: 5,000 frames maximum. It must support 513 execution frames. A
repeated cursor, incomplete page sequence, page 101, row 5,001, or remaining
cursor at the bound is unresolved, never an empty result. This is an internal
safety cap, not a claim that Bybit's execution maximum is 50.

Primitive types:

- `sha256`: `^[a-f0-9]{64}$`;
- `evt_alias`: `^evt_[a-f0-9]{64}$`;
- risk-reduction action alias: `^rr_[a-f0-9]{64}$`;
- private aliases:
  `^(ord|exe|fee|strategy|cost|risk)_[a-f0-9]{64}$`;
- activation epoch: `^act_[a-f0-9]{64}$`;
- client key: `^[A-Za-z0-9_-]{1,36}$`;
- exact decimal:
  `^-?(0|[1-9][0-9]{0,47})(\.[0-9]{1,18})?$`, no exponent,
  negative zero, NaN, infinity, whitespace, or numeric JSON token;
- UTC: `YYYY-MM-DDTHH:MM:SS.ffffffZ`, real calendar time only;
- integers: JSON integers, no booleans, within the field bounds below.

Every event has exactly:

```json
{
  "schema": "tios.demo_decision_evidence.v2",
  "event_id": "evt_<64hex>",
  "sequence": 1,
  "previous_event_sha256": null,
  "activation_epoch": "act_<64hex>",
  "event_type": "ENUM_BELOW",
  "recorded_at": "UTC",
  "payload": {}
}
```

`sequence` is 1..2^63-1 and contiguous. `previous_event_sha256` is null only at
sequence 1, otherwise the SHA-256 of the prior complete canonical frame.
`event_id` is `evt_` plus SHA-256 of the canonical event with `event_id`
omitted. Payloads contain exactly the following fields:

| Event type | Exact payload |
| --- | --- |
| `ACTIVATION_BOUND` | `activation_receipt_sha256`, `config_sha256`, `independent_review_sha256`, `flat_reconciliation_sha256`, `rollback_config_sha256`, `controlled_restart_id`, `repo_commit` |
| `DECISION_OBSERVED` | `strategy_alias`, `cost_alias`, `risk_alias`, `symbol`, `timeframe`, `decision`, `side`, `requested_qty`, `quantity_unit` |
| `RISK_VERDICT_OBSERVED` | `decision_event_id`, `verdict`, `reason_code`, `approved_qty`, `quantity_unit`, `quote_cap` |
| `IDEMPOTENCY_KEY_RESERVED` | `decision_event_id`, `risk_event_id`, `order_alias`, `client_key`, `client_key_sha256` |
| `SUBMISSION_INTENT_COMMITTED` | `key_event_id`, `order_alias`, `order_kind`, `side`, `order_type`, `qty`, `quantity_unit`, `trigger_price`, `risk_increasing` |
| `SUBMISSION_ATTEMPTED` | `intent_event_id`, `order_alias`, `client_key_sha256`, `endpoint`, `attempt_ordinal` |
| `VENUE_ACKNOWLEDGED` | `attempt_event_id`, `order_alias`, `venue_code`, `result_code` |
| `VENUE_REJECTED` | `attempt_event_id`, `order_alias`, `venue_code`, `result_code` |
| `SUBMISSION_RESULT_UNKNOWN` | `attempt_event_id`, `order_alias`, `venue_code`, `result_code` |
| `ORDER_UPDATE_OBSERVED` | `order_alias`, `order_status`, `cum_exec_qty`, `cum_exec_value`, `leaves_qty`, `avg_price`, `source` |
| `FILL_OBSERVED` | `order_alias`, `execution_alias`, `fee_alias`, `side`, `exec_qty`, `exec_price`, `exec_value`, `fee_amount`, `fee_currency`, `source` |
| `CANCEL_OBSERVED` | `order_alias`, `client_key_sha256`, `cancel_state`, `venue_code`, `source` |
| `EXIT_UPDATE_OBSERVED` | `episode_open_event_id`, `order_alias`, `exit_state`, `executed_base_qty`, `received_quote_value` |
| `TERMINAL_RECONCILIATION_COMMITTED` | `order_alias`, `terminal_status`, `buy_exec_qty`, `sell_exec_qty`, `entry_exec_value`, `exit_exec_value`, `quote_fee`, `base_fee`, `third_fee_present`, `position_base_qty`, `protective_stop_state`, `flat`, `source`, `all_pages_complete` |
| `CLOSED_EPISODE_COMMITTED` | `series_sha256`, `episode_ordinal`, `entry_base_qty`, `exit_base_qty`, `entry_exec_value`, `exit_exec_value`, `gross_quote`, `quote_fee`, `base_fee`, `third_fee_present`, `net_quote`, `terminal_reconciliation_event_id`, `eligibility`, `ineligibility_code` |
| `CORRECTION_COMMITTED` | `target_event_id`, `target_event_sha256`, `correction_code`, `replacement_event_id` |
| `EVIDENCE_OUTAGE_RECORDED` | `incident_sha256`, `outage_code`, `first_affected_event_id`, `risk_reduction_occurred` |
| `RECOVERY_COMMITTED` | `incident_sha256`, `recovery_record_sha256`, `approval_sha256`, `reconciliation_event_id`, `prior_head_sha256` |

`client_key` in `IDEMPOTENCY_KEY_RESERVED` is the sole explicitly private raw
correlation exception. It never appears in projection, logs, error text, lane
state, or another payload. No raw venue order/execution/account/wallet/signal
identifier is permitted.

Field enums and bounds:

- `symbol=ETHUSDT`; `timeframe=1h`;
- `decision=ENTRY|EXIT|STOP|CANCEL|NO_ACTION`;
- `side=BUY|SELL|NONE`;
- `quantity_unit=BASE|QUOTE|NONE`;
- `verdict=ALLOW_RISK_INCREASE|BLOCK|RISK_REDUCING`;
- `reason_code=POLICY_PASS|POLICY_BLOCK|EXIT_ONLY|KILL_SWITCH`;
- `order_kind=ENTRY|EXIT|STOP_CREATE|STOP_REPLACE|STOP_CLEANUP|CANCEL`;
- `order_type=MARKET|STOP_MARKET`;
- `endpoint=CREATE|CANCEL`; `attempt_ordinal` is exactly 1 for `CREATE`;
- `result_code=ACCEPTED_PENDING|POLICY_REJECTED|VENUE_REJECTED|TIMEOUT|DISCONNECT|MALFORMED|UNKNOWN`;
- `venue_code` is an integer from -2^31 through 2^31-1; no venue text;
- `order_status=NEW|PARTIALLY_FILLED|FILLED|CANCELLED|REJECTED|PARTIALLY_FILLED_CANCELED|UNTRIGGERED|TRIGGERED|DEACTIVATED|UNKNOWN`;
- `source=REALTIME|HISTORY|EXECUTION|RECONCILIATION`;
- `cancel_state=ACK_PENDING|CONFIRMED|REJECTED|UNKNOWN`;
- `exit_state=STARTED|PARTIAL|TERMINAL|UNKNOWN`;
- `terminal_status=FILLED|CANCELLED|REJECTED|PARTIALLY_FILLED_CANCELED`;
- `protective_stop_state=CLEAR|ACTIVE|FILLED|CANCELLED|UNKNOWN`;
- `fee_currency=USDT|ETH|THIRD`; a `THIRD` fee uses only `fee_alias`;
- `eligibility=ELIGIBLE|PERMANENTLY_INELIGIBLE`;
- `ineligibility_code=NONE|LEGACY|OUTAGE|CORRECTION|THIRD_CURRENCY_FEE|CHAIN_GAP|UNRESOLVED|STOP_NOT_CLEAR`;
- `correction_code=SOURCE_CORRECTION|DUPLICATE_CONFLICT|RECONCILIATION_CORRECTION`;
- `outage_code=WRITE|FSYNC|PERMISSION|CAPACITY|HASH|SEQUENCE|SCHEMA|UNKNOWN_RESULT`.

All decimal fields are exact decimal strings. Required nonnegative economic
fields reject negatives. `third_fee_present`, `flat`,
`all_pages_complete`, and `risk_reduction_occurred` are JSON booleans.
Nullable fields are explicitly JSON null:
`trigger_price`, `avg_price`, `first_affected_event_id`,
`replacement_event_id`, `net_quote` (null only for a permanently ineligible
episode with a nonzero third-currency fee), and `ineligibility_code` (null only
when eligible).
No arbitrary string, list, object, reason, note, action, error, or metadata map
is accepted.

#### Risk-reducing create durability

Every `EXIT_CREATE`, `STOP_CREATE`, and `STOP_REPLACE_CREATE` key is derived
from the already committed risk-increasing
`SUBMISSION_INTENT_COMMITTED.event_id` that created the exposure. A fill event
is never the subject because risk reduction must remain possible before any
fill event can be durably written.

The canonical preimage is the exact ASCII byte concatenation:

```text
ASCII("tios.demo_decision_evidence.v2\0risk-reduction-create\0")
+ ASCII(activation_epoch)
+ ASCII("\0")
+ ASCII(subject_intent_event_id)
+ ASCII("\0")
+ ASCII(action_kind)
+ ASCII("\0")
+ ASCII(base10_sequence_without_leading_zeroes)
+ ASCII("\0")
+ ASCII(payload_sha256)
```

The client key is:

```text
"tios2_r_" + lowercase_hex(SHA256(preimage))[0:28]
```

It is exactly 36 allowed characters. `client_key_sha256` in lane state is the
full lowercase SHA-256 of that client key; the raw key is recomputed only from
the verified pending record. The exact protocol under the lane lock is:

1. validate the typed payload, bind its canonical `payload_sha256`, derive the
   action ID/key, and atomically persist phase `RESERVED` plus directory fsync
   in existing `lane_state.json`;
2. atomically persist `POST_UNKNOWN` **before** the one permitted create POST;
3. issue exactly one create POST;
4. persist `ACK_PENDING` after a valid asynchronous acknowledgement;
5. query realtime/history/executions by the derived key until exact terminal
   reconciliation, then persist `TERMINAL`.

A crash at `RESERVED` may continue once through step 2. A crash at
`POST_UNKNOWN` or `ACK_PENDING` is query-only and never replays create. Empty
realtime/history/execution results do not prove non-creation. A pre-POST crash
that leaves `POST_UNKNOWN` stays unresolved and permits no automatic new
create. A later distinct risk-reduction action requires operator-reviewed
recovery plus fresh full position/order/stop reconciliation; it is never
inferred from an empty lookup.

`CANCEL_TARGET` derives no key. It uses the target's original private
`orderLinkId` from the committed private chain or the exact venue `orderId`
already tracked by the existing lane stop state, performs a fresh status query
before any cancel, persists `POST_UNKNOWN` before one cancel POST, and after
ambiguity queries again before any separately justified repeat. It never
cancels by a guessed or newly derived correlation.

This record is owned by the already-durable lane state, so Stage B evidence
write outage cannot block the first exit/stop/cancel attempt. Submission
ambiguity may still block an automatic duplicate create. Tests cover four crash
points—before `RESERVED`, after `RESERVED`, after `POST_UNKNOWN` before POST,
and after POST before acknowledgement persistence—for each exit, stop-create,
and stop-replace path, plus cancel correlation and payload-hash verification.

### Appendix C — generation and projection schemas

`manifest.json` contains exactly:

```json
{
  "schema": "tios.demo_decision_evidence.generation_manifest.v1",
  "activation_epoch": "act_<64hex>",
  "activation_receipt_sha256": "<64hex>",
  "controlled_restart_id": "restart_<allowed>",
  "repo_commit": "<40-lowercase-hex>",
  "config_sha256": "<64hex>",
  "previous_manifest_sha256": "<64hex-or-null>",
  "first_sequence": 1,
  "last_sequence": 1,
  "event_count": 1,
  "events_sha256": "<64hex>",
  "events_bytes": 1,
  "reducer_state_sha256": "<64hex>",
  "reducer_state_bytes": 1,
  "public_projection_sha256": "<64hex>",
  "public_projection_bytes": 1,
  "committed_at": "UTC"
}
```

`event_count` is 1..4,096. `events_bytes` is
1..268,435,456; `reducer_state_bytes` is 1..33,554,432; and
`public_projection_bytes` is 1..4,194,304. The generation directory is `G-`
plus SHA-256 of the canonical manifest bytes; the manifest does not contain its
own digest. Any bound breach fails the generation, makes the projection
`UNAVAILABLE`, and latches `ENTRY_BLOCK`.

There is no staging directory. Under the exclusive lane lock, the writer
computes the three data files and canonical manifest bytes/hashes in memory,
derives the final `G-<manifest_sha256>` name, and exclusively creates that final
directory. It then writes and fsyncs `events.jsonl`, `reducer_state.json`, and
`public_projection.json`; writes and fsyncs the fixed
`.manifest.json.tmp`; atomically renames that file to `manifest.json`; and
fsyncs the generation directory. The manifest rename is the sole commit point.

A partial final directory without a valid `manifest.json` is atomically renamed
under the lock to a fresh `quarantine/U-<uuid>/` and fsynced; it is never
promoted. A valid manifest means committed. The only transient names allowed
are `.manifest.json.tmp` inside the exclusive new final generation and
`HEAD.json.tmp` directly under `store/`, both only while the lock is held.

If `G-<digest>` already exists with valid manifest, exact canonical bytes,
hashes, modes, owner, and links, the operation is idempotent and writes nothing.
Any same-name byte/metadata conflict latches `ENTRY_BLOCK`; it is never
overwritten. Crash tests cover immediately before and immediately after the
manifest rename, each data/file-directory fsync, and `HEAD` temp/rename.

`HEAD.json` contains exactly:

```json
{
  "schema": "tios.demo_decision_evidence.head.v1",
  "activation_epoch": "act_<64hex>",
  "manifest_sha256": "<64hex>",
  "generation_path": "store/generations/G-<64hex>",
  "last_sequence": 1
}
```

`reducer_state.json` contains exactly:

```json
{
  "schema": "tios.demo_decision_evidence.reducer_state.v1",
  "activation_epoch": "act_<64hex>",
  "activation_receipt_sha256": "<64hex>",
  "controlled_restart_id": "restart_<allowed>",
  "repo_commit": "<40-lowercase-hex>",
  "config_sha256": "<64hex>",
  "last_sequence": 1,
  "last_event_sha256": "<64hex>",
  "evidence_state": "READY|ENTRY_BLOCK|RECOVERY_AUTHORIZED|RECONCILED_PENDING_COMMIT",
  "incident_sha256": "<64hex-or-null>",
  "unresolved_order_alias": "ord_<64hex>-or-null",
  "unresolved_client_key": "<private-client-key-or-null>",
  "flat": true,
  "protective_stop_state": "CLEAR|ACTIVE|FILLED|CANCELLED|UNKNOWN",
  "series": []
}
```

`series` is an array in first-fill order, maximum 256. Each item has exactly
`series_number`, `series_sha256`, `strategy_alias`, `cost_alias`, `risk_alias`,
`next_episode_ordinal`, `open_episode_event_id`, and `cohorts`.
`series_number` is 1..256 and immutable. `next_episode_ordinal` is
1..2^63-1. `open_episode_event_id` is nullable.
`cohorts` is an ordered array; at most 4,096 cohorts exist across all series
combined. Each item has exactly
`cohort_number`, `assigned_count`, `eligible_closed_count`,
`ineligible_count`, `open_count`, and `aggregate`. Counts are integers 0..30;
`aggregate` is null or the exact aggregate object below. No episode rows are
stored in the projection; the private event chain remains authoritative.

The private `public_projection.json` is distinct from the API envelope and
contains exactly:

```json
{
  "schema": "tios.demo_decision_evidence.public_projection.v1",
  "status": "READY|ENTRY_BLOCK|UNAVAILABLE",
  "cohort_size": 30,
  "series": []
}
```

Each series has exactly `series_number` and `cohorts`; it contains no private
alias/hash. Cohorts and aggregate objects have exactly the public fields
defined below. The file is at most 4,194,304 bytes and contains at most 4,096
cohorts total. Overflow makes the API Stage B status `UNAVAILABLE` and latches
`ENTRY_BLOCK`; it never truncates or selects a subset.

The GET `/api/v1/demo-lane` combines that validated private projection with
operational fields and may expose exactly:

```json
{
  "schema_version": 2,
  "operational_status": "RUNNING|STOPPING|STOPPED|IDLE|UNAVAILABLE",
  "kill_switch": false,
  "environment": "VENUE_DEMO",
  "real_money": false,
  "execution_authority": "NONE",
  "validation_state": "UNVALIDATED",
  "promotion_eligible": false,
  "auto_tune": false,
  "stage_b": {
    "status": "NOT_ACTIVATED|READY|ENTRY_BLOCK|UNAVAILABLE",
    "cohort_size": 30,
    "series": []
  }
}
```

Every successful body produced by the demo-lane action handler is restricted
to:

```json
{
  "schema_version": 2,
  "ok": true,
  "action": "START|STOP|RUN_ONCE",
  "state": "RUNNING|STOPPING|STOPPED|IDLE|UNAVAILABLE"
}
```

`ok` is a JSON boolean. No timestamp, PID, idempotency key, audit detail, free
text, exception text, or private field is returned on success. Detailed action
audit stays disk-only. The existing in-scope `dashboard_api/demo_lane.py` owns
success-response sanitization and replaces reflected invalid-action text with
a fixed generic error. Pre-handler and exception responses remain the
unchanged server's generic schema-v1 error envelope and are explicitly outside
the Stage B evidence projection; they must not reflect request values or
contain evidence, venue, wallet, PID, or private fields. Tests cover the exact
success body, generic non-reflecting handler/server errors, and prove
`START`/`RUN_ONCE` cannot clear the latch.

Every immutable series is returned in first-fill order. Each public series has
exactly `series_number` and `cohorts`; no private hash or strategy/cost/risk
alias is projected. Each cohort has exactly `cohort_number`,
`assigned_count`, `eligible_closed_count`, `ineligible_count`, `open_count`,
`readiness`, and `aggregate`.
`readiness=COLLECTING|COMPLETE|PERMANENTLY_INELIGIBLE`.

`aggregate` is null until exactly 30 ordinals are assigned, all 30 are eligible
and closed, and reconciliation is complete. If any assigned ordinal becomes
ineligible, that ordinal is never replaced/refilled and that cohort remains
`PERMANENTLY_INELIGIBLE` with `aggregate=null`. A completed aggregate contains
exactly:

```json
{
  "closed_count": 30,
  "positive_count": 0,
  "negative_count": 0,
  "flat_count": 30,
  "entry_exec_value_total": "0",
  "exit_exec_value_total": "0",
  "gross_quote_total": "0",
  "quote_fee_total": "0",
  "base_fee_total": "0",
  "net_quote_total": "0"
}
```

No request/query parameter may select a series, cohort, period, asset, outcome,
or subgroup. Later cohorts never alter earlier cohort bytes.

The global allowlist intentionally removes legacy heartbeat timestamps, PID,
cursor, wallet, positions, position/order rows, signal data, per-trade PnL,
window PnL, best/worst, streak, and curves in inactive and active states. This
reduces operator detail to eliminate side-channel disclosure; it is not a
nested-only redaction.

### Appendix D — activation receipt and alias material

All five activation JSON files are canonical, deny-unknown, duplicate-key
rejecting, single-link user-owned `0600` files under the fixed `0700`
activation directory.

`CONFIG.json` contains exactly:

```json
{
  "schema": "tios.demo_decision_evidence.config.v1",
  "implementation_module_sha256": "<64hex>",
  "paths": {
    "private_root": "artifacts/evidence/private_demo/stage_b_v2",
    "receipt": "activation/ACTIVATION_RECEIPT.json",
    "config": "activation/CONFIG.json",
    "independent_review": "activation/INDEPENDENT_REVIEW.json",
    "flat_reconciliation": "activation/FLAT_RECONCILIATION.json",
    "rollback_config": "activation/ROLLBACK_CONFIG.json",
    "alias_key": "private/install_alias.key",
    "generations": "store/generations",
    "head": "store/HEAD.json",
    "quarantine": "quarantine",
    "recovery": "recovery",
    "lane_state": "artifacts/trading_domain/demo_lane/lane_state.json"
  },
  "limits": {
    "frame_bytes": 65536,
    "events_per_generation": 4096,
    "events_bytes": 268435456,
    "reducer_bytes": 33554432,
    "public_projection_bytes": 4194304,
    "cohorts_total": 4096,
    "pages_per_endpoint": 100,
    "rows_per_page_internal": 50
  },
  "contracts": {
    "event_schema": "tios.demo_decision_evidence.v2",
    "cohort_size": 30,
    "formula": "EXACT_EXECUTION_CASHFLOW_V1",
    "dashboard_schema": "TIOS_DEMO_LANE_GLOBAL_ALLOWLIST_V2",
    "commit_protocol": "FINAL_DIR_MANIFEST_RENAME_V1",
    "create_attempts_per_logical_submission": 1
  }
}
```

`implementation_module_sha256` binds the source file that owns and checks these
constants. SHA-256 of the complete canonical CONFIG bytes is `config_sha256`.

`INDEPENDENT_REVIEW.json` contains exactly
`schema=tios.demo_decision_evidence.independent_review.v1`, `decision=GO`,
`reviewed_commit` (40 lowercase hex), `file_sha256`, `config_sha256`, and
`reviewed_at` (UTC). `file_sha256` is the exact 15-key map printed in the
receipt schema below, with no additional/missing key, and every value is a
64-hex digest.

`FLAT_RECONCILIATION.json` contains exactly:

```json
{
  "schema": "tios.demo_decision_evidence.flat_reconciliation.v1",
  "repo_commit": "<40-lowercase-hex>",
  "config_sha256": "<64hex>",
  "prior_stage_b_head_sha256": "<64hex-or-null>",
  "observed_at": "UTC",
  "position_base_qty": "0",
  "open_order_count": 0,
  "unresolved_attempt_count": 0,
  "protective_stop_state": "CLEAR",
  "all_pages_complete": true,
  "source": "REALTIME_HISTORY_EXECUTION"
}
```

`ROLLBACK_CONFIG.json` contains exactly:

```json
{
  "schema": "tios.demo_decision_evidence.rollback_config.v1",
  "rollback_commit": "<40-lowercase-hex>",
  "prior_file_sha256": {
    "scripts/demo_eth_lane.py": "<64hex>",
    "scripts/demo_roundtrip.py": "<64hex>",
    "src/tios/services/dashboard_api/demo_lane.py": "<64hex>",
    "src/tios/services/dashboard_ui/dashboard.html": "<64hex>"
  },
  "prior_config": {
    "schema": "tios.demo_decision_evidence.rollback_prior_config.v1",
    "stage_b": "ABSENT",
    "execution_authority": "NONE"
  },
  "make_start_target": "demo-lane",
  "make_once_target": "demo-lane-once",
  "recorded_at": "UTC"
}
```

`prior_stage_b_head_sha256` is null for the first Stage B epoch and otherwise
binds the last validated prior-epoch head. The inline `prior_config` object is
the authoritative pre-Stage-B configuration; it is canonical data, not a
digest without a source object.

`ACTIVATION_RECEIPT.json` contains exactly:

```json
{
  "schema": "tios.demo_decision_evidence.activation_receipt.v1",
  "state": "ACTIVE",
  "environment": "VENUE_DEMO",
  "real_money": false,
  "execution_authority": "NONE",
  "package_version": "v8.146",
  "repo_commit": "<40-lowercase-hex>",
  "file_sha256": {
    "src/tios/evidence/demo_decision_evidence_v2.py": "<64hex>",
    "tests/test_demo_decision_evidence_v2.py": "<64hex>",
    "scripts/demo_eth_lane.py": "<64hex>",
    "scripts/demo_roundtrip.py": "<64hex>",
    "tests/test_demo_eth_lane.py": "<64hex>",
    "tests/test_demo_roundtrip.py": "<64hex>",
    "src/tios/services/dashboard_api/demo_lane.py": "<64hex>",
    "tests/test_demo_lane_api.py": "<64hex>",
    "src/tios/services/dashboard_ui/dashboard.html": "<64hex>",
    "tests/test_dashboard.py": "<64hex>",
    "PROJECT_STATE.md": "<64hex>",
    "DECISION_LOG.md": "<64hex>",
    "docs/architecture/AD.md": "<64hex>",
    "PACKAGE_CHANGELOG.md": "<64hex>",
    "PACKAGE_INTEGRITY_MANIFEST.md": "<64hex>"
  },
  "config_path": "artifacts/evidence/private_demo/stage_b_v2/activation/CONFIG.json",
  "config_sha256": "<64hex>",
  "independent_review_path": "artifacts/evidence/private_demo/stage_b_v2/activation/INDEPENDENT_REVIEW.json",
  "independent_review_sha256": "<64hex>",
  "flat_reconciliation_path": "artifacts/evidence/private_demo/stage_b_v2/activation/FLAT_RECONCILIATION.json",
  "flat_reconciliation_sha256": "<64hex>",
  "rollback_config_path": "artifacts/evidence/private_demo/stage_b_v2/activation/ROLLBACK_CONFIG.json",
  "rollback_config_sha256": "<64hex>",
  "private_root": "artifacts/evidence/private_demo/stage_b_v2",
  "receipt_path": "artifacts/evidence/private_demo/stage_b_v2/activation/ACTIVATION_RECEIPT.json",
  "alias_key_path": "artifacts/evidence/private_demo/stage_b_v2/private/install_alias.key",
  "alias_key_sha256": "<64hex>",
  "rollback_commit": "<40-lowercase-hex>",
  "controlled_restart_id": "restart_<1-64-allowed-chars>",
  "activation_epoch": "act_<64hex>",
  "approved_at": "UTC"
}
```

`file_sha256` has exactly those 15 keys. Each of the four activation digest
fields is SHA-256 of the exact canonical bytes at its fixed path; parsed
contents must also cross-bind the same commit/config/file hashes.
`controlled_restart_id` matches `^restart_[A-Za-z0-9_-]{1,64}$`.
Unknown/missing fields, hash mismatch, dirty/unbound source, wrong version or
environment, `real_money!=false`, authority other than `NONE`, stale approval,
permission/link/owner drift, alias mismatch, non-flat reconciliation, or
rollback mismatch fails activation.

The receipt is immutable for one activation epoch and is consumed only on first
activation. At sequence 1, `ACTIVATION_BOUND` binds the receipt, CONFIG, review,
flat-reconciliation, and rollback-config hashes, controlled restart ID, repo
commit, and epoch. The first valid manifest containing that event is the
authoritative consumed-ID record and pins the same receipt hash, restart ID,
repo commit, and config hash in manifest, reducer, and lane latch. A crash
before that manifest rename leaves the ID unconsumed; a crash after it
reconstructs consumed state from the committed manifest/event.

Only first consumption applies the 15-minute `approved_at` rule and unused-ID
check. Later process restarts in the same activation epoch reuse the pinned
immutable receipt without a new activation and must complete startup
reconciliation before entries. Changed source, config, alias material, or epoch
requires verified-flat state, a separate activation, new receipt, and new
series. Starting with bytes that differ from the pinned receipt fails closed.

These same-user activation/review files are procedural evidence and hash-bound
change control; they are not cryptographic proof of operator identity or
independent-reviewer identity.

At later operator activation, `install_alias.key` is exactly 32 CSPRNG bytes.
For raw canonical UTF-8 bytes `value` and tag
`ord|exe|fee|strategy|cost|risk`, the alias is:

```text
tag + "_" + lowercase_hex(
  HMAC-SHA256(key, "tios.demo_decision_evidence.v2\0" + tag + "\0" + value)
)
```

The full 256-bit digest is retained; truncation is forbidden. Alias regex is
`^(ord|exe|fee|strategy|cost|risk)_[a-f0-9]{64}$`. A single alias bound to
contradictory typed content fails closed. Material is immutable for one
activation epoch. Rotation requires verified flat state, a new activation
receipt and epoch, and new immutable series; aliases/cohorts never pool across
epochs. The key is created only in the later operator activation, never during
implementation.

### Appendix E — recovery and unlatch contract

The existing v2 module owns the only recovery interface:

```bash
uv run python -m tios.evidence.demo_decision_evidence_v2 recover \
  --approval <absolute-json> \
  --expected-head <64hex> \
  --expected-incident <64hex> \
  --expected-reconciliation <evt_alias> \
  --expected-quarantine <64hex>
```

The approval path must be absolute, user-owned, regular, single-link `0600`.
Its JSON contains exactly:

```json
{
  "schema": "tios.demo_decision_evidence.recovery_approval.v1",
  "decision": "APPROVE_RECOVERY_RECORD_ONLY",
  "activation_epoch": "act_<64hex>",
  "expected_head_sha256": "<64hex>",
  "expected_incident_sha256": "<64hex>",
  "expected_reconciliation_event_id": "evt_<64hex>",
  "expected_quarantine_inventory_sha256": "<64hex>",
  "reason_code": "CHAIN_VERIFIED_AND_FLAT_RECONCILIATION_REQUIRED",
  "approved_at": "UTC"
}
```

Approval must be no older than 15 minutes. The CLI rejects unknown fields and
requires every argument to equal the approval. The quarantine digest is the
SHA-256 of this exact canonical object:

```json
{
  "schema": "tios.demo_decision_evidence.quarantine_inventory.v1",
  "entries": [
    {
      "path": "U-<uuid>/events.jsonl",
      "type": "FILE",
      "mode": "0600",
      "bytes": 1,
      "sha256": "<64hex>"
    }
  ]
}
```

Every descendant directory and file is included. `path` is a relative POSIX
path matching ASCII `^[A-Za-z0-9._/-]+$`, with no empty, dot, or dot-dot
component and no leading/trailing slash. Names outside the fixed inventory fail
validation. `type=DIR|FILE`; mode is the four-character string `0700` for
directories or `0600` for files. Directories have `bytes=null` and
`sha256=null`; files have nonnegative integer bytes and content SHA-256.
Entries sort by raw UTF-8 path bytes. Unicode is forbidden, so normalization
cannot change identity. A count alone is insufficient.

The expected reconciliation event must already exist in the validated chain
and is the operator's pre-recovery candidate evidence; it cannot clear the
latch. The CLI validates the full manifest chain, event/reducer/projection
hashes, exact quarantine digest, activation receipt, alias hash, ownership,
links, and exact `0700`/`0600` modes. It has no
network/order/credential capability.

The CLI writes only
`recovery/RECOVERY-<sha256>.json`, create-only, manifest-independent, `0600`,
where `<sha256>` is the SHA-256 of canonical bytes. The record contains exactly
`schema=tios.demo_decision_evidence.recovery_record.v1`,
`activation_epoch`, `approval_sha256`, `incident_sha256`,
`expected_head_sha256`, `expected_reconciliation_event_id`,
`expected_quarantine_inventory_sha256`, `validated_head_sha256`,
`activation_receipt_sha256`, `quarantine_entry_count`, and `recorded_at`. It
never writes `HEAD`, events, lane state, receipt, key, quarantine, or another
file and never clears a latch.

Under the lane lock, unlatch requires all of:

1. a valid recovery record for the current incident/head;
2. a new fresh typed exact-client-key reconciliation performed after that
   record, distinct from the approval's expected reconciliation, proving
   every attempt terminal, position exactly flat, and protective-stop state
   `CLEAR`;
3. a durable `RECOVERY_COMMITTED` event binding the record, incident, approval,
   and reconciliation event;
4. atomic lane-state write clearing the incident only after the committed
   recovery event.

Reconciliation alone or recovery record alone never clears the latch. A crash
after step 3 may repeat only the lane-state projection under the lock; it may
not append another recovery event or create attempt.

| Current state | Input | Next state | New entry |
| --- | --- | --- | --- |
| absent/disabled | no valid receipt | disabled | existing behavior; v2 inactive |
| `READY` | evidence/submit ambiguity or outage | `ENTRY_BLOCK` | blocked |
| `ENTRY_BLOCK` | reconciliation only | `ENTRY_BLOCK` | blocked |
| `ENTRY_BLOCK` | valid recovery record only | `RECOVERY_AUTHORIZED` | blocked |
| `RECOVERY_AUTHORIZED` | fresh exact-key terminal+flat+stop-clear reconciliation | `RECONCILED_PENDING_COMMIT` | blocked |
| `RECONCILED_PENDING_COMMIT` | durable `RECOVERY_COMMITTED` + lane-state projection | `READY` | allowed for a new logical submission |
| any blocked state | restart, dashboard `START`, or `RUN_ONCE` | same blocked state | blocked |

Evidence-store failure leaves the first risk-reducing exit/stop/cancel,
kill-switch, and reconciliation attempt available. A risk-reducing create
already in `POST_UNKNOWN` remains query/operator-recovery-only in every state;
no availability claim authorizes a duplicate create.

### Appendix F — episode assignment and fee formulas

An immutable series identity is SHA-256 over activation epoch plus
`strategy_alias`, `cost_alias`, and `risk_alias`. Series appear in first-fill
order. An episode ordinal is assigned under the lane lock at its first positive
entry fill, before the outcome is known. Cohort number is
`floor((ordinal-1)/30)+1`. Restart, concurrent close, correction, outage, version
change, or ineligibility cannot move, replace, refill, or reuse an ordinal.
Version/cost/risk/epoch change starts a new series at ordinal 1.

For all executions assigned to one episode:

```text
entry_exec_value = Σ Buy execValue
exit_exec_value  = Σ Sell execValue
quote_fee        = Σ feeAmount where feeCurrency=USDT
base_fee         = Σ feeAmount where feeCurrency=ETH
third_fee_present = any nonzero feeAmount where feeCurrency=THIRD
gross_quote      = exit_exec_value - entry_exec_value
net_quote        = gross_quote - quote_fee, only when third_fee_present=false
acquired_base    = Σ Buy execQty - Σ Buy base-fee charged from acquired base
disposed_base    = Σ Sell execQty + Σ Sell base-fee charged from held base
terminal_base    = acquired_base - disposed_base
```

Quote fees always subtract from net. Base fees change exact reconciled quantity
and therefore actual exit cashflow; they are disclosed as base fees but never
converted to quote or subtracted again. Exact `execValue` owns entry/exit quote
cashflow. Wallet/rounded deltas and mark conversion never own a formula.

Every third-currency fill retains its exact `fee_amount` and `fee_alias`; values
from different third currencies are never summed. Any nonzero third-currency
fee makes `net_quote=null` and the already assigned episode permanently
cohort-ineligible. It is not converted, dropped, replaced, or used to refill a
cohort. Eligibility additionally requires exact terminal base zero and
protective-stop `CLEAR`, complete pages, no outage/correction/chain gap, and
durable terminal reconciliation.

### Appendix G — mandatory additional tests

In addition to the earlier matrix, tests must prove:

- repository runtime paths and latch fields stay absent during implementation;
- a temporary valid receipt/key/root passes the positive activation reader;
- CONFIG/review/flat/rollback files reject every unknown/missing field and
  digest/cross-binding mismatch; same-user records are never reported as
  cryptographic identity proof;
- each receipt hash/path/mode/owner/link/staleness/epoch/restart/alias mismatch
  fails;
- first activation crash before `ACTIVATION_BOUND` manifest rename leaves the
  restart ID unconsumed; crash after rename reconstructs it as consumed;
  same-epoch restart reuses the pinned receipt after startup reconciliation;
- raw alias material is 32 bytes; every domain vector produces the full expected
  HMAC; contradictory reuse and rotation-without-flat fail;
- 64 KiB/65 KiB frames, 4,096/4,097 events,
  268,435,456/268,435,457 event bytes,
  33,554,432/33,554,433 reducer bytes, and
  4,194,304/4,194,305 public bytes hit exact boundaries;
- realtime/history official 50-row maxima and execution official 100-row
  maximum are represented, while every Stage B request remains internally
  capped at 50; 100/101 pages, 5,000/5,001 total frames, and 513 execution
  frames hit the exact internal boundaries;
- every event payload rejects each missing/extra/wrong-type/unknown-enum field;
- immediately pre-manifest-rename is uncommitted/demoted; immediately
  post-rename is committed; `.manifest.json.tmp`/`HEAD.json.tmp` are accepted
  only under lock; byte conflicts fail and identical bytes are idempotent;
- stale/missing/corrupt `HEAD` reconstructs from manifests and cannot commit;
- quarantine is never promoted; any path/byte/mode/content inventory-digest
  mismatch fails; recovery writes exactly one allowed record;
- reconciliation alone and recovery-record alone do not unlatch;
- exact-key fresh reconciliation plus durable recovery event is required;
- timeout/ambiguity causes zero create retries across same-process and restart;
- deterministic risk-reduction keys reconstruct across restart, advance only
  through the durable lane-owned sequence, contain no raw client key in lane
  state, and evidence-store failure cannot block their first single POST;
  `POST_UNKNOWN` blocks automatic duplicate creates;
- each exit/stop-create/stop-replace path covers crashes before `RESERVED`,
  after `RESERVED`, after pre-POST `POST_UNKNOWN`, and after POST before ack;
  `CANCEL_TARGET` uses only original correlation after fresh status, and every
  pending payload hash/combinatorial constraint is verified; empty lookups
  never become terminal or authorize another automatic create;
- assigned-then-ineligible remains in place; later episodes do not refill it;
- restart preserves ordinal; interleaved series/version changes do not pool;
- outage/correction makes the assigned episode ineligible;
- concurrent closes serialize and cannot duplicate ordinal;
- episode 31 and every later cohort leave cohort 1 bytes unchanged;
- third-currency fee is ineligible; quote/base fee formulas have no double count;
- no API/query selector can request a subgroup;
- private public projection contains only schema/status/cohort size/numbered
  series/cohorts, stays below 4 MiB and 4,096 total cohorts, and overflow is
  unavailable plus `ENTRY_BLOCK`;
- demo-lane action success responses contain exactly the four typed fields and
  no timestamp/idempotency/PID/free text; detailed audit remains disk-only;
  unchanged server error envelopes are generic, non-reflecting, and outside
  the Stage B projection;
- inactive and active dashboard responses globally omit every legacy forbidden
  field, activation epoch, private hash, and strategy/cost/risk alias;
- dashboard `START` and `RUN_ONCE` cannot clear `ENTRY_BLOCK`.

Independent architecture/security review of this remediated contract returned
`GO` for seeking the two exact approvals. Independent review of the eventual
exact implementation remains mandatory before the v8.146 gate and again before
activation.
