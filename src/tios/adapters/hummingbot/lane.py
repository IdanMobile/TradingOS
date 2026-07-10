"""Hummingbot bake-off lane (T-006-05, REQ-018). Container-only: nothing in this
process imports hummingbot; the runner (`_run.py`) executes inside the digest-pinned
`hummingbot/hummingbot:version-2.15.0` image (conda env "hummingbot") via `docker run`,
mirroring the Freqtrade lane's subprocess-isolation pattern (AD-02) — here for
container-boundary hygiene rather than a GPL requirement.

Converter C-hb (declared lossy): canonical decimal128 -> float64 (pandas/hummingbot's
dataframe model); loss recorded in every artifact manifest, same as Freqtrade's C-ft.

Run: uv run python -m tios.adapters.hummingbot.lane
     [--scenarios F0/S0,F1/S1] [--baselines B1,B2,B3,B4] [--pairs BTCUSDT,ETHUSDT]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from tios.core_types.engine import MANDATORY_GRID, FeeSlippageScenario

ROOT = Path(__file__).resolve().parents[4]
ENGINE_DIR = ROOT / "engines" / "hummingbot"
LANE = ENGINE_DIR / "lane"  # engine working dir (gitignored)
DATA_DIR = LANE / "data"
ARTIFACTS = ROOT / "artifacts" / "bakeoff" / "hummingbot"
NORM = ROOT / "data" / "normalized"
IMAGE = "hummingbot/hummingbot:version-2.15.0"

PAIRS = {"BTCUSDT": "BTC-USDT", "ETHUSDT": "ETH-USDT"}
TIMEFRAME = "5m"
START = datetime(2021, 1, 1, tzinfo=UTC)
END = datetime(2026, 7, 1, tzinfo=UTC)
BASELINES = ("B1", "B2", "B3", "B4")


def convert_data(pairs: list[str]) -> list[str]:
    """Canonical parquet -> CSV(timestamp_epoch_s, OHLCV float) for in-container
    injection into BacktestingDataProvider.candles_feeds (no network fetch)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    notes = []
    for sym in pairs:
        table = pq.read_table(NORM / f"{sym}_{TIMEFRAME}.parquet")
        dest = DATA_DIR / f"{sym}_{TIMEFRAME}.csv"
        with dest.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            for row in table.select(
                ["timestamp_open_utc", "open", "high", "low", "close", "volume_base"]
            ).to_pylist():
                w.writerow(
                    [
                        int(row["timestamp_open_utc"].timestamp()),
                        float(row["open"]),
                        float(row["high"]),
                        float(row["low"]),
                        float(row["close"]),
                        float(row["volume_base"]),
                    ]
                )
        notes.append(f"{dest.name}: {table.num_rows} rows from {sym}_{TIMEFRAME}.parquet")
    return notes


def run_backtest(
    baseline: str, sym: str, scenario: FeeSlippageScenario, run_tag: str
) -> dict[str, Any]:
    trading_pair = PAIRS[sym]
    out_dir = ARTIFACTS / baseline / sym / scenario.scenario_id.replace("/", "_") / run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_out = out_dir / "raw.json"

    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{LANE}:/lane:ro",
        "-v",
        f"{out_dir}:/out",
        "--entrypoint",
        "/bin/bash",
        IMAGE,
        "-lc",
        (
            "source /opt/conda/etc/profile.d/conda.sh && conda activate hummingbot && "
            "export PYTHONPATH=/home/hummingbot && "
            f"python /lane/_run.py --baseline {baseline} --trading-pair {trading_pair} "
            f"--csv /lane/data/{sym}_{TIMEFRAME}.csv "
            f"--start {int(START.timestamp())} --end {int(END.timestamp())} "
            f"--trade-cost {scenario.fee_rate_per_side} --out /out/raw.json"
        ),
    ]
    started = datetime.now(tz=UTC).isoformat()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    (out_dir / "stdout.log").write_text(proc.stdout)
    (out_dir / "stderr.log").write_text(proc.stderr)

    status = "OK" if proc.returncode == 0 and raw_out.exists() else "FAILED"
    manifest = {
        "artifact_id": f"hummingbot-{baseline}-{sym}-{scenario.scenario_id}-{run_tag}",
        "produced_by": "T-006-05",
        "status": status,
        "engine": "hummingbot",
        "engine_version": "2.15.0",
        "image_digest_ref": str(ENGINE_DIR / "env_manifest.txt"),
        "command": cmd,
        "returncode": proc.returncode,
        "started_utc": started,
        "scenario": scenario.scenario_id,
        "fee_rate_per_side": str(scenario.fee_rate_per_side),
        "capability_gaps": [
            "DirectionalTradingControllerBase's native exit path is triple-barrier "
            "(stop-loss/take-profit/time-limit), not signal-based; disabled via "
            "stop_loss=take_profit=time_limit=None and replaced with an overridden "
            "stop_actions_proposal driven by the canonical exit rule (supported "
            "extension point, not an internals patch).",
            "No native per-side bps slippage model in run_backtesting()/"
            "PositionExecutorSimulator; S-scenarios applied post-hoc in parity "
            "analysis, same convention as the Freqtrade lane.",
            "leverage forced to 1 and position_mode forced to ONEWAY to adapt the "
            "perpetual-oriented DirectionalTradingControllerConfigBase defaults "
            "(leverage=20, HEDGE) to the Crypto Spot MVP slice.",
        ],
        "engine_bug_workarounds": [
            "hummingbot 2.15.0 + pandas 3.0.3: DataFrame.set_index() silently collapses "
            "an evenly-spaced int64 column into a RangeIndex; BacktestingEngineBase."
            "prepare_market_data() hits this on its post-merge_asof timestamp index, "
            "then position_executor_simulator.simulate()'s bare `df[:tl_timestamp]` "
            "slice throws TypeError because tl_timestamp is a float (iterrows() "
            "upcasts a mixed int/float row). Fix: keep the injected timestamp column "
            "float64 end-to-end (engines/hummingbot/_run_template.py load_candles) so "
            "the index never collapses to RangeIndex — no engine-internals patch.",
        ],
        "converter_losses": ["decimal128->float64 (pandas/hummingbot dataframe model)"],
        "input_refs": ["DS-CRYPTO-SPOT-BAKEOFF-V1"],
        "files": (
            [{"path": "raw.json", "sha256": hashlib.sha256(raw_out.read_bytes()).hexdigest()}]
            if raw_out.exists()
            else []
        ),
        "schema_version": 1,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", default="F0/S0,F1/S1")
    parser.add_argument("--baselines", default=",".join(BASELINES))
    parser.add_argument("--pairs", default=",".join(PAIRS))
    parser.add_argument("--run-tag", default="run1")
    args = parser.parse_args()
    wanted = args.scenarios.split(",")
    scenarios = [s for s in MANDATORY_GRID if s.scenario_id in wanted]
    pairs = args.pairs.split(",")

    LANE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ENGINE_DIR / "_run_template.py", LANE / "_run.py")

    notes = convert_data(pairs)
    for n in notes:
        print("data:", n)

    for baseline in args.baselines.split(","):
        for sym in pairs:
            for scenario in scenarios:
                m = run_backtest(baseline, sym, scenario, args.run_tag)
                print(
                    f"{baseline} {sym} {scenario.scenario_id}: {m['status']} (rc={m['returncode']})"
                )


if __name__ == "__main__":
    main()
