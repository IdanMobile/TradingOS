# Frozen AI & Agent Benchmark Suite V1

Status: Definition complete; corpus construction and execution pending.

## Goal
Measure which exact model + agent configuration performs best for each non-deterministic task class, with cost, latency, stability, and downstream usefulness tracked separately.

## Benchmark modes

### Mode A — Controlled
Same:
- task
- frozen corpus
- prompt
- tools
- budget
- timeout
- output schema

Purpose: isolate model effect.

### Mode B — Best Configuration
Allow model-specific:
- prompts
- reasoning settings
- tools
- workflow

Purpose: find best deployable agent system.

### Mode C — Longitudinal
Rerun frozen tasks after model/provider changes.

Purpose: detect regression, improvement, and routing changes.

## V1 task set

### T1 — Source verification
Input: 12 frozen claims and source documents.
Output: supported / contradicted / insufficient, with evidence spans.
Metrics:
- claim classification accuracy
- citation correctness
- unsupported-claim rate
- cost
- latency

### T2 — Strategy extraction
Input: 5 frozen strategy descriptions/papers/scripts.
Output: canonical strategy specification.
Metrics:
- rule completeness
- entry/exit correctness
- timing correctness
- ambiguity detection
- hidden-assumption detection

### T3 — Strategy semantic implementation review
Input: natural-language strategy + generated implementation + frozen data.
Output: semantic mismatch report.
Prior art alignment: QuantCode-Bench.
Metrics:
- mismatch recall
- false-positive rate
- executable test suggestions

### T4 — Backtest plan construction
Input: strategy specification + available datasets.
Output: reproducible backtest plan.
Prior art alignment: BacktestBench.
Metrics:
- leakage prevention
- cost assumptions
- OOS design
- reproducibility
- missing-dependency detection

### T5 — Red-team strategy critique
Input: attractive backtest report.
Output: strongest falsification plan.
Metrics:
- number of material failure modes found
- severity-weighted recall
- irrelevant-warning rate
- recommended test usefulness

### T6 — Tool comparison
Input: frozen official docs for 3 tools.
Output: capability matrix and decision.
Metrics:
- factual accuracy
- unsupported comparison rate
- implementation-reference precision
- cost

### T7 — Dictionary/ontology extraction
Input: venue docs containing overloaded terms.
Output: canonical concepts, aliases, context-specific meanings.
Metrics:
- concept precision/recall
- ambiguity preservation
- incorrect synonym merge rate

### T8 — Research Asset synthesis
Input: frozen corpus of 8 sources with conflicts.
Output: reusable research asset.
Metrics:
- primary-source weighting
- contradiction handling
- freshness caveats
- downstream reuse quality

## Leakage controls
- Freeze corpus hashes.
- Record corpus publication dates.
- Controlled mode has network disabled.
- Where model memory contamination is plausible, mask ticker/entity/date identifiers consistently.
- Do not treat raw profit as proof of reasoning skill.
- For economic tasks, record beta/style/regime exposure where possible.

This is informed by 2026 KTD-Fin prior art, which shows that historical-memory leakage and passive exposure can materially distort apparent LLM trading skill.

## Scoring outputs
Never emit one global model score.

Required views:
- Model × Task Quality
- Agent Configuration × Task Quality
- Cost-adjusted Quality
- Stability
- Failure Profile
- Downstream Conversion
- Research Asset Reuse

## First candidate set
Populate at execution time from currently available models. Exact model IDs must be resolved and recorded then; do not hard-code stale model names into the benchmark definition.

## Promotion rule
A model/agent may become default for a task class only after:
1. enough repeated runs for variance estimation;
2. no critical failure mode is hidden by average score;
3. cost/latency constraints fit the task;
4. exact model snapshot is recorded;
5. fallback route exists.
