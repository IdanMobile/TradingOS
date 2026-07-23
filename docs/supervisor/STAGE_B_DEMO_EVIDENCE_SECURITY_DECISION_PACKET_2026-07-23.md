# Stage B demo-evidence security decision packet — 2026-07-23

## Decision required

The operator must choose whether the fake-money demo lane should continue with
manual, incomplete Stage A capture or later receive a reviewed in-lane Stage B
evidence tap.

**Recommendation: Option A, full evidence-first Stage B, subject to every
implementation and activation gate in this packet.** This recommendation is
about evidence integrity, not trading performance.

This packet is review-only. It does not authorize implementation, service
restart, demo activation, order submission, strategy approval, promotion,
auto-tuning, a production venue, live trading, or real money. Its execution
authority is `NONE`.

## Verified starting point

The latest retained point-in-time service check reported a healthy operational
substrate: the orchestrator was not halted, the dashboard returned HTTP `200`,
and the demo lane was running with fake money, `UNVALIDATED`,
`promotion_eligible=false`, and an active protective stop. No restart was
required at that check. This is liveness evidence only; it is not evidence of
future uptime, strategy quality, PnL, edge, or profitability.

The first real sanitized capture and offline Stage A import also passed their
software and replay checks, but they retained only one aggregate order
observation in an open, incomplete legacy episode:

- completeness: `PARTIAL_LEGACY_OPEN`;
- position state: `OPEN_INCOMPLETE`;
- realized outcomes: `0`;
- PnL available: `false`;
- strategy evaluation available: `false`;
- promotion eligible: `false`;
- execution authority: `NONE`.

**Stage A cannot report realized PnL.** Its two retained events are not a
complete decision-to-terminal-reconciliation chain. Repeating manual Stage A
captures does not retroactively make the pre-existing position or its missing
history complete.

The sanitized Stage A evidence root already uses `0700` directories, `0600`
files, and manifest-last commits. Separately, the existing legacy raw demo-lane
runtime paths were observed with directories at `0755` and files at `0644`.
Those raw paths must be hardened before any in-lane tap is activated. No raw
value from those files is reproduced in this packet.

Authoritative project boundaries remain in force:

- `PROJECT_STATE.md` is the live authority;
- Phase 2b external activation and genuine independent review are incomplete;
- Phases 3 and 4 remain blocked;
- no strategy is approved or proven profitable;
- no candidate admission, production venue, live order, or real-money authority
  exists.

## Options

### Option A — full evidence-first Stage B — recommended

Build a synchronous in-lane evidence boundary for the fake-money demo only. A
risk-increasing submission may occur only after its complete pre-submission
evidence generation, including its client idempotency key, is durably committed
and `fsync`-verified. Venue results and terminal reconciliation are then
appended without mutating prior evidence.

Benefits:

- establishes a complete post-activation decision-to-reconciliation chain;
- makes duplicate prevention and recovery auditable;
- can eventually support strictly aggregate, after-cost demo diagnostics;
- fails closed for new exposure when evidence integrity is unavailable.

Costs and risks:

- touches the order-path boundary and therefore needs an explicit policy
  decision, bounded implementation authority, controlled restart, and
  independent security review;
- increases operational coupling between evidence availability and new-entry
  availability;
- cannot reconstruct or validate the pre-existing legacy position;
- still cannot validate, approve, promote, or auto-tune a strategy.

### Option B — passive partial Stage B tap

Add an asynchronous observer after the existing order decision/submission
boundary. It must never affect order behavior and must label all output
`PASSIVE_PARTIAL`.

This is lower coupling, but it cannot prove that evidence was durable before a
submission, cannot supply strong duplicate-prevention evidence, and cannot
establish a complete decision chain. Its outputs remain operational diagnostics
only. They cannot be combined with Option A cohorts or used for PnL validation,
promotion, approval, or auto-tuning.

### Option C — continue manual Stage A

Make no in-lane code or runtime change. Continue explicit read-only capture and
separate offline import under the existing source label and fail-closed
history.

This is the lowest operational risk and requires no restart. It preserves the
current limitation: Stage A cannot report realized PnL or produce a complete
closed-episode chain.

## Option A security contract

### 1. Exact boundary

The tap may observe and persist only typed, allowlisted demo decision,
risk-verdict, submission, venue-result, position, and reconciliation facts. It
must be one fixed, non-pluggable sanitized sink invoked under the existing demo
lane lock. It may not be dynamically selected or called outside the lane's
serialization boundary.

Its schema is `tios.demo_decision_evidence.v2`, a new chain separate from Stage
A v1. Stage A v1 stays unchanged and must not be upgraded or appended into v2.
The immutable simulation `DecisionTrace` types are inapplicable and must not be
modified or reused as a shortcut.

The tap must not:

- create, change, size, route, retry, cancel, or approve an order;
- change a strategy signal, risk verdict, stop, target, or lane state;
- acquire independent venue, wallet, or network capability;
- read or export credentials, request headers, environment secrets, private
  keys, API keys, withdrawal permissions, or wallet identifiers;
- add a dashboard mutation surface;
- create admission, approval, promotion, or live authority.

The existing decision, risk, and order owners remain unchanged. The tap is an
evidence gate for risk-increasing submissions, not a trading authority.

### 2. Activation boundary

Activation may occur only during a controlled restart while the demo lane is
verified flat and has no unresolved venue order. The flat check must be
performed through the existing typed reconciliation path, not inferred from a
dashboard label.

If a position, protective order, non-terminal order, or unresolved submission
exists, activation is a `NO-GO`. Reconcile through the existing lane and
reschedule only after verified flat. All pre-activation history remains
`LEGACY_EXCLUDED`; missing history cannot be completed by inference.

### 3. Exact append-only event chain

For each logical risk-increasing submission, the exact chain is:

1. `DECISION_OBSERVED`
2. `RISK_VERDICT_OBSERVED`
3. `IDEMPOTENCY_KEY_RESERVED`
4. `SUBMISSION_INTENT_COMMITTED`
5. `SUBMISSION_ATTEMPTED`
6. exactly one initial result:
   `VENUE_ACKNOWLEDGED`, `VENUE_REJECTED`, or
   `SUBMISSION_RESULT_UNKNOWN`
7. zero or more typed lifecycle events:
   `ORDER_UPDATE_OBSERVED`, `FILL_OBSERVED`,
   `CANCEL_OBSERVED`, or `EXIT_UPDATE_OBSERVED`
8. `TERMINAL_RECONCILIATION_COMMITTED`
9. if and only if a post-activation filled entry has returned to verified flat:
   `CLOSED_EPISODE_COMMITTED`

The first four events form the pre-submission evidence generation.
`SUBMISSION_ATTEMPTED` is forbidden until that generation is durably committed.
No event may be edited, deleted, reordered, or replaced. Corrections are new
events that reference the prior generation hash and carry a typed correction
reason.

Every generation must:

1. serialize only the allowlisted typed data files into a private temporary
   directory;
2. hash the exact bytes and derive a content-addressed generation identity;
3. `fsync` every data file;
4. atomically place the content-addressed data files;
5. `fsync` the containing directory;
6. write the manifest last as the sole commit point;
7. `fsync` the manifest and containing directory;
8. bind the previous committed manifest hash to form one append-only chain.

Any hash, sequence, parent, schema, permission, ownership, path, duplicate, or
`fsync` failure leaves the generation uncommitted.

### 4. Idempotency and reconciliation

A unique, venue-supported client idempotency key is required for every logical
submission. For a risk-increasing order it must be generated,
collision-checked, persisted in `IDEMPOTENCY_KEY_RESERVED`, and sent in the
venue's supported client-key field. The same logical retry must reuse that key;
a new key must never be minted merely because the result is unknown.

The private internal record must retain the key for recovery, but the dashboard
and aggregate export must not disclose it. A duplicate key, conflicting payload
under one key, or uncertain initial venue result:

- blocks another risk-increasing retry;
- latches the evidence state degraded;
- requires typed venue/order/position reconciliation by that exact client key;
- ends only with `TERMINAL_RECONCILIATION_COMMITTED`.

Terminal reconciliation must bind the final order state, aggregate fills,
position state, and whether the lane is verified flat. No new risk-increasing
entry is permitted while an earlier risk-increasing submission has an unknown
result or incomplete terminal reconciliation.

### 5. Evidence-failure behavior

On an evidence write, hash, `fsync`, permission, ownership, disk-space,
sequence, schema, duplicate, or reconciliation failure:

- block every new entry and every other risk-increasing submission;
- latch `EVIDENCE_DEGRADED` plus `ENTRY_BLOCK`, placing the lane in exit-only
  mode;
- do not auto-clear the latch on process restart or on the next successful
  write;
- preserve the failed/uncommitted material for diagnosis without treating it
  as committed evidence;
- require a deterministic reconciliation and an operator-reviewed recovery
  record before new exposure can resume.

**Evidence failure must never block a verified risk-reducing sell/exit,
protective-stop create/replace/cleanup, cancel, kill-switch action, or
reconciliation.** Those actions retain priority even when no evidence write is
possible; the sink may observe but may not authorize them. If their evidence
cannot be written synchronously, allow the risk reduction, retain a typed
outage marker when storage recovers, reconcile against the venue, and
permanently exclude the episode from complete-cohort disclosure.

### 6. Sanitization and storage

Stage B evidence uses strict typed schemas and deny-by-default serialization.
It must not persist or project:

- raw venue order, execution, account, or wallet identifiers;
- raw signal references or signal payloads;
- wallet addresses, balances, post-order balances, or portfolio snapshots;
- action strings, execution notes, rule text, exception text, request/response
  bodies, URLs, headers, or arbitrary/free text;
- credentials, tokens, keys, secrets, environment dumps, or process arguments;
- raw venue error messages.

Where correlation is necessary, the owning adapter must emit a bounded opaque
alias produced with operator-user-owned private installation material. D-115's
root-owned trust boundary is specific to Phase 2b and must not be extended to
this demo-evidence design. The raw identifier and private material must not
enter the evidence process, repository, dashboard, logs, or exports. Venue
errors must map to a reviewed enum plus a non-sensitive numeric/status code.

The private evidence root and every parent created for it must be `0700`; every
evidence file must be `0600`. Symlinks, unexpected hard links, ownership drift,
permission drift, unexpected files, and path escapes fail closed for new
exposure.

The currently observed legacy raw demo-lane `0755` directory and `0644` file
modes must be hardened to `0700`/`0600` before activation. Mode hardening must
be independently verified and must not alter evidence content.

The dashboard projection must be separately reviewed before activation. It may
show only allowlisted status and completed aggregate fields. It must redact all
raw identifiers and signals and must never read the private evidence files
directly through a static-file route.

### 7. Fixed aggregate-disclosure rule

Demo evidence is diagnostic only. There are no individual-trade disclosures.
The only performance disclosure unit is a fixed, non-overlapping cohort of
**exactly 30 eligible closed episodes**.

An eligible episode:

- begins at the first positive fill of a fully evidenced, post-activation entry;
- belongs to one immutable strategy version, venue-demo context, cost model,
  and risk-policy version;
- ends only at `CLOSED_EPISODE_COMMITTED` after terminal reconciliation verifies
  exact entry and exit quantities and prices, exact quote-currency cashflows,
  exact fee amounts and fee currencies, terminal position state, terminal
  protective-stop state, and a fully reconciled flat position;
- derives no outcome from wallet balance, rounded balance delta, mark-to-market
  estimate, or missing fill;
- has no evidence outage, chain gap, legacy component, unresolved order,
  sanitizer violation, or reconciliation exception.

An internal episode ordinal is assigned at the first positive fill, before its
outcome is known. Cohort 1 is ordinals 1–30, cohort 2 is 31–60, and so on.
Cohorts never overlap. An episode cannot be dropped, replaced, moved, or pooled
with another version after its ordinal is assigned. A strategy, cost-model, or
risk-policy version change starts a separate cohort series; it does not finish
or refill an earlier series.

Until all 30 assigned episodes are eligible, closed, and terminally reconciled,
the public/reporting aggregate is `null`. For example, at 29:

```json
{"closed_episode_count": 29, "aggregate": null}
```

Internally, progress may be represented only as a bounded readiness count; no
outcomes may be disclosed. When a cohort is complete, a read-only projection
may disclose only its closed/positive/negative/flat episode counts and exact
cohort totals for entry quote cashflow, exit quote cashflow, gross result, fees
by currency, and net result after costs. Episode 30 releases cohort 1; episode
31 belongs to cohort 2 and cannot change cohort 1. The projection must not
disclose individual rows, identifiers, timestamps, assets if they identify an
episode, best/worst episode, loss or win streak, equity curves, cumulative
curves, charts reconstructing a path, or selectively chosen subgroups.

The initial `PARTIAL_LEGACY_OPEN` Stage A material is never eligible for a
cohort.

### 8. Learning and promotion boundary

Stage B must not:

- validate or promote a strategy;
- change a strategy, parameter, threshold, risk limit, or cohort definition;
- select a winner or stop a cohort because outcomes look good or bad;
- learn from, react to, or “rescue” an individual win or loss;
- bypass existing validation, admission, holdout, prospective, or independent
  review gates.

Any proposed improvement is a new, immutable strategy or policy version. It
requires a preregistered hypothesis, fixed data and trial budget, hierarchy-wide
multiple-testing accounting, unchanged risk and validation gates, and untouched
validation evidence. The original version and all failures remain retained.
Demo cohort evidence may motivate a hypothesis; it cannot validate or promote
the new version.

## Gates before implementation

No Stage B source edit may begin until all are true:

- [ ] Operator selects Option A or B using the exact wording below.
- [ ] A bounded design identifies every source, test, governance, manifest, and
      runtime path that would change.
- [ ] The design proves the risk-reducing bypass cannot be blocked by evidence
      failure.
- [ ] The exact typed event schemas, sequence machine, storage commit protocol,
      idempotency semantics, sanitizer allowlist, dashboard projection, and
      rollback behavior receive independent security review.
- [ ] A fresh, one-time
      **`STAGE-B-DEMO-EVIDENCE-ONLY` integrity/decision-log exception** is
      explicitly authorized. It must name every manifest-listed file to be
      edited, permit only the existing corresponding hash rows and required
      package-version line to change, require a `PACKAGE_CHANGELOG.md` entry in
      the same change, and permit the exact `DECISION_LOG.md` entry and its hash
      reconciliation. It may add or remove no manifest row and grants no
      continuing authority. No other `IMMUTABLE_PATHS` edit is permitted.
- [ ] The D-115 and D-116 one-time integrity exceptions are acknowledged as
      exhausted; neither confers Stage B authority.
- [ ] The implementation scope remains fake-money venue demo only with
      execution authority `NONE`.

The implementing agent cannot provide the required independent security
review.

## Gates before activation

Implementation approval is not activation approval. Activation additionally
requires:

- [ ] Focused unit, property, fault-injection, crash/replay, duplicate,
      reconciliation, permission, sanitizer, and dashboard-redaction tests
      pass.
- [ ] `make check` passes with no concurrent pytest suite.
- [ ] Package manifest hashes and `PACKAGE_CHANGELOG.md` are reconciled in the
      same reviewed change where required.
- [ ] Independent security review binds the exact committed source, tests,
      schemas, installed files, configuration, and hashes.
- [ ] Legacy raw demo-lane directories/files are verified `0700`/`0600`.
- [ ] Private evidence parents/directories/files are verified `0700`/`0600`.
- [ ] Dashboard projection is verified allowlist-only and cannot expose private
      files or reconstruct individual episodes.
- [ ] Pre-activation backup/rollback identities and the last good evidence-chain
      head are recorded.
- [ ] The demo lane is verified flat with no unresolved submission or order;
      this activation gate is mandatory.
- [ ] A controlled restart window is explicitly approved.
- [ ] Post-restart smoke checks prove fake-money mode, protective risk controls,
      idempotent replay, entry fail-closed behavior, risk-reducing bypass, and
      execution authority `NONE`.

## Exact operator approval wording

To authorize Option A implementation and review, but not activation, the
operator must provide this exact statement:

> I approve Option A, full evidence-first Stage B, for implementation and
> testing in the fake-money demo lane only under the 2026-07-23 Stage B
> demo-evidence security decision packet. I do not authorize activation,
> restart, live trading, real money, strategy approval, promotion, auto-tuning,
> or any authority beyond NONE. Before edits, provide the exact proposed
> STAGE-B-DEMO-EVIDENCE-ONLY integrity and decision-log exception scope for my
> separate approval.

To select Option B instead:

> I select Option B, passive partial Stage B, for a bounded design and
> independent security review only. It must remain PASSIVE_PARTIAL, must not
> affect orders, and must not be used for PnL validation, approval, promotion,
> or auto-tuning. This does not authorize implementation, activation, restart,
> live trading, real money, or authority beyond NONE.

To select Option C:

> I select Option C. Continue the existing explicit manual Stage A
> capture-and-import workflow. Do not implement or activate an in-lane evidence
> tap. I understand Stage A cannot report realized PnL.

After Option A is implemented and every activation checklist item is evidenced,
activation still requires this separate statement:

> I approve one controlled activation restart of the independently reviewed
> Option A Stage B build in the fake-money demo lane only. I have reviewed the
> bound commit, installed hashes, security review, rollback identity, file-mode
> hardening, dashboard redaction, and evidence that the lane is flat with no
> unresolved submission or order. All pre-activation history remains
> LEGACY_EXCLUDED. Execution authority remains NONE, and this approval grants
> no live, real-money, strategy-promotion, or auto-tuning authority.

If the lane is not flat or any submission/order remains unresolved, this
activation statement is inapplicable and activation remains a `NO-GO`.

## Rollback plan

Rollback is designed before activation and is tested against the exact build.

1. Record the prior reviewed build identity, configuration identity, evidence
   chain head, service start target, and file permissions.
2. On a Stage B fault, first latch `EVIDENCE_DEGRADED` and block new
   risk-increasing submissions.
3. Do not interrupt or remove protective stops, exits, cancels, or
   reconciliation. If exposure exists, keep the minimum order-path components
   needed to reduce risk until the venue-demo position is verified flat.
4. Preserve all committed and uncommitted evidence; never delete, rewrite, or
   truncate it to make rollback pass.
5. Reconcile all uncertain submissions and venue-demo state.
6. Restore the prior reviewed source/configuration only through the approved
   Makefile service target and a separately approved restart window.
7. Reverify fake-money mode, protective controls, no unresolved orders,
   dashboard redaction, permissions, prior-chain readability, and execution
   authority `NONE`.
8. Append a typed rollback/recovery record after storage is healthy. Do not
   merge pre-fault and post-rollback evidence into a complete cohort if the
   chain had an outage.
9. Require independent incident review before any later Stage B reactivation.

Immediate rollback triggers include any credential/raw-ID exposure, dashboard
leak, permission drift, hash/sequence divergence, failure to block a new entry
under degraded evidence, any obstruction of a risk-reducing action, duplicate
submission ambiguity, unreconciled restart state, or departure from fake-money
mode.

## Acceptance decision

Option A is the only option that can eventually support complete,
post-activation aggregate demo diagnostics. It is also the highest-risk option
because it sits at the order-path boundary. The independent architecture
assessment is **conditional design GO / activation NO-GO**. Approve Option A
for bounded design/implementation only after the separate integrity exception
and independent review path are in place; do not authorize activation yet.

Known unknowns that implementation design must resolve include the exact owning
module, venue-demo reconciliation semantics, restart choreography,
operator-user-owned private installation-material lifecycle, and exact
manifest-listed dependency surface. This packet does not invent those facts.
