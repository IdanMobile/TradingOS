# Deterministic Automation Adoption and Integrity-Exception Proposal

Date: 2026-07-23
Status: **PROPOSED / NOT APPROVED / DOCUMENTATION ONLY**
Execution authority: **`NONE`**
Proposed adoption release: **v8.147**, valid only after Stage B closes exactly as
v8.146 and records D-117 as the immediately preceding decision. Any Stage B
renumbering or different resolution invalidates this packet and requires a newly
numbered, separately approved automation packet.

## 1. Purpose and controlling sources

**Fixed predecessor condition:** Stage B must close exactly as v8.146, D-117 must be its decision and the immediately preceding decision, or this packet expires unexercised and must be replaced by a newly numbered, separately approved automation packet.

This packet defines the exact one-time documentation and integrity exception that
must be approved before Automation Phases 1–5 in
`docs/supervisor/DETERMINISTIC_AUTOMATION_AI_ESCALATION_ONLY_PLAN_2026-07-23.md`
become live implementation work.

This packet is frozen to Stage B closing exactly as v8.146 and recording D-117
as the immediately preceding decision. Any Stage B renumbering or different
resolution invalidates this packet; it cannot be amended or reused and must be
replaced by a newly numbered, separately approved automation packet.

It is subordinate to:

- `PROJECT_STATE.md` and `DECISION_LOG.md`;
- every frozen protocol under `research/`;
- `PACKAGE_INTEGRITY_MANIFEST.md` and
  `src/tios/ops/self_modification.py::IMMUTABLE_PATHS`;
- the Stage B packet and its separate v8.146 exception;
- `todos/21_deterministic_automation.md`.

This packet grants nothing by existing. Initiative 21 remains
`PROPOSED / UNINDEXED / HUMAN-GATED` until the exact approval in §8 is supplied
and the v8.147 reconciliation passes.

## 2. Verified pre-adoption baseline

**Fixed predecessor condition:** Stage B must close exactly as v8.146, D-117 must be its decision and the immediately preceding decision, or this packet expires unexercised and must be replaced by a newly numbered, separately approved automation packet.

At preparation time:

- `PACKAGE_CHANGELOG.md` ends at v8.145;
- no v8.146 or v8.147 changelog heading exists;
- v8.146 is reserved exclusively by the pending Stage B packet and must close
  with D-117;
- only after that exact v8.146/D-117 predecessor exists is v8.147 the next free
  version available for automation adoption;
- `PACKAGE_INTEGRITY_MANIFEST.md` is at v8.134 and lists the following exact
  adoption targets once each:

| Existing manifest path | Current row occurrences | Adoption treatment |
|---|---:|---|
| `TODO.md` | 1 | rehash the one existing row |
| `docs/architecture/AD.md` | 1 | rehash the one existing row |
| `docs/traceability/TRACEABILITY_MATRIX.md` | 1 | rehash the one existing row |
| `PROJECT_STATE.md` | 1 | rehash the one existing row |
| `DECISION_LOG.md` | 1 | rehash the one existing row |

`todos/21_deterministic_automation.md` currently has zero manifest rows. The
proposed exception adds exactly one row for that file after its adoption edits.
No manifest row is proposed for this packet or for the broader supervisor plan.

Before applying the exception, the implementer must recheck the changelog,
decision log, and manifest. Stage B must have closed exactly as v8.146, D-117
must be its decision and the immediately preceding decision, v8.147 must remain
free, and every row count must match §2. If any condition differs, this packet
expires unexercised. Prepare a newly numbered, separately approved automation
packet; never amend, reuse, or slide this approval to another predecessor,
decision, or version.

## 3. Exact v8.147 adoption edits

**Fixed predecessor condition:** Stage B must close exactly as v8.146, D-117 must be its decision and the immediately preceding decision, or this packet expires unexercised and must be replaced by a newly numbered, separately approved automation packet.

This packet is valid only after Stage B closes exactly as v8.146 and records
D-117 as the immediately preceding decision. Any Stage B renumbering or
different resolution requires a newly numbered, separately approved automation
packet. Under that fixed predecessor, the v8.147 change is
documentation/governance adoption only and may make exactly these semantic
edits.

### 3.1 `TODO.md` — one existing manifest row

1. Add Initiative 21 to the initiative index:
   `todos/21_deterministic_automation.md`, stage `S2 bounded operations`,
   purpose `deterministic automation with AI escalation only`, critical path
   `yes for unattended governed operations`.
2. Add the dependency order exactly as retained in the task file:
   `T-021-01 → {T-021-06, T-021-02} → T-021-03 →
   {T-021-05, T-021-04} → T-021-08 → T-021-07`.
3. State that T-021-09 is separately Stage-B-gated and that T-021-10 covers only
   the enabled bounded slice.
4. State that adoption authorizes implementation and testing of Phases 1–5 only,
   default-disabled and shadow-first. It does not authorize runtime activation,
   an AI call, demo control, a research campaign, or an order.

### 3.2 `todos/21_deterministic_automation.md` — one new manifest row

1. Change the initiative status from `PROPOSED / UNINDEXED` to
   `ADOPTED / INDEXED / IMPLEMENTATION AUTHORIZED FOR PHASES 1–5 ONLY`.
2. Change T-021-01 through T-021-06 and T-021-08 from
   `PROPOSED / UNINDEXED / HUMAN-GATED` to `TODO / AUTHORIZED FOR
   DEFAULT-DISABLED IMPLEMENTATION AND TESTING`.
3. Leave T-021-07 as `HUMAN-GATED / NOT AUTHORIZED` because even a zero-call AI
   proposal path is Phase 6.
4. Leave T-021-09 as `HUMAN-GATED / NOT AUTHORIZED` because it depends on
   separately approved, implemented, reviewed, activated, and completed Stage B
   aggregate evidence.
5. Leave T-021-10 `BLOCKED` until the enabled Phase 1–5 slice is independently
   reviewed and ready for the 24-hour and seven-day soaks.
6. Replace requirement references with the exact REQ-059 through REQ-062 mapping
   in §3.4 while retaining REQ-044, REQ-046, and REQ-056 as predecessor
   traceability where applicable.

### 3.3 `docs/architecture/AD.md` — one existing manifest row

1. Add to §H that routine operation is deterministic and has no external-AI call
   path by default; AI output is proposal-only and cannot mutate evidence,
   protocol, threshold, schedule, strategy, promotion, demo control, venue,
   credential, authority, or order state.
2. Add to §S the typed
   `NOOP | RETRY_AT | ENQUEUE_FIXED_JOB | PARK | ESCALATE | HALT` planner,
   stable escalation identity, append-only outbox, fixed-handler-only dispatch,
   single-instance cycle/maintenance locks, and default-disabled shadow rollout.
3. Add to §AD the deny-unknown retry/failure rule: closed families, protected
   outcomes, exhausted work, missing external authority, and unknown states may
   not be rescued by retry.
4. Add architecture decision AD-18:

   > Deterministic automation with external AI disabled by default; typed
   > planner, fixed handlers, append-only escalation, proposal-only AI; no demo,
   > order, promotion, or authority effects.

   Status is `APPROVED FOR DEFAULT-DISABLED PHASES 1–5 IMPLEMENTATION ONLY`;
   evidence is the automation plan plus the v8.147/D-118 decision; alternatives
   rejected are free-form agent dispatch, provider-first operation, a general
   broker/scheduler, and demo auto-restart; reverify before any runtime enablement
   or provider budget.

### 3.4 `docs/traceability/TRACEABILITY_MATRIX.md` — one existing manifest row

Add four rows after REQ-058:

| REQ | Requirement | Architecture / predecessor | TODO tasks | Required verification | Gate/evidence |
|---|---|---|---|---|---|
| 059 | deterministic automation contract, retry policy, durable cycle state, and planner | AD §H/§S/§AD, AD-18; REQ-056 | T-021-01, T-021-02, T-021-03, T-021-06 | contract/property, failure injection, concurrency, crash recovery, protected-state rejection | Phase-3 shadow review and focused-test evidence |
| 060 | one fixed read-only job, append-only escalation outbox, and deny-unknown maintenance | AD-10/AD-18; REQ-056 | T-021-04, T-021-05, T-021-08 | fixed-dispatch, idempotency, lease/recovery, security, single-test-lock integration | Phase-5 default-disabled review, receipts, outbox, and gate logs |
| 061 | zero-call AI boundary and bounded efficiency proof | AD-12/AD-18; REQ-044/REQ-046 | T-021-07, T-021-10 | AI evaluation, redaction/security, 24-hour and seven-day soak | separate Phase-6 authorization; zero calls and USD 0.00 by default |
| 062 | read-only consumption of a complete governed Stage B aggregate | AD §W/§T/AD-18; separate Stage B decision | T-021-09 | contract, provenance, complete-cohort, redaction, replay, zero Stage B writes | separate Stage B activation/aggregate/review gates |

Also extend the reverse-check summary to state that Initiative 21 has no orphan
task or untraced architecture component and that REQ-061/062 do not authorize
their gated runtime work.

### 3.5 `PROJECT_STATE.md` — one existing manifest row

1. Advance only the package-state description to v8.147 after the reconciliation
   has passed.
2. Record Initiative 21 as adopted and indexed, with Phase 0 documentation
   complete and Phases 1–5 authorized only for default-disabled implementation
   and testing.
3. Record Phases 6–8, T-021-07, T-021-09, T-021-10, provider calls, Stage B
   consumption, and all runtime activation as not authorized or separately
   gated.
4. Add the implementation sequence and independent-review gates to `OPEN ITEMS`.
5. Preserve the current facts that all seven searched strategy families are
   closed with zero passes, protected review dates remain binding, and execution
   authority is `NONE`.

### 3.6 `DECISION_LOG.md` — one existing manifest row

After Stage B closes exactly as v8.146 and records D-117 as the immediately
preceding decision, append D-118:

- approve Initiative 21 documentation adoption and Phases 1–5 implementation and
  testing only;
- freeze external-AI calls/cost at zero;
- freeze fixed-handler, deny-unknown, no-demo-control, no-order, no-authority,
  shadow-first boundaries;
- record the exact v8.147 manifest exception and its expiry;
- state that Phases 6–8 and any activation require separate decisions.

If Stage B is renumbered or resolved differently, or D-117 is not its decision
and the decision immediately preceding adoption, this packet expires
unexercised. Do not update or reuse it; prepare a newly numbered, separately
approved automation packet.

### 3.7 `PACKAGE_INTEGRITY_MANIFEST.md` and `PACKAGE_CHANGELOG.md`

For v8.147 only:

1. change the manifest package-version line to identify the v8.147 automation
   adoption and D-118;
2. replace the digest in exactly the five existing rows listed in §2;
3. add exactly one row for `todos/21_deterministic_automation.md`, placed
   immediately after the existing `TODO.md` row in the planning-system table;
4. do not add, remove, reorder, or edit any other row;
5. add one v8.147 changelog entry in the same change naming the six final row
   occurrences, the approval boundary, tests, independent review, and authority
   `NONE`.

This proposal does not modify the manifest or changelog.

## 4. Version and dependency sequence

**Fixed predecessor condition:** Stage B must close exactly as v8.146, D-117 must be its decision and the immediately preceding decision, or this packet expires unexercised and must be replaced by a newly numbered, separately approved automation packet.

This packet is valid only for the exact v8.146 Stage B reconciliation with D-117
as its decision and the immediately preceding decision. Any Stage B renumbering
or different resolution invalidates this packet and requires a newly numbered,
separately approved automation packet. Under that fixed predecessor, the proposed
release sequence is exact:

| Version | Scope | Required terminal state |
|---|---|---|
| v8.146 | Stage B implementation package only, under its separate two approvals | implementation reviewed; `NOT_ACTIVATED`; authority `NONE` |
| v8.147 | Initiative 21 documentation adoption and integrity reconciliation only | six manifest row occurrences correct; `make check` green; D-118 recorded |
| v8.148 | Phase 1: contracts | default-disabled, focused tests and review green |
| v8.149 | Phase 2: retry policy and durable store | no dispatch; crash/concurrency review green |
| v8.150 | Phase 3: planner | shadow decisions only; zero effects |
| v8.151 | Phase 4A/4B: fixed read-only job and outbox | handler unscheduled; outbox append-only; operator CLI only |
| v8.152 | Phase 5: dispatcher and maintenance coordinator | default-disabled/shadow; manual verification only |

Each phase waits for its predecessor's required terminal state. The two Phase 2
components may be developed in parallel but are accepted together. Phase 4A and
4B may be developed in parallel but begin only after Phase 3 shadow review.

If v8.147 is consumed, this packet expires and requires a newly numbered,
separately approved automation packet. If only a later v8.148–v8.152 slot is
consumed after v8.147 closes successfully, stop and record a new phase sequence
in a separate approved changelog/decision update. Do not reuse or broaden a
prior integrity exception. Later source-only releases do not gain permission to
edit manifest-listed files merely because a version appears in this table.

## 5. Later Phase 1–5 scope recorded by adoption

The v8.147 exception permits no source implementation. Its exact semantic edits
record D-118 and the later Phase 1–5 boundary. Only after the v8.147
documentation reconciliation passes its terminal gates may the separate
v8.148–v8.152 releases implement the following scope from the controlling
automation plan:

- new typed automation contracts and tests;
- deterministic retry policy and tests;
- single-instance durable cycle state and bounded orchestrator integration;
- deterministic planner in shadow mode;
- one exact read-only `DATA_QUALITY` handler:
  `VERIFY_SHORTFRAME_SNAPSHOT_V1` with payload
  `{"contract_id":"VERIFY_SHORTFRAME_SNAPSHOT_V1"}`;
- append-only escalation outbox and fixed operator acknowledgement/resolution CLI;
- deny-unknown dispatcher and single-lock deterministic maintenance coordinator;
- focused tests, sequential repository gates, evidence, and independent review.

Only fixed in-process functions or fixed argv already named in the plan may be
used. No payload may supply a command, path, URL, module, provider, plugin,
strategy, venue, credential, or executable text.

## 6. Explicitly prohibited scope

This proposal and the proposed approval do **not** authorize:

- any external-AI/provider call, nonzero call budget, or nonzero cost budget;
- Phase 6, 7, or 8, T-021-07, T-021-09, or T-021-10 execution;
- AI auto-apply, self-review acceptance, machine verdict, or state mutation;
- demo-lane start, stop, restart, action, configuration, credential, order,
  cancellation, risk-limit change, or wallet/account access;
- paper, limited-live, live, real-money, venue, promotion, admission, or strategy
  approval authority;
- any campaign start, family rescue, retune, closed-family retry, or trial-budget
  change;
- any read of prospective, holdout, or sealed outcomes before their protocol
  gates, including when a calendar date arrives without separate authorization;
- Stage B capture, mutation, activation, aggregate consumption, or writes;
- new dashboard mutation routes or controls;
- a generic broker, scheduler, plugin interface, shell executor, or distributed
  service;
- an edit to `Makefile`, `src/tios/ops/self_modification.py`, any other
  `IMMUTABLE_PATHS` entry, or any manifest-listed file outside the exact v8.147
  rows;
- any path under `artifacts/holdout/` or `artifacts/sealed/`;
- concurrent pytest suites or representing `make check` as `make check-full`;
- use of `AUTHORITY_GATED` as execution authority.

The current demo service must remain observationally separate from this
initiative. Automation may report that it is unavailable; it may never control
or restart it.

## 7. Verification, review, shadow rollout, and rollback

### 7.1 v8.147 adoption verification

Run sequentially:

1. pre-edit `git status`; preserve all operator/runtime/data changes;
2. pre-edit strict integrity verification;
3. apply only the §3 inventory;
4. compute final SHA-256 values after every protected edit;
5. assert manifest occurrence counts:
   `TODO.md ×1`, `AD.md ×1`, traceability `×1`, `PROJECT_STATE.md ×1`,
   `DECISION_LOG.md ×1`, and the new Initiative 21 task row `×1`;
6. assert no other manifest row changed;
7. run decision-ID uniqueness, TODO completeness, traceability, immutable-path,
   architecture, and secret tests;
8. run focused documentation/integrity tests sequentially;
9. run `make check` once as the final quality gate;
10. obtain an independent architecture/security review bound to the exact commit,
    diff, six-row inventory, hashes, approval text, and test output.

Any failure stops reconciliation; no partial adoption may be reported as current
state.

### 7.2 Phase rollout

- **Phase 1:** importable contracts only; no orchestrator call site and no
  external effect.
- **Phase 2:** durable state may mirror current observations in an isolated
  shadow root; no dispatch or restart.
- **Phase 3:** compare planner decisions with current operator-visible state;
  decisions are retained as shadow evidence only.
- **Phase 4:** keep the job unscheduled and outbox unconsumed; exercise fixtures
  and explicit manual test invocations only.
- **Phase 5:** keep dispatcher and coordinator default-disabled; first run is
  dry-run/read-only, then a separately reviewed bounded shadow soak. No service
  installation or automatic startup is authorized.

Every phase requires focused tests, `make check`, and independent review before
the next phase. Never run two pytest suites concurrently.

### 7.3 Rollback

Rollback is disable-first and forward-only:

- keep every new runtime flag disabled;
- stop scheduling the fixed handler and stop manual coordinator invocation;
- preserve append-only cycle, job, escalation, and gate evidence;
- never delete, rewrite, or truncate evidence to make rollback appear clean;
- never call `self_modification._revert()` against a dirty operator worktree;
- use an operator-approved known commit or a reviewed forward fix for source
  rollback;
- rerun focused tests and `make check`;
- record rollback identity, reason, affected phase, evidence hashes, and review.

Any malformed state, ambiguous recovery, protected-read suspicion, unexpected
provider call, demo/order effect, or authority expansion requires `HALT`,
preservation of evidence, and human review.

## 8. Exact one-time operator approval language

**Fixed predecessor condition:** Stage B must close exactly as v8.146, D-117 must be its decision and the immediately preceding decision, or this packet expires unexercised and must be replaced by a newly numbered, separately approved automation packet.

The following statement must be supplied verbatim. A general instruction such as
“implement all” does not replace its integrity-bound inventory.

> I approve the v8.147 DETERMINISTIC-AUTOMATION-ADOPTION-ONLY package and
> only the semantic documentation edits enumerated in §§3.1–3.6 of the
> 2026-07-23 Deterministic Automation Adoption and Integrity-Exception
> Proposal. This approval is valid only after Stage B closes exactly as v8.146
> and records D-117 as the immediately preceding decision. I approve a one-time
> integrity exception permitting PACKAGE_INTEGRITY_MANIFEST.md to change only
> its package-version line and exactly six planning-system row operations: rehash
> the one existing row each for TODO.md, docs/architecture/AD.md,
> docs/traceability/TRACEABILITY_MATRIX.md, PROJECT_STATE.md, and
> DECISION_LOG.md, and add exactly one new row for
> todos/21_deterministic_automation.md immediately after TODO.md.
> PACKAGE_CHANGELOG.md must contain the matching v8.147 entry in the same
> change. No source implementation is part of v8.147. No other semantic edit or
> manifest row addition, removal, reorder, or change is authorized. This
> exception expires after the v8.147 reconciliation. I do not authorize external
> AI calls or cost, Phases 6–8, Stage B consumption or mutation, demo control or
> restart, research-family rescue, protected-outcome reads, strategy admission
> or promotion, paper/live/real-money trading, venue or credential access,
> orders, or any authority beyond NONE. If Stage B is renumbered or resolved
> differently, if D-117 is not its decision and the immediately preceding
> decision, or if v8.147 is unavailable, this packet expires unexercised and
> must be replaced by a newly numbered, separately approved automation packet.

## 9. Terminal state of this proposal

This file is a new, non-manifest proposal artifact. It does not edit a protected
file, activate Initiative 21, consume a version, authorize implementation, call
AI, control the demo lane, or create execution authority. Until §8 is supplied
and v8.147 is reconciled successfully, Automation Phases 1–5 remain
human-gated.
