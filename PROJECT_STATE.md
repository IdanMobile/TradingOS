# Trading Intelligence OS — Project State

Last updated: 2026-07-06 (evening — S1 execution started)
Package version: v8 (planning system) + S1 execution commits
Status: **S1 prototype execution IN PROGRESS.** Not approved for full production build or real-money trading.

## Current phase

S0 finished 2026-07-06. **S1 started same day.** Progress:

- **HG-1 intake gate: PASSED** — `artifacts/reports/PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md` (AI keys: add later ×3; MLflow/DVC: fully local).
- **Initiative 03 (repository foundation): DONE** — T-003-01..05 all complete. Git repo live; AD §F tree + module skeletons; idempotent `scripts/bootstrap.py`; one-command local gate (`make check`: ruff+mypy-strict+pytest incl. architecture dependency-law test, decision-ID uniqueness, secret scan — proven failable); 5 engine envs built+smoke-tested (freqtrade 2026.6, nautilus 1.230.0, vectorbt 1.1.0, lean CLI 1.0.227, hummingbot 2.15.0 digest-pinned); security review #1 PASS (0 secrets, 0 blocking, 6 findings fixed) at `artifacts/reports/SECURITY_REVIEW_01.md`; pre-commit secret-scan hook auto-installed; pip-audit clean.
- **T-001-01 / RG-03: CLOSED** — vectorbt 1.1.0 license verified from installed dist-info: Apache 2.0 + Commons Clause (internal use OK). Evidence `engines/vectorbt/LICENSE_CAPTURED.txt`. RG-04 closed via per-engine isolation (CG-10/CG-11 in gap matrix).
- **Initiative 04 (data foundation): DONE — EG-1 evidence complete.** DS-CRYPTO-SPOT-BAKEOFF-V1 frozen: 396 raw files (all official-checksum-verified), 1,637,118 normalized rows across 6 tables (BTCUSDT/ETHUSDT × 5m/15m/1h, 2021-01-01→2026-06-30), decimal128 precision, Amendment A1 µs/ms detection (48 ms + 18 µs files per table, boundary goldens on real rows), quality PASS, double-regeneration identical hashes, independent audit PASS_WITH_NOTES zero discrepancies. Artifacts: `artifacts/datasets/` (frozen manifest, quality report, audit).
- **Initiative 05 (strategy domain): DONE.** Canonical spec model + validator (property-tested), immutable StrategyVersion, baselines B1–B4 VALID with hand-derived + independently recomputed micro-fixture goldens (`fixtures/strategies/baselines/`, `fixtures/micro/`).
- **Initiative 18: T-018-01/03 DONE** (secret hygiene incl. artifacts; license audit — core venv copyleft-free, planted AGPL flagged); T-018-02 awaits T-010-01; T-018-04 recurring.
- **Initiative 06 (bake-off): T-006-01 DONE** (EngineAdapter port, NormalizedResult, CapabilityReport, mandatory F/S grid, fee recomputation audit). Engine lanes T-006-02..05 next.
- Local gate: 63 tests green (`make check` <2 min).
- **T-006-02 Freqtrade lane IN PROGRESS**: full matrix B1–B4 × {F0/S0, F1/S1} ran OK on the frozen dataset (up to 102k roundtrips/run); normalized to canonical decimal parquet; fee/PnL audit PASS all runs (max dev 5e-9); determinism PASS (byte-identical rerun); slippage CapabilityGap documented; lookahead-analysis flag root-caused as execution-state artifact with numeric proof (`artifacts/bakeoff/freqtrade/LOOKAHEAD_ANALYSIS_B2.md`). Remaining: hyperopt retention probe, dry-run probe, signal parity vs micro goldens.
- **T-006-06 vectorbt probe IN PROGRESS**: 34-combo B2 sweep over 577,803 bars in 15.0s (1.31M bar-combos/s), all trials retained (`artifacts/bakeoff/vectorbt/`).
- Semantic note for parity: freqtrade compounding unlimited-stake + fees collapses executed-trade counts (F1/S1 2,501 vs F0 83,996 roundtrips on B2) — parity runs should pin a fixed stake.
- Next: remaining T-006-02 probes → T-006-03 Nautilus lane → T-006-04 LEAN (Docker) → T-006-05 Hummingbot → T-006-07 parity; then {07, 08} per TODO order.

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

Continue S1 execution order: **initiative 04** (`todos/04_data_foundation.md`) — canonical dataset DS-CRYPTO-SPOT-BAKEOFF-V1 freeze with Amendment A1 (µs timestamps in files dated ≥2025-01-01; boundary golden test). Then {05, 18} → 06 → {07, 08} → 09 → 14 → 19, with 10 and 11 in parallel.

## Exit condition of next phase (unchanged)

Satisfy `specs/CRYPTO_SPOT_MVP_VERTICAL_SLICE_V1.md` and produce `decisions/PROTOTYPE_EVIDENCE_DECISION.md`; then HG-2 operator review gates S2.
