#!/usr/bin/env python3
"""Run all strategies across the expanded multi-pair universe (DS-CRYPTO-MULTI-V1).

The public-20 and signal-5 searches only ever saw BTC/ETH. This runs the SAME 25
strategies and the SAME honest screen across every normalized_multi pair/timeframe
we now hold (1h/4h/1d — the low timeframes just churn fees, per D-040). More pairs =
more shots on goal; the screen and (later) G10 stay exactly as strict.

Research only: nothing validated, no venue, no orders, execution_authority=NONE.

Single-run only: like the demo lanes, this holds its own advisory flock and exits 3 if a
search is already in flight, so two runs can never clobber the same output JSON.

ponytail: reuses the strategy rosters + screen helpers from the two existing searches;
adds only the multi-pair parquet loader and the universe loop.
"""

from __future__ import annotations

import fcntl
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.run_external_strategy_search as ext  # noqa: E402
import scripts.run_signal_strategy_search as sig  # noqa: E402

MULTI = ROOT / "data" / "normalized_multi"
OUT = ROOT / "artifacts" / "research_lab" / "universe_search"
# Same file the dashboard's START_RESEARCH guard reads for a fast "already running" 409; the flock
# below (not that PID probe) is what actually guarantees a single search.
RUN_LOCK = OUT / ".research_run.lock"
REPORT = OUT / "UNIVERSE_SEARCH_TRAIN_SELECT_V2_2026_07_13.json"
TIMEFRAMES = ("1h", "4h", "1d")  # tradeable frequencies; skip fee-churning 5m/15m
# Require near-complete history per timeframe (~70%+ of full 2021-2026 coverage) so
# partial / still-downloading series (e.g. a 1-month listing pump) can't contaminate.
MIN_BARS = {"1h": 33000, "4h": 8000, "1d": 1400}
ALL_STRATEGIES = (*ext.STRATEGIES, *sig.STRATEGIES)  # 32 public + 5 signal


@contextmanager
def exclusive_search_lock() -> Iterator[bool]:
    """Hold the single-search lock for this process's lifetime (mirrors demo_eth_lane's lane lock).

    Two concurrent searches would clobber the same output JSON, so only one may run. Yields False
    if another search already holds it — and then writes nothing, so a live run's lock record and
    report survive untouched. The lock releases when the process exits, so a crashed search never
    wedges the next start.
    """
    OUT.mkdir(parents=True, exist_ok=True)
    handle = RUN_LOCK.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps({"pid": os.getpid(), "started_at": datetime.now(UTC).isoformat()}))
        handle.flush()
        os.fsync(handle.fileno())
        yield True
    finally:
        handle.close()


def _load(path: Path) -> ext.Candles:
    cols = ["open", "high", "low", "close", "volume_base", "quote_volume", "taker_buy_base_volume"]
    t = pq.read_table(path, columns=cols)
    out = {c: [Decimal(str(v.as_py())) for v in t.column(c)] for c in cols}
    out["volume"] = out.pop("volume_base")
    out["taker_buy"] = out.pop("taker_buy_base_volume")
    return out


def _datasets() -> list[tuple[str, ext.Candles]]:
    found = []
    for path in sorted(MULTI.glob("*.parquet")):
        tf = path.stem.rsplit("_", 1)[1]
        if tf not in TIMEFRAMES:
            continue
        candles = _load(path)
        if len(candles["open"]) >= MIN_BARS[tf]:
            found.append((path.stem, candles))
    return found


def evaluate(strategy: object, datasets: list[tuple[str, ext.Candles]]) -> dict:
    variants = strategy.variants  # type: ignore[attr-defined]
    passes = []
    best_overall = None
    for name, candles in datasets:
        row = {
            "dataset": name,
            **ext._temporal_screen(candles, variants),
        }
        row["best_return_pct"] = round(float(row["train_total_return"]) * 100, 1)
        row["buy_hold_pct"] = round(float(row["holdout_buy_hold_return"]) * 100, 1)
        row["trades"] = row["total_trades"]
        if best_overall is None or Decimal(row["train_total_return"]) > Decimal(
            best_overall["train_total_return"]
        ):
            best_overall = row
        if row["screen_pass"]:
            passes.append(row)
    return {
        "strategy_id": strategy.strategy_id,  # type: ignore[attr-defined]
        "screen_pass_contexts": passes,
        "best_context": best_overall,
    }


def build_report() -> dict:
    datasets = _datasets()
    results = [evaluate(s, datasets) for s in ALL_STRATEGIES]
    context_passes = [
        {"strategy_id": r["strategy_id"], "contexts": r["screen_pass_contexts"]}
        for r in results
        if r["screen_pass_contexts"]
    ]
    return {
        "schema": "tios-universe-search-v2",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "promotion_status": "METHOD_BLOCKED",
        "search_lineage_complete": False,
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "winner_selected": False,
        "screen": {
            "method_id": "train-select-validation-freeze-single-holdout-v1",
            "scope": "context-level exploratory screen; not globally frozen-candidate validation",
            "split_rule": "chronological contiguous thirds",
            "candidate_roster_selection": "predeclared before evaluation; no winner selected",
            "parameter_selection_partition": "train",
            "best_context_ranking_partition": "train",
            "validation_used_for_selection": False,
            "holdout_used_for_selection": False,
            "holdout_evaluations_per_context": 1,
            "global_candidate_frozen": False,
            "promotion_eligible": False,
        },
        "dataset_count": len(datasets),
        "pairs": sorted({d[0].rsplit("_", 1)[0] for d in datasets}),
        "timeframes": list(TIMEFRAMES),
        "strategy_count": len(ALL_STRATEGIES),
        "context_pass_count": len(context_passes),
        "context_passes": context_passes,
        "strategies": results,
    }


def main() -> int:
    with exclusive_search_lock() as acquired:
        if not acquired:
            print("another research search is already running — refusing to start a second one.")
            return 3
        report = build_report()
        REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "datasets": report["dataset_count"],
                    "pairs": len(report["pairs"]),
                    "strategies": report["strategy_count"],
                    "context_passes": report["context_pass_count"],
                    "context_pass_ids": [s["strategy_id"] for s in report["context_passes"]],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
