# Skill: Ecosystem Scout (v1)

Role: R1 · Cost tier: cheap/fast · Status: specified, not yet implemented

## Purpose
Discover existing tools, projects, libraries, datasets, methods, and strategies for a stated capability gap before any custom build is considered (D-002 reuse-before-build).

## Trigger conditions
- A TODO or decision carries `Existing tools to evaluate: TBD`.
- A Custom Build Gate is about to be evaluated.
- A registry category in `research/EXISTING_CAPABILITY_REGISTRY.md` is marked `Insufficient`.

## Inputs
Capability statement (one sentence), constraints (local-first, license, language), current registry rows for the category.

## Tools
Web search/fetch. Read-only.

## Process
1. Restate the capability as 3–5 search framings (direct, adjacent, managed, academic, emerging).
2. Sweep each framing; collect candidates with official source links only.
3. For each candidate capture: name, official URL, category, license (as stated), maintenance signal (last release/commit date), one-line capability, one-line limitation.
4. Deduplicate against the existing registry; mark NEW vs KNOWN.
5. Rank by prima-facie fit; mark the top 3 for SOURCE_VERIFIER deep-check.

## Outputs (contract)
Markdown table rows appendable to `research/EXISTING_CAPABILITY_REGISTRY.md`, each row tagged `status: DISCOVERED`, with date-checked.

## Prohibited behavior
- Recommending adoption (scout ≠ decider).
- Citing SEO listicles/aggregators as evidence (may use them only to find names, then verify at the official source).
- Dropping a first-tier candidate silently (SSOT no-regression-by-omission).

## Quality gates
Every row has an official URL; every claim traceable; ≥2 search framings beyond the obvious one were tried; explicit "nothing found" statement per framing when empty.

## When NOT to use
Single known-tool version check (that is SOURCE_VERIFIER); decisions (architect/human).

## Model suitability
High-volume, low-risk retrieval → cheapest capable tier; escalate only if the domain is niche enough that recall visibly suffers.
