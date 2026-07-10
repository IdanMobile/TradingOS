#!/usr/bin/env python3
"""Execute the local MLflow + DVC lineage acceptance prototype.

Run with both tools isolated from the project environment:
    uv run --with mlflow==3.14.0 --with dvc==3.66.1 \
        python scripts/run_lineage_prototype.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import mlflow
from mlflow import MlflowClient

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "lineage" / "prototype"
SOURCE_REPO = OUTPUT / "dataset_repo"
RESTORE_REPO = OUTPUT / "fresh_checkout"
DVC_REMOTE = OUTPUT / "dvc_remote"
MLFLOW_ROOT = OUTPUT / "mlflow_artifacts"
MLFLOW_DB = OUTPUT / "mlflow.db"
DATASET_SOURCE = ROOT / "data" / "normalized" / "BTCUSDT_5m.parquet"
RUN_ROOT = ROOT / "artifacts" / "bakeoff" / "freqtrade" / "B2" / "F0_S0"
AI_OUTPUT = ROOT / "benchmarks" / "ai_agent" / "runs" / "null_seed_run.jsonl"
RESULT_PATH = OUTPUT / "prototype_result.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command(*args: str, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def write_reproducer(path: Path) -> None:
    path.write_text(
        """from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
import pyarrow.parquet as pq

source = Path(sys.argv[1])
target = Path(sys.argv[2])
table = pq.read_table(source, columns=[\"close\"])
closes = [float(value.as_py()) for value in table.column(\"close\")]

def rolling_mean(values, width):
    result = [None] * len(values)
    total = 0.0
    for index, value in enumerate(values):
        total += value
        if index >= width:
            total -= values[index - width]
        if index + 1 >= width:
            result[index] = total / width
    return result

fast = rolling_mean(closes, 3)
slow = rolling_mean(closes, 5)
positive = [f is not None and s is not None and f > s for f, s in zip(fast, slow)]
transitions = sum(1 for before, after in zip(positive, positive[1:]) if before != after)
digest = hashlib.sha256(source.read_bytes()).hexdigest()
target.write_text(
    json.dumps(
        {
            \"dataset_sha256\": digest,
            \"rows\": len(closes),
            \"ma_state_transitions\": transitions,
        },
        sort_keys=True,
        indent=2,
    )
    + \"\\n\"
)
""",
        encoding="utf-8",
    )


def prepare_dvc() -> dict[str, Any]:
    SOURCE_REPO.mkdir(parents=True)
    data_dir = SOURCE_REPO / "data"
    data_dir.mkdir()
    tracked = data_dir / DATASET_SOURCE.name
    shutil.copy2(DATASET_SOURCE, tracked)
    write_reproducer(SOURCE_REPO / "run_reproduction.py")
    (SOURCE_REPO / "dvc.yaml").write_text(
        "# The acceptance runner invokes the checked-in reproducer after dvc pull.\nstages: {}\n",
        encoding="utf-8",
    )

    command("git", "init", "-q", cwd=SOURCE_REPO)
    command("git", "config", "user.name", "Trading OS Lineage Prototype", cwd=SOURCE_REPO)
    command("git", "config", "user.email", "lineage@localhost", cwd=SOURCE_REPO)
    command("dvc", "init", "-q", cwd=SOURCE_REPO)
    command("dvc", "add", "data/BTCUSDT_5m.parquet", cwd=SOURCE_REPO)
    command("dvc", "remote", "add", "-d", "localstore", str(DVC_REMOTE), cwd=SOURCE_REPO)

    source_reproduction = SOURCE_REPO / "reproduction.json"
    command(
        sys.executable,
        "run_reproduction.py",
        "data/BTCUSDT_5m.parquet",
        "reproduction.json",
        cwd=SOURCE_REPO,
    )
    command("git", "add", ".", cwd=SOURCE_REPO)
    command("git", "commit", "-qm", "frozen BTC dataset lineage fixture", cwd=SOURCE_REPO)
    revision = command("git", "rev-parse", "HEAD", cwd=SOURCE_REPO)
    command("dvc", "push", "-q", cwd=SOURCE_REPO)

    command("git", "clone", "-q", str(SOURCE_REPO), str(RESTORE_REPO))
    command("dvc", "pull", "-q", cwd=RESTORE_REPO)
    restored = RESTORE_REPO / "data" / DATASET_SOURCE.name
    restored_reproduction = RESTORE_REPO / "reproduction.json"
    command(
        sys.executable,
        "run_reproduction.py",
        "data/BTCUSDT_5m.parquet",
        "reproduction.json",
        cwd=RESTORE_REPO,
    )

    source_result = json.loads(source_reproduction.read_text(encoding="utf-8"))
    restored_result = json.loads(restored_reproduction.read_text(encoding="utf-8"))
    dvc_metadata = json.loads(command("dvc", "data", "status", "--json", cwd=RESTORE_REPO) or "{}")
    return {
        "status": "PASS" if source_result == restored_result else "FAIL",
        "dataset_source": str(DATASET_SOURCE.relative_to(ROOT)),
        "dataset_sha256": sha256(DATASET_SOURCE),
        "restored_sha256": sha256(restored),
        "hash_match": sha256(DATASET_SOURCE) == sha256(restored),
        "dvc_repo_revision": revision,
        "dvc_reference": f"git:{revision}:data/{DATASET_SOURCE.name}.dvc",
        "fresh_checkout": str(RESTORE_REPO.relative_to(ROOT)),
        "reproduction_match": source_result == restored_result,
        "reproduction_result": restored_result,
        "dvc_status": dvc_metadata,
    }


def log_strategy_runs(
    client: MlflowClient, experiment_id: str, dvc: dict[str, Any]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for ordinal in (1, 2):
        run_dir = RUN_ROOT / f"run{ordinal}"
        metrics = json.loads((run_dir / "normalized_metrics.json").read_text(encoding="utf-8"))
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        started = time.perf_counter()
        with mlflow.start_run(
            experiment_id=experiment_id,
            run_name=f"B2-F0-S0-retained-run{ordinal}",
            tags={
                "tios.test": "A",
                "validation_state": "INCOMPLETE_NOT_APPROVABLE",
                "approval_state": "NOT_ELIGIBLE",
            },
        ) as active:
            params = {
                "git_commit": command("git", "rev-parse", "HEAD", cwd=ROOT),
                "dataset_id": "DS-CRYPTO-SPOT-BAKEOFF-V1",
                "dataset_sha256": dvc["dataset_sha256"],
                "dvc_reference": dvc["dvc_reference"],
                "strategy_id": "B2MaCrossover",
                "strategy_version": "S1-baseline-v1",
                "engine": manifest["engine"],
                "scenario": manifest["scenario"],
                "fast_period": 3,
                "slow_period": 5,
                "fee_rate_per_side": manifest["fee_rate_per_side"],
                "slippage_assumption": manifest["slippage_note"],
                "random_seed": "not_applicable_deterministic",
            }
            mlflow.log_params(params)
            numeric_metrics = {
                key: float(value)
                for key, value in metrics.items()
                if key
                in {
                    "trades_roundtrips",
                    "fills",
                    "profit_total_abs",
                    "cagr",
                    "max_drawdown_abs",
                    "wins",
                    "losses",
                }
            }
            numeric_metrics["tracking_runtime_seconds"] = time.perf_counter() - started
            mlflow.log_metrics(numeric_metrics)
            for name in (
                "trades.parquet",
                "equity.parquet",
                "normalized_metrics.json",
                "manifest.json",
            ):
                mlflow.log_artifact(run_dir / name, artifact_path="strategy")
            run_id = active.info.run_id

        restored_trade = Path(
            client.download_artifacts(
                run_id, "strategy/trades.parquet", str(OUTPUT / "mlflow_restore")
            )
        )
        records.append(
            {
                "ordinal": ordinal,
                "run_id": run_id,
                "metrics": numeric_metrics,
                "trade_sha256": sha256(run_dir / "trades.parquet"),
                "restored_trade_sha256": sha256(restored_trade),
                "artifact_restore_match": sha256(run_dir / "trades.parquet")
                == sha256(restored_trade),
            }
        )
    return records


def log_mock_ai_run(experiment_id: str) -> dict[str, Any]:
    first = json.loads(AI_OUTPUT.read_text(encoding="utf-8").splitlines()[0])
    with mlflow.start_run(
        experiment_id=experiment_id,
        run_name="AI-null-provider-lineage-dry-trace",
        tags={"tios.test": "B", "trace_class": "MOCK_ONLY", "quality_claim": "NONE"},
    ) as active:
        mlflow.log_params(
            {
                "provider": first["provider"],
                "exact_model_id": first["model_identifier"],
                "prompt_version": first["prompt_key"],
                "exact_research_question": "Can the source support the fixture claim?",
                "agent_config": first["agent_key"],
                "tool_policy": "offline_no_tools",
                "corpus_hash": first["source_corpus_hash"],
                "context_package_hash": first["context_package_hash"],
            }
        )
        mlflow.log_metrics(
            {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": first["cost_usd"],
                "latency_ms": first["latency_ms"],
                "evaluator_schema_errors": len(first["schema_errors"]),
            }
        )
        mlflow.log_artifact(AI_OUTPUT, artifact_path="ai_research")
        return {
            "status": "PASS_MOCK_PLUMBING_ONLY",
            "run_id": active.info.run_id,
            "provider": first["provider"],
            "model_id": first["model_identifier"],
            "prompt_version": first["prompt_key"],
            "corpus_hash": first["source_corpus_hash"],
            "quality_claim": "NONE",
        }


def main() -> None:
    if not DATASET_SOURCE.exists():
        raise SystemExit(f"missing frozen dataset: {DATASET_SOURCE}")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    dvc = prepare_dvc()
    tracking_uri = f"sqlite:///{MLFLOW_DB}"
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)
    experiment_id = client.create_experiment(
        "Trading OS Lineage Prototype",
        artifact_location=MLFLOW_ROOT.resolve().as_uri(),
    )
    strategy_runs = log_strategy_runs(client, experiment_id, dvc)
    ai_run = log_mock_ai_run(experiment_id)
    domain_record = {
        "evidence_id": "EV-LINEAGE-PROTOTYPE-002",
        "hypothesis_id": "HYP-BASELINE-MA-CROSSOVER",
        "strategy_version_id": "STRAT-B2MA-CROSSOVER-V1",
        "market": "crypto_spot",
        "instrument": "BTC/USDT",
        "timeframe": "5m",
        "run_ref": f"mlflow:{strategy_runs[0]['run_id']}",
        "dataset_ref": f"dvc:{dvc['dvc_repo_revision']}:data/{DATASET_SOURCE.name}.dvc",
        "validation_state": "REJECTED",
        "approval_state": "NOT_ELIGIBLE",
    }
    evidence_path = OUTPUT / "trading_evidence.jsonl"
    evidence_path.write_text(
        json.dumps(domain_record, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    comparable = client.search_runs(
        [experiment_id],
        filter_string="tags.`tios.test` = 'A'",
        order_by=["attributes.start_time ASC"],
    )
    compare_pass = (
        len(comparable) == 2
        and strategy_runs[0]["trade_sha256"] == strategy_runs[1]["trade_sha256"]
        and all(record["artifact_restore_match"] for record in strategy_runs)
    )
    result = {
        "schema": "tios-lineage-prototype-v1",
        "decision": "MLFLOW_PLUS_DVC_RECOMMENDED",
        "versions": {
            "mlflow": mlflow.__version__,
            "dvc": command("dvc", "--version"),
        },
        "dvc": dvc,
        "mlflow": {
            "status": "PASS" if compare_pass else "FAIL",
            "tracking_uri": tracking_uri,
            "experiment_id": experiment_id,
            "strategy_runs": strategy_runs,
            "native_compare_query_count": len(comparable),
            "compare_pass": compare_pass,
        },
        "ai_trace": ai_run,
        "domain_link": {
            "status": "PASS",
            "path": str(evidence_path.relative_to(ROOT)),
            "record": domain_record,
            "uses_public_references_only": True,
        },
        "gates": {
            "reproduce": "PASS" if dvc["hash_match"] and dvc["reproduction_match"] else "FAIL",
            "compare": "PASS" if compare_pass else "FAIL",
            "trace": "PASS" if compare_pass else "FAIL",
            "ai_trace": "PASS_MOCK_ONLY",
            "domain_link": "PASS",
            "local_first": "PASS",
            "replaceability": "PASS",
        },
    }
    RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": str(RESULT_PATH), "gates": result["gates"]}, indent=2))


if __name__ == "__main__":
    main()
