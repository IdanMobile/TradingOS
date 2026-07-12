#!/usr/bin/env python3
"""Market-character profile of the frozen dataset — the view a desk wants first.

Operator request (2026-07-12): show volatility, volume/liquidity, VWAP behaviour,
and buy/sell pressure for what we actually hold, per coin and timeframe. These are
descriptive statistics of the market we trade against, not a strategy.

Everything here is DERIVED from fields already in DS-CRYPTO-SPOT-BAKEOFF-V1
(OHLC + volume_base + quote_volume + trade_count + taker_buy_*). No new data, no
network. Float math is fine for descriptive stats (not money accounting).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from math import log, sqrt
from pathlib import Path
from statistics import median, pstdev

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "normalized"
OUT = ROOT / "artifacts" / "research_lab" / "data_profile"
INSTRUMENTS = ("BTCUSDT", "ETHUSDT")
TIMEFRAMES = ("5m", "15m", "1h")
BARS_PER_YEAR = {"5m": 288 * 365, "15m": 96 * 365, "1h": 24 * 365}


@dataclass(frozen=True)
class Profile:
    instrument: str
    timeframe: str
    bars: int
    span_start: str
    span_end: str
    annualized_vol_pct: float
    avg_atr_pct: float  # mean true-range / close, a per-bar volatility feel
    avg_daily_usd_volume_musd: float  # average USD traded per day, in $millions
    median_trades_per_bar: int
    avg_buy_pressure_pct: float  # % of volume that was aggressive (taker) buying
    buy_pressure_stdev_pct: float
    price_max_drawdown_pct: float  # worst peak-to-trough of buy-and-hold


def _profile(instrument: str, timeframe: str) -> Profile:
    t = pq.read_table(
        DATA / f"{instrument}_{timeframe}.parquet",
        columns=[
            "timestamp_open_utc",
            "open",
            "high",
            "low",
            "close",
            "volume_base",
            "quote_volume",
            "trade_count",
            "taker_buy_base_volume",
        ],
    )
    close = [float(v.as_py()) for v in t.column("close")]
    high = [float(v.as_py()) for v in t.column("high")]
    low = [float(v.as_py()) for v in t.column("low")]
    qvol = [float(v.as_py()) for v in t.column("quote_volume")]
    vol = [float(v.as_py()) for v in t.column("volume_base")]
    tbuy = [float(v.as_py()) for v in t.column("taker_buy_base_volume")]
    trades = [int(v.as_py()) for v in t.column("trade_count")]
    times = t.column("timestamp_open_utc")

    log_returns = [log(close[i] / close[i - 1]) for i in range(1, len(close)) if close[i - 1] > 0]
    ann_vol = pstdev(log_returns) * sqrt(BARS_PER_YEAR[timeframe]) * 100 if log_returns else 0.0

    true_ranges = []
    for i in range(1, len(close)):
        tr = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        if close[i] > 0:
            true_ranges.append(tr / close[i])
    avg_atr_pct = (sum(true_ranges) / len(true_ranges) * 100) if true_ranges else 0.0

    bars_per_day = BARS_PER_YEAR[timeframe] / 365
    avg_daily_usd = (sum(qvol) / len(qvol)) * bars_per_day / 1_000_000 if qvol else 0.0

    buy_ratios = [tbuy[i] / vol[i] * 100 for i in range(len(vol)) if vol[i] > 0]
    avg_buy = sum(buy_ratios) / len(buy_ratios) if buy_ratios else 0.0
    buy_std = pstdev(buy_ratios) if len(buy_ratios) > 1 else 0.0

    peak = close[0]
    max_dd = 0.0
    for price in close:
        peak = max(peak, price)
        max_dd = min(max_dd, price / peak - 1)

    return Profile(
        instrument=instrument,
        timeframe=timeframe,
        bars=len(close),
        span_start=str(times[0].as_py()),
        span_end=str(times[-1].as_py()),
        annualized_vol_pct=round(ann_vol, 1),
        avg_atr_pct=round(avg_atr_pct, 3),
        avg_daily_usd_volume_musd=round(avg_daily_usd, 1),
        median_trades_per_bar=int(median(trades)),
        avg_buy_pressure_pct=round(avg_buy, 2),
        buy_pressure_stdev_pct=round(buy_std, 2),
        price_max_drawdown_pct=round(max_dd * 100, 1),
    )


def build_report() -> dict:
    profiles = [_profile(i, tf) for i in INSTRUMENTS for tf in TIMEFRAMES]
    return {
        "schema": "tios-data-profile-v1",
        "dataset_id": "DS-CRYPTO-SPOT-BAKEOFF-V1",
        "note": "Descriptive market character, derived from existing OHLCV + order-flow "
        "fields. Not a strategy. Market cap, order book, funding, on-chain and sentiment "
        "are NOT in this dataset.",
        "profiles": [asdict(p) for p in profiles],
    }


def _print(report: dict) -> None:
    print(f"\nData profile — {report['dataset_id']}")
    print(
        f"  {'pair/tf':<14}{'ann.vol':>9}{'ATR%':>7}{'$vol/day':>11}"
        f"{'trades/bar':>12}{'buy-press':>11}{'maxDD':>8}"
    )
    for p in report["profiles"]:
        print(
            f"  {p['instrument'] + ' ' + p['timeframe']:<14}"
            f"{str(p['annualized_vol_pct']) + '%':>9}{p['avg_atr_pct']:>7}"
            f"{'$' + str(p['avg_daily_usd_volume_musd']) + 'M':>11}"
            f"{p['median_trades_per_bar']:>12}"
            f"{str(p['avg_buy_pressure_pct']) + '%':>11}{str(p['price_max_drawdown_pct']) + '%':>8}"
        )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (OUT / "DATA_PROFILE.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _print(report)
    print(f"\n  artifact: {(OUT / 'DATA_PROFILE.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
