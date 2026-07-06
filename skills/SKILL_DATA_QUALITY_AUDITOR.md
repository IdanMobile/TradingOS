# Skill: Data Quality Auditor (v1)

Role: R4 · Cost tier: mid · Status: specified, not yet implemented

## Purpose
Audit a dataset freeze against `specs/CANONICAL_BAKEOFF_DATASET_V1.md` quality gates and known source pitfalls.

## Trigger conditions
Every dataset freeze/refreeze; every new data source; source format-change alerts from SOURCE_VERIFIER.

## Inputs
Raw manifest, normalized dataset + hashes, quality report, source documentation.

## Process
1. Recompute/verify: monotonic timestamps, duplicates, interval spacing, OHLC invariants, non-negative volume, row counts.
2. Cross-check missing-interval report against known exchange downtime where documented.
3. Source-pitfall checklist (living list; current known items):
   - Binance Spot files: timestamp unit switched ms → **microseconds from 2025-01-01** (verified 2026-07-06) — mixed-unit windows must be normalized explicitly and tested at the boundary.
   - Zip integrity + published checksums where the source provides them.
   - Timezone: source claims UTC — verify against a known event candle.
4. Regeneration audit: confirm double-run hash equality evidence exists (not claimed).
5. Verdict: PASS / PASS_WITH_NOTES / FAIL(reasons).

## Outputs (contract)
Audit report attached to the dataset manifest; FAIL blocks EG-1.

## Prohibited behavior
Auditing by reading the producer's own quality report alone (must recompute or spot-verify); approving forward-filled data presented as raw.

## Quality gates
Every checklist item has evidence (computed value or artifact ref), not assertion.

## When NOT to use
Strategy-level leakage analysis (Red Team owns that).

## Model suitability
Mostly mechanical + checklist reasoning → mid tier; the checks themselves should be code the agent runs, not prose.
