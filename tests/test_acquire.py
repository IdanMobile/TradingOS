"""URL/scope construction checks for the multi-dataset acquirer (no network).

The download/HEAD paths are I/O; what must be exactly right offline is the month
range and the Binance URL/path layout, since a wrong path silently 404s every file.
"""

from __future__ import annotations

import json

import pytest

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


def test_filtered_kline_scope_is_exact_and_validated() -> None:
    planned = a.planned_files(
        ("klines",),
        symbols=("BTCUSDT", "ETHUSDT"),
        timeframes=("1m",),
        start_month="2026-05",
        end_month="2026-06",
    )
    assert [(item.symbol, item.interval, item.month) for item in planned] == [
        ("BTCUSDT", "1m", "2026-05"),
        ("BTCUSDT", "1m", "2026-06"),
        ("ETHUSDT", "1m", "2026-05"),
        ("ETHUSDT", "1m", "2026-06"),
    ]
    with pytest.raises(ValueError, match="only for --kinds klines"):
        a.planned_files(("aggTrades",), symbols=("BTCUSDT",))
    with pytest.raises(ValueError, match="unsupported symbols"):
        a.planned_files(("klines",), symbols=("NOTREAL",))
    with pytest.raises(ValueError, match="unsupported timeframes"):
        a.planned_files(("klines",), timeframes=("2m",))
    with pytest.raises(ValueError, match="within 2021-01..2026-06"):
        a.planned_files(("klines",), start_month="2020-12")
    with pytest.raises(ValueError, match="expected YYYY-MM"):
        a.planned_files(("klines",), start_month="2026-13")


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


def test_manifests_are_content_addressed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(a, "RAW_ROOT", tmp_path)
    rel = "klines/BTCUSDT/1m/BTCUSDT-1m-2026-06.zip"
    acquired = a.Acquired(rel, 1, "a" * 64, False, None, "reused")
    klines = a.write_manifest(
        ("klines",),
        [acquired],
        symbols=("BTCUSDT",),
        timeframes=("1m",),
        start_month="2026-06",
        end_month="2026-06",
    )

    assert klines.parent.name == "klines"
    assert json.loads(klines.read_text())["files"][0]["checksum_verified"] is False


def test_filtered_manifest_binds_scope_and_checksum_requirement(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(a, "RAW_ROOT", tmp_path)
    acquired = a.Acquired(
        "klines/BTCUSDT/1m/BTCUSDT-1m-2026-06.zip",
        1,
        "a" * 64,
        True,
        "a" * 64,
        "reused",
    )
    path = a.write_manifest(
        ("klines",),
        [acquired],
        symbols=("BTCUSDT",),
        timeframes=("1m",),
        start_month="2026-06",
        end_month="2026-06",
        require_official_checksums=True,
    )
    manifest = json.loads(path.read_text())
    assert manifest["window"] == {"start": "2026-06", "end": "2026-06"}
    assert manifest["scope"] == {
        "symbols": ["BTCUSDT"],
        "timeframes": ["1m"],
        "planned_file_count": 1,
        "require_official_checksums": True,
    }


def test_manifest_refuses_missing_extra_duplicate_and_wrong_planned_names(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(a, "RAW_ROOT", tmp_path)
    kwargs = {
        "symbols": ("BTCUSDT",),
        "timeframes": ("1m",),
        "start_month": "2026-06",
        "end_month": "2026-06",
    }
    rel = "klines/BTCUSDT/1m/BTCUSDT-1m-2026-06.zip"
    valid = a.Acquired(rel, 0, "", False, None, "missing")
    manifest = a.write_manifest(("klines",), [valid], **kwargs)
    assert json.loads(manifest.read_text())["files"] == []
    with pytest.raises(ValueError, match="do not match planned scope"):
        a.write_manifest(("klines",), [], **kwargs)
    with pytest.raises(ValueError, match="duplicate paths"):
        a.write_manifest(("klines",), [valid, valid], **kwargs)
    wrong = a.Acquired("klines/BTCUSDT/1m/wrong.zip", 0, "", False, None, "missing")
    with pytest.raises(ValueError, match="do not match planned scope"):
        a.write_manifest(("klines",), [wrong], **kwargs)
    extra = a.Acquired("klines/BTCUSDT/1m/extra.zip", 0, "", False, None, "missing")
    with pytest.raises(ValueError, match="do not match planned scope"):
        a.write_manifest(("klines",), [valid, extra], **kwargs)


def test_empty_explicit_cli_selector_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["acquire", "plan", "--kinds", "klines", "--symbols", ""])
    with pytest.raises(SystemExit):
        a.main()


def test_fetch_required_official_checksums_fails_before_manifest(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(a, "RAW_ROOT", tmp_path)
    spec = a._kline_spec("BTCUSDT", "1m", "2026-06")
    monkeypatch.setattr(a, "planned_files", lambda *_args, **_kwargs: [spec])
    monkeypatch.setattr(
        a,
        "download_one",
        lambda _spec: a.Acquired(_spec.rel, 4, "a" * 64, False, None, "reused"),
    )
    with pytest.raises(RuntimeError, match="official checksum required"):
        a.fetch(("klines",), 1, require_official_checksums=True)
    assert not (tmp_path / "manifests").exists()
