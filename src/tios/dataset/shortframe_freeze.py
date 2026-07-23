"""Certify and freeze the bounded BTC/ETH short-frame dataset.

The production surface is deliberately fixed to BTCUSDT/ETHUSDT × 1m/5m/15m
for 2021-01..2026-06.  It consumes retained Binance archives only; it never
downloads data and grants no research, strategy, or execution authority.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet

from tios.dataset import normalize_multi
from tios.dataset.acquire import months
from tios.dataset.normalize import CANONICAL_SCHEMA, SOURCE_TAG, content_sha256
from tios.trading_domain import Timeframe

DATASET_ID = "DS-CRYPTO-SPOT-SHORTFRAMES-V1"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
TIMEFRAMES = ("1m", "5m", "15m")
START_MONTH = "2021-01"
END_MONTH = "2026-06"
CUTOFF_UTC = datetime(2026, 7, 1, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = ROOT / "data" / "normalized" / DATASET_ID
NORMALIZED_ROOT = OUTPUT_ROOT.parent
REPORT_ROOT = ROOT / "artifacts" / "datasets"
MULTI_RAW_ROOT = ROOT / "data" / "raw"
ONE_MINUTE_MANIFEST_ROOT = MULTI_RAW_ROOT / "manifests" / "klines"
BAKEOFF_RAW_ROOT = ROOT / "data" / "raw" / "binance_spot"
BAKEOFF_RAW_MANIFEST = BAKEOFF_RAW_ROOT / "raw_manifest.json"
BAKEOFF_NORM_ROOT = ROOT / "data" / "normalized"
BAKEOFF_DATASET_MANIFEST = REPORT_ROOT / "DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"
BAKEOFF_QUALITY_REPORT = REPORT_ROOT / "QUALITY_REPORT.json"
CODE_SURFACE = (
    "src/tios/dataset/acquire.py",
    "src/tios/dataset/download.py",
    "src/tios/dataset/normalize.py",
    "src/tios/dataset/normalize_multi.py",
    "src/tios/dataset/quality.py",
    "src/tios/dataset/shortframe_freeze.py",
    "src/tios/trading_domain/__init__.py",
    "src/tios/trading_domain/models.py",
)
INTERVAL_US = {frame.value: frame.seconds * 1_000_000 for frame in Timeframe}
CLOSE_TIME_SEMANTIC_LABEL = (
    "source_close_preserved_within_open_interval_exact_early_close_inventory_v1"
)
EarlyClosePin = tuple[str, str, str, str, str, str]
EARLY_CLOSE_INVENTORY: tuple[EarlyClosePin, ...] = (
    (
        "BTCUSDT",
        "1m",
        "2021-02-11T03:40:00.000000Z",
        "2021-02-11T03:40:54.773000Z",
        "klines/BTCUSDT/1m/BTCUSDT-1m-2021-02.zip",
        "21723e4951ba30037cb8417278b7cf4a38d47c625b1cb5ac97864d539ae6d407",
    ),
    (
        "BTCUSDT",
        "1m",
        "2021-04-25T04:00:00.000000Z",
        "2021-04-25T04:00:58.146000Z",
        "klines/BTCUSDT/1m/BTCUSDT-1m-2021-04.zip",
        "016ea34ee7e52c4783c1e03ec65c710361c1ccf228d3a4c0b44a4d0baa859641",
    ),
    (
        "BTCUSDT",
        "1m",
        "2021-08-13T01:59:00.000000Z",
        "2021-08-13T01:59:59.000000Z",
        "klines/BTCUSDT/1m/BTCUSDT-1m-2021-08.zip",
        "8e886c3aeb7eb625493e875bfaf181eeb5a316dad424c86d042ad2c73cad563b",
    ),
    (
        "BTCUSDT",
        "1m",
        "2021-12-24T04:59:00.000000Z",
        "2021-12-24T04:59:54.362000Z",
        "klines/BTCUSDT/1m/BTCUSDT-1m-2021-12.zip",
        "2b6c79547da2d87e6735d29fcb2d75f0e15c9cbfcec6396c8d8f20b3632d8e0b",
    ),
    (
        "BTCUSDT",
        "1m",
        "2023-03-24T12:39:00.000000Z",
        "2023-03-24T12:39:41.646000Z",
        "klines/BTCUSDT/1m/BTCUSDT-1m-2023-03.zip",
        "5591171a15f210af647a2fb68ab8cbad45a3a595cfe9a0eec9d06e5e84928bec",
    ),
    (
        "BTCUSDT",
        "5m",
        "2021-02-11T03:40:00.000000Z",
        "2021-02-11T03:40:54.773000Z",
        "klines/BTCUSDT/5m/BTCUSDT-5m-2021-02.zip",
        "64cacfee55b7e73d6728a6e7cf32b03be2f205c06ad27a99889f002d0c853769",
    ),
    (
        "BTCUSDT",
        "5m",
        "2021-04-25T04:00:00.000000Z",
        "2021-04-25T04:00:58.146000Z",
        "klines/BTCUSDT/5m/BTCUSDT-5m-2021-04.zip",
        "e365a42f9b3cd6262110977b37d341f90e339ef5b617de2d90c945c53a930854",
    ),
    (
        "BTCUSDT",
        "5m",
        "2021-08-13T01:55:00.000000Z",
        "2021-08-13T01:59:59.000000Z",
        "klines/BTCUSDT/5m/BTCUSDT-5m-2021-08.zip",
        "ad8168331b2f0c83e7d4dea149b09881d5f4ecb0e6c7049f8637f2ef5a6dbf78",
    ),
    (
        "BTCUSDT",
        "5m",
        "2021-12-24T04:55:00.000000Z",
        "2021-12-24T04:59:54.362000Z",
        "klines/BTCUSDT/5m/BTCUSDT-5m-2021-12.zip",
        "17c2731a870d09d0ea1345b9af40234fae47c947ff373499799169cdfda3b41c",
    ),
    (
        "BTCUSDT",
        "5m",
        "2023-03-24T12:35:00.000000Z",
        "2023-03-24T12:39:41.646000Z",
        "klines/BTCUSDT/5m/BTCUSDT-5m-2023-03.zip",
        "840da3f1dba73d44c483b2c600528ee845366a8f2dec3db1d0be9e128741ec19",
    ),
    (
        "BTCUSDT",
        "15m",
        "2021-02-11T03:30:00.000000Z",
        "2021-02-11T03:40:54.773000Z",
        "klines/BTCUSDT/15m/BTCUSDT-15m-2021-02.zip",
        "2b2658c43308a1a0ec6684f7d938879d3a6e4cc8828f0875e342e0ddf8f5f4f0",
    ),
    (
        "BTCUSDT",
        "15m",
        "2021-04-25T04:00:00.000000Z",
        "2021-04-25T04:00:58.146000Z",
        "klines/BTCUSDT/15m/BTCUSDT-15m-2021-04.zip",
        "726f7165f3703ec852194e6fbd54157ecf54760d670db399adec8de23026a947",
    ),
    (
        "BTCUSDT",
        "15m",
        "2021-08-13T01:45:00.000000Z",
        "2021-08-13T01:59:59.000000Z",
        "klines/BTCUSDT/15m/BTCUSDT-15m-2021-08.zip",
        "e4d20bbe576a94c7474f951b4e44adb1a0d6149e6b9eed0be2ad69504ca775e0",
    ),
    (
        "BTCUSDT",
        "15m",
        "2021-12-24T04:45:00.000000Z",
        "2021-12-24T04:59:54.362000Z",
        "klines/BTCUSDT/15m/BTCUSDT-15m-2021-12.zip",
        "5e87f4e0e328a170291c91001dd48e124533108af2c6d17315821399b43a0dd7",
    ),
    (
        "BTCUSDT",
        "15m",
        "2023-03-24T12:30:00.000000Z",
        "2023-03-24T12:39:41.646000Z",
        "klines/BTCUSDT/15m/BTCUSDT-15m-2023-03.zip",
        "c9871c6908687def566067cbadd1e0bab4740956f4d842992b7da52828ccae96",
    ),
    (
        "ETHUSDT",
        "1m",
        "2021-02-11T03:40:00.000000Z",
        "2021-02-11T03:40:55.829000Z",
        "klines/ETHUSDT/1m/ETHUSDT-1m-2021-02.zip",
        "964070408500f1e189daf68832abc14d53ee03c53e9971d23aef180f5730543e",
    ),
    (
        "ETHUSDT",
        "1m",
        "2021-04-25T04:00:00.000000Z",
        "2021-04-25T04:00:59.271000Z",
        "klines/ETHUSDT/1m/ETHUSDT-1m-2021-04.zip",
        "7a9c6f70708570a7a786afe7451c8fc8cab20e5efb6fcb11aa242521bd19edc9",
    ),
    (
        "ETHUSDT",
        "1m",
        "2021-08-13T01:59:00.000000Z",
        "2021-08-13T01:59:59.000000Z",
        "klines/ETHUSDT/1m/ETHUSDT-1m-2021-08.zip",
        "e6d65e00e8eb757c748c61469268d921f679968e40b9329b04d66ed5392c0073",
    ),
    (
        "ETHUSDT",
        "1m",
        "2021-12-24T04:59:00.000000Z",
        "2021-12-24T04:59:56.158000Z",
        "klines/ETHUSDT/1m/ETHUSDT-1m-2021-12.zip",
        "4afcb0943a7a7e474904bc2f40983abc5155c6c88cd0775f5b5b2977cb69a69f",
    ),
    (
        "ETHUSDT",
        "1m",
        "2023-03-24T12:39:00.000000Z",
        "2023-03-24T12:39:43.061000Z",
        "klines/ETHUSDT/1m/ETHUSDT-1m-2023-03.zip",
        "e2552c2298f4b67027bfa1f7da364b0d398e96a76dae8fa2085dddf357f60a69",
    ),
    (
        "ETHUSDT",
        "5m",
        "2021-02-11T03:40:00.000000Z",
        "2021-02-11T03:40:55.829000Z",
        "klines/ETHUSDT/5m/ETHUSDT-5m-2021-02.zip",
        "fa4d766b72174fc35d443700f5101d8b48c17f1665187947066bd7d426f05da3",
    ),
    (
        "ETHUSDT",
        "5m",
        "2021-04-25T04:00:00.000000Z",
        "2021-04-25T04:00:59.271000Z",
        "klines/ETHUSDT/5m/ETHUSDT-5m-2021-04.zip",
        "463e140802908fdea8cfda06baa26096c4f66f25add9bfaeca849fbd342cb194",
    ),
    (
        "ETHUSDT",
        "5m",
        "2021-08-13T01:55:00.000000Z",
        "2021-08-13T01:59:59.000000Z",
        "klines/ETHUSDT/5m/ETHUSDT-5m-2021-08.zip",
        "1f30d155249567e4e9b491ec12ad5daffff7539786ec02df69531efdec594614",
    ),
    (
        "ETHUSDT",
        "5m",
        "2021-12-24T04:55:00.000000Z",
        "2021-12-24T04:59:56.158000Z",
        "klines/ETHUSDT/5m/ETHUSDT-5m-2021-12.zip",
        "db0dd70c525f0eb5a2d644ae82a06a106fee0d917e29465c79138ef6488fda00",
    ),
    (
        "ETHUSDT",
        "5m",
        "2023-03-24T12:35:00.000000Z",
        "2023-03-24T12:39:43.061000Z",
        "klines/ETHUSDT/5m/ETHUSDT-5m-2023-03.zip",
        "048244294ce3d656c9d29a376cfd244df6f6c604bfe0d070888fa87a528ff0d4",
    ),
    (
        "ETHUSDT",
        "15m",
        "2021-02-11T03:30:00.000000Z",
        "2021-02-11T03:40:55.829000Z",
        "klines/ETHUSDT/15m/ETHUSDT-15m-2021-02.zip",
        "a89838e59572696d8524402600cb7cc6ded07eb8a4cc69d13d22514d0f088518",
    ),
    (
        "ETHUSDT",
        "15m",
        "2021-04-25T04:00:00.000000Z",
        "2021-04-25T04:00:59.271000Z",
        "klines/ETHUSDT/15m/ETHUSDT-15m-2021-04.zip",
        "0044bc8e84a9f16285dc5f1bc1706234f61543839a8e6619b5ed069681c3d61f",
    ),
    (
        "ETHUSDT",
        "15m",
        "2021-08-13T01:45:00.000000Z",
        "2021-08-13T01:59:59.000000Z",
        "klines/ETHUSDT/15m/ETHUSDT-15m-2021-08.zip",
        "f5fa5199358586df77da71ffaa6c40eccf6e53e1fc5224bac5814eec70597211",
    ),
    (
        "ETHUSDT",
        "15m",
        "2021-12-24T04:45:00.000000Z",
        "2021-12-24T04:59:56.158000Z",
        "klines/ETHUSDT/15m/ETHUSDT-15m-2021-12.zip",
        "5f67b5cfc6122db50b2546db64fb1c135fe8ec96aa40990ecc8242ab941549db",
    ),
    (
        "ETHUSDT",
        "15m",
        "2023-03-24T12:30:00.000000Z",
        "2023-03-24T12:39:43.061000Z",
        "klines/ETHUSDT/15m/ETHUSDT-15m-2023-03.zip",
        "63f591e35691c501c232b06a980641f87aded1f9497281ad279999babaca1e71",
    ),
)


@dataclass(frozen=True)
class FreezeScope:
    symbols: tuple[str, ...]
    timeframes: tuple[str, ...]
    start_month: str
    end_month: str
    cutoff_utc: datetime

    @property
    def month_values(self) -> list[str]:
        start = (int(self.start_month[:4]), int(self.start_month[5:]))
        end = (int(self.end_month[:4]), int(self.end_month[5:]))
        return months(start, end)

    @property
    def keys(self) -> set[str]:
        return {f"{symbol}_{frame}" for symbol in self.symbols for frame in self.timeframes}


@dataclass(frozen=True)
class FreezePaths:
    output_root: Path = OUTPUT_ROOT
    normalized_root: Path = NORMALIZED_ROOT
    report_root: Path = REPORT_ROOT
    multi_raw_root: Path = MULTI_RAW_ROOT
    one_minute_manifest_root: Path = ONE_MINUTE_MANIFEST_ROOT
    bakeoff_raw_root: Path = BAKEOFF_RAW_ROOT
    bakeoff_raw_manifest: Path = BAKEOFF_RAW_MANIFEST
    bakeoff_norm_root: Path = BAKEOFF_NORM_ROOT
    bakeoff_authority_root: Path = REPORT_ROOT
    bakeoff_dataset_manifest: Path = BAKEOFF_DATASET_MANIFEST
    bakeoff_quality_report: Path = BAKEOFF_QUALITY_REPORT
    authority_git_root: Path = ROOT
    repo_root: Path = ROOT


DEFAULT_PATHS = FreezePaths()
FIXED_SCOPE = FreezeScope(SYMBOLS, TIMEFRAMES, START_MONTH, END_MONTH, CUTOFF_UTC)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parquet_logical_content_sha256(table: pa.Table) -> str:
    """Hash logical rows independent of Parquet row-group/Arrow chunk boundaries."""
    return content_sha256(table.combine_chunks())


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _require_regular_file(path: Path, *, label: str) -> Path:
    absolute = path.absolute()
    try:
        metadata = absolute.lstat()
    except FileNotFoundError as error:
        raise ValueError(f"{label} is missing: {absolute}") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"{label} must be a regular non-symlink file: {absolute}")
    if metadata.st_nlink != 1:
        raise ValueError(f"{label} must have exactly one hard link: {absolute}")
    return absolute


def _require_real_directory(path: Path, *, label: str) -> Path:
    absolute = path.absolute()
    if not absolute.is_dir() or absolute.is_symlink() or absolute.resolve() != absolute:
        raise ValueError(f"{label} must be an exact non-symlink directory: {absolute}")
    return absolute


def _prepare_real_directory(path: Path, *, label: str) -> Path:
    absolute = path.absolute()
    if absolute.exists() or absolute.is_symlink():
        return _require_real_directory(absolute, label=label)
    parent = _require_real_directory(absolute.parent, label=f"{label} parent")
    absolute.mkdir(mode=0o755)
    if not _fsync_directory(parent):
        raise RuntimeError(f"directory fsync failed after creating {label}: {absolute}")
    return _require_real_directory(absolute, label=label)


def _require_head_blob(path: Path, *, git_root: Path, label: str) -> None:
    root = _require_real_directory(git_root, label=f"{label} Git root")
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError(f"{label} is outside its authority Git root") from error
    tree = subprocess.run(
        ["git", "ls-tree", "HEAD", "--", relative],
        cwd=root,
        capture_output=True,
        text=True,
    )
    fields = tree.stdout.strip().split(maxsplit=3)
    if tree.returncode != 0 or len(fields) != 4 or fields[1] != "blob":
        raise ValueError(f"{label} is untracked or absent from committed HEAD")
    committed = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=root, capture_output=True)
    if committed.returncode != 0 or committed.stdout != path.read_bytes():
        raise ValueError(f"{label} bytes differ from committed HEAD")


def _canonical_authority_file(paths: FreezePaths, name: str, *, label: str) -> Path:
    root = _require_real_directory(paths.bakeoff_authority_root, label="canonical authority root")
    expected = root / name
    configured = (
        paths.bakeoff_dataset_manifest
        if name == "DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"
        else paths.bakeoff_quality_report
    ).absolute()
    if configured != expected:
        raise ValueError(f"{label} is not at its exact authority path")
    retained = _require_regular_file(expected, label=label)
    if retained.parent != root or retained.resolve() != retained:
        raise ValueError(f"{label} has a symlinked ancestor")
    _require_head_blob(retained, git_root=paths.authority_git_root, label=label)
    return retained


def _confined_regular(root: Path, relative: Path, *, label: str) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} path is not confined: {relative}")
    exact_root = _require_real_directory(root, label=f"{label} root")
    current = exact_root
    for part in relative.parts[:-1]:
        current = current / part
        if not current.is_dir() or current.is_symlink():
            raise ValueError(f"{label} parent is missing or symlinked: {current}")
    candidate = _require_regular_file(exact_root / relative, label=label)
    if candidate.resolve() != candidate or not candidate.is_relative_to(exact_root):
        raise ValueError(f"{label} path escapes its fixed root: {candidate}")
    return candidate


def _content_addressed_one_minute_manifest(path: Path, root: Path) -> Path:
    exact_root = _require_real_directory(root, label="1m manifest root")
    absolute = path.absolute()
    if absolute.parent != exact_root:
        raise ValueError("1m proof manifest must be directly under the fixed klines manifest root")
    match = re.fullmatch(r"raw_manifest_([0-9a-f]{64})\.json", absolute.name)
    if match is None:
        raise ValueError("1m proof manifest filename is not content-addressed")
    retained = _require_regular_file(absolute, label="1m proof manifest")
    if retained.resolve() != retained:
        raise ValueError("1m proof manifest or its parent is symlinked")
    if _sha256(retained) != match.group(1):
        raise ValueError("1m proof manifest filename hash does not match its bytes")
    return retained


def _expected_rel(symbol: str, interval: str, month: str) -> str:
    name = f"{symbol}-{interval}-{month}.zip"
    return f"klines/{symbol}/{interval}/{name}"


def _verify_canonical_authority(*, paths: FreezePaths, scope: FreezeScope) -> dict[str, Any]:
    manifest_path = _canonical_authority_file(
        paths,
        "DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json",
        label="canonical bake-off dataset manifest",
    )
    quality_path = _canonical_authority_file(
        paths, "QUALITY_REPORT.json", label="canonical bake-off quality report"
    )
    expected_raw_manifest = paths.bakeoff_raw_root.absolute() / "raw_manifest.json"
    if paths.bakeoff_raw_manifest.absolute() != expected_raw_manifest:
        raise ValueError("canonical bake-off raw manifest is not at its exact fixed path")
    raw_manifest_path = _confined_regular(
        paths.bakeoff_raw_root,
        Path("raw_manifest.json"),
        label="canonical bake-off raw manifest",
    )
    manifest = _load_object(manifest_path)
    quality = _load_object(quality_path)
    if manifest.get("dataset_id") != "DS-CRYPTO-SPOT-BAKEOFF-V1":
        raise ValueError("unexpected canonical bake-off dataset manifest")
    if quality.get("dataset_id") != "DS-CRYPTO-SPOT-BAKEOFF-V1" or quality.get("overall") != "PASS":
        raise ValueError("canonical bake-off quality report is not PASS")
    raw_ref = manifest.get("raw_manifest")
    if not isinstance(raw_ref, dict) or raw_ref.get("sha256") != _sha256(raw_manifest_path):
        raise ValueError("canonical dataset manifest does not bind the actual raw manifest")
    if manifest.get("quality_report_sha256") != _sha256(quality_path):
        raise ValueError("canonical dataset manifest does not bind the actual quality report")
    regeneration = manifest.get("regeneration_proof")
    if (
        not isinstance(regeneration, dict)
        or regeneration.get("runs") != 2
        or regeneration.get("identical_content_hashes") is not True
        or not isinstance(regeneration.get("content_sha256_by_table"), dict)
    ):
        raise ValueError("canonical dataset lacks valid double-regeneration proof")
    records = manifest.get("tables")
    quality_tables = quality.get("tables")
    if not isinstance(records, dict) or not isinstance(quality_tables, dict):
        raise ValueError("canonical dataset table authority is malformed")
    verified: dict[str, dict[str, Any]] = {}
    for symbol in scope.symbols:
        for interval in (frame for frame in scope.timeframes if frame in {"5m", "15m"}):
            key = f"{symbol}_{interval}"
            record = records.get(key)
            quality_record = quality_tables.get(key)
            if not isinstance(record, dict) or not isinstance(quality_record, dict):
                raise ValueError(f"canonical table authority missing: {key}")
            if record.get("parquet") != f"{key}.parquet":
                raise ValueError(f"canonical table filename mismatch: {key}")
            table_path = _confined_regular(
                paths.bakeoff_norm_root, Path(record["parquet"]), label=f"canonical table {key}"
            )
            table = pyarrow.parquet.read_table(table_path)
            logical = _parquet_logical_content_sha256(table)
            if (
                _sha256(table_path) != record.get("parquet_sha256")
                or logical != record.get("content_sha256")
                or regeneration["content_sha256_by_table"].get(key) != logical
                or record.get("rows") != table.num_rows
            ):
                raise ValueError(f"canonical table bytes or regeneration proof drifted: {key}")
            checks = quality_record.get("checks")
            if (
                not isinstance(checks, list)
                or any(
                    not isinstance(check, dict) or check.get("status") != "PASS" for check in checks
                )
                or quality_record.get("dropped_duplicate_open_timestamps") != 0
            ):
                raise ValueError(f"canonical table quality evidence is not PASS: {key}")
            verified[key] = dict(record)
    return {
        "manifest": manifest,
        "tables": verified,
        "proof": {
            "dataset_manifest_path": str(manifest_path),
            "dataset_manifest_sha256": _sha256(manifest_path),
            "raw_manifest_sha256": _sha256(raw_manifest_path),
            "quality_report_path": str(quality_path),
            "quality_report_sha256": _sha256(quality_path),
            "regeneration_runs": 2,
            "identical_content_hashes": True,
        },
    }


def verify_raw_proof(
    one_minute_manifest: Path,
    *,
    paths: FreezePaths = DEFAULT_PATHS,
    scope: FreezeScope = FIXED_SCOPE,
) -> dict[str, Any]:
    """Verify retained bytes against exact official-checksum proof before normalization."""
    one_minute_manifest = _content_addressed_one_minute_manifest(
        one_minute_manifest, paths.one_minute_manifest_root
    )
    canonical_authority = _verify_canonical_authority(paths=paths, scope=scope)
    expected_1m = {
        _expected_rel(symbol, "1m", month)
        for symbol in scope.symbols
        for month in scope.month_values
        if "1m" in scope.timeframes
    }
    one = _load_object(one_minute_manifest)
    required_scope = {
        "symbols": list(scope.symbols),
        "timeframes": ["1m"],
        "planned_file_count": len(expected_1m),
        "require_official_checksums": True,
    }
    if one.get("dataset_id") != "DS-CRYPTO-MULTI-V1" or one.get("kinds") != ["klines"]:
        raise ValueError("1m proof is not a DS-CRYPTO-MULTI-V1 klines manifest")
    if one.get("window") != {"start": scope.start_month, "end": scope.end_month}:
        raise ValueError("1m proof window does not match the fixed freeze scope")
    if one.get("scope") != required_scope:
        raise ValueError("1m proof selectors do not match the fixed freeze scope")
    entries = one.get("files")
    if not isinstance(entries, list) or len(entries) != len(expected_1m):
        raise ValueError(f"1m proof must contain exactly {len(expected_1m)} files")
    seen: set[str] = set()
    verified_1m: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("rel"), str):
            raise ValueError("malformed 1m proof entry")
        rel = entry["rel"]
        if rel in seen or rel not in expected_1m:
            raise ValueError(f"unexpected or duplicate 1m proof entry: {rel}")
        seen.add(rel)
        digest = entry.get("sha256")
        if (
            entry.get("checksum_verified") is not True
            or not isinstance(digest, str)
            or entry.get("official_sha256") != digest
        ):
            raise ValueError(f"1m file lacks exact official checksum proof: {rel}")
        local = _confined_regular(paths.multi_raw_root, Path(rel), label="retained 1m archive")
        if (
            not local.is_file()
            or local.stat().st_size != entry.get("size")
            or _sha256(local) != digest
        ):
            raise ValueError(f"1m retained bytes do not match proof: {rel}")
        verified_1m.append({"path": rel, "size": local.stat().st_size, "sha256": digest})
    if seen != expected_1m:
        raise ValueError("1m proof grid is incomplete")

    bakeoff = _load_object(paths.bakeoff_raw_manifest)
    if bakeoff.get("dataset_id") != "DS-CRYPTO-SPOT-BAKEOFF-V1":
        raise ValueError("unexpected canonical bake-off raw dataset")
    index: dict[str, dict[str, Any]] = {}
    for entry in bakeoff.get("files", []):
        if isinstance(entry, dict) and isinstance(entry.get("file"), str):
            if entry["file"] in index:
                raise ValueError(f"duplicate canonical raw proof entry: {entry['file']}")
            index[entry["file"]] = entry
    verified_existing: list[dict[str, Any]] = []
    for symbol in scope.symbols:
        for interval in (frame for frame in scope.timeframes if frame in {"5m", "15m"}):
            for month in scope.month_values:
                name = f"{symbol}-{interval}-{month}.zip"
                canonical_rel = f"{symbol}/{interval}/{name}"
                entry = index.get(canonical_rel)
                if entry is None or entry.get("checksum_verified") is not True:
                    raise ValueError(f"canonical checksum proof missing: {canonical_rel}")
                digest = entry.get("sha256")
                canonical = _confined_regular(
                    paths.bakeoff_raw_root,
                    Path(canonical_rel),
                    label="canonical raw archive",
                )
                multi_rel = _expected_rel(symbol, interval, month)
                local = _confined_regular(
                    paths.multi_raw_root, Path(multi_rel), label="retained multi raw archive"
                )
                if not isinstance(digest, str):
                    raise ValueError(f"retained source missing: {multi_rel}")
                if (
                    canonical.stat().st_size != entry.get("size")
                    or local.stat().st_size != entry.get("size")
                    or _sha256(canonical) != digest
                    or _sha256(local) != digest
                ):
                    raise ValueError(f"multi archive differs from canonical proof: {multi_rel}")
                verified_existing.append(
                    {"path": multi_rel, "size": local.stat().st_size, "sha256": digest}
                )
    return {
        "one_minute_manifest": {
            "path": str(one_minute_manifest),
            "sha256": _sha256(one_minute_manifest),
            "official_checksum_verified_files": len(verified_1m),
        },
        "canonical_bakeoff_raw_manifest": {
            "path": str(paths.bakeoff_raw_manifest),
            "sha256": _sha256(paths.bakeoff_raw_manifest),
            "matched_files": len(verified_existing),
        },
        "canonical_bakeoff_authority": canonical_authority["proof"],
        "files": sorted(verified_1m + verified_existing, key=lambda item: item["path"]),
    }


def _code_identity(paths: FreezePaths) -> dict[str, Any]:
    files = []
    for relative in CODE_SURFACE:
        path = paths.repo_root / relative
        if not path.is_file():
            raise ValueError(f"normalization code surface missing: {relative}")
        files.append({"path": relative, "sha256": _sha256(path)})
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=paths.repo_root, capture_output=True, text=True
    )
    state = subprocess.run(
        ["git", "status", "--porcelain", "--", *CODE_SURFACE],
        cwd=paths.repo_root,
        capture_output=True,
        text=True,
    )
    commit_value = commit.stdout.strip() if commit.returncode == 0 else "unknown"
    commit_object = subprocess.run(
        ["git", "cat-file", "-e", f"{commit_value}^{{commit}}"],
        cwd=paths.repo_root,
        capture_output=True,
    )
    return {
        "files": files,
        "git_commit": commit_value,
        "git_commit_valid": bool(
            re.fullmatch(r"[0-9a-f]{40}", commit_value) and commit_object.returncode == 0
        ),
        "git_state": "committed" if state.returncode == 0 and not state.stdout else "modified",
    }


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _early_close_record(pin: EarlyClosePin) -> dict[str, str]:
    symbol, interval, opened, closed, source_path, source_sha256 = pin
    return {
        "instrument": symbol,
        "interval": interval,
        "timestamp_open_utc": opened,
        "close_timestamp_utc": closed,
        "source_path": source_path,
        "source_sha256": source_sha256,
    }


def _close_time_quality(
    table: pa.Table,
    symbol: str,
    interval: str,
    source_files: list[dict[str, Any]],
    *,
    expected_inventory: tuple[EarlyClosePin, ...] | None,
) -> dict[str, Any]:
    """Validate preserved source close times without inventing nominal closes."""
    step = INTERVAL_US[interval]
    source_by_path = {
        str(item.get("path")): item for item in source_files if isinstance(item, dict)
    }
    connection = duckdb.connect()
    try:
        connection.execute("SET TimeZone='UTC'")
        connection.register("bars", table)
        candidates = connection.execute(
            """
            SELECT
              epoch_us(timestamp_open_utc) AS opened_us,
              epoch_us(close_timestamp_utc) AS closed_us,
              epoch_us(close_timestamp_utc) - epoch_us(timestamp_open_utc) AS duration_us
            FROM bars
            WHERE epoch_us(close_timestamp_utc) - epoch_us(timestamp_open_utc)
                  NOT IN (?, ?)
            ORDER BY timestamp_open_utc
            """,
            [step - 1000, step - 1],
        ).fetchall()
    finally:
        connection.close()

    anomalies: list[dict[str, Any]] = []
    invalid_rows: list[dict[str, Any]] = []
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    for opened_us, closed_us, duration_us in candidates:
        opened_text = _utc_text(epoch + timedelta(microseconds=int(opened_us)))
        closed_text = _utc_text(epoch + timedelta(microseconds=int(closed_us)))
        duration = int(duration_us)
        row = {
            "instrument": symbol,
            "interval": interval,
            "timestamp_open_utc": opened_text,
            "close_timestamp_utc": closed_text,
            "duration_us": duration,
        }
        if duration < 0:
            invalid_rows.append({**row, "violation": "close_before_open"})
            continue
        if duration >= step:
            invalid_rows.append({**row, "violation": "close_at_or_after_next_open"})
            continue
        month = opened_text[:7]
        source_path = _expected_rel(symbol, interval, month)
        source = source_by_path.get(source_path)
        source_sha256 = source.get("sha256") if source is not None else None
        anomalies.append(
            {
                **row,
                "source_path": source_path,
                "source_sha256": source_sha256,
            }
        )

    source_mapping_failures = [
        item
        for item in anomalies
        if not isinstance(item["source_sha256"], str)
        or re.fullmatch(r"[0-9a-f]{64}", item["source_sha256"]) is None
    ]
    actual_records = [
        {
            key: item[key]
            for key in (
                "instrument",
                "interval",
                "timestamp_open_utc",
                "close_timestamp_utc",
                "source_path",
                "source_sha256",
            )
        }
        for item in anomalies
    ]
    expected_records = (
        [_early_close_record(pin) for pin in expected_inventory]
        if expected_inventory is not None
        else []
    )
    actual_by_key = {
        (item["instrument"], item["interval"], item["timestamp_open_utc"]): item
        for item in actual_records
    }
    expected_by_key = {
        (item["instrument"], item["interval"], item["timestamp_open_utc"]): item
        for item in expected_records
    }
    missing = [
        expected_by_key[key] for key in sorted(expected_by_key.keys() - actual_by_key.keys())
    ]
    unexpected = [
        actual_by_key[key] for key in sorted(actual_by_key.keys() - expected_by_key.keys())
    ]
    changed = [
        {"expected": expected_by_key[key], "actual": actual_by_key[key]}
        for key in sorted(expected_by_key.keys() & actual_by_key.keys())
        if expected_by_key[key] != actual_by_key[key]
    ]
    inventory_enforced = expected_inventory is not None
    inventory_pass = not inventory_enforced or not (missing or unexpected or changed)
    passed = not invalid_rows and not source_mapping_failures and inventory_pass
    return {
        "semantic_label": CLOSE_TIME_SEMANTIC_LABEL,
        "status": "PASS" if passed else "FAIL",
        "bounds": "timestamp_open_utc <= close_timestamp_utc < next_interval_boundary",
        "normal_terminal_forms_us": [step - 1000, step - 1],
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "invalid_count": len(invalid_rows),
        "invalid_rows": invalid_rows,
        "source_mapping_failure_count": len(source_mapping_failures),
        "inventory": {
            "status": (
                "NOT_ENFORCED" if not inventory_enforced else ("PASS" if inventory_pass else "FAIL")
            ),
            "expected_count": len(expected_records) if inventory_enforced else None,
            "missing_count": len(missing),
            "unexpected_count": len(unexpected),
            "changed_count": len(changed),
            "missing": missing,
            "unexpected": unexpected,
            "changed": changed,
        },
    }


def _table_quality(
    path: Path,
    symbol: str,
    interval: str,
    cutoff: datetime,
    expected_first_open: datetime,
    expected_last_open: datetime,
    normalization_info: dict[str, Any],
    *,
    require_publication_fsync: bool,
    expected_early_closes: tuple[EarlyClosePin, ...] | None,
) -> dict[str, Any]:
    table = pyarrow.parquet.read_table(path)
    failures: list[str] = []
    if table.schema != CANONICAL_SCHEMA:
        failures.append("canonical_schema")
    if table.schema.metadata:
        failures.append("schema_metadata")
    if table.num_rows == 0:
        failures.append("nonempty")
    nulls = sum(column.null_count for column in table.columns)
    if nulls:
        failures.append("no_nulls")
    step = INTERVAL_US[interval]
    connection = duckdb.connect()
    try:
        connection.execute("SET TimeZone='UTC'")
        connection.register("bars", table)
        basic = connection.execute(
            """
            SELECT
              count(*) FILTER (
                WHERE instrument != ? OR interval != ? OR source != ?
              ) AS bad_identity,
              count(*) FILTER (WHERE low > open OR low > close OR high < open OR high < close
                                      OR low > high) AS bad_ohlc,
              count(*) FILTER (WHERE volume_base < 0 OR quote_volume < 0 OR trade_count < 0
                                      OR taker_buy_base_volume < 0
                                      OR taker_buy_quote_volume < 0) AS bad_volume,
              count(*) FILTER (WHERE epoch_us(timestamp_open_utc) % ? != 0) AS bad_alignment,
              count(*) FILTER (WHERE close_timestamp_utc > ?) AS open_candles
            FROM bars
            """,
            [symbol, interval, SOURCE_TAG, step, cutoff],
        ).fetchone()
    finally:
        connection.close()
    assert basic is not None
    opens_us: list[int] = table.column("timestamp_open_utc").cast(pa.int64()).to_pylist()
    deltas = [right - left for left, right in zip(opens_us[:-1], opens_us[1:], strict=True)]
    bad_steps = sum(1 for delta in deltas if delta <= 0 or delta % step)
    gaps = [delta for delta in deltas if delta > step]
    labels = (
        "row_identity",
        "ohlc_invariants",
        "nonnegative_volumes",
        "interval_alignment",
        "closed_by_cutoff",
    )
    failures.extend(label for label, count in zip(labels, basic, strict=True) if int(count))
    if bad_steps:
        failures.append("monotonic_unique_exact_spacing")
    timezone_ok = all(
        table.schema.field(name).type.tz == "UTC"
        for name in ("timestamp_open_utc", "close_timestamp_utc")
    )
    if not timezone_ok:
        failures.append("utc_timestamps")
    actual_bytes = _sha256(path)
    actual_logical = _parquet_logical_content_sha256(table)
    if normalization_info.get("rows") != table.num_rows:
        failures.append("reported_rows")
    if normalization_info.get("parquet_sha256") != actual_bytes:
        failures.append("reported_parquet_sha256")
    if normalization_info.get("content_sha256") != actual_logical:
        failures.append("reported_content_sha256")
    if (
        require_publication_fsync
        and normalization_info.get("parquet_directory_fsync") != "CONFIRMED"
    ):
        failures.append("parquet_directory_fsync")
    if normalization_info.get("dropped_duplicate_open_timestamps") != 0:
        failures.append("dropped_duplicate_open_timestamps")
    if normalization_info.get("missing_months"):
        failures.append("source_month_coverage")
    if len(normalization_info.get("source_files", [])) != len(
        normalization_info.get("file_unit_detections", [])
    ):
        failures.append("source_detection_coverage")
    opens = table.column("timestamp_open_utc")
    closes = table.column("close_timestamp_utc")
    first_open = opens[0].as_py() if table.num_rows else None
    last_open = opens[-1].as_py() if table.num_rows else None
    if first_open != expected_first_open:
        failures.append("exact_coverage_start")
    if last_open != expected_last_open:
        failures.append("exact_coverage_end")
    detections = normalization_info.get("file_unit_detections", [])
    source_files = normalization_info.get("source_files", [])
    close_time = _close_time_quality(
        table,
        symbol,
        interval,
        source_files,
        expected_inventory=expected_early_closes,
    )
    if close_time["status"] != "PASS":
        failures.append("close_time_semantics")
    expected_months = [
        month
        for month in months(
            (expected_first_open.year, expected_first_open.month),
            (expected_last_open.year, expected_last_open.month),
        )
    ]
    expected_detection_files = {f"{symbol}-{interval}-{month}.zip" for month in expected_months}
    if (
        len(detections) != len(expected_months)
        or {item.get("file") for item in detections if isinstance(item, dict)}
        != expected_detection_files
        or any(
            not isinstance(item, dict)
            or item.get("detected_unit") != item.get("expected_unit")
            or not isinstance(item.get("rows"), int)
            or item["rows"] <= 0
            for item in detections
        )
    ):
        failures.append("file_unit_detection_coverage")
    detection_rows = sum(
        int(item["rows"])
        for item in detections
        if isinstance(item, dict) and isinstance(item.get("rows"), int)
    )
    dropped = normalization_info.get("dropped_duplicate_open_timestamps")
    if not isinstance(dropped, int) or detection_rows - dropped != table.num_rows:
        failures.append("source_row_accounting")
    expected_sources = {_expected_rel(symbol, interval, month) for month in expected_months}
    if {item.get("path") for item in source_files if isinstance(item, dict)} != expected_sources:
        failures.append("source_file_mapping")
    connection = duckdb.connect()
    try:
        connection.execute("SET TimeZone='UTC'")
        connection.register("bars", table)
        month_rows = connection.execute(
            """
            SELECT strftime(timestamp_open_utc, '%Y-%m') AS month, count(*) AS rows
            FROM bars GROUP BY month ORDER BY month
            """
        ).fetchall()
    finally:
        connection.close()
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "rows": table.num_rows,
        "schema": str(table.schema),
        "coverage_start_utc": str(first_open) if first_open is not None else None,
        "coverage_end_utc": str(last_open) if last_open is not None else None,
        "last_close_utc": str(closes[-1].as_py()) if table.num_rows else None,
        "gap_count": len(gaps),
        "missing_bars_total": sum(delta // step - 1 for delta in gaps),
        "null_values": nulls,
        "parquet_sha256": actual_bytes,
        "content_sha256": actual_logical,
        "close_time_semantics": close_time,
        "row_counts_by_month": {str(month): int(rows) for month, rows in month_rows},
        "dropped_duplicate_open_timestamps": normalization_info.get(
            "dropped_duplicate_open_timestamps"
        ),
        "file_unit_detections": detections,
        "source_files": source_files,
    }


def validate_run(
    stage: Path,
    normalized: dict[str, dict[str, Any]],
    *,
    paths: FreezePaths,
    scope: FreezeScope,
    require_publication_fsync: bool = True,
) -> dict[str, Any]:
    """Validate one staged regeneration without retaining all six tables in memory."""
    stage = _require_real_directory(stage, label="short-frame table directory")
    files = {path.stem for path in stage.iterdir() if path.name.endswith(".parquet")}
    if files != scope.keys or set(normalized) != scope.keys:
        raise ValueError("staged short-frame grid is incomplete or contains extras")
    canonical_tables = _verify_canonical_authority(paths=paths, scope=scope)["tables"]
    results: dict[str, Any] = {}
    schemas: set[str] = set()
    enforce_production_inventory = scope == FIXED_SCOPE
    for symbol in scope.symbols:
        for interval in scope.timeframes:
            key = f"{symbol}_{interval}"
            table_path = _confined_regular(stage, Path(f"{key}.parquet"), label=f"table {key}")
            expected_early_closes = (
                tuple(
                    pin for pin in EARLY_CLOSE_INVENTORY if pin[0] == symbol and pin[1] == interval
                )
                if enforce_production_inventory
                else None
            )
            result = _table_quality(
                table_path,
                symbol,
                interval,
                scope.cutoff_utc,
                datetime.fromisoformat(f"{scope.start_month}-01T00:00:00+00:00"),
                scope.cutoff_utc - timedelta(seconds=Timeframe(interval).seconds),
                normalized[key],
                require_publication_fsync=require_publication_fsync,
                expected_early_closes=expected_early_closes,
            )
            if len(normalized[key].get("source_files", [])) != len(scope.month_values):
                result["failures"].append("source_month_coverage")
                result["status"] = "FAIL"
            schemas.add(result["schema"])
            if interval in {"5m", "15m"}:
                reference = canonical_tables.get(key)
                if not isinstance(reference, dict):
                    result["failures"].append("canonical_bakeoff_table_missing")
                else:
                    if result["content_sha256"] != reference.get("content_sha256"):
                        result["failures"].append("canonical_bakeoff_logical_mismatch")
                result["status"] = "PASS" if not result["failures"] else "FAIL"
            results[key] = result
    schema_ok = len(schemas) == 1 and next(iter(schemas), "") == str(CANONICAL_SCHEMA)
    overall = schema_ok and all(item["status"] == "PASS" for item in results.values())
    report = {
        "overall": "PASS" if overall else "FAIL",
        "exact_table_grid": "PASS",
        "schema_identical": "PASS" if schema_ok else "FAIL",
        "cutoff_utc": scope.cutoff_utc.isoformat(),
        "tables": results,
        "gaps_are_informational_and_not_filled": True,
    }
    if not overall:
        failed_tables = {
            key: {
                "failures": value["failures"],
                "close_time_semantics": {
                    "anomaly_count": value["close_time_semantics"]["anomaly_count"],
                    "invalid_count": value["close_time_semantics"]["invalid_count"],
                    "inventory": {
                        count: value["close_time_semantics"]["inventory"][count]
                        for count in ("missing_count", "unexpected_count", "changed_count")
                    },
                },
            }
            for key, value in results.items()
            if value["status"] != "PASS"
        }
        summary = {
            "schema_identical": report["schema_identical"],
            "failed_tables": failed_tables,
        }
        raise ValueError(
            f"short-frame quality gate failed: "
            f"{json.dumps(summary, sort_keys=True, separators=(',', ':'))}"
        )
    return report


def _regenerate(
    stage: Path, *, paths: FreezePaths, scope: FreezeScope
) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for symbol in scope.symbols:
        for interval in scope.timeframes:
            info = normalize_multi.normalize_pair(
                symbol,
                interval,
                output_root=stage,
                raw_root=paths.multi_raw_root,
                selected_months=scope.month_values,
            )
            if info is None:
                raise ValueError(f"no raw data for required coordinate: {symbol}_{interval}")
            normalized[f"{symbol}_{interval}"] = info
    return normalized


def _require_deterministic(run1: dict[str, Any], run2: dict[str, Any]) -> dict[str, str]:
    hashes1 = {key: value["content_sha256"] for key, value in run1["tables"].items()}
    hashes2 = {key: value["content_sha256"] for key, value in run2["tables"].items()}
    if hashes1 != hashes2:
        raise ValueError("double regeneration produced nondeterministic logical content")
    return hashes2


def _existing_output_info(
    output_root: Path, fresh: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Describe existing physical files while retaining fresh source-lineage metadata."""
    described: dict[str, dict[str, Any]] = {}
    for key, fresh_info in fresh.items():
        path = _confined_regular(
            output_root, Path(f"{key}.parquet"), label=f"existing output table {key}"
        )
        table = pyarrow.parquet.read_table(path)
        info = dict(fresh_info)
        info["rows"] = table.num_rows
        info["parquet_sha256"] = _sha256(path)
        info["content_sha256"] = _parquet_logical_content_sha256(table)
        described[key] = info
    return described


def _disk_anchor(path: Path) -> Path:
    candidate = path
    while not candidate.exists():
        if candidate.parent == candidate:
            raise ValueError(f"no existing disk anchor for {path}")
        candidate = candidate.parent
    return candidate


def require_disk_headroom(paths: FreezePaths, proof: dict[str, Any]) -> dict[str, int]:
    source_bytes = sum(int(item["size"]) for item in proof["files"])
    required = max(1024**3, source_bytes * 6)
    free = shutil.disk_usage(_disk_anchor(paths.output_root.parent)).free
    if free < required:
        raise RuntimeError(f"insufficient disk headroom: required={required} free={free}")
    return {"source_bytes": source_bytes, "required_free_bytes": required, "free_bytes": free}


def _prepare_publication_roots(paths: FreezePaths) -> None:
    normalized_root = _prepare_real_directory(
        paths.normalized_root, label="short-frame normalized root"
    )
    expected_output = normalized_root / DATASET_ID
    if paths.output_root.absolute() != expected_output:
        raise ValueError("short-frame output root is not the exact fixed dataset directory")
    if expected_output.exists() or expected_output.is_symlink():
        _require_real_directory(expected_output, label="existing short-frame dataset directory")
    _prepare_real_directory(paths.report_root, label="short-frame artifact root")


@contextmanager
def _process_lock(target: Path) -> Iterator[None]:
    identity = hashlib.sha256(os.fsencode(target.resolve())).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / f"tios-daily-update-{identity}.lock"
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("short-frame freeze is already running") from error
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _fsync_directory(path: Path) -> bool:
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        return False
    return True


def _atomic_write(path: Path, content: bytes) -> None:
    _require_real_directory(path.parent, label="artifact parent directory")
    if path.exists() or path.is_symlink():
        _require_regular_file(path, label="existing artifact")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        if not _fsync_directory(path.parent):
            raise RuntimeError(f"directory fsync failed after publishing {path}")
    finally:
        temporary.unlink(missing_ok=True)


def _publish_json(root: Path, stem: str, payload: dict[str, Any]) -> tuple[Path, Path, str]:
    root = _require_real_directory(root, label="short-frame artifact root")
    encoded = _canonical_json(payload)
    digest = hashlib.sha256(encoded).hexdigest()
    archived = root / f"{stem}_{digest}.json"
    current = root / f"{stem}.json"
    if archived.exists() or archived.is_symlink():
        _require_regular_file(archived, label="content-addressed artifact")
        if archived.read_bytes() != encoded:
            raise ValueError(f"content-addressed artifact is corrupt: {archived}")
    else:
        _atomic_write(archived, encoded)
    _atomic_write(current, encoded)
    return archived, current, digest


def _result(
    paths: FreezePaths,
    *,
    quality_sha: str,
    manifest_sha: str,
    status: str,
) -> dict[str, Any]:
    quality_current = paths.report_root / f"{DATASET_ID}.QUALITY_REPORT.json"
    manifest_current = paths.report_root / f"{DATASET_ID}.manifest.json"
    return {
        "status": status,
        "dataset_root": str(paths.output_root),
        "quality_report": str(quality_current),
        "quality_report_archive": str(
            paths.report_root / f"{DATASET_ID}.QUALITY_REPORT_{quality_sha}.json"
        ),
        "quality_report_sha256": quality_sha,
        "manifest": str(manifest_current),
        "manifest_archive": str(paths.report_root / f"{DATASET_ID}.manifest_{manifest_sha}.json"),
        "manifest_sha256": manifest_sha,
        "execution_authority": "NONE",
    }


def _verified_completed_result(
    *,
    paths: FreezePaths,
    scope: FreezeScope,
    proof: dict[str, Any],
    code: dict[str, Any],
    output_quality: dict[str, Any],
) -> dict[str, Any] | None:
    report_root = _require_real_directory(paths.report_root, label="short-frame artifact root")
    if not _fsync_directory(report_root):
        raise RuntimeError("artifact root fsync failed during recovery verification")
    quality_path = paths.report_root / f"{DATASET_ID}.QUALITY_REPORT.json"
    manifest_path = paths.report_root / f"{DATASET_ID}.manifest.json"
    if not quality_path.exists() or not manifest_path.exists():
        return None
    quality_path = _require_regular_file(quality_path, label="current short-frame quality report")
    manifest_path = _require_regular_file(manifest_path, label="current short-frame manifest")
    quality = _load_object(quality_path)
    manifest = _load_object(manifest_path)
    quality_sha = _sha256(quality_path)
    manifest_sha = _sha256(manifest_path)
    scope_record = {
        "symbols": list(scope.symbols),
        "timeframes": list(scope.timeframes),
        "window": {"start": scope.start_month, "end": scope.end_month},
    }
    if (
        quality.get("dataset_id") != DATASET_ID
        or quality.get("overall") != "PASS"
        or quality.get("raw_proof") != proof
        or quality.get("code_identity") != code
        or quality.get("quality_run2") != output_quality
        or manifest.get("dataset_id") != DATASET_ID
        or manifest.get("scope") != scope_record
        or manifest.get("cutoff_utc") != scope.cutoff_utc.isoformat()
        or manifest.get("raw_proof") != proof
        or manifest.get("code_identity") != code
        or manifest.get("tables") != output_quality["tables"]
        or manifest.get("quality_report_sha256") != quality_sha
        or manifest.get("execution_authority") != "NONE"
    ):
        raise ValueError("existing short-frame artifacts do not bind the verified output")
    quality_archive = paths.report_root / f"{DATASET_ID}.QUALITY_REPORT_{quality_sha}.json"
    manifest_archive = paths.report_root / f"{DATASET_ID}.manifest_{manifest_sha}.json"
    if not quality_archive.exists() or not manifest_archive.exists():
        return None
    quality_archive = _require_regular_file(
        quality_archive, label="content-addressed quality report"
    )
    manifest_archive = _require_regular_file(
        manifest_archive, label="content-addressed dataset manifest"
    )
    if _sha256(quality_archive) != quality_sha or _sha256(manifest_archive) != manifest_sha:
        raise ValueError("content-addressed short-frame artifacts drifted")
    return _result(
        paths,
        quality_sha=quality_sha,
        manifest_sha=manifest_sha,
        status="VERIFIED_EXISTING",
    )


def _freeze(
    one_minute_manifest: Path,
    *,
    paths: FreezePaths,
    scope: FreezeScope,
    require_committed_code: bool = True,
) -> dict[str, Any]:
    proof = verify_raw_proof(one_minute_manifest, paths=paths, scope=scope)
    disk = require_disk_headroom(paths, proof)
    code = _code_identity(paths)
    if require_committed_code and (
        code.get("git_state") != "committed" or code.get("git_commit_valid") is not True
    ):
        raise RuntimeError("production freeze requires a valid committed code identity")
    _prepare_publication_roots(paths)
    stage1 = Path(tempfile.mkdtemp(prefix=f".{DATASET_ID}.run1.", dir=paths.output_root.parent))
    stage2: Path | None = Path(
        tempfile.mkdtemp(prefix=f".{DATASET_ID}.run2.", dir=paths.output_root.parent)
    )
    try:
        run1_norm = _regenerate(stage1, paths=paths, scope=scope)
        if verify_raw_proof(one_minute_manifest, paths=paths, scope=scope) != proof:
            raise ValueError("raw proof changed during first regeneration")
        run1 = validate_run(stage1, run1_norm, paths=paths, scope=scope)
        assert stage2 is not None
        run2_norm = _regenerate(stage2, paths=paths, scope=scope)
        if verify_raw_proof(one_minute_manifest, paths=paths, scope=scope) != proof:
            raise ValueError("raw proof changed during second regeneration")
        run2 = validate_run(stage2, run2_norm, paths=paths, scope=scope)
        hashes1 = {key: value["content_sha256"] for key, value in run1["tables"].items()}
        hashes2 = _require_deterministic(run1, run2)
        if _code_identity(paths) != code:
            raise ValueError("normalization code or Git identity changed during freeze")
        if paths.output_root.exists():
            existing_info = _existing_output_info(paths.output_root, run2_norm)
            output_quality = validate_run(
                paths.output_root,
                existing_info,
                paths=paths,
                scope=scope,
                require_publication_fsync=False,
            )
            if {
                key: value["content_sha256"] for key, value in output_quality["tables"].items()
            } != hashes2:
                raise ValueError("existing frozen output differs from fresh regeneration")
            if not _fsync_directory(paths.output_root.parent):
                raise RuntimeError("normalized parent fsync failed during recovery verification")
            completed = _verified_completed_result(
                paths=paths,
                scope=scope,
                proof=proof,
                code=code,
                output_quality=output_quality,
            )
            if completed is not None:
                return completed
        else:
            assert stage2 is not None
            os.replace(stage2, paths.output_root)
            stage2 = None
            if not _fsync_directory(paths.output_root.parent):
                raise RuntimeError("dataset directory publication fsync failed")
            output_quality = run2
        generated = datetime.now(tz=UTC).isoformat()
        report: dict[str, Any] = {
            "schema_version": 1,
            "dataset_id": DATASET_ID,
            "generated_utc": generated,
            "overall": "PASS",
            "scope": {
                "symbols": list(scope.symbols),
                "timeframes": list(scope.timeframes),
                "window": {"start": scope.start_month, "end": scope.end_month},
            },
            "raw_proof": proof,
            "disk_preflight": disk,
            "code_identity": code,
            "double_regeneration": {
                "status": "PASS",
                "run1_logical_hashes": hashes1,
                "run2_logical_hashes": hashes2,
            },
            "quality_run1": run1,
            "quality_run2": output_quality,
            "execution_authority": "NONE",
            "limitation": "Data quality is not evidence of strategy validity or profitability.",
        }
        report_bytes = _canonical_json(report)
        report_sha = hashlib.sha256(report_bytes).hexdigest()
        manifest: dict[str, Any] = {
            "schema_version": 1,
            "dataset_id": DATASET_ID,
            "generated_utc": generated,
            "lineage_status": "recorded_at_normalization",
            "scope": report["scope"],
            "cutoff_utc": scope.cutoff_utc.isoformat(),
            "raw_proof": proof,
            "quality_report_sha256": report_sha,
            "code_identity": code,
            "tables": output_quality["tables"],
            "execution_authority": "NONE",
            "limitation": "Data quality is not evidence of strategy validity or profitability.",
        }
        quality_archive, quality_current, actual_report_sha = _publish_json(
            paths.report_root, f"{DATASET_ID}.QUALITY_REPORT", report
        )
        if actual_report_sha != report_sha:
            raise AssertionError("quality report hash changed during publication")
        manifest_archive, manifest_current, manifest_sha = _publish_json(
            paths.report_root, f"{DATASET_ID}.manifest", manifest
        )
        if not _fsync_directory(paths.report_root):
            raise RuntimeError("artifact root fsync failed after publication")
        published = _result(
            paths,
            quality_sha=report_sha,
            manifest_sha=manifest_sha,
            status="PUBLISHED_OR_RECOVERED",
        )
        assert quality_archive == Path(published["quality_report_archive"])
        assert quality_current == Path(published["quality_report"])
        assert manifest_archive == Path(published["manifest_archive"])
        assert manifest_current == Path(published["manifest"])
        return published
    finally:
        shutil.rmtree(stage1, ignore_errors=True)
        if stage2 is not None:
            shutil.rmtree(stage2, ignore_errors=True)


def freeze_shortframes(
    one_minute_manifest: Path, *, paths: FreezePaths = DEFAULT_PATHS
) -> dict[str, Any]:
    """Run the fixed production freeze under a same-dataset interprocess lock."""
    with _process_lock(paths.output_root):
        return _freeze(one_minute_manifest, paths=paths, scope=FIXED_SCOPE)


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze the fixed BTC/ETH short-frame dataset")
    parser.add_argument(
        "--one-minute-manifest",
        type=Path,
        required=True,
        help="explicit filtered, official-checksum-required 1m acquisition manifest",
    )
    args = parser.parse_args()
    result = freeze_shortframes(args.one_minute_manifest)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
