# Initiative 18 — Security (S1, gate-level)

Requirement source: AD §AB, SSOT secret rules, intake gate. Skills: R7 + SKILL_SECURITY_REVIEWER.

## T-018-01 Secret hygiene enforcement
- Purpose: scanning + gitignore + report-redaction checks in local gate. Requirement: REQ-052.
- Acceptance: planted-secret fixture caught in repo, artifacts, and report-builder outputs. Complexity: S. Dependencies: T-003-04. Status: TODO.

## T-018-02 Ingested-code containment policy (executable)
- Purpose: external strategy code never runs in-process; isolated env without credentials/network for reproduction. Requirement: REQ-053.
- Actions: containment wrapper + policy test; document in ingestion module.
- Acceptance: containment test (ingested sample cannot read env/secrets); policy doc linked from ingestion lifecycle. Complexity: M. Dependencies: T-010-01. Status: TODO.

## T-018-03 Dependency & license audit wiring
- Purpose: vulnerability audit + license-compatibility check (GPL/LGPL/AGPL boundaries per AD-02) in local gate. Requirement: REQ-054.
- Acceptance: audit runs; a planted AGPL dep in core is flagged. Complexity: S. Status: TODO.

## T-018-04 Stage-exit security reviews
- Purpose: SKILL_SECURITY_REVIEWER pass at each stage exit. Requirement: REQ-055.
- Acceptance: review reports; blocking findings resolved or open-itemed. Complexity: S recurring. Status: TODO.
