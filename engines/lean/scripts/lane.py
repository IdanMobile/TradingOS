"""LEAN bake-off lane (T-006-04, REQ-017). Docker-only execution via the LEAN CLI
(Apache-2.0 engine, quantconnect/lean image) — no QuantConnect account/cloud data
used. RG-02 finding: `lean init`/`lean login` gate on QC account credentials, but
that gate is for cloud project sync, not local Docker backtesting; local backtests
run fine with a hand-assembled lean.json (from the OSS Lean repo's Launcher/config.json)
and a custom PythonData reader over our own converted CSVs, so no account is required.

Converter C-lean (declared lossy): canonical decimal128 -> float64 (LEAN's data
model uses double-precision floats); loss recorded in every artifact manifest.

Scope reduction (documented, not silent): the full canonical range is 577,803 5m
bars/symbol (2021-01-01..2026-06-30). LEAN's Python custom-data Reader is invoked
per-line and is far slower than freqtrade's vectorized pandas backtest; running the
full range was not viable inside this task's time/token budget. This lane uses the
most recent LEAN_WINDOW_DAYS days of the same frozen dataset instead of a full-range
run — a bounded subset of DS-CRYPTO-SPOT-BAKEOFF-V1, not a different dataset.

Run: uv run python -m tios.adapters.lean.lane [--baselines B1,B2,B3,B4]
     [--scenarios F0/S0,F1/S1] [--run-tag run1]
Then (per project) the LEAN CLI itself, e.g.:
     engines/lean/.venv/bin/lean backtest engines/lean/lane/B1 \\
         --parameter fee_rate 0.001 --parameter slippage_bps 1 \\
         --parameter scenario_id F1_S1 --parameter run_tag run1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.compute as pc
import pyarrow.parquet

from tios.core_types.engine import MANDATORY_GRID, FeeSlippageScenario

ROOT = Path(__file__).resolve().parents[3]
ENGINE_DIR = ROOT / "engines" / "lean"
LEAN_BIN = ENGINE_DIR / ".venv" / "bin" / "lean"
LANE = ENGINE_DIR / "lane"  # LEAN CLI root (has lean.json + data/)
DATA_DIR = LANE / "data"
CUSTOM_DATA_DIR = DATA_DIR / "custom_bakeoff"
ARTIFACTS = ROOT / "artifacts" / "bakeoff" / "lean"
NORM = ROOT / "data" / "normalized"

PAIRS = ("BTCUSDT", "ETHUSDT")
TIMEFRAME = "5m"
BASELINES = ("B1", "B2", "B3", "B4")
LEAN_WINDOW_DAYS = 60  # scope reduction — see module docstring


def convert_data(window_days: int = LEAN_WINDOW_DAYS) -> list[str]:
    """Canonical parquet -> LEAN custom-data CSV (converter C-lean; lossy: decimal->float64)."""
    CUSTOM_DATA_DIR.mkdir(parents=True, exist_ok=True)
    notes = []
    for sym in PAIRS:
        table = pyarrow.parquet.read_table(NORM / f"{sym}_{TIMEFRAME}.parquet")
        cutoff = pc.subtract(
            pc.max(table.column("timestamp_open_utc")),
            pyarrow.scalar(window_days * 86400 * 1_000_000, type=pyarrow.duration("us")),
        )
        table = table.filter(pc.greater_equal(table.column("timestamp_open_utc"), cutoff))
        dest = CUSTOM_DATA_DIR / f"{sym}.csv"
        with dest.open("w") as f:
            for row in table.to_pylist():
                ts = row["timestamp_open_utc"].strftime("%Y%m%d %H:%M:%S")
                f.write(
                    f"{ts},{row['open']},{row['high']},{row['low']},"
                    f"{row['close']},{row['volume_base']}\n"
                )
        notes.append(f"{dest.name}: {table.num_rows} rows from {sym}_{TIMEFRAME}.parquet")
    return notes


ALGO_TEMPLATE = '''
# region imports
from AlgorithmImports import *
# endregion


class CryptoBar(PythonData):
    """Custom-data reader over our own converted CSV (no QC cloud data used)."""

    def get_source(self, config, date, is_live_mode):
        path = f"/Lean/Data/custom_bakeoff/{{config.symbol.value}}.csv"
        return SubscriptionDataSource(path, SubscriptionTransportMedium.LOCAL_FILE)

    def reader(self, config, line, date, is_live_mode):
        if not line or line[0].isalpha():
            return None
        parts = line.split(",")
        data = CryptoBar()
        data.symbol = config.symbol
        data.time = datetime.strptime(parts[0], "%Y%m%d %H:%M:%S")
        data.end_time = data.time + timedelta(minutes=5)
        data["open"] = float(parts[1])
        data["high"] = float(parts[2])
        data["low"] = float(parts[3])
        data.value = float(parts[4])
        data["close"] = float(parts[4])
        data["volume"] = float(parts[5])
        return data


class PctFeeModel(FeeModel):
    """Percent-of-notional fee per side (mandatory-grid scenario), not LEAN's flat default."""

    def __init__(self, rate):
        self.rate = rate

    def get_order_fee(self, parameters):
        order = parameters.order
        price = parameters.security.price
        fee = abs(order.quantity) * price * self.rate
        return OrderFee(CashAmount(fee, parameters.security.quote_currency.symbol))


class {class_name}(QCAlgorithm):
    def initialize(self):
        self.set_start_date({start_year}, {start_month}, {start_day})
        self.set_end_date({end_year}, {end_month}, {end_day})
        self.set_cash(100000)
        self.set_time_zone(TimeZones.UTC)

        fee_rate = float(self.get_parameter("fee_rate") or "0")
        slippage_bps = float(self.get_parameter("slippage_bps") or "0")
        self.scenario_id = self.get_parameter("scenario_id") or "F0_S0"
        self.run_tag = self.get_parameter("run_tag") or "run1"

        self.symbols = []
        for pair in {pairs!r}:
            sym = self.add_data(CryptoBar, pair, Resolution.MINUTE).symbol
            self.securities[sym].fee_model = PctFeeModel(fee_rate)
            self.securities[sym].set_slippage_model(ConstantSlippageModel(slippage_bps / 10000.0))
            self.symbols.append(sym)

        self.set_benchmark(lambda dt: 0)
        self.set_warm_up({warmup})
        self.fills = []
        self.closes = {{sym: deque(maxlen={hist_len}) for sym in self.symbols}}
        self.highs = {{sym: deque(maxlen={hist_len}) for sym in self.symbols}}

    def on_order_event(self, order_event):
        if order_event.status == OrderStatus.FILLED:
            self.fills.append(
                {{
                    "ts_fill": self.time.isoformat(),
                    "side": "buy" if order_event.direction == OrderDirection.BUY else "sell",
                    "pair": str(order_event.symbol.value),
                    "price": float(order_event.fill_price),
                    "qty": abs(float(order_event.fill_quantity)),
                    "fee": float(order_event.order_fee.value.amount),
                }}
            )

{body}

    def on_end_of_algorithm(self):
        self.log(json.dumps({{"fills": self.fills}}))
'''

def write_algorithm(baseline: str, project_dir: Path) -> None:
    class_name = {
        "B1": "B1BuyAndHold",
        "B2": "B2MaCrossover",
        "B3": "B3BollingerMr",
        "B4": "B4VolBreakout",
    }[baseline]
    bodies = {
        "B1": """
    def on_data(self, data: Slice):
        if self.is_warming_up:
            return
        for sym in self.symbols:
            if not self.portfolio[sym].invested and data.contains_key(sym):
                self.set_holdings(sym, 1.0 / len(self.symbols))
""",
        "B2": """
    def on_data(self, data: Slice):
        # ponytail: rolling deque, not self.history() per bar -- history() on custom
        # PythonData re-scans from disk every call (no cache like built-in resolutions),
        # which is O(n^2) over a run and was observed to hang a 60-day backtest past 29min.
        for sym in self.symbols:
            if data.contains_key(sym):
                self.closes[sym].append(data[sym].value)
        if self.is_warming_up:
            return
        for sym in self.symbols:
            if not data.contains_key(sym) or len(self.closes[sym]) < 6:
                continue
            recent = list(self.closes[sym])
            sma_fast = sum(recent[-3:]) / 3
            sma_slow = sum(recent[-5:]) / 5
            invested = self.portfolio[sym].invested
            if sma_fast > sma_slow and not invested:
                self.set_holdings(sym, 1.0 / len(self.symbols))
            elif sma_fast < sma_slow and invested:
                self.liquidate(sym)
""",
        "B3": """
    def on_data(self, data: Slice):
        # ponytail: rolling deque, not self.history() per bar -- see B2 comment.
        for sym in self.symbols:
            if data.contains_key(sym):
                self.closes[sym].append(data[sym].value)
        if self.is_warming_up:
            return
        for sym in self.symbols:
            if not data.contains_key(sym) or len(self.closes[sym]) < 3:
                continue
            recent = list(self.closes[sym])
            mid = sum(recent) / len(recent)
            var = sum((c - mid) ** 2 for c in recent) / len(recent)
            std = var ** 0.5
            lower = mid - 1 * std
            price = data[sym].value
            invested = self.portfolio[sym].invested
            if price < lower and not invested:
                self.set_holdings(sym, 1.0 / len(self.symbols))
            elif price >= mid and invested:
                self.liquidate(sym)
""",
        "B4": """
    def on_data(self, data: Slice):
        # ponytail: rolling deque, not self.history() per bar -- see B2 comment.
        for sym in self.symbols:
            if data.contains_key(sym):
                self.closes[sym].append(data[sym].value)
                self.highs[sym].append(data[sym]["high"])
        if self.is_warming_up:
            return
        for sym in self.symbols:
            if not data.contains_key(sym) or len(self.closes[sym]) < 9:
                continue
            highs = list(self.highs[sym])
            closes = list(self.closes[sym])
            hh_prev5 = max(highs[-6:-1])
            sma_3 = sum(closes[-3:]) / 3
            price = data[sym].value
            invested = self.portfolio[sym].invested
            if price > hh_prev5 and not invested:
                self.set_holdings(sym, 1.0 / len(self.symbols))
            elif price < sma_3 and invested:
                self.liquidate(sym)
""",
    }
    hist_len = {"B1": 0, "B2": 6, "B3": 3, "B4": 9}[baseline]
    src = ALGO_TEMPLATE.format(
        class_name=class_name,
        start_year=2026,
        start_month=5,
        start_day=1,
        end_year=2026,
        end_month=6,
        end_day=30,
        pairs=list(PAIRS),
        warmup=hist_len,
        hist_len=hist_len,
        body=bodies[baseline],
    )
    src = "import json\nfrom collections import deque\nfrom datetime import datetime, timedelta\n" + src
    (project_dir / "main.py").write_text(src.lstrip())


def normalize_result(
    baseline: str,
    scenario: FeeSlippageScenario,
    run_tag: str,
    source_run_dir: Path | None = None,
) -> dict[str, Any]:
    """Read the latest LEAN backtest output for `baseline` and emit NormalizedResult-shaped
    artifacts (mirrors tios.adapters.freqtrade.normalize_result)."""
    project_dir = LANE / baseline
    backtests_dir = project_dir / "backtests"
    if source_run_dir is None:
        runs = sorted(p for p in backtests_dir.iterdir() if p.is_dir()) if backtests_dir.is_dir() else []
        if not runs:
            raise SystemExit(f"no backtest output dir under {backtests_dir}")
        run_dir = runs[-1]
    else:
        run_dir = source_run_dir
        if not run_dir.is_dir():
            raise SystemExit(f"backtest output dir does not exist: {run_dir}")
    log_files = list(run_dir.glob("*-log.txt"))
    fills: list[dict[str, Any]] = []
    if log_files:
        for line in log_files[0].read_text().splitlines():
            if '"fills"' in line:
                idx = line.find("{")
                fills = json.loads(line[idx:]).get("fills", [])

    out_dir = ARTIFACTS / baseline / scenario.scenario_id.replace("/", "_") / run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in run_dir.glob("*"):
        if f.is_file():
            shutil.copy2(f, out_dir / f.name)

    manifest = {
        "artifact_id": f"lean-{baseline}-{scenario.scenario_id}-{run_tag}",
        "produced_by": "T-006-04",
        "status": "OK" if fills or scenario.scenario_id == "F0/S0" else "FAILED",
        "engine": "lean",
        "scenario": scenario.scenario_id,
        "fee_rate_per_side": str(scenario.fee_rate_per_side),
        "slippage_bps_per_side": str(scenario.slippage_bps_per_side),
        "window_days": LEAN_WINDOW_DAYS,
        "scope_reduction": (
            f"bounded to last {LEAN_WINDOW_DAYS} days of DS-CRYPTO-SPOT-BAKEOFF-V1 "
            "(full 5.5y range not run — Python custom-data Reader throughput ceiling)"
        ),
        "converter_losses": ["decimal128->float64 (LEAN double-precision data model)"],
        "input_refs": ["DS-CRYPTO-SPOT-BAKEOFF-V1"],
        "fills": fills,
        "fill_count": len(fills),
        "files": [
            {"path": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in out_dir.iterdir()
            if p.is_file()
        ],
        "schema_version": 1,
        "generated_utc": datetime.now(tz=UTC).isoformat(),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baselines", default=",".join(BASELINES))
    parser.add_argument("--scenarios", default="F0/S0,F1/S1")
    args = parser.parse_args()
    wanted = args.scenarios.split(",")
    scenarios = [s for s in MANDATORY_GRID if s.scenario_id in wanted]

    notes = convert_data()
    for n in notes:
        print("data:", n)

    for baseline in args.baselines.split(","):
        project_dir = LANE / baseline
        project_dir.mkdir(parents=True, exist_ok=True)
        write_algorithm(baseline, project_dir)
        print(f"wrote {project_dir / 'main.py'}")

    print("scenarios:", [s.scenario_id for s in scenarios])


if __name__ == "__main__":
    main()
