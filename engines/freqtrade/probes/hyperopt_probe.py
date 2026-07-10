"""Bounded hyperopt + all-trial-retention probe (T-006-02): runs a small, bounded Freqtrade
hyperopt search (subprocess/CLI only, AD-02) and verifies every epoch/trial is retained in
the results store, not just the best one (a common footgun: hyperopt tooling that reports
"best" also needs to expose the full trial history for audit/reproducibility).

Run: python3 engines/freqtrade/probes/hyperopt_probe.py [--epochs 8]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ENGINE_DIR = ROOT / "engines" / "freqtrade"
FT_BIN = ENGINE_DIR / ".venv" / "bin" / "freqtrade"
LANE = ENGINE_DIR / "lane"
CONFIG = LANE / "config_F1_S1.json"
HYPEROPT_RESULTS_DIR = LANE / "user_data" / "hyperopt_results"
OUT_DIR = ROOT / "artifacts" / "bakeoff" / "freqtrade" / "hyperopt_probe"

STRATEGY = "B2MaCrossover"
TIMERANGE = "20250101-20250401"  # 3mo bounded window, kept small for probe speed
FEE = "0.001"
HYPEROPT_LOSS = "SharpeHyperOptLoss"


def run_hyperopt(epochs: int) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in HYPEROPT_RESULTS_DIR.glob("*.fthypt"):
        old.unlink()  # start clean so epoch-count verification below is unambiguous

    cmd = [
        str(FT_BIN),
        "hyperopt",
        "--config",
        str(CONFIG),
        "--strategy",
        STRATEGY,
        "--timerange",
        TIMERANGE,
        "--fee",
        FEE,
        "--epochs",
        str(epochs),
        "--spaces",
        "roi",
        "stoploss",
        "--hyperopt-loss",
        HYPEROPT_LOSS,
        "--job-workers",
        "1",
        "--random-state",
        "42",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=LANE, timeout=1800)
    (OUT_DIR / "hyperopt_stdout.log").write_text(proc.stdout)
    (OUT_DIR / "hyperopt_stderr.log").write_text(proc.stderr)
    return {"returncode": proc.returncode, "cmd": cmd}


def verify_retention(epochs: int) -> dict:
    result_files = sorted(HYPEROPT_RESULTS_DIR.glob("*.fthypt"))
    if not result_files:
        return {"status": "FAIL", "reason": "no .fthypt result file produced"}
    result_file = result_files[-1]

    csv_path = OUT_DIR / "hyperopt_list.csv"
    proc = subprocess.run(
        [
            str(FT_BIN),
            "hyperopt-list",
            "--config",
            str(CONFIG),
            "--hyperopt-filename",
            result_file.name,
            "--no-color",
            "--export-csv",
            str(csv_path),
            "--no-details",
        ],
        capture_output=True,
        text=True,
        cwd=LANE,
        timeout=120,
    )
    (OUT_DIR / "hyperopt_list_stdout.log").write_text(proc.stdout)
    if proc.returncode != 0:
        return {
            "status": "FAIL",
            "reason": "hyperopt-list nonzero exit",
            "stderr": proc.stderr[-2000:],
        }
    if not csv_path.exists():
        return {"status": "FAIL", "reason": "hyperopt-list produced no export-csv"}

    import csv as csv_module

    with csv_path.open() as f:
        epoch_rows = list(csv_module.DictReader(f))

    retained = len(epoch_rows)
    dest = OUT_DIR / result_file.name
    dest.write_bytes(result_file.read_bytes())
    return {
        "status": "PASS" if retained == epochs else "FAIL",
        "requested_epochs": epochs,
        "retained_epochs": retained,
        "result_file": str(dest.relative_to(ROOT)),
    }


def write_report(run_info: dict, retention: dict, epochs: int) -> Path:
    lines = [
        "# Freqtrade bounded hyperopt + all-trial-retention probe (T-006-02)",
        "",
        f"Strategy: {STRATEGY} · Timerange: {TIMERANGE} (bounded, probe speed) · "
        f"Epochs requested: {epochs} · Spaces: roi, stoploss · Loss: {HYPEROPT_LOSS}",
        "",
        f"Hyperopt run exit code: {run_info['returncode']}",
        "",
        f"Retention check: **{retention['status']}**",
        f"- requested epochs: {retention.get('requested_epochs', epochs)}",
        f"- epochs retained in results store (via `freqtrade hyperopt-list --export-csv`):"
        f" {retention.get('retained_epochs', 'n/a')}",
    ]
    if retention["status"] == "FAIL":
        lines.append(f"- reason: {retention.get('reason', 'epoch count mismatch')}")
    if "result_file" in retention:
        lines.append(f"- results store copy: `{retention['result_file']}`")
    lines += [
        "",
        "Evidence: `hyperopt_stdout.log`, `hyperopt_stderr.log`, `hyperopt_list_stdout.log`"
        " under `artifacts/bakeoff/freqtrade/hyperopt_probe/`.",
    ]
    report_path = ROOT / "artifacts" / "bakeoff" / "freqtrade" / "HYPEROPT_RETENTION_PROBE.md"
    report_path.write_text("\n".join(lines) + "\n")
    return report_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=8)
    args = parser.parse_args()
    run_info = run_hyperopt(args.epochs)
    retention = verify_retention(args.epochs)
    (OUT_DIR / "result.json").write_text(
        json.dumps({"run": run_info, "retention": retention}, indent=2, default=str) + "\n"
    )
    report_path = write_report(run_info, retention, args.epochs)
    print(f"report: {report_path}")
    print(f"status: {retention['status']}")
