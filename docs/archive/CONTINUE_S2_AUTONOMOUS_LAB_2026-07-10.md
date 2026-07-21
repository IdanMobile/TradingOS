# Trading OS — Clean-Session Continuation Handoff

Created: 2026-07-10
Workspace: `/Users/user/Downloads/trading_os_project_package`
Current stage: **S2 autonomous research lab, constrained/no-money**

## Read first

1. `/Users/user/.codex/attachments/fe0b0e48-e77c-463c-a781-b006559b88f6/goal-objective.md`
2. `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md`
3. `docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md`
4. This handoff.

The operator explicitly approved HG-2/S2 work. This does **not** approve any strategy,
paper/demo venue connection, credentials, order routing, live trading, or real money.
Current evidence must remain `UNVALIDATED` / `NOT_ELIGIBLE` until all gates pass.

## What is now real

- D-036 records constrained S2 entry; D-037 records the S2 architecture lock.
- Architecture: modular monolith, SQLite operational path, Parquet/DuckDB analytics,
  MLflow+DVC behind ports, read-only console, inert trading contracts.
- Primary-source registry: 10 original papers, all hypothesis-only/noneligible.
- Explicit B2/B3/B4 hypothesis proxies are linked to canonical, content-derived
  StrategyVersion IDs with semantic-loss notes.
- Research Lab v0 is content-addressed, path-confined, mock/offline-only, retains all
  successes/failures, emits provenance + independent scorecards, and has no execution
  authority.
- Real lab batch:
  `artifacts/research_lab/v0/LAB-702f87fbfb18d6ebce2c0822c620c9db6ec0650a5d205cacc4178f8dd6af43bc/`
  - 3 experiments, 66/66 completed, 66 evidence rows.
  - `execution_authority=NONE`, `venue_connection=NONE`, paper/live `DISABLED`.
  - Seven evidence blockers remain; no winner or approval.
- Persisted job DB: `artifacts/jobs/jobs.sqlite3` (schema v2, mode 0600).
  - `JOB-702e68ef5ab6acaf588c`: SUCCEEDED, first current-code LAB-702 run.
  - `JOB-3a92af780816a2561498`: SUCCEEDED, reused LAB-702 with unchanged artifacts.
  - Recurring schedule: `s2-production-offline-research-lab-v0-every-6h-v1`, every
    21,600 seconds, next due `2026-07-11T00:00:00+00:00`.
  - No daemon is running, so the schedule will not execute until deliberately started.
- Hardened job runner passed its final independent review: descriptor-relative storage,
  atomic migrations/publication, cancellation, leases, bounded retries, process-group
  cleanup, credential-free environment, macOS network-denying sandbox, no shell and no
  trading job types.
- Latest fully verified suite before the paused integration edit: **278 tests**, Ruff,
  format, strict mypy; job stress and independent reviews passed.
- Dashboard is currently running at `http://127.0.0.1:8765` (exec session 4250).
  The refreshed S2 UI was browser-verified with LAB evidence and no overflow at
  375/768/1024/1440.

## Important paused state

The operator stopped work while two subagents were integrating job/automation status
into the dashboard. Both were shut down immediately. Therefore these files may contain
partial, unverified edits and must be inspected first:

- `src/tios/services/jobs/projection.py`
- `src/tios/services/jobs/__init__.py`
- `src/tios/services/dashboard_api/status.py`
- `src/tios/services/dashboard_ui/dashboard.html`
- `tests/test_jobs.py`
- `tests/test_dashboard.py`

`git diff --check` currently passes, but no post-shutdown test run proves that partial
integration. Do not assume it is complete.

## Exact next actions

1. Inspect the six paused-integration files and current diff; preserve all existing work.
2. Finish the read-only `build_jobs_projection(root)` contract without mutating the DB.
3. Finish the dashboard Automation view: queue counts, two jobs, reused result, recurring
   schedule/next due, integrity state, allowlist, and explicit no-trading boundary.
4. Run focused jobs/dashboard tests, Ruff/format, strict mypy, then `make required`.
5. Restart the dashboard and browser-verify Overview, Research Lab, Automation, and
   Market Monitor at desktop + mobile widths. Keep the page open for the operator.
6. Only after all checks pass, start the confined local worker loop if desired:
   `.venv/bin/python scripts/run_job_worker.py run-loop`
   Keep its exec session alive and confirm the future schedule is visible; do not force
   an early occurrence.
7. Update project state/TODO/report artifacts with LAB-702 and queue evidence.
8. Regenerate `PACKAGE_INTEGRITY_MANIFEST.md` last; it currently has stale hashes from
   controlled-file edits.
9. Run final independent code/security/replay/live-unreachability audit. Prepare S2 exit
   evidence, but do not claim HG-3 or enable paper/demo/live.

## Current known blockers (expected, not bugs)

- No candidate is validated or promotion-eligible.
- Economic/drawdown validation, parameter-neighborhood robustness, walk-forward,
  regime stability, baseline superiority, multiple-testing/G10, and cross-engine
  reproduction remain incomplete.
- LEAN/Hummingbot follow-ups remain environment/Docker constrained.
- HG-3 and all later paper/live decisions are human-only.

## Useful commands

```sh
cd /Users/user/Downloads/trading_os_project_package
git status --short
git diff --check
.venv/bin/python scripts/run_job_worker.py list --limit 10
.venv/bin/python scripts/run_job_worker.py status JOB-3a92af780816a2561498
uv run pytest -q tests/test_jobs.py tests/test_dashboard.py
make required
curl -fsS http://127.0.0.1:8765/api/v1/status | python3 -m json.tool
```

## Suggested prompt for the new session

> Continue Trading OS from
> `handoffs/CONTINUE_S2_AUTONOMOUS_LAB_2026-07-10.md`. Read the goal objective and
> authoritative handoff first. Preserve the dirty worktree. Finish and verify the paused
> automation-dashboard integration, restart and browser-test the real dashboard, then
> continue the ordered S2 plan. Use parallel subagents for independent tracks. Do not
> enable paper/demo/live or real money; stop only at a genuine human-only gate.
