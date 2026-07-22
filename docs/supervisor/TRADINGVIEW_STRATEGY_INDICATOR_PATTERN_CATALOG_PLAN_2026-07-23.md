# TradingView Strategy, Indicator, and Pattern Catalog Plan

Date: 2026-07-23
Status: PROPOSED; documentation discovery complete; implementation not authorized by this plan
Mode: targeted architecture and roadmap plan
Execution authority: NONE
Venue connection: NONE
Paper/live authority created: false

## Decision first

Build an OS-owned, versioned catalog of TradingView-derived research candidates, beginning with a
dated snapshot of all current built-in strategies and then expanding through classic indicators,
independently specified price/candlestick patterns, and license-cleared open-source community
scripts.

Do **not** attempt a wholesale copy of everything on TradingView. “All available” has three precise
meanings in this plan:

1. **Built-ins:** complete catalog coverage for a timestamped TradingView UI/help snapshot.
2. **Community scripts:** a continuously refreshed, best-effort public metadata catalog, never a
   claim of completeness. Only source-visible, license-cleared, semantically reproducible items can
   become OS strategy candidates.
3. **Indicators and patterns:** complete coverage only for a separately frozen, sourced OS support
   manifest. Implementation advances in bounded compatibility tranches.

The current first strategy tranche contains 22 evidenced built-in candidates: the 20 items in the
[official Built-in Strategies folder](https://www.tradingview.com/support/folders/43000587406-built-in-strategies/)
plus `MovingAvg Cross` and `MovingAvg2Line Cross`, which are visible in the supplied current UI and
have separate official help pages. Phase 0 must recheck and freeze the exact live list because the
folder index and current UI are inconsistent.

This is a research expansion, not a confidence shortcut. Indicators and patterns are feature
hypotheses, not strategies and not independent votes. More agreeing indicators must never
automatically increase a bot's score or confidence. Any incremental value must survive causal,
out-of-sample, after-cost, correlation, ablation, multiple-testing, and calibration checks.

## Why the scope is bounded

- TradingView documents more than 150,000 community scripts; the population changes continuously.
- Open-source, protected, and invite-only scripts have different access and reuse boundaries.
- Protected, invite-only, purchased, account-gated, or unclear-license implementations must remain
  metadata-only or excluded; they are never copied, scraped, or behaviorally cloned.
- The embedded Advanced Chart widget cannot add Pine scripts or strategies. OS strategies must live
  in the OS catalog and run only on OS-owned/licensed market data.
- TradingView content and data are not an automated strategy datafeed. The OS must independently
  compute every feature and signal from its own point-in-time data.
- TradingView Strategy Reports are external comparison evidence, not local validation or approval.

Official sources retrieved 2026-07-23:

- [TradingView policies and Terms](https://www.tradingview.com/policies/)
- [Pine publishing and visibility types](https://www.tradingview.com/pine-script-docs/writing/publishing/)
- [Script publishing rules](https://www.tradingview.com/support/solutions/43000590599-script-publishing-rules/)
- [Pine strategy semantics](https://www.tradingview.com/pine-script-docs/concepts/strategies/)
- [Strategy Report entry points](https://www.tradingview.com/support/solutions/43000764138-tradingview-strategy-report-how-to-start/)
- [Widget limitations](https://www.tradingview.com/widget-docs/faq/general/)
- [Automatic chart-pattern scope](https://www.tradingview.com/support/solutions/43000690464-auto-chart-patterns-on-tradingview/)

## Locked invariants

- Preserve `ResearchSource → Hypothesis → CanonicalStrategySpec → StrategyVersion → Experiment →
  ValidationPackage → Approval` as the evidence spine.
- Extend `SRC-TRADINGVIEW-PUBLIC-STRATEGIES`, `INTAKE-TRADINGVIEW-PUBLIC-STRATEGIES`, and
  `RPH-TRADINGVIEW-PUBLIC-STRATEGY-TESTER`; do not create parallel identities.
- Preserve the lifecycle in
  `specs/STRATEGY_INGESTION_AND_REPRODUCTION_WORKFLOW_V1.md`:
  `DISCOVERED → SOURCE_CAPTURED → LICENSE_CHECKED → SEMANTIC_EXTRACTED →
  AMBIGUITIES_RECORDED → CANONICAL_SPEC_CREATED → REFERENCE_REPRODUCED → PARITY_CHECKED →
  INTERNAL_BASELINE_RUN → VALIDATION_ELIGIBLE|REJECTED`.
- Every implementation uses OS-owned or appropriately licensed point-in-time data. No TradingView
  market data, alerts, chart exports, or displayed outputs become a bot input.
- Every source begins unvalidated. Published profitability, popularity, editor selection, rankings,
  and Strategy Report results never transfer into OS evidence.
- Every evaluated trial remains retained and hierarchy-counted. A renamed, ported, or parameterized
  copy does not reset a closed family's trial budget.
- TradingView remains `DISCOVERY_AND_COMPARISON_EVIDENCE_ONLY` under
  `research/STRATEGY_ELIGIBILITY_CONTRACT_V1.yaml`.
- Independent score dimensions remain separate. No global weighted score, indicator vote count, or
  “magic confidence” score may override a hard gate.
- Missing, ambiguous, repainting, non-causal, unavailable, or unsupported semantics fail closed.
- No implementation in this plan can place, simulate, route, or authorize a live order.
- `make check` is the release gate; pytest suites do not run concurrently.

## Current verified baseline

- The existing public-source intake plan already records license/access, Pine version, symbol,
  timeframe, Strategy Report context, costs, parameters, and explicit prohibitions in
  `research/EXTERNAL_SOURCE_INTAKE_PLANS_V1.yaml`.
- `artifacts/source_intake/tradingview_public_strategies/selected_candidates_2026_07_11.json`
  contains eight selected public candidates.
- `scripts/run_tradingview_public_strategy_replay.py` locally replays two bounded strategy families
  from retained source summaries without copying protected Pine or connecting an account.
- `scripts/run_external_strategy_search.py` has 32 research systems: 20 public strategy families,
  eight indicator-based systems, and four candlestick-pattern systems.
- The repository has 20 immutable registered `StrategyVersion` rows, while the current dashboard
  Strategies projection exposes only five strategy rows. Catalog truth and UI projection are not
  yet unified.
- `src/tios/strategy/evaluator.py` supports only a bounded canonical vocabulary: SMA, EMA,
  Bollinger, Wilder RSI, prior-bar Donchian, rate of change, reference price, Supertrend,
  volume-threshold, and a UTC calendar window. Unsupported indicators fail closed.
- Existing historical TradingView/public-family searches have negative and method-blocked evidence.
  New source coverage must deduplicate against those trials rather than silently starting a fresh
  search population.
- The autonomous research factory's campaign admission phases remain blocked on the external
  independent-review activation gate documented in
  `docs/supervisor/AUTONOMOUS_RESEARCH_FACTORY_AND_OPERATIONS_PLAN_2026-07-21.md`.

## Definitions and user-visible states

Every catalog item must expose exactly one lifecycle state and never collapse the states into
“available”:

| State | Meaning |
|---|---|
| `CATALOGED` | Name, type, source URL, observation time, and source class retained. |
| `SOURCE_CAPTURED` | Exact lawful source/reference snapshot and digest retained. |
| `LICENSE_CLEARED` | Reuse decision and attribution obligations recorded. |
| `SPECIFIED` | Exact OS-native, point-in-time semantics and ambiguity record exist. |
| `PARITY_TESTED` | Reference vectors/signals/trades agree within declared tolerances. |
| `RESEARCH_TESTED` | Complete retained local trial population exists. |
| `VALIDATED` | G1–G11, all ten dimensions, and required independent reviews pass. |
| `PAPER_PROVEN` | Separate later G12 prospective paper evidence passes. |
| `LIVE_PROVEN` | Future live evidence only; unreachable under this plan. |
| `BLOCKED` | A named data, license, semantic, architecture, or admission blocker exists. |
| `REJECTED` | The candidate failed policy, integrity, reproduction, or research gates. |
| `EXCLUDED` | Closed/protected/invite-only/purchased/unlawful or out-of-scope implementation. |

Catalog presence means discoverability only. It does not mean implemented, profitable, validated,
recommended, or approved.

---

## Phase 0 — Documentation discovery and versioned inventory freeze

Status: COMPLETE for plan creation; repeat at implementation start because the upstream catalog is
mutable.

### What to implement

1. Create a dated immutable inventory manifest for the current built-in Strategies, Indicators,
   Profiles, and Patterns tabs. Capture item name, type, official URL, observed access class,
   source-code visibility, documentation/source availability, and observed-at UTC.
2. Seed the strategy manifest with the 22 currently evidenced built-ins, then reconcile it against
   the live UI and record additions/removals instead of overwriting history.
3. Create a separate community discovery policy that defines allowed manual/API discovery,
   pagination boundaries, refresh cadence, rate limits, and completeness limitations before any
   automated collection is proposed.
4. Record a dated terms/license evidence note and require a legal/product review before commercial
   redistribution or automated bulk collection.

### Allowed APIs and copy sources

- Copy source identity and strict parsing patterns from
  `src/tios/research_assets/registry.py` and `src/tios/research_assets/source_intake.py`.
- Copy the existing TradingView intake fields and prohibitions from
  `research/EXTERNAL_SOURCE_INTAKE_PLANS_V1.yaml` rather than inventing a second intake schema.
- Copy immutable manifest/digest behavior from existing dataset and strategy-version registries.
- Use the official TradingView pages listed above only as discovery/reference sources.

### Verification checklist

- The frozen manifest is deterministic and content-addressed.
- Every built-in UI item has one row or a named capture gap.
- The manifest reports its observation time and never claims timeless completeness.
- Re-running unchanged discovery is idempotent; changed upstream content creates a new snapshot.
- No credentials, cookies, private account content, scraping bypass, or TradingView datafeed enters
  the artifact.

### Anti-pattern guards

- Do not infer the complete live inventory from the currently stale official folder index.
- Do not bulk scrape community descriptions, code, metrics, or user accounts.
- Do not call a catalog snapshot an implemented strategy set.

## Phase 1 — Catalog, feature, and source contracts

### What to implement

1. Add one strict `TradingViewCatalogItem`-style research contract under the existing
   `research_assets` ownership boundary. Required fields include source ID, upstream item ID/URL,
   item type, access class, source visibility, license/reuse status, snapshot digest, upstream
   version/Pine version, capture time, supersession links, lifecycle state, blockers, and
   `execution_authority=NONE`.
2. Propose an architecture decision for first-class `IndicatorDefinition` and `PatternDefinition`
   research entities. Do not overload `CanonicalStrategySpec.indicators` with an unversioned global
   feature library.
3. Define each indicator with exact inputs, outputs, formula, smoothing/seed convention, parameter
   domain, lookback/warm-up, missing-value rules, timeframe semantics, causal availability time,
   implementation version/hash, source/license refs, and reference fixtures.
4. Define each pattern with exact geometry/rules, required pivots, confirmation delay, invalidation,
   lookback, in-progress/final state, repaint behavior, target semantics, implementation version,
   source/license refs, and labeled reference fixtures.
5. Add equivalence/deduplication keys so aliases and cosmetically different scripts map to one
   mechanism/family and share multiplicity lineage.

### Documentation references

- `docs/architecture/TYPE_AND_CONTRACT_CATALOG.md` — `ResearchSource`, `CanonicalStrategySpec`,
  `StrategyVersion`, `Experiment`, `Scorecard`, and `ValidationPackage` invariants.
- `src/tios/strategy/spec.py::Indicator` — existing strategy-local indicator shape.
- `src/tios/strategy/registry.py::{register, resolve, verify_artifact_spec}` — immutable identity.
- `docs/security/INGESTED_CODE_CONTAINMENT.md` — untrusted-code boundary.

### Verification checklist

- Strict parsers reject missing/extra fields, duplicate IDs, invalid transitions, and unknown access
  or license classes.
- Any semantic change creates a new definition/version hash.
- Every definition has point-in-time availability and repaint status.
- Protected/invite-only/purchased items cannot reach `LICENSE_CLEARED` or `SPECIFIED` without an
  explicit direct license artifact.
- Architecture Guardian review and a new decision-log entry approve the new entity types before
  implementation changes the type catalog.

### Anti-pattern guards

- Do not store executable foreign code inside catalog rows.
- Do not treat a display plot, name, or prose description as an exact formula.
- Do not create another StrategyVersion identity system.

## Phase 2 — OS-native indicator engine and parity harness

### What to implement

1. Extract a versioned OS-native indicator library behind a pure deterministic interface. Preserve
   the current evaluator's fail-closed behavior while adapters move one proven indicator at a time.
2. Prioritize primitives required by the 22 built-in strategies and existing candidates before
   broad indicator coverage: moving-average variants, Bollinger/Keltner/Donchian channels, MACD,
   momentum, RSI, stochastic, ATR, Parabolic SAR, Supertrend, pivot calculations, and technical
   ratings inputs.
3. For every indicator, create hand-verifiable micro fixtures and independent reference vectors.
   User-authorized TradingView CSV output may be retained only as a bounded parity fixture, never as
   a production datafeed or bot input.
4. Test warm-up, seeds, smoothing, rounding, `na` propagation, parameter boundaries, recursive
   history sensitivity, bar-close availability, and future-bar mutation.
5. Add explicit support states: `SUPPORTED_EXACT`, `SUPPORTED_WITH_DECLARED_DIVERGENCE`, and
   `UNSUPPORTED`. Strategy translation fails when a required feature is not exact enough.

### Documentation references

- Copy pure Decimal-based formulas and signal transitions from
  `src/tios/strategy/evaluator.py`; do not copy ad-hoc formulas from research scripts without parity
  review.
- Copy fixture strategy from `fixtures/micro/` and `docs/testing/TEST_MASTER_PLAN.md`.
- Copy causal future-mutation testing from `tests/test_canonical_baseline_engine.py`.
- Copy current public-search builder tests from `tests/test_external_strategy_search.py` only as
  hypotheses to re-verify, not as authoritative TradingView parity.

### Verification checklist

- Golden vector parity passes within per-indicator declared Decimal tolerances.
- Mutating future bars cannot change past confirmed outputs.
- Different warm-up history either produces identical mature outputs or an explicit recursive
  sensitivity blocker.
- Missing volume or unsupported fields fail closed for volume-dependent indicators.
- Existing canonical evaluator tests remain byte/behavior compatible until an explicit migration.

### Anti-pattern guards

- No floating placeholder formula presented as parity-complete.
- No library dependency becomes the semantic authority without reference-vector tests.
- No indicator output becomes an order or approval.

## Phase 3 — OS-native pattern engine

### What to implement

1. Separate candlestick patterns from multi-bar chart patterns.
2. Migrate and version the four existing candlestick-pattern hypotheses from
   `scripts/run_external_strategy_search.py` after exact definition and parity review.
3. Build a first chart-pattern research manifest for the 16 currently documented TradingView names:
   bullish/bearish flags, bullish/bearish pennants, double/triple tops and bottoms, head-and-
   shoulders and inverse, rising/falling wedges, triangle, rectangle, cup-and-handle, and inverted
   cup-and-handle.
4. Implement detectors from transparent, independently sourced definitions—not by reverse
   engineering TradingView's unavailable Chart Pattern source. Label them `OS_NATIVE`, never
   “TradingView identical,” unless exact lawful parity evidence later exists.
5. Require confirmed-pivot timing, detection timestamp, in-progress/final state, invalidation, and
   target calculations in every detection artifact.
6. Build human-labeled evaluation sets and measure precision, recall, inter-rater disagreement,
   detection delay, and stability under one-bar extensions.

### Documentation references

- Official scope reference:
  [All Chart Patterns](https://www.tradingview.com/support/solutions/43000706927-all-chart-patterns/).
- Copy causal bar-index and deterministic test patterns from existing evaluator/micro-fixture tests.
- Copy evidence/source fields from `ResearchSource`, not from TradingView chart output.

### Verification checklist

- No confirmed pattern appears before its required confirmation bars exist.
- Adding future bars cannot move an earlier recorded detection time backward.
- Precision/recall and disagreement are reported separately; no single accuracy score hides class
  imbalance.
- Each detector has adversarial near-miss fixtures and a minimum-data blocker.
- Pattern output is a feature event, not a strategy signal or order.

### Anti-pattern guards

- Do not visually clone proprietary Chart Pattern behavior.
- Do not use ZigZag/future pivots without recording confirmation delay.
- Do not market pattern targets as predictions or guarantees.

## Phase 4 — First compatibility tranche: all frozen built-in strategies

### What to implement

1. For each item in the Phase-0 built-in manifest, capture official source/help, visible Pine source
   when lawfully available, exact defaults, position direction, sizing, order types, pyramiding,
   risk functions, calculation flags, and Strategy Report settings.
2. Translate each candidate into `CanonicalStrategySpec` only when the current rule model can
   express it without loss. Open an architecture decision for unsupported short, reversal,
   pyramiding, intrabar, or risk semantics; do not approximate them silently.
3. Register every accepted spec with `src/tios/strategy/registry.py::register` and link aliases to
   existing mechanisms and trials.
4. Produce a three-level parity report per strategy:
   - feature/output vector parity;
   - signal and order-intent parity;
   - trade-ledger/metric parity under fixed broker-emulator assumptions.
5. Freeze symbol, venue, standard OHLC chart type, timeframe, session, timezone, data window,
   adjustment rules, warm-up, tick size/rounding, capital, sizing, fees, slippage, margin,
   pyramiding, `calc_on_every_tick`, `calc_on_order_fills`, `process_orders_on_close`, and Bar
   Magnifier state in every comparison.

### Documentation references

- Copy the existing Pine seed dossier structure from `strategies/seed/07-pine-bb-strategy/` and
  `strategies/seed/08-pine-supertrend-strategy/`.
- Copy spec validation from `src/tios/strategy/spec.py` and `validator.py`.
- Copy local parity/divergence reporting from
  `scripts/run_tradingview_public_strategy_replay.py` and its tests.
- Use official strategy pages and Pine strategy execution documentation as reference evidence.

### Verification checklist

- 100% of the frozen built-in manifest has a terminal catalog status.
- Every implemented built-in resolves to one immutable strategy version and complete source/license
  dossier.
- Every unimplementable item has a precise semantic, source, data, or license blocker.
- Long/short/reversal, risk, fill timing, sizing, and cost semantics are never discarded.
- A parity pass still leaves the strategy `UNVALIDATED` and `approval_eligible=false`.

### Anti-pattern guards

- Do not port only the entry rule and call it the same strategy.
- Do not compare results produced with different chart types, datasets, costs, or fill settings.
- Do not inherit a TradingView performance claim.

## Phase 5 — Open-source community candidate intake

### What to implement

1. Extend the existing eight-candidate batch process in small, preregistered source batches.
2. Admit only public, source-visible scripts whose exact license/reuse obligations are recorded and
   compatible with the intended OS use. Protected and invite-only items remain excluded unless a
   direct author license is retained.
3. Run source files as untrusted data through the containment workflow: snapshot hash, isolated
   environment, no inherited secrets, no network, bounded resources, logs, and manifest.
4. Cluster near-duplicates by formula/rules/parameters/source lineage before creating hypotheses.
5. Prefer genuinely new mechanisms or independently useful source corroboration. Link duplicates
   to existing closed families and trial populations instead of re-testing under new names.
6. Require human/legal review before any automated discovery or bulk capture capability.

### Documentation references

- `research/EXTERNAL_SOURCE_PUBLIC_CAPTURE_V1.yaml` — access and reuse classification.
- `research/EXTERNAL_SOURCE_INTAKE_PLANS_V1.yaml` — current TradingView plan.
- `docs/security/INGESTED_CODE_CONTAINMENT.md` — containment requirements.
- `tests/test_tradingview_public_strategy_candidates.py` and
  `tests/test_strategy_ingestion.py` — existing boundary tests.

### Verification checklist

- Every source has URL, author, capture time, access class, license evidence, hash, Pine version,
  attribution obligations, and terms-review status.
- Duplicate/alias detection binds multiplicity lineage and cannot reset a trial budget.
- Closed-source code and account-gated content never appear in repository artifacts.
- Intake cannot represent admission, approval, or execution authority.

### Anti-pattern guards

- No popularity/top/trending/editor badge as selection evidence.
- No behavioral cloning of protected or invite-only scripts.
- No automatic conversion of arbitrary Pine into trusted in-process Python.

## Phase 6 — Feature selection, confluence, and calibrated confidence research

### What to implement

1. Treat every indicator/pattern combination as a preregistered hypothesis with a hierarchy-wide
   trial identity and budget.
2. Measure feature redundancy using rank/linear correlation, mutual information where justified,
   shared lookbacks, and signal-overlap matrices. Cluster redundant features before confluence
   research.
3. Require ablation and incremental-value tests: baseline alone versus baseline + feature, with the
   same frozen split, costs, and decision threshold.
4. Use chronological walk-forward evaluation with purge/gap at least as long as the maximum
   lookback/label horizon. Keep the final holdout sealed until selection is frozen.
5. Evaluate after-cost return and risk alongside Brier score, log loss, calibration error/reliability
   curves, coverage, abstention rate, and decision utility when a model emits probabilities.
6. Calibrate confidence only on a dedicated calibration partition and evaluate calibration once on
   untouched data. Confidence must be contextual to strategy × asset × venue × timeframe × regime ×
   configuration and include sample size/freshness/blockers.
7. Retain negative results, no-trade decisions, failures, all parameter trials, and family lineage.

### Documentation references

- `src/tios/validation/splits.py` — purge/gap semantics.
- `src/tios/validation/trial_budget.py` and `campaign.py` — trial lineage and budgets.
- `research/STRATEGY_ELIGIBILITY_CONTRACT_V1.yaml` — independent dimensions and no global score.
- `docs/supervisor/STATISTICAL_REMEDIATION_PLAN_D112_2026-07-21.md` — statistical remediation.

### Verification checklist

- Adding a duplicate indicator cannot increase an evidence score or modeled confidence.
- Every reported lift includes uncertainty, sample size, trials considered, after-cost effect, and
  an ablation reference.
- Holdout access occurs only after selection freeze and exactly as preregistered.
- Calibration metrics are computed out of sample; label leakage and future-bar mutation tests pass.
- No feature or ensemble reaches promotion because it merely improves one metric.

### Anti-pattern guards

- No majority vote across correlated indicators.
- No optimization for maximum historical profit or win rate.
- No confidence percentage without a defined event, horizon, calibration set, and reliability
  evidence.
- No new indicator added solely to rescue a failed closed family.

## Phase 7 — Governed campaign, validation, and promotion integration

### What to implement

1. Keep catalog/license/spec/parity work available while campaign admission remains blocked.
2. After the separately governed external activation prerequisite is complete, copy the unified
   campaign contract and executor path from the autonomous research factory plan.
3. Bind source, feature definitions, strategy version, dataset, implementation hashes, engines,
   costs, splits, regimes, baselines, trial population, and stop rules before evaluation.
4. Produce exact G1–G11 evidence and all ten independent scorecard dimensions.
5. Require independent statistical, risk, supervisor, and security reviews. G12 remains a later
   prospective paper-forward gate.

### Documentation references

- `docs/supervisor/AUTONOMOUS_RESEARCH_FACTORY_AND_OPERATIONS_PLAN_2026-07-21.md`, Phases 2b–5.
- `src/tios/validation/eligibility.py` and `promotion_package.py`.
- `src/tios/approval/history.py` and `state.py`.

### Verification checklist

- Before external activation, no catalog or parity item can become campaign-admitted.
- Missing evidence is `NOT_ELIGIBLE`, never zero or PASS.
- G1–G11 and every required dimension/review are present and PASS before offline promotion.
- Catalog, research, validation, paper, and live states remain distinct in API and UI.

### Anti-pattern guards

- Do not weaken the admission gate to accelerate catalog testing.
- Do not let the implementing agent self-satisfy independent review roles.
- Do not convert Strategy Report metrics into OS gate evidence.

## Phase 8 — OS Strategies, Indicators, and Patterns product surface

### What to implement

1. Replace the current five-row Strategies projection with the unified registry/read model. Preserve
   source catalogs and immutable strategy versions as truth; the dashboard remains a projection.
2. Add separate tabs or filters for `Strategies`, `Indicators`, and `Patterns`.
3. Show lifecycle badge, family, source class, license/access, version, supported assets/timeframes,
   parity state, latest local research state, evidence freshness, blockers, and evidence links.
4. Add comparisons that keep the ten evidence dimensions separate. If a probability/confidence is
   shown, include its event/horizon, sample size, calibration state, and freshness beside it.
5. Keep `Open full TradingView chart` as external context only; no chart selection can import,
   activate, or execute a strategy.
6. Add explicit counts: cataloged, source-captured, license-cleared, specified, parity-tested,
   research-tested, validated, blocked, rejected, and excluded.

### Documentation references

- Copy read-only projection patterns from `src/tios/services/dashboard_api/status.py` and
  `strategy_eligibility.py`.
- Copy view/accessibility and safety patterns from
  `src/tios/services/dashboard_ui/dashboard.html` and `tests/test_dashboard.py`.
- Preserve dashboard projection boundaries in `docs/architecture/AD.md`, D-034.

### Verification checklist

- All registered/current catalog items appear exactly once or have a documented projection blocker.
- A user can distinguish cataloged from implemented and validated without opening an artifact.
- Filters are keyboard-accessible, mobile-bounded, and have exact table alternatives.
- UI exposes no import, run, approve, paper, live, credential, or order action.
- API safety flags remain `execution_authority=NONE`, venue connection absent, and order capability
  disabled.

### Anti-pattern guards

- No green badge for catalog presence alone.
- No “best strategy” leaderboard without complete comparable contexts and evidence.
- No mixed TradingView performance and local OS performance column without explicit provenance.

## Phase 9 — Refresh, drift, retirement, and observability

### What to implement

1. Add a bounded periodic metadata refresh only after terms/product/legal approval and a documented
   supported collection method exist.
2. Diff upstream inventory by immutable snapshots; never mutate history.
3. Flag removed, renamed, source-changed, license-changed, formula-changed, or Pine-version-changed
   items for re-review. A source change invalidates parity until re-established.
4. Record ingestion failures, rate limits, access changes, duplicate clusters, license blockers,
   parity drift, test failures, and stale evidence as first-class observations.
5. Retire or supersede OS definitions without deleting their historical experiments or approvals.

### Documentation references

- Copy freshness/supersession behavior from `ResearchSourceRegistry`.
- Copy append-only/idempotent operational patterns from existing jobs and evidence stores only after
  an allowlisted handler is approved.
- Copy monitoring boundaries from the autonomous research factory plan; do not add a generic job.

### Verification checklist

- Unchanged refresh is idempotent; drift creates a new source snapshot and blocker.
- A removed upstream item remains historically resolvable.
- Refresh failure cannot change implementation, validation, approval, or runtime state.
- No arbitrary URL, code, or shell payload enters a worker.

### Anti-pattern guards

- No unattended scraper or browser automation before approval.
- No auto-update of production strategy formulas from upstream changes.
- No auto-promotion after a successful refresh or parity check.

## Phase 10 — Final verification and release gate

### Verification sequence

1. Re-read the current official documentation and compare every implemented API/field to the frozen
   Phase-0 allowed-API list.
2. Grep for prohibited paths: TradingView data/alerts as inputs, protected/invite-only source,
   execution callbacks, global confidence/weighted score, unversioned indicator formulas, and
   uncounted trials.
3. Run focused unit, property, parser, license, containment, parity, future-mutation, recursive,
   split/leakage, trial-budget, validation, API, dashboard, and architecture-boundary tests.
4. Run deterministic end-to-end reproduction for at least one simple built-in per supported semantic
   class.
5. Run `make check` once, serially.
6. Obtain Architecture Guardian, statistical, risk, supervisor, security, license/legal, and product
   reviews appropriate to the implemented tranche.

### Release acceptance criteria

- 100% of the frozen built-in strategy manifest has a terminal catalog state.
- 100% of implemented items have immutable source, license, definition/spec, implementation, and
  parity evidence.
- 0 protected/invite-only/purchased sources are copied or behaviorally cloned.
- 0 TradingView market-data or alert outputs feed OS decisions.
- 0 duplicate indicators can inflate confidence/evidence.
- 0 missing/unsupported semantics silently fall back.
- 100% of research trials are retained and linked to family-wide multiplicity lineage.
- The dashboard truthfully separates cataloged, implemented, parity-tested, research-tested,
  validated, paper-proven, and live-proven states.
- No new live, venue, credential, order, or capital authority exists.

## Priority order

1. Freeze the live built-in inventory and terms evidence.
2. Approve feature/catalog contracts and deduplication lineage.
3. Build exact indicator primitives and parity fixtures needed by the built-ins.
4. Complete the 22-candidate built-in strategy compatibility tranche.
5. Build OS-native candlestick/chart-pattern research definitions.
6. Expand open-source community intake in bounded, deduplicated batches.
7. Run confluence/calibration research only after causal feature integrity is proven.
8. Unify the OS product surface.
9. Activate governed campaigns only after the existing independent admission blocker is resolved.

## Known unknowns and required decisions

- Exact live built-in inventory and source visibility as of implementation start.
- Exact full indicator/profile/pattern inventory and which items require non-OHLCV/fundamental data.
- Whether the OS is private, commercial, distributed, or paywalled; this affects license review.
- Approved supported method, if any, for periodic TradingView public metadata discovery.
- Direct licenses, if any, for community scripts the operator wants prioritized.
- Whether short/reversal/pyramiding/intrabar/risk semantics justify expanding
  `CanonicalStrategySpec` or require a separate execution-neutral research representation.
- Exact reference tolerance and authoritative fixtures for each indicator/strategy.
- Human-labeled datasets and annotation policy for subjective chart patterns.
- Resolution of the existing external independent-review activation blocker before campaign
  admission.

## Recommended next action

Approve only Phase 0 and the Phase-1 architecture decision first. That produces a defensible exact
inventory, legal/source boundary, entity model, deduplication policy, and effort estimate before any
strategy formula or foreign source is implemented. Implementation should then proceed in bounded
tranches with a review checkpoint after each phase.
