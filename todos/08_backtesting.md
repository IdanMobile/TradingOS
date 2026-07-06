# Initiative 08 — Backtesting / Experiment Ledger (S1) — CRITICAL PATH

Requirement source: AD §D Experimentation context; type catalog §2 EXP/RUN. Skill: R7.

## T-008-01 Experiment ledger (EXP/RUN records)
- Purpose: declared searches + all-trial retention. Requirement: REQ-026.
- Actions: implement `experiment` module: declare experiment (hypothesis ref, SV, dataset, engine, param space, scenario set, selection procedure), record runs w/ env manifests + artifact refs; append-only.
- Acceptance: retention invariant test (winner references population); append-only test. Complexity: M. Dependencies: T-007-04. Status: TODO.

## T-008-02 Run executor over engine adapters
- Purpose: one command: SV × dataset × engine × scenario → RUN with artifacts. Requirement: REQ-027.
- Actions: jobs-module integration, content-addressed inputs, idempotent rerun, failure preservation.
- Acceptance: idempotency test; crash-mid-run leaves FAILED status + partial artifacts. Complexity: M. Dependencies: T-008-01, T-006-01. Status: TODO.

## T-008-03 Fee/slippage scenario grid runner
- Purpose: mandatory 6-cell grid per `specs/FEE_AND_SLIPPAGE_ASSUMPTION_PACKAGE_V1.md`. Requirement: REQ-028.
- Actions: scenario expansion (F0/S0, F1/S1, F1/S2, F1/S3, F2/S2, F2/S3), per-cell runs, sensitivity table artifact.
- Acceptance: grid completeness test (missing cell fails report build); F0/S0 flagged diagnostic-only in every artifact. Complexity: S. Dependencies: T-008-02. Status: TODO.
