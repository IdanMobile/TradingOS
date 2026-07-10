"""Dry-run capability probe (T-006-02): starts `freqtrade trade --dry-run` (subprocess/CLI
only, AD-02), lets it initialize and run one bot-loop iteration against live exchange market
data with simulated (not real) orders, then stops it cleanly and records the evidence.

Not a live-trading test: config_F0_S0.json has dry_run=true (simulated fills only); no
API key/secret is set (empty strings), so no authenticated/order-placing exchange calls
are possible even if attempted.

Run: python3 engines/freqtrade/probes/dry_run_probe.py [--seconds 25]
"""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ENGINE_DIR = ROOT / "engines" / "freqtrade"
FT_BIN = ENGINE_DIR / ".venv" / "bin" / "freqtrade"
LANE = ENGINE_DIR / "lane"
CONFIG = LANE / "config_F0_S0.json"
OUT_DIR = ROOT / "artifacts" / "bakeoff" / "freqtrade" / "dry_run_probe"

PASS_MARKERS = ("Dry run is enabled",)
FAIL_MARKERS = ("Traceback (most recent call last)", "CRITICAL")


def run_probe(seconds: int) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    config = json.loads(CONFIG.read_text())
    assert config["dry_run"] is True, "refusing to run probe: dry_run must be true"
    assert not config["exchange"]["key"] and not config["exchange"]["secret"], (
        "refusing to run probe: exchange API credentials must be empty for this probe"
    )

    cmd = [str(FT_BIN), "trade", "--config", str(CONFIG), "--strategy", "B2MaCrossover"]
    proc = subprocess.Popen(
        cmd, cwd=LANE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    time.sleep(seconds)
    proc.send_signal(signal.SIGINT)  # freqtrade's documented graceful-stop signal
    try:
        stdout, _ = proc.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, _ = proc.communicate()

    (OUT_DIR / "trade_dry_run.log").write_text(stdout)
    found_pass = [m for m in PASS_MARKERS if m in stdout]
    found_fail = [m for m in FAIL_MARKERS if m in stdout]
    result = {
        "status": "PASS" if found_pass and not found_fail else "FAIL",
        "seconds_run": seconds,
        "pass_markers_found": found_pass,
        "fail_markers_found": found_fail,
        "log_path": str((OUT_DIR / "trade_dry_run.log").relative_to(ROOT)),
    }
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def write_report(result: dict) -> Path:
    lines = [
        "# Freqtrade dry-run capability probe (T-006-02)",
        "",
        f"Status: **{result['status']}** · ran {result['seconds_run']}s then sent SIGINT"
        " (freqtrade's documented graceful-stop signal).",
        "",
        "Config: `engines/freqtrade/lane/config_F0_S0.json` (`dry_run: true`,"
        " empty exchange key/secret — asserted before launch, so no authenticated/"
        "order-placing exchange calls are possible).",
        "",
        f"Pass markers found: {result['pass_markers_found'] or 'none'}",
        f"Fail markers found: {result['fail_markers_found'] or 'none'}",
        "",
        f"Full log: `{result['log_path']}`",
    ]
    report_path = ROOT / "artifacts" / "bakeoff" / "freqtrade" / "DRY_RUN_PROBE.md"
    report_path.write_text("\n".join(lines) + "\n")
    return report_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=25)
    args = parser.parse_args()
    result = run_probe(args.seconds)
    report_path = write_report(result)
    print(f"report: {report_path}")
    print(f"status: {result['status']}")
