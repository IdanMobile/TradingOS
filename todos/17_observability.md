# Initiative 17 — Observability (S2)

Requirement source: AD §AC. Entry: S2. Bounded job/dashboard visibility exists; a
general observability stack remains deferred unless evidence justifies it.

## T-017-01 Structured logging standard + env tagging (S1 does the minimum inside T-003-02; this task formalizes)
- Status: **DONE FOR BOUNDED S2 2026-07-10** — `OBSERVABILITY_BOUNDARY_REPORT.md`
  records the current standard: JSON artifacts, SQLite job rows, environment mode fields,
  and dashboard read models are the structured records; no global logging framework is
  adopted without a process/host boundary.
## T-017-02 Metrics counters (data freshness, API failures, job stats) surfaced in ops view
- Status: **DONE FOR BOUNDED S2 SLICE 2026-07-10** — the dashboard surfaces jobs
  counts, schedule state, integrity, worker mode, stale refresh handling, and API failure
  states without adding a general metrics stack.
## T-017-03 Evaluate Prometheus/Grafana adoption vs DB-counter sufficiency (evidence-based; licenses fine — REG §4)
- Status: **REJECTED FOR BOUNDED S2 2026-07-10** — DB counters and dashboard projection
  are sufficient for the single-operator local lab. Reopen on queue saturation, repeated
  worker failures, or a multi-host/process requirement.
## T-017-04 OTel façade decision (GenAI semconv stability check at S2 — REG §4 churn warning)
- Status: **REJECTED FOR BOUNDED S2 2026-07-10** — no real provider telemetry or
  distributed tracing boundary exists. Re-evaluate before real-provider benchmark or
  multi-process tracing.
## T-017-05 AI cost telemetry into cost-intelligence views
- Status: **DEFERRED-CREDENTIALS 2026-07-11** — operator selected the
  credentials-configured action, but environment recheck found no `OPENAI_API_KEY`,
  `GOOGLE_API_KEY`, or `ANTHROPIC_API_KEY`. Mock/null-provider work has no provider
  spend; retained local evidence cost/reuse is covered by RA cost amortization. Reopen
  with an authorized real-provider benchmark and credentials visible to the worker.
  Evidence: `artifacts/reports/AI_COST_TELEMETRY_CREDENTIAL_RECHECK_2026_07_11.md`.

Acceptance pattern for all: adopted OR rejected with evidence; no tool adopted for résumé value.
