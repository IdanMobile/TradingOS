# Deterministic Automation and AI-Escalation-Only Plan

Date: 2026-07-23
Status: **PROPOSED / DOCUMENTATION ONLY / EXECUTION AUTHORITY `NONE`**
Authority: subordinate to `PROJECT_STATE.md`, `DECISION_LOG.md`, every frozen
protocol under `research/`, and the existing human and integrity gates.

## 1. Outcome

Run the Trading Intelligence OS continuously with **zero external-AI calls by
default**. Deterministic software owns ordinary observation, verification,
scheduling, backtests, evidence capture, risk checks, and known failure
classification. AI is reserved for bounded proposals when the deterministic
system encounters genuinely new ambiguity or when a scheduled evidence cohort is
ready for review.

This plan does not authorize implementation by itself. It does not activate an
AI provider, spend money, restart the demo lane, create an order, change a risk
limit, approve or promote a strategy, read a protected outcome, weaken a gate, or
grant paper/live/real-money authority.

## 2. Verified baseline

The core runtime is already zero-LLM:

- `src/tios/ops/orchestrator.py` has no provider client. It observes deterministic
  project state, writes `SITUATION.json`, appends a summary journal, and halts on
  `ESCALATE`.
- `src/tios/ops/driver.py` runs only allowlisted `scripts/*.py` verifiers through
  fixed argv. It does not run campaign producers or an AI model.
- `src/tios/services/jobs/runner.py` pins `TIOS_AI_MODE=mock`; the supervised jobs
  worker cannot incur provider cost.
- the MVRV and CFTC observers use frozen, keyless rules and attempt at most once
  per UTC day;
- the demo lane is deterministic, fake-money-only, unpromotable, and outside the
  local-service auto-restart set;
- full-demo readiness is a bounded, read-only check;
- real-provider benchmarking is manual, credential-gated evaluation
  infrastructure, not an operational decision path.

The current gaps are not “add AI.” They are:

1. `ACT` observations have no deterministic consumer;
2. no durable typed escalation outbox exists;
3. the jobs queue has no currently useful successful handler;
4. the orchestrator has no single-instance cycle lock or durable cycle identity;
5. unchanged state is journaled every cycle rather than deduplicated;
6. observation and artifact writes are not uniformly atomic;
7. the evidence-producer map applies active prohibitions to every verifier,
   including otherwise safe verification-only nodes;
8. known transient/permanent failures do not share a deterministic retry policy;
9. no optional AI proposal intake exists behind a zero-call budget and a
   deterministic proposal validator;
10. demo win/loss attribution remains Stage B design only and is separately
    approval-gated.

## 3. Non-negotiable architecture

```text
typed retained input
→ deterministic schema, provenance, timing, and authority validation
→ deterministic allowlist and precondition evaluation
├─ exact permitted action
│  → idempotent fixed handler
│  → append-only evidence
└─ unknown / contradiction / missing evidence
   → durable escalation request
   → optional AI proposal, only when separately enabled and budgeted
   → deterministic proposal validation
   → operator or independent-review gate when required
```

### 3.1 Deterministic system owns

- service and process health;
- data and snapshot integrity;
- freshness and staleness checks;
- preregistration and hierarchy-wide trial accounting;
- fixed campaign/backtest execution after lawful admission;
- metric computation and hard-gate verdicts;
- demo risk enforcement, reconciliation, and kill-switch behavior;
- Stage B event capture and exact accounting, if later authorized;
- retry/cooldown/idempotency decisions for known error codes;
- append-only evidence and operator-visible blocker state.

### 3.2 AI may only

- summarize an already-sanitized escalation packet;
- classify a novel failure into a proposed taxonomy extension;
- draft a hypothesis, implementation plan, or patch proposal;
- review a completed, governed aggregate evidence cohort;
- propose a new preregistered strategy family when genuinely new data supports it.

Every AI result is a proposal. It cannot directly mutate evidence, state, a
schedule, a gate, a threshold, a protocol, a strategy version, a demo control, an
approval, a credential, a venue, or an order.

### 3.3 Human or independent review remains mandatory

- external reviewer enrollment, trust, and Phase-2b activation evidence;
- changes to immutable or integrity-manifested constraints;
- risk-limit and capital-limit changes;
- strategy admission/promotion where the retained gate requires a reviewer;
- demo activation beyond already authorized behavior;
- any paper, limited-live, or real-money authority;
- recovery from an ambiguous order or protected-evidence incident.

## 4. External-AI cost policy

The fixed default is:

```json
{
  "external_ai_enabled": false,
  "max_external_calls_per_utc_day": 0,
  "max_external_cost_usd_per_utc_day": "0.00",
  "execution_authority": "NONE"
}
```

A later nonzero budget requires a separate operator decision naming the provider,
configuration, task classes, daily call count, daily cost ceiling, expiry, and
rollback. Provider absence, quota exhaustion, timeout, malformed output, or budget
exhaustion produces `PARK` or `ESCALATE_TO_HUMAN`; it never changes a deterministic
verdict.

The runtime must never send raw frames, raw venue IDs, credentials, private paths,
wallet/account values, raw signals, prospective outcomes, sealed outcomes, or
unbounded logs to an AI provider. Only compact typed evidence references and
sanitized summaries are eligible.

## 5. Phase 0 — documentation discovery — complete

### Allowed APIs and patterns

Copy established patterns rather than inventing new infrastructure:

- `Observation`, `Situation`, `observe()`, and `run_cycle()` from
  `src/tios/ops/orchestrator.py`;
- verifier allowlisting, traversal rejection, timeout, and bounded concurrency
  from `src/tios/ops/driver.py`;
- `JobStore.enqueue()`, `claim()`, `renew_lease()`, `succeed()`, `fail()`,
  `add_schedule()`, and `materialize_due()` from
  `src/tios/services/jobs/store.py`;
- the worker lease/failure lifecycle from
  `src/tios/services/jobs/runner.py`;
- fixed service wrappers and intentional-halt behavior from
  `src/tios/ops/local_services.py`;
- bounded no-follow reads and authenticated process matching from
  `src/tios/ops/demo_readiness.py`;
- content-addressed intent and fail-closed projection from
  `src/tios/services/observations/flow.py`;
- proposal-only validation from
  `src/tios/ai_eval/decision_inspector.py`;
- mock-first provider selection from
  `benchmarks/ai_agent/harness/provider.py`;
- the fast frozen-snapshot verifier only after its independent code review returns
  `GO`.

### APIs that do not exist

Do not assume or call:

- `orchestrator.dispatch()` or `consume_actions()`;
- a generic campaign dispatcher;
- an AI escalation consumer or Task Router;
- a useful successful jobs handler;
- an enqueue/schedule CLI;
- an implemented `CampaignContract`;
- an automatic self-modification call from the orchestrator;
- an authority-bearing demo restart or action API.

### Anti-pattern guards

- no shell or arbitrary command/path payloads;
- no generic plugin or provider execution;
- no automatic demo-lane restart;
- no rescue/retry of a closed strategy family;
- no prospective or sealed outcome read before its protocol gate;
- no AI verdict, self-approval, auto-apply, or auto-promotion;
- no use of `self_modification._revert()` against a dirty operator worktree;
- no new broker, distributed scheduler, microservice, or cloud dependency;
- no concurrent pytest suites;
- no `make check` result represented as `make check-full`;
- no use of `AUTHORITY_GATED` as execution authority.

## 6. Phase 1 — freeze the automation decision contract

### What to implement

Create:

- `src/tios/ops/automation_contracts.py`;
- `tests/test_automation_contracts.py`.

Define exact deny-unknown types:

- `AutomationAction`:
  `NOOP | RETRY_AT | ENQUEUE_FIXED_JOB | PARK | ESCALATE | HALT`;
- `AutomationReason`: fixed reason-code vocabulary, not free-form control;
- `AutomationDecision`: cycle ID, observation digest, action, reason,
  earliest time, fixed handler ID, evidence references, and authority `NONE`;
- `EscalationRequest`: stable content-derived escalation ID over the normalized
  escalation class (not an outbox event ID), first/last observed time, occurrence
  count, sanitized evidence refs, severity, review class, and external-AI
  eligibility;
- `AutomationBudget`: zero-call default, bounded non-negative counts/Decimal cost,
  exact expiry, and operator-decision reference for any nonzero budget.

Canonical JSON must reject duplicate keys, floats, non-finite values, unknown
fields, control characters, unbounded strings/lists, unsafe paths, and any
authority other than `NONE`.

### Documentation references

- `orchestrator.py::Observation` and `Situation`;
- `driver.py::BlockerStatus`;
- `decision_inspector.py::InspectionProposal` and
  `InspectionEvaluation(auto_apply=False)`;
- `intake_external_contracts.py` canonical JSON discipline.

### Verification

- identical input produces byte-identical decision and ID;
- field-order changes do not change identity;
- unknown fields and unknown reason/action codes fail;
- nonzero AI budget without an exact operator decision fails;
- forbidden path, credential, venue, order, promotion, and authority fields fail;
- repeated evidence for the same normalized escalation class retains the same
  escalation ID;
- AI absence does not change the deterministic decision.

### Stop conditions

Stop if the contract needs a protected threshold/protocol edit or if any action
can carry arbitrary argv, Python import, URL, path, or executable text.

## 7. Phase 2 — deterministic retry policy and durable observation

The retry policy and durable store are parallel successors to the contract. Both
must pass before the planner is implemented.

### What to implement

Create the retry policy:

- `src/tios/ops/automation_retry_policy.py`;
- `tests/test_automation_retry_policy.py`.

Freeze exact capability/reason classes, cooldowns, maximum attempts, and terminal
`PARK`, `ESCALATE`, or `HALT` transitions. Unknown classes fail closed. A retry
cannot rescue a closed family, alter a cohort, weaken a protocol, or authorize an
early protected-outcome read.

Modify:

- `src/tios/ops/orchestrator.py`;
- `tests/test_orchestrator.py`.

Create:

- `src/tios/ops/automation_store.py`;
- `tests/test_automation_store.py`.

Add:

1. a single-instance, no-follow orchestrator cycle lock;
2. a content-derived cycle ID over normalized observations excluding observation
   time;
3. atomic, file-synced, directory-synced `SITUATION.json` publication;
4. append-only journal rows only when the normalized state changes, plus a bounded
   periodic liveness checkpoint so freshness remains observable;
5. retained first/last seen and occurrence count for repeated conditions;
6. exact cycle/store recovery after interruption;
7. a read-only snapshot-integrity observation, only after the verifier is
   production-only, offline, write-free, race-safe, and independently `GO`.

### Copy-ready references

- lock and descriptor patterns from the demo lane and jobs store;
- atomic checkpoint/status publication from the prospective observer scripts;
- `orchestrator.py::run_cycle()` composition;
- `demo_readiness.py` bounded read model.

### Verification

- exact retry fixtures cover every allowed capability/reason pair;
- no same-day observer retry occurs unless the frozen policy explicitly permits
  it;
- closed, protected, exhausted, and unknown work never retries;
- two concurrent cycles produce one writer and one deterministic refusal;
- identical observations do not append duplicate state-change events;
- liveness remains fresh without semantic journal spam;
- crash before/after publication recovers without false PASS;
- snapshot failure becomes one exact escalation, never a repair;
- no service restart, order, campaign, AI call, or protected read occurs.

## 8. Phase 3 — deterministic action planner

### What to implement

Create:

- `src/tios/ops/automation_planner.py`;
- `tests/test_automation_planner.py`.

Modify only after focused review:

- `src/tios/ops/orchestrator.py`;
- `tests/test_orchestrator.py`.

Map exact observation/reason combinations to actions:

| Condition | Action |
|---|---|
| all current/pass | `NOOP` |
| known transient source failure with frozen retry rule | `RETRY_AT` |
| fixed safe handler exists and all preconditions pass | `ENQUEUE_FIXED_JOB` |
| missing external data/credential/reviewer/future date | `PARK` |
| novel, contradictory, malformed, or unsafe state | `ESCALATE` |
| constraint, holdout, integrity, or order-ambiguity incident | `HALT` |

The planner never consumes free-form summaries as control. It uses typed domain,
severity, reason code, and evidence state.

### Verification

- full rule table has one result per allowed state;
- no ambiguous fallthrough; unknown always escalates;
- repeated identical input returns the same decision/idempotency key;
- `ACT` finally has a deterministic consumer;
- `ESCALATE` and `HALT` cannot dispatch work;
- protected-date and closed-family fixtures remain parked/prohibited.

## 9. Phase 4A — useful fixed job, without arbitrary dispatch

### What to implement

Do not revive `RESEARCH_LAB_V0`. It is quarantined.

Preserve the existing `JobType.DATA_QUALITY` member and existing SQLite enum/check
values. Do not add a job type and do not run a schema migration. Map
`DATA_QUALITY` exclusively to one read-only successful handler:

- handler ID `VERIFY_SHORTFRAME_SNAPSHOT_V1`;
- exact payload `{"contract_id":"VERIFY_SHORTFRAME_SNAPSHOT_V1"}`;
- calls the production-only verifier;
- stores only its compact receipt or compact failure code;
- idempotency key binds handler ID, frozen manifest pin, and scheduled occurrence.

The version is part of the fixed contract ID. Previously persisted
`DATA_QUALITY` rows remain deserializable without a SQLite enum change, but only
the exact V1 payload is dispatchable. Empty, legacy-arbitrary, extra-field,
unknown-version, command, path, URL, module, provider, strategy, and venue
payloads are retained as rejected jobs; they never fall through to another
handler.

Full-demo readiness is not a jobs handler. It remains a fixed read-only check
owned by the maintenance coordinator in Phase 5.

Potentially modify:

- `src/tios/services/jobs/store.py`;
- `src/tios/services/jobs/runner.py`;
- `src/tios/services/jobs/projection.py`;
- corresponding focused tests and one fixed CLI.

### Verification

- existing serialized `DATA_QUALITY` rows still deserialize without a schema or
  enum change;
- the exact V1 payload routes only to `VERIFY_SHORTFRAME_SNAPSHOT_V1`;
- empty, incompatible, extra-field, and unknown-version payloads are rejected and
  retained without execution;
- duplicate schedule occurrences enqueue one job;
- lease loss and retry do not duplicate evidence;
- every handler uses fixed argv or an in-process pure/read-only API;
- no payload can name a command, path, URL, module, provider, strategy, or venue;
- `TIOS_AI_MODE=mock` remains forced;
- failure produces retained evidence and never fabricates a PASS;
- closed research schedules remain disabled.

### Anti-pattern guards

Do not route MVRV/CFTC through the network-denied jobs worker. Do not split,
restart, backfill, or rescue the managed continuity observer.

## 10. Phase 4B — durable escalation outbox

### What to implement

Create:

- `src/tios/ops/escalation_outbox.py`;
- `tests/test_escalation_outbox.py`;
- `scripts/manage_escalation_outbox.py`;
- `tests/test_manage_escalation_outbox.py`;
- a read-only projection under the existing dashboard API only if separately
  reviewed.

Use an append-only event stream:

- `OPENED`;
- `SEEN_AGAIN`;
- `ACKNOWLEDGED`;
- `RESOLVED`;
- `INVALIDATED`.

State is derived; history is never rewritten. Event identity is content-derived
from a stable `escalation_id` plus event type, the next monotonic per-escalation
sequence, and the exact canonical evidence references. The resulting unique
`outbox_event_id` is distinct from the stable `escalation_id`; recurrence
coalesces under the latter while every event has its own identity. The outbox
stores no secret, raw signal, raw order/venue ID, wallet/account value, or
protected outcome.

Only the fixed operator CLI may append `ACKNOWLEDGED` or `RESOLVED`. Its argv
accepts an exact escalation ID, fixed event verb, and exact evidence reference;
it accepts no arbitrary command, path, URL, module, or executable text. The
dashboard remains read-only and exposes no mutation route.

### Verification

- identical escalations coalesce while occurrence count and last-seen advance;
- every event has a unique evidence-bound `outbox_event_id` and a strictly
  increasing per-escalation sequence;
- materially different evidence creates a new event without changing the stable
  escalation ID when the normalized escalation class is unchanged;
- acknowledgement cannot resolve;
- acknowledgement and resolution require the fixed operator CLI and an exact
  evidence reference;
- malformed/truncated tail recovers fail-closed;
- projection is bounded and contains no write control or dashboard mutation
  endpoint.

## 11. Phase 5 — deterministic dispatch and maintenance cadence

### What to implement

Create only after the planner, outbox, and fixed job handler pass:

- `src/tios/ops/automation_dispatcher.py`;
- `tests/test_automation_dispatcher.py`;
- `scripts/run_deterministic_maintenance_cycle.py`;
- `tests/test_deterministic_maintenance_cycle.py`.

The dispatcher is deny-unknown and accepts only a validated
`AutomationDecision`. `ENQUEUE_FIXED_JOB` may enqueue only the exact
`DATA_QUALITY` / `VERIFY_SHORTFRAME_SNAPSHOT_V1` contract. `ESCALATE` and `HALT`
may append only their exact outbox events and cannot dispatch work. `NOOP`,
`RETRY_AT`, and `PARK` cannot invoke a handler. The dispatcher has no generic
command, path, URL, module, provider, strategy, venue, or plugin interface.

The coordinator holds one test lock and never runs two pytest suites concurrently.
It may:

- run the fast frozen-snapshot verifier on its fixed cadence;
- run `make check` only after a source-state digest changes or the approved maximum
  age expires;
- propose, but not silently enable, a lower-frequency `make check-full` cadence;
- run read-only readiness and integrity verifiers;
- retain duration, exit code, exact gate name, and source digest.

The `Makefile` is immutable. This phase must use existing targets and cannot add or
weaken a gate without an exact operator exception.

### Verification

- concurrent coordinator invocation is refused;
- unchanged source within freshness window performs no test run;
- changed source runs exactly one `make check`;
- `make check` and `make check-full` evidence remain distinct;
- a failed gate halts further mutation and remains visible;
- no demo restart or AI call occurs.

## 12. Phase 6 — optional AI proposal path, still zero-call by default

### What to implement

Create only after Phases 1–5 pass:

- `src/tios/ops/ai_escalation_policy.py`;
- `tests/test_ai_escalation_policy.py`.

The first implementation does **not** call a provider. It:

1. decides deterministically whether an escalation is eligible for optional AI
   review;
2. emits a frozen sanitized request artifact;
3. accepts a separately supplied proposal artifact;
4. validates it through `decision_inspector`-style rules;
5. returns only `PASS_FOR_HUMAN_REVIEW` or `REJECT`.

A future provider worker is a separate decision. It must bind provider/model/prompt
versions, exact task class, timeout, daily call/cost budget, redaction report,
request/response hashes, and cost/latency evidence.

### Verification

- default budget produces zero provider calls;
- eligible request generation is deterministic and byte-identical;
- provider timeout/quota/schema failure leaves the escalation open;
- proposal cannot self-approve or request deployment;
- protected paths, threshold/gate changes, schedule mutations, demo controls,
  strategy promotion, and orders are rejected;
- same-model self-review is insufficient for critical acceptance.

## 13. Phase 7 — read-only governed Stage B aggregate consumption

This phase is gated by the two exact Stage B approvals. Before then it is design
only.

After separately authorized Stage B code has already published a complete,
governed aggregate and a separately reviewed activation permits consumption, this
phase may:

1. open the already-published aggregate read-only with bounded no-follow reads;
2. validate its fixed schema, provenance, redaction statement, publication
   identity, and exact complete-cohort marker;
3. reject raw, partial, mutable, prospective, sealed, or unapproved inputs;
4. append only a new automation outbox event and, when deterministically eligible,
   a new sanitized AI-request artifact;
5. permit a separately supplied AI proposal to enter the proposal-only validation
   path;
6. require a new preregistration and hierarchy-wide trial accounting before any
   proposed hypothesis is tested.

This consumer performs no event/fill/fee/PnL accounting, does not create or amend
Stage B aggregates, and writes zero files in the Stage B inventory. Stage B owns
capture and aggregation; automation owns only its new outbox/request artifacts.
Tests must pin read-only access, complete-cohort rejection boundaries, aggregate
schema/provenance validation, redaction, replay/idempotency, and zero writes to the
Stage B inventory.

The current seven searched families remain closed at 0 passes. This plan does not
rerun, retune, reinterpret, or rescue them. The 2027 holdout/prospective dates remain
binding.

## 14. Phase 8 — soak and acceptance

### 24-hour operational soak

Require:

- exactly one dashboard, orchestrator, jobs worker, and demo lane;
- zero external-AI calls and cost;
- zero duplicate jobs or state-change events;
- no protected outcome reads;
- no order/campaign started by automation;
- fake-money/unpromotable demo boundary intact;
- deterministic snapshot/readiness/integrity checks passing;
- transient/permanent failures classified by exact reason code.

### Seven-day efficiency soak

Retain:

- orchestrator cycles;
- semantic state changes;
- jobs materialized/executed/deduplicated;
- retries/parks/escalations;
- external-AI eligible events;
- actual external-AI calls and cost, expected zero by default;
- manual operator interventions;
- CPU time and disk growth.

Acceptance:

- at least 80% of recurring operational checks complete deterministically;
- unchanged state creates no repeated review request;
- every unknown becomes one bounded escalation;
- no AI result changes a machine verdict or authority;
- `make check` passes;
- full-demo readiness remains operational and honestly gated.

## 15. Rollout and rollback

Roll out one phase at a time:

1. contract;
2. retry policy and durable store in parallel;
3. planner in shadow mode after both predecessors pass;
4. escalation outbox and the one fixed read-only job handler in parallel;
5. deny-unknown dispatch and maintenance coordinator;
6. optional AI proposal artifacts, still with zero provider calls by default;
7. read-only Stage B aggregate consumption only after its separate gates and
   already-published aggregate exist.

Each phase starts default-disabled or shadow-only. Rollback disables the new fixed
handler/consumer and preserves append-only evidence. Never delete or rewrite
history to make rollback look clean.

## 16. Protected documentation reconciliation

The following requested edits are prepared conceptually but are **not authorized
in this plan**:

- add a zero-LLM-default / AI-escalation-only paragraph to `AD.md` §H;
- add the deterministic planner/outbox boundary to `AD.md` §S;
- add `AD-18` to the architecture decision table;
- add Initiative 21 to `TODO.md`;
- update the traceability matrix for Initiative 21 requirements, tasks,
  verification, and authority boundaries;
- optionally add the new task file to the planning-system integrity rows;
- reconcile `PROJECT_STATE.md` and `DECISION_LOG.md` when this becomes live work.

`docs/architecture/AD.md`, `TODO.md`,
`docs/traceability/TRACEABILITY_MATRIX.md` (current manifest-row occurrence
count: `×1`), `PROJECT_STATE.md`, and `DECISION_LOG.md` are manifest-listed.
Here, `×1` is the integrity-manifest row count for that path, not a limit on
textual references. `PACKAGE_INTEGRITY_MANIFEST.md` is immutable. D-115 and D-116
are exhausted. The pending Stage B packet reserves v8.146 and cannot be expanded
or reused.

The safe order is:

1. retain this plan and the unindexed proposed task file as unprotected planning
   artifacts;
2. complete or formally renumber the pending Stage B v8.146 package;
3. request a separate, exact automation-documentation integrity exception for the
   then-next free version, expected no earlier than v8.147;
4. name every existing row occurrence and any explicitly permitted new row;
5. update the changelog and verify all manifest rows in the same change;
6. obtain independent architecture/security review before enabling a runtime
   consumer.

No protected file may be edited merely because this plan exists.

## 17. Exact next execution order

The bounded zero-authority automation path is:

1. retain this plan and `todos/21_deterministic_automation.md` as
   `PROPOSED / UNINDEXED`;
2. obtain the separate protected-document exception with the complete adoption
   inventory;
3. implement the contract;
4. implement the retry policy and durable store in parallel;
5. implement the planner only after both pass;
6. implement the outbox and fixed short-frame job in parallel, with the job alone
   waiting for the production verifier's independent `GO`;
7. implement deny-unknown dispatch and maintenance;
8. implement optional AI request/proposal artifacts with provider calls still
   disabled;
9. run the approved gates and then the 24-hour zero-AI soak.

Independent Phase-2b reviewer sourcing, including the reviewer-key-possession
packet and no-authority handoff, is a parallel external evidence track. It is not
a predecessor to contracts, retry/store, planner, outbox, fixed dispatch, or
maintenance. The Stage B approvals are another separate track and gate only the
read-only aggregate consumer; absent those approvals, Stage B remains untouched.
