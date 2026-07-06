# Trading Intelligence OS — Living Project Package

This ZIP is the continuity and handoff package for the project.

## Current status

Ready for constrained coding-agent prototype execution.

## Start here as a human

1. `PROJECT_STATE.md`
2. `TRADING_OS_NORTH_STAR.md`
3. `docs/product/MVP_SCOPE.md` and `docs/program/PROGRAM_PLAN.md`
4. `DECISION_LOG.md`
5. `decisions/CODING_AGENT_READINESS_GATE_V1.md`
6. `docs/architecture/AD.md` for the architecture decision record (note maturity labels)

## Start here as the coding agent

Read and execute only:

`handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md`

This is the single operational source of truth (SSOT) for coding-agent execution. All other files are subordinate according to the precedence hierarchy defined inside that file.

Do not give the coding agent only the North Star and ask it to build everything.

## Package purpose

Preserve:
- decisions;
- research;
- evidence requirements;
- open items;
- rejected directions;
- specs;
- handoff instructions.

The package should be updated after every major research, prototype, decision, or handoff phase.


## Handoff integrity

Before giving this package to a coding agent, keep the ZIP intact. The package includes:

- `PACKAGE_INTEGRITY_MANIFEST.md` — required handoff inputs and expected generated outputs;
- `handoffs/HANDOFF_SIMULATION_AUDIT_V1.md` — fresh-agent flow simulation and audit findings.

The coding agent must start only from the SSOT path documented above.
