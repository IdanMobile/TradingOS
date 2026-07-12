#!/usr/bin/env python3
"""Run all strategies across the expanded multi-pair universe (DS-CRYPTO-MULTI-V1).

The public-20 and signal-5 searches only ever saw BTC/ETH. This runs the SAME 25
strategies and the SAME honest screen across every normalized_multi pair/timeframe
we now hold (1h/4h/1d — the low timeframes just churn fees, per D-040). More pairs =
more shots on goal; the screen and (later) G10 stay exactly as strict.

Research only: nothing validated, no venue, no orders, execution_authority=NONE.

ponytail: reuses the strategy rosters + screen helpers from the two existing searches;
adds only the multi-pair parquet loader and the universe loop.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.run_external_strategy_search as ext  # noqa: E402
import scripts.run_signal_strategy_search as sig  # noqa: E402

MULTI = ROOT / "data" / "normalized_multi"
OUT = ROOT / "artifacts" / "research_lab" / "universe_search"
TIMEFRAMES = ("1h", "4h", "1d")  # tradeable frequencies; skip fee-churning 5m/15m
# Require near-complete history per timeframe (~70%+ of full 2021-2026 coverage) so
# partial / still-downloading series (e.g. a 1-month listing pump) can't contaminate.
MIN_BARS = {"1h": 33000, "4h": 8000, "1d": 1400}
ALL_STRATEGIES = (*ext.STRATEGIES, *sig.STRATEGIES)  # 20 public + 5 signal


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
        trials = [ext._run_variant(candles, b, k) for k, b in variants.items()]
        best = max(trials, key=lambda t: t.total_return)
        pos_frac = Decimal(sum(1 for t in trials if t.total_return > 0)) / Decimal(len(trials))
        bh = ext._buy_hold(candles)
        thirds_ok, thirds = ext._thirds_all_positive(
            candles, variants[best.trial_key], best.trial_key
        )
        screen_pass = bool(
            best.total_return > 0
            and best.total_return > bh
            and thirds_ok
            and pos_frac >= ext.MIN_NEIGHBOURHOOD_POSITIVE
            and best.trades >= ext.MIN_TRADES
        )
        row = {
            "dataset": name,
            "best_trial_key": best.trial_key,
            "best_return_pct": round(float(best.total_return) * 100, 1),
            "buy_hold_pct": round(float(bh) * 100, 1),
            "trades": best.trades,
            "thirds_all_positive": thirds_ok,
            "thirds": thirds,
            "screen_pass": screen_pass,
        }
        if (
            best_overall is None
            or best.total_return > Decimal(str(best_overall["best_return_pct"])) / 100
        ):
            best_overall = row
        if screen_pass:
            passes.append(row)
    return {
        "strategy_id": strategy.strategy_id,  # type: ignore[attr-defined]
        "screen_pass_contexts": passes,
        "best_context": best_overall,
    }


def build_report() -> dict:
    datasets = _datasets()
    results = [evaluate(s, datasets) for s in ALL_STRATEGIES]
    survivors = [
        {"strategy_id": r["strategy_id"], "contexts": r["screen_pass_contexts"]}
        for r in results
        if r["screen_pass_contexts"]
    ]
    return {
        "schema": "tios-universe-search-v1",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "dataset_count": len(datasets),
        "pairs": sorted({d[0].rsplit("_", 1)[0] for d in datasets}),
        "timeframes": list(TIMEFRAMES),
        "strategy_count": len(ALL_STRATEGIES),
        "survivor_count": len(survivors),
        "survivors": survivors,
        "strategies": results,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (OUT / "UNIVERSE_SEARCH.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "datasets": report["dataset_count"],
                "pairs": len(report["pairs"]),
                "strategies": report["strategy_count"],
                "survivors": report["survivor_count"],
                "survivor_ids": [s["strategy_id"] for s in report["survivors"]],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
