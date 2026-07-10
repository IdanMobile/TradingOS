"""Signal-timestamp parity probe (T-006-02): compares Freqtrade's generated B1-B4 strategies
against the hand-derived fixtures/micro/ goldens, bar-by-bar. Stdlib only in this process —
the actual freqtrade strategy code runs isolated in engines/freqtrade/.venv via
signal_parity_worker.py (subprocess/CLI only, AD-02 GPL boundary).

Tolerance: exact per-bar boolean match (no tolerance defined in fixtures/strategies/baselines/
*.yaml or fixtures/micro/GOLDEN_DERIVATION.md), i.e. 0 mismatched bars.

Run: python3 engines/freqtrade/probes/signal_parity_probe.py
"""

from __future__ import annotations

import csv
import io
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VENV_PY = ROOT / "engines" / "freqtrade" / ".venv" / "bin" / "python"
WORKER = Path(__file__).resolve().parent / "signal_parity_worker.py"
FIXTURES = ROOT / "fixtures" / "micro"
OUT_DIR = ROOT / "artifacts" / "bakeoff" / "freqtrade" / "signal_parity"
BASELINES = ("B1", "B2", "B3", "B4")


def read_csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def to_bool(s: str) -> bool:
    return s.strip().lower() == "true"


def run_probe() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for baseline in BASELINES:
        proc = subprocess.run(
            [str(VENV_PY), str(WORKER), baseline],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=120,
        )
        if proc.returncode != 0:
            results[baseline] = {"status": "ERROR", "stderr": proc.stderr[-2000:]}
            continue
        produced_text = proc.stdout
        (OUT_DIR / f"produced_{baseline}.csv").write_text(produced_text)
        produced = read_csv_rows(produced_text)
        golden = read_csv_rows((FIXTURES / f"expected_signals_{baseline}.csv").read_text())

        mismatches = []
        for p, g in zip(produced, golden, strict=True):
            assert p["bar"] == g["bar"]
            if to_bool(p["entry"]) != to_bool(g["entry"]) or to_bool(p["exit"]) != to_bool(
                g["exit"]
            ):
                mismatches.append(
                    {
                        "bar": p["bar"],
                        "produced": {"entry": p["entry"], "exit": p["exit"]},
                        "expected": {"entry": g["entry"], "exit": g["exit"]},
                    }
                )
        results[baseline] = {
            "status": "PASS" if not mismatches else "FAIL",
            "bars_compared": len(produced),
            "mismatches": mismatches,
        }
    return results


def write_report(results: dict) -> Path:
    overall = "PASS" if all(r["status"] == "PASS" for r in results.values()) else "FAIL"
    lines = [
        "# Freqtrade signal-timestamp parity probe vs fixtures/micro/ goldens (T-006-02)",
        "",
        f"Overall: **{overall}** · Tolerance: exact per-bar boolean match (0 bars),"
        " per fixtures/micro/GOLDEN_DERIVATION.md (no tolerance is defined there or in"
        " fixtures/strategies/baselines/*.yaml).",
        "",
        "Method: the generated freqtrade strategy classes"
        " (engines/freqtrade/lane/user_data/strategies/) are applied directly to"
        " fixtures/micro/bars.csv (16 bars) via populate_indicators/populate_entry_trend/"
        "populate_exit_trend, run inside engines/freqtrade/.venv"
        " (signal_parity_worker.py, subprocess-isolated per AD-02). Output compared"
        " bar-by-bar against expected_signals_B{1-4}.csv.",
        "",
        "| Baseline | Status | Bars compared | Mismatches |",
        "|---|---|---|---|",
    ]
    for b, r in results.items():
        if r["status"] == "ERROR":
            lines.append(f"| {b} | ERROR | - | worker subprocess failed, see stderr below |")
        else:
            lines.append(f"| {b} | {r['status']} | {r['bars_compared']} | {len(r['mismatches'])} |")
    lines.append("")
    for b, r in results.items():
        if r["status"] == "ERROR":
            lines.append(f"## {b} worker error\n```\n{r['stderr']}\n```\n")
        elif r["mismatches"]:
            mismatches_json = json.dumps(r["mismatches"], indent=2)
            lines.append(f"## {b} mismatches\n```json\n{mismatches_json}\n```\n")
    report_path = ROOT / "artifacts" / "bakeoff" / "freqtrade" / "SIGNAL_PARITY_MICRO.md"
    report_path.write_text("\n".join(lines) + "\n")
    return report_path


if __name__ == "__main__":
    results = run_probe()
    report_path = write_report(results)
    (OUT_DIR / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"report: {report_path}")
    for b, r in results.items():
        print(f"{b}: {r['status']}")
