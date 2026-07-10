"""CLI: run the frozen corpus end-to-end through the null provider (T-011-03).

`python -m harness.run` (with benchmarks/ai_agent/ on sys.path, e.g. via
conftest.py or `cd benchmarks/ai_agent && python -m harness.run`) requires no
provider credential and touches no network.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from harness.pipeline import load_corpus, run_fixture
from harness.provider import NullProvider

CORPUS_DIR = Path(__file__).parent.parent / "fixtures" / "corpus"
OUT_PATH = Path(__file__).parent.parent / "runs" / "null_seed_run.jsonl"
FROZEN_TIMESTAMP = "2026-07-07T00:00:00Z"  # pinned: this is a fixed self-test run, not wall-clock


def main() -> dict[str, int]:
    manifest, items = load_corpus(CORPUS_DIR)
    corpus_hash = hashlib.sha256(
        json.dumps(manifest["files"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    provider = NullProvider()
    records = [
        run_fixture(rel_path, fixture, corpus_hash, provider, FROZEN_TIMESTAMP)
        for rel_path, fixture in items
    ]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
    counts_by_class: dict[str, int] = {}
    errors = 0
    for rec in records:
        counts_by_class[rec["task_class"]] = counts_by_class.get(rec["task_class"], 0) + 1
        if rec["schema_errors"]:
            errors += 1
    summary = {"total": len(records), "schema_errors": errors, **counts_by_class}
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
