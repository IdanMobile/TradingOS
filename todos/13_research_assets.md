# Initiative 13 — Research Assets (S2)

Requirement source: AD §U, type catalog §2 RA, D-006. Skills: R5 + R7. Entry: S2.

## T-013-01 RA registry implementation
- Acceptance: RA records with freshness states, supersession chains, consumer tracking; invalid-without-evidence enforcement. Complexity: M. Status: **DONE FOR BOUNDED S2 2026-07-10** — `research/RESEARCH_ASSETS_V1.json` loads through `ResearchAssetRegistry`, validates evidence refs, freshness, dependencies, supersession graphs, and consumers. Focused tests cover missing evidence, unknown refs, cycles, freshness filters, and deterministic digest.

## T-013-02 Backfill S0/S1 research as first RAs
- Purpose: this planning pass's research (registry, gap matrix closures) becomes queryable RAs with freshness triggers.
- Acceptance: ≥5 RAs from existing artifacts; human review flags set. Complexity: S. Status: **DONE FOR BOUNDED S2 2026-07-10** — 8 retained RAs backfill S0/S1/S2 environment, dataset, engine, validation, lineage, seed-ingestion, LAB-799, and seed-cycle evidence; each has human-review status, consumers, freshness, reverify trigger, and existing source/quality refs.

## T-013-03 Cost-amortization view
- Acceptance: reuse counts per RA feed cost intelligence. Complexity: S. Status: **DONE FOR BOUNDED S2 2026-07-10** — `ResearchAssetRegistry.cost_amortization()` projects cost, consumer count, consumers, and cost per consumer from the retained RA registry; current local evidence has zero external cost but reuse counts are queryable and tested.
