# Observability Boundary Report

Generated: 2026-07-10

Status: **BOUNDED S2 OBSERVABILITY COMPLETE — GENERAL STACK REJECTED FOR NOW**

## Evidence Used

- `artifacts/jobs/jobs.sqlite3` retains the local S2 job queue and schedule state.
- Dashboard `/api/v1/dashboard` projects job counts, schedule, DB integrity, worker mode,
  stale refresh, and failure state without write controls.
- `make required` passes with dashboard/jobs tests covering the read-only projection.
- No real AI provider credential, paper/demo/live venue, broker, distributed worker, or
  multi-host process boundary is authorized.

## Decisions

| TODO | Decision | Evidence |
|---|---|---|
| T-017-01 structured logging standard | DONE for bounded S2: existing JSON artifacts, job rows, and dashboard read models remain the structured operational records. No global logging framework is added. | Job DB schema v2, report artifacts, dashboard status projection |
| T-017-03 Prometheus/Grafana evaluation | REJECTED for bounded S2: SQLite counters and dashboard projection are sufficient for the single-operator local lab. | Three succeeded jobs, no queue backlog, no multi-host requirement |
| T-017-04 OTel facade decision | REJECTED for bounded S2: no real GenAI/provider telemetry or distributed tracing boundary exists. Re-evaluate before real-provider benchmark or multi-process tracing. | AI work remains mock/null-provider; no provider credentials configured |
| T-017-05 AI cost telemetry | DEFERRED-CREDENTIALS: local mock AI has no provider spend; RA cost amortization covers retained zero-cost local evidence. | `ResearchAssetRegistry.cost_amortization()` and AI-key add-later disposition |

## Reopen Triggers

- A second process or host becomes part of normal S2 operations.
- Queue saturation, repeated worker failures, or API-refresh failures become visible.
- A real AI provider credential and paid benchmark run are authorized.
- Paper/demo/live execution is separately approved by the required human gate.

Until one of those triggers occurs, observability remains deliberately local, read-only,
and artifact-backed.
