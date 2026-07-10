# Initiative 17 — Observability (S2)

Requirement source: AD §AC. Entry: S2. Bounded job/dashboard visibility exists; a
general observability stack remains deferred unless evidence justifies it.

## T-017-01 Structured logging standard + env tagging (S1 does the minimum inside T-003-02; this task formalizes)
- Status: **DEFERRED-S2**.
## T-017-02 Metrics counters (data freshness, API failures, job stats) surfaced in ops view
- Status: **DONE FOR BOUNDED S2 SLICE 2026-07-10** — the dashboard surfaces jobs
  counts, schedule state, integrity, worker mode, stale refresh handling, and API failure
  states without adding a general metrics stack.
## T-017-03 Evaluate Prometheus/Grafana adoption vs DB-counter sufficiency (evidence-based; licenses fine — REG §4)
- Status: **DEFERRED-S2**.
## T-017-04 OTel façade decision (GenAI semconv stability check at S2 — REG §4 churn warning)
- Status: **DEFERRED-S2**.
## T-017-05 AI cost telemetry into cost-intelligence views
- Status: **DEFERRED-S2**.

Acceptance pattern for all: adopted OR rejected with evidence; no tool adopted for résumé value.
