# Open Tasks and Docs Audit — 2026-07-11

Scope: all markdown/text/planning docs, specs, TODO files, decision log, reports,
handoffs, audits, open-items files, traceability matrix, `.env.example`, and the
workspace TODO API. Builds on and re-verifies `OPEN_MARKERS_AUDIT_2026_07_11.md`
with an independent sweep (TODO/FIXME/TBD/UNRESOLVED/PLACEHOLDER/BLOCKED/DEFERRED/
WARN/NOT_RUN/follow-up/pending/not implemented and related markers).

## Method and result summary

- Files scanned: full repo tree excluding caches/venvs (`todos/` 21 files, `docs/`,
  `specs/` 11, `decisions/` 4, `audits/` 4, `handoffs/` 3, `research/`,
  `artifacts/reports/` 27+, state files, `.env.example`, `Makefile`, `src/`, `tests/`,
  `scripts/`).
- Independent marker sweep found **no unhandled actionable marker** beyond those
  already classified in `OPEN_MARKERS_AUDIT_2026_07_11.md`, plus **two new findings**
  from this pass: (1) the AD §AI vs POST-route contract mismatch, (2) `TIOS_AI_MODE`/
  `TIOS_AI_PROVIDER` missing from `.env.example`. Both are now handled (T-002-05;
  `.env.example` updated).
- Workspace TODO API state at audit time: 87 tasks — 73 done, 0 open, 0 in-progress,
  7 gated, 4 recurring (before T-002-05 was added).

## Classified open items (complete inventory of remaining work)

Classification legend: 1 architecture gap · 2 spec gap · 3 TODO gap · 4 research gap ·
5 validation gap · 6 test gap · 7 doc stale/conflict · 8 human decision gate ·
9 credential/config gate · 10 external dependency gate · 11 scope expansion ·
12 future/not-MVP · 13 stale marker, work done · 14 false positive.

| Item | Source | Class | Canonical task | Status |
|---|---|---|---|---|
| Dashboard POST route vs AD §AI/type-catalog GET-only lock | this audit | 1 + 8 | **T-002-05 (added)** | DECISION REQUIRED (operator) |
| Hummingbot full-history chunking/throughput design + rerun decision | HUMMINGBOT_FULL_HISTORY_TIMEOUT / PRODUCTIONIZATION reports | 3 + 11 | T-006-05 | throughput track, open |
| Hummingbot timeout behavior + container cleanup | same reports | 13 | T-006-05 | DONE — bounded lane has window/timeout controls, named-container stop, timeout manifests |
| Nautilus full-history parity decision | lane notes, MISSING_AND_OPEN_ITEMS | 11 + 8 | T-006-03 follow-up | deferred scope expansion (D-037) |
| Nautilus latency/fill-model scope decision | lane notes | 11 + 8 | T-006-03 follow-up | deferred scope expansion |
| Cross-engine parity residuals (B1 timing, B2 order-state/data-gap) | ENGINE_PARITY_REPORT, B2_PARITY_RESIDUAL_REPORT | 13 | T-006-07 | explained + retained; zero UNEXPLAINED |
| Cached-evidence reuse handling | HUMMINGBOT_PRODUCTIONIZATION_STEP | 13 | T-006-05 | feature caching retained (~32 s bounded B2 probe) |
| Engine-result normalization gaps | converter C3 semantic_notes | 14 | — | design feature (unknown fields preserved), not a defect |
| G4 WARN resolution or accepted-warning decision | BACKTEST_VALIDATION_REPORT | 5 + 8 | T-009-02 | WARN retained; blocks promotion claims |
| G10 production integration + independent recomputation | G10_METHOD_FIXTURES_2026_07_11 | 5 | T-009-04 / RG-07 | fixtures pass; production inactive |
| OOS/walk-forward/robustness on future candidates | validation package | 5 | T-009-03 (rerun per candidate) | done for B2 (negative); recurring per candidate |
| Benchmark comparison, fee/slippage stress | cost_sensitivity.json, benchmark comparison | 13 | T-008-03/T-009-03 | complete for retained candidates |
| Promotion eligibility requirements | S2_REQUIREMENT_AUDIT | 5 + 8 | S2 exit predicate | no candidate COMPLETE_APPROVABLE — promotion correctly blocked |
| No strategy validated / promotion-eligible | LAB-f99d, seed cycle | 5 | — | confirmed: 0 validated, 0 eligible; all marked UNVALIDATED/NOT_ELIGIBLE |
| First strategy candidate selection | RESEARCH_HYPOTHESES_V1, seed cycle | 4 | next evidence cycle (operator-triggered) | 2 seeds REPRODUCED, both negative on proxy |
| Strategy seed ingestion | STRATEGY_INGESTION_REPORT | 13 | T-010-* | DONE 10/10 with licenses/ambiguities |
| Rejected/failed strategy memory | trial ledger, evidence rows | 13 | T-008-01 | all trials retained append-only |
| Paper/demo/testnet not enabled | S2_LIVE_UNREACHABILITY_REPORT | 12 + 8 | T-015-01..05 | confirmed disabled; DEFERRED-S3/S4 |
| Approval UI | todos/14 backlog | 12 + 8 | T-014-14 | DEFERRED-HG |
| Kill-switch requirements, paper/live visual separation, paper-vs-backtest comparison | AD §Z/§AA, RG-13 | 12 | T-015-03/04, initiative 16 backlog | designed in AD; build gated S3 |
| Exchange/broker operator eligibility gates | MISSING_AND_OPEN_ITEMS "Human-only" ×10 | 8 | T-015-05 | human-only, S4 |
| AI provider credentials/spend gate | AI_COST_TELEMETRY_CREDENTIAL_RECHECK | 9 | T-011-05, T-017-05 | DEFERRED-CREDENTIALS (env recheck: no key present) |
| Judge calibration human review | benchmarks/ai_agent/calibration | 8 | T-011-04 residual | PENDING_HUMAN_REVIEW in frozen artifact |
| Benchmark corpus / model/agent/prompt registries / AI tracing | AI_BENCHMARK_SEED_REPORT | 13 | T-011-01..03, 06 | DONE (null-provider) |
| AI cost tracking + downstream value | AD §T | 9 + 12 | T-017-05 | credential-gated; RA cost amortization covers retained zero-cost evidence |
| Canonical dataset coverage/quality | dataset manifest, audit | 13 | T-004-* | FROZEN, PASS, double-regen identical |
| S3 artifact storage / remote lineage | AD §P | 12 | reopen trigger in AD §P | local-first approved (D-037); no remote storage authorized |
| RG-05 venue account eligibility (human part) | VENUE_ISRAEL_SOURCE_RECHECK | 8 | T-001-03 residual | public-source slice DONE; account checks DEFERRED-S3 |
| RG-06 fee tiers | RESEARCH_GAP_MATRIX | 8 + 4 | S3 prep | human/account-specific |
| Market data provider decisions (paid tiers) | D-018 | 12 | deferred list | deferred until justified |
| Dashboard missing pages (entity detail, comparisons, rewrite) | DASHBOARD_BOUNDARY_REPORT | 12 | T-014-10/11/13 | REJECTED FOR BOUNDED S2 with reopen triggers |
| Registry 90-day refresh | todos/01 | 8 (recurring) | T-001-06 | first due 2026-10-04 |
| One-command verification, cleanup, state scripts | Makefile, scripts/ | 13 | T-003-04, T-019-02 | `make check` / `make required` / report builders exist |
| CI decision | AD §AH / RG-14 | 8 + 12 | deferred decision | local gate is the guarantee until then |
| Secrets/`.env`/key-scope rules | SECURITY_REVIEW_01/02, tests | 13 | T-018-* | enforced + tested; `.env` ignored verified 2026-07-11 |
| `TIOS_AI_MODE`/`TIOS_AI_PROVIDER` not in `.env.example` | this audit | 7 + 9 | fixed this pass | `.env.example` updated 2026-07-11 |
| Old research-phase "Unresolved" venue rows | research/ecosystem_discovery | 13/14 | — | superseded point-in-time evidence; retained per retention policy |
| Enum markers (OPEN/WARN/NOT_RUN/REJECTED) in artifacts | validation/domain data | 14 | — | data states, not TODOs |

## Required-coverage verification

Every category demanded by the audit mandate maps to at least one canonical task or an
explicit approved gate/deferral (table above): engine/bakeoff ✓, validation ✓, strategy
readiness ✓, paper/demo/live ✓, AI evaluation ✓, data ✓, dashboard ✓, infra/ops ✓,
security ✓, documentation/handoff ✓. The only **new** task this audit had to add is
T-002-05; everything else was already tracked, gated, or evidenced.

## Docs consistency verdict

- No doc claims the project is fully ready to run/use; PROJECT_STATE, EXECUTION_PLAN,
  and the S2 requirement audit all state the exit blockers consistently.
- One contract conflict found (AD §AI/type-catalog vs POST route) — now recorded in AD
  as a Current Implementation Gap and tasked (T-002-05).
- No stale "DONE" claims found without evidence artifacts; spot checks of DONE tasks
  (T-004-*, T-006-*, T-009-*, T-012/13/14/17/19) all reference existing artifacts.
