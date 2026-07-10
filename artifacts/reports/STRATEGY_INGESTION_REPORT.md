# Strategy Ingestion Report — Seed Batch (T-010-12, EG-5)

Status: 10/10 seed items ingested (`research/EXISTING_STRATEGY_REGISTRY_V1.md`).
This report answers the five completion-report questions from
`specs/STRATEGY_SEED_BATCH_V1.md`.

## 1. Recurring schema fields

Every one of the 10 items needed the same handful of fields regardless of
source class:

- `family` (trend_following / mean_reversion / breakout / market_making):
  always resolvable, even for the schema-mismatched market-making item.
- Two mandatory assumption strings — a warm-up statement and a bar
  close/open timing statement — were needed on every single item, including
  the one (market making) where they carry no real content. That the
  validator forces these even when meaningless (item 6) suggests the
  validator's completeness check is tuned for directional strategies and
  should eventually gain a family-aware exemption, rather than forcing
  boilerplate assumption text.
- `license_ref`/`source_refs` cross-links were trivial and recurring; no
  friction there.
- Every item needed at least one genuine (non-filler) ambiguity — the
  acceptance criterion "ambiguities non-empty or justified" was easy to
  satisfy honestly in all 10 cases, because every real source under-specifies
  *something* (tie-break rules, exit conventions, exact window lengths,
  warm-up handling).

## 2. Ambiguous concepts

Recurring ambiguity classes across the batch:

- **Parameter under-specification**: window lengths, thresholds, and
  tie-break rules are rarely pinned by the source itself (items 1, 2, 3, 4,
  7, 8) — sources describe a *shape*, not a fully-specified rule.
- **Timing/warm-up mapping**: every framework has its own warm-up/readiness
  semantics (LEAN `IsReady`, freqtrade `startup_candle_count`, Pine `na`
  until ready, Hummingbot `update_processed_data`); all were mapped to this
  project's uniform "no signal until window is full" assumption, which is a
  modeling choice this project makes, not something every source states
  identically.
- **Cross-sectional-to-single-instrument collapse** (items 9, 10): academic
  papers describe *ranking/portfolio* strategies; this project's spec schema
  only expresses single-instrument threshold rules. This is the single
  largest, most consequential ambiguity class in the batch — not a small
  reading choice but a structural simplification that changes what the
  strategy *is*.
- **Provenance-without-live-fetch**: no item in this pass used a browsing
  tool to pin an exact commit/permalink; every item honestly flags this as
  an ambiguity rather than fabricating a citation. This is a process
  limitation of this ingestion pass, not a property of the sources.

## 3. Incompatible semantics

Two items exposed genuine schema/semantic incompatibilities rather than mere
ambiguity:

- **Item 6 (Hummingbot `pmm_simple`, market making)**: `CanonicalStrategySpec`
  has no primitive for continuous two-sided quoting (bid + ask around a
  reference price, refresh timer, no discrete entry/exit event). It was
  force-fit using `always_in_market: true` plus a pseudo-indicator carrying
  the spread/refresh config — a workaround, not a faithful capture. Any
  future market-making ingestion at scale will need either a dedicated
  spec variant for quote-based strategies or an explicit "out of schema
  scope" rejection path.
- **Items 9-10 (academic papers)**: cross-sectional decile/rank strategies
  do not fit a single-instrument rule schema at all; the long-short design
  is also unrepresentable (this project's spec is long-only,
  entry_long/exit_long). Any future ingestion of relative-value or
  cross-sectional academic strategies will hit the same wall.

Everything else (single-instrument directional/breakout/mean-reversion
rules from frameworks 1-5, 7-8) mapped cleanly — the schema fits the
directional-signal family well; it does not fit market-making or
cross-sectional families.

## 4. License blockers

- **Copyleft granularity gap**: this project's `license_class` enum
  (`permissive | copyleft | proprietary | unclear`) cannot distinguish
  GPL-3.0's project-level copyleft (items 3, 4) from MPL-2.0's file-level
  (weak) copyleft (items 7, 8) — both bucket as `copyleft`, but the actual
  reuse obligations differ materially. Real automation would need a richer
  enum or a separate `copyleft_strength` field.
  - `code_reuse_allowed` is `true` for `copyleft` sources, meaning a naive
    reader could over-conclude "safe to reuse" without noticing the
    attribution/share-alike strings attached — worth a stronger warning in
    the gate output, not just a `requires_attribution` boolean.
- **Academic papers as `unclear`** (items 9, 10): no source code exists to
  reuse, so `code_reuse_allowed: false` is correct, but `spec_extraction_allowed`
  is always `true` regardless of `license_class` — this is precisely the
  case `license_gate()` was designed for (method/idea extraction from a
  copyrighted text is not a code copy). This worked exactly as intended and
  is the strongest validation this batch produced of the ingestion module's
  existing design (T-010-01).
- No item in this batch was a hard blocker (nothing `proprietary` with a
  no-extraction claim) — the seed spec's slot mix did not include a
  closed/opaque-claim source class, so this batch cannot speak to how well
  the workflow handles a genuinely hostile license.

## 5. Automation opportunities and hazards

**Opportunities:**
- The six-file-per-item shape is fully mechanical once a human has done the
  semantic extraction — a template/scaffolding tool (empty files + required
  keys) would remove boilerplate without touching the judgment calls.
- License-class lookup for well-known repositories (LEAN, freqtrade,
  Hummingbot) is a one-time fact per repo, not per-strategy — a small static
  table (`repo -> license_class, license_name, evidence_url`) would remove
  10 near-identical manual license_record.yaml writes down to 1 lookup.
- Validator-driven feedback (VALID_WITH_AMBIGUITIES / INVALID) is fast and
  cheap to run per item — safe to automate as a pre-commit-style gate on any
  future ingestion, human or automated.

**Hazards (why D-020's "no mass automation yet" holds after this batch):**
- The two incompatible-semantics findings (item 6, items 9-10) were only
  caught because a human was reading each source's actual mechanism, not
  just its shape. A scraper mapping "source has an indicator + a threshold"
  to a canonical spec would have silently produced a plausible-looking but
  semantically wrong spec for the market-making and academic-paper items
  (e.g., inventing a fake single-instrument momentum rule and never
  surfacing that it drops cross-sectional ranking) — the exact failure this
  workflow exists to prevent (D-011).
- Every item in this pass depended on a judgment call about warm-up,
  tie-breaks, or exit convention that the source itself did not fix;
  automating "pick a default" would quietly convert an honest ambiguity
  into a silent, unreviewed assumption at 10x-100x the volume.
- No live fetch tool was used in this pass for any item — automation at
  scale would need real browsing/fetching, license-detection, and
  provenance-pinning infrastructure that does not exist yet; building that
  before the manual batch revealed these failure modes would have automated
  the wrong thing first.

## Net conclusion

The manual seed batch did what `specs/STRATEGY_INGESTION_AND_REPRODUCTION_WORKFLOW_V1.md`'s
"automation rule" asked it to do: it surfaced a stable recurring schema (§1),
a real ambiguity taxonomy (§2), two genuine incompatible-semantics findings
that a scraper would have missed (§3), a license-enum granularity gap (§4),
and a concrete, narrow automation opportunity (templating + a static
license-lookup table) bounded by real hazards (§5). Recommendation: automate
the mechanical scaffolding only; keep semantic extraction, ambiguity
recording, and schema-fit judgment manual until a future batch demonstrates
those can be checked cheaply too.
