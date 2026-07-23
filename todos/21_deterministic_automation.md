# Initiative 21 — Deterministic Automation / AI Escalation Only

Status: **PROPOSED / UNINDEXED**. This file is not live task authority until
`TODO.md`, architecture, traceability, state, and integrity evidence are updated
under an exact operator-approved exception.

Plan:
`docs/supervisor/DETERMINISTIC_AUTOMATION_AI_ESCALATION_ONLY_PLAN_2026-07-23.md`

Global boundaries:

- external AI disabled by default; call and cost budget both zero;
- AI proposals only; no auto-apply, self-approval, promotion, or authority;
- no arbitrary commands, paths, URLs, modules, providers, or dashboard controls;
- no demo auto-restart or order-bearing automation;
- no closed-family rescue or protected outcome read;
- no immutable/manifest edit without an exact exception;
- no concurrent pytest suites.

Stable task IDs are retained. The dependency order is:
`T-021-01 → {T-021-06, T-021-02} → T-021-03 →
{T-021-05, T-021-04} → T-021-08 → T-021-07`. T-021-09 is a separately
gated read-only consumer, and T-021-10 covers only the enabled bounded slice.

## T-021-01 Freeze the automation decision contract

- Status: **PROPOSED / UNINDEXED** — **HUMAN-GATED** pending the protected adoption exception; documentation only; no implementation or authority.
- Purpose: define exact deterministic actions, escalation predicates, forbidden
  effects, and typed outputs.
- Requirement/source: REQ-056 plus REQ-044/046; AD §H/§S;
  D-096/D-100/D-107/D-108.
- Dependencies/blocks: protected documentation exception is separate; no Stage B
  or Phase-2b authority is inherited.
- Actions: implement deny-unknown `AutomationDecision`,
  `EscalationRequest` with a stable normalized-class `escalation_id`, and
  zero-default `AutomationBudget`.
- Outputs: `src/tios/ops/automation_contracts.py`;
  `tests/test_automation_contracts.py`.
- Tests/acceptance: canonical identity; unknown fields/actions fail; arbitrary
  execution data fails; nonzero AI budget needs an exact operator reference;
  authority is always `NONE`.
- Failure: any AI output can change state or any free-form value becomes control.
- Skill/agent: Trading OS supervisor plus independent architecture/security review.
- Complexity: M.

## T-021-02 Add durable single-instance cycle state

- Status: **PROPOSED / UNINDEXED** — **HUMAN-GATED** pending the protected adoption exception; documentation only; no implementation or authority.
- Purpose: prevent duplicate cycles and make state publication crash-safe.
- Requirement/source: REQ-056; AD §R/§S/§AD; D-107.
- Dependencies/blocks: T-021-01; developed and reviewed in parallel with
  T-021-06, both before T-021-03.
- Actions: add no-follow cycle lock, content-derived cycle ID, atomic/fsynced
  situation publication, state-change journal deduplication, bounded liveness
  checkpoints, and recovery.
- Outputs: `src/tios/ops/automation_store.py`;
  `tests/test_automation_store.py`; bounded changes to orchestrator/tests.
- Tests/acceptance: concurrent writer refused; crash recovery; identical states do
  not create duplicate change events; freshness remains valid.
- Failure: false PASS, history rewrite, ambiguous recovery, or service restart.
- Skill/agent: R7.
- Complexity: L.

## T-021-03 Consume ACT through a deterministic planner

- Status: **PROPOSED / UNINDEXED** — **HUMAN-GATED** pending the protected adoption exception; documentation only; no implementation or authority.
- Purpose: turn observation into one exact non-AI action.
- Requirement/source: AD §H/§S; D-100/D-107.
- Dependencies/blocks: T-021-01/02/06.
- Actions: implement `NOOP`, `RETRY_AT`, `ENQUEUE_FIXED_JOB`, `PARK`,
  `ESCALATE`, and `HALT` over typed reason codes.
- Outputs: `src/tios/ops/automation_planner.py`;
  `tests/test_automation_planner.py`; orchestrator integration in shadow mode.
- Tests/acceptance: complete rule table; unknown always escalates; repeated input
  is idempotent; protected/future work remains prohibited.
- Failure: free-form summary drives control or an escalation dispatches work.
- Skill/agent: R7 plus risk/security review.
- Complexity: L.

## T-021-04 Productize one fixed read-only job

- Status: **PROPOSED / UNINDEXED** — **HUMAN-GATED** pending the protected adoption exception; documentation only; no implementation or authority.
- Purpose: make the supervised jobs worker useful without generic dispatch.
- Requirement/source: REQ-056; AD-10; D-108.
- Dependencies/blocks: short-frame verifier independent `GO`;
  T-021-01/02/03/06. It may proceed in parallel with T-021-05.
- Actions: preserve the existing `JobType.DATA_QUALITY` member and SQLite
  enum/check values; map `DATA_QUALITY` exclusively to handler
  `VERIFY_SHORTFRAME_SNAPSHOT_V1` with exact payload
  `{"contract_id":"VERIFY_SHORTFRAME_SNAPSHOT_V1"}`, fixed
  occurrence/idempotency identity, and compact receipt. Full-demo readiness stays
  out of jobs and remains a fixed read-only maintenance check.
- Outputs: bounded job store/runner/projection changes and focused tests.
- Tests/acceptance: existing serialized `DATA_QUALITY` rows deserialize without
  schema/enum changes; exact V1 payload routes only to the fixed handler; empty,
  incompatible, extra-field, and unknown-version payloads are rejected and
  retained; duplicate occurrence produces one job; lease/retry safe;
  `TIOS_AI_MODE=mock`; failure retained.
- Failure: legacy research revival, network/provider access, mutable path, or fake
  PASS.
- Skill/agent: R7.
- Complexity: M.

## T-021-05 Build the append-only escalation outbox

- Status: **PROPOSED / UNINDEXED** — **HUMAN-GATED** pending the protected adoption exception; documentation only; no implementation or authority.
- Purpose: coalesce recurring known issues and retain novel issues once.
- Requirement/source: AD §R/§AD; D-107.
- Dependencies/blocks: T-021-01/02/03/06. It may proceed in parallel with
  T-021-04.
- Actions: implement a stable content-derived `escalation_id` and a unique
  `outbox_event_id` bound to that escalation ID, fixed event type, next monotonic
  per-escalation sequence, and exact canonical evidence references; append only
  `OPENED/SEEN_AGAIN/ACKNOWLEDGED/RESOLVED/INVALIDATED` events. Only a fixed
  operator CLI may append `ACKNOWLEDGED` or `RESOLVED`; the dashboard stays
  read-only.
- Outputs: `src/tios/ops/escalation_outbox.py`;
  `tests/test_escalation_outbox.py`; `scripts/manage_escalation_outbox.py`;
  `tests/test_manage_escalation_outbox.py`.
- Tests/acceptance: repeat coalescing under stable escalation ID; unique
  evidence-bound event ID and monotonic sequence; operator-only acknowledgement
  and exact evidence-bound resolution; no dashboard mutation; truncated-tail
  recovery; bounded sanitized projection.
- Failure: history rewrite, secret/raw-order/raw-signal storage, or acknowledgement
  treated as resolution.
- Skill/agent: R7 plus security review.
- Complexity: L.

## T-021-06 Add deterministic failure and retry policy

- Status: **PROPOSED / UNINDEXED** — **HUMAN-GATED** pending the protected adoption exception; documentation only; no implementation or authority.
- Purpose: distinguish retryable source faults from permanent/prohibited work.
- Requirement/source: AD §AD; prospective protocol retry boundaries.
- Dependencies/blocks: T-021-01; developed and reviewed in parallel with
  T-021-02, both before T-021-03.
- Actions: freeze exact reason classes, cooldowns, maximum attempts, and
  park/escalate transitions per capability.
- Outputs: `src/tios/ops/automation_retry_policy.py`;
  `tests/test_automation_retry_policy.py`.
- Tests/acceptance: no same-day observer retry unless the frozen policy permits;
  closed/protected work never retries; unknown halts/escalates.
- Failure: retry rescues a failed result, changes a cohort, or reads early outcomes.
- Skill/agent: R7 plus quant/risk review.
- Complexity: M.

## T-021-07 Add zero-call AI proposal intake

- Status: **PROPOSED / UNINDEXED** — **HUMAN-GATED** pending the protected adoption exception; documentation only; no implementation or authority.
- Purpose: allow bounded AI help without putting AI in the operating control loop.
- Requirement/source: AD §H/§T; `decision_inspector` proposal-only contract.
- Dependencies/blocks: T-021-01/03/05/08; real provider remains separately gated.
- Actions: create sanitized frozen request artifacts, validate separately supplied
  proposals, return only `PASS_FOR_HUMAN_REVIEW` or `REJECT`.
- Outputs: `src/tios/ops/ai_escalation_policy.py`;
  `tests/test_ai_escalation_policy.py`.
- Tests/acceptance: zero provider calls by default; timeout/quota/malformed proposal
  leaves escalation open; protected/gate/deployment changes rejected.
- Failure: auto-apply, provider default-on, missing cost ceiling, or AI verdict.
- Skill/agent: AI evaluator plus independent security review.
- Complexity: M.

## T-021-08 Coordinate deterministic maintenance

- Status: **PROPOSED / UNINDEXED** — **HUMAN-GATED** pending the protected adoption exception; documentation only; no implementation or authority.
- Purpose: automate repeated checks without repeated AI sessions or concurrent test
  suites, using deny-unknown fixed dispatch.
- Requirement/source: D-108; testing master plan §5.
- Dependencies/blocks: T-021-02/03/04/05/06; Makefile remains immutable.
- Actions: add deny-unknown dispatch from validated decisions to only the exact
  fixed job or append-only outbox; add a fixed coordinator lock,
  source-digest/freshness-triggered `make check`, fixed
  snapshot/readiness/integrity checks, and separately proposed slow-gate cadence.
- Outputs: `src/tios/ops/automation_dispatcher.py`;
  `tests/test_automation_dispatcher.py`;
  `scripts/run_deterministic_maintenance_cycle.py`;
  `tests/test_deterministic_maintenance_cycle.py`.
- Tests/acceptance: unchanged source skips test run; changed source runs one
  `make check`; gate identities stay distinct; failures halt mutation.
- Failure: concurrent pytest, gate weakening, hidden restart, or AI call.
- Skill/agent: R7.
- Complexity: L.

## T-021-09 Connect governed demo learning

- Status: **PROPOSED / UNINDEXED** — **HUMAN-GATED** pending the protected adoption exception; documentation only; no implementation or authority.
- Purpose: consume an already-published governed Stage B aggregate read-only
  without AI-per-frame or AI-per-trade usage.
- Requirement/source: Stage B security/scope packet.
- Dependencies/blocks: T-021-01/05/07; both exact Stage B approvals, v8.146
  exception, implementation review, separate activation, and an already-published
  complete aggregate. These gates apply only to this task.
- Actions: bounded no-follow read of the already-published aggregate; validate
  fixed schema, provenance, redaction, publication identity, and complete-cohort
  marker; append only new automation outbox/request artifacts. Perform no
  event/fill/fee/PnL accounting and no Stage B mutation.
- Outputs: only new automation outbox/request artifacts; zero writes to the
  separately approved Stage B inventory.
- Tests/acceptance: raw/partial/mutable/unapproved aggregate rejection;
  complete-cohort and provenance validation; replay/idempotency; redaction; zero
  writes to the Stage B inventory; no promotion/auto-tune.
- Failure: early/partial cohort analysis, raw value exposure, order origination, or
  evidence failure blocking first risk reduction.
- Skill/agent: quant, risk/execution, architecture/security reviewers.
- Complexity: XL.

## T-021-10 Prove zero-AI operation

- Status: **PROPOSED / UNINDEXED** — **HUMAN-GATED** pending the protected adoption exception; documentation only; no implementation or authority.
- Purpose: demonstrate that normal operation does not consume external AI usage.
- Requirement/source: this plan §14; AD §AF/§AC.
- Dependencies/blocks: T-021-01 through the enabled bounded slice.
- Actions: 24-hour and seven-day soaks; retain cycles, state changes, jobs,
  escalations, calls/cost, interventions, CPU time, and disk growth.
- Outputs: machine-readable soak evidence plus report projection.
- Tests/acceptance: zero external calls/cost by default; no duplicates/protected
  reads/order starts; ≥80% recurring checks deterministic; `make check` and
  readiness pass.
- Failure: hidden provider call, repeated unchanged escalation, authority expansion,
  or unverifiable cost.
- Skill/agent: R7 plus independent review.
- Complexity: M.

## Protected adoption gate

Before this initiative becomes canonical, obtain a separate one-time integrity
exception for the then-next free version, expected no earlier than v8.147. The
pending Stage B v8.146 exception is not reusable. The adoption package must name
the exact manifest rows for `TODO.md`, `docs/architecture/AD.md`,
`docs/traceability/TRACEABILITY_MATRIX.md` (current manifest-row occurrence
count: `×1`), and any state or decision-log reconciliation, plus any explicitly
authorized new manifest row for this file, and include `PACKAGE_CHANGELOG.md` in
the same change. Here, `×1` is the integrity-manifest row count for the
traceability path, not a limit on textual references.
