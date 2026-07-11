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

## T-002-05 Resolve dashboard workspace-decision write path vs AD §AI GET-only lock
- Purpose: `POST /api/v1/workspace-actions/decision` exists (test-pinned in
  `tests/test_dashboard.py` as the only allowed write path; used by the operator —
  9 records in `artifacts/human_decisions/workspace_decisions.jsonl`), but AD §AI and
  `docs/architecture/TYPE_AND_CONTRACT_CATALOG.md` §API lock `/api/v1/` to
  GET/HEAD/OPTIONS with no POST route. Requirement: REQ-048 (contract integrity).
- Actions: operator chooses one: (a) record a decision-log entry (next free D-nnn)
  amending AD §AI + type catalog §API to permit exactly one loopback human-decision
  recording route (no order/approval/job mutation authority), or (b) remove the POST
  route and move workspace-decision recording to a local CLI command.
- Outputs: decision-log entry + AD §AI/type-catalog §API update, or route removal PR
  with CLI replacement; updated `tests/test_dashboard.py` either way.
- Acceptance: AD, type catalog, tests, and implementation agree; gap note in AD §AI
  removed. Failure: contract and implementation continue to disagree.
- Human approval: **Yes (architecture change decision)**. Credentials: none.
- Skill: R9 architect review + operator. Complexity: S.
- Source: `artifacts/reports/AD_IMPLEMENTATION_GAP_AUDIT_2026_07_11.md`.
- Status: **DONE 2026-07-11 (D-038)** — operator approved keeping the single audited loopback workspace-decision POST route; AD §AI and TYPE_AND_CONTRACT_CATALOG §7 now record the scoped exception (operator-driven, allowlist-validated, append-only audited, test-pinned sole write path; no trading/order/credential/paper/demo/live mutation; any expansion requires a new decision gate). Gap note removed from AD §AI.
