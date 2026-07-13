# Initial Trading OS supervision

Use the project-local Trading OS Supervisor skill.

Goal: establish supervisory context for the current Trading OS and determine what level of research or project review is actually required.

This is a read-only supervisory run. Do not execute trades, access secrets, request private keys, install third-party skills, or modify code.

Start by:

1. Reading the project SSOT, architecture documents, current state, handoffs, manifests, and existing supervisor records.
2. Identifying the project’s stated goal, current market scope, locked decisions, constraints, and known gaps.
3. Mapping the current system at a high level without assuming that documented behavior is implemented behavior.
4. Determining whether the user’s goal can be answered with general knowledge, targeted inspection, subsystem review, or a full project review.

If the evidence is insufficient, state exactly what is missing and why. Ask for the smallest necessary review or clarification. Do not automatically launch a full audit merely because the project is complex.

If a broad review is genuinely required, present the proposed scope and explain the reason before starting it.

When enough context is available, report:

- verified project facts;
- current architecture and ownership boundaries;
- active strategies, research, data, validation, risk, and execution capabilities;
- unknowns and unsupported assumptions;
- the most important supervisory concerns;
- the next best action;
- whether a targeted or full review is justified;
- validation criteria for any proposed improvement.

Use the project’s existing terminology and preserve its SSOT. Do not redesign the system during this run.
