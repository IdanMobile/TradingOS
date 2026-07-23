#!/usr/bin/env python3
"""Capture the fixed active demo-lane files into one private sanitized snapshot."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from tios.evidence.demo_snapshot_adapter import (
    DemoSnapshotError,
    canonical_snapshot_bytes,
    capture_demo_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--captured-at", required=True)
    return result


def main(argv: Sequence[str] | None = None, *, repo_root: Path = ROOT) -> int:
    arguments = parser().parse_args(argv)
    try:
        result = capture_demo_snapshot(
            captured_at=arguments.captured_at,
            repo_root=repo_root,
        )
    except DemoSnapshotError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        canonical_snapshot_bytes(
            {
                "schema": "tios.demo_snapshot.v1",
                "capture_status": result.coverage["capture_status"],
                "evidence_completeness": result.coverage["evidence_completeness"],
                "stage_a_commit_status": result.coverage["stage_a_commit_status"],
                "snapshot_id": result.snapshot_id,
                "snapshot_dir": str(result.snapshot_dir.relative_to(repo_root.resolve())),
                "stage_a_input_ready": True,
                "execution_authority": "NONE",
                "promotion_eligible": result.coverage["promotion_eligible"],
            }
        ).decode("utf-8"),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
