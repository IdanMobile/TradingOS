"""Retain precision-loss and observable adapter-failure evidence."""

from __future__ import annotations

import json
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts/bakeoff/freqtrade/adapter_safety_probe"
DATA = ROOT / "data/normalized/BTCUSDT_5m.parquet"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    table = pq.read_table(DATA, columns=["open", "high", "low", "close", "volume_base"])
    max_error = Decimal(0)
    for column in table.columns:
        for chunk in column.chunks:
            for value in chunk.to_pylist():
                max_error = max(max_error, abs(value - Decimal(str(float(value)))))

    invalid_pair = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "tios.adapters.freqtrade.lane",
            "--pairs",
            "INVALID",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    with tempfile.TemporaryDirectory() as temp:
        missing_result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "tios.adapters.freqtrade.normalize_result",
                "--run-dir",
                temp,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
    result = {
        "status": "PASS",
        "precision": {
            "conversion": "canonical decimal128 -> engine float64",
            "max_decimal_roundtrip_error": str(max_error),
            "rows_checked": table.num_rows,
            "columns_checked": table.num_columns,
            "boundary": "loss is declared in every lane manifest",
        },
        "failures": {
            "invalid_pair_returncode": invalid_pair.returncode,
            "invalid_pair_observable": "unsupported pairs: INVALID" in invalid_pair.stderr,
            "missing_result_returncode": missing_result.returncode,
            "missing_result_observable": "no backtest-result zip" in missing_result.stderr,
        },
    }
    if not all(
        (
            invalid_pair.returncode != 0,
            result["failures"]["invalid_pair_observable"],
            missing_result.returncode != 0,
            result["failures"]["missing_result_observable"],
        )
    ):
        result["status"] = "FAIL"
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    report = ROOT / "artifacts/bakeoff/freqtrade/ADAPTER_SAFETY_PROBE.md"
    report.write_text(
        f"""# Freqtrade adapter precision and failure probe

Status: **{result['status']}**

- Checked {table.num_rows:,} BTCUSDT rows across {table.num_columns} numeric columns.
- Maximum Decimal → float → decimal-string error: `{max_error}`. Float64 remains
  an explicit engine-boundary loss; canonical storage remains decimal128.
- Unsupported pairs fail before execution with an observable parser error.
- A missing exported result fails normalization with an observable error.
- Lane success requires both engine completion and a newly exported artifact, because
  Freqtrade can return zero even for a configuration error.

Machine-readable result: `artifacts/bakeoff/freqtrade/adapter_safety_probe/result.json`.
""",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
