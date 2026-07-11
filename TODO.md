# TODO — Canonical Task Index (Trading Intelligence OS)

Status: S2 architecture lock recorded 2026-07-10 (D-037). This is the task index; tasks live in `todos/NN_*.md`. Program logic (stages, gates, critical path) lives in `docs/program/PROGRAM_PLAN.md`. The SSOT decides what is *authorized*; this index decides what is *next inside the authorized scope*.

## Field conventions (apply to every task unless the task overrides them)

- **Defaults**: Human approval: No · Credentials: none · Rollback: delete generated outputs; no shared state mutated · Parallelizable: No · Status: TODO · Maturity: Planned.
- Every task states: ID, Title, Purpose, Requirement (REQ-nn from traceability matrix + source spec), Dependencies/Blocks, Actions, Outputs (exact files), Tests/Acceptance, Failure condition, Skill/agent, Complexity (S/M/L).
- A task is DONE only when its acceptance criteria have evidence artifacts; "looks done" is not a status.

## Initiative index

| # | File | Stage | Purpose | Critical path? |
|---|---|---|---|---|
| 00 | `todos/00_program.md` | S0 | governance, state upkeep, package integrity | — |
| 01 | `todos/01_research_completion.md` | S0/S1 | close open research gaps (RG-xx) | no |
| 02 | `todos/02_architecture_foundation.md` | S2 | architecture lock from retained S1 evidence | **done (D-037)** |
| 03 | `todos/03_repository_foundation.md` | S1 | WS1 bootstrap: repo, envs, gates, security | **yes** |
| 04 | `todos/04_data_foundation.md` | S1 | WS2 canonical dataset | **yes** |
| 05 | `todos/05_strategy_domain.md` | S1 | canonical spec model + 4 baselines | **yes** |
| 06 | `todos/06_engine_bakeoff.md` | S1 | WS3+WS4 engines + parity | **yes** |
| 07 | `todos/07_experiment_lineage.md` | S1 | WS5 MLflow/DVC prototype + evidence link | **yes** |
| 08 | `todos/08_backtesting.md` | S1 | experiment ledger + run execution | **yes** |
| 09 | `todos/09_validation.md` | S1 | WS6 gates G1–G11 harness | **yes** |
| 10 | `todos/10_strategy_ingestion.md` | S1 | WS7 10-item seed batch | no |
| 11 | `todos/11_ai_agent_eval.md` | S1 | WS8 benchmark harness + fixtures | no |
| 12 | `todos/12_dictionary_ontology.md` | S2 bounded done | concept tables + FIBO-provenance seed; full ontology deferred | no |
| 13 | `todos/13_research_assets.md` | S2 bounded done / deferred cost view | sourced research/hypothesis and RA registry slice | S2 |
| 14 | `todos/14_dashboard.md` | S1 done / S2 active | existing read-only evidence and research console; no write controls | S2 |
| 15 | `todos/15_paper_trading.md` | S3 | paper lane + divergence tracking | S3 |
| 16 | `todos/16_risk_approvals.md` | S1 thin / deferred | approval evidence model retained; runtime risk rules await later gate | no |
| 17 | `todos/17_observability.md` | S2 bounded done | bounded batch/job visibility; no always-on observability stack | S2 |
| 18 | `todos/18_security.md` | S1 | secret hygiene, sandbox policy, audits | **gate** |
| 19 | `todos/19_operations.md` | S1 done / S2 active | bounded jobs only after proved idempotency; reports and state automation | S2 |
| 20 | `todos/20_future_market_expansion.md` | S3+ | perps/US-equities design-only | no |

## Execution order

S1 is closed through HG-2. S2 architecture lock (02) is done; bounded S2 delivery now
uses `{13, 14, 17, 19}` under the S2 plan. Initiative 12 remains deferred. Real
Research Lab batch evidence and a bounded read-only job/schedule projection now exist;
strategy promotion, paper/demo connectivity, and S2 exit remain unclaimed and
gate-controlled.

## Anti-vagueness rule

No task may say "build X" without exact outputs + acceptance evidence. Any task found vague during execution is split before starting, and the split is recorded in `PACKAGE_CHANGELOG.md`.
