# AI Benchmark Seed Report (Initiative 11 / WS8)

Source: `todos/11_ai_agent_eval.md`, `specs/AI_AGENT_EVALUATION_BLUEPRINT_V1.md`,
`benchmarks/ai_agent/FROZEN_BENCHMARK_SUITE_V1.md`. Requirement: REQ-047.

Status: T-011-01..04 and T-011-06 complete. T-011-05 (real runs) is deferred —
no AI-provider credential is configured in this environment (see below).

## T-011-01 Registries (MDL/AGT/PRM)

`benchmarks/ai_agent/registries/records.py` — frozen dataclasses (`ModelRecord`,
`AgentRecord`, `PromptRecord`) with strict `parse_*` functions (mirrors
`tios.strategy.spec`'s style) and canonical-JSON sha256 hashing. Provider
policy fields (REG §7 / `docs/architecture/AD.md` L176) are populated per
provider: Anthropic 60-day minimum deprecation notice, OpenAI 14 days
(conservative bound for previews), Google provisional pending RG-08. Seed
data: `benchmarks/ai_agent/registries/seed/{models,agents,prompts}.json` — 4
models (3 unresolved-snapshot placeholders per provider + 1 null-provider
test double), 2 agent configurations, 8 prompt templates (one per T1-T8).
Round-trip verified by `test_model_registry_round_trip` and
`test_agent_and_prompt_registries_round_trip`.

## T-011-02 Frozen fixture corpus

`benchmarks/ai_agent/fixtures/build_fixtures.py` generates
`benchmarks/ai_agent/fixtures/corpus/` — 27 self-contained fixtures across all
8 task classes, each fixture bundling its own source/ground-truth so no live
external document or network access is required:

| Task | Count | Note |
|---|---|---|
| T1 source verification | 12 | claims against quoted excerpts of this repo's own frozen docs |
| T2 strategy extraction | 5 | one per `tios.strategy.spec.FAMILIES` entry used in this suite |
| T3 semantic implementation review | 2 | synthetic strategy/implementation pairs |
| T4 backtest plan construction | 2 | reference `DS-CRYPTO-SPOT-BAKEOFF-V1` |
| T5 red-team critique | 2 | synthetic backtest reports with known failure modes |
| T6 tool comparison | 1 (3 tools) | freqtrade / vectorbt / nautilus_trader |
| T7 dictionary/ontology | 2 | overloaded terms: leverage, fill |
| T8 research synthesis | 1 (8 sources) | includes a deliberate primary/secondary contradiction |

Manifest: `benchmarks/ai_agent/fixtures/corpus/manifest.json` — sha256 per
file, `frozen_utc: 2026-07-07T13:42:10Z`, leakage-control checklist (corpus
hashes frozen, publication dates recorded, controlled-mode network disabled,
no real ticker/entity/date leakage risk since fixtures are synthetic or
self-referential, raw profit not treated as reasoning proof). Verified by
`test_fixture_manifest_hashes_match_files`.

## T-011-03 Harness (null-provider end-to-end)

`benchmarks/ai_agent/harness/{provider,pipeline,run}.py`. `NullProvider`
imports no networking library and returns a fixed, labeled stub per task
class; `RealProviderGate` raises `CredentialNotConfiguredError` rather than
fabricating a run when a provider's API-key env var is absent.

Ran end-to-end with no credentials present:

```
$ python -m harness.run
{"T1": 12, "T2": 5, "T3": 2, "T4": 2, "T5": 2, "T6": 1, "T7": 2, "T8": 1, "schema_errors": 0, "total": 27}
```

Output: `benchmarks/ai_agent/runs/null_seed_run.jsonl` (27 fully-provenanced
run records — task ID/class, model identifier, provider, agent/prompt keys,
source-corpus hash, context hash, timestamp, cost, latency, raw/normalized
output, schema errors, empty evaluator results). Zero schema errors, zero
cost. No-network enforcement verified by
`test_null_provider_never_touches_the_network` (monkeypatches `socket.socket`
to raise; the full corpus still runs clean).

## T-011-04 Judge calibration set

`benchmarks/ai_agent/calibration/build_calibration_set.py` freezes a 6-sample
draw from the null seed run plus a 4-criterion rubric (instruction adherence,
factual accuracy, completeness, hallucination) into
`benchmarks/ai_agent/calibration/calibration_set.json`, with a `set_hash` and
`review_status: "PENDING_HUMAN_REVIEW"`. Per the blueprint's evaluation
safeguards ("LLM-as-judge scores require calibration and spot human review")
and this initiative's explicit human-approval requirement, the review itself
is **not fabricated** here — `reviewer`/`reviewed_at` stay `null` until an
operator records a decision. Because the sample is drawn from the null
provider, no real judge-quality signal exists yet; T-011-05 real runs are
what this calibration set is structurally ready to receive.

## T-011-05 First real runs — deferred (credential-gated)

Checked for `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` in the
environment and for a tracked `.env` file: **none present** (`.env` does not
exist; `.gitignore` correctly excludes it; `.env.example` lists only variable
names). Per the intake gate's "add later" AI-key disposition, T-011-05 does
not proceed. Recorded as an open item in `MISSING_AND_OPEN_ITEMS.md`. No
provider secret value appears anywhere in this repository as a result.

## T-011-06 Scoring views

Never a single global score (per suite spec). With only null-provider data
available, the required views are structurally present but carry no
quality/cost signal yet — populating them meaningfully is gated on T-011-05:

- **Model × Task Quality** — n/a (`model_identifier = "null"` for every run)
- **Agent Configuration × Task Quality** — n/a (single self-test agent config)
- **Cost-adjusted Quality** — cost = $0.00 for all 27 runs (null provider)
- **Stability** — n/a (null provider is deterministic by construction, not evidence of real-model stability)
- **Failure Profile** — 0/27 schema errors; the plumbing itself is validated, not model behavior
- **Downstream Conversion** — n/a (no downstream research/strategy artifacts consumed real AI output yet)
- **Research Asset Reuse** — n/a

## Next steps

1. Configure an AI-provider credential (operator action) to unblock T-011-05.
2. Run controlled-mode Mode A on the same 27 fixtures with a real provider;
   populate the scoring views above with actual quality/cost/latency/variance.
3. Have the operator review `calibration/calibration_set.json` once it
   contains real-model samples, and record `reviewer`/`reviewed_at`.
