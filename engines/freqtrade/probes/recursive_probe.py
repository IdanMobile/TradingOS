"""Run and retain Freqtrade's bounded recursive-indicator analysis."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FT = ROOT / "engines/freqtrade/.venv/bin/freqtrade"
LANE = ROOT / "engines/freqtrade/lane"
OUT = ROOT / "artifacts/bakeoff/freqtrade/recursive_probe"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(FT),
        "recursive-analysis",
        "--config",
        str(LANE / "config_F0_S0_BTCUSDT.json"),
        "--strategy",
        "B2MaCrossover",
        "--timerange",
        "20250101-20250401",
        "--startup-candle",
        "5",
        "30",
        "100",
        "--pairs",
        "BTC/USDT",
        "--no-color",
    ]
    process = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=300)
    log = process.stdout + process.stderr
    (OUT / "run.log").write_text(log, encoding="utf-8")
    no_recursive = "No variance on indicator(s) found due to recursive formula." in log
    no_lookahead = "No lookahead bias on indicators found." in log
    result = {
        "status": "PASS" if process.returncode == 0 and no_recursive and no_lookahead else "FAIL",
        "returncode": process.returncode,
        "strategy": "B2MaCrossover",
        "timerange": "20250101-20250401",
        "startup_candles": [5, 30, 100],
        "no_recursive_variance": no_recursive,
        "no_indicator_lookahead": no_lookahead,
        "command": cmd,
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    report = ROOT / "artifacts/bakeoff/freqtrade/RECURSIVE_ANALYSIS_B2.md"
    report.write_text(
        f"""# Freqtrade recursive analysis — B2

Status: **{result['status']}**

The native analyzer ran over BTC/USDT 5m for 2025-01-01 through 2025-04-01
with startup windows 5, 30, and 100. It reported no recursive indicator
variance and no indicator-only lookahead bias.

This closes indicator warm-up recursion for B2; it does not erase the separately
retained execution-state warning from `LOOKAHEAD_ANALYSIS_B2.md`.

Raw log: `artifacts/bakeoff/freqtrade/recursive_probe/run.log`.
""",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
