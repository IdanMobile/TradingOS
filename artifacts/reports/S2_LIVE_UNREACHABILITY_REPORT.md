# S2 Live-Unreachability Review

Date: 2026-07-10
Status: **SUPERSEDED HISTORICAL PASS — NOT CURRENT STAGE-EXIT EVIDENCE**

> Superseded 2026-07-13: authenticated Bybit demo scripts were added and exercised
> after this review window. D-046 now quarantines those transports before network
> access, and repository tests verify the current boundary. This report cannot be
> used for HG-3/S3; a refreshed formal security review is still required.

## Scope

- dashboard API and UI surface;
- approval state transitions;
- jobs and automation runner;
- external strategy-code containment;
- validation and Research Lab authority fields.

## Evidence

| Control | Result | Evidence |
|---|---|---|
| HTTP mutation surface | PASS | `tests/test_dashboard.py` rejects POST/PUT/PATCH/DELETE/OPTIONS/HEAD and confirms the server has no `do_POST` handler |
| Dashboard execution flags | PASS | `tests/test_dashboard.py` asserts `venue_connection=NONE` and demo/paper/live orders `DISABLED` |
| Approval live states | PASS | `tests/test_approval.py` verifies live-family states raise `ApprovalError("unreachable")` |
| Job safety | PASS | `tests/test_jobs.py` covers read-only projection, allowlisted offline jobs, cancellation state, and redacted errors |
| Ingested code containment | PASS | `tests/test_ingested_code_containment.py` verifies clean environment and macOS network deny for untrusted code |
| Validation authority | PASS | `artifacts/validation/B2_F0_S0/validation_summary.json` remains `INCOMPLETE_NOT_APPROVABLE`; promotion eligibility is false |
| Research Lab authority | PASS | `artifacts/research_lab/v0/LAB-799f7d81843d15aaf3b161036a4cd543ac37a709cb1e2ecc72a161f7348488fa/lab_run.json` selects no winner and exposes no execution authority |

Focused verification run:

```text
uv run pytest tests/test_s2_restore_replay.py tests/test_validation_package.py tests/test_dashboard.py tests/test_approval.py tests/test_ingested_code_containment.py tests/test_jobs.py
100 passed
```

## Result

At the 2026-07-10 review snapshot, no paper/demo/testnet venue connection,
credential-bearing client, order route, live command, approval-write endpoint,
synthetic wallet, or real-money capability was present or authorized in S2. This
historical conclusion does not describe the later demo scripts or replace D-046.
