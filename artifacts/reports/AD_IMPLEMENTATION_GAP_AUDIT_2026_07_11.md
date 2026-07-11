# AD ↔ Implementation Gap Audit — 2026-07-11

Scope: `docs/architecture/AD.md` (desired architecture authority, D-030/D-037) compared
against current implementation evidence, specs, TODO state, and the workspace TODO API.
Rule applied: AD is the desired-architecture authority; implementation shortcuts are never
normalized into AD without an approved decision. Companion reports:
`OPEN_TASKS_AND_DOCS_AUDIT_2026_07_11.md`, `ENV_AND_CREDENTIALS_AUDIT_2026_07_11.md`,
`WORKSPACE_TODO_API_SYNC_2026_07_11.md`.

## Major mismatch table

| Area | Desired AD Intent | Current State Evidence | Gap Type | Required Action | Update AD? | Update TODO? | Notes |
|---|---|---|---|---|---|---|---|
| Dashboard API write path | AD §AI + TYPE_AND_CONTRACT_CATALOG §API: `/api/v1/` has **no POST/PUT/PATCH/DELETE route** | `POST /api/v1/workspace-actions/decision` exists in `src/tios/services/dashboard_ui/server.py`, is test-pinned as "the only allowed write path" (`tests/test_dashboard.py`), and the operator used it (9 records in `artifacts/human_decisions/workspace_decisions.jsonl`, incl. authorizations later acted on) | 6 — Intentional architecture change candidate | Operator decision: either record a decision-log amendment scoping AD §AI/type-catalog to "no *trading/approval/job* mutation route; single localhost human-decision recording route permitted", or remove the route and move workspace decisions to CLI | **Decision required** (Current Implementation Gap note added to AD §AI; desired lock preserved) | **Yes — add task** (T-002-05 added to `todos/02_architecture_foundation.md`) | The route records human governance choices only, validates against a fixed option allowlist, loopback-only; it is not an order/approval-transition route. Still, the locked contract wording forbids it. |
| Hummingbot full-history | AD §K: full-history completion is a throughput track within retained bounded role | Full-history B2 F1/S1 timed out at 1800s and cached retry at 3600s with clean manifests (`HUMMINGBOT_FULL_HISTORY_TIMEOUT_2026_07_11.md`); bounded 30-day matrix complete and deterministic | 2 — Implementation incomplete | Chunking/throughput design, then rerun decision | No — implementation must change | No — already covered (T-006-05 status records the throughput track) | Not a credential or approval blocker per D-037. |
| Nautilus full-history parity + latency/fill | AD §K: bounded event-simulation lane; full-history parity and latency/fill evidence named as gaps | Bounded B1–B4 × grid × run1/run2 byte-deterministic; full-history/latency not run | 2 — Implementation incomplete | Scope-expansion decision + run when authorized | No — implementation must change | No — already covered (T-006-03 follow-ups in lane notes) | Deferred scope expansion under D-037. |
| G4 leakage gate | AD §H/§I: gates G1–G9 deterministic; promotion requires zero hard-fails and clean gates | G4 retained WARN — Freqtrade lookahead tool overrides requested stake/trade-limit settings (`BACKTEST_VALIDATION_REPORT.md`) | 2 — Implementation incomplete (upstream tool limitation, honestly retained) | Resolve WARN or record an accepted-warning decision before any promotion claim | No — implementation must change | No — already covered (T-009-02 WARN status; MISSING_AND_OPEN_ITEMS §S2 item 2) | Blocks clean promotion claims, not offline research. |
| G10 multiple-testing gate | AD §X + validation blueprint: G10 PBO/DSR part of gate set | Synthetic known-answer fixtures pass (`G10_METHOD_FIXTURES_2026_07_11.json`); candidate-specific integration + independent recomputation NOT done; production G10 inactive | 2 — Implementation incomplete | Integrate estimators per candidate + independent recomputation before any G10 PASS | No — implementation must change | No — already covered (T-009-04, RG-07) | Correctly not claimed as PASS anywhere. |
| Strategy promotion | AD §I: PAPER_CANDIDATE requires VAL package, zero hard-fails, red team | No candidate `COMPLETE_APPROVABLE`; B2 rejected; LAB-f99d retains 66 trials, no winner (`S2_REQUIREMENT_AUDIT.md`) | Not a mismatch — desired gates are correctly blocking | Continue evidence cycles; no promotion | No | No — already covered | S2 exit/HG-3 blocked on evidence grounds, exactly as AD intends. |
| Paper/demo/live boundary | AD §AA: all execution predicates false in S2; no credential, wallet, venue path | `S2_LIVE_UNREACHABILITY_REPORT.md` PASS; `test_live_unreachable.py`; no venue/exchange env vars exist | Aligned | None | No | No | Desired architecture fully enforced. |
| Real-provider AI benchmarks | AD §T/AD-12: real providers outside S2 until credential authority + benchmark evidence | Null-provider harness complete; no provider key present (rechecked 2026-07-11); T-011-05 DEFERRED-CREDENTIALS | Aligned (credential gate) | Operator configures a provider key when authorized | No | No — already covered (T-011-05) | Operator "credentials_configured" decision for T-017-05 conflicted with env recheck — reconciled to DEFERRED-CREDENTIALS with evidence. |
| `.env.example` completeness | AD §AH: `.env.example`-driven config, fail-closed startup validation | `TIOS_AI_MODE` / `TIOS_AI_PROVIDER` are read by code (`benchmarks/ai_agent/harness/provider.py`, `scripts/run_research_lab_v0.py`, jobs runner) but were absent from `.env.example` | 7 — Documentation stale/conflict | Add the two names+comments to `.env.example` | No | No — fixed in this pass | Fixed 2026-07-11; see `ENV_AND_CREDENTIALS_AUDIT_2026_07_11.md`. Fail-closed behavior exists (`TIOS_AI_MODE` invalid value raises; `real` without provider raises). |
| Full ontology, 27-page console, Task Router, paper/live contexts | North Star long-term capabilities preserved in AD §D/§T/§V/§AI as deferred | Not built | Deferred by approved decision (D-037, AD-07) | Keep deferred; do not delete from AD | No | No — gated tasks retained (12, 14 backlog, 15, 16, 20) | Correct handling: capability retained in AD, execution gated. |

## AD update actions taken this pass (policy-compliant)

1. AD §AI: added a **Current Implementation Gap** note recording the workspace-decision
   POST route mismatch and its pending decision (policy: "add explicit Current
   Implementation Gap notes while preserving desired architecture" + "add references").
   No desired-architecture wording was weakened; the GET-only lock remains the desired
   contract until an operator decision says otherwise.

No AD section was downgraded, deleted, or rewritten to match implementation.

## Final readiness assessment (against desired AD, not current implementation)

| Readiness Area | Desired AD Requirement | Current State | Status | Blocking Gaps |
|---|---|---|---|---|
| Documentation consistency | State/docs current with newest evidence (T-000-01) | State files updated through 2026-07-11; one contract mismatch found (POST route) | PARTIAL | T-002-05 decision |
| AD completeness | §A–§AL cover desired OS; maturity labels binding | Complete for S2 lock; one gap note added | PASS | none (T-002-05 is a decision, not missing architecture) |
| TODO completeness | Every remaining work item task-tracked with acceptance | 87 tasks + T-002-05 added; required-coverage checklist verified in OPEN_TASKS audit | PASS | — |
| Workspace TODO API sync | API projects canonical `todos/*.md`; decisions retained | API up at 127.0.0.1:8765; zero divergence by construction; 9 decisions retained; 1 decision-vs-env conflict reconciled | PASS | — |
| `.env` / credential readiness | Names-only template, `.env` ignored, fail-closed | `.env` git-ignored (verified); template updated with TIOS_AI_* names; no secrets found | PASS | AI provider keys remain operator "add later" |
| Prototype readiness | S1 EG-1..7 + HG-2 | HG-2 approved (D-036) | PASS | — |
| MVP readiness | Constrained S2 scope of MVP_SCOPE | Bounded S2 slices done; S2 exit blocked | PARTIAL | validated strategy required |
| Backtesting readiness | Deterministic engines + ledger + fee grid | Freqtrade/Nautilus/vectorbt/LEAN(bounded)/Hummingbot(bounded) evidenced | PASS | full-history throughput tracks open |
| Live-data readiness | S2 = historical only; live feeds are S3+ | No live feed; frozen dataset only | DEFERRED BY APPROVED DECISION (D-037) | HG-3, paper-lane decision |
| Signals readiness | Signals as inert historical projections in S2 | Signal/fill annotations on owned chart; inert contracts | PASS (S2 scope) | live signals gated S3 |
| Demo/paper wallet readiness | AA predicates; synthetic wallet requires HG-3+ | Design-only readiness is now projected in `trading_domain.demo_wallet_design`; no ledger, synthetic capital, mutation API, order route, venue connection, or activation control exists | DESIGN-ONLY S2 READINESS PROJECTED; activation NOT STARTED | S2 exit, HG-3, validated strategy, security pass, operator approval |
| Paper trading readiness | §AA predicate chain | Not enabled | NOT STARTED (by design) | same predicate chain |
| Live trading readiness | S4, HG-5, human-only gates | Unreachable (tested) | NOT STARTED (by design) | S3 exit + HG-4/5 + 10 human-only items |
| Strategy promotion readiness | Zero hard-fails + complete gates + red team | No candidate; G4 WARN; G10 inactive; economics negative | FAIL (honest) | G4, G10, positive candidate evidence |
| AI/model/agent evaluation readiness | Registries+fixtures+harness; real runs gated | Null-provider complete; real runs credential-gated | PARTIAL | provider key + spend authority + judge calibration human review |
| Dashboard readiness | Read-only bounded S2 console (AD §AI) | Live, browser-verified, read-only except the disputed decision route | PARTIAL | T-002-05 decision |
| Risk/approval readiness | Inert RiskDecision + approval preconditions only in S2 | Implemented + tested; live states unreachable | PASS (S2 scope) | runtime risk engine is S3 |

**Overall: the system is NOT "fully ready to run and use" against the desired AD** — by
design: S2 exit, strategy promotion, paper/demo, and live workflows are blocked by
evidence and human gates that the desired architecture itself mandates. Offline research
operations are fully runnable today (`make check`, `make dashboard`,
`scripts/run_research_lab_v0.py`).
