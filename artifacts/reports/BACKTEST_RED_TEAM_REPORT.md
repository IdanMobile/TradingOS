# Backtest Red-Team Report

Status: **NO APPROVAL — MATERIAL ISSUES REMAIN**.

The executable red-team record for the retained B2 F0/S0 package is
`artifacts/validation/B2_F0_S0/red_team_report.json`. It attacks provenance,
costs, timing, leakage, regimes, and multiple-testing exposure. The report does
not approve the strategy; B2 remains a rejected infrastructure baseline.

The strongest open issue is G4: the Freqtrade lookahead follow-up overrides the
requested fixed stake and trade-limit settings, leaving a WARN. G10 is honestly
deferred as a method candidate until PBO/DSR literature review and known-answer
fixtures are complete. The zero-cost-only hard-fail predicate is demonstrated by
`tests/test_validation_gates.py::test_cost_rule_hard_fails_zero_cost_only_profit`.
