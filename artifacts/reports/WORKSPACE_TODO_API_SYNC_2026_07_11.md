# Workspace TODO API Sync Report — 2026-07-11

The workspace TODO API is the project's own local dashboard API
(`make dashboard` → `http://127.0.0.1:8765/api/v1/status`), served by
`src/tios/services/dashboard_ui/server.py` over
`src/tios/services/dashboard_api/status.py`. It parses the canonical task source
(`todos/NN_*.md`, indexed by `TODO.md`) live on every request, and retains operator
decisions in `artifacts/human_decisions/workspace_decisions.jsonl` via the single
loopback POST route.

## 1. API availability

**UP.** Verified 2026-07-11: `GET /api/v1/status` returned HTTP 200 with
`schema_version: 1`, loopback-only binding.

## 2. Config variables required

None. The API is local-first, loopback-bound, credential-less by design (AD §AI/§P
operator-only rule). No `.env` entry is required or appropriate; see
`ENV_AND_CREDENTIALS_AUDIT_2026_07_11.md`.

## 3–5. Task counts and sync actions

| Metric | Value |
|---|---|
| Local canonical tasks (`todos/*.md`) before this pass | 87 |
| Workspace API tasks before this pass | 87 (identical — API parses the local files directly) |
| Tasks added this pass | 1 — **T-002-05** (dashboard write-path architecture decision) in `todos/02_architecture_foundation.md` |
| Tasks updated in API | automatic — the API projects the file change on next request (verified post-edit: total 88; T-002-05 appears in the human-gated bucket) |
| Tasks closed/marked obsolete | 0 — no obsolete task found; nothing silently deleted |

Divergence between local docs and the API is structurally impossible for task
definitions (single source), so "sync" reduces to: (a) keeping `todos/*.md` canonical,
(b) reconciling the operator-decision JSONL against task statuses.

## 6. Operator decisions on record (workspace_decisions.jsonl, 9 records)

| Task | Decision (2026-07-11) | Reconciliation status |
|---|---|---|
| T-001-03 | authorize_source_recheck | HONORED — `VENUE_ISRAEL_SOURCE_RECHECK_2026_07_11.md` done; human account checks remain deferred |
| T-000-01/03/04, T-001-06 | acknowledge_recurring | consistent — recurring governance |
| T-020-01/02/03 | authorize_design_only | HONORED — `FUTURE_MARKET_EXPANSION_DESIGN_REVIEW_2026_07_11.md`; implementation still deferred |
| T-017-05 | credentials_configured | **CONFLICT, RESOLVED** — env recheck found no provider key (`AI_COST_TELEMETRY_CREDENTIAL_RECHECK_2026_07_11.md`); task status set back to DEFERRED-CREDENTIALS with evidence in `todos/17_observability.md`. Not treated as a credential grant. |

## 7–9. Conflicts

- Found: 1 (T-017-05 decision vs environment reality). Resolved with evidence; the
  decision record is retained append-only, not deleted.
- Requiring human decision: 1 — **T-002-05**: the decision-recording POST route itself
  conflicts with the locked AD §AI / type-catalog "no POST" contract. Options are
  presented in the task; until decided, the desired architecture (GET-only) stands and
  the route is flagged as a Current Implementation Gap in AD §AI.

## 10. Gated tasks correctly represented in both systems

T-011-05 (DEFERRED-CREDENTIALS), T-015-01..04 (DEFERRED-S3), T-015-05 (DEFERRED-S4-HUMAN),
T-017-05 (DEFERRED-CREDENTIALS) — all appear in the API `gated_tasks` bucket with the
same statuses as the local files, each carrying its gate in the status string.

## 11. Remaining API blockers

None operational. One architectural decision open (T-002-05). If the operator chooses
to remove the POST route, decision recording moves to a CLI command and this report's
§6 mechanism changes accordingly.
