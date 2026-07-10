"""Judge calibration set (T-011-04, REQ-045).

Freezes a small sample of run outputs plus a scoring rubric for the operator
to review. The set itself (sample + rubric + hash) is frozen here; the
*review* is a human step this script cannot perform and does not fabricate —
`review_status` stays "PENDING_HUMAN_REVIEW" until an operator edits this
file's output to record a decision.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

RUN_PATH = Path(__file__).parent.parent / "runs" / "null_seed_run.jsonl"
OUT_PATH = Path(__file__).parent / "calibration_set.json"

RUBRIC = {
    "criteria": [
        "instruction_adherence: did the output follow the requested JSON schema exactly?",
        "factual_accuracy: does the output correctly reflect the fixture (not outside knowledge)?",
        "completeness: are all required fields present and non-trivially filled?",
        "hallucination: does the output assert anything not present in the fixture?",
    ],
    "scale": "1 (fails) - 5 (fully meets criterion), per criterion",
}


def build(sample_size: int = 6) -> dict[str, object]:
    lines = RUN_PATH.read_text().splitlines()
    sample = [json.loads(line) for line in lines[:sample_size]]
    payload = {
        "rubric": RUBRIC,
        "sample": sample,
        "review_status": "PENDING_HUMAN_REVIEW",
        "reviewer": None,
        "reviewed_at": None,
        "notes": (
            "Sample drawn from the null-provider seed run (runs/null_seed_run.jsonl); "
            "outputs are the deterministic null stub, not real model output, so no "
            "calibration judgment is meaningful yet. This file exists to freeze the "
            "sample+rubric structure T-011-05's real runs will populate for review."
        ),
    }
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload["set_hash"] = payload_hash
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


if __name__ == "__main__":
    p = build()
    print(f"calibration set built: {len(p['sample'])} samples, status={p['review_status']}")
