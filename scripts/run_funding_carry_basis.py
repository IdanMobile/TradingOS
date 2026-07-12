#!/usr/bin/env python3
"""Funding carry WITH spot-perp basis risk — the honest version + production G10 (DSR).

`run_funding_carry.py` modelled only the funding leg and inflated Sharpe to ~11. This
adds the piece it omitted: the actual spot-vs-perp price divergence (basis). For a
1x-funded delta-neutral position (long spot / short perp), the per-period return is:

    carry = funding + (spot_return - perp_return) - fees

The (spot_return - perp_return) term is the basis P&L — near-zero on average but volatile,
with tail losses when spot and perp diverge in a shock (the risk that killed naive carry
in 2022). 1x funding means no liquidation; leverage would re-add it (noted ceiling).
Counterparty/exchange risk is out of scope (the real 2022 killer — operator risk).

Honest bar: DSR >= 0.95. RESEARCH-ONLY (perps/margin S4-gated); execution_authority=NONE.
Float math for statistics.

ponytail: reads the 8h spot/perp/funding zips, aligns on 8h period index, reuses the DSR.
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from itertools import product
from math import sqrt
from pathlib import Path
from statistics import mean, pstdev

import pyarrow.csv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tios.dataset.acquire import BASIS_PAIRS  # noqa: E402
from tios.dataset.normalize import UNIT_THRESHOLD  # noqa: E402
from tios.validation.multiple_testing import (  # noqa: E402
    deflated_sharpe_ratio,
    sharpe_variance_from_trials,
)

RAW = ROOT / "data" / "raw"
OUT = ROOT / "artifacts" / "validation" / "funding_carry_basis"
PPY = 3 * 365
FEE = 0.0004
DSR_PASS = 0.95
EIGHT_H_MS = 8 * 3600 * 1000
THRESHOLDS = (0.0, 0.0001)
LOOKBACKS = (9, 21, 63)
REBALANCES = (3, 9, 21)


def _to_ms(ts: int) -> int:
    return ts // 1000 if ts >= UNIT_THRESHOLD else ts


def _period(ts: int) -> int:
    return _to_ms(ts) // EIGHT_H_MS


def _load_klines(kind: str) -> dict[str, dict[int, float]]:
    """8h close per pair keyed by 8h period index (kind = 'spot8h' | 'perp8h')."""
    out: dict[str, dict[int, float]] = {}
    for pair_dir in sorted((RAW / kind).glob("*")):
        if not pair_dir.is_dir():
            continue
        rows: dict[int, float] = {}
        for zp in sorted(pair_dir.glob("*.zip")):
            with zipfile.ZipFile(zp) as z:
                data = z.read(z.namelist()[0])
            skip = 1 if data[:9].lower().startswith(b"open_time") else 0
            table = pyarrow.csv.read_csv(
                io.BytesIO(data),
                read_options=pyarrow.csv.ReadOptions(
                    column_names=[
                        "ot",
                        "o",
                        "h",
                        "low",
                        "c",
                        "v",
                        "ct",
                        "q",
                        "n",
                        "tb",
                        "tq",
                        "ig",
                    ],
                    skip_rows=skip,
                ),
            )
            for ot, close in zip(
                table.column("ot").to_pylist(), table.column("c").to_pylist(), strict=True
            ):
                rows[_period(int(ot))] = float(close)
        if rows:
            out[pair_dir.name] = rows
    return out


def _load_funding() -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {}
    for pair_dir in sorted((RAW / "fundingRate").glob("*")):
        if not pair_dir.is_dir():
            continue
        rows: dict[int, float] = {}
        for zp in sorted(pair_dir.glob("*.zip")):
            with zipfile.ZipFile(zp) as z:
                data = z.read(z.namelist()[0])
            table = pyarrow.csv.read_csv(io.BytesIO(data))
            for ts, rate in zip(
                table.column("calc_time").to_pylist(),
                table.column("last_funding_rate").to_pylist(),
                strict=True,
            ):
                rows[_period(int(ts))] = float(rate)
        out[pair_dir.name] = rows
    return out


def build_matrix() -> tuple[list[int], dict[str, dict[str, list[float | None]]]]:
    spot, perp, fund = _load_klines("spot8h"), _load_klines("perp8h"), _load_funding()
    pairs = [p for p in BASIS_PAIRS if p in spot and p in perp and p in fund]
    periods = sorted(set().union(*[set(spot[p]) & set(perp[p]) & set(fund[p]) for p in pairs]))
    data = {
        p: {
            "spot": [spot[p].get(t) for t in periods],
            "perp": [perp[p].get(t) for t in periods],
            "fund": [fund[p].get(t) for t in periods],
        }
        for p in pairs
    }
    return periods, data


def _carry_return(d: dict[str, list[float | None]], t: int) -> float | None:
    """funding + (spot_return - perp_return) for one pair at period t (basis-aware)."""
    s0, s1 = d["spot"][t - 1], d["spot"][t]
    p0, p1 = d["perp"][t - 1], d["perp"][t]
    f = d["fund"][t]
    if None in (s0, s1, p0, p1, f):
        return None
    return f + (s1 / s0 - 1) - (p1 / p0 - 1)


def backtest(data: dict[str, dict], threshold: float, lookback: int, rebalance: int) -> list[float]:
    pairs = list(data)
    n = len(next(iter(data.values()))["fund"])
    held: set[str] = set()
    strat = [0.0] * n
    for t in range(1, n):
        if held:
            got = [r for p in held if (r := _carry_return(data[p], t)) is not None]
            strat[t] = sum(got) / len(got) if got else 0.0
        if t >= lookback and t % rebalance == 0:
            new = set()
            for p in pairs:
                w = [
                    data[p]["fund"][t - k]
                    for k in range(lookback)
                    if data[p]["fund"][t - k] is not None
                ]
                if w and mean(w) > threshold:
                    new.add(p)
            if new != held:
                strat[t] -= FEE * len(new ^ held) / max(len(new | held), 1)
            held = new
    return strat


def _metrics(strat: list[float]) -> dict:
    equity = peak = 1.0
    max_dd = 0.0
    for r in strat:
        equity *= 1 + r
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1)
    sd = pstdev(strat)
    sb = mean(strat) / sd if sd > 0 else 0.0
    return {
        "sharpe_bar": sb,
        "sharpe_ann": round(sb * sqrt(PPY), 2),
        "ann_return_pct": round((equity ** (PPY / len(strat)) - 1) * 100, 1)
        if equity > 0
        else -100.0,
        "max_drawdown_pct": round(max_dd * 100, 1),
        "total_return_pct": round((equity - 1) * 100, 1),
        "bars": len(strat),
    }


def build_report() -> dict:
    periods, data = build_matrix()
    trials = []
    for threshold, lookback, rebalance in product(THRESHOLDS, LOOKBACKS, REBALANCES):
        strat = backtest(data, threshold, lookback, rebalance)
        m = _metrics(strat)
        m.update(threshold=threshold, lookback=lookback, rebalance=rebalance, returns=strat)
        trials.append(m)
    sharpes = [t["sharpe_bar"] for t in trials]
    best = max(trials, key=lambda t: t["sharpe_bar"])
    ret = best["returns"]
    mr, sd = mean(ret), pstdev(ret)
    skew = (sum((r - mr) ** 3 for r in ret) / len(ret)) / sd**3 if sd > 0 else 0.0
    kurt = (sum((r - mr) ** 4 for r in ret) / len(ret)) / sd**4 if sd > 0 else 3.0
    dsr = deflated_sharpe_ratio(
        observed_sharpe=best["sharpe_bar"],
        sharpe_variance=sharpe_variance_from_trials(sharpes),
        independent_trials=len(trials),
        sample_count=best["bars"],
        skewness=skew,
        kurtosis=kurt,
    )
    keys = (
        "threshold",
        "lookback",
        "rebalance",
        "sharpe_ann",
        "ann_return_pct",
        "max_drawdown_pct",
    )
    return {
        "schema": "tios-funding-carry-basis-v1",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "execution_authority": "NONE",
        "tradeability": "RESEARCH_ONLY — perps/margin S4-gated; 1x (no liquidation modelled); "
        "exchange counterparty risk out of scope",
        "universe_pairs": len(data),
        "periods": len(periods),
        "trials_searched": len(trials),
        "best": {k: best[k] for k in (*keys, "total_return_pct")},
        "g10_dsr": {
            "dsr": round(dsr["dsr"], 4),
            "expected_max_noise_sharpe": round(dsr["expected_maximum_noise_sharpe"], 4),
            "threshold": DSR_PASS,
            "verdict": "PASS" if dsr["dsr"] >= DSR_PASS else "FAIL",
            "verdict_is_genuine": False,
            "note": "Basis-aware (funding + spot-perp divergence) — and the carry SURVIVES "
            "basis risk (that is real: a well-arbitraged perp tracks spot within ~0.1%). But "
            "Sharpe ~9 is still inflated: it omits execution slippage, intraperiod basis "
            "spikes (8h closes), leverage/liquidation, and exchange COUNTERPARTY risk (the "
            "actual 2022 killer). Real-world carry Sharpe is ~2-4. The remaining validation "
            "is EXECUTION-level — it needs S3 paper trading to measure real fills/slippage — "
            "and counterparty risk is an operator/venue decision, not a backtest number.",
        },
        "top_configs": [
            {k: t[k] for k in keys}
            for t in sorted(trials, key=lambda t: t["sharpe_bar"], reverse=True)[:5]
        ],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (OUT / "FUNDING_CARRY_BASIS.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    b, g = report["best"], report["g10_dsr"]
    print(f"universe: {report['universe_pairs']} pairs, {report['periods']} 8h periods")
    cfg = f"thr={b['threshold']} lb={b['lookback']} reb={b['rebalance']}"
    print(
        f"best basis-aware carry: Sharpe {b['sharpe_ann']} ({cfg}) "
        f"ann {b['ann_return_pct']}% maxDD {b['max_drawdown_pct']}%"
    )
    print(f"G10 DSR: {g['dsr']} (need >= {g['threshold']}) -> {g['verdict']}")


if __name__ == "__main__":
    main()
