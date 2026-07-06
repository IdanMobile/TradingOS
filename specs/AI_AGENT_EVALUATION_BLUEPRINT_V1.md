# AI & Agent Evaluation Blueprint V1

Status: Draft design candidate.
Date: 2026-07-05

## Goal
Learn which versioned model + agent + prompt + tools + context + workflow performs best for each non-deterministic task under quality, cost, latency, and downstream-value constraints.

## Evaluation unit
Never score model name alone.

Canonical unit:
`AgentConfiguration = model snapshot + provider + prompt version + tools + context package + reasoning settings + budget + workflow + output schema`

## Task classes for MVP preparation
1. Deep ecosystem research.
2. Source verification.
3. Strategy extraction from paper/code.
4. Strategy formalization into deterministic specification.
5. Strategy red-team critique.
6. Evidence synthesis.
7. Tool comparison.
8. Dictionary/ontology extraction.
9. Experiment-result explanation.
10. Coding-agent strategy implementation support later.

## Benchmark modes
### Controlled
Freeze corpus, tools, prompt, budget, timeout, schema.
Purpose: isolate model effect.

### Best-configuration
Allow optimized prompt/tools/workflow per model.
Purpose: measure real deployable configuration.

### Longitudinal
Re-run frozen benchmark after model/provider update.
Purpose: detect regression or improvement.

## Core metrics
### Task quality
- factual accuracy
- instruction adherence
- completeness
- relevance
- structured output validity

### Research quality
- primary-source ratio
- citation correctness
- supported-claim ratio
- contradiction discovery
- source freshness
- duplicate/low-value discovery rate

### Strategy-research quality
- extracted rule correctness
- ambiguity detection
- reproducibility of specification
- hidden assumption count
- downstream sanity-screen survival
- OOS survival attribution where statistically meaningful

### Operational
- latency p50/p95
- token usage
- direct cost
- retry rate
- tool-call failure
- malformed output
- timeout rate

### Stability
- variance across repeated runs
- disagreement rate

### Downstream
- hypotheses formalized
- hypotheses rejected early
- strategies implemented
- strategies surviving validation
- paper candidates
- approved live candidates
- reusable research asset count
- reuse count per research asset

## Cost metrics
- cost per accepted research artifact
- cost per verified claim
- cost per useful hypothesis
- cost per validation survivor
- amortized cost per Research Asset reuse

## Provenance requirements
Every run stores:
- task ID
- task class
- exact model identifier
- provider
- agent version
- prompt version
- tool versions
- source corpus snapshot
- context package hash
- timestamp
- cost
- latency
- raw output
- normalized output
- evaluator results
- downstream links

## Evaluation safeguards
- no generic public benchmark score can override internal task evidence.
- LLM-as-judge scores require calibration and spot human review.
- same-model self-judging is not sufficient for critical tasks.
- model updates trigger re-evaluation when alias behavior can change.
- one-time research provenance is distinguished from runtime AI-in-trade-path usage.

## Prior art incorporated
- OpenAI evaluation guidance: task-specific evals.
- MLflow agent/LLM tracing and evaluation candidate infrastructure.
- QuantCode-Bench: syntax alone is insufficient; executable behavior and semantic alignment matter.
- Other quant benchmarks remain discovery inputs, not direct approval criteria.

## First benchmark set recommendation
Create a frozen 20-task seed suite:
- 4 source-verification tasks
- 4 strategy extraction tasks
- 4 strategy critique tasks
- 4 tool comparison tasks
- 4 ontology/dictionary tasks

Run at least repeated trials per configuration before drawing stability conclusions.
