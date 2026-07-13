"""Focused checks for the portable canonical BTCUSDT 5m restore path."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import restore_canonical_btcusdt_5m as restore  # noqa: E402

MANIFEST = ROOT / "data/raw/manifests/DS-CRYPTO-SPOT-BTCUSDT-5M-V1.source.json"


def test_tracked_manifest_is_complete_portable_and_exactly_pinned() -> None:
    manifest = restore.load_manifest(MANIFEST)
    paths = [
        manifest["local_layout"]["raw_root"],
        manifest["local_layout"]["normalized_path"],
        manifest["normalization"]["implementation_path"],
        *(item["path"] for item in manifest["files"]),
    ]

    assert len(manifest["files"]) == 66
    assert sum(item["size"] for item in manifest["files"]) == 30626469
    assert all(not PurePosixPath(path).is_absolute() for path in paths)
    assert all(".." not in PurePosixPath(path).parts for path in paths)
    assert "/Users/" not in MANIFEST.read_text(encoding="utf-8")


def test_default_cli_is_offline_and_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(restore, "verify_sources", lambda *_: calls.append("sources"))
    monkeypatch.setattr(restore, "verify_normalized", lambda *_: calls.append("normalized"))
    monkeypatch.setattr(
        restore,
        "fetch_missing",
        lambda *_: (_ for _ in ()).throw(AssertionError("network path called")),
    )
    monkeypatch.setattr(
        restore,
        "rebuild",
        lambda *_: (_ for _ in ()).throw(AssertionError("write path called")),
    )

    assert restore.main(["--manifest", str(MANIFEST)]) == 0
    assert calls == ["sources", "normalized"]


def test_existing_file_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    target = tmp_path / "source.zip"
    target.write_bytes(b"bad")
    expected = hashlib.sha256(b"new").hexdigest()

    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        restore.verify_file(target, expected, 3, "test source")


def test_bad_download_is_not_installed(tmp_path: Path) -> None:
    expected = b"good"
    manifest = {
        "files": [
            {
                "month": "2021-01",
                "path": "BTCUSDT/5m/BTCUSDT-5m-2021-01.zip",
                "url": "https://data.binance.vision/example.zip",
                "sha256": hashlib.sha256(expected).hexdigest(),
                "size": len(expected),
            }
        ]
    }

    with pytest.raises(RuntimeError, match="does not match its frozen pins"):
        restore.fetch_missing(manifest, tmp_path, fetcher=lambda _: b"evil")
    assert list(tmp_path.rglob("*")) == []
