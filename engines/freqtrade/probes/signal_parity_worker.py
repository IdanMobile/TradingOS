"""Runs INSIDE engines/freqtrade/.venv (imports freqtrade strategy classes; GPL boundary
AD-02 — only invoked as a subprocess by signal_parity_probe.py, never imported by core code).

Loads fixtures/micro/bars.csv, applies one baseline's generated strategy
(populate_indicators/populate_entry_trend/populate_exit_trend, no engine init needed since
these are pure-pandas transforms) and prints the per-bar entry/exit signals as CSV to stdout.

Run: engines/freqtrade/.venv/bin/python signal_parity_worker.py B2
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BARS_CSV = ROOT / "fixtures" / "micro" / "bars.csv"
STRATEGIES_DIR = ROOT / "engines" / "freqtrade" / "lane" / "user_data" / "strategies"

CLASS_NAMES = {
    "B1": "B1BuyAndHold",
    "B2": "B2MaCrossover",
    "B3": "B3BollingerMr",
    "B4": "B4VolBreakout",
}


def load_strategy_class(baseline: str):
    class_name = CLASS_NAMES[baseline]
    module_path = STRATEGIES_DIR / f"{class_name}.py"
    spec = importlib.util.spec_from_file_location(class_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


def compute_signals(baseline: str) -> pd.DataFrame:
    cls = load_strategy_class(baseline)
    strat = cls.__new__(cls)  # bypass IStrategy.__init__ (needs live config); methods are pure
    df = pd.read_csv(BARS_CSV).rename(
        columns={"timestamp_open_utc": "date", "volume_base": "volume"}
    )
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = strat.populate_indicators(df, {"pair": "BTC/USDT"})
    df = strat.populate_entry_trend(df, {"pair": "BTC/USDT"})
    df = strat.populate_exit_trend(df, {"pair": "BTC/USDT"})
    for col in ("enter_long", "exit_long"):
        if col not in df:
            df[col] = 0
    out = df[["bar"]].copy()
    out["entry"] = df["enter_long"].fillna(0).astype(bool)
    out["exit"] = df["exit_long"].fillna(0).astype(bool)
    return out


if __name__ == "__main__":
    baseline = sys.argv[1]
    signals = compute_signals(baseline)
    print(signals.to_csv(index=False, lineterminator="\n"), end="")
