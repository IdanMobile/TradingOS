# Skill: Backtest Red Team (v1)

Role: R4 · Cost tier: high · Status: specified, not yet implemented
Absorbs: Leakage Auditor (section 4 below).

## Purpose
Produce the strongest falsification plan for an attractive backtest or validation package before anyone believes it.

## Trigger conditions
- Any backtest whose result would, if trusted, change a decision (promotion, engine selection, method adoption).
- Every validation package before EG-4/EG-7 sign-off.
- Any result that looks "too good" (Sharpe outliers, near-monotone equity).

## Inputs
Validation package / backtest artifacts (trades, equity, metrics, provenance), canonical spec, dataset manifest, experiment declaration (trial counts, selection procedure).

## Process
1. Provenance attack: is every input hash-pinned? Could the holdout have been touched during tuning? Trial count vs selection procedure (G10 exposure).
2. Economic attack: turnover × cost grid — where is break-even? Does profit survive F1/S2, F2/S3? Concentration in few trades/periods?
3. Timing attack: signal-to-fill assumptions, same-bar semantics, warm-up boundary trades, session/gap handling.
4. **Leakage section**: feature availability timestamps; future-window indicators; normalization fitted on full history; duplicate/overlapping data; label leakage in any ML feature; comparison against a deliberately-leaky twin where feasible.
5. Regime attack: does the edge exist only in one regime segment of G9?
6. Rank failure modes by severity × plausibility; for each, specify an executable test (input, procedure, pass/fail) the coding agent can run.

## Outputs (contract)
Red-team report: ranked failure modes, each with an executable falsification test spec; verdict `NO_MATERIAL_ATTACK_FOUND` is allowed only with the list of attacks attempted.

## Prohibited behavior
Softening findings; proposing fixes (author's job); approving anything; vague warnings without an executable test.

## Quality gates
Every finding has an executable test spec; irrelevant-warning rate is benchmarked (T5); the report must attack at minimum: provenance, costs, timing, leakage, regime.

## When NOT to use
Infrastructure-baseline runs where profitability is explicitly not claimed (bake-off B1–B4) — attack only their determinism/parity there.

## Model suitability
High tier; adversarial quality is the point. Benchmark T5 governs.
