# S2 Autonomous Research Lab — Implementation Plan

Status: ACTIVE after operator HG-2 authorization on 2026-07-10.

## Outcome

Build an application-owned, unattended research and validation loop that can ingest
documented strategy hypotheses, run reproducible experiments on frozen market data,
retain every trial, score evidence across independent dimensions, and show its work in
the live Trading OS dashboard.

S2 autonomy means autonomous evidence operations. It does not mean autonomous order
routing. No strategy, synthetic wallet, venue demo/testnet connection, or real-money
path is activated by this plan.

## Non-negotiable boundaries

- Research claims from papers or websites enter as hypotheses, never inherited proof.
- Every run is content-addressed, idempotent, retained, and tied to dataset, strategy,
  engine, environment, cost assumptions, and source provenance.
- Scores remain multi-dimensional. The system must not hide failed gates behind one
  blended number.
- A candidate remains `UNVALIDATED` and `NOT_ELIGIBLE` until the complete validation
  and independent risk predicates pass.
- Paper/demo venue connectivity requires S2 exit, HG-3, a validation-eligible strategy,
  an explicit paper-lane architecture decision, a security pass, and a new operator
  approval for that specific integration.
- Live-family approvals, credential-bearing venue clients, and real-money commands stay
  unreachable.

## Delivery waves

### Wave S2-0 — Governance reconciliation

Record the operator's HG-2 decision as D-036 and update the stage-exit, prototype
decision, project state, operational handoff, execution plan, task states, changelog,
and integrity manifest. Preserve every recorded S1 constraint, including the rejected
B2 paper decision, G4 warning, G10 absence, mock-only AI evidence, and engine gaps.

Acceptance:

- All authoritative files agree that S2 is active.
- They all agree that paper/demo venue and live trading remain unauthorized.
- The live dashboard reports the same stage.

### Wave S2-1 — Architecture lock and contracts

Resolve T-002-01 through T-002-04 from retained S1 evidence:

- modular monolith with ports/adapters remains the application boundary;
- SQLite is the local operational state store unless measured contention disproves it;
- Parquet + DuckDB remain the analytical path;
- MLflow + DVC remain behind lineage ports with explicit retention/backup rules;
- engine subprocess isolation and normalized-result contracts remain mandatory;
- the first job runner is a bounded deterministic command, with persisted scheduling
  added only after the command is proven idempotent.

Add inert typed records for market bars/quotes, signals, order intents and states,
fills, bracket levels, positions, accounts, portfolios, risk decisions, approval
records, and chart annotations. These records expose no venue client and no mutation
endpoint.

Acceptance:

- Contract tests cover decimal money/quantity, UTC timestamps, stable IDs, lifecycle
  invariants, environment tags, and prohibited live transitions.
- No HTTP write endpoint, credential variable, exchange write API, or order command is
  introduced.

### Wave S2-2 — Research Lab v0

Create one offline, deterministic batch command that reuses the frozen canonical data,
baseline specs, vectorbt accelerator, experiment ledger, evidence registry, and mock-AI
policy.

Required flow:

```text
frozen-data preflight
→ canonical-spec validation
→ retained B2/B3/B4 parameter sweeps
→ append-only per-batch experiment ledger
→ evidence rows marked UNVALIDATED / NOT_ELIGIBLE
→ multi-dimensional scorecard and explicit blockers
→ read-only dashboard projection
```

Implementation scope:

- Parameterize `engines/vectorbt/probe_sweep.py` with dataset and output paths.
- Refactor `scripts/register_vectorbt_trials.py` so it never deletes a retained ledger.
- Add `scripts/run_research_lab_v0.py` with deterministic batch identity, fail-closed
  preflight, idempotent reuse, complete failure retention, and a command allowlist.
- Store batches under `artifacts/research_lab/v0/LAB-<content-hash>/`.
- Emit a manifest, all trial tables, experiment ledger, evidence ledger, scorecards,
  provenance references, and blockers.
- Reject real AI mode, Freqtrade trade/dry-run, testnet, sandbox, venue, paper, and live
  commands in v0.

Initial score dimensions:

1. data integrity and freshness;
2. economic performance after declared costs;
3. drawdown and loss severity;
4. parameter-neighborhood robustness;
5. temporal/walk-forward stability;
6. regime stability;
7. baseline superiority;
8. multiple-testing/selection-bias control;
9. cross-engine reproduction;
10. operational and evidence completeness.

Missing dimensions are blockers, not zero-filled inputs to a blended score.

Acceptance:

- An identical complete batch is reused without recomputation.
- Partial/failed batches are retained and visible.
- All 66 current vectorbt trials are retained; no winner is automatically selected.
- The batch declares `execution_authority=NONE`, `venue_connection=NONE`,
  `paper_orders=DISABLED`, and `live_orders=DISABLED`.
- Focused tests and the full repository gate pass.

### Wave S2-3 — Research sources and candidate expansion

Add an application-owned research-source registry containing bibliographic identity,
canonical URL/DOI, publication date, authors, access/license notes, claim summary,
hypothesis family, implementation assumptions, review timestamp, supersession links,
and reproduction status.

Seed only primary sources for trend/time-series momentum, mean reversion, volatility
sizing, transaction costs, and backtest-overfitting controls. Each source creates one or
more explicit hypotheses that must be translated into canonical strategy specs and
locally reproduced before comparison.

Acceptance:

- Source provenance is visible beside every candidate.
- Unsupported or ambiguous claims are labeled, not silently resolved.
- No source is described as "proven" merely because it was published or profitable in
  its original sample.

### Wave S2-4 — Live Trading OS research console

Extend the existing dashboard without breaking its refreshability:

- Research Lab view: batch state, elapsed time, retained trials, failures, blockers.
- Candidates view: hypothesis/source links, parameter families, independent scores,
  validation state, and approval state.
- Comparison view: equity, drawdown, cost sensitivity, robustness, regime, and
  cross-engine evidence.
- Market workspace: owned historical candle chart with signal/fill/TP/SL annotations;
  an attributed TradingView widget may remain a contextual market monitor.
- Automation view: last run, next eligible work, failed jobs, and safe manual trigger.
- Trading-domain view: read-only/inert order, position, portfolio, and risk projections
  explicitly labeled disabled until the later gate.

The v0 trigger can remain a local command while its idempotency is established. A
persisted SQLite job table and scheduler follow in a bounded S2 increment; they may run
only allowlisted research, freshness, validation, and report jobs.

Acceptance:

- The page stays available at `http://127.0.0.1:8765` throughout normal development.
- The UI never presents an unavailable action as executable.
- API and UI contract tests prove paper/live controls remain disabled.

### Wave S2-5 — First autonomous evidence cycle

Run the seeded hypotheses through research sweeps, retain all populations, escalate
promising candidates through cost, temporal, regime, robustness, multiple-testing, and
cross-engine checks, and publish the resulting evidence packages and ranked dimensions.

The cycle may conclude that no candidate is eligible. That is a valid result and must
not be overridden to manufacture a demo-trading milestone.

Acceptance:

- Every candidate has a reproducible lineage from source to spec to run to scorecard.
- Any promotion proposal cites a complete validation package and independent risk pass.
- If no candidate qualifies, demo/paper remains disabled and the next hypothesis cycle
  is scheduled from the recorded gaps.

### Wave S2-6 — Verification and S2 exit package

Run the full quality gate, an independent code/security review, restore/replay tests,
live-unreachability tests, and a requirement-by-requirement S2 audit. Prepare HG-3 only
when the evidence actually supports it.

## Paper/demo activation predicate

```text
S2_EXIT_PASS
AND HG_3_APPROVED
AND validation.status == COMPLETE_APPROVABLE
AND validation.promotion_eligible == true
AND paper_lane_architecture_decision_exists
AND security_review_passes
AND operator_approved_specific_demo_or_testnet_integration
```

Until all terms are true, the Trading OS remains historical, research-only, read-only
at execution boundaries, and disconnected from venue paper/demo and real-money paths.
