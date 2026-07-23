"""Fast, read-only verification of the frozen production short-frame snapshot.

Run with no arguments:

    python -B -m tios.dataset.shortframe_snapshot_verify

The public API is production-only. It never regenerates data, publishes
evidence, consults a remote, or grants authority. Historical code identity is
read from local Git blobs at the manifest-recorded commit.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import selectors
import stat
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[3]
DATASET_ID = "DS-CRYPTO-SPOT-SHORTFRAMES-V1"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
TIMEFRAMES = ("1m", "5m", "15m")
EXPECTED_KEYS = frozenset(f"{symbol}_{timeframe}" for symbol in SYMBOLS for timeframe in TIMEFRAMES)
EXPECTED_SCOPE = {
    "symbols": list(SYMBOLS),
    "timeframes": list(TIMEFRAMES),
    "window": {"start": "2021-01", "end": "2026-06"},
}
EXPECTED_CUTOFF = "2026-07-01T00:00:00+00:00"
EXPECTED_MANIFEST_SHA256 = "05ccd69008c54f14f3b3299226e27c313d60fa224bf9b701e11ecc92beec7ce4"
EXPECTED_QUALITY_SHA256 = "cd281975e187f8e1cf43fd62fe03585891cf8c02cd44baf319575e42837f1186"
EXPECTED_CODE_PATHS = frozenset(
    {
        "src/tios/dataset/acquire.py",
        "src/tios/dataset/download.py",
        "src/tios/dataset/normalize.py",
        "src/tios/dataset/normalize_multi.py",
        "src/tios/dataset/quality.py",
        "src/tios/dataset/shortframe_freeze.py",
        "src/tios/trading_domain/__init__.py",
        "src/tios/trading_domain/models.py",
    }
)

# Frozen V1 schema pin. This must not import a mutable normalization definition.
_DECIMAL = pa.decimal128(38, 8)
_UTC_US = pa.timestamp("us", tz="UTC")
FROZEN_V1_ARROW_SCHEMA = pa.schema(
    [
        ("timestamp_open_utc", _UTC_US),
        ("open", _DECIMAL),
        ("high", _DECIMAL),
        ("low", _DECIMAL),
        ("close", _DECIMAL),
        ("volume_base", _DECIMAL),
        ("close_timestamp_utc", _UTC_US),
        ("quote_volume", _DECIMAL),
        ("trade_count", pa.int64()),
        ("taker_buy_base_volume", _DECIMAL),
        ("taker_buy_quote_volume", _DECIMAL),
        ("source", pa.string()),
        ("instrument", pa.string()),
        ("interval", pa.string()),
    ]
)

MAX_JSON_BYTES = 1_048_576
MAX_PARQUET_BYTES = 268_435_456
MAX_PARQUET_FOOTER_BYTES = 2_097_152
MAX_PARQUET_ROWS = 4_000_000
MAX_ROW_GROUPS = 4_096
MAX_THRIFT_STRING_BYTES = 1_048_576
MAX_THRIFT_CONTAINER_ITEMS = 65_536
MAX_CODE_BLOB_BYTES = 2_097_152
MAX_GIT_TEXT_BYTES = 128
MAX_GIT_STDERR_BYTES = 4_096
GIT_TIMEOUT_SECONDS = 10.0
HASH_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
CODE_PATH_RE = re.compile(r"src/[A-Za-z0-9_./-]+")

_DIR_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NOFOLLOW", 0)
)
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
_TRUSTED_GIT_BINARY = Path("/usr/bin/git")


class SnapshotVerificationError(RuntimeError):
    """A compact, operator-safe verification failure."""


@dataclass(frozen=True)
class _SnapshotPaths:
    """Private path injection used only by isolated non-production tests."""

    root: Path
    expected_manifest_sha256: str
    expected_quality_sha256: str

    @property
    def manifest_archive_name(self) -> str:
        return f"{DATASET_ID}.manifest_{self.expected_manifest_sha256}.json"

    @property
    def quality_archive_name(self) -> str:
        return f"{DATASET_ID}.QUALITY_REPORT_{self.expected_quality_sha256}.json"


def _production_paths() -> _SnapshotPaths:
    return _SnapshotPaths(
        root=ROOT,
        expected_manifest_sha256=EXPECTED_MANIFEST_SHA256,
        expected_quality_sha256=EXPECTED_QUALITY_SHA256,
    )


@dataclass
class _DirectoryHandle:
    descriptor: int
    parent: _DirectoryHandle | None
    name: str | None
    label: str
    inode: tuple[int, int, int]


@dataclass
class _FileHandle:
    stream: BinaryIO
    parent: _DirectoryHandle
    name: str
    label: str
    state: tuple[int, int, int, int, int, int, int]


def _inode(metadata: os.stat_result) -> tuple[int, int, int]:
    return metadata.st_dev, metadata.st_ino, stat.S_IFMT(metadata.st_mode)


def _file_state(metadata: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _require_directory_metadata(metadata: os.stat_result, *, label: str) -> None:
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise SnapshotVerificationError(f"{label}: directory path is not real")


def _require_file_metadata(metadata: os.stat_result, *, label: str) -> None:
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise SnapshotVerificationError(f"{label}: not a regular non-symlink file")
    if metadata.st_nlink != 1:
        raise SnapshotVerificationError(f"{label}: hard-link count is not one")


@dataclass
class _AnchoredSnapshot:
    """Descriptor-anchored view retained until the final PASS revalidation."""

    paths: _SnapshotPaths
    root: _DirectoryHandle | None = None
    data: _DirectoryHandle | None = None
    normalized: _DirectoryHandle | None = None
    dataset: _DirectoryHandle | None = None
    artifacts: _DirectoryHandle | None = None
    evidence: _DirectoryHandle | None = None
    files: list[_FileHandle] = field(default_factory=list)
    directories: list[_DirectoryHandle] = field(default_factory=list)

    def __enter__(self) -> _AnchoredSnapshot:
        try:
            self.root = self._open_root()
            self.data = self._open_directory(self.root, "data", "data root")
            self.normalized = self._open_directory(self.data, "normalized", "normalized data root")
            self.dataset = self._open_directory(
                self.normalized, DATASET_ID, "short-frame dataset root"
            )
            self.artifacts = self._open_directory(self.root, "artifacts", "artifact root")
            self.evidence = self._open_directory(
                self.artifacts, "datasets", "dataset evidence root"
            )
            self._require_exact_inventory()
            return self
        except Exception:
            self.close()
            raise

    def __exit__(self, *_: object) -> None:
        self.close()

    def _open_root(self) -> _DirectoryHandle:
        absolute = Path(os.path.abspath(self.paths.root))
        try:
            before = absolute.lstat()
            _require_directory_metadata(before, label="repository root")
            descriptor = os.open(absolute, _DIR_FLAGS)
            opened = os.fstat(descriptor)
        except (OSError, SnapshotVerificationError) as error:
            if isinstance(error, SnapshotVerificationError):
                raise
            raise SnapshotVerificationError("repository root: secure open failed") from error
        if _inode(before) != _inode(opened):
            os.close(descriptor)
            raise SnapshotVerificationError("repository root: changed during open")
        handle = _DirectoryHandle(
            descriptor=descriptor,
            parent=None,
            name=None,
            label="repository root",
            inode=_inode(opened),
        )
        self.directories.append(handle)
        return handle

    def _open_directory(self, parent: _DirectoryHandle, name: str, label: str) -> _DirectoryHandle:
        try:
            before = os.stat(name, dir_fd=parent.descriptor, follow_symlinks=False)
            _require_directory_metadata(before, label=label)
            descriptor = os.open(name, _DIR_FLAGS, dir_fd=parent.descriptor)
            opened = os.fstat(descriptor)
        except (OSError, SnapshotVerificationError) as error:
            if isinstance(error, SnapshotVerificationError):
                raise
            raise SnapshotVerificationError(f"{label}: secure open failed") from error
        if _inode(before) != _inode(opened):
            os.close(descriptor)
            raise SnapshotVerificationError(f"{label}: changed during open")
        handle = _DirectoryHandle(
            descriptor=descriptor,
            parent=parent,
            name=name,
            label=label,
            inode=_inode(opened),
        )
        self.directories.append(handle)
        return handle

    def open_file(self, parent: _DirectoryHandle, name: str, label: str) -> _FileHandle:
        try:
            before = os.stat(name, dir_fd=parent.descriptor, follow_symlinks=False)
            _require_file_metadata(before, label=label)
            descriptor = os.open(name, _FILE_FLAGS, dir_fd=parent.descriptor)
            opened = os.fstat(descriptor)
        except (OSError, SnapshotVerificationError) as error:
            if isinstance(error, SnapshotVerificationError):
                raise
            raise SnapshotVerificationError(f"{label}: secure open failed") from error
        if _file_state(before) != _file_state(opened):
            os.close(descriptor)
            raise SnapshotVerificationError(f"{label}: changed during open")
        handle = _FileHandle(
            stream=os.fdopen(descriptor, "rb", buffering=0),
            parent=parent,
            name=name,
            label=label,
            state=_file_state(opened),
        )
        self.files.append(handle)
        return handle

    def _require_exact_inventory(self) -> None:
        dataset = self._dataset()
        names: set[str] = set()
        try:
            with os.scandir(dataset.descriptor) as entries:
                for entry in entries:
                    if len(names) == len(EXPECTED_KEYS):
                        raise SnapshotVerificationError(
                            "dataset: exact six-file inventory mismatch"
                        )
                    names.add(entry.name)
        except OSError as error:
            raise SnapshotVerificationError("dataset: inventory read failed") from error
        if names != {f"{key}.parquet" for key in EXPECTED_KEYS}:
            raise SnapshotVerificationError("dataset: exact six-file inventory mismatch")

    def revalidate(self) -> None:
        """Rebind every retained descriptor to its original directory entry."""

        root = self._root()
        try:
            root_path_state = _inode(Path(os.path.abspath(self.paths.root)).lstat())
        except OSError as error:
            raise SnapshotVerificationError("repository root: final path missing") from error
        if root_path_state != root.inode or _inode(os.fstat(root.descriptor)) != root.inode:
            raise SnapshotVerificationError("repository root: final identity mismatch")
        for directory in self.directories[1:]:
            assert directory.parent is not None and directory.name is not None
            try:
                entry = os.stat(
                    directory.name,
                    dir_fd=directory.parent.descriptor,
                    follow_symlinks=False,
                )
                opened = os.fstat(directory.descriptor)
            except OSError as error:
                raise SnapshotVerificationError(
                    f"{directory.label}: final entry missing"
                ) from error
            if _inode(entry) != directory.inode or _inode(opened) != directory.inode:
                raise SnapshotVerificationError(f"{directory.label}: final identity mismatch")
        self._require_exact_inventory()
        for handle in self.files:
            try:
                entry = os.stat(
                    handle.name,
                    dir_fd=handle.parent.descriptor,
                    follow_symlinks=False,
                )
                opened = os.fstat(handle.stream.fileno())
            except OSError as error:
                raise SnapshotVerificationError(f"{handle.label}: final entry missing") from error
            if _file_state(entry) != handle.state or _file_state(opened) != handle.state:
                raise SnapshotVerificationError(f"{handle.label}: final identity mismatch")

    def close(self) -> None:
        while self.files:
            file_handle = self.files.pop()
            try:
                file_handle.stream.close()
            except OSError:
                pass
        while self.directories:
            directory_handle = self.directories.pop()
            try:
                os.close(directory_handle.descriptor)
            except OSError:
                pass

    def _root(self) -> _DirectoryHandle:
        if self.root is None:
            raise SnapshotVerificationError("repository root: not anchored")
        return self.root

    def _dataset(self) -> _DirectoryHandle:
        if self.dataset is None:
            raise SnapshotVerificationError("dataset: not anchored")
        return self.dataset

    def _evidence(self) -> _DirectoryHandle:
        if self.evidence is None:
            raise SnapshotVerificationError("evidence: not anchored")
        return self.evidence


def _read_bounded(handle: _FileHandle, *, limit: int) -> bytes:
    before = os.fstat(handle.stream.fileno())
    if _file_state(before) != handle.state:
        raise SnapshotVerificationError(f"{handle.label}: changed before read")
    if before.st_size > limit:
        raise SnapshotVerificationError(f"{handle.label}: size limit exceeded")
    handle.stream.seek(0)
    remaining = before.st_size
    chunks: list[bytes] = []
    while remaining:
        chunk = handle.stream.read(min(1024 * 1024, remaining))
        if not chunk:
            raise SnapshotVerificationError(f"{handle.label}: early EOF")
        chunks.append(chunk)
        remaining -= len(chunk)
    payload = b"".join(chunks)
    after = os.fstat(handle.stream.fileno())
    if _file_state(after) != handle.state:
        raise SnapshotVerificationError(f"{handle.label}: changed during read")
    return payload


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require_sha256(value: object, *, label: str) -> str:
    if not isinstance(value, str) or HASH_RE.fullmatch(value) is None:
        raise SnapshotVerificationError(f"{label}: invalid SHA-256")
    return value


def _strict_object(payload: bytes, *, label: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise SnapshotVerificationError(f"{label}: duplicate JSON key")
            value[key] = item
        return value

    def reject_constant(_: str) -> None:
        raise SnapshotVerificationError(f"{label}: non-finite JSON number")

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except SnapshotVerificationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise SnapshotVerificationError(f"{label}: invalid JSON") from error
    if not isinstance(value, dict):
        raise SnapshotVerificationError(f"{label}: JSON root is not an object")
    return value


def _artifact_pair(
    stable: _FileHandle,
    archive: _FileHandle,
    *,
    expected_sha256: str,
    label: str,
) -> dict[str, Any]:
    expected = _require_sha256(expected_sha256, label=f"{label} pin")
    stable_bytes = _read_bounded(stable, limit=MAX_JSON_BYTES)
    archive_bytes = _read_bounded(archive, limit=MAX_JSON_BYTES)
    if stable_bytes != archive_bytes:
        raise SnapshotVerificationError(f"{label}: stable/archive drift")
    if _sha256_bytes(stable_bytes) != expected or _sha256_bytes(archive_bytes) != expected:
        raise SnapshotVerificationError(f"{label}: pinned bytes drift")
    return _strict_object(stable_bytes, label=label)


def _require_exact_grid(tables: object, *, label: str) -> dict[str, Any]:
    if not isinstance(tables, dict) or set(tables) != EXPECTED_KEYS:
        raise SnapshotVerificationError(f"{label}: exact six-table grid mismatch")
    if any(not isinstance(record, dict) for record in tables.values()):
        raise SnapshotVerificationError(f"{label}: malformed table record")
    return tables


def _verify_evidence(
    manifest: dict[str, Any], quality: dict[str, Any], *, paths: _SnapshotPaths
) -> dict[str, Any]:
    if (
        manifest.get("schema_version") != 1
        or manifest.get("dataset_id") != DATASET_ID
        or manifest.get("scope") != EXPECTED_SCOPE
        or manifest.get("cutoff_utc") != EXPECTED_CUTOFF
        or manifest.get("lineage_status") != "recorded_at_normalization"
        or manifest.get("execution_authority") != "NONE"
    ):
        raise SnapshotVerificationError("manifest: fixed identity contract failed")
    if manifest.get("quality_report_sha256") != paths.expected_quality_sha256:
        raise SnapshotVerificationError("manifest: quality cross-link mismatch")
    tables = _require_exact_grid(manifest.get("tables"), label="manifest")
    if (
        quality.get("schema_version") != 1
        or quality.get("dataset_id") != DATASET_ID
        or quality.get("overall") != "PASS"
        or quality.get("scope") != EXPECTED_SCOPE
        or quality.get("execution_authority") != "NONE"
    ):
        raise SnapshotVerificationError("quality: fixed PASS contract failed")
    if quality.get("code_identity") != manifest.get("code_identity"):
        raise SnapshotVerificationError("quality: code identity cross-link mismatch")
    for run_name in ("quality_run1", "quality_run2"):
        run = quality.get(run_name)
        if (
            not isinstance(run, dict)
            or run.get("overall") != "PASS"
            or run.get("exact_table_grid") != "PASS"
            or run.get("schema_identical") != "PASS"
            or _require_exact_grid(run.get("tables"), label=run_name) != tables
        ):
            raise SnapshotVerificationError(f"{run_name}: PASS/table cross-link failed")
    regeneration = quality.get("double_regeneration")
    logical = {
        key: _require_sha256(record.get("content_sha256"), label=f"table {key} logical")
        for key, record in tables.items()
    }
    if (
        not isinstance(regeneration, dict)
        or regeneration.get("status") != "PASS"
        or regeneration.get("run1_logical_hashes") != logical
        or regeneration.get("run2_logical_hashes") != logical
    ):
        raise SnapshotVerificationError("quality: double-regeneration cross-link failed")
    return tables


def _verify_table(handle: _FileHandle, record: dict[str, Any], *, key: str) -> None:
    if (
        record.get("status") != "PASS"
        or record.get("failures") != []
        or type(record.get("rows")) is not int
        or not 0 < record["rows"] <= MAX_PARQUET_ROWS
        or record.get("schema") != str(FROZEN_V1_ARROW_SCHEMA)
    ):
        raise SnapshotVerificationError(f"table {key}: manifest metadata invalid")
    expected_sha = _require_sha256(record.get("parquet_sha256"), label=f"table {key} parquet")
    before = os.fstat(handle.stream.fileno())
    if _file_state(before) != handle.state:
        raise SnapshotVerificationError(f"table {key}: changed before verification")
    if before.st_size < 12 or before.st_size > MAX_PARQUET_BYTES:
        raise SnapshotVerificationError(f"table {key}: size bound failed")
    if _hash_exact_size(handle, before=before) != expected_sha:
        raise SnapshotVerificationError(f"table {key}: byte SHA-256 mismatch")
    handle.stream.seek(-8, os.SEEK_END)
    trailer = handle.stream.read(8)
    footer_size = int.from_bytes(trailer[:4], "little")
    if trailer[4:] != b"PAR1" or not 0 < footer_size <= MAX_PARQUET_FOOTER_BYTES:
        raise SnapshotVerificationError(f"table {key}: Parquet footer bound failed")
    handle.stream.seek(0)
    try:
        parquet = pq.ParquetFile(
            handle.stream,
            thrift_string_size_limit=MAX_THRIFT_STRING_BYTES,
            thrift_container_size_limit=MAX_THRIFT_CONTAINER_ITEMS,
        )
        metadata = parquet.metadata
        schema = parquet.schema_arrow
    except Exception as error:
        raise SnapshotVerificationError(f"table {key}: Parquet metadata invalid") from error
    after = os.fstat(handle.stream.fileno())
    if _file_state(after) != handle.state:
        raise SnapshotVerificationError(f"table {key}: changed during verification")
    if (
        metadata.num_rows != record["rows"]
        or not 0 < metadata.num_row_groups <= MAX_ROW_GROUPS
        or metadata.num_columns != len(FROZEN_V1_ARROW_SCHEMA)
        or metadata.serialized_size > MAX_PARQUET_FOOTER_BYTES
        or not schema.equals(FROZEN_V1_ARROW_SCHEMA, check_metadata=True)
        or schema.metadata not in (None, {})
    ):
        raise SnapshotVerificationError(f"table {key}: canonical metadata mismatch")
    row_group_rows = sum(
        metadata.row_group(index).num_rows for index in range(metadata.num_row_groups)
    )
    if row_group_rows != record["rows"]:
        raise SnapshotVerificationError(f"table {key}: row-group metadata mismatch")


def _hash_exact_size(handle: _FileHandle, *, before: os.stat_result) -> str:
    """Hash only the prevalidated size; never follow a concurrent append."""

    if _file_state(before) != handle.state:
        raise SnapshotVerificationError(f"{handle.label}: changed before hash")
    handle.stream.seek(0)
    digest = hashlib.sha256()
    remaining = before.st_size
    while remaining:
        chunk = handle.stream.read(min(1024 * 1024, remaining))
        if not chunk:
            raise SnapshotVerificationError(f"{handle.label}: early EOF")
        digest.update(chunk)
        remaining -= len(chunk)
    if _file_state(os.fstat(handle.stream.fileno())) != handle.state:
        raise SnapshotVerificationError(f"{handle.label}: changed during hash")
    return digest.hexdigest()


def _git_environment(_: dict[str, str] | None = None) -> dict[str, str]:
    """Return a minimal local-only environment; inherit no injection surface."""

    return {
        "LC_ALL": "C",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_PROTOCOL_FROM_USER": "0",
    }


def _trusted_git_state() -> tuple[int, int, int, int, int]:
    if _TRUSTED_GIT_BINARY != Path("/usr/bin/git") or not _TRUSTED_GIT_BINARY.is_absolute():
        raise SnapshotVerificationError("Git binary: fixed path contract failed")
    try:
        metadata = _TRUSTED_GIT_BINARY.lstat()
    except OSError as error:
        raise SnapshotVerificationError("Git binary: unavailable") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise SnapshotVerificationError("Git binary: not a regular trusted file")
    if metadata.st_mode & 0o111 == 0:
        raise SnapshotVerificationError("Git binary: not executable")
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
    )


def _git_command(arguments: list[str], *, label: str) -> list[str]:
    allowed = (
        len(arguments) == 3
        and arguments[:2] == ["rev-parse", "--verify"]
        or len(arguments) == 3
        and arguments[:2] == ["cat-file", "-s"]
        or len(arguments) == 3
        and arguments[:2] == ["cat-file", "blob"]
    )
    if not allowed:
        raise SnapshotVerificationError(f"{label}: prohibited Git operation")
    return [
        str(_TRUSTED_GIT_BINARY),
        "-c",
        "protocol.allow=never",
        "-c",
        "credential.helper=",
        *arguments,
    ]


def _kill_and_reap(process: subprocess.Popen[bytes]) -> None:
    try:
        if process.poll() is None:
            process.kill()
    except OSError:
        pass
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        process.wait()


def _run_git_bounded(
    root: Path,
    arguments: list[str],
    *,
    label: str,
    stdout_limit: int,
) -> bytes:
    """Run one fixed Git read with bounded pipes, timeout, kill, and reap.

    A ``preexec_fn`` resource limit is intentionally avoided: Python documents
    it as unsafe in threaded applications, and its macOS behavior is not a
    suitable portable boundary here. The parent reads at most each explicit
    limit plus one overflow byte; pipe backpressure bounds further child output,
    and overflow or timeout triggers immediate kill/reap.
    """

    if stdout_limit < 0:
        raise SnapshotVerificationError(f"{label}: invalid output bound")
    binary_state = _trusted_git_state()
    command = _git_command(arguments, label=label)
    try:
        process = subprocess.Popen(
            command,
            cwd=root,
            env=_git_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
    except OSError as error:
        raise SnapshotVerificationError(f"{label}: Git start failed") from error
    if process.stdout is None or process.stderr is None:
        _kill_and_reap(process)
        raise SnapshotVerificationError(f"{label}: Git pipes unavailable")
    output = bytearray()
    error_output = bytearray()
    selector = selectors.DefaultSelector()
    deadline = time.monotonic() + GIT_TIMEOUT_SECONDS
    try:
        os.set_blocking(process.stdout.fileno(), False)
        os.set_blocking(process.stderr.fileno(), False)
        selector.register(process.stdout, selectors.EVENT_READ, (output, stdout_limit, "stdout"))
        selector.register(
            process.stderr,
            selectors.EVENT_READ,
            (error_output, MAX_GIT_STDERR_BYTES, "stderr"),
        )
        while selector.get_map():
            remaining_time = deadline - time.monotonic()
            if remaining_time <= 0:
                raise SnapshotVerificationError(f"{label}: Git timeout")
            events = selector.select(timeout=min(remaining_time, 0.1))
            if not events:
                continue
            for key, _ in events:
                buffer, limit, stream_name = key.data
                remaining_capacity = limit - len(buffer)
                read_size = min(65_536, max(1, remaining_capacity + 1))
                try:
                    chunk = os.read(key.fd, read_size)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffer.extend(chunk)
                if len(buffer) > limit:
                    raise SnapshotVerificationError(f"{label}: Git {stream_name} bound exceeded")
        wait_time = deadline - time.monotonic()
        if wait_time <= 0:
            raise SnapshotVerificationError(f"{label}: Git timeout")
        returncode = process.wait(timeout=wait_time)
    except (OSError, subprocess.TimeoutExpired) as error:
        _kill_and_reap(process)
        raise SnapshotVerificationError(f"{label}: Git read failed") from error
    except SnapshotVerificationError:
        _kill_and_reap(process)
        raise
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()
    if _trusted_git_state() != binary_state:
        raise SnapshotVerificationError(f"{label}: Git binary changed during read")
    if returncode != 0:
        raise SnapshotVerificationError(f"{label}: Git object unavailable")
    return bytes(output)


def _git_text(root: Path, arguments: list[str], *, label: str) -> str:
    payload = _run_git_bounded(
        root,
        arguments,
        label=label,
        stdout_limit=MAX_GIT_TEXT_BYTES,
    )
    try:
        return payload.decode("ascii").strip()
    except UnicodeDecodeError as error:
        raise SnapshotVerificationError(f"{label}: invalid Git text") from error


def _read_git_blob_exact(
    root: Path,
    object_spec: str,
    *,
    expected_size: int,
    label: str,
) -> bytes:
    if not 0 <= expected_size <= MAX_CODE_BLOB_BYTES:
        raise SnapshotVerificationError(f"{label}: size bound failed")
    payload = _run_git_bounded(
        root,
        ["cat-file", "blob", object_spec],
        label=label,
        stdout_limit=expected_size,
    )
    if len(payload) != expected_size:
        raise SnapshotVerificationError(f"{label}: size changed between Git reads")
    return payload


def _verify_code_identity(identity: object, *, root: Path) -> None:
    if not isinstance(identity, dict):
        raise SnapshotVerificationError("code identity: malformed")
    commit = identity.get("git_commit")
    if (
        not isinstance(commit, str)
        or COMMIT_RE.fullmatch(commit) is None
        or identity.get("git_commit_valid") is not True
        or identity.get("git_state") != "committed"
    ):
        raise SnapshotVerificationError("code identity: invalid recorded commit")
    commit_check = _git_text(
        root, ["rev-parse", "--verify", f"{commit}^{{commit}}"], label="code identity"
    )
    if commit_check != commit:
        raise SnapshotVerificationError("code identity: commit resolution mismatch")
    files = identity.get("files")
    if not isinstance(files, list) or len(files) != len(EXPECTED_CODE_PATHS):
        raise SnapshotVerificationError("code identity: surface mismatch")
    recorded: dict[str, str] = {}
    for item in files:
        if not isinstance(item, dict):
            raise SnapshotVerificationError("code identity: malformed file record")
        path = item.get("path")
        if (
            not isinstance(path, str)
            or CODE_PATH_RE.fullmatch(path) is None
            or Path(path).is_absolute()
            or ".." in Path(path).parts
            or path in recorded
        ):
            raise SnapshotVerificationError("code identity: unsafe or duplicate path")
        recorded[path] = _require_sha256(item.get("sha256"), label="code identity file")
    if set(recorded) != EXPECTED_CODE_PATHS:
        raise SnapshotVerificationError("code identity: surface mismatch")
    for path in sorted(recorded):
        object_spec = f"{commit}:{path}"
        size_result = _git_text(root, ["cat-file", "-s", object_spec], label=f"code blob {path}")
        try:
            size = int(size_result)
        except (TypeError, ValueError) as error:
            raise SnapshotVerificationError(f"code blob {path}: invalid size") from error
        if not 0 <= size <= MAX_CODE_BLOB_BYTES:
            raise SnapshotVerificationError(f"code blob {path}: size bound failed")
        blob = _read_git_blob_exact(
            root, object_spec, expected_size=size, label=f"code blob {path}"
        )
        if hashlib.sha256(blob).hexdigest() != recorded[path]:
            raise SnapshotVerificationError(f"code blob {path}: recorded hash mismatch")


def _verify_at_fixed_snapshot(paths: _SnapshotPaths) -> None:
    """Private engine. It returns no PASS-shaped non-production receipt."""

    _require_sha256(paths.expected_manifest_sha256, label="manifest pin")
    _require_sha256(paths.expected_quality_sha256, label="quality pin")
    with _AnchoredSnapshot(paths) as anchored:
        evidence = anchored._evidence()
        dataset = anchored._dataset()
        manifest = _artifact_pair(
            anchored.open_file(evidence, f"{DATASET_ID}.manifest.json", "manifest stable"),
            anchored.open_file(evidence, paths.manifest_archive_name, "manifest archive"),
            expected_sha256=paths.expected_manifest_sha256,
            label="manifest",
        )
        quality = _artifact_pair(
            anchored.open_file(
                evidence, f"{DATASET_ID}.QUALITY_REPORT.json", "quality report stable"
            ),
            anchored.open_file(evidence, paths.quality_archive_name, "quality report archive"),
            expected_sha256=paths.expected_quality_sha256,
            label="quality report",
        )
        tables = _verify_evidence(manifest, quality, paths=paths)
        for key in sorted(EXPECTED_KEYS):
            handle = anchored.open_file(dataset, f"{key}.parquet", f"table {key}")
            _verify_table(handle, tables[key], key=key)
        _verify_code_identity(manifest.get("code_identity"), root=Path(os.path.abspath(paths.root)))
        anchored.revalidate()


def _verify_nonproduction_fixture(paths: _SnapshotPaths) -> None:
    """Test-only entry point; deliberately returns no production-like receipt."""

    _verify_at_fixed_snapshot(paths)


def verify_snapshot() -> dict[str, object]:
    """Verify only the fixed production snapshot and return a bounded receipt."""

    _verify_at_fixed_snapshot(_production_paths())
    return {
        "dataset_id": DATASET_ID,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "quality_report_sha256": EXPECTED_QUALITY_SHA256,
        "status": "PASS",
        "tables_verified": len(EXPECTED_KEYS),
    }


def _compact_json(value: dict[str, object]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def main() -> int:
    if len(sys.argv) != 1:
        print(
            _compact_json({"error": "fixed invocation accepts no arguments", "status": "FAIL"}),
            file=sys.stderr,
        )
        return 2
    try:
        result = verify_snapshot()
    except SnapshotVerificationError as error:
        print(_compact_json({"error": str(error)[:240], "status": "FAIL"}), file=sys.stderr)
        return 1
    except Exception:
        print(
            _compact_json({"error": "unexpected verification failure", "status": "FAIL"}),
            file=sys.stderr,
        )
        return 1
    print(_compact_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
