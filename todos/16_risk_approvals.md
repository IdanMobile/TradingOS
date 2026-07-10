# Initiative 16 — Risk & Approvals (S1 thin / S2 full)

Requirement source: AD §Y/§Z, type catalog §2 APR. Skill: R7.

## T-016-01 Approval state machine (model only, S1)
- Purpose: APR identity + states + transition guards; live states unreachable. Requirement: REQ-050.
- Acceptance: forbidden-transition tests; live-state-unreachable test (also security gate). Complexity: M. Dependencies: T-007-04. Status: **DONE 2026-07-10** — contextual identity, evidence guards, human paper decision guard, and current-phase live-state-unreachable tests pass.

## T-016-02 Risk rules as validation preconditions (S1)
- Purpose: encode MVP risk posture (no live, cost-stress mandatory, drawdown/tail metrics reported) as checks consumed by validation packages. Requirement: REQ-051.
- Acceptance: rules evaluated in every VAL package. Complexity: S. Status: **DONE 2026-07-10** — B2 package records no-live, complete-cost-grid, drawdown/tail metrics, and promotion-ineligibility independently of strategy logic.

## S2/S3 backlog (deferred; design in AD §Z): independent runtime risk engine, kill-switch drills, portfolio caps, per-strategy budgets. Entry: S3 paper lane existence.
