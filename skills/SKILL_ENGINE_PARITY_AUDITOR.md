# Skill: Engine Parity Auditor (v1)

Role: R4 · Cost tier: high · Status: specified, not yet implemented
Absorbs: Fee/Slippage Auditor (section 3).

## Purpose
Explain every cross-engine divergence semantically (WS4 rule: a numeric P&L difference without semantic diagnosis is insufficient).

## Trigger conditions
Bake-off parity runs; any engine version upgrade; any adapter change touching normalization.

## Inputs
Normalized results from ≥2 engines for the same baseline/dataset/scenario; adapter capability reports; engine docs.

## Process
1. Align signal timestamps; classify mismatches: warm-up length, indicator formula variant (e.g., EMA seeding), same-bar execution, session boundaries, data feed granularity.
2. Align trades: entry/exit timing deltas, fill price assumptions, partial fills, rounding/lot constraints.
3. **Cost audit**: verify each engine actually applied the configured fee/slippage scenario (recompute expected fees from trades; compare); confirm the scenario grid completeness (6 mandatory cells).
4. Attribute every residual numeric delta to a classified cause or mark `UNEXPLAINED` (which blocks parity PASS).
5. Write per-divergence: cause class, evidence, whether it is engine-config-fixable, adapter-normalizable, or intrinsic semantics.

## Outputs (contract)
Divergence report per engine pair per baseline; parity verdict: EXPLAINED / UNEXPLAINED_RESIDUAL (itemized).

## Prohibited behavior
Averaging away divergences; declaring parity from aggregate metrics; hiding an engine's failure to apply costs.

## Quality gates
Zero `UNEXPLAINED` items for a PASS; recomputed fee totals match configured scenario within documented tolerance.

## When NOT to use
Single-engine determinism checks (that is gate G1).

## Model suitability
High tier for diagnosis; the alignment computations are code, not prose.
