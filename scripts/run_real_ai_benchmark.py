#!/usr/bin/env python3
"""T-011-05: first real AI benchmark runs — Mode A, two configurations.

Runs the frozen corpus through two real providers (Anthropic claude-opus-4-8 and OpenAI
gpt-4o) with identical prompts and schema instructions — Mode A isolates the model effect,
so nothing is provider-tuned. Each configuration runs the corpus twice: providers offer no
determinism guarantees, so single-sample numbers are anecdotes; AD-11 requires
multi-sample variance.

Credentials are loaded from `.env` selectively — only the two provider keys, nothing else
enters the process environment (SUP-011: shared .env loading must not import unrelated
values). Keys are never printed.

Outputs:
  benchmarks/ai_agent/runs/real_modea_v1.jsonl        one record per call, full provenance
  artifacts/ai_benchmarks/REAL_RUN_MODEA_V1.json      summary with variance estimates
  artifacts/ai_benchmarks/cost_telemetry.jsonl        per-run cost rows (T-017-05 seed)

    python scripts/run_real_ai_benchmark.py
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "ai_agent"))
sys.path.insert(0, str(ROOT / "src"))

from harness.pipeline import load_corpus, run_fixture  # noqa: E402
from harness.provider import RealProviderGate  # noqa: E402
from harness.real_provider import (  # noqa: E402
    PRICING_USD_PER_MTOK,
    AnthropicRealProvider,
    OpenAIRealProvider,
    RealProviderError,
)

CORPUS_DIR = ROOT / "benchmarks" / "ai_agent" / "fixtures" / "corpus"
RUN_PATH = ROOT / "benchmarks" / "ai_agent" / "runs" / "real_modea_v1.jsonl"
SUMMARY_PATH = ROOT / "artifacts" / "ai_benchmarks" / "REAL_RUN_MODEA_V1.json"
COST_LEDGER = ROOT / "artifacts" / "ai_benchmarks" / "cost_telemetry.jsonl"
SAMPLES_PER_CONFIG = 2
AI_KEY_NAMES = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def load_ai_keys_only(env_path: Path = ROOT / ".env") -> dict[str, str]:
    """Extract exactly the AI provider keys from .env; import nothing else (SUP-011)."""
    keys: dict[str, str] = {}
    if not env_path.is_file():
        return keys
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" not in line or line.startswith("#"):
            continue
        name, _, value = line.partition("=")
        if name.strip() in AI_KEY_NAMES:
            keys[name.strip()] = value.strip().strip('"').strip("'")
    return keys


def _git_commit() -> str:
    return subprocess.run(  # noqa: S603
        ("git", "rev-parse", "HEAD"), cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()


def _variance(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-configuration variance across samples: the AD-11 requirement.

    Output stability compares the *content* of answers between samples of the same
    fixture — a provider that returns different JSON for the same frozen prompt is
    measurably unstable in a way latency variance alone cannot show.
    """
    by_fixture: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_fixture.setdefault(record["fixture_path"], []).append(record)

    latencies = [record["latency_ms"] for record in records]
    costs = [record["cost_usd"] for record in records]
    stable = sum(
        1
        for samples in by_fixture.values()
        if len({json.dumps(s["raw_output"], sort_keys=True) for s in samples}) == 1
    )
    valid = sum(1 for record in records if not record["schema_errors"])

    return {
        "calls": len(records),
        "schema_valid_rate": round(valid / len(records), 4) if records else None,
        "output_stable_fixtures": stable,
        "fixtures": len(by_fixture),
        "output_stability_rate": round(stable / len(by_fixture), 4) if by_fixture else None,
        "latency_ms_mean": round(statistics.mean(latencies), 1) if latencies else None,
        "latency_ms_stdev": (round(statistics.stdev(latencies), 1) if len(latencies) > 1 else None),
        "cost_usd_total": round(sum(costs), 6),
        "cost_usd_mean": round(statistics.mean(costs), 6) if costs else None,
    }


def main() -> int:
    keys = load_ai_keys_only()
    for provider_name in ("anthropic", "openai"):
        gate = RealProviderGate(provider_name)
        # The gate reads os.environ; feed it only what it needs, nothing else.
        import os

        env_var = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}[provider_name]
        if keys.get(env_var):
            os.environ[env_var] = keys[env_var]
        gate.require_configured()  # raises honestly instead of fabricating a run

    manifest, items = load_corpus(CORPUS_DIR)
    corpus_hash = manifest.get("corpus_hash", "")
    # Three configurations: two Anthropic models (Mode A model comparison) plus OpenAI.
    # A configuration whose account cannot serve (quota/billing) is recorded as BLOCKED
    # after one probe failure rather than hammered 54 times.
    providers = [
        AnthropicRealProvider(keys["ANTHROPIC_API_KEY"], model="claude-opus-4-8"),
        AnthropicRealProvider(keys["ANTHROPIC_API_KEY"], model="claude-haiku-4-5"),
        OpenAIRealProvider(keys["OPENAI_API_KEY"]),
    ]
    print(
        f"corpus: {len(items)} fixtures | {SAMPLES_PER_CONFIG} samples x {len(providers)} configs"
    )

    all_records: list[dict[str, Any]] = []
    failures: list[str] = []
    RUN_PATH.parent.mkdir(parents=True, exist_ok=True)

    blocked_configs: dict[str, str] = {}
    with RUN_PATH.open("w", encoding="utf-8") as handle:
        for provider in providers:
            config_key = f"{provider.provider}:{provider.model_identifier}"
            config_blocked = False
            for sample in range(SAMPLES_PER_CONFIG):
                if config_blocked:
                    break
                for rel_path, fixture in items:
                    timestamp = datetime.now(tz=UTC).isoformat()
                    try:
                        record = run_fixture(rel_path, fixture, corpus_hash, provider, timestamp)
                    except RealProviderError as error:
                        failures.append(f"{config_key}/{rel_path}: {error}")
                        message = str(error).lower()
                        if "quota" in message or "billing" in message:
                            # Account-level, not transient: every further call would fail
                            # identically. One honest probe is the evidence; 54 are noise.
                            blocked_configs[config_key] = str(error)
                            config_blocked = True
                            break
                        continue
                    record["config_key"] = config_key
                    record["agent_key"] = f"AGT-modeA-{provider.provider}"
                    record["sample_index"] = sample
                    record["pricing_usd_per_mtok"] = PRICING_USD_PER_MTOK[provider.model_identifier]
                    handle.write(json.dumps(record, sort_keys=True) + "\n")
                    all_records.append(record)
                print(f"  {config_key} sample {sample + 1}: {len(all_records)} records total")

    by_config = {
        f"{p.provider}:{p.model_identifier}": [
            r for r in all_records if r["config_key"] == f"{p.provider}:{p.model_identifier}"
        ]
        for p in providers
    }
    summary = {
        "schema_version": 1,
        "task": "T-011-05 first real runs, Mode A (controlled)",
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "git_commit": _git_commit(),
        "corpus_hash": corpus_hash,
        "fixtures": len(items),
        "samples_per_config": SAMPLES_PER_CONFIG,
        "configurations": [
            {"provider": p.provider, "model": p.model_identifier} for p in providers
        ],
        "mode": "A",
        "prompt_discipline": "identical frozen prompt + identical schema instruction per task",
        "variance_by_config": {name: _variance(recs) for name, recs in by_config.items() if recs},
        "blocked_configs": blocked_configs,
        "failures": failures,
        "total_cost_usd": round(sum(r["cost_usd"] for r in all_records), 6),
        "judge_calibration_note": (
            "Judge-based evaluators remain PENDING_HUMAN_REVIEW (T-011-04); this run "
            "records schema validity, stability, cost, and latency only."
        ),
        "execution_authority": "NONE",
        "promotion_eligible": False,
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    # T-017-05 seed: every real run appends one cost row per configuration.
    with COST_LEDGER.open("a", encoding="utf-8") as handle:
        for name, recs in by_config.items():
            if not recs:
                continue
            handle.write(
                json.dumps(
                    {
                        "at": summary["generated_at"],
                        "provider": name,
                        "model": next(r["model_identifier"] for r in recs),
                        "calls": len(recs),
                        "cost_usd": round(sum(r["cost_usd"] for r in recs), 6),
                        "source": "real_modea_v1",
                    },
                    sort_keys=True,
                )
                + "\n"
            )

    print(json.dumps({k: summary[k] for k in ("total_cost_usd", "failures")}, indent=2))
    for name, stats in summary["variance_by_config"].items():
        print(f"{name}: {json.dumps(stats)}")
    print(f"summary -> {SUMMARY_PATH.relative_to(ROOT)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
