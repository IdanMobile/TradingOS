#!/usr/bin/env python3
"""Verify the offline checkpoint-to-risk-decision flow without writing state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tios.services.observations import (
    build_observation_projection,
    build_risk_signal_projection,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    observation = build_observation_projection(root)
    projection = build_risk_signal_projection(root, observation)
    print(json.dumps(projection, sort_keys=True, indent=2))
    valid = (
        projection.get("availability") == "AVAILABLE"
        and projection.get("flow_state") == "RISK_BLOCKED"
        and projection.get("signal", {}).get("side") == "FLAT"
        and projection.get("signal", {}).get("promotion_eligible") is False
        and projection.get("risk_decision", {}).get("decision") == "BLOCK"
        and projection.get("risk_decision", {}).get("independent") is True
        and projection.get("capabilities", {}).get("execution_authority") == "NONE"
        and projection.get("capabilities", {}).get("paper_orders") == "DISABLED"
        and projection.get("capabilities", {}).get("live_orders") == "DISABLED"
        and projection.get("capabilities", {}).get("order_creation") is False
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
