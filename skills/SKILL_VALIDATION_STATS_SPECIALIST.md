# Skill: Validation Stats Specialist (v1)

Role: R4/R7 · Cost tier: high · Status: specified, not yet implemented

## Purpose
Verify statistical validation methods (PBO/CSCV, DSR, and successors) against primary literature before their outputs are trusted in gates (G10 requirement).

## Trigger conditions
First implementation of PBO/DSR; any change to their code; adoption of any new multiple-testing/overfitting statistic.

## Inputs
Primary papers (Bailey et al. PBO ssrn 2326253; Bailey & López de Prado DSR ssrn 2460551), the implementation, test fixtures.

## Process
1. Extract the method's exact assumptions (return distribution, independence, trial definitions) from the paper.
2. Map each equation to code; verify constants, estimator choices, and edge cases (small N trials, short samples).
3. Construct known-answer fixtures: synthetic trial populations where PBO/DSR values are analytically or numerically derivable; require implementation match.
4. Document interpretation limits (what the statistic does NOT prove) for the validation report template.
5. Verdict: METHOD_VALIDATED / DEVIATIONS(listed) / NOT_VALIDATED.

## Outputs (contract)
Method validation report + known-answer fixtures added to `tests/golden/`; verdict gates G10's status from "method candidate" to "active gate".

## Prohibited behavior
Trusting third-party library implementations without fixture verification; presenting PBO/DSR as profitability proof; silently substituting a simpler statistic.

## Quality gates
Known-answer fixtures pass; assumptions documented; interpretation-limits section present.

## When NOT to use
Routine gate execution (validation module code does that once validated).

## Model suitability
Highest tier; mathematical correctness is the point.
