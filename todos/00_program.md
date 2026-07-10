# Initiative 00 — Program Governance (S0, continuous)

## T-000-01 State upkeep discipline
- Purpose: keep PROJECT_STATE / DECISION_LOG / MISSING_AND_OPEN_ITEMS / RESEARCH_BACKLOG / PACKAGE_CHANGELOG current (SSOT §8). Requirement: REQ-030.
- Actions: after every completed task or blocker, update affected state files in the same working session.
- Outputs: updated state files. Acceptance: no state file older than the newest evidence artifact it should reference. Failure: drift found by audit.
- Skill: R7. Complexity: S. Status: ONGOING.

## T-000-02 Package integrity manifest regeneration
- Purpose: manifest hashes must match reality after any controlled edit to a required input. Requirement: REQ-031.
- Dependencies: any task editing manifest-listed files. Actions: recompute SHA-256 table; note change in PACKAGE_CHANGELOG.
- Outputs: updated `PACKAGE_INTEGRITY_MANIFEST.md`. Acceptance: verification script passes. Failure: any FAIL row.
- Skill: R7. Complexity: S. Status: **DONE 2026-07-10** — controlled-input hashes regenerated and verification passes; changelog updated.

## T-000-03 Decision-log hygiene
- Purpose: unique IDs, no silent amendments (duplicate D-022/D-023 defect class). Requirement: REQ-032.
- Actions: on every new decision: next free ID; amendments reference the amended ID explicitly.
- Acceptance: ID-uniqueness check passes (add to local gate in T-003-04). Status: ONGOING (defect fixed 2026-07-06, D-027/D-028 renumbering).

## T-000-04 Stage-exit reviews
- Purpose: run PROGRAM_PLAN gates (EG/HG) at each boundary. Requirement: REQ-033.
- Actions: at each stage exit, produce gate-check report; obtain HG decisions from operator where required.
- Outputs: `artifacts/reports/STAGE_EXIT_<stage>.md`. Human approval: **Yes for HG gates**. Complexity: M. Status: **S1 EXIT DONE 2026-07-10** — `STAGE_EXIT_S1.md` records HG-2 approval (D-036); recurring for S2/HG-3.
