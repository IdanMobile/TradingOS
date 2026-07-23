#!/usr/bin/env python3
"""Build private Stage A evidence from explicit operator-copied demo files."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from tios.evidence.demo_decision_bridge import (
    DEFAULT_STAGE_A_OUTPUT,
    DemoDecisionBridgeError,
    canonical_json,
    run_bridge,
)

ROOT = Path(__file__).resolve().parents[1]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--lane-state", type=Path, required=True)
    result.add_argument("--heartbeat", type=Path, required=True)
    result.add_argument("--orders", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, default=DEFAULT_STAGE_A_OUTPUT)
    result.add_argument("--source-label", required=True)
    result.add_argument("--captured-at", required=True)
    return result


def main(argv: Sequence[str] | None = None, *, repo_root: Path = ROOT) -> int:
    arguments = parser().parse_args(argv)
    try:
        result = run_bridge(
            lane_state_path=arguments.lane_state,
            heartbeat_path=arguments.heartbeat,
            orders_path=arguments.orders,
            output_dir=arguments.output_dir,
            source_label=arguments.source_label,
            captured_at=arguments.captured_at,
            repo_root=repo_root,
        )
    except DemoDecisionBridgeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        canonical_json(
            {
                "schema": "tios.demo_decision_evidence.v1",
                "status": "PASS",
                "projection_status": result.projection["projection_status"],
                "event_count": len(result.events),
                "appended_event_count": result.appended_event_count,
                "export_sha256": result.export_sha256,
                "execution_authority": "NONE",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
