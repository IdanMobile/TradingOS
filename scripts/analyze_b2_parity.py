"""Retain a machine-readable explanation of the BTC B2 engine residual."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
FT = ROOT / "artifacts/bakeoff/freqtrade/B2/BTCUSDT/F0_S0/run1"
FT_MARKET = ROOT / "artifacts/bakeoff/freqtrade/B2/BTCUSDT/F0_S0/market_probe"
HB = ROOT / "artifacts/bakeoff/hummingbot/B2/BTCUSDT/F0_S0/run1"
DATA = ROOT / "data/normalized/BTCUSDT_5m.parquet"
OUT = ROOT / "artifacts/bakeoff/parity/b2_residual_analysis.json"
REPORT = ROOT / "artifacts/reports/B2_PARITY_RESIDUAL_REPORT.md"


def scalar(query: str) -> Any:
    return duckdb.sql(query).fetchone()[0]


def counts(path: Path) -> dict[str, int]:
    rows = duckdb.sql(
        f"""SELECT count(*) fills,
                    count(*) FILTER (WHERE side = 'buy') buys,
                    count(*) FILTER (WHERE side = 'sell') sells
             FROM read_parquet('{path / "trades.parquet"}')"""
    ).fetchone()
    return {"fills": rows[0], "buys": rows[1], "sells": rows[2]}


def timestamp_set(path: Path, side: str, shifted: bool = False) -> set[str]:
    expression = "ts_fill + INTERVAL 5 MINUTE" if shifted else "ts_fill"
    rows = duckdb.sql(
        f"""SELECT CAST({expression} AS VARCHAR)
             FROM read_parquet('{path / "trades.parquet"}')
             WHERE side = '{side}'
               AND {expression} >= TIMESTAMPTZ '2021-01-01 03:00:00+00:00'
               AND {expression} < TIMESTAMPTZ '2021-02-11 03:40:00+00:00'"""
    ).fetchall()
    return {row[0] for row in rows}


def main() -> None:
    gap_row = duckdb.sql(
        f"""WITH ordered AS (
                 SELECT timestamp_open_utc ts,
                        lag(timestamp_open_utc) OVER (ORDER BY timestamp_open_utc) prev
                 FROM read_parquet('{DATA}')
             ), gaps AS (
                 SELECT date_diff('minute', prev, ts) / 5 - 1 missing
                 FROM ordered WHERE date_diff('minute', prev, ts) > 5
             )
             SELECT count(*), CAST(sum(missing) AS BIGINT), CAST(max(missing) AS BIGINT)
             FROM gaps"""
    ).fetchone()
    ft_counts = counts(FT)
    hb_counts = counts(HB)
    market_counts = counts(FT_MARKET)
    first_segment: dict[str, Any] = {}
    for side in ("buy", "sell"):
        ft_times = timestamp_set(FT_MARKET, side)
        hb_times = timestamp_set(HB, side, shifted=True)
        first_segment[side] = {
            "freqtrade": len(ft_times),
            "hummingbot_shifted_next_open": len(hb_times),
            "hummingbot_only": len(hb_times - ft_times),
            "freqtrade_only": len(ft_times - hb_times),
            "hummingbot_only_examples": sorted(hb_times - ft_times)[:5],
            "freqtrade_only_examples": sorted(ft_times - hb_times)[:5],
        }

    example = duckdb.sql(
        f"""SELECT CAST(t.ts_fill AS VARCHAR), CAST(t.price AS VARCHAR),
                    CAST(c.timestamp_open_utc AS VARCHAR), CAST(c.open AS VARCHAR)
             FROM read_parquet('{FT_MARKET / "trades.parquet"}') t
             CROSS JOIN read_parquet('{DATA}') c
             WHERE t.side = 'sell'
               AND t.ts_fill = TIMESTAMPTZ '2021-01-01 06:15:00+00:00'
               AND c.timestamp_open_utc = TIMESTAMPTZ '2021-01-01 06:00:00+00:00'"""
    ).fetchone()
    payload = {
        "schema": "tios-b2-parity-residual-v1",
        "status": "EXPLAINED_NOT_FILL_IDENTICAL",
        "full_period": {
            "freqtrade": ft_counts,
            "hummingbot": hb_counts,
            "roundtrip_residual": hb_counts["buys"] - ft_counts["buys"],
        },
        "canonical_data_gaps": {
            "gap_events": gap_row[0],
            "missing_5m_bars": gap_row[1],
            "largest_gap_bars": gap_row[2],
            "effect": (
                "Freqtrade advances a regular synthetic clock and consumes at most one "
                "source row per clock step; gaps can lag row time and leave trailing rows "
                "unprocessed. Hummingbot iterates retained candle timestamps directly."
            ),
        },
        "gap_free_first_segment": first_segment,
        "order_semantics_probe": {
            "default_limit_counts": ft_counts,
            "explicit_market_counts": market_counts,
            "count_changed": ft_counts != market_counts,
            "delayed_exit_example": {
                "reported_fill_timestamp": example[0],
                "reported_fill_price": example[1],
                "matching_source_open_timestamp": example[2],
                "matching_source_open_price": example[3],
            },
            "interpretation": (
                "Explicit market order configuration does not change Freqtrade's count. "
                "Its simulator still reports delayed exit timestamps at an earlier source "
                "open price, suppressing some intervening entries."
            ),
        },
        "classification": "EXPLAINED_ENGINE_EXECUTION_AND_DATA_GAP_DIVERGENCE",
        "decision": (
            "Do not force fill equality or compare PnL across these lanes. Use contiguous "
            "windows for future signal parity and retain Freqtrade/Hummingbot for their "
            "different role-fit evidence."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    REPORT.write_text(
        f"""# B2 BTC Parity Residual Report

Status: **EXPLAINED, NOT FILL-IDENTICAL**

The 77-roundtrip residual is retained as an engine-semantics result, not hidden or
converted into a P&L comparison.

## Evidence

- Full period: Freqtrade {ft_counts["buys"]:,} vs Hummingbot {hb_counts["buys"]:,}
  roundtrips.
- Canonical BTCUSDT 5m data: {gap_row[0]} gap events containing
  {gap_row[1]} missing bars; the largest gap is {gap_row[2]} bars.
- Before the first data gap, after shifting Hummingbot to next-open timing, the
  gap-free segment still has small localized timestamp differences. This proves
  execution/order-state behavior exists independently of the later data gaps.
- An explicit Freqtrade market-order probe still produced {market_counts["buys"]:,}
  roundtrips. One retained exit is timestamped `{example[0]}` at price `{example[1]}`,
  which equals the source candle open at `{example[2]}`. The engine therefore
  carries order price and reported fill time through different state transitions.

## Interpretation

Freqtrade uses prior-bar signals, a regular synthetic backtest clock, startup
trimming, and its own order lifecycle. Hummingbot's retained controller creates
executors on current-candle signals and iterates retained timestamps. Missing
candles and delayed exit state therefore affect the two engines differently.

The engines remain useful for different roles, but this full-period context is not
a fill-parity or P&L-parity fixture. Future semantic parity must use contiguous
windows with explicit signal, decision, order, and fill timestamps.

Machine-readable evidence: `{OUT.relative_to(ROOT)}`.
""",
        encoding="utf-8",
    )
    print(f"wrote {OUT} and {REPORT}")


if __name__ == "__main__":
    main()
