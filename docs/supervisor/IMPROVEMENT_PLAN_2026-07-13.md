# Trading OS supervisory improvement plan — 2026-07-13

Status: active, dependency ordered.  
Baseline: `docs/supervisor/SUPERVISORY_BASELINE_2026-07-13.md`.  
Rule: no hard fail may be averaged away, and no item is complete until its acceptance criteria pass.

## Progress snapshot — 2026-07-13

| Finding | Current status | Evidence / residual |
|---|---|---|
| SUP-001 | **CONTAINED** | Default authenticated transports raise before network access; reactivation remains human/evidence gated. |
| SUP-002 | **CORRECTED** | Shared/comparison DSR equation and fixtures corrected; dated diagnostics regenerated. |
| SUP-003 | **CONTAINED** | Unknown fills and failed flattening remain non-success with residual state visible; venue scripts remain quarantined. |
| SUP-004 | **COMPLETE** | `make check` enforces controlled-file hashes; v8.53 manifest and changelog are reconciled. |
| SUP-005 | **PARTIAL / METHOD_BLOCKED** | The preregistered 66-trial campaign completed with immutable per-family evidence: B2/B4 numerically fail, B3 is method-blocked, and overall G10 remains method-blocked. Historical upstream admission is unavailable; retained proxies also deviate from canonical next-open semantics. |
| SUP-006 | **PARTIAL / NOT VALIDATED** | Claims are static cost stress; a research-only multi-leg spec and deterministic open/settle/rehedge/close capital/funding/basis/fee/isolated-margin lifecycle exist. Venue semantics, intraperiod liquidation, empirical costs, counterparty risk, and G12 remain open. |
| SUP-007 | **PARTIAL / CURRENT BYTES PINNED** | Future raw/REST lineage is retained; the 69 current REST pages are content-addressed and included with the deliverable; the current 69-table normalized snapshot is deterministic and verifiable; future substantive artifacts have a fail-closed metadata contract. Original run identity and historical REST payloads cannot be reconstructed. |
| SUP-008 | **PARTIAL / METHOD_BLOCKED** | Future public/signal/universe runners select on train only and evaluate a frozen context once on holdout. Exact source/spec/license identity and one globally frozen candidate remain open. |
| SUP-009 | **PARTIAL** | MTF is fail-closed and family-wide claims are downgraded; stat-arb, cross-sectional, and combination method reconstruction remains open. |
| SUP-010 | **PARTIAL** | Funding uses a backward-compatible research-only multi-leg schema and remains `VALID_WITH_AMBIGUITIES`; ranking, MTF, composition, funding-input, collateral, settlement, and reconciliation primitives remain incomplete. |
| SUP-011 | **PARTIAL** | Credential names/environment isolation/ignore rules are fixed; oversized sdist is deferred until a release is authorized. |

## Priority order

1. Restore statistical and execution-governance truth.
2. Restore package integrity, provenance, and SSOT consistency.
3. Repair research methodology and canonical strategy ownership.
4. Rebuild funding carry only after its capital/risk semantics are explicit.
5. Expand product or execution scope only after evidence and human gates.

## Findings and bounded initiatives

### SUP-001 — Unapproved authenticated demo execution

- **Severity:** Critical
- **Owning layer:** Governance / security / execution boundary
- **Evidence:** D-036/D-037/D-042/D-043 and AD §AA require staged evidence and human gates; no HG-3/HG-4/Bybit approval exists; `PROJECT_STATE.md` records real Bybit demo spot/perp orders.
- **Intake behavior:** standalone scripts could load demo credentials and issue authenticated venue orders while the SSOT said no venue connection or order command existed. D-046 now quarantines every authenticated transport before network access.
- **Intended behavior:** authenticated venue I/O is unreachable until every matching validation, security, stage-gate, venue, and operator predicate is durable and current.
- **Why it matters:** the project's main safety guarantee is independent human control over advancement toward capital-bearing capability.
- **Recommended change:** quarantine authenticated transports now; retain past artifacts as unauthorized historical demo evidence; design a typed adapter only after a future approved gate.
- **Dependencies:** none for quarantine; human evidence required for any reactivation.
- **Validation:** default authenticated transports raise before network access; repository-level test detects new authenticated order endpoints; no running demo process.
- **Acceptance criteria:** no credentialed demo entrypoint can reach the network; dashboard/docs state `QUARANTINED`; prior evidence is not counted as S3 qualification.
- **Human approval required:** Yes, only to reactivate a specific future demo integration; not required to enforce existing locks.

### SUP-002 — Incorrect Deflated Sharpe Ratio equation

- **Severity:** Critical
- **Owning layer:** Quant validation / G10
- **Evidence:** shared and comparison implementations used `sr0` in the non-normality denominator; the Bailey/López de Prado DSR formula uses the observed Sharpe. Existing synthetic fixtures pinned the incorrect value.
- **Current behavior:** every DSR value using non-normal returns is numerically invalid; duplicate code agreed because it duplicated the same defect.
- **Intended behavior:** use the primary-paper estimator, with a known-answer test that distinguishes observed Sharpe from the null threshold.
- **Why it matters:** G10 is a promotion hard gate and a central claim of the project.
- **Recommended change:** correct the primitive and comparison functions; recompute all dependent artifacts; keep RG-07 open before honoring any future PASS.
- **Dependencies:** primary-source formula verification; retained trial inputs.
- **Validation:** focused known-answer tests; independent recomputation; rerun every script that calls `deflated_sharpe_ratio`.
- **Acceptance criteria:** corrected regression values pass; affected artifacts either reproduce with new hashes or are marked superseded; no prior PASS is inherited.
- **Human approval required:** No for correction; stats-specialist review is required before a future PASS can support promotion.

### SUP-003 — Demo order and flatten reconciliation fails open

- **Severity:** Critical
- **Owning layer:** Execution / reconciliation
- **Evidence:** managed sells used `status == Filled or True`; carry treated missing status as filled; strategy/managed bots could return success after failed flattening.
- **Current behavior:** local state can declare flat without a verified terminal fill or final position/balance reconciliation.
- **Intended behavior:** unknown, partial, cancelled, rejected, or timed-out outcomes remain non-success; state changes only after verified fills; final flatness is reconciled.
- **Why it matters:** duplicate, orphaned, and directional residual positions are core execution failure modes.
- **Recommended change:** fail closed, consult order history when realtime is empty, stop/unwind asymmetric legs, reconcile final spot/perp state, and do not trade negative funding.
- **Dependencies:** SUP-001 quarantine remains in force.
- **Validation:** injected offline tests for empty status, rejection, failed flatten, asymmetric legs, negative funding, and final reconciliation.
- **Acceptance criteria:** all negative branches remain non-success and do not clear local position state; no default network call is made.
- **Human approval required:** No for offline correctness; yes for any later venue exercise.

### SUP-004 — Controlled-file integrity manifest drift

- **Severity:** High
- **Owning layer:** Governance / release engineering
- **Evidence:** six mandatory files mismatch `PACKAGE_INTEGRITY_MANIFEST.md`; the manifest calls this a hard blocker, while `make check` omitted the verification.
- **Current behavior:** a retained PASS gate can coexist with package-integrity failure.
- **Intended behavior:** the local gate fails on missing/mismatched mandatory inputs; controlled edits regenerate the manifest and changelog in one change.
- **Why it matters:** the SSOT precedence and handoff continuity depend on detecting uncontrolled drift.
- **Recommended change:** add the check to `make check`; reconcile docs; regenerate hashes only after the content is final.
- **Dependencies:** SUP-001/SUP-002 documentation reconciliation.
- **Validation:** intentionally stale hash fails; current hashes pass.
- **Acceptance criteria:** `make check` includes and passes package integrity; manifest version/changelog describe this cycle.
- **Human approval required:** No.

### SUP-005 — G10 independence and selection procedure are unsubstantiated

- **Severity:** High
- **Owning layer:** Quant validation / experiment lineage
- **Evidence:** callers pass raw grid size as `independent_trials`; parameter/dataset trials are correlated; sequential family searches are omitted; core G10 selects by total return but deflates Sharpe; MTF passes one Sharpe with zero cross-trial variance.
- **Current behavior:** local direction and magnitude of deflation are unknown, and MTF DSR is not a valid multiple-testing adjustment.
- **Intended behavior:** pre-register the search family, retain the actual selection population and return correlations, use one selection metric end to end, and estimate or conservatively bound effective independent trials.
- **Why it matters:** a corrected equation alone does not make a search process statistically valid.
- **Recommended change:** mark current G10 results method-limited; fix MTF immediately; design hierarchical trial accounting before any new strategy PASS claim.
- **Dependencies:** SUP-002.
- **Validation:** a fixture with correlated trials; a genuine multi-trial MTF training population; untouched OOS evaluation.
- **Acceptance criteria:** artifacts distinguish raw trials from effective independent trials and record the selection metric/search lineage; future PASS requires specialist review.
- **Human approval required:** No, but specialist review required for PASS use.

### SUP-006 — Funding carry evidence overstates execution and validation

- **Severity:** High
- **Owning layer:** Strategy / data / backtest / risk / execution
- **Evidence:** the basis model continuously combines equal-notional spot/perp returns while charging only membership toggles; capital denominator, collateral, rehedging, mark/index/funding timing, maintenance margin, liquidation, missing data, point-in-time universe, and counterparty dependence are incomplete. The “S3 paper” run uses fixed fees/slippage and a tautological synthetic ledger.
- **Current behavior:** reports call the candidate execution-robust or a real edge even though `verdict_is_genuine=false` and G12 was not observed.
- **Intended behavior:** classify the current run as static G5 cost stress; validate an event-timestamped two-leg ledger on total deployable capital with complete risk/cost semantics and nested OOS.
- **Why it matters:** an apparently smooth carry series can hide leverage, collateral, liquidation, basis-spike, and counterparty tails.
- **Recommended change:** downgrade claims now; create a complete canonical strategy specification; rebuild the model only after semantics are sourced and testable.
- **Dependencies:** SUP-002/SUP-005, immutable multi-data provenance.
- **Validation:** hand-derived two-leg fixtures, settlement-boundary cases, missing-data failure, rehedge turnover, liquidation/basis stress, nested OOS, and empirical paper evidence only after approved gates.
- **Acceptance criteria:** current artifacts no longer count as G12/S3 evidence; corrected model states capital/collateral/venue assumptions and passes all relevant gates before any promotion proposal.
- **Human approval required:** No for offline model; yes for venue/counterparty selection and later paper/live stages.

### SUP-007 — Expanded market-data and quant artifact provenance is incomplete

- **Severity:** High
- **Owning layer:** Data / experiment lineage
- **Evidence:** the sole raw manifest is overwritten by acquisition kind; existing files can be marked verified without consulting retained official checksums; normalized multi manifest is absent; several retained artifacts lack commit, runner/spec/data hashes, UTC range, version, and exact cost model; some are stale relative to code.
- **Current behavior:** important research results cannot be reproduced from an immutable input identity.
- **Intended behavior:** immutable per-run raw and normalized manifests; every artifact carries complete provenance and all-trial lineage.
- **Why it matters:** no result is defensible when inputs can drift silently.
- **Recommended change:** repair manifest semantics before further multi-pair research; add artifact schema checks; mark stale outputs.
- **Dependencies:** none; should precede strategy reruns beyond corrective DSR recomputation.
- **Validation:** restore/replay from declared hashes; deliberate byte drift fails; artifact/code mismatch is visible.
- **Acceptance criteria:** every promoted research claim traces to immutable source files, normalization, code, spec, parameters, costs, and output hashes.
- **Human approval required:** No.

### SUP-008 — Public-strategy and universe searches leak holdout and lack exact source identity

- **Severity:** High
- **Owning layer:** Strategy ingestion / validation
- **Evidence:** best parameters are selected on the full dataset before thirds/holdout reporting; generic “public” strategies lack exact URL, author, version, license, ambiguity, and canonical spec records.
- **Current behavior:** holdout influenced selection, and results cannot be attributed to an exact copied implementation.
- **Intended behavior:** train-only selection, validation freeze, one untouched holdout use, and exact source/spec/license provenance.
- **Why it matters:** otherwise both performance and “copied public strategy” language are misleading.
- **Recommended change:** retain current runs as exploratory only; do not regenerate until provenance and split design are fixed.
- **Dependencies:** SUP-007 and canonical strategy ownership.
- **Validation:** tests prove holdout data is unavailable during selection; every candidate resolves to a source/spec hash.
- **Acceptance criteria:** no holdout-selected candidate is called validated; all source claims are reproducible and licensed.
- **Human approval required:** No.

### SUP-009 — Stat-arb, MTF, cross-sectional, and combination conclusions exceed methods

- **Severity:** High
- **Owning layer:** Strategy / quant validation
- **Evidence:** stat-arb uses a simplified unaugmented DF test, fixed beta, and tunes on its OOS tail; cross-sectional data has survivor and short-cost bias; combinations test event pulses rather than a persistent portfolio; MTF selection/DSR population is invalid.
- **Current behavior:** retained negatives are useful exploratory evidence but cannot prove that entire families are dead or that cointegration decayed.
- **Intended behavior:** exact family specifications, nested temporal validation, point-in-time universes, correct costs/capital, and family-appropriate statistics.
- **Why it matters:** negative-result discipline must be as rigorous as positive-result discipline.
- **Recommended change:** downgrade causal/family-wide claims; prioritize data/provenance repair over more variants.
- **Dependencies:** SUP-005/SUP-007.
- **Validation:** family-specific fixtures and untouched tests; exact capital/cost accounting.
- **Acceptance criteria:** reports distinguish tested implementation failure from family rejection.
- **Human approval required:** No.

### SUP-010 — Major research strategies bypass the canonical registry

- **Severity:** High
- **Owning layer:** Strategy domain / evidence spine
- **Evidence:** funding, stat-arb, cross-sectional, MTF, combinations, and generic public strategies exist only in scripts/artifacts, not as immutable strategy versions with complete specifications.
- **Current behavior:** formulas, invalidation, exits, sizing, portfolio limits, no-trade conditions, costs, failure modes, and promotion status are not versioned end to end.
- **Intended behavior:** every retained candidate has a full canonical specification and artifact-embedded spec hash; script behavior is parity-tested against the spec.
- **Why it matters:** a strategy cannot be audited or promoted without a stable identity.
- **Recommended change:** register only candidates worth retaining; avoid mass-converting already-invalid exploratory variants.
- **Dependencies:** SUP-007 and methodology decisions.
- **Validation:** source→spec→signal→run parity tests.
- **Acceptance criteria:** no substantive candidate result is presented without a resolvable immutable strategy version.
- **Human approval required:** No.

### SUP-011 — Credential and packaging hygiene gaps

- **Severity:** Medium
- **Owning layer:** Security / packaging
- **Evidence:** legacy `PYBIT_*` aliases differ from documentation; shared `.env` loading imported unrelated values; `.env.demo`/`.env.production` were not ignored; sdist is approximately 207 MB because tracked data/evidence/cache content is included.
- **Current behavior:** credential names and process scope are inconsistent; an accidental source distribution would contain excessive project evidence.
- **Intended behavior:** one demo-specific name pair, load only those variables, ignore all `.env.*` except `.env.example`, and publish no sdist unless a bounded distribution is explicitly needed.
- **Why it matters:** least privilege applies to process environment and artifact distribution, not only Git secrets.
- **Recommended change:** standardize names and ignores now; defer sdist packaging until there is a release requirement.
- **Dependencies:** SUP-001.
- **Validation:** env-loader isolation and git-ignore tests; optional bounded build test when publishing is authorized.
- **Acceptance criteria:** no unrelated secret enters a demo process; secret variants are ignored; no unintentional distribution is published.
- **Human approval required:** No.

## Deferred or human-only items

- Any reactivation of Bybit/other venue demo or testnet connectivity.
- HG-3, HG-4, and HG-5 decisions.
- Venue account eligibility, permissions, terms, fees, credentials, counterparty allocation, and capital limits.
- Paid data procurement.
- Any real-money path.

These do not block offline remediation, documentation, test strengthening, or honest negative research.
