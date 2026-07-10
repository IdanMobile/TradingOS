# Trading Intelligence OS — Single Execution Plan

Status: HG-2 is approved, the S2 architecture lock is recorded as D-037, and bounded
S2 research-only execution is active. This file is the operator-facing index for
execution; the detailed acceptance criteria remain in `todos/NN_*.md`, and the
architecture authority remains the SSOT handoff and `PROJECT_STATE.md`.

## Working agreement

- Every task is completed only when its acceptance evidence exists and the local gate is green.
- Work is executed in dependency order; parallel work is limited to disjoint engine or benchmark lanes.
- The local dashboard at `http://127.0.0.1:8765` is the live read-only progress surface.
- No live trading, credential entry, external messaging, or human approval is delegated.

## Current execution sequence

| Wave | Work | State | Exit evidence |
|---|---|---|---|
| 0 | Repository foundation, environment intake, security baseline | DONE | `artifacts/reports/PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md`, `SECURITY_REVIEW_01.md` |
| 1 | Canonical dataset and strategy domain | DONE | frozen dataset manifest, quality report, baseline goldens |
| 2 | Engine bake-off and parity | DONE WITH RECORDED BLOCKED LANES | `artifacts/reports/ENGINE_BAKEOFF_REPORT.md` |
| 3 | Experiment lineage prototype | DONE — Test A/B/C, AI mock-only | `artifacts/reports/LINEAGE_PROTOTYPE_REPORT.md` |
| 4 | Experiment ledger, run executor, fee/slippage grid | DONE | append-only ledger tests and grid artifact |
| 5 | Validation gates and red-team review | DONE — NO APPROVAL | `artifacts/reports/BACKTEST_VALIDATION_REPORT.md`, `artifacts/reports/BACKTEST_RED_TEAM_REPORT.md` |
| 6 | Read-only evidence dashboard and prototype decision | DONE — HG-2 APPROVED (D-036) | dashboard contract/UI evidence, decision, readiness report |
| S2 | Architecture lock and autonomous research lab | ACTIVE — architecture lock DONE; later waves open | D-037, `docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md` |

## Current S2 sequence

1. DONE — lock T-002-01 through T-002-04 from retained S1 evidence (D-037).
2. DONE FOR CURRENT SLICE — inert typed contracts, read-only projections, and no venue
   client or mutation endpoint remain the boundary.
3. DONE FOR CURRENT SLICE — real LAB-799 exists, retains all current trials, selects no
   winner, and remains `UNVALIDATED` / `NOT_ELIGIBLE`.
4. PARTIAL — sourced hypothesis provenance is visible in the dashboard; the broader RA
   registry/freshness slice remains bounded S2 work.
5. DONE FOR CURRENT SLICE — bounded allowlisted local jobs and the read-only Automation
   dashboard exist after idempotent reuse evidence; S2 verification/HG-3 evidence remains open.

## S2 product slice (former product wave 7; no live execution)

1. DONE — added the attributed TradingView Widget market monitor to the live dashboard.
2. DONE — expose historical candle queries and artifact-backed signal/fill annotations.
3. Maintain inert typed order/position/portfolio/risk contracts; no paper command path is authorized.
4. DONE FOR CURRENT SLICE — OS-owned historical candle/fill chart overlays are visible;
   future richer comparison overlays remain S2 console backlog.
5. Defer Trading Platform/Broker API and real-money execution until the human-only gates are satisfied.
6. DONE — default AI work to offline mock mode and resolve provider-specific real-mode gates without exposing keys.
7. DONE FOR CURRENT SLICE — allowlisted bounded research jobs exist after identical-input
   reuse evidence. Synthetic-wallet or venue-demo activation remains outside S2 and
   requires the full later predicate.

## Parallel non-blocking work

- Strategy ingestion seed batch: evidence exists; maintain the report and record schema-fit lessons.
- AI benchmark seed: null-provider harness is complete; constrained S2 remains mock-only and real-provider credentials/runs are out of scope.
- Research gaps: close only when their S2 dependency is reached; sourced claims remain hypotheses until locally reproduced.
- Active initiatives are limited to the remaining bounded slices in 13, 14, 17, and 19.
  Initiative 13 has source-provenance evidence but not the full RA lifecycle; Initiative
  17 has bounded dashboard/job visibility but not a general observability stack.
  Initiative 12 ontology work remains deferred unless a concrete dependency is recorded.

## Human gates and explicit blockers

- HG-2 operator review is complete (D-036); constrained S2 architecture/research work is active.
- AI provider credentials and real-provider calibration remain outside D-036 and require separate future authority.
- Venue eligibility, API permissions, fees, capital, tax, and any live-trading approval remain human-only.

## Stage gates

All S1 evidence gates in `docs/program/PROGRAM_PLAN.md` are satisfied, the prototype
decision is recorded, `make check` passes, and the operator has reviewed the evidence.
S1 completion does not authorize real-money trading.

S2 exit requires the verification package and HG-3. No strategy, synthetic wallet,
paper/demo/testnet venue connection, credentials, order routing, live trading, or real
money is authorized. B2 remains `INCOMPLETE_NOT_APPROVABLE` and rejected for paper. AI
cannot approve or trade.
