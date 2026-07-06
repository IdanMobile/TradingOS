# Skill: Architecture Guardian (v1)

Role: R9 · Cost tier: high · Status: specified, not yet implemented
Absorbs: Dependency Boundary Auditor.

## Purpose
Review changes and decisions against `docs/architecture/AD.md`, the MODULE_CATALOG dependency law, and SSOT boundaries; detect drift between documents and code.

## Trigger conditions
Any non-trivial diff during S1/S2; any proposed new dependency; any new module; periodically per stage exit; whenever docs and code disagree.

## Inputs
Diff/PR, AD.md, MODULE_CATALOG.md, TYPE_AND_CONTRACT_CATALOG.md, DECISION_LOG.md.

## Process
1. Dependency audit: imports vs dependency law; new third-party deps vs reuse matrix + license policy (note: Freqtrade is GPL-3.0, NautilusTrader LGPL-3.0, backtesting.py AGPL-3.0 — verified 2026-07-06; process isolation vs code-linking implications must be assessed per use).
2. Boundary audit: deterministic/non-deterministic boundary intact (no AI call inside deterministic execution paths); no live-trading affordances; paper/live separation.
3. Contract audit: changed types/serialization vs catalog versioning rules.
4. Drift audit: does the change contradict an Approved decision? If deliberately so → require decision-log amendment, not silent divergence.
5. Report violations with file/line refs + the specific rule breached; propose (never self-approve) decision-log entries.

## Outputs (contract)
Review report: violations (blocking), concerns (non-blocking), doc-drift list.

## Prohibited behavior
Rewriting the SSOT; approving its own proposals; style nitpicking presented as architecture findings.

## Quality gates
Every violation cites the exact rule/file; zero unexplained "just seems wrong" findings.

## When NOT to use
Trivial mechanical changes with no dependency/contract surface.

## Model suitability
High tier; judgment-heavy.
