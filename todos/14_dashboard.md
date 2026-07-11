# Initiative 14 — Dashboard (S1 WS9 read-only; S2 console)

Requirement source: SSOT WS9, MVP_SCOPE §7, AD §AI.

## T-014-01 Read-only dashboard API
- Purpose: `/api/v1/` read endpoints mirroring type-catalog queries for the six MVP views. Requirement: REQ-048.
- Acceptance: contract tests pin schemas; zero write endpoints (test enforces). Complexity: M. Dependencies: first producers (T-004-04, T-008-01). Skill: R7. Status: **DONE 2026-07-10** — dashboard/status/market projections are tested; unapproved inputs fail; no POST or order write surface exists.

## T-014-02 Evidence surface (Streamlit — AD-06)
- Purpose: six views (datasets, runs, strategies, engine comparison, validation status, evidence links). Requirement: REQ-049 (WS9 exit).
- Actions: single-app Streamlit over the API or direct read models; empty states; environment banner.
- Acceptance: every S1 evidence artifact reachable by browsing; operator can trace dataset→run→validation→decision without touching the filesystem. Complexity: M. Status: **DONE FOR S1 2026-07-10** — the real OS dashboard, TradingView monitor, canonical candle/fill chart, evidence registry, validation gates, workspace status, and HG-2 readiness are live at `http://127.0.0.1:8765`; S2 entity-detail UX remains deferred.

## T-014-03 S2 Automation dashboard projection
- Purpose: expose the bounded local jobs queue, retained results, recurring schedule,
  and no-trading automation boundary as a read-only S2 console view. Requirement:
  S2 plan wave S2-4.
- Acceptance: `build_jobs_projection(root)` snapshots `artifacts/jobs/jobs.sqlite3`
  without mutation; focused jobs/dashboard tests pass; full `make required` passes;
  browser verification covers Overview, Research Lab, Automation, and Market Monitor at
  375/768/1024/1440 px. Status: **DONE 2026-07-10** — Automation shows 3 succeeded
  `RESEARCH_LAB_V0` jobs, latest persisted job reused LAB-799, recurring six-hour
  schedule, integrity PASS, allowlist-only worker mode, and explicit no POST / no venue
  / no order / no paper-demo-live controls.

## S2 backlog (not authorized in S1 — recorded to prevent scope creep INTO S1)
- T-014-10 console IA spike (Next.js+shadcn, AD-07): Status **REJECTED FOR BOUNDED S2 2026-07-10** — `DASHBOARD_BOUNDARY_REPORT.md` records that the current local read-only dashboard satisfies the evidence surface; a rewrite adds churn without a missing workflow.
- T-014-11 entity-detail layout pattern: Status **REJECTED FOR BOUNDED S2 2026-07-10** — existing tables/artifact links expose current entities; detail pages reopen only with repeated inspection needs or a validated candidate.
- T-014-12 global search (FTS): Status **DONE FOR BOUNDED S2 2026-07-10** — Dictionary view projects `DICTIONARY_CONCEPTS_V1` concepts, aliases, contexts, explicit gaps, and FIBO provenance from the dashboard API; `ConceptRegistry` uses SQLite FTS5 and tests cover query behavior.
- T-014-13 comparisons UI: Status **REJECTED FOR BOUNDED S2 2026-07-10** — comparison evidence remains visible in validation/research reports and Research Lab score dimensions; richer UI waits for a candidate with positive evidence.
- T-014-14 approvals UI (write-path, HG-gated): Status **DEFERRED-HG** — no approval write path is authorized; dashboard remains read-only.
