# Coding Agent Readiness Gate V1

Date: 2026-07-05
Decision: PASS for constrained prototype execution, conditional on completion of the mandatory pre-code environment/credentials intake gate.

## Scope of PASS

The project is ready to be handed to a coding agent for:
- environment bootstrap;
- canonical data snapshot construction;
- engine bake-off execution;
- experiment-lineage prototype;
- strategy-ingestion seed batch;
- first validation harness;
- minimal evidence dashboard/control surface;
- evidence-backed recommendation report.

## Scope explicitly NOT approved

- full Trading Intelligence OS build;
- final production architecture;
- live/real-money trading;
- storing real exchange credentials;
- autonomous execution;
- choosing tools by agent preference without tests;
- silently dropping candidates;
- mass strategy scraping;
- paid data purchase without approval.

## Why PASS is justified

1. North Star is stable.
2. MVP market and sequence are locked.
3. Reuse-first rule is explicit.
4. Serious candidates were researched from current official sources.
5. Common tests and acceptance gates exist.
6. Canonical dataset and transaction-cost assumptions are defined.
7. Backtesting validation model exists.
8. Experiment lineage prototype is bounded.
9. AI/agent evaluation and strategy ingestion are bounded.
10. Remaining uncertainties require executable evidence.

## Human-only blockers deferred

These do not block prototype work:
- live exchange account eligibility;
- account-specific fee tier;
- live API permissions;
- paid data purchase;
- real-money capital amount.

They become mandatory before later phases.

## Required first instruction

Use only:
`handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md`

This is the single operational SSOT for coding-agent execution.

Before any coding/scaffolding/install-driven implementation work, the agent must complete:
`specs/ENVIRONMENT_AND_CREDENTIALS_INTAKE_GATE_V1.md`
