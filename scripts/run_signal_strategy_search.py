#!/usr/bin/env python3
"""Search strategies that USE the signals price-only backtests ignore.

Operator request (2026-07-12): our OHLC strategies never looked at volume,
volatility, or order flow — all of which we already have. This adds strategy
families built on those fields and runs them through the SAME honest screen as the
public-strategy search (positive holdout + beats buy-and-hold + neighbourhood
robust + >=10 trades). Genuinely new shots on goal, same standards, no shortcuts.

Research only: nothing validated, no venue, no orders, execution_authority=NONE.

ponytail: reuses the screen helpers from run_external_strategy_search; adds only a
richer loader (volume/quote_volume/taker-buy) and the signal builders.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.run_external_strategy_search as ext  # noqa: E402

OUT = ROOT / "artifacts" / "research_lab" / "signal_strategy_search"
DATA = ROOT / "data" / "normalized"

Candles = ext.Candles
SignalBuilder = ext.SignalBuilder


def load_rich(instrument: str, timeframe: str) -> Candles:
    """OHLC plus the order-flow / volume fields, as aligned Decimal lists."""
    cols = ["open", "high", "low", "close", "volume_base", "quote_volume", "taker_buy_base_volume"]
    t = pq.read_table(DATA / f"{instrument}_{timeframe}.parquet", columns=cols)
    out = {c: [Decimal(str(v.as_py())) for v in t.column(c)] for c in cols}
    out["volume"] = out.pop("volume_base")
    out["taker_buy"] = out.pop("taker_buy_base_volume")
    return out


def _rolling_sum(values: list[Decimal], window: int) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(values)
    total = Decimal("0")
    for i, v in enumerate(values):
        total += v
        if i >= window:
            total -= values[i - window]
        if i + 1 >= window:
            out[i] = total
    return out


def _rolling_vwap(c: Candles, window: int) -> list[Decimal | None]:
    q = _rolling_sum(c["quote_volume"], window)
    v = _rolling_sum(c["volume"], window)
    return [
        None if qq is None or vv is None or vv == 0 else qq / vv
        for qq, vv in zip(q, v, strict=True)
    ]


def _rolling_taker_ratio(c: Candles, window: int) -> list[Decimal | None]:
    tb = _rolling_sum(c["taker_buy"], window)
    v = _rolling_sum(c["volume"], window)
    return [
        None if t is None or vv is None or vv == 0 else t / vv for t, vv in zip(tb, v, strict=True)
    ]


def _atr_pct(c: Candles, window: int) -> list[Decimal | None]:
    high, low, close = c["high"], c["low"], c["close"]
    tr = [Decimal("0")] * len(close)
    for i in range(1, len(close)):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    sums = _rolling_sum(tr, window)
    return [
        None if s is None or close[i] == 0 else (s / window) / close[i] for i, s in enumerate(sums)
    ]


# --- signal strategies ------------------------------------------------------ #
def vwap_reversion(window: int) -> SignalBuilder:
    """Buy when price dips below its rolling VWAP, exit when it recovers above."""

    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        vwap = _rolling_vwap(c, window)
        close = c["close"]
        entries = [w is not None and p < w for p, w in zip(close, vwap, strict=True)]
        exits = [w is not None and p > w for p, w in zip(close, vwap, strict=True)]
        return entries, exits

    return build


def vwap_trend(window: int) -> SignalBuilder:
    """Hold while price is above its rolling VWAP (institutional trend proxy)."""

    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        vwap = _rolling_vwap(c, window)
        close = c["close"]
        entries = [w is not None and p > w for p, w in zip(close, vwap, strict=True)]
        exits = [w is not None and p < w for p, w in zip(close, vwap, strict=True)]
        return entries, exits

    return build


def volume_breakout(window: int, mult: Decimal) -> SignalBuilder:
    """Donchian breakout only when this bar's volume exceeds mult x its average."""

    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        close, high, low, volume = c["close"], c["high"], c["low"], c["volume"]
        vol_sum = _rolling_sum(volume, window)
        n = len(close)
        entries = [False] * n
        exits = [False] * n
        for i in range(window, n):
            avg_vol = vol_sum[i]
            if avg_vol is None:
                continue
            avg_vol = avg_vol / window
            entries[i] = close[i] > max(high[i - window : i]) and volume[i] > avg_vol * mult
            exits[i] = close[i] < min(low[i - window : i])
        return entries, exits

    return build


def flow_momentum(window: int, buy_ratio: Decimal, exit_ratio: Decimal) -> SignalBuilder:
    """Buy when aggressive-buy share of volume is high, exit when it fades."""

    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        ratio = _rolling_taker_ratio(c, window)
        entries = [r is not None and r > buy_ratio for r in ratio]
        exits = [r is not None and r < exit_ratio for r in ratio]
        return entries, exits

    return build


def vol_regime_trend(fast: int, slow: int, atr_window: int, atr_floor: Decimal) -> SignalBuilder:
    """SMA-cross trend, but only take entries when volatility is elevated."""

    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        close = c["close"]
        f = ext._sma(close, fast)
        s = ext._sma(close, slow)
        atr = _atr_pct(c, atr_window)
        entries = [
            a is not None and b is not None and v is not None and a > b and v > atr_floor
            for a, b, v in zip(f, s, atr, strict=True)
        ]
        exits = [a is not None and b is not None and a < b for a, b in zip(f, s, strict=True)]
        return entries, exits

    return build


def _grid(factory, grid: list[dict]) -> dict:
    return {",".join(f"{k}={v}" for k, v in p.items()): factory(**p) for p in grid}


@dataclass(frozen=True)
class Strategy:
    strategy_id: str
    source: str
    variants: dict


STRATEGIES: tuple[Strategy, ...] = (
    Strategy(
        "SIG-VWAP-REVERSION",
        "rolling-VWAP mean reversion (order-flow-derived)",
        _grid(vwap_reversion, [{"window": 24}, {"window": 48}, {"window": 96}]),
    ),
    Strategy(
        "SIG-VWAP-TREND",
        "rolling-VWAP trend follow (order-flow-derived)",
        _grid(vwap_trend, [{"window": 24}, {"window": 48}, {"window": 96}]),
    ),
    Strategy(
        "SIG-VOLUME-BREAKOUT",
        "volume-confirmed Donchian breakout",
        _grid(
            volume_breakout,
            [
                {"window": 20, "mult": Decimal("1.5")},
                {"window": 40, "mult": Decimal("1.5")},
                {"window": 20, "mult": Decimal("2")},
            ],
        ),
    ),
    Strategy(
        "SIG-FLOW-MOMENTUM",
        "taker buy/sell order-flow imbalance momentum",
        _grid(
            flow_momentum,
            [
                {"window": 24, "buy_ratio": Decimal("0.52"), "exit_ratio": Decimal("0.48")},
                {"window": 48, "buy_ratio": Decimal("0.52"), "exit_ratio": Decimal("0.48")},
                {"window": 24, "buy_ratio": Decimal("0.55"), "exit_ratio": Decimal("0.45")},
            ],
        ),
    ),
    Strategy(
        "SIG-VOL-REGIME-TREND",
        "SMA trend gated by elevated ATR volatility",
        _grid(
            vol_regime_trend,
            [
                {"fast": 20, "slow": 50, "atr_window": 14, "atr_floor": Decimal("0.005")},
                {"fast": 10, "slow": 30, "atr_window": 14, "atr_floor": Decimal("0.005")},
                {"fast": 20, "slow": 50, "atr_window": 14, "atr_floor": Decimal("0.01")},
            ],
        ),
    ),
)


def evaluate(strategy: Strategy) -> dict:
    contexts: list[dict] = []
    survivors: list[dict] = []
    for instrument in ext.INSTRUMENTS:
        for timeframe in ext.TIMEFRAMES:
            candles = load_rich(instrument, timeframe)
            trials = [ext._run_variant(candles, b, k) for k, b in strategy.variants.items()]
            best = max(trials, key=lambda t: t.total_return)
            pos_frac = Decimal(sum(1 for t in trials if t.total_return > 0)) / Decimal(len(trials))
            bh = ext._buy_hold(candles)
            builder = strategy.variants[best.trial_key]
            thirds_ok, thirds = ext._thirds_all_positive(candles, builder, best.trial_key)
            screen_pass = bool(
                best.total_return > 0
                and best.total_return > bh
                and thirds_ok
                and pos_frac >= ext.MIN_NEIGHBOURHOOD_POSITIVE
                and best.trades >= ext.MIN_TRADES
            )
            row = {
                "dataset": f"{instrument}_{timeframe}",
                "best_trial_key": best.trial_key,
                "best_total_return": str(best.total_return),
                "best_trades": best.trades,
                "buy_hold_return": str(bh),
                "neighbourhood_positive_fraction": str(pos_frac),
                "thirds_all_positive": thirds_ok,
                "thirds": thirds,
                "screen_pass": screen_pass,
            }
            contexts.append(row)
            if screen_pass:
                survivors.append(row)
    return {
        "strategy_id": strategy.strategy_id,
        "source": strategy.source,
        "approval_status": "NOT_ELIGIBLE",
        "execution_authority": "NONE",
        "screen_pass_contexts": survivors,
        "contexts": contexts,
    }


def build_report() -> dict:
    results = [evaluate(s) for s in STRATEGIES]
    survivors = [
        {"strategy_id": r["strategy_id"], "contexts": r["screen_pass_contexts"]}
        for r in results
        if r["screen_pass_contexts"]
    ]
    return {
        "schema": "tios-signal-strategy-search-v1",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "winner_selected": False,
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "uses_signals": ["rolling_vwap", "volume", "taker_buy_sell_imbalance", "atr_volatility"],
        "strategy_count": len(STRATEGIES),
        "survivor_count": len(survivors),
        "survivors": survivors,
        "strategies": results,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (OUT / "SIGNAL_STRATEGY_SEARCH.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "strategies": report["strategy_count"],
                "survivors": report["survivor_count"],
                "survivor_ids": [s["strategy_id"] for s in report["survivors"]],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
