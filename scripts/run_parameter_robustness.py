"""Execute the B2 parameter neighborhood on the untouched holdout window."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "validation" / "B2_F0_S0" / "robustness"
STRATEGY_TEMPLATE = """from freqtrade.strategy import IStrategy
from pandas import DataFrame

class {class_name}(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = False
    minimal_roi = {{"0": 1000}}
    stoploss = -1.0
    startup_candle_count = {slow}
    process_only_new_candles = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma_fast"] = dataframe["close"].rolling({fast}).mean()
        dataframe["sma_slow"] = dataframe["close"].rolling({slow}).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["sma_fast"] > dataframe["sma_slow"], "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["sma_fast"] < dataframe["sma_slow"], "exit_long"] = 1
        return dataframe
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timerange", default="20250525-20260701")
    args = parser.parse_args()
    variants = ((2, 5), (3, 5), (4, 5), (3, 4), (3, 6))
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tios_b2_robustness_") as strategy_dir:
        strategy_path = Path(strategy_dir)
        for fast, slow in variants:
            variant = f"fast{fast}_slow{slow}"
            class_name = f"B2Neighborhood{fast}{slow}"
            (strategy_path / f"{class_name}.py").write_text(
                STRATEGY_TEMPLATE.format(class_name=class_name, fast=fast, slow=slow)
            )
            run_dir = OUT / variant
            run_dir.mkdir(parents=True, exist_ok=True)
            command = [
                str(ROOT / "engines/freqtrade/.venv/bin/freqtrade"),
                "backtesting",
                "--config",
                str(ROOT / "engines/freqtrade/lane/config_F1_S1.json"),
                "--strategy-path",
                str(strategy_path),
                "--strategy",
                class_name,
                "--timerange",
                args.timerange,
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
                raise SystemExit(f"{variant} failed: rc={proc.returncode}, zips={len(zips)}")
            manifest = {
                "artifact_id": f"B2-ROBUSTNESS-{variant}",
                "produced_by": "T-009-03",
                "status": "OK",
                "engine": "freqtrade",
                "strategy": class_name,
                "dataset_id": "DS-CRYPTO-SPOT-BAKEOFF-V1",
                "scenario": "F1/S1",
                "window": args.timerange,
                "parameters": {"fast_window": fast, "slow_window": slow},
                "files": [
                    {
                        "path": zips[-1].name,
                        "sha256": hashlib.sha256(zips[-1].read_bytes()).hexdigest(),
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
    summary = []
    for path in sorted(OUT.glob("*/normalized_metrics.json")):
        data = json.loads(path.read_text())
        summary.append(
            {
                "variant": path.parent.name,
                "profit_total_abs": data["profit_total_abs"],
                "trades_roundtrips": data["trades_roundtrips"],
                "fee_audit": data["fee_audit"],
                "artifact": str(path.parent.relative_to(ROOT)),
            }
        )
    (OUT / "summary.json").write_text(
        json.dumps(
            {
                "status": "COMPLETE_ENGINE_RUNS",
                "holdout_window": args.timerange,
                "variants": summary,
                "interpretation": (
                    "All retained neighborhood variants are evidence; "
                    "no isolated optimum is promoted."
                ),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {OUT / 'summary.json'}")


if __name__ == "__main__":
    main()
