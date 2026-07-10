"""Materialize validation dates and search neighborhoods before optimization."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from tios.validation.planning import (
    chronological_split,
    parameter_neighborhood,
    walk_forward_windows,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "validation" / "B2_F0_S0"


def main() -> None:
    manifest = json.loads(
        (ROOT / "artifacts/datasets/DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json").read_text()
    )
    first = next(iter(manifest["tables"].values()))
    start = datetime.fromisoformat(first["coverage_start_utc"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(first["coverage_end_utc"].replace("Z", "+00:00"))
    split = chronological_split(start, end)
    windows = walk_forward_windows(start, end, 365, 90, 90)
    neighborhood = parameter_neighborhood(
        {"fast_window": Decimal("3"), "slow_window": Decimal("5")}
    )
    (OUT / "oos_report.json").write_text(
        json.dumps(
            {
                "status": "PLAN_MATERIALIZED_NOT_EXECUTED",
                "rule": "dates materialized before optimization; chronological only",
                "split": {key: value.isoformat() for key, value in split.__dict__.items()},
                "source_dataset": "DS-CRYPTO-SPOT-BAKEOFF-V1",
            },
            indent=2,
        )
        + "\n"
    )
    (OUT / "walk_forward_report.json").write_text(
        json.dumps(
            {
                "status": "PLAN_MATERIALIZED_NOT_EXECUTED",
                "train_days": 365,
                "test_days": 90,
                "step_days": 90,
                "windows": [
                    {key: value.isoformat() for key, value in row.items()} for row in windows
                ],
            },
            indent=2,
        )
        + "\n"
    )
    (OUT / "parameter_robustness.json").write_text(
        json.dumps(
            {
                "status": "PLAN_MATERIALIZED_NOT_EXECUTED",
                "base_parameters": {"fast_window": "3", "slow_window": "5"},
                "neighborhood": [
                    {key: str(value) for key, value in row.items()} for row in neighborhood
                ],
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote validation plans in {OUT}")


if __name__ == "__main__":
    main()
