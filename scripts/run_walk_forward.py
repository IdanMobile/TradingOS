"""Execute the planned rolling walk-forward test windows for B2."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts" / "validation" / "B2_F0_S0" / "walk_forward"


def stamp(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%Y%m%d")


def main() -> None:
    plan = json.loads(
        (ROOT / "artifacts" / "validation" / "B2_F0_S0" / "walk_forward_report.json").read_text()
    )
    windows = plan["windows"]
    for index, window in enumerate(windows):
        run_dir = BASE / f"w{index:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        timerange = f"{stamp(window['test_start'])}-{stamp(window['test_end'])}"
        command = [
            str(ROOT / "engines/freqtrade/.venv/bin/freqtrade"),
            "backtesting",
            "--config",
            str(ROOT / "engines/freqtrade/lane/config_F1_S1.json"),
            "--strategy",
            "B2MaCrossover",
            "--timerange",
            timerange,
            "--timeframe",
            "5m",
            "--fee",
            "0.001",
            "--stake-amount",
            "1000",
            "--max-open-trades",
            "1",
            "--dry-run-wallet",
            "2000",
            "--export",
            "trades",
            "--backtest-directory",
            str(run_dir),
        ]
        proc = subprocess.run(command, capture_output=True, text=True, timeout=600)
        (run_dir / "run.log").write_text(proc.stdout + "\n" + proc.stderr)
        zips = sorted(run_dir.glob("*.zip"))
        if proc.returncode != 0 or not zips:
            raise SystemExit(f"walk-forward {index} failed: rc={proc.returncode}, zips={len(zips)}")
        zip_path = zips[-1]
        manifest = {
            "artifact_id": f"B2-WALK-FORWARD-{index:02d}",
            "produced_by": "T-009-03",
            "status": "OK",
            "engine": "freqtrade",
            "strategy": "B2MaCrossover",
            "dataset_id": "DS-CRYPTO-SPOT-BAKEOFF-V1",
            "window": window,
            "timerange": timerange,
            "parameters": {"fast_window": 3, "slow_window": 5},
            "fee_rate_per_side": "0.001",
            "files": [
                {
                    "path": zip_path.name,
                    "sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
                }
            ],
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "tios.adapters.freqtrade.normalize_result",
                "--run-dir",
                str(run_dir),
            ],
            cwd=ROOT,
            check=True,
        )
        print(f"window {index + 1}/{len(windows)} complete")
    summary = []
    for path in sorted(BASE.glob("w*/normalized_metrics.json")):
        metrics = json.loads(path.read_text())
        summary.append(
            {
                "window": path.parent.name,
                "profit_total_abs": metrics["profit_total_abs"],
                "trades_roundtrips": metrics["trades_roundtrips"],
                "fee_audit": metrics["fee_audit"],
                "artifact": str(path.parent.relative_to(ROOT)),
            }
        )
    (BASE / "summary.json").write_text(
        json.dumps(
            {
                "status": "COMPLETE_ENGINE_RUNS",
                "train_days": plan["train_days"],
                "test_days": plan["test_days"],
                "step_days": plan["step_days"],
                "windows": summary,
                "interpretation": (
                    "All test windows retain results; no test-window tuning was performed."
                ),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {BASE / 'summary.json'}")


if __name__ == "__main__":
    main()
