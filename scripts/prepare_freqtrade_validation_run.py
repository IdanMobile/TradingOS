"""Prepare one Freqtrade export for canonical normalization."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("window")
    parser.add_argument("zip_path", type=Path)
    args = parser.parse_args()
    out = ROOT / "artifacts" / "validation" / "B2_F0_S0" / "runs" / args.window
    out.mkdir(parents=True, exist_ok=True)
    dest = out / args.zip_path.name
    shutil.copy2(args.zip_path, dest)
    manifest = {
        "artifact_id": f"B2-F1-S1-{args.window}",
        "produced_by": "T-009-03",
        "status": "OK",
        "engine": "freqtrade",
        "strategy": "B2MaCrossover",
        "window": args.window,
        "dataset_id": "DS-CRYPTO-SPOT-BAKEOFF-V1",
        "scenario": "F1/S1",
        "fee_rate_per_side": "0.001",
        "stake_amount": "1000",
        "max_open_trades": 1,
        "files": [{"path": dest.name, "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()}],
        "schema_version": 1,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(out)


if __name__ == "__main__":
    main()
