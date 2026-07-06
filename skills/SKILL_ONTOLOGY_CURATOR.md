# Skill: Ontology Curator (v1)

Role: R6 · Cost tier: mid · Status: specified, not yet implemented
Absorbs: Ontology Extractor + Dictionary Curator.

## Purpose
Extract and curate canonical trading concepts (CON records) with aliases, abbreviations, and venue/market-specific meanings preserved — never flattened.

## Trigger conditions
An MVP artifact references an undefined term; seeding batches from license-cleared sources; SOURCE_VERIFIER flags a definition change.

## Inputs
Authoritative source documents (exchange docs, regulator glossaries, FIBO — MIT-licensed, verified 2026-07-06 and safe to seed from), existing concept table.

## Process
1. Extract candidate concepts with exact source spans.
2. Check licensing before ingesting any external glossary text: FIBO OK (MIT); Investopedia and similar copyrighted glossaries are NOT ingestible verbatim (write original definitions instead, cite the concept only).
3. For overloaded terms, create context-specific meaning entries (venue variant, market variant) rather than merging.
4. Link related concepts; record abbreviation collisions (e.g., "BE" break-even vs. other uses) explicitly.
5. Dictionary/config boundary: definitions never contain strategy parameter values (North Star rule: TP1 *means* first take-profit; TP1=+2% is strategy config).

## Outputs (contract)
CON records with provenance + ambiguity flags; incorrect-merge rate is benchmarked (T7).

## Prohibited behavior
Wholesale scraping of copyrighted glossaries; merging distinct venue semantics; inventing authoritative-sounding definitions without a source or an `internal-definition` tag.

## Quality gates
Every concept has ≥1 source or an explicit internal-definition tag; overloaded terms have ≥2 context entries or a reviewed justification.

## When NOT to use
Full ontology ingestion (explicitly deferred — MISSING_AND_OPEN_ITEMS); MVP seeds only concepts actually referenced by MVP artifacts.

## Model suitability
Mid tier; precision/recall benchmarked (T7).
