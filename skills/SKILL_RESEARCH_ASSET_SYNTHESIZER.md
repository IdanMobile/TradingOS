# Skill: Research Asset Synthesizer (v1)

Role: R5 · Cost tier: high · Status: specified, not yet implemented

## Purpose
Turn completed multi-source research into a durable, reusable Research Asset (RA) with contradictions and freshness explicitly preserved (D-006, North Star §9.3-08).

## Trigger conditions
A research task produced findings likely to be consumed more than once; a research gap in `research/RESEARCH_GAP_MATRIX.md` is resolved; periodic consolidation of scattered findings.

## Inputs
Source materials + evidence records, the research question, existing RAs on adjacent topics.

## Process
1. Check for an existing RA answering this question → update/supersede rather than duplicate.
2. Weight primary sources over secondary; tag every claim with its evidence record.
3. Preserve contradictions as first-class content (never average conflicting facts).
4. State freshness: date-checked per claim + the event/time trigger that would stale the asset.
5. Declare dependencies (other RAs, datasets, tool versions) and intended consumers.
6. Set `human_review: PENDING` — an RA is not authoritative until reviewed.

## Outputs (contract)
RA record per TYPE_AND_CONTRACT_CATALOG §2 with supersession links if applicable.

## Prohibited behavior
Unsourced claims; resolving contradictions by fiat; regenerating an existing RA from scratch (amortization is the point); marking own output human-reviewed.

## Quality gates
Every claim → evidence link; contradiction section present (or explicit "none found"); freshness triggers concrete.

## When NOT to use
One-off ephemeral questions; raw discovery (Scout).

## Model suitability
High tier; synthesis quality drives downstream value. Benchmark T8 governs.
