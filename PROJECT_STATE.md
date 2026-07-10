# Trading Intelligence OS — Project State

Last updated: 2026-07-10 (HG-2 approved; constrained S2 active)
Package version: v8 (planning system) + S1 evidence + S2 governance entry
Status: **S2 AUTONOMOUS RESEARCH LAB ACTIVE (CONSTRAINED).** No strategy, venue connection, or real-money trading is approved.

## Current phase

S0 finished 2026-07-06. S1 evidence execution is complete and **HG-2 was approved by
the operator on 2026-07-10 (D-036)**. Constrained S2 work now follows
`docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md`. Retained S1 evidence and constraints:

- **HG-1 intake gate: PASSED** — `artifacts/reports/PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md` (AI keys: add later ×3; MLflow/DVC: fully local).
- **Initiative 03 (repository foundation): DONE** — T-003-01..05 all complete. Git repo live; AD §F tree + module skeletons; idempotent `scripts/bootstrap.py`; one-command local gate (`make check`: ruff+mypy-strict+pytest incl. architecture dependency-law test, decision-ID uniqueness, secret scan — proven failable); 5 engine envs built+smoke-tested (freqtrade 2026.6, nautilus 1.230.0, vectorbt 1.1.0, lean CLI 1.0.227, hummingbot 2.15.0 digest-pinned); security review #1 PASS (0 secrets, 0 blocking, 6 findings fixed) at `artifacts/reports/SECURITY_REVIEW_01.md`; pre-commit secret-scan hook auto-installed; pip-audit clean.
- **T-001-01 / RG-03: CLOSED** — vectorbt 1.1.0 license verified from installed dist-info: Apache 2.0 + Commons Clause (internal use OK). Evidence `engines/vectorbt/LICENSE_CAPTURED.txt`. RG-04 closed via per-engine isolation (CG-10/CG-11 in gap matrix).
- **Initiative 04 (data foundation): DONE — EG-1 evidence complete.** DS-CRYPTO-SPOT-BAKEOFF-V1 frozen: 396 raw files (all official-checksum-verified), 1,637,118 normalized rows across 6 tables (BTCUSDT/ETHUSDT × 5m/15m/1h, 2021-01-01→2026-06-30), decimal128 precision, Amendment A1 µs/ms detection (48 ms + 18 µs files per table, boundary goldens on real rows), quality PASS, double-regeneration identical hashes, independent audit PASS_WITH_NOTES zero discrepancies. Artifacts: `artifacts/datasets/` (frozen manifest, quality report, audit).
- **Initiative 05 (strategy domain): DONE.** Canonical spec model + validator (property-tested), immutable StrategyVersion, baselines B1–B4 VALID with hand-derived + independently recomputed micro-fixture goldens (`fixtures/strategies/baselines/`, `fixtures/micro/`).
- **Initiative 18: T-018-01/03 DONE** (secret hygiene incl. artifacts; license audit — core venv copyleft-free, planted AGPL flagged); T-018-02 awaits T-010-01; T-018-04 recurring.
- **Initiative 06 (bake-off): T-006-01 DONE** (EngineAdapter port, NormalizedResult, CapabilityReport, mandatory F/S grid, fee recomputation audit). Freqtrade and Nautilus have B1–B4 evidence; Hummingbot and LEAN retain explicit gaps.
- **T-006-02 Freqtrade lane DONE WITH CONSTRAINTS**: full matrix B1–B4 × {F0/S0, F1/S1}, exact micro signal parity, determinism, recursive analysis, bounded hyperopt retention, dry-run, precision/failure probes, fee audits, and export pass. Native lookahead forced-state behavior and slippage remain explicit WARN/capability gaps.
- **T-006-06 vectorbt probe DONE**: B2/B3/B4 ran 66 trials over 577,803 bars; all 66 are retained in Parquet and the append-only ledger, no winner selected, and binding overfit controls keep vectorbt an accelerator only.
- **T-006-03 Nautilus lane:** bounded B1–B4 × {F0/S0, F1/S1} × {run1,run2} is now physically present; all 16 runs are byte-deterministic across normalized trade/equity/metric artifacts and all fee audits pass.
- **Cross-engine parity:** three full-period BTC contexts are comparable with zero unexplained available-lane residuals. B1 timing differences and B2 execution/order-state plus missing-data behavior are retained; B2 is not fill/P&L parity.
- **Initiative 07 (lineage): DONE.** Local MLflow 3.14.0 + DVC 3.66.1 Tests A/B/C pass reproduce, compare, trace, domain-link, local-first, and replaceability gates; AI trace is explicitly null-provider/mock-only. The fresh clone restored the exact 577,803-row BTC dataset and matched deterministic reproduction output. Decision D-035 selects the composition for S2 architecture input.
- **S1 approval/risk/security closure:** contextual approval transitions require evidence, paper states require a human decision, and all live states are unreachable; every validation package now carries independent no-live/cost-grid/drawdown-tail/promotion preconditions; external ingested code is subprocess-contained with no inherited secrets or network. Security Review #2 passes with zero blockers.
- **S2 entry:** architecture/research-console work, sourced strategy research, offline backtesting, retained-trial scoring, validation, and eventual demo preparation are active. Docker-dependent LEAN and Hummingbot B3/B4 remain exact follow-up constraints.
- **Governance re-check (gov-02, 2026-07-07): PASS.** `make check` green (63 tests, ruff, mypy-strict). Fixed a real gate gap: D-027/D-028 used `##` headings, exempting them from the decision-ID uniqueness regex (`### D-NNN` only) — normalized to `###` (D-033); all 32 IDs now covered. No invented decision-category labels found in `DECISION_LOG.md` (the 7-label taxonomy from SSOT §7 applies to the `decisions/`/`research/`/`artifacts/reports/` decision artifacts, most of which are correctly not-yet-created since bake-off (initiative 06) is still in progress). No stop-condition triggers pending or worked around.
- **S1 execution closure (2026-07-10):** live Trading OS evidence dashboard is operational with an attributed TradingView Market Monitor plus an OS-owned canonical-candle chart and retained B2 markers; read-only APIs explicitly disable paper/live orders; staged TradingView direction is D-034; offline-first AI/provider gates are implemented; local MLflow+DVC lineage is selected in D-035; Freqtrade and vectorbt lanes are closed with constraints; bake-off contains 30 normalized runs plus 66 ledgered accelerator trials. B2 remains `INCOMPLETE_NOT_APPROVABLE`, G4 WARN, G10 deferred, and rejected for paper. Full local gate: 123 tests, ruff, format, mypy-strict.
- **D-036 boundaries:** no strategy approval; no synthetic wallet activation; no paper/demo/testnet venue connection; no credentials, order routing, live trading, or real-money authorization. AI cannot approve or trade.
- **S2 Research Lab v0 and automation evidence (2026-07-10):** latest real retained
  batch `LAB-799f7d81843d15aaf3b161036a4cd543ac37a709cb1e2ecc72a161f7348488fa`
  completed 3 experiments / 66 trials with 66 evidence rows, all marked
  `UNVALIDATED` / `NOT_ELIGIBLE`; no winner is selected. Score dimensions now bind to
  retained validation evidence: economic performance, drawdown severity, parameter
  neighborhood, walk-forward, and baseline superiority are negative/failing; regime is
  descriptive-only; multiple-testing and cross-engine reproduction remain blockers.
  The local SQLite jobs DB has three succeeded `RESEARCH_LAB_V0` records; the latest
  persisted job reused the unchanged LAB-799 artifacts, and a six-hour recurring
  offline schedule is visible with next due `2026-07-11T00:00:00+00:00`. The Automation
  dashboard is read-only/browser-verified at 375/768/1024/1440 px with no POST, queue
  mutation, credential, venue, paper/demo/live, or order control.
- **S2 verification package (2026-07-10):** restore/replay verification PASS
  (`artifacts/reports/S2_RESTORE_REPLAY_REPORT.md`), live-unreachability PASS
  (`artifacts/reports/S2_LIVE_UNREACHABILITY_REPORT.md`), and requirement audit BLOCKED
  before S2 exit (`artifacts/reports/S2_REQUIREMENT_AUDIT.md`) because no candidate is
  `COMPLETE_APPROVABLE` or promotion-eligible.
- **S2 seed-candidate cycle (2026-07-10):**
  `SEEDCYCLE-5bd3faa48ad47e23f0af45e12c0e613c843215fda324b3821b58b35d53da5c1a`
  retained 16 offline trials across the two seed strategies already marked
  `REPRODUCED` (`STRAT-QC1-dual-ma-cross`, `STRAT-QC2-donchian-breakout`). The cycle
  reused idempotently, selected no winner, and kept both candidates `UNVALIDATED` /
  `NOT_ELIGIBLE`; the simple next-open all-in proxy is strongly negative and does not
  change S2 exit status.

## Operational SSOT (unchanged)

`handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md` remains the single operational source of truth for coding-agent execution (D-027). It was updated 2026-07-06 to reference the planning system (D-030); no competing controller exists.

## Coding authorization status (explicit, per planning mandate §25)

- Planning Complete? **YES** (this pass; see audits).
- Research Complete Enough? **YES for constrained S2 entry** — S2 sourced research remains hypothesis input, not inherited proof or strategy approval.
- Architecture Approved? **PARTIALLY — S2 resolution active.** Boundaries, contracts, principles, lifecycle, and rejections are APPROVED; S2-1 resolves remaining PROVISIONAL/UNRESOLVED items from S1 evidence.
- Prototype Execution Authorized? **YES** (D-025 + readiness gate PASS; entry condition: HG-1 intake gate).
- Constrained S2 Architecture/Research Lab Authorized? **YES** — D-036; scope is `docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md`.
- MVP Build Authorized? **NO beyond the constrained S2 research-lab/research-console scope.**
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

No blocker prevents continuing constrained S2 evidence operations. Docker is stopped,
so LEAN and missing Hummingbot follow-up lanes remain recorded constraints. B2 and the
current S2 hypothesis population remain incomplete and not approvable; this blocks
strategy promotion and demo activation, not offline research. Open items are tracked in
`MISSING_AND_OPEN_ITEMS.md`.

## Exact next action

Stop before HG-3/paper-demo preparation unless the operator explicitly authorizes a new
offline hypothesis cycle or resolves human-only blockers. The retained S2 verification
package says S2 exit is blocked by lack of a validated, promotion-eligible strategy.
The live progress surface remains `make dashboard` at `http://127.0.0.1:8765`,
including the read-only Automation view over `artifacts/jobs/jobs.sqlite3`.

## Exit condition of next phase (unchanged)

S2 exit requires the plan's verification package and HG-3. Paper/demo activation also
requires complete approvable validation, promotion eligibility, a paper-lane
architecture decision, a security pass, and new operator approval for the specific
integration. Until then, venue connections and execution remain disabled.
