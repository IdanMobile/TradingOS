#!/usr/bin/env python3
"""Verify the frozen prospective campaign without reading warm-up outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from tios.services.observations import build_observation_projection

CAMPAIGN = Path("research/PROSPECTIVE_BTC_LIQUIDATION_ASSOCIATION_OVERLAY_CAMPAIGN_V1.yaml")


def build_preflight(root: Path) -> dict[str, Any]:
    root = root.resolve()
    campaign = yaml.safe_load((root / CAMPAIGN).read_text())
    if campaign.get("status") != "FROZEN_UNRUN_WAITING_MINIMA":
        raise ValueError("campaign status changed")
    if campaign.get("execution_authority") != "NONE":
        raise ValueError("campaign authority changed")
    for item in campaign["frozen_inputs"].values():
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("frozen input is missing or escapes root")
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"frozen input hash mismatch: {item['path']}")

    observation = build_observation_projection(root)
    evidence = observation.get("evidence", {})
    longest = int(evidence.get("longest_chain", 0))
    blockers = []
    if observation.get("availability") != "AVAILABLE":
        blockers.append("OBSERVATION_UNAVAILABLE")
    if longest < 8_640:
        blockers.append("WARMUP_SAMPLE_INCOMPLETE")
    blockers.extend(
        [
            "FIRST_REVIEW_MINIMA_NOT_PROVEN",
            "VALIDATED_ALPHA_STRATEGY_MISSING",
            "OVERLAY_CHILD_BLOCKED",
        ]
    )
    return {
        "schema_version": 1,
        "campaign_id": campaign["campaign_id"],
        "status": "WAITING" if blockers else "ELIGIBLE_TO_EVALUATE",
        "declared_trial_count": campaign["declared_trial_population"]["terminal_trial_count"],
        "observation": {
            "availability": observation.get("availability"),
            "finalized_windows": evidence.get("finalized", 0),
            "longest_continuity_chain": longest,
        },
        "blockers": blockers,
        "metrics_computed": False,
        "label_files_read": 0,
        "warmup_outcomes_read": False,
        "execution_authority": "NONE",
        "order_creation": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = build_preflight(args.root)
    except Exception as error:
        print(json.dumps({"status": "ERROR", "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
