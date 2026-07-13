# Trading OS system review

## Review the full path

Trace each material decision through:

`source → ingestion → normalization → feature calculation → strategy signal → portfolio decision → risk gate → execution proposal → order adapter → fill/reconciliation → monitoring → memory`

For each boundary, identify owner, contract, timestamp, failure behavior, and evidence.

## Architecture questions

- Are research, simulation, paper, and live paths clearly separated?
- Are strategy, portfolio, risk, execution, and monitoring separate responsibilities?
- Can a strategy be tested without calling a live venue?
- Can risk limits reject a decision independently of the LLM?
- Are order adapters venue-specific and tested against official semantics?
- Is the same feature definition used in research and production?
- Are data lineage and experiment lineage preserved?
- Can the system recover from restart, delay, duplicate events, and partial failure?
- Are current decisions reproducible from recorded inputs and versions?
- Are secrets isolated from prompts, logs, reports, and skills?

## Code and logic red flags

- placeholder formulas presented as complete indicators;
- misleading names such as `volume_24h` calculated from one candle;
- hardcoded parameters without configuration or provenance;
- generic capital percentages used as position sizing;
- unclosed candles used as confirmed signals;
- future values leaking into features or labels;
- duplicate indicators counted as independent evidence;
- live and backtest code using different formulas;
- silent fallback to stale or alternate data;
- errors swallowed without observability;
- mocked execution paths treated as production-ready;
- missing tests for boundary conditions, units, timestamps, and failure modes.

## Change ownership

Classify the owning layer before proposing a fix. Do not repair a data problem in the strategy layer, an execution problem in the signal layer, or a governance problem by adding another indicator.

Default to read-only inspection and recommendations. When implementation is later authorized, create a bounded task with files, behavior, tests, acceptance criteria, and regression checks.
