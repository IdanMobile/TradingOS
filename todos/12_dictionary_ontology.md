# Initiative 12 — Dictionary / Ontology (S2)

Requirement source: AD §V (AD-08/AD-09), North Star §9.3. Skills: R6 (SKILL_ONTOLOGY_CURATOR) + R7. Entry: S2 + RG-16 concept extraction from S1 artifacts.

## T-012-01 Concept tables + FTS (relational, per AD-08)
- Acceptance: CON/alias/context-variant schema + FTS query tests. Complexity: M. Status: **DONE FOR BOUNDED S2 2026-07-10** — `ConceptRegistry` validates `CON-*` records from `research/DICTIONARY_CONCEPTS_V1.json` and exposes SQLite FTS5 search over names, aliases, definitions, categories, market contexts, and venue variants.

## T-012-02 FIBO-seeded first batch (license-clean, AD-09)
- Acceptance: seeded concepts carry FIBO provenance; no scraped copyrighted definitions (audit). Complexity: M. Status: **DONE FOR BOUNDED S2 2026-07-10** — the first batch includes FIBO URI provenance for trading-domain concepts while definitions remain local paraphrases from project contracts; tests enforce the FIBO URI namespace and source-file existence.

## T-012-03 MVP-referenced concept backfill (RG-16)
- Acceptance: every term used in S1 artifacts resolves to a concept or an explicit gap row. Complexity: M. Status: **DONE FOR BOUNDED S2 2026-07-10** — 16 concepts cover the S1/S2 evidence vocabulary for datasets, strategies, evidence, RA/SRC, experiments, engines, validation, approval, signal/fill/order/risk, lab batches, and jobs. Full FIBO import, venue-specific meanings, and scraped definitions are explicit gap rows.

Full ontology ingestion remains deferred (MISSING_AND_OPEN_ITEMS) — do not expand scope here.
