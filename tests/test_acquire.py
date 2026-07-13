"""URL/scope construction checks for the multi-dataset acquirer (no network).

The download/HEAD paths are I/O; what must be exactly right offline is the month
range and the Binance URL/path layout, since a wrong path silently 404s every file.
"""

from __future__ import annotations

import json

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


def test_reused_file_requires_exact_official_checksum(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(a, "RAW_ROOT", tmp_path)
    spec = a._kline_spec("BTCUSDT", "1h", "2024-01")
    path = tmp_path / spec.rel
    path.parent.mkdir(parents=True)
    path.write_bytes(b"retained")

    monkeypatch.setattr(a, "official_checksum", lambda _url: None)
    unverified = a.download_one(spec)
    assert unverified.status == "reused"
    assert unverified.checksum_verified is False
    assert unverified.official_sha256 is None

    digest = a.sha256_hex(b"retained")
    monkeypatch.setattr(a, "official_checksum", lambda _url: digest)
    verified = a.download_one(spec)
    assert verified.checksum_verified is True
    assert verified.official_sha256 == digest


def test_manifests_are_content_addressed_and_separated_by_kind(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(a, "RAW_ROOT", tmp_path)
    acquired = a.Acquired("x.zip", 1, "a" * 64, False, None, "reused")
    klines = a.write_manifest(("klines",), [acquired])
    funding = a.write_manifest(("fundingRate",), [acquired])

    assert klines.parent.name == "klines"
    assert funding.parent.name == "fundingRate"
    assert klines != funding
    assert json.loads(klines.read_text())["files"][0]["checksum_verified"] is False
