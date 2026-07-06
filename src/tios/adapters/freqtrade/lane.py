"""Freqtrade bake-off lane (T-006-02, REQ-015). Subprocess/CLI ONLY — GPL boundary
(AD-02): nothing here imports freqtrade; generated strategy files run inside the
engine's own isolated venv (engines/freqtrade/.venv).

Converter C-ft (declared lossy): canonical decimal128 → float64 (freqtrade's
dataframe model); loss recorded in every artifact manifest.

Run: uv run python -m tios.adapters.freqtrade.lane
     [--scenarios F0/S0,F1/S1] [--baselines B1,B2,B3,B4]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.feather
import pyarrow.parquet

from tios.core_types.engine import MANDATORY_GRID, FeeSlippageScenario

ROOT = Path(__file__).resolve().parents[4]
ENGINE_DIR = ROOT / "engines" / "freqtrade"
FT_BIN = ENGINE_DIR / ".venv" / "bin" / "freqtrade"
LANE = ENGINE_DIR / "lane"  # engine working dir (gitignored)
USER_DATA = LANE / "user_data"
ARTIFACTS = ROOT / "artifacts" / "bakeoff" / "freqtrade"
NORM = ROOT / "data" / "normalized"

PAIRS = {"BTCUSDT": "BTC/USDT", "ETHUSDT": "ETH/USDT"}
TIMEFRAME = "5m"
TIMERANGE = "20210101-20260701"
BASELINES = ("B1", "B2", "B3", "B4")

STRATEGY_SOURCES: dict[str, str] = {
    # Generated from fixtures/strategies/baselines/*.yaml (canonical specs).
    # Semantics: signal evaluated at bar close, execution next bar open (freqtrade default).
    "B1": """
from freqtrade.strategy import IStrategy
from pandas import DataFrame


class B1BuyAndHold(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = False
    minimal_roi = {"0": 1000}   # effectively never (100000%)
    stoploss = -1.0             # never
    startup_candle_count = 0
    process_only_new_candles = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "exit_long"] = 0
        return dataframe
""",
    "B2": """
from freqtrade.strategy import IStrategy
from pandas import DataFrame


class B2MaCrossover(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = False
    minimal_roi = {"0": 1000}
    stoploss = -1.0
    startup_candle_count = 5
    process_only_new_candles = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma_fast"] = dataframe["close"].rolling(3).mean()
        dataframe["sma_slow"] = dataframe["close"].rolling(5).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["sma_fast"] > dataframe["sma_slow"], "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["sma_fast"] < dataframe["sma_slow"], "exit_long"] = 1
        return dataframe
""",
    "B3": """
from freqtrade.strategy import IStrategy
from pandas import DataFrame


class B3BollingerMr(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = False
    minimal_roi = {"0": 1000}
    stoploss = -1.0
    startup_candle_count = 3
    process_only_new_candles = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # canonical spec: window 3, k=1, POPULATION std (ddof=0)
        dataframe["middle_band"] = dataframe["close"].rolling(3).mean()
        std = dataframe["close"].rolling(3).std(ddof=0)
        dataframe["lower_band"] = dataframe["middle_band"] - 1 * std
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["close"] < dataframe["lower_band"], "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["close"] >= dataframe["middle_band"], "exit_long"] = 1
        return dataframe
""",
    "B4": """
from freqtrade.strategy import IStrategy
from pandas import DataFrame


class B4VolBreakout(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = False
    minimal_roi = {"0": 1000}
    stoploss = -1.0
    startup_candle_count = 6
    process_only_new_candles = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # canonical spec: max of previous 5 HIGHS excluding current bar (shift 1)
        dataframe["hh_prev5"] = dataframe["high"].rolling(5).max().shift(1)
        dataframe["sma_3"] = dataframe["close"].rolling(3).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["close"] > dataframe["hh_prev5"], "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["close"] < dataframe["sma_3"], "exit_long"] = 1
        return dataframe
""",
}
STRATEGY_CLASSES = {
    "B1": "B1BuyAndHold",
    "B2": "B2MaCrossover",
    "B3": "B3BollingerMr",
    "B4": "B4VolBreakout",
}


def convert_data() -> list[str]:
    """Canonical parquet → freqtrade feather (converter C-ft; lossy: decimal→float64)."""
    out_dir = USER_DATA / "data" / "binance"
    out_dir.mkdir(parents=True, exist_ok=True)
    notes = []
    for sym, pair in PAIRS.items():
        src = pyarrow.parquet.read_table(NORM / f"{sym}_{TIMEFRAME}.parquet")
        table = pa.table(
            {
                "date": src.column("timestamp_open_utc"),
                "open": src.column("open").cast(pa.float64()),
                "high": src.column("high").cast(pa.float64()),
                "low": src.column("low").cast(pa.float64()),
                "close": src.column("close").cast(pa.float64()),
                "volume": src.column("volume_base").cast(pa.float64()),
            }
        )
        dest = out_dir / f"{pair.replace('/', '_')}-{TIMEFRAME}.feather"
        pyarrow.feather.write_feather(table, dest)
        notes.append(f"{dest.name}: {table.num_rows} rows from {sym}_{TIMEFRAME}.parquet")
    return notes


def write_config(scenario: FeeSlippageScenario) -> Path:
    config = {
        "trading_mode": "spot",
        "dry_run": True,
        "max_open_trades": 1,
        "stake_currency": "USDT",
        "stake_amount": "unlimited",
        "dataformat_ohlcv": "feather",
        "pairlists": [{"method": "StaticPairList"}],
        "exchange": {
            "name": "binance",
            "key": "",
            "secret": "",
            "pair_whitelist": list(PAIRS.values()),
            "pair_blacklist": [],
        },
        "entry_pricing": {
            "price_side": "same",
            "use_order_book": False,
            "order_book_top": 1,
            "check_depth_of_market": {"enabled": False, "bids_to_ask_delta": 1},
        },
        "exit_pricing": {"price_side": "same", "use_order_book": False, "order_book_top": 1},
        "user_data_dir": str(USER_DATA),
    }
    path = LANE / f"config_{scenario.scenario_id.replace('/', '_')}.json"
    path.write_text(json.dumps(config, indent=2))
    return path


def run_backtest(baseline: str, scenario: FeeSlippageScenario, run_tag: str) -> dict[str, Any]:
    config = write_config(scenario)
    cmd = [
        str(FT_BIN),
        "backtesting",
        "--config",
        str(config),
        "--strategy",
        STRATEGY_CLASSES[baseline],
        "--timerange",
        TIMERANGE,
        "--fee",
        str(scenario.fee_rate_per_side),
        "--export",
        "trades",
        "--timeframe",
        TIMEFRAME,
    ]
    started = datetime.now(tz=UTC).isoformat()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=LANE, timeout=3600)
    out_dir = ARTIFACTS / baseline / scenario.scenario_id.replace("/", "_") / run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "stdout.log").write_text(proc.stdout)
    (out_dir / "stderr.log").write_text(proc.stderr)

    results_dir = USER_DATA / "backtest_results"
    exported = sorted(
        p for p in results_dir.glob("backtest-result-*") if p.suffix in (".zip", ".json")
    )
    result_file = exported[-1] if exported else None
    files = []
    if result_file:
        dest = out_dir / result_file.name
        shutil.copy2(result_file, dest)
        files.append(dest)
    manifest = {
        "artifact_id": f"freqtrade-{baseline}-{scenario.scenario_id}-{run_tag}",
        "produced_by": "T-006-02",
        # success requires BOTH a zero exit code AND an exported result artifact
        "status": "OK" if proc.returncode == 0 and result_file else "FAILED",
        "engine": "freqtrade",
        "command": cmd,
        "returncode": proc.returncode,
        "started_utc": started,
        "scenario": scenario.scenario_id,
        "fee_rate_per_side": str(scenario.fee_rate_per_side),
        "slippage_note": (
            "CapabilityGap: freqtrade backtesting has no per-side bps slippage model; "
            "S-scenarios applied post-hoc in parity analysis (documented, not silent)"
        ),
        "converter_losses": ["decimal128->float64 (freqtrade dataframe model)"],
        "input_refs": ["DS-CRYPTO-SPOT-BAKEOFF-V1"],
        "files": [
            {"path": f.name, "sha256": hashlib.sha256(f.read_bytes()).hexdigest()} for f in files
        ],
        "schema_version": 1,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", default="F0/S0,F1/S1")
    parser.add_argument("--baselines", default=",".join(BASELINES))
    parser.add_argument("--run-tag", default="run1")
    args = parser.parse_args()
    wanted = args.scenarios.split(",")
    scenarios = [s for s in MANDATORY_GRID if s.scenario_id in wanted]

    LANE.mkdir(parents=True, exist_ok=True)
    strat_dir = USER_DATA / "strategies"
    strat_dir.mkdir(parents=True, exist_ok=True)
    for b, src in STRATEGY_SOURCES.items():
        (strat_dir / f"{STRATEGY_CLASSES[b]}.py").write_text(src.lstrip())

    notes = convert_data()
    for n in notes:
        print("data:", n)

    for baseline in args.baselines.split(","):
        for scenario in scenarios:
            m = run_backtest(baseline, scenario, args.run_tag)
            print(f"{baseline} {scenario.scenario_id}: {m['status']} (rc={m['returncode']})")


if __name__ == "__main__":
    main()
