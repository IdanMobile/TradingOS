"""Read-only frozen short-frame snapshot verification."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import shutil
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from tios.dataset import normalize
from tios.dataset import shortframe_snapshot_verify as snapshot

D = Decimal


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _git(root: Path, *arguments: str, text: bool = True) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=text,
        check=True,
    )


def _initialize_git(root: Path) -> tuple[str, dict[str, str]]:
    root.mkdir()
    _git(root, "init", "-q", "--object-format=sha1")
    for relative in sorted(snapshot.EXPECTED_CODE_PATHS):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# historical fixture blob: {relative}\n", encoding="utf-8")
    _git(root, "add", "--", *sorted(snapshot.EXPECTED_CODE_PATHS))
    _git(
        root,
        "-c",
        "user.name=Snapshot Fixture",
        "-c",
        "user.email=snapshot@example.invalid",
        "-c",
        "commit.gpgSign=false",
        "commit",
        "-qm",
        "fixture code identity",
    )
    commit = _git(root, "rev-parse", "HEAD").stdout.strip()
    assert len(commit) == 40
    hashes = {
        relative: hashlib.sha256(
            _git(root, "cat-file", "blob", f"{commit}:{relative}", text=False).stdout
        ).hexdigest()
        for relative in sorted(snapshot.EXPECTED_CODE_PATHS)
    }
    return commit, hashes


def _rows(symbol: str, timeframe: str) -> list[dict[str, Any]]:
    minutes = {"1m": 1, "5m": 5, "15m": 15}[timeframe]
    base = D("100") if symbol == "BTCUSDT" else D("200")
    rows: list[dict[str, Any]] = []
    for month in (1, 2, 3):
        start = datetime(2021, month, 1, tzinfo=UTC)
        for index in range(9):
            opened = start + timedelta(minutes=minutes * index)
            price = base + D(month) + D(index) / D(10)
            rows.append(
                {
                    "timestamp_open_utc": opened,
                    "open": price,
                    "high": price + D("1.00000000"),
                    "low": price - D("1.00000000"),
                    "close": price + D("0.10000000"),
                    "volume_base": D("1.00000000"),
                    "close_timestamp_utc": (
                        opened + timedelta(minutes=minutes) - timedelta(milliseconds=1)
                    ),
                    "quote_volume": D("2.00000000"),
                    "trade_count": index + 1,
                    "taker_buy_base_volume": D("0.40000000"),
                    "taker_buy_quote_volume": D("0.80000000"),
                    "source": "fixture",
                    "instrument": symbol,
                    "interval": timeframe,
                }
            )
    return rows


def _publish_pair(
    evidence_root: Path, prefix: str, value: dict[str, Any]
) -> tuple[Path, Path, str]:
    payload = _canonical(value)
    digest = hashlib.sha256(payload).hexdigest()
    stable = evidence_root / f"{prefix}.json"
    archive = evidence_root / f"{prefix}_{digest}.json"
    stable.write_bytes(payload)
    archive.write_bytes(payload)
    return stable, archive, digest


@dataclass
class Fixture:
    root: Path
    paths: snapshot._SnapshotPaths
    manifest: dict[str, Any]
    quality: dict[str, Any]

    @property
    def dataset_root(self) -> Path:
        return self.root / "data" / "normalized" / snapshot.DATASET_ID

    @property
    def evidence_root(self) -> Path:
        return self.root / "artifacts" / "datasets"

    @property
    def manifest_archive(self) -> Path:
        return self.evidence_root / self.paths.manifest_archive_name

    def republish(self) -> snapshot._SnapshotPaths:
        _, _, quality_sha = _publish_pair(
            self.evidence_root, f"{snapshot.DATASET_ID}.QUALITY_REPORT", self.quality
        )
        _, _, manifest_sha = _publish_pair(
            self.evidence_root, f"{snapshot.DATASET_ID}.manifest", self.manifest
        )
        self.paths = snapshot._SnapshotPaths(
            root=self.root,
            expected_manifest_sha256=manifest_sha,
            expected_quality_sha256=quality_sha,
        )
        return self.paths

    def bind_quality(self) -> snapshot._SnapshotPaths:
        paths = self.republish()
        self.manifest["quality_report_sha256"] = paths.expected_quality_sha256
        return self.republish()

    def update_table_byte_hash(self, key: str) -> snapshot._SnapshotPaths:
        digest = _sha256(self.dataset_root / f"{key}.parquet")
        self.manifest["tables"][key]["parquet_sha256"] = digest
        for run_name in ("quality_run1", "quality_run2"):
            self.quality[run_name]["tables"][key]["parquet_sha256"] = digest
        return self.bind_quality()


@pytest.fixture
def frozen_fixture(tmp_path: Path) -> Fixture:
    root = tmp_path / "fixture-repo"
    commit, code_hashes = _initialize_git(root)
    dataset = root / "data" / "normalized" / snapshot.DATASET_ID
    evidence = root / "artifacts" / "datasets"
    dataset.mkdir(parents=True)
    evidence.mkdir(parents=True)
    records: dict[str, Any] = {}
    for symbol in snapshot.SYMBOLS:
        for timeframe in snapshot.TIMEFRAMES:
            key = f"{symbol}_{timeframe}"
            table = pa.Table.from_pylist(
                _rows(symbol, timeframe), schema=snapshot.FROZEN_V1_ARROW_SCHEMA
            )
            path = dataset / f"{key}.parquet"
            pq.write_table(table, path, row_group_size=4)
            assert pq.ParquetFile(path).metadata.num_row_groups > 1
            records[key] = {
                "status": "PASS",
                "failures": [],
                "rows": table.num_rows,
                "schema": str(snapshot.FROZEN_V1_ARROW_SCHEMA),
                "parquet_sha256": _sha256(path),
                "content_sha256": hashlib.sha256(f"logical:{key}".encode()).hexdigest(),
            }
    code_identity = {
        "files": [{"path": path, "sha256": code_hashes[path]} for path in sorted(code_hashes)],
        "git_commit": commit,
        "git_commit_valid": True,
        "git_state": "committed",
    }
    run = {
        "overall": "PASS",
        "exact_table_grid": "PASS",
        "schema_identical": "PASS",
        "tables": records,
    }
    logical = {key: value["content_sha256"] for key, value in records.items()}
    quality = {
        "schema_version": 1,
        "dataset_id": snapshot.DATASET_ID,
        "overall": "PASS",
        "scope": snapshot.EXPECTED_SCOPE,
        "code_identity": code_identity,
        "quality_run1": deepcopy(run),
        "quality_run2": deepcopy(run),
        "double_regeneration": {
            "status": "PASS",
            "run1_logical_hashes": deepcopy(logical),
            "run2_logical_hashes": deepcopy(logical),
        },
        "execution_authority": "NONE",
    }
    _, _, quality_sha = _publish_pair(evidence, f"{snapshot.DATASET_ID}.QUALITY_REPORT", quality)
    manifest = {
        "schema_version": 1,
        "dataset_id": snapshot.DATASET_ID,
        "lineage_status": "recorded_at_normalization",
        "scope": snapshot.EXPECTED_SCOPE,
        "cutoff_utc": snapshot.EXPECTED_CUTOFF,
        "quality_report_sha256": quality_sha,
        "code_identity": code_identity,
        "tables": records,
        "execution_authority": "NONE",
    }
    _, _, manifest_sha = _publish_pair(evidence, f"{snapshot.DATASET_ID}.manifest", manifest)
    return Fixture(
        root=root,
        paths=snapshot._SnapshotPaths(
            root=root,
            expected_manifest_sha256=manifest_sha,
            expected_quality_sha256=quality_sha,
        ),
        manifest=manifest,
        quality=quality,
    )


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(key).lower() for key in value} | {
            nested for item in value.values() for nested in _all_keys(item)
        }
    if isinstance(value, list):
        return {nested for item in value for nested in _all_keys(item)}
    return set()


def _tree_state(root: Path) -> dict[Path, tuple[Any, ...]]:
    state: dict[Path, tuple[Any, ...]] = {}
    for path in [root, *root.rglob("*")]:
        metadata = path.lstat()
        relative = path.relative_to(root)
        content: str | None = None
        if path.is_file() and not path.is_symlink():
            content = _sha256(path)
        elif path.is_symlink():
            content = os.readlink(path)
        state[relative] = (
            metadata.st_mode,
            metadata.st_nlink,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
            content,
        )
    return state


def test_nonproduction_multi_month_multi_row_group_fixture_passes_without_receipt(
    frozen_fixture: Fixture,
) -> None:
    assert snapshot._verify_nonproduction_fixture(frozen_fixture.paths) is None


def test_public_api_is_no_arg_and_production_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[snapshot._SnapshotPaths] = []

    def capture(paths: snapshot._SnapshotPaths) -> None:
        observed.append(paths)

    monkeypatch.setattr(snapshot, "_verify_at_fixed_snapshot", capture)
    assert list(inspect.signature(snapshot.verify_snapshot).parameters) == []
    result = snapshot.verify_snapshot()
    assert observed == [snapshot._production_paths()]
    assert observed[0].root == snapshot.ROOT
    assert result == {
        "dataset_id": snapshot.DATASET_ID,
        "manifest_sha256": snapshot.EXPECTED_MANIFEST_SHA256,
        "quality_report_sha256": snapshot.EXPECTED_QUALITY_SHA256,
        "status": "PASS",
        "tables_verified": 6,
    }


def test_stable_archive_drift_fails_closed(frozen_fixture: Fixture) -> None:
    frozen_fixture.manifest_archive.write_bytes(b"{}")
    with pytest.raises(snapshot.SnapshotVerificationError, match="stable/archive drift"):
        snapshot._verify_nonproduction_fixture(frozen_fixture.paths)


def test_table_byte_drift_fails_closed(frozen_fixture: Fixture) -> None:
    path = frozen_fixture.dataset_root / "BTCUSDT_1m.parquet"
    with path.open("r+b") as target:
        target.seek(16)
        original = target.read(1)
        target.seek(16)
        target.write(bytes([original[0] ^ 1]))
    with pytest.raises(snapshot.SnapshotVerificationError, match="byte SHA-256 mismatch"):
        snapshot._verify_nonproduction_fixture(frozen_fixture.paths)


def test_missing_grid_entry_fails_closed(frozen_fixture: Fixture) -> None:
    key = "ETHUSDT_15m"
    del frozen_fixture.manifest["tables"][key]
    for run_name in ("quality_run1", "quality_run2"):
        del frozen_fixture.quality[run_name]["tables"][key]
    del frozen_fixture.quality["double_regeneration"]["run1_logical_hashes"][key]
    del frozen_fixture.quality["double_regeneration"]["run2_logical_hashes"][key]
    paths = frozen_fixture.bind_quality()
    with pytest.raises(snapshot.SnapshotVerificationError, match="six-table grid"):
        snapshot._verify_nonproduction_fixture(paths)


def test_manifest_quality_cross_hash_mismatch_fails_closed(frozen_fixture: Fixture) -> None:
    frozen_fixture.manifest["quality_report_sha256"] = "0" * 64
    paths = frozen_fixture.republish()
    with pytest.raises(snapshot.SnapshotVerificationError, match="quality cross-link"):
        snapshot._verify_nonproduction_fixture(paths)


def test_missing_snapshot_file_fails_exact_inventory(frozen_fixture: Fixture) -> None:
    (frozen_fixture.dataset_root / "ETHUSDT_1m.parquet").unlink()
    with pytest.raises(snapshot.SnapshotVerificationError, match="six-file inventory"):
        snapshot._verify_nonproduction_fixture(frozen_fixture.paths)


def test_unexpected_snapshot_file_fails_exact_inventory(frozen_fixture: Fixture) -> None:
    (frozen_fixture.dataset_root / "unexpected.parquet").write_bytes(b"x")
    with pytest.raises(snapshot.SnapshotVerificationError, match="six-file inventory"):
        snapshot._verify_nonproduction_fixture(frozen_fixture.paths)


def test_duplicate_json_table_key_is_refused() -> None:
    payload = b'{"tables":{"BTCUSDT_1m":{},"BTCUSDT_1m":{}}}'
    with pytest.raises(snapshot.SnapshotVerificationError, match="duplicate JSON key"):
        snapshot._strict_object(payload, label="duplicate fixture")


@pytest.mark.parametrize(
    "evidence_name",
    [
        "manifest_stable",
        "manifest_archive",
        "quality_stable",
        "quality_archive",
    ],
)
@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_evidence_links_are_refused(
    frozen_fixture: Fixture,
    evidence_name: str,
    link_kind: str,
) -> None:
    paths = {
        "manifest_stable": (frozen_fixture.evidence_root / f"{snapshot.DATASET_ID}.manifest.json"),
        "manifest_archive": frozen_fixture.manifest_archive,
        "quality_stable": (
            frozen_fixture.evidence_root / f"{snapshot.DATASET_ID}.QUALITY_REPORT.json"
        ),
        "quality_archive": (
            frozen_fixture.evidence_root / frozen_fixture.paths.quality_archive_name
        ),
    }
    target = paths[evidence_name]
    retained = frozen_fixture.root / f"retained-{evidence_name}-{link_kind}.json"
    target.rename(retained)
    if link_kind == "symlink":
        target.symlink_to(retained)
        expected = "non-symlink"
    else:
        os.link(retained, target)
        expected = "hard-link"
    with pytest.raises(snapshot.SnapshotVerificationError, match=expected):
        snapshot._verify_nonproduction_fixture(frozen_fixture.paths)


@pytest.mark.parametrize(
    "parent_name",
    ["root", "data", "normalized", "dataset", "artifacts", "evidence"],
)
def test_each_parent_directory_symlink_is_refused(
    frozen_fixture: Fixture,
    parent_name: str,
) -> None:
    if parent_name == "root":
        alias = frozen_fixture.root.parent / "fixture-repo-alias"
        alias.symlink_to(frozen_fixture.root, target_is_directory=True)
        paths = snapshot._SnapshotPaths(
            root=alias,
            expected_manifest_sha256=frozen_fixture.paths.expected_manifest_sha256,
            expected_quality_sha256=frozen_fixture.paths.expected_quality_sha256,
        )
    else:
        targets = {
            "data": frozen_fixture.root / "data",
            "normalized": frozen_fixture.root / "data" / "normalized",
            "dataset": frozen_fixture.dataset_root,
            "artifacts": frozen_fixture.root / "artifacts",
            "evidence": frozen_fixture.evidence_root,
        }
        target = targets[parent_name]
        retained = frozen_fixture.root / f"retained-parent-{parent_name}"
        target.rename(retained)
        target.symlink_to(retained, target_is_directory=True)
        paths = frozen_fixture.paths
    with pytest.raises(snapshot.SnapshotVerificationError, match="directory path is not real"):
        snapshot._verify_nonproduction_fixture(paths)


def test_symlinked_table_is_refused(frozen_fixture: Fixture) -> None:
    path = frozen_fixture.dataset_root / "BTCUSDT_5m.parquet"
    retained = frozen_fixture.root / "retained-symlink-target.parquet"
    path.rename(retained)
    path.symlink_to(retained)
    with pytest.raises(snapshot.SnapshotVerificationError, match="non-symlink"):
        snapshot._verify_nonproduction_fixture(frozen_fixture.paths)


def test_hardlinked_table_is_refused(frozen_fixture: Fixture) -> None:
    path = frozen_fixture.dataset_root / "ETHUSDT_5m.parquet"
    retained = frozen_fixture.root / "retained-hardlink-target.parquet"
    path.rename(retained)
    os.link(retained, path)
    with pytest.raises(snapshot.SnapshotVerificationError, match="hard-link"):
        snapshot._verify_nonproduction_fixture(frozen_fixture.paths)


def test_parent_swap_race_fails_final_descriptor_revalidation(
    frozen_fixture: Fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = snapshot._AnchoredSnapshot.revalidate

    def swap_parent(anchored: snapshot._AnchoredSnapshot) -> None:
        normalized = frozen_fixture.root / "data" / "normalized"
        retained = frozen_fixture.root / "retained-normalized"
        normalized.rename(retained)
        normalized.mkdir()
        original(anchored)

    monkeypatch.setattr(snapshot._AnchoredSnapshot, "revalidate", swap_parent)
    with pytest.raises(snapshot.SnapshotVerificationError, match="final entry missing|identity"):
        snapshot._verify_nonproduction_fixture(frozen_fixture.paths)


def test_table_replacement_race_fails_final_descriptor_revalidation(
    frozen_fixture: Fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = snapshot._AnchoredSnapshot.revalidate

    def replace_table(anchored: snapshot._AnchoredSnapshot) -> None:
        table = frozen_fixture.dataset_root / "BTCUSDT_15m.parquet"
        retained = frozen_fixture.root / "retained-race-table.parquet"
        table.rename(retained)
        shutil.copyfile(retained, table)
        original(anchored)

    monkeypatch.setattr(snapshot._AnchoredSnapshot, "revalidate", replace_table)
    with pytest.raises(snapshot.SnapshotVerificationError, match="final identity mismatch"):
        snapshot._verify_nonproduction_fixture(frozen_fixture.paths)


def test_inventory_race_fails_final_descriptor_revalidation(
    frozen_fixture: Fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = snapshot._AnchoredSnapshot.revalidate

    def add_inventory_entry(anchored: snapshot._AnchoredSnapshot) -> None:
        (frozen_fixture.dataset_root / "raced.parquet").write_bytes(b"x")
        original(anchored)

    monkeypatch.setattr(snapshot._AnchoredSnapshot, "revalidate", add_inventory_entry)
    with pytest.raises(snapshot.SnapshotVerificationError, match="six-file inventory"):
        snapshot._verify_nonproduction_fixture(frozen_fixture.paths)


def test_inventory_scan_stops_and_fails_at_seventh_entry(
    frozen_fixture: Fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry_names = sorted(f"{key}.parquet" for key in snapshot.EXPECTED_KEYS) + ["seventh-entry"]
    calls = 0

    class Entry:
        def __init__(self, name: str) -> None:
            self.name = name

    class BoundedEntries:
        def __enter__(self) -> BoundedEntries:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def __iter__(self) -> BoundedEntries:
            return self

        def __next__(self) -> Entry:
            nonlocal calls
            if calls >= len(entry_names):
                raise AssertionError("inventory iterator advanced beyond seventh entry")
            entry = Entry(entry_names[calls])
            calls += 1
            return entry

    monkeypatch.setattr(snapshot.os, "scandir", lambda _: BoundedEntries())
    with pytest.raises(snapshot.SnapshotVerificationError, match="six-file inventory"):
        snapshot._verify_nonproduction_fixture(frozen_fixture.paths)
    assert calls == 7


def test_recorded_commit_blob_hash_mismatch_fails_closed(frozen_fixture: Fixture) -> None:
    identity = deepcopy(frozen_fixture.manifest["code_identity"])
    identity["files"][0]["sha256"] = "0" * 64
    frozen_fixture.manifest["code_identity"] = identity
    frozen_fixture.quality["code_identity"] = deepcopy(identity)
    paths = frozen_fixture.bind_quality()
    with pytest.raises(snapshot.SnapshotVerificationError, match="recorded hash mismatch"):
        snapshot._verify_nonproduction_fixture(paths)


def test_missing_recorded_commit_fails_closed(frozen_fixture: Fixture) -> None:
    identity = deepcopy(frozen_fixture.manifest["code_identity"])
    identity["git_commit"] = "f" * 40
    frozen_fixture.manifest["code_identity"] = identity
    frozen_fixture.quality["code_identity"] = deepcopy(identity)
    paths = frozen_fixture.bind_quality()
    with pytest.raises(snapshot.SnapshotVerificationError, match="Git object unavailable"):
        snapshot._verify_nonproduction_fixture(paths)


def test_code_identity_path_traversal_fails_closed(frozen_fixture: Fixture) -> None:
    identity = deepcopy(frozen_fixture.manifest["code_identity"])
    identity["files"][0]["path"] = "../escape.py"
    frozen_fixture.manifest["code_identity"] = identity
    frozen_fixture.quality["code_identity"] = deepcopy(identity)
    paths = frozen_fixture.bind_quality()
    with pytest.raises(snapshot.SnapshotVerificationError, match="unsafe or duplicate path"):
        snapshot._verify_nonproduction_fixture(paths)


def test_git_environment_is_local_only_and_prohibits_other_operations(
    frozen_fixture: Fixture,
) -> None:
    hostile = {
        "PATH": "/hostile/bin",
        "DYLD_INSERT_LIBRARIES": "/hostile.dylib",
        "LD_PRELOAD": "/hostile.so",
        "PYTHONPATH": "/hostile/python",
        "GIT_DIR": "/redirect",
        "GIT_WORK_TREE": "/redirect",
        "GIT_COMMON_DIR": "/redirect",
        "GIT_OBJECT_DIRECTORY": "/redirect",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": "/redirect",
        "GIT_SSH_COMMAND": "helper",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "url.bad.insteadOf",
        "GIT_CONFIG_VALUE_0": "https://example.invalid",
        "SSH_ASKPASS": "helper",
    }
    sanitized = snapshot._git_environment(hostile)
    assert sanitized["GIT_NO_LAZY_FETCH"] == "1"
    assert sanitized["GIT_OPTIONAL_LOCKS"] == "0"
    assert sanitized["GIT_PROTOCOL_FROM_USER"] == "0"
    assert sanitized["GIT_TERMINAL_PROMPT"] == "0"
    assert all(
        key not in sanitized
        for key in (
            "PATH",
            "DYLD_INSERT_LIBRARIES",
            "LD_PRELOAD",
            "PYTHONPATH",
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_COMMON_DIR",
            "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_SSH_COMMAND",
            "GIT_CONFIG_COUNT",
            "GIT_CONFIG_KEY_0",
            "GIT_CONFIG_VALUE_0",
            "SSH_ASKPASS",
        )
    )
    object_spec = (
        frozen_fixture.manifest["code_identity"]["git_commit"] + ":src/tios/dataset/acquire.py"
    )
    command = snapshot._git_command(
        ["cat-file", "-s", object_spec],
        label="environment fixture",
    )
    result = snapshot._git_text(
        frozen_fixture.root,
        ["cat-file", "-s", object_spec],
        label="environment fixture",
    )
    assert int(result) > 0
    assert command[0] == "/usr/bin/git"
    assert "protocol.allow=never" in command
    assert not any(token in command for token in ("fetch", "clone", "remote", "credential"))
    with pytest.raises(snapshot.SnapshotVerificationError, match="prohibited Git operation"):
        snapshot._git_command(["fetch", "origin"], label="network fixture")


def test_oversized_second_git_blob_read_is_bounded_killed_and_reaped(
    frozen_fixture: Fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeProcess:
        def __init__(self) -> None:
            stdout_read, stdout_write = os.pipe()
            stderr_read, stderr_write = os.pipe()
            os.write(stdout_write, b"oversized")
            os.close(stdout_write)
            os.close(stderr_write)
            self.stdout = os.fdopen(stdout_read, "rb", buffering=0)
            self.stderr = os.fdopen(stderr_read, "rb", buffering=0)
            self.returncode: int | None = None
            self.killed = False
            self.reaped = False

        def poll(self) -> int | None:
            return self.returncode

        def kill(self) -> None:
            self.killed = True
            self.returncode = -9

        def wait(self, timeout: float | None = None) -> int:
            del timeout
            self.reaped = True
            if self.returncode is None:
                self.returncode = 0
            return self.returncode

    fake = FakeProcess()
    observed: dict[str, Any] = {}

    def fake_popen(command: list[str], **kwargs: Any) -> FakeProcess:
        observed["command"] = command
        observed["env"] = kwargs["env"]
        return fake

    original_read = snapshot.os.read
    stdout_read_sizes: list[int] = []

    def bounded_read(descriptor: int, size: int) -> bytes:
        if descriptor == fake.stdout.fileno():
            stdout_read_sizes.append(size)
        return original_read(descriptor, size)

    monkeypatch.setattr(snapshot.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(snapshot.os, "read", bounded_read)
    with pytest.raises(snapshot.SnapshotVerificationError, match="stdout bound exceeded"):
        snapshot._read_git_blob_exact(
            frozen_fixture.root,
            "0" * 40 + ":src/tios/dataset/acquire.py",
            expected_size=1,
            label="oversized blob fixture",
        )
    assert fake.killed is True
    assert fake.reaped is True
    assert stdout_read_sizes and max(stdout_read_sizes) <= 2
    assert observed["command"][0] == "/usr/bin/git"
    assert observed["env"]["GIT_NO_LAZY_FETCH"] == "1"
    assert "PATH" not in observed["env"]


def test_fake_git_on_hostile_path_cannot_execute(
    frozen_fixture: Fixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hostile_bin = tmp_path / "hostile-bin"
    hostile_bin.mkdir()
    marker = tmp_path / "fake-git-executed"
    fake_git = hostile_bin / "git"
    fake_git.write_text(
        f"#!/bin/sh\n/usr/bin/touch '{marker}'\nexit 99\n",
        encoding="utf-8",
    )
    fake_git.chmod(0o755)
    monkeypatch.setenv("PATH", str(hostile_bin))
    monkeypatch.setenv("DYLD_INSERT_LIBRARIES", str(tmp_path / "hostile.dylib"))
    monkeypatch.setenv("LD_PRELOAD", str(tmp_path / "hostile.so"))
    assert snapshot._verify_nonproduction_fixture(frozen_fixture.paths) is None
    assert not marker.exists()


def test_nontrusted_git_binary_path_fails_closed(
    frozen_fixture: Fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(snapshot, "_TRUSTED_GIT_BINARY", frozen_fixture.root / "git")
    with pytest.raises(snapshot.SnapshotVerificationError, match="fixed path contract"):
        snapshot._verify_nonproduction_fixture(frozen_fixture.paths)


def test_current_normalizer_schema_substitution_cannot_change_verifier(
    frozen_fixture: Fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replacement = pa.schema([("mutable", pa.int64())])
    monkeypatch.setattr(normalize, "CANONICAL_SCHEMA", replacement)
    assert snapshot.FROZEN_V1_ARROW_SCHEMA != normalize.CANONICAL_SCHEMA
    assert snapshot._verify_nonproduction_fixture(frozen_fixture.paths) is None


def test_parquet_footer_bound_fails_closed(frozen_fixture: Fixture) -> None:
    key = "BTCUSDT_15m"
    path = frozen_fixture.dataset_root / f"{key}.parquet"
    with path.open("r+b") as target:
        target.seek(-8, os.SEEK_END)
        target.write((snapshot.MAX_PARQUET_FOOTER_BYTES + 1).to_bytes(4, "little") + b"PAR1")
    paths = frozen_fixture.update_table_byte_hash(key)
    with pytest.raises(snapshot.SnapshotVerificationError, match="footer bound"):
        snapshot._verify_nonproduction_fixture(paths)


def test_parquet_row_group_bound_fails_closed(
    frozen_fixture: Fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(snapshot, "MAX_ROW_GROUPS", 1)
    with pytest.raises(snapshot.SnapshotVerificationError, match="canonical metadata"):
        snapshot._verify_nonproduction_fixture(frozen_fixture.paths)


def test_parquet_schema_metadata_fails_closed(frozen_fixture: Fixture) -> None:
    key = "ETHUSDT_15m"
    path = frozen_fixture.dataset_root / f"{key}.parquet"
    table = pq.read_table(path).replace_schema_metadata({b"unexpected": b"metadata"})
    pq.write_table(table, path, row_group_size=4)
    paths = frozen_fixture.update_table_byte_hash(key)
    with pytest.raises(snapshot.SnapshotVerificationError, match="canonical metadata"):
        snapshot._verify_nonproduction_fixture(paths)


def test_parquet_row_count_metadata_fails_closed(frozen_fixture: Fixture) -> None:
    key = "ETHUSDT_1m"
    frozen_fixture.manifest["tables"][key]["rows"] += 1
    for run_name in ("quality_run1", "quality_run2"):
        frozen_fixture.quality[run_name]["tables"][key]["rows"] += 1
    paths = frozen_fixture.bind_quality()
    with pytest.raises(snapshot.SnapshotVerificationError, match="canonical metadata"):
        snapshot._verify_nonproduction_fixture(paths)


def test_controlled_large_append_is_not_chased_and_fails_bounded(
    frozen_fixture: Fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = snapshot._hash_exact_size
    appended = False

    def append_then_hash(handle: snapshot._FileHandle, *, before: os.stat_result) -> str:
        nonlocal appended
        if not appended:
            appended = True
            path = frozen_fixture.dataset_root / handle.name
            with path.open("ab") as target:
                target.write(b"x" * (8 * 1024 * 1024))
        return original(handle, before=before)

    monkeypatch.setattr(snapshot, "_hash_exact_size", append_then_hash)
    with pytest.raises(snapshot.SnapshotVerificationError, match="changed during hash"):
        snapshot._verify_nonproduction_fixture(frozen_fixture.paths)
    assert appended is True


def test_pyarrow_metadata_parser_receives_thrift_bounds(
    frozen_fixture: Fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = snapshot.pq.ParquetFile
    observed: list[dict[str, Any]] = []

    def capture(source: Any, **kwargs: Any) -> Any:
        observed.append(kwargs)
        return original(source, **kwargs)

    monkeypatch.setattr(snapshot.pq, "ParquetFile", capture)
    assert snapshot._verify_nonproduction_fixture(frozen_fixture.paths) is None
    assert len(observed) == 6
    assert all(
        item["thrift_string_size_limit"] == snapshot.MAX_THRIFT_STRING_BYTES
        and item["thrift_container_size_limit"] == snapshot.MAX_THRIFT_CONTAINER_ITEMS
        for item in observed
    )


def test_verification_writes_nothing_including_git_and_returns_no_receipt(
    frozen_fixture: Fixture,
) -> None:
    before = _tree_state(frozen_fixture.root)
    assert snapshot._verify_nonproduction_fixture(frozen_fixture.paths) is None
    after = _tree_state(frozen_fixture.root)
    assert after == before


def test_exact_dash_b_cli_in_fresh_writable_copy_makes_no_filesystem_writes(
    frozen_fixture: Fixture,
) -> None:
    module = frozen_fixture.root / "src" / "tios" / "dataset" / "shortframe_snapshot_verify.py"
    source = Path(snapshot.__file__).read_text(encoding="utf-8")
    source = source.replace(
        snapshot.EXPECTED_MANIFEST_SHA256,
        frozen_fixture.paths.expected_manifest_sha256,
    ).replace(
        snapshot.EXPECTED_QUALITY_SHA256,
        frozen_fixture.paths.expected_quality_sha256,
    )
    (module.parents[1] / "__init__.py").write_text("", encoding="utf-8")
    (module.parent / "__init__.py").write_text("", encoding="utf-8")
    module.write_text(source, encoding="utf-8")
    before = _tree_state(frozen_fixture.root)
    environment = os.environ.copy()
    environment.pop("PYTHONDONTWRITEBYTECODE", None)
    environment.pop("PYTHONPYCACHEPREFIX", None)
    environment["PYTHONPATH"] = str(frozen_fixture.root / "src")
    python = shutil.which("python")
    assert python is not None
    result = subprocess.run(
        [python, "-B", "-m", "tios.dataset.shortframe_snapshot_verify"],
        cwd=frozen_fixture.root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"
    assert payload["tables_verified"] == 6
    assert payload["manifest_sha256"] == frozen_fixture.paths.expected_manifest_sha256
    prohibited = {
        "execution_authority",
        "authority",
        "strategy",
        "signal",
        "trade",
        "return",
        "pnl",
        "sharpe",
        "drawdown",
        "promotion",
        "profitability",
    }
    assert not (_all_keys(payload) & prohibited)
    assert result.stderr == ""
    assert _tree_state(frozen_fixture.root) == before


def test_cli_rejects_arguments_without_running_verifier(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    called = False

    def forbidden() -> dict[str, object]:
        nonlocal called
        called = True
        return {"status": "PASS"}

    monkeypatch.setattr(snapshot, "verify_snapshot", forbidden)
    monkeypatch.setattr(snapshot.sys, "argv", ["shortframe_snapshot_verify", "--root", "/tmp"])
    assert snapshot.main() == 2
    captured = capsys.readouterr()
    assert called is False
    assert captured.out == ""
    assert captured.err == ('{"error":"fixed invocation accepts no arguments","status":"FAIL"}\n')
