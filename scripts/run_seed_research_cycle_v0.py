#!/usr/bin/env python3
"""Run an offline seed-strategy evidence cycle for reproduced seed specs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from itertools import product
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "normalized" / "BTCUSDT_5m.parquet"
FROZEN_MANIFEST = ROOT / "artifacts" / "datasets" / "DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"
QUALITY_REPORT = ROOT / "artifacts" / "datasets" / "QUALITY_REPORT.json"
OUTPUT_ROOT = ROOT / "artifacts" / "research_lab" / "seed_cycle_v0"
FEES = Decimal("0.001")
INITIAL_CASH = Decimal("1000")
QC1_FAST = (3, 5, 8, 10)
QC1_SLOW = (20, 30, 50)
QC2_WINDOW = (10, 20, 40, 80)


@dataclass(frozen=True)
class Trial:
    candidate_id: str
    trial_key: str
    status: str
    total_return: str
    final_equity: str
    trades: int
    failure_reason: str | None = None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_candles(path: Path = DATASET) -> dict[str, list[Decimal]]:
    table = pq.read_table(path, columns=["open", "high", "low", "close"])
    return {
        name: [Decimal(str(value.as_py())) for value in table.column(name)]
        for name in ("open", "high", "low", "close")
    }


def rolling_mean(values: list[Decimal], window: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    total = Decimal("0")
    for index, value in enumerate(values):
        total += value
        if index >= window:
            total -= values[index - window]
        if index + 1 >= window:
            result[index] = total / Decimal(window)
    return result


def simulate_next_open(
    opens: list[Decimal], entries: list[bool], exits: list[bool]
) -> tuple[Decimal, int]:
    cash = INITIAL_CASH
    quantity = Decimal("0")
    trades = 0
    for signal_index in range(len(opens) - 1):
        price = opens[signal_index + 1]
        if quantity == 0 and entries[signal_index]:
            quantity = (cash * (Decimal("1") - FEES)) / price
            cash = Decimal("0")
            trades += 1
        elif quantity > 0 and exits[signal_index]:
            cash = quantity * price * (Decimal("1") - FEES)
            quantity = Decimal("0")
            trades += 1
    final_equity = cash if quantity == 0 else quantity * opens[-1] * (Decimal("1") - FEES)
    return final_equity, trades


def qc1_trials(candles: dict[str, list[Decimal]]) -> list[Trial]:
    close, opens = candles["close"], candles["open"]
    rows: list[Trial] = []
    for fast, slow in product(QC1_FAST, QC1_SLOW):
        if fast >= slow:
            continue
        key = f"fast={fast},slow={slow}"
        fast_ma = rolling_mean(close, fast)
        slow_ma = rolling_mean(close, slow)
        entries = [
            f is not None and s is not None and f > s for f, s in zip(fast_ma, slow_ma, strict=True)
        ]
        exits = [
            f is not None and s is not None and f < s for f, s in zip(fast_ma, slow_ma, strict=True)
        ]
        equity, trades = simulate_next_open(opens, entries, exits)
        rows.append(
            Trial(
                candidate_id="STRAT-QC1-dual-ma-cross",
                trial_key=key,
                status="COMPLETED",
                total_return=str((equity / INITIAL_CASH) - Decimal("1")),
                final_equity=str(equity),
                trades=trades,
            )
        )
    return rows


def qc2_trials(candles: dict[str, list[Decimal]]) -> list[Trial]:
    close, opens, high, low = candles["close"], candles["open"], candles["high"], candles["low"]
    rows: list[Trial] = []
    for window in QC2_WINDOW:
        key = f"window={window}"
        entries: list[bool] = []
        exits: list[bool] = []
        for index, price in enumerate(close):
            if index < window:
                entries.append(False)
                exits.append(False)
                continue
            prior_high = max(high[index - window : index])
            prior_low = min(low[index - window : index])
            entries.append(price > prior_high)
            exits.append(price < prior_low)
        equity, trades = simulate_next_open(opens, entries, exits)
        rows.append(
            Trial(
                candidate_id="STRAT-QC2-donchian-breakout",
                trial_key=key,
                status="COMPLETED",
                total_return=str((equity / INITIAL_CASH) - Decimal("1")),
                final_equity=str(equity),
                trades=trades,
            )
        )
    return rows


def write_trials(path: Path, rows: list[Trial]) -> None:
    table = pa.Table.from_pylist([row.__dict__ for row in rows])
    pq.write_table(table, path)


def build_hashes() -> dict[str, str]:
    return {
        "dataset": sha256(DATASET),
        "frozen_manifest": sha256(FROZEN_MANIFEST),
        "quality_report": sha256(QUALITY_REPORT),
        "runner": sha256(Path(__file__)),
        "config": canonical_hash(
            {
                "fees": str(FEES),
                "initial_cash": str(INITIAL_CASH),
                "qc1_fast": QC1_FAST,
                "qc1_slow": QC1_SLOW,
                "qc2_window": QC2_WINDOW,
            }
        ),
    }


def run_cycle() -> dict[str, Any]:
    hashes = build_hashes()
    cycle_id = "SEEDCYCLE-" + canonical_hash(hashes)
    out = OUTPUT_ROOT / cycle_id
    result_path = out / "cycle_run.json"
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["reused"] = True
        return result
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now(tz=UTC).isoformat()
    candles = load_candles()
    qc1 = qc1_trials(candles)
    qc2 = qc2_trials(candles)
    write_trials(out / "qc1_trials.parquet", qc1)
    write_trials(out / "qc2_trials.parquet", qc2)
    evidence = [
        {
            "candidate_id": candidate,
            "validation_status": "UNVALIDATED",
            "approval_status": "NOT_ELIGIBLE",
            "execution_authority": "NONE",
        }
        for candidate in ("STRAT-QC1-dual-ma-cross", "STRAT-QC2-donchian-breakout")
    ]
    (out / "evidence.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in evidence),
        encoding="utf-8",
    )
    scorecards = {
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "winner_selected": False,
        "candidates": {
            "STRAT-QC1-dual-ma-cross": {
                "trials": len(qc1),
                "best_total_return": max(row.total_return for row in qc1),
            },
            "STRAT-QC2-donchian-breakout": {
                "trials": len(qc2),
                "best_total_return": max(row.total_return for row in qc2),
            },
        },
        "blockers": [
            "no temporal validation package exists for these seed candidates",
            "no cross-engine reproduction exists for these seed candidates",
            "no multiple-testing production estimator is activated",
            "no candidate is promotion eligible",
        ],
    }
    (out / "scorecards.json").write_text(
        json.dumps(scorecards, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    finished = datetime.now(tz=UTC).isoformat()
    artifacts = {
        path.name: sha256(path)
        for path in sorted(out.iterdir())
        if path.name not in {"cycle_run.json", "manifest.json"}
    }
    manifest = {
        "schema": "tios-seed-cycle-v0-manifest",
        "cycle_id": cycle_id,
        "status": "COMPLETED",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "winner_selected": False,
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "hashes": hashes,
        "artifacts": artifacts,
        "started_at_utc": started,
        "finished_at_utc": finished,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result = {
        **manifest,
        "schema": "tios-seed-cycle-v0-run",
        "reused": False,
        "counts": {"candidates": 2, "trials": len(qc1) + len(qc2), "evidence_records": 2},
        "artifact_manifest_sha256": sha256(out / "manifest.json"),
        "content_sha256": canonical_hash({"manifest": manifest, "scorecards": scorecards}),
    }
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    result = run_cycle()
    print(json.dumps({"cycle_id": result["cycle_id"], "reused": result["reused"]}, indent=2))


if __name__ == "__main__":
    main()
