# Session handoff — deterministic automation / AI escalation only — 2026-07-23

## Outcome

Prepared a full implementation plan and proposed Initiative 21 for running normal
Trading OS operations with zero external-AI calls by default.

Added:

- `docs/supervisor/DETERMINISTIC_AUTOMATION_AI_ESCALATION_ONLY_PLAN_2026-07-23.md`;
- `todos/21_deterministic_automation.md`;
- this handoff.

No runtime automation was enabled by these documents.

## Verified facts

- the current orchestrator contains no AI-provider call;
- the jobs worker forces `TIOS_AI_MODE=mock`;
- current observers, readiness, demo risk, trial accounting, and backtest gates are
  deterministic;
- `ACT` has no consumer and the jobs worker has no useful successful handler;
- no escalation outbox or provider-backed operational Task Router exists;
- real-provider benchmark execution is manual and credential-gated;
- normal app operation is not the source of the Codex usage consumed by an
  interactive development session.

## Plan direction

The plan introduces, sequentially:

1. deny-unknown automation contracts;
2. deterministic retry policy and a single-instance durable cycle store in
   parallel;
3. a deterministic `NOOP/RETRY/ENQUEUE/PARK/ESCALATE/HALT` planner;
4. an append-only escalation outbox and one fixed read-only verification job in
   parallel;
5. deny-unknown dispatch plus a single-lock maintenance coordinator;
6. zero-call AI proposal artifacts;
7. a read-only consumer of already-published Stage B aggregates only after its
   separate approvals;
8. 24-hour and seven-day zero-AI soaks.

The retry outputs are fixed as
`src/tios/ops/automation_retry_policy.py` and
`tests/test_automation_retry_policy.py`. The job design preserves the existing
`JobType.DATA_QUALITY` and SQLite enum/check, mapping that type exclusively to
the exact `{"contract_id":"VERIFY_SHORTFRAME_SNAPSHOT_V1"}` payload and handler.
Full-demo readiness is not a job; it stays in the maintenance coordinator.

Escalations use a stable `escalation_id`. Each append-only event has a separate
unique `outbox_event_id` bound to that escalation ID, fixed event type, monotonic
per-escalation sequence, and exact evidence. Only the fixed operator CLI can
acknowledge or resolve; the dashboard remains read-only.

AI remains proposal-only. The fixed default budget is zero calls and USD 0.00 per
UTC day.

## Integrity and authority state

`docs/architecture/AD.md` and `TODO.md` are manifest-listed.
`PACKAGE_INTEGRITY_MANIFEST.md` is immutable. D-115 and D-116 are exhausted. The
pending Stage B packet reserves v8.146 and its exact exception cannot be expanded.

Therefore:

- `todos/21_deterministic_automation.md` is `PROPOSED / UNINDEXED`;
- `TODO.md` and `AD.md` remain unchanged;
- the proposed AD §H/§S/AD-18 and TODO index amendments require a separate exact
  operator-approved integrity exception for the then-next free version, expected
  no earlier than v8.147;
- that future protected adoption inventory includes
  `docs/traceability/TRACEABILITY_MATRIX.md` with current manifest-row occurrence
  count `×1`; this is the integrity-manifest row count, not a limit on textual
  references;
- `PROJECT_STATE.md` remains the live authority and was not changed;
- execution authority remains `NONE`.

No file under `IMMUTABLE_PATHS`, `artifacts/holdout/`, or `artifacts/sealed/` was
changed. No prospective or sealed outcome was read. No service was restarted, no
campaign/order was started, and no provider was called.

## Exact next gates

For bounded zero-authority automation:

1. after v8.146 is resolved, seek a separate exact automation-doc integrity
   exception for AD/TODO adoption;
2. implement contracts;
3. implement retry policy and durable store in parallel;
4. implement the planner;
5. implement the outbox and fixed short-frame job in parallel, with only the job
   waiting for the production verifier's independent `GO`;
6. implement deny-unknown dispatch and maintenance;
7. add optional AI artifacts only after the deterministic path passes;
8. keep every runtime path zero-LLM until a separate nonzero provider budget is
   explicitly approved.

Independent Phase-2b reviewer sourcing and its key-possession/no-authority packet
continue as a parallel external evidence track, not a predecessor to this bounded
automation. The two exact Stage B approvals gate only the read-only aggregate
consumer; without them, Stage B remains untouched. That consumer may emit only
new automation outbox/request artifacts and must write zero files in the Stage B
inventory.

## Stop conditions

Stop on any attempt to:

- treat this plan as strategy approval or execution authority;
- modify the protected AD/TODO/index/manifest without the exact exception;
- run two pytest suites concurrently;
- auto-restart or control the demo lane;
- rescue a closed family or read a protected outcome early;
- let AI mutate evidence, a gate, threshold, schedule, demo control, strategy
  promotion, credential, venue, or order;
- consume v8.146 for this initiative or piggyback on the Stage B exception.
