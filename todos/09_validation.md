# Initiative 09 — Validation Harness (S1, WS6) — CRITICAL PATH

Requirement source: `specs/BACKTESTING_VALIDATION_BLUEPRINT_V1.md`. Skills: R7 + SKILL_BACKTEST_RED_TEAM + SKILL_VALIDATION_STATS_SPECIALIST.

## T-009-01 Gates G1–G3 (reproducibility, data/timestamp integrity, semantic correctness)
- Requirement: REQ-034. Actions: implement as composable checks over RUN artifacts; G1 rerun-parity harness; G3 spec-vs-implementation signal sampling.
- Acceptance: each gate has a must-FAIL fixture and a passing fixture (TEST_MASTER_PLAN rule). Complexity: L. Dependencies: T-008-02. Status: **DONE 2026-07-10** — composable checks, pass/fail tests, rerun evidence, dataset quality, and exact B1–B4 signal parity are integrated into the retained package.

## T-009-02 Gate G4 leakage checks
- Requirement: REQ-035. Actions: Freqtrade lookahead-analysis integration where applicable; cross-engine temporal leakage tests; feature-availability audit; `fixtures/leaky/` corpus.
- Acceptance: every leaky fixture rejected; clean fixture passes. Failure: any leaky fixture passing = initiative-blocking bug. Complexity: L. Status: **DONE WITH WARN 2026-07-10** — temporal leak fixtures fail closed; recursive indicator lookahead passes; native Freqtrade execution-state analysis retains an explicit WARN because it overrides requested stake settings.

## T-009-03 Gates G5–G9, G11 (cost stress, OOS, walk-forward, robustness, regime, benchmark comparison)
- Requirement: REQ-036. Actions: implement over grid runner; materialize exact OOS dates from dataset manifest **before** any optimization (G6 rule); parameter-neighborhood surface; ex-post regime segmentation; baseline comparisons.
- Acceptance: one full validation package on ≥1 baseline strategy (EG-4 core). Complexity: L. Dependencies: T-009-01, T-008-03. Status: **DONE — NEGATIVE RESULT 2026-07-10** — B2 package includes cost, OOS, 18-window walk-forward, five-neighbor robustness, regime, benchmark, red-team, and independent risk-precondition evidence; B2 is not promotion-eligible.

## T-009-04 G10 method-candidate work (PBO/DSR)
- Requirement: REQ-037 (RG-07). Actions: SKILL_VALIDATION_STATS_SPECIALIST review vs primary papers; known-answer fixtures; implement only after method validation; else record method-candidate status honestly (SSOT: do not claim full production validation).
- Acceptance: METHOD_VALIDATED verdict or explicit deferral record. Complexity: L. Parallelizable: Yes. Status: **DONE — METHOD FIXTURES VALIDATED / PRODUCTION G10 STILL INACTIVE** — `src/tios/validation/multiple_testing.py` and `tests/test_multiple_testing_methods.py` retain synthetic known-answer fixtures for PBO/CSCV and DSR arithmetic. `artifacts/validation/G10_METHOD_FIXTURES_2026_07_11.json` records fixture evidence. Candidate-specific integration and independent recomputation remain required before production G10 can PASS.

## T-009-05 Validation report + red-team pass
- Requirement: REQ-038. Actions: assemble `artifacts/reports/BACKTEST_VALIDATION_REPORT.md` (EG-4); run SKILL_BACKTEST_RED_TEAM on the package; attach red-team report.
- Acceptance: report + red-team verdict present; hard-fail logic demonstrated (a deliberately-bad baseline must fail). Complexity: M. Dependencies: T-009-01..03. Status: **DONE — NO APPROVAL** — red-team report and machine-readable attack record are present; G4 remains WARN and B2 remains rejected.
