# Skill: Benchmark Runner (v1)

Role: R8 · Cost tier: mid-high · Status: specified, not yet implemented
Absorbs: Model Benchmark Runner + Agent Benchmark Runner (mode is a parameter).

## Purpose
Execute frozen AI benchmark tasks (`benchmarks/ai_agent/FROZEN_BENCHMARK_SUITE_V1.md`) under leakage controls and score them with calibrated judges.

## Trigger conditions
WS8 seed execution; new model/agent configuration registration; provider model-change events (Mode C longitudinal); routing decisions needing evidence.

## Inputs
Frozen corpus (hash-verified), task definitions T1–T8, agent configuration(s), judge configuration + calibration set.

## Process
1. Verify corpus hashes before any run; refuse on mismatch.
2. Controlled mode (A): network disabled, frozen prompt/tools/budget/timeout/schema; **multiple repeated runs per configuration** — providers offer no determinism guarantee (verified 2026-07-06: Anthropic rejects temperature params on current models; Gemini documents non-determinism; OpenAI seed status unconfirmed) — so stability scoring uses run-to-run variance, never a single sample.
3. Best-config mode (B): allow per-model prompt/tool/workflow optimization; freeze and record each optimized configuration as its own AGT record.
4. Score: rubric metrics per task; judge model ≠ producer model for critical tasks; judge outputs spot-checked against the human-calibrated sample.
5. Record: full provenance (model snapshot ID, prompt version, corpus hash, cost, latency, raw + normalized output) per `specs/AI_AGENT_EVALUATION_BLUEPRINT_V1.md`.
6. Emit the required scoring views (Model × Task, Config × Task, cost-adjusted, stability, failure profile). Never a single global score.

## Outputs (contract)
BMK records + scoring views; deferred-execution report if credentials absent (fixtures validated, execution marked BLOCKED — never fabricated).

## Prohibited behavior
Fabricating or extrapolating model outputs; modifying frozen fixtures; single-run conclusions; same-model self-judging for critical tasks; treating raw profit as model skill (D-021).

## Quality gates
Corpus hash check logged; ≥N repeated runs where variance is claimed; judge calibration evidence linked.

## When NOT to use
Ad-hoc "which model feels better" questions — those are not evidence and must not enter records.

## Model suitability
Harness orchestration is mechanical (cheap); judging is mid-high and calibration-bound.
