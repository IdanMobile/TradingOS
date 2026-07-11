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
# D-040: the cycle compares every reproduced candidate across the full frozen grid.
DATASETS = {
    f"{instrument}_{timeframe}": ROOT / "data" / "normalized" / f"{instrument}_{timeframe}.parquet"
    for instrument in ("BTCUSDT", "ETHUSDT")
    for timeframe in ("5m", "15m", "1h")
}
FROZEN_MANIFEST = ROOT / "artifacts" / "datasets" / "DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"
QUALITY_REPORT = ROOT / "artifacts" / "datasets" / "QUALITY_REPORT.json"
OUTPUT_ROOT = ROOT / "artifacts" / "research_lab" / "seed_cycle_v0"
FEES = Decimal("0.001")
INITIAL_CASH = Decimal("1000")
QC1_FAST = (3, 5, 8, 10)
QC1_SLOW = (20, 30, 50)
QC2_WINDOW = (10, 20, 40, 80)
PINE1_WINDOW = (10, 20, 40)
PINE1_STD = (Decimal("1.5"), Decimal("2"), Decimal("2.5"))
FT1_RSI_WINDOW = (7, 14, 21)
FT1_RSI_THRESHOLD = (Decimal("20"), Decimal("30"), Decimal("40"))
FT1_BB_WINDOW = 20
FT1_BB_STD = Decimal("2")
FT2_SHORT = (3, 5, 8)
FT2_LONG = (10, 20, 30)


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


def rolling_bollinger(
    values: list[Decimal], window: int, deviations: Decimal
) -> list[tuple[Decimal, Decimal, Decimal] | None]:
    """Rolling (lower, mid, upper) with population std via incremental sums."""
    result: list[tuple[Decimal, Decimal, Decimal] | None] = [None] * len(values)
    total = Decimal("0")
    total_squares = Decimal("0")
    for index, value in enumerate(values):
        total += value
        total_squares += value * value
        if index >= window:
            leaving = values[index - window]
            total -= leaving
            total_squares -= leaving * leaving
        if index + 1 >= window:
            mid = total / Decimal(window)
            variance = total_squares / Decimal(window) - mid * mid
            std = max(variance, Decimal("0")).sqrt()
            result[index] = (mid - deviations * std, mid, mid + deviations * std)
    return result


def wilder_rsi(values: list[Decimal], window: int) -> list[Decimal | None]:
    """Wilder-smoothed RSI (the talib/freqtrade convention)."""
    result: list[Decimal | None] = [None] * len(values)
    average_gain = Decimal("0")
    average_loss = Decimal("0")
    hundred = Decimal("100")
    for index in range(1, len(values)):
        delta = values[index] - values[index - 1]
        gain = delta if delta > 0 else Decimal("0")
        loss = -delta if delta < 0 else Decimal("0")
        if index <= window:
            average_gain += gain / Decimal(window)
            average_loss += loss / Decimal(window)
            if index < window:
                continue
        else:
            average_gain = (average_gain * (window - 1) + gain) / Decimal(window)
            average_loss = (average_loss * (window - 1) + loss) / Decimal(window)
        if average_loss == 0:
            result[index] = hundred
        else:
            result[index] = hundred - hundred / (1 + average_gain / average_loss)
    return result


def rolling_ema(values: list[Decimal], window: int) -> list[Decimal | None]:
    """True recursive EMA, talib convention: SMA seed, alpha = 2/(window+1)."""
    result: list[Decimal | None] = [None] * len(values)
    alpha = Decimal(2) / Decimal(window + 1)
    total = Decimal("0")
    for index, value in enumerate(values):
        if index + 1 < window:
            total += value
            continue
        if index + 1 == window:
            total += value
            result[index] = total / Decimal(window)
        else:
            previous = result[index - 1]
            assert previous is not None
            result[index] = alpha * value + (1 - alpha) * previous
    return result


def ft2_trials(candles: dict[str, list[Decimal]]) -> list[Trial]:
    """STRAT-FT2-ema-cross: enter ema_short>ema_long, exit ema_short<ema_long."""
    close, opens = candles["close"], candles["open"]
    rows: list[Trial] = []
    for short_window, long_window in product(FT2_SHORT, FT2_LONG):
        if short_window >= long_window:
            continue
        key = f"short={short_window},long={long_window}"
        short_ema = rolling_ema(close, short_window)
        long_ema = rolling_ema(close, long_window)
        entries = [
            fast is not None and slow is not None and fast > slow
            for fast, slow in zip(short_ema, long_ema, strict=True)
        ]
        exits = [
            fast is not None and slow is not None and fast < slow
            for fast, slow in zip(short_ema, long_ema, strict=True)
        ]
        equity, trades = simulate_next_open(opens, entries, exits)
        rows.append(
            Trial(
                candidate_id="STRAT-FT2-ema-cross",
                trial_key=key,
                status="COMPLETED",
                total_return=str((equity / INITIAL_CASH) - Decimal("1")),
                final_equity=str(equity),
                trades=trades,
            )
        )
    return rows


def pine1_trials(candles: dict[str, list[Decimal]]) -> list[Trial]:
    """STRAT-PINE1-bb-strategy: enter close<bb_lower, exit close>bb_upper."""
    close, opens = candles["close"], candles["open"]
    rows: list[Trial] = []
    for window, deviations in product(PINE1_WINDOW, PINE1_STD):
        key = f"window={window},std={deviations}"
        bands = rolling_bollinger(close, window, deviations)
        entries = [b is not None and price < b[0] for price, b in zip(close, bands, strict=True)]
        exits = [b is not None and price > b[2] for price, b in zip(close, bands, strict=True)]
        equity, trades = simulate_next_open(opens, entries, exits)
        rows.append(
            Trial(
                candidate_id="STRAT-PINE1-bb-strategy",
                trial_key=key,
                status="COMPLETED",
                total_return=str((equity / INITIAL_CASH) - Decimal("1")),
                final_equity=str(equity),
                trades=trades,
            )
        )
    return rows


def ft1_trials(candles: dict[str, list[Decimal]]) -> list[Trial]:
    """STRAT-FT1-sample-strategy: enter close<bb_lower and rsi<threshold, exit close>bb_mid."""
    close, opens = candles["close"], candles["open"]
    bands = rolling_bollinger(close, FT1_BB_WINDOW, FT1_BB_STD)
    rows: list[Trial] = []
    for rsi_window, threshold in product(FT1_RSI_WINDOW, FT1_RSI_THRESHOLD):
        key = f"rsi_window={rsi_window},rsi_threshold={threshold}"
        rsi = wilder_rsi(close, rsi_window)
        entries = [
            b is not None and r is not None and price < b[0] and r < threshold
            for price, b, r in zip(close, bands, rsi, strict=True)
        ]
        exits = [b is not None and price > b[1] for price, b in zip(close, bands, strict=True)]
        equity, trades = simulate_next_open(opens, entries, exits)
        rows.append(
            Trial(
                candidate_id="STRAT-FT1-sample-strategy",
                trial_key=key,
                status="COMPLETED",
                total_return=str((equity / INITIAL_CASH) - Decimal("1")),
                final_equity=str(equity),
                trades=trades,
            )
        )
    return rows


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
        **{f"dataset_{name}": sha256(path) for name, path in DATASETS.items()},
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
                "pine1_window": PINE1_WINDOW,
                "pine1_std": [str(value) for value in PINE1_STD],
                "ft1_rsi_window": FT1_RSI_WINDOW,
                "ft1_rsi_threshold": [str(value) for value in FT1_RSI_THRESHOLD],
                "ft1_bb": [FT1_BB_WINDOW, str(FT1_BB_STD)],
                "ft2_short": FT2_SHORT,
                "ft2_long": FT2_LONG,
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
    family_runners = {
        "qc1": ("STRAT-QC1-dual-ma-cross", qc1_trials),
        "qc2": ("STRAT-QC2-donchian-breakout", qc2_trials),
        "pine1": ("STRAT-PINE1-bb-strategy", pine1_trials),
        "ft1": ("STRAT-FT1-sample-strategy", ft1_trials),
        "ft2": ("STRAT-FT2-ema-cross", ft2_trials),
    }
    # families: family name -> (candidate_id, {dataset name -> trials})
    families: dict[str, tuple[str, dict[str, list[Trial]]]] = {}
    for dataset_name, dataset_path in DATASETS.items():
        candles = load_candles(dataset_path)
        for name, (candidate, runner) in family_runners.items():
            trials = runner(candles)
            families.setdefault(name, (candidate, {}))[1][dataset_name] = trials
            write_trials(out / f"{name}_{dataset_name}_trials.parquet", trials)
    evidence = [
        {
            "candidate_id": candidate,
            "validation_status": "UNVALIDATED",
            "approval_status": "NOT_ELIGIBLE",
            "execution_authority": "NONE",
        }
        for candidate, _ in families.values()
    ]
    (out / "evidence.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in evidence),
        encoding="utf-8",
    )
    scorecards = {
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "winner_selected": False,
        "candidates": {
            candidate: {
                "trials": sum(len(rows) for rows in by_dataset.values()),
                "best_total_return": max(
                    row.total_return for rows in by_dataset.values() for row in rows
                ),
                "by_dataset": {
                    dataset_name: {
                        "trials": len(rows),
                        "best_total_return": max(row.total_return for row in rows),
                        "max_trades": max(row.trades for row in rows),
                        "min_trades": min(row.trades for row in rows),
                    }
                    for dataset_name, rows in by_dataset.items()
                },
            }
            for candidate, by_dataset in families.values()
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
        "counts": {
            "candidates": len(families),
            "datasets": len(DATASETS),
            "trials": sum(
                len(rows) for _, by_dataset in families.values() for rows in by_dataset.values()
            ),
            "evidence_records": len(evidence),
        },
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
