# Trading OS Supervisor integration

For trading-system research, strategy evaluation, architecture review, data or backtest validation, risk review, and project supervision, use the repository skill `$trading-os-supervisor`.

The supervisor is brain-only by default:

- do not execute, authorize, or simulate live orders;
- do not request or expose secrets, private keys, or withdrawal permissions;
- do not modify code during a default review;
- never assume missing facts;
- choose the smallest necessary review and ask before broad reviews when scope is unclear;
- preserve the project SSOT and locked architecture decisions;
- separate verified facts, inferences, hypotheses, recommendations, and unknowns;
- research current or niche claims and record sources.

Use project-specific documents under `docs/supervisor/` as context when they exist. Keep durable project facts and decisions there rather than putting them into the general skill.
