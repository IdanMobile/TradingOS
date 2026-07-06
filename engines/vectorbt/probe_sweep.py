"""vectorbt accelerator probe (T-006-06, REQ-019). Runs INSIDE engines/vectorbt/.venv
(Apache-2.0 + Commons Clause — internal research use; never imported by src/tios).

B2-family MA-crossover parameter sweep on the frozen dataset with ALL trials
retained (anti-overfit rule: winners are meaningless without their population).

Run: engines/vectorbt/.venv/bin/python engines/vectorbt/probe_sweep.py
"""

import json
import time
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "bakeoff" / "vectorbt"
FEES = 0.001  # F1 per side

FAST = [2, 3, 5, 8, 10, 15]
SLOW = [10, 20, 30, 40, 50, 60]


def main() -> None:
    import vectorbt as vbt

    close = pd.read_parquet(
        ROOT / "data" / "normalized" / "BTCUSDT_5m.parquet",
        columns=["timestamp_open_utc", "close"],
    ).set_index("timestamp_open_utc")["close"].astype("float64")

    combos = [(f, s) for f, s in product(FAST, SLOW) if f < s]
    t0 = time.perf_counter()
    fast_ma = vbt.MA.run(close, [c[0] for c in combos], short_name="fast", per_column=False)
    slow_ma = vbt.MA.run(close, [c[1] for c in combos], short_name="slow", per_column=False)
    entries = fast_ma.ma_crossed_above(slow_ma)
    exits = fast_ma.ma_crossed_below(slow_ma)
    pf = vbt.Portfolio.from_signals(close, entries, exits, fees=FEES, init_cash=1000.0)
    total_return = pf.total_return()
    trades_count = pf.trades.count()
    elapsed = time.perf_counter() - t0

    OUT.mkdir(parents=True, exist_ok=True)
    results = pd.DataFrame(
        {
            "fast": [c[0] for c in combos],
            "slow": [c[1] for c in combos],
            "total_return": list(total_return),
            "trades": list(trades_count),
        }
    )
    results.to_parquet(OUT / "b2_sweep_all_trials.parquet", index=False)
    meta = {
        "probe": "T-006-06 vectorbt B2 MA-crossover sweep",
        "engine": f"vectorbt {vbt.__version__}",
        "dataset": "DS-CRYPTO-SPOT-BAKEOFF-V1 BTCUSDT_5m (577,803 bars)",
        "fees_per_side": FEES,
        "combos": len(combos),
        "elapsed_seconds": round(elapsed, 3),
        "bars_x_combos_per_second": round(len(close) * len(combos) / elapsed),
        "all_trials_retained": True,
        "ran_utc": datetime.now(tz=UTC).isoformat(),
        "note": "throughput probe; profitability is NOT a selection criterion here",
    }
    (OUT / "b2_sweep_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
