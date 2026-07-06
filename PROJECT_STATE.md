# Trading Intelligence OS — Project State

Last updated: 2026-07-06
Package version: v8 (planning system)
Status: Planning phase COMPLETE. Ready for constrained coding-agent prototype execution (stage S1). Not approved for full production build or real-money trading.

## Current phase

S0 (planning completion) finished 2026-07-06. Next stage: **S1 — Prototype execution** per `docs/program/PROGRAM_PLAN.md`.

## Operational SSOT (unchanged)

`handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md` remains the single operational source of truth for coding-agent execution (D-027). It was updated 2026-07-06 to reference the planning system (D-030); no competing controller exists.

## Coding authorization status (explicit, per planning mandate §25)

- Planning Complete? **YES** (this pass; see audits).
- Research Complete Enough? **YES for S1** — remaining gaps are executable (RG-01, RG-10, RG-11) or non-blocking desk items (RG-02/03/05/08 with owners/triggers).
- Architecture Approved? **PARTIALLY — by design.** Boundaries, contracts, principles, lifecycle, and rejections are APPROVED; component selections marked PROVISIONAL/UNRESOLVED in `docs/architecture/AD.md` §AL await S1 evidence (D-007 stands).
- Prototype Execution Authorized? **YES** (D-025 + readiness gate PASS; entry condition: HG-1 intake gate).
- MVP Build Authorized? **NO** — requires S1 exit + HG-2 (prototype evidence approval).
- Live Trading Authorized? **NO** — S4; human-only gates untouched.

## What was added 2026-07-06 (planning pass)

- Architecture: `docs/architecture/AD.md` (§A–§AL), `MODULE_CATALOG.md`, `TYPE_AND_CONTRACT_CATALOG.md`.
- Program/product: `docs/program/PROGRAM_PLAN.md` (stages S0–S4, EG/HG gates), `docs/product/MVP_SCOPE.md`.
- Tasks: `TODO.md` + 21 initiative files under `todos/` (REQ-traced, acceptance-gated).
- Testing: `docs/testing/TEST_MASTER_PLAN.md`.
- Traceability: `docs/traceability/TRACEABILITY_MATRIX.md` (REQ-001…058 + deferred series).
- AI: `docs/ai/AGENT_ROLES.md` (R1–R9), `skills/` (README + 13 skill specs).
- Research: `research/EXISTING_CAPABILITY_REGISTRY.md` (evidence refreshed 2026-07-06), `research/RESEARCH_GAP_MATRIX.md` (9 gaps closed, 16 open with owners).
- Audits: `audits/ARCHITECTURE_COMPLETENESS_AUDIT.md`, `audits/TODO_COMPLETENESS_AUDIT.md`, `audits/RED_TEAM_PLAN_REVIEW.md`, `audits/PLANNING_HANDOFF_SIMULATION.md`.
- Decisions: D-029 (dataset µs amendment), D-030 (planning layer), D-031 (ID hygiene fix), D-032 (registry-driven candidate adjustments). Duplicate IDs renumbered to D-027/D-028.

## Material evidence updates folded in (2026-07-06)

- Binance public Spot data: timestamps microseconds from files dated 2025-01-01 → dataset spec Amendment A1.
- vectorbt OSS reactivated (v1.1.0) → probe OSS first; Backtrader/backtesting.py rejected.
- All four first-tier engines confirmed actively maintained; license boundaries recorded (Freqtrade GPL-3.0 → subprocess integration).
- MLflow 3.14 GenAI tracing mature; DVC now stewarded by lakeFS (active) → D-019 hypothesis retained/strengthened.
- Venue notes: OKX Israel-supported + demo env; Coinbase likely Israel-unavailable (RG-05); live-venue human gates unchanged.
- AI providers: no determinism guarantees → multi-sample benchmarking (AD-11); OpenAI Evals platform EOL → not a dependency.

## Unresolved blockers

None blocking S1 start. Open items tracked in `MISSING_AND_OPEN_ITEMS.md` + `research/RESEARCH_GAP_MATRIX.md`.

## Exact next action

Give the package to the coding agent with the single instruction:

`Read and execute handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md`

The agent's first initiative is `todos/03_repository_foundation.md`, first task **T-003-01 — Pre-Code Environment & Credentials Intake Gate** (interactive; requires the operator). No code before that gate passes.

## Exit condition of next phase (unchanged)

Satisfy `specs/CRYPTO_SPOT_MVP_VERTICAL_SLICE_V1.md` and produce `decisions/PROTOTYPE_EVIDENCE_DECISION.md`; then HG-2 operator review gates S2.
