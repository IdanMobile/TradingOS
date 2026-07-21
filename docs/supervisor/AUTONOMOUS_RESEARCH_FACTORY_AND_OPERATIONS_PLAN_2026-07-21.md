# Autonomous Research Factory and Operations Plan

Date: 2026-07-21  
Status: implementation authorized; Phase 0 complete; no live-capital authority  
Objective: operate the Trading Intelligence OS continuously from sourced hypothesis through
research, rejection or validation, independently reviewed promotion, and bounded demo evidence.
Profit is an observed outcome after costs, never an approval input or guaranteed deliverable.

## Invariants

- `PROJECT_STATE.md` remains the live task authority until an operator-governed integrity update.
- No live or real-money activation is authorized by this plan.
- No closed strategy family may be re-searched, renamed, flipped, ensembled, or versioned to reset
  its trial budget.
- No sealed or prospective outcome may be read before its preregistered review gate.
- Every evaluated trial is retained and counted hierarchy-wide.
- Campaigns cannot promote themselves; independent review and human stage decisions remain binding.
- Canonical evidence is append-only filesystem evidence; SQLite is a rebuildable operational view.
- No immutable path or manifest-listed file is edited without the project’s integrity protocol.
- `make check` is the release gate; pytest suites never run concurrently.

## Phase 0 — Documentation discovery and baseline freeze

Status: COMPLETE.

### Verified baseline

- The reviewed demo resting-stop repair is committed as `7e7cde2`.
- Dashboard, orchestrator, prospective observers, demo lane, trial ledger, strategy registries,
  eligibility contract, jobs store, and bounded worker already exist.
- Seven searchable families have zero passes; public-signal family mining is closed under V9.
- The jobs CLI supports a continuous worker, but it is not productized as a supervised service.
- Orchestrator observes evidence and blockers but does not dispatch generic campaign jobs.
- Research source, hypothesis, StrategyVersion, campaign, validation, and approval primitives exist
  as disconnected or duplicated vertical slices.

### Allowed APIs and copy sources

- Service entrypoints: `scripts/run_orchestrator.py --loop --interval 900`,
  `scripts/run_job_worker.py run-loop --poll 1.0`, and
  `python -m tios.services.dashboard_ui.server --host 127.0.0.1 --port 8765`.
- Launchd/TCC pattern: `ops/install_daily_update.sh`; wrapper pattern:
  `ops/run_daily_update.sh`.
- Health reads: dashboard `GET /api/v1/status`, retained orchestrator `observed_at`/`halted`,
  and existing demo advisory-lock liveness.
- Source/hypothesis strict parsers: `research_assets/registry.py` and `hypotheses.py`.
- Canonical spec parsing/validation: `strategy/spec.py` and `strategy/validator.py`.
- Persistent spec registry: `strategy/registry.py`.
- Budget and campaign primitives: `validation/trial_budget.py` and `validation/campaign.py`.
- Safe selection barrier: `scripts/run_funding_pressure_campaign.py::SelectionBarrier`.
- Job leases/idempotency/confinement: `services/jobs/store.py` and `runner.py`.
- Eligibility and promotion: `validation/eligibility.py` and `approval/history.py`.

### Anti-patterns

- No `nohup`, PID-only health, arbitrary shell-command job payloads, new microservices, or cloud
  deployment in this milestone.
- No unconditional restart of orchestrator escalation or the order-bearing demo lane.
- No generic dashboard process-control endpoint.
- No second StrategyVersion identity system.
- No use of the B2-specific validation-package script as though it were generic.

## Phase 1 — Local operating substrate

Goal: make non-order services survive terminal closure and expose honest local health.

### Implementation

1. Copy the root/venv/TCC/plist-generation pattern from `ops/install_daily_update.sh` into new,
   dedicated local-service tooling under `ops/local_services/`.
2. Generate fixed-argv user LaunchAgents for:
   - dashboard;
   - orchestrator;
   - continuous offline jobs worker.
3. Copy wrapper semantics from `ops/run_daily_update.sh`: explicit repository cwd, direct venv
   Python, explicit `PYTHONPATH`, no shell interpolation of job payloads.
4. Add a read-only health checker that distinguishes:
   - dashboard reachability;
   - orchestrator evidence freshness from process liveness and halt state;
   - jobs LaunchAgent state;
   - demo-lane state as observed only, never automatically restarted.
5. Refuse installation from macOS TCC-protected locations unless the operator explicitly moves
   the repository or chooses the existing documented force path. Rendering and dry-run remain
   available in the current Downloads location.

### Verification

- Generated plists pass `plutil -lint`.
- Fixed argv contains no secrets and no shell command payload.
- TCC refusal, label uniqueness, restart policy, and health classification have focused tests.
- Orchestrator intentional halt is not auto-restarted.
- Dashboard/jobs unexpected exit policy is restartable.
- One final `make check` passes.

### Guards

- Do not edit immutable `Makefile` or manifest-listed dashboard/status sources in this phase.
- Do not install or bootstrap LaunchAgents until code/render tests pass and the Downloads/TCC
  deployment decision is explicit.
- Do not auto-restart the demo lane.

## Phase 2 — Research candidate intake ledger

Goal: retain ideas at a fail-closed boundary without granting experiment or admission authority.

### Implementation

1. Add an immutable candidate dossier using the strict parsing/digest patterns in
   `research_assets/registry.py` and `hypotheses.py`.
2. Retain source IDs/digests, hypothesis ID/digest, family identity, dataset/package refs and
   hashes, spec hash, lawful-reopen evidence class, closed-family comparison, lifecycle state,
   authority `NONE`, and an explicit intake verdict.
3. Add an append-only candidate intake registry with deterministic record identity,
   idempotent duplicate handling, and conflict rejection.
4. Fail closed when evidence is missing, the family matches a closed context without lawful new
   evidence, or the request implies a rescue/version reset.
5. Produce review requests for data/access/operator gaps; never synthesize an admission.
6. Limit current states to `REVIEW_REQUIRED` and terminal `REJECT`. Phase 2 implements no
   `ADMIT` transition because this repository does not yet bind a trusted independent reviewer
   identity.

### Verification

- Same canonical input produces the same ID and one retained record.
- Same ID with conflicting content fails.
- Closed-family rescue attempts fail.
- Official/licensed/operator-supplied/prospective evidence classes are explicit and tested.
- Every retained record has `execution_authority=NONE` and no performance result.
- No Phase-2 API or stored value can represent `ADMIT`.

### Guards

- Do not read strategy outcomes while deciding admission.
- Do not expand the current B2–B4 hypothesis registry by weakening its validation; add the new
  boundary alongside it and migrate only after compatibility evidence.
- The intake ledger's unkeyed hash chain detects ordinary tampering but not tail truncation or a
  complete rewrite without an external checkpoint; it is not an approval boundary.

## Phase 2b — Typed intake-decision scaffold and external activation gate

Goal: define and semantically assess a typed independent-review statement without representing
or granting admission. The repository currently has no intake-admitted state.

### Scaffold implemented in this repository

1. The typed statement binds the exact dossier, catalog and assessment digests, predecessor,
   claimed reviewer identity/role/credential, declared trust snapshot, decision/expiry times,
   every pending DATA/ACCESS/OPERATOR domain, and authority `NONE`.
2. Canonical signing bytes and detached-attestation types exist, but there is no signer, key,
   cryptographic verifier adapter, key generation, or production verifier composition here.
3. A caller-supplied verifier can only support a historical semantic assessment. A semantically
   valid ADMIT statement stops at `VERIFIED_PENDING_EXTERNAL_ACTIVATION`; a semantically valid
   external REJECT stops at `VERIFIED_REJECTION_PENDING_EXTERNAL_ACTIVATION`. Both retain the
   same explicit external blockers and authority `NONE`. Neither can admit, close, or permanently
   reject a candidate or strategy family.
4. Evidence digests inside review resolutions remain untrusted reviewer claims. This module does
   not resolve those digests to independently verified typed review evidence.
5. Duplicate, competing, stale, malformed, revoked, expired, and binding-mismatched inputs fail
   closed. This does not prove that a caller supplied the complete external decision sequence.

### Operator-gated external activation substep — NOT IMPLEMENTED

Admission remains unavailable until an operator-approved change supplies all of the following:

- a fixed production external verifier composition that repository-writing agents cannot replace;
- authoritative append-only decision history plus an externally retained monotonic checkpoint;
- a typed resolver that independently verifies every review-evidence digest and domain outcome;
- trusted current time and current credential/revocation/trust-snapshot evidence;
- a genuinely independent reviewer identity and credential lifecycle outside this repository;
- frozen interfaces, integrity-manifest rows, changelog evidence, and independent security review.

Only that separately reviewed substep may introduce an admitted state, terminal external rejection,
or an API consumable by a campaign contract. Generic workspace decisions, free-form files,
repository fakes, caller-selected verifiers, and omitted history can never do so. The authoritative
Phase-2 intake ledger's policy `REJECT` remains terminal because it is local fail-closed policy, not
a caller-supplied external decision.

### Verification

- No `ADMITTED` state/value or admission resolver is exposed by the scaffold.
- Fake-verifier semantic tests can reach only blocked admission-pending or rejection-pending
  assessment states with authority `NONE`.
- Direct status fabrication, duplicate JSON keys, non-canonical artifacts, sentinel algorithms,
  malformed verifiers, replay/competing decisions, rollback, and stale trust fail closed.

### Guards

- Phase 3 and Phase 4 remain blocked until the operator-gated external activation substep is
  implemented, frozen, and independently reviewed.
- Phase 5 strategy validation/promotion review cannot substitute for candidate-intake authority.

## Phase 3 — Unified campaign contract and StrategyVersion bridge

Goal: bind candidate, immutable strategy identity, data, implementation, engines, costs, splits,
and trial budget before evaluation.

Status: BLOCKED on the operator-gated external activation substep in Phase 2b.

### Implementation

1. After the external activation substep introduces a frozen, independently reviewed admission
   contract, require that future contract; the current Phase-2b pending status is not consumable.
   Then define a strict `CampaignContract` parser with exact fields and canonical digest.
2. Bridge the existing parameter-resolved `create_version()` identity to the persistent
   `strategy.registry` identity without creating a third identity system.
3. Include parent/family lineage, rationale, falsification test, and family budget reference for
   future V2/V3 candidates.
4. Bind pinned dataset, implementation files, engine versions, scenario grid, chronology,
   thresholds, stop rules, and authority `NONE`.
5. Verify a clean tree and all pins before marking a contract `READY`.

### Verification

- Any changed input changes the contract digest.
- Missing or mismatched pins fail before evaluation.
- A new version does not reset family multiplicity.
- No validation/holdout accessor exists before frozen selection.

### Guards

- Copy the funding-pressure selection barrier, not the invalidated calendar reserve ordering.
- Preserve the existing persistent StrategyVersion registry as the identity base.

## Phase 4 — Generic campaign executor

Goal: run admitted candidates through one reusable, retained, hierarchy-accounted path.

Status: BLOCKED on Phase 3 and the operator-gated external activation substep in Phase 2b.

### Implementation

1. Reject every candidate until the future frozen external admission contract exists and verifies;
   `VERIFIED_PENDING_EXTERNAL_ACTIVATION` is always rejected. Then copy the mature preflight,
   selection, and atomic-publish pattern from the funding-pressure and transaction-activity runners.
2. Call `trial_budget.preregister()` before evaluation and `record_trial()` immediately after
   every development trial.
3. Require `TrialScore` with completed-trade and aligned-bar returns.
4. Freeze selection before validation; keep holdout inaccessible.
5. Retain per-trial/per-slice statistics required for honest DSR/PBO and parameter stability.
6. Publish immutable success, failure, timeout, and incomplete artifacts atomically.

### Verification

- Fault injection covers interruption, duplicate job, late result, corrupt selection hash, and
  mismatched trial count.
- Replays are idempotent and byte-equivalent where timestamps are excluded from identity.
- Campaign results remain non-promotable.

### Guards

- One campaign at a time initially.
- No arbitrary script path or shell payload.
- No dirty-tree execution or sealed/prospective outcome access.

## Phase 5 — Generic validation and promotion package

Goal: turn retained campaign evidence into an honest eligibility decision and review request.

This phase reviews a strategy after research execution. It does not create or substitute for the
Phase-2b independent decision that first authorized the candidate to enter research.

### Implementation

1. Normalize campaign gate evidence into exact G1–G11 keys.
2. Build `MetricEvidence`, `ScorecardEvidence`, `PromotionEvidence`, and a ledger-backed
   `BudgetVerdict` for `evaluate_strategy_eligibility()`.
3. Retain all missing/failed dimensions; never convert missing evidence to zero or PASS.
4. Generate typed independent statistical, risk, supervisor, and security review requests.
5. Bind typed `HumanDecisionRecord` and `GatedApprovalEvidence` only after evidence gates pass.

### Verification

- Incomplete evidence is `NOT_ELIGIBLE` with explicit blockers.
- All G1–G11, ten score dimensions, budget verification, and four independent reviews are
  mandatory for promotion eligibility.
- Generic workspace decisions cannot masquerade as typed approval evidence.
- Live-order capability present always blocks research promotion.

### Guards

- The implementing agent cannot satisfy independent-review roles.
- Attestation does not replace validation, review, or typed stage-gate approval.

## Phase 6 — Fixed job handlers and orchestrator dispatch

Goal: operate the research factory continuously without granting arbitrary execution.

### Implementation

1. Add fixed allowlisted job types for intake/admission verification, campaign preflight, campaign
   execution, validation-package build, and report refresh.
2. Payloads contain only retained contract IDs/hashes.
3. Add orchestrator dispatch policy only for future externally admitted `READY` candidates, one
   campaign at a time; the current pending-activation scaffold is never dispatchable.
4. Halt/escalate on integrity failure, unexpected promotion eligibility, or authority drift.
5. Park data, credentials, independent review, and future-date gates with exact release criteria.

### Verification

- Arbitrary command/path payloads are rejected.
- Duplicate schedules/jobs are idempotent.
- Worker timeouts stop process groups and retain failure evidence.
- Closed-family and future-date candidates are never dispatched.

## Phase 7 — Shadow and demo evidence

Goal: measure prospective decision and execution quality without confusing it with strategy proof.

### Implementation

1. Produce structured `DecisionPacket`/decision traces from point-in-time numeric data in shadow
   mode, including `NO_TRADE` and expiry.
2. Compare later outcomes only at preregistered review times.
3. For separately approved demo candidates, use the typed asynchronous state machine,
   idempotency IDs, fill reconciliation, divergence, and stability evidence.
4. Resolve `FILLED_PENDING_RECONCILIATION` before any demo lane can resume order production.
5. Convert demo measurements into typed G12 evidence only under a frozen G12 contract.

### Verification

- Stale/gapped data yields `NO_TRADE`.
- Restart, lost acknowledgement, duplicate fill, partial fill, cancel/fill race, and reconciliation
  mismatch tests pass.
- Demo P&L is labeled execution evidence only.

## Phase 8 — Limited-live proposal

This phase remains operator-gated and is not authorized for implementation or activation by this
plan. It requires a validated candidate, independent reviews, prospective/demo evidence, current
venue/legal checks, a valid operator attestation, explicit capital/loss limits, rollback, and a
new human decision. AI cannot approve or activate it.

## External gates and fastest lawful research path

- Current public historical family mining is exhausted. The fastest lawful reopening is genuinely
  new exogenous evidence, preferably a point-in-time delisting-complete crypto universe because it
  resolves a foundational survivorship gap across cross-sectional research.
- Provider evaluation may be researched, but purchasing or accepting license terms remains an
  operator decision.
- Existing MVRV/CFTC/ETH/liquidation prospective protocols remain sealed until their frozen gates.
- Independent D-099 review must come from an operator-sourced reviewer.

## Milestone completion criteria

The OS is operating as intended when:

1. dashboard, orchestrator, and offline jobs are supervised and honestly observable;
2. every new hypothesis enters through the Phase-2 intake ledger and cannot reach Phase 3,
   Phase 4, or any campaign without the future operator-approved, frozen external admission
   contract; current `REVIEW_REQUIRED`, `VERIFIED_PENDING_EXTERNAL_ACTIVATION`, and
   `VERIFIED_REJECTION_PENDING_EXTERNAL_ACTIVATION` states confer no admission or campaign
   authority;
3. every trial is preregistered, retained, and hierarchy-counted;
4. every candidate exits as rejected, insufficient, blocked, or independently reviewable;
5. eligible candidates progress through shadow/demo only by typed evidence and human gates;
6. no process can weaken constraints, rescue a failed family, self-approve, or activate real money;
7. profitability, if discovered, is measured prospectively after every cost and can trigger
   suspension when it disappears.
