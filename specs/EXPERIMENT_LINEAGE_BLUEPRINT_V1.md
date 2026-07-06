# Experiment Lineage Blueprint V1

Status: Strong design candidate; exact tools not yet approved.

## Problem
The OS must preserve code, data, parameters, engine, strategy, model/agent provenance, artifacts, failed trials, comparisons, approvals, and downstream outcomes.

## Recommended layered responsibility
### Layer A — Run tracking candidate
MLflow-class infrastructure.
Owns:
- run IDs
- parameters
- metrics
- artifacts
- code/model links
- dataset references
- LLM/agent traces where applicable

### Layer B — Data/artifact reproducibility candidate
DVC-class infrastructure.
Owns:
- dataset versions
- Git-aligned pointers
- reproducible pipelines/artifacts

### Layer C — Custom Trading Evidence Registry
Owns domain semantics not delegated to generic MLOps:
- hypothesis
- strategy version
- market
- venue
- timeframe
- regime
- validation package
- contradiction
- strategy-market-timeframe approval
- promotion/demotion
- paper/live divergence
- evidence freshness
- Research Asset reuse
- AI provenance graph

## Key principle
Do not custom-build generic experiment tracking unless bake-off evidence proves existing tools inadequate.

## Canonical lineage chain
Source -> Research Asset -> Hypothesis -> Strategy Spec -> Strategy Version -> Dataset Snapshot -> Engine Run -> Validation Package -> Paper Deployment -> Limited Live -> Outcome -> Learning

## Trial retention rule
All trials are retained, including failures. A selected winner must reference the search population from which it was selected.

## Minimum immutable fields
- canonical ID
- created_at
- creator type (human/agent/system)
- parent IDs
- exact versions
- hashes
- environment manifest
- status transitions
- evidence links

## Decision pending
Compare:
- MLflow only
- DVC only
- MLflow + DVC
- alternatives where justified

No final selection until a small executable lineage prototype is run.
