# Initiative 02 — Architecture Foundation (S2 lock complete)

Purpose: convert AD.md PROVISIONAL items to Approved/Rejected using S1 evidence. Entry criteria satisfied: EG-1..7 complete + HG-2 approved (D-036). Execute under `docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md`. Skill: architect (R9 review) + operator. Status: **DONE 2026-07-10 (D-037); S2 remains active**.

## T-002-01 Resolve AD-01/AD-03/AD-10 (monolith, DB path, jobs) against S1 telemetry (RG-15)
- Acceptance: decision-log entry with evidence; AD.md maturity labels updated. Complexity: M. Status: **DONE 2026-07-10** — D-037 records the modular-monolith, SQLite/PostgreSQL-trigger, and bounded-jobs lock; AD-01/03/10 are `APPROVED S2`.

## T-002-02 Adopt engine role selections from HG-2 into AD §K
- Acceptance: per-engine role decisions recorded; non-selected/deferred adapters and normalized artifacts retained as evidence-only/deferred assets, not deleted, and excluded from general S2 execution. Status: **DONE 2026-07-10** — D-037 and AD §K record vectorbt, Freqtrade, NautilusTrader, Hummingbot, and LEAN roles; the changelog records the retention rule.

## T-002-03 Finalize lineage architecture from EG-3 verdict
- Acceptance: AD-05 resolved; storage/serialization decisions (type catalog §0 note) locked. Status: **DONE 2026-07-10** — D-037 locks Parquet/DuckDB and MLflow+DVC behind ports; AD-04/05 and the type catalog carry the approved boundaries.

## T-002-04 S2 scope cut for the console + inert contracts
- Acceptance: S2 implementation plan derived from MVP_SCOPE + prototype lessons; only initiatives 13/14/17/19 activated for bounded S2 work, with initiative 12 deferred unless a concrete ontology dependency appears. Status: **DONE 2026-07-10** — D-037, the S2 plan, roadmap, and canonical TODO index define the cut.

Boundary: architecture work may define inert contracts and research operations only.
It may not approve a strategy; B2 remains `INCOMPLETE_NOT_APPROVABLE` and rejected for
paper. It may not activate a synthetic wallet, venue connection, credentials, order
routing, live trading, real money, or AI approval/trading authority.
