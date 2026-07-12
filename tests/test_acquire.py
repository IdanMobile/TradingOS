"""URL/scope construction checks for the multi-dataset acquirer (no network).

The download/HEAD paths are I/O; what must be exactly right offline is the month
range and the Binance URL/path layout, since a wrong path silently 404s every file.
"""

from __future__ import annotations

from tios.dataset import acquire as a


def test_month_range_is_the_frozen_window() -> None:
    ms = a.months()
    assert ms[0] == "2021-01" and ms[-1] == "2026-06"
    assert len(ms) == 66  # 5.5 years inclusive


def test_kline_spec_url_and_path_layout() -> None:
    s = a._kline_spec("SOLUSDT", "1h", "2024-03")
    assert s.url == (
        "https://data.binance.vision/data/spot/monthly/klines/SOLUSDT/1h/SOLUSDT-1h-2024-03.zip"
    )
    assert s.rel == "klines/SOLUSDT/1h/SOLUSDT-1h-2024-03.zip"


def test_aggtrades_and_funding_spec_layout() -> None:
    agg = a._simple_spec("spot", "aggTrades", "BTCUSDT", "2025-01")
    assert agg.url.endswith("spot/monthly/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2025-01.zip")
    fund = a._simple_spec("futures/um", "fundingRate", "ETHUSDT", "2025-01")
    assert fund.url.endswith(
        "futures/um/monthly/fundingRate/ETHUSDT/ETHUSDT-fundingRate-2025-01.zip"
    )


def test_planned_file_counts_match_scope() -> None:
    klines = a.planned_files(("klines",))
    assert len(klines) == len(a.TOP_PAIRS) * len(a.TIMEFRAMES) * 66
    ticks = a.planned_files(("aggTrades",))
    assert len(ticks) == len(a.TICK_PAIRS) * 66  # BTC + ETH only
    assert all(f.kind == "aggTrades" for f in ticks)
