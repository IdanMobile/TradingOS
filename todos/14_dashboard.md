# Initiative 14 — Dashboard (S1 WS9 read-only; S2 console)

Requirement source: SSOT WS9, MVP_SCOPE §7, AD §AI.

## T-014-01 Read-only dashboard API
- Purpose: `/api/v1/` read endpoints mirroring type-catalog queries for the six MVP views. Requirement: REQ-048.
- Acceptance: contract tests pin schemas; zero write endpoints (test enforces). Complexity: M. Dependencies: first producers (T-004-04, T-008-01). Skill: R7. Status: TODO.

## T-014-02 Evidence surface (Streamlit — AD-06)
- Purpose: six views (datasets, runs, strategies, engine comparison, validation status, evidence links). Requirement: REQ-049 (WS9 exit).
- Actions: single-app Streamlit over the API or direct read models; empty states; environment banner.
- Acceptance: every S1 evidence artifact reachable by browsing; operator can trace dataset→run→validation→decision without touching the filesystem. Complexity: M. Status: TODO.

## S2 backlog (not authorized in S1 — recorded to prevent scope creep INTO S1)
- T-014-10 console IA spike (Next.js+shadcn, AD-07), T-014-11 entity-detail layout pattern, T-014-12 global search (FTS), T-014-13 comparisons UI, T-014-14 approvals UI (write-path, HG-gated). Status: DEFERRED-S2, entry criteria: prototype decision + RG-12 contract evidence.
