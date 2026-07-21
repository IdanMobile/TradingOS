# Continuous-Learning Decision Intelligence Plan

Date: 2026-07-21  
Status: offline vertical slice implemented; order-path implementation remains gated by Phase 0  
Authority: offline planning and simulation only; no new order or capital authority

## Outcome

Build an evidence-driven loop that can explain every decision, distinguish normal trading losses from system defects, propose bounded improvements, produce immutable V2/V3 candidates, evaluate its own AI components, and eventually operate on real-time numeric market data in shadow mode before any separately authorized demo or live promotion.

The system must optimize for trustworthy decisions and controlled risk-adjusted expectancy, not for making every historical loss look avoidable. A losing trade can be correct. An AI may recommend; it may never approve its own recommendation, weaken a gate, or deploy a strategy.

## Verified baseline

- The project already defines `SignalEvent`, `RiskDecision`, `OrderIntent`, `FillEvent`, `OrderStatus`, `PaperDivergenceReport`, and `OperationalIncidentRecord` in `src/tios/trading_domain/models.py`.
- Synthetic risk, fill, divergence, and stability logic already exists and should be extended rather than replaced.
- The AI benchmark already has model, agent, and prompt registries plus T1-T8 fixtures and provenance.
- `src/tios/services/reporting/` and `src/tios/ai_eval/` do not yet contain the proposed production services.
- The fast non-slow suite is currently healthy: 1,120 passed and 29 deselected in 52.30 seconds. A focused decision/execution/AI slice passed in about 1.8 seconds.
- Current repository text contains an authority conflict. The highest-precedence start handoff still confines work to S2 and keeps authenticated demo execution quarantined, while D-104 through D-106 record an approved and active demo measurement lane. This must be reconciled before order-path implementation.
- 2026-07-21 implementation evidence now includes immutable offline decision traces, deterministic reporting and backtest loss attribution, a fail-closed authority auditor, and an independent Inspector proposal evaluator. These additions do not alter execution authority.

## System loop

```text
point-in-time data -> features -> strategy signal -> portfolio/risk decision
        -> intent -> venue state machine -> fills/reconciliation -> outcome
        -> deterministic attribution -> Inspector AI -> recommendations
        -> sandboxed candidate V(n+1) -> frozen evaluation -> human promotion gate
```

Every arrow emits an immutable event joined by stable correlation IDs. “No trade,” blocked trade, rejection, partial fill, timeout, and reconciliation correction are first-class outcomes.

## Core contracts

Reuse existing trading-domain types. Add only the missing concepts below after contract review:

- `DecisionTrace`: correlation ID, timestamps, data/feature/spec hashes, signal, risk decision, intent, execution references, outcome references, environment, and authority.
- `OutcomeRecord`: gross and net P&L, fees, slippage, adverse/favorable excursion, latency, horizon, exit reason, data quality, reconciliation status, and completeness.
- `FailureAttribution`: observed failure class, evidence references, confidence, competing explanations, unknowns, and deterministic checks performed.
- `CounterfactualResult`: exactly one declared intervention, unchanged inputs, recomputed result, cost assumptions, and leakage guard result.
- `RecommendationRecord`: proposed change, predicted benefit, risks, evidence, affected contracts, falsification test, and required approval.
- `AgentEvaluationRecord`: agent/model/prompt/tool/context versions, frozen fixture set, scores, cost, latency, failures, evaluator identity, and independence status.
- `DecisionPacket` for shadow real time: as-of timestamp, horizon, scenario probabilities, expected gross/net edge, uncertainty, expiry, regime, risk blockers, and recommended action including `NO_TRADE`.

Stable domain fields must not depend on experimental OpenTelemetry GenAI attribute names. Exporters map domain events outward.

## Failure taxonomy

Attribution is hierarchical and may remain `UNKNOWN`:

1. Data: missing, stale, revised, misaligned, survivorship, lookahead, timezone, or schema drift.
2. Research: selection bias, multiple testing, overfitting, unstable parameters, insufficient sample, or invalid cost assumptions.
3. Strategy: regime mismatch, weak signal, incorrect sizing request, correlated exposure, or ordinary statistical loss.
4. Risk/portfolio: rule error, stale state, concentration, sizing, limit interaction, or correct preventive block.
5. Execution: rejection, partial fill, price impact, slippage, latency, duplicate event, cancel/fill race, or venue constraint.
6. Operations: restart, cursor error, idempotency failure, clock skew, rate limit, connectivity, or reconciliation mismatch.
7. AI: unsupported claim, missing evidence, tool error, prompt/model regression, evaluator capture, or unsafe recommendation.

Attribution must separate facts, inference, hypothesis, recommendation, and unknown. It must never rewrite historical evidence.

## Phased implementation

### Phase 0 — Reconcile authority and freeze the baseline

Goal: establish one unambiguous source of truth before code changes.

Work:

- Resolve the conflict between the highest-precedence start handoff/D-046-era quarantine and D-104-D-106.
- Record whether the demo lane is active, suspended, or design-only; update every higher-precedence document, project state, decision log, open-items record, and integrity manifest atomically.
- Snapshot the dirty worktree and identify which current files/artifacts are accepted baseline versus work in progress.
- State separately the authority for offline research, shadow data, venue demo, and live capital.

Exit checks:

- A machine-readable authority test and human-readable documents agree.
- No contradictory stage or execution status remains.
- Existing changes are preserved and assigned provenance.

### Phase 1 — Canonical decision and outcome ledger

Goal: make every decision reproducible and joinable.

Work:

- Add the missing contracts through the existing domain catalog and append-only evidence patterns.
- Generate correlation IDs at the first accepted data snapshot and propagate them through all downstream records.
- Hash canonical inputs, strategy version, parameters, code revision, cost model, and calendar/split definitions.
- Store JSONL as canonical append-only evidence; use SQLite/DuckDB/Parquet only as rebuildable query projections.
- Define deterministic completeness rules: a trace cannot be called complete until terminal execution and reconciliation state are known.

Exit checks:

- Replay yields byte-equivalent canonical records.
- Duplicate events are idempotent; conflicting duplicates become incidents.
- Property tests cover missing, reordered, repeated, and late events.

### Phase 2 — Reporting and correlated observability

Goal: answer what happened, why, and what remains unknown without reading raw logs.

Reports:

- run manifest and test-duration report;
- strategy scorecard by asset, regime, horizon, side, and cost scenario;
- decision funnel: observed -> eligible -> signaled -> risk-approved -> submitted -> filled -> reconciled;
- execution quality: reject/partial-fill rates, latency, spread, slippage, fees, and divergence;
- failure attribution and unresolved-evidence report;
- AI evaluation, cost, latency, recommendation acceptance, and regression report;
- promotion-readiness and rollback report.

Work:

- Implement reporting as pure projections over immutable events.
- Add optional OpenTelemetry-compatible export behind a port; retain domain-owned names and redact secrets/raw credentials.
- Report `NO_TRADE`, blocks, errors, and abandoned attempts, not just winners and fills.

Exit checks:

- Each metric links to source event IDs and manifests.
- Reports rebuild deterministically and expose missing/late evidence.
- Redaction tests prevent secrets, signatures, and sensitive request material entering traces.

### Phase 3 — Faster, reliable tests

Goal: shorten feedback while preserving the full release gate.

Lanes:

- `smoke` target: under 10 seconds, contracts and critical invariants.
- `focused` target: under 25 seconds, changed-module dependency slice.
- `offline-core` target: under 2 minutes, domain/research/AI without slow data profiles.
- `full` release gate: all tests, security scans, data profiles, typing, lint, and manifests.

Work:

- Emit machine-readable test duration and failure artifacts on every run.
- Use hermetic `tmp_path`; use session-scoped cached fixtures only for immutable expensive inputs.
- Remove repeated canonical baseline setup and redundant data-profile work using content-addressed caches.
- Parallelize only after eliminating shared output paths and order dependence.
- Add Hypothesis state machines for order, cancel, fill, restart, and reconciliation sequences.
- Run leakage, recursive-indicator, split-boundary, and cost-model checks as mandatory research gates.

Exit checks:

- Two shuffled runs have identical outcomes.
- Cache-on and cache-off results match.
- Failed commands and collection errors are recorded, not hidden by retries.

### Phase 4 — Backtest learning and immutable strategy versions

Goal: convert evidence into falsifiable candidates without contaminating validation.

Work:

- Decompose return into signal edge, sizing, fees, spread/slippage, funding, execution approximation, and regime exposure.
- Run the existing G1-G12 evidence gates plus walk-forward, temporal purging/embargo where relevant, stress costs, parameter perturbation, and multiple-testing correction.
- Preserve a sealed holdout/reserve that the Inspector, Recommender, and Fixer cannot inspect.
- Permit counterfactuals only as diagnostics: one declared intervention at a time, no retroactive alteration of the observed result.
- Create `V2`, `V3`, etc. as new immutable specifications with parent hash, change rationale, falsification test, and complete evaluation record. Never mutate V1.
- Stop a family when its trial budget is exhausted; a new version does not reset the budget.

Promotion sequence:

```text
idea -> preregistered candidate -> development -> validation -> sealed reserve
     -> shadow -> separately authorized demo/paper -> limited live proposal
```

Exit checks:

- No strategy is selected on the reserve set.
- Deflated Sharpe/PBO or an approved equivalent accounts for selection multiplicity.
- Results include uncertainty, turnover/capacity, drawdown, and all-in costs—not only net profit.

### Phase 5 — Inspector, Recommender, Fixer, and independent Evaluator

Goal: improve both trading candidates and the agents while preventing self-approval.

Roles:

- Inspector: read-only evidence analysis; identifies facts, hypotheses, and missing evidence.
- Recommender: proposal-only; writes a bounded change and falsification plan.
- Fixer: applies an approved proposal only in an isolated branch/sandbox; cannot edit protected gates, authority, audit history, or sealed fixtures.
- Evaluator: runs deterministic and frozen AI evaluations; must be versioned and independent of the candidate agent.

Self-improvement rules:

- Version the model, prompt, tools, retrieval corpus, context policy, and budget independently.
- Promote an agent version only on frozen historical failures plus prospective shadow cases.
- An agent may not author its own acceptance criteria, see sealed answers, choose only favorable cases, or approve/deploy itself.
- Deterministic validators outrank LLM judgments. Human review remains mandatory for critical recommendations.
- Reward evidence completeness, calibrated uncertainty, safety, and prospective decision quality; never raw reported profit alone.

Exit checks:

- Unsupported causal claims fail evaluation.
- A proposal that deletes a test or weakens a threshold is rejected mechanically.
- Rollback restores the prior model/prompt/tool bundle without changing historical traces.

### Phase 6 — Real-time shadow decision intelligence

Goal: read actual structured feeds and produce expiring, auditable decisions without placing orders.

Work:

- Consume numeric market/account feeds, not chart screenshots; enforce point-in-time availability and closed-bar rules.
- Maintain feed freshness, sequence, gap, and clock-skew health.
- Add regime classification and strategy sleeves, then portfolio aggregation that accounts for correlation and shared risk.
- Produce `DecisionPacket`s containing uncertainty and `NO_TRADE` as a valid outcome.
- Compare shadow decisions with later realized outcomes and with the existing canonical strategy evaluator.

Exit checks:

- Stale, gapped, or ambiguous inputs force `NO_TRADE`/risk block.
- Replay of the same event stream produces the same decisions.
- Prospective performance meets predeclared thresholds across a minimum observation window.

### Phase 7 — Separately authorized demo/paper execution measurement

Goal: measure venue behavior only after Phase 0 and explicit human/security approval.

Work:

- Use a typed asynchronous order state machine; do not treat REST acknowledgement as a fill.
- Assign a unique client idempotency key (`orderLinkId` for a Bybit adapter), persist intent before submission, and recover by that key after restart.
- Consume and deduplicate order and execution streams; support multiple fills, cancel/fill races, late events, and terminal reconciliation.
- Reconcile orders, executions, fees, balances, and positions before advancing signal cursors or allowing a retry.
- Enforce stale-data, rate-limit, exposure, kill-switch, and single-writer controls.

Exit checks:

- Fault injection passes for lost acknowledgement, duplicate `Filled`, partial fill, restart, websocket gap, rate limit, and reconciliation mismatch.
- Demo P&L is classified as execution evidence, never strategy validation.

### Phase 8 — Limited-live proposal, not automatic activation

This plan grants no live authority. A future proposal requires completed validation, prospective shadow/demo evidence, security review, legal/venue verification, capital and loss limits, operator attestation, monitoring, rollback, and an explicit human decision. AI cannot enable it.

## Implementation order and dependency rule

Implement only one vertical slice at a time:

1. Phase 0 authority contract.
2. One complete offline `DecisionTrace` from existing backtest signal through synthetic outcome and report.
3. Test timing/reliability infrastructure.
4. Deterministic attribution before AI explanation.
5. Inspector and frozen evaluation before Recommender/Fixer.
6. Shadow real time before any execution adapter change.

No microservice split is needed. Preserve the modular monolith and existing ports. MLflow may be evaluated as an adapter for AI traces/evaluations; it must not become the canonical trading ledger. OpenTelemetry is an export boundary, not a domain model.

## Definition of implementation-ready

The overall design is ready for implementation when Phase 0 is explicitly resolved. Phase 1 then begins with a contract-only change and tests. Execution-related Phases 7-8 remain separately gated regardless of offline progress.

## Non-goals

- Guaranteeing profit or converting every loss into profit.
- Letting AI directly trade, approve itself, mutate production, or weaken risk/validation gates.
- Optimizing from chart images when structured source data is available.
- Replacing deterministic accounting, risk, validation, or reconciliation with natural-language judgment.
- Treating backtest, demo, or AI-generated evidence as live approval.
