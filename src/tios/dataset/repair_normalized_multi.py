"""One-time, fail-closed repair for pre-v8.131 open-candle refresh corruption.

``plan`` is offline and immutable: it derives the exact affected coordinates from
the ten retained daily manifests and binds every input byte. ``apply`` accepts only
that content-addressed plan, revalidates all bindings before network access, fetches
one exact Binance kline per coordinate, and transactionally replaces the affected
rows.  A receipt is the commit marker; a missing receipt always means rollback.

This module deliberately has no configurable production URL or dataset path.
Generated plans, raw responses, journals, audits, receipts, and repaired data are
runtime evidence and must not be committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet

from tios.dataset.daily_update import REST, _klines_json_to_raw, _process_lock
from tios.dataset.normalize import content_sha256, to_canonical

ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "data" / "normalized_multi"
RAW_ROOT = ROOT / "data" / "raw" / "rest_klines"
PLAN_ROOT = DATASET / "repair_plans"
STATE_ROOT = DATASET / "repair_state"
MANIFEST_NAME = "normalized_multi_manifest.json"
STATUS_NAME = "daily_update_status.json"
MAX_RESPONSE_BYTES = 128 * 1024
PLAN_SCHEMA = 1
REPAIR_ID = "NORMALIZED-MULTI-PRE-V8.131-OPEN-CANDLE-REPAIR-V1"

ARCHIVE_DIGESTS = (
    "78b86d2e7a4df48759c68c9b3c314fc31580c6604b7b4d9dbf02d386ec3692a5",
    "a9217e629c5186f958ff01dab2c970b6b759fada5dd1861078d003f87d01e8c2",
    "4414ce8a7bcefbe4a51b1ee17a1bd2bdc679665bd4ea4eb0a0661d553e587f90",
    "23ddeb7a6e1c3288b238c5c6a35ed1928ede1fce8236e74d489af5485ae22d1a",
    "6cf82e505299d67dd15dfa93cf8363246ce28612293f03df8d452c53f04b7648",
    "2046a8184a9cd2248ed3411f26fbcdc897c34d02eaf759d97a8f063de6c49a01",
    "49fdbd469877a7733684e4eff4f89d5896b3a7c01ce461981460311d7488507e",
    "02a9c125e8f3036d050549adb9af59d3b3d65d9cb0e94cc511012a0d052cc34c",
    "517640069cb57e417b6ee94e0f384facc9c95e738c13b418ab12303b710b5eae",
    "62353a5fadcbb812f1780ce75815e1bbbe5d3863cb8f0aca61a1056ff6f999d0",
)
STALE_TABLES = frozenset(
    {"EOSUSDT_1d", "FTMUSDT_1d", "MATICUSDT_1d", "MATICUSDT_1h", "MATICUSDT_4h"}
)
INTERVAL_MS = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


class RepairError(RuntimeError):
    """The repair cannot safely continue."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _strict_regular(path: Path, *, expected_parent: Path | None = None) -> os.stat_result:
    if expected_parent is not None and path.parent.resolve() != expected_parent.resolve():
        raise RepairError(f"path escaped its fixed directory: {path}")
    try:
        info = path.lstat()
    except FileNotFoundError as error:
        raise RepairError(f"required file is missing: {path}") from error
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RepairError(f"file is not a single-link regular file: {path}")
    return info


def _safe_path(base: Path, relative: str | Path, *, create_parents: bool = False) -> Path:
    relative = Path(relative)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise RepairError("path is not a confined relative path")
    try:
        base_info = base.lstat()
    except FileNotFoundError as error:
        raise RepairError(f"fixed path root is missing: {base}") from error
    if not stat.S_ISDIR(base_info.st_mode):
        raise RepairError(f"fixed path root is not a real directory: {base}")
    cursor = base
    for part in relative.parts[:-1]:
        cursor /= part
        try:
            info = cursor.lstat()
        except FileNotFoundError:
            if not create_parents:
                raise RepairError(f"confined path parent is missing: {cursor}") from None
            cursor.mkdir(mode=0o700)
            info = cursor.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise RepairError(f"confined path parent is not a real directory: {cursor}")
    return base / relative


def _read_bound(path: Path, maximum: int = 16 * 1024 * 1024) -> bytes:
    info = _strict_regular(path)
    if info.st_size > maximum:
        raise RepairError(f"file exceeds byte limit: {path}")
    value = path.read_bytes()
    if len(value) != info.st_size:
        raise RepairError(f"file changed while read: {path}")
    return value


def _load_json_bytes(value: bytes, label: str) -> dict[str, Any]:
    try:
        decoded = value.decode("utf-8")
        payload = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RepairError(f"{label} is not valid UTF-8 JSON") from error
    if not isinstance(payload, dict):
        raise RepairError(f"{label} must be a JSON object")
    return cast(dict[str, Any], payload)


def _git_commit(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RepairError("cannot identify the source commit")
    return result.stdout.strip()


def _file_binding(path: Path, relative_to: Path) -> dict[str, object]:
    info = _strict_regular(path)
    return {
        "path": path.relative_to(relative_to).as_posix(),
        "size": info.st_size,
        "sha256": _sha256(path),
    }


def _parse_utc(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise RepairError(f"{label} is not a timestamp")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as error:
        raise RepairError(f"{label} is malformed") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise RepairError(f"{label} is not timezone-aware")
    return result.astimezone(UTC)


def _open_ms(value: object, label: str) -> int:
    instant = _parse_utc(value, label)
    return int(instant.timestamp()) * 1000 + instant.microsecond // 1000


def _validate_archive(payload: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    required = {
        "schema_version",
        "dataset_id",
        "source_snapshot_utc",
        "lineage_status",
        "lineage_limitation",
        "normalization_code",
        "pair_count",
        "tables",
    }
    if set(payload) != required or payload.get("schema_version") != 2:
        raise RepairError(f"{label} has an unexpected manifest schema")
    if payload.get("dataset_id") != "DS-CRYPTO-MULTI-V1" or payload.get("pair_count") != 40:
        raise RepairError(f"{label} has the wrong dataset identity")
    _parse_utc(payload.get("source_snapshot_utc"), f"{label} source snapshot")
    tables = payload.get("tables")
    if not isinstance(tables, dict) or len(tables) != 69:
        raise RepairError(f"{label} must contain exactly 69 tables")
    for key, item in tables.items():
        if not isinstance(key, str) or not isinstance(item, dict):
            raise RepairError(f"{label} contains a malformed table")
        if item.get("parquet") != f"{key}.parquet":
            raise RepairError(f"{label} table/path mismatch: {key}")
        if not isinstance(item.get("rows"), int) or item["rows"] <= 0:
            raise RepairError(f"{label} has an invalid row count: {key}")
        _open_ms(item.get("coverage_end_utc"), f"{label} coverage for {key}")
    return cast(Mapping[str, Any], tables)


def _raw_evidence(
    dataset: Path, table: str, coordinate: int, item: Mapping[str, Any]
) -> dict[str, object]:
    rest = item.get("rest_update_source")
    if not isinstance(rest, dict) or rest.get("endpoint") != REST:
        raise RepairError(f"missing fixed REST lineage for {table}")
    pages = rest.get("source_pages")
    if not isinstance(pages, list):
        raise RepairError(f"malformed REST lineage for {table}")
    matches: list[dict[str, object]] = []
    root = dataset.parent / "raw"
    for page in pages:
        if not isinstance(page, dict):
            raise RepairError(f"malformed REST page lineage for {table}")
        relative = page.get("path")
        digest = page.get("sha256")
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise RepairError(f"malformed REST page binding for {table}")
        path = _safe_path(root, relative)
        if path.name != f"{digest}.json":
            raise RepairError(f"REST evidence filename is not content-addressed for {table}")
        value = _read_bound(path, MAX_RESPONSE_BYTES)
        if _sha256_bytes(value) != digest:
            raise RepairError(f"REST evidence digest mismatch for {table}")
        try:
            rows = json.loads(value)
        except json.JSONDecodeError as error:
            raise RepairError(f"REST evidence is invalid JSON for {table}") from error
        if not isinstance(rows, list):
            raise RepairError(f"REST evidence is not a row list for {table}")
        if any(isinstance(row, list) and len(row) >= 1 and row[0] == coordinate for row in rows):
            matches.append(
                {
                    "path": path.relative_to(dataset.parents[1]).as_posix(),
                    "size": len(value),
                    "sha256": digest,
                }
            )
    if len(matches) != 1:
        raise RepairError(f"expected one retained REST source for {table}@{coordinate}")
    return matches[0]


def _logical_without(table: pa.Table, opens_ms: frozenset[int]) -> str:
    opens = table.column("timestamp_open_utc")
    targets = pa.array(sorted(opens_ms), type=pa.timestamp("ms", tz="UTC")).cast(opens.type)
    retained = table.filter(pc.invert(pc.is_in(opens, value_set=targets)))
    return content_sha256(retained.replace_schema_metadata(None))


def build_plan(
    *, dataset: Path = DATASET, module_path: Path | None = None, root: Path = ROOT
) -> tuple[dict[str, object], bytes, str]:
    """Build the deterministic repair plan without network or mutation."""
    module_path = module_path or Path(__file__)
    manifests: list[dict[str, object]] = []
    decoded: list[tuple[dict[str, Any], Mapping[str, Any]]] = []
    expected_tables: set[str] | None = None
    for digest in ARCHIVE_DIGESTS:
        name = f"normalized_multi_manifest_{digest}.json"
        path = _safe_path(dataset, Path("manifests") / name)
        value = _read_bound(path)
        if _sha256_bytes(value) != digest:
            raise RepairError(f"archive digest does not match filename: {name}")
        payload = _load_json_bytes(value, name)
        tables = _validate_archive(payload, name)
        names = set(tables)
        if expected_tables is None:
            expected_tables = names
        elif names != expected_tables:
            raise RepairError("archived manifest table sets differ")
        manifests.append({"path": f"manifests/{name}", "size": len(value), "sha256": digest})
        decoded.append((payload, tables))
    if expected_tables is None or not STALE_TABLES < expected_tables:
        raise RepairError("the five stale tables are not present")
    active = sorted(expected_tables - STALE_TABLES)
    intervals = {interval: 0 for interval in INTERVAL_MS}
    for name in active:
        try:
            intervals[name.rsplit("_", 1)[1]] += 1
        except KeyError as error:
            raise RepairError(f"unsupported table interval: {name}") from error
    if intervals != {"1h": 14, "4h": 13, "1d": 37}:
        raise RepairError(f"unexpected refreshable table counts: {intervals}")

    coordinates: list[dict[str, object]] = []
    by_table: dict[str, set[int]] = {name: set() for name in active}
    prior_snapshot: datetime | None = None
    for archive_index, (payload, tables) in enumerate(decoded):
        snapshot = _parse_utc(payload["source_snapshot_utc"], "archive source snapshot")
        if prior_snapshot is not None and snapshot <= prior_snapshot:
            raise RepairError("archived manifests are not strictly chronological")
        prior_snapshot = snapshot
        for table in active:
            item = cast(Mapping[str, Any], tables[table])
            coordinate = _open_ms(item["coverage_end_utc"], f"coverage for {table}")
            interval = table.rsplit("_", 1)[1]
            if coordinate + INTERVAL_MS[interval] <= int(snapshot.timestamp() * 1000):
                raise RepairError(f"coordinate was already closed at snapshot: {table}")
            if coordinate in by_table[table]:
                raise RepairError(f"duplicate derived coordinate for {table}")
            by_table[table].add(coordinate)
            evidence: dict[str, object]
            if archive_index == 0:
                evidence = {"class": "MANIFEST_ONLY"}
            else:
                evidence = {
                    "class": "RETAINED_REST",
                    "raw": _raw_evidence(dataset, table, coordinate, item),
                }
            coordinates.append(
                {
                    "table": table,
                    "symbol": table.rsplit("_", 1)[0],
                    "interval": interval,
                    "open_ms": coordinate,
                    "archive_sha256": ARCHIVE_DIGESTS[archive_index],
                    "evidence": evidence,
                }
            )
    if len(coordinates) != 640:
        raise RepairError("repair coordinate count is not exactly 640")
    classes = [cast(Mapping[str, object], row["evidence"])["class"] for row in coordinates]
    if classes.count("RETAINED_REST") != 576 or classes.count("MANIFEST_ONLY") != 64:
        raise RepairError("repair evidence-class counts are not exact")

    parquet_bindings: list[dict[str, object]] = []
    for name in sorted(expected_tables):
        path = _safe_path(dataset, f"{name}.parquet")
        binding = _file_binding(path, dataset)
        table = pyarrow.parquet.read_table(path)
        binding["rows"] = table.num_rows
        binding["schema"] = str(table.replace_schema_metadata(None).schema)
        if name in by_table:
            binding["non_target_content_sha256"] = _logical_without(
                table, frozenset(by_table[name])
            )
        parquet_bindings.append(binding)

    current = _file_binding(_safe_path(dataset, MANIFEST_NAME), dataset)
    status = _file_binding(_safe_path(dataset, STATUS_NAME), dataset)
    plan: dict[str, object] = {
        "schema_version": PLAN_SCHEMA,
        "repair_id": REPAIR_ID,
        "execution_authority": "OFFLINE_DATA_REPAIR_ONLY",
        "endpoint": REST,
        "archive_manifests": manifests,
        "excluded_stale_tables": sorted(STALE_TABLES),
        "counts": {
            "tables_total": 69,
            "tables_affected": 64,
            "coordinates": 640,
            "retained_rest": 576,
            "manifest_only": 64,
            "1d": 370,
            "1h": 140,
            "4h": 130,
        },
        "coordinates": coordinates,
        "current_state": {
            "parquets": parquet_bindings,
            "manifest": current,
            "status": status,
        },
        "code": {
            "repair": _file_binding(module_path, root),
            "daily_update": _file_binding(root / "src/tios/dataset/daily_update.py", root),
            "git_commit": _git_commit(root),
        },
    }
    encoded = _canonical(plan)
    digest = _sha256_bytes(encoded)
    return plan, encoded, digest


def write_plan(*, dataset: Path = DATASET) -> Path:
    """Publish a no-clobber content-addressed plan under the fixed plan directory."""
    _, encoded, digest = build_plan(dataset=dataset)
    directory = dataset / "repair_plans"
    directory.mkdir(mode=0o700, parents=False, exist_ok=True)
    path = directory / f"repair_plan_{digest}.json"
    if path.exists():
        if _read_bound(path) != encoded:
            raise RepairError("existing content-addressed plan is corrupt")
    else:
        _atomic_bytes(path, encoded, base=dataset)
    return path


def _load_bound_plan(path: Path, *, dataset: Path = DATASET) -> tuple[dict[str, Any], str]:
    if ".." in path.parts:
        raise RepairError("plan path traversal is forbidden")
    dataset = Path(os.path.abspath(dataset))
    candidate = path if path.is_absolute() else Path(os.path.abspath(path))
    plan_root = dataset / "repair_plans"
    try:
        relative = candidate.relative_to(dataset)
    except ValueError:
        relative = Path("__ESCAPED__")
    expected = _safe_path(dataset, relative)
    if expected != candidate or candidate.parent != plan_root:
        raise RepairError("plan is outside the fixed plan directory")
    value = _read_bound(candidate)
    digest = _sha256_bytes(value)
    if candidate.name != f"repair_plan_{digest}.json":
        raise RepairError("plan filename/content digest mismatch")
    payload = _load_json_bytes(value, "repair plan")
    if _canonical(payload) != value:
        raise RepairError("repair plan is not canonical JSON")
    return payload, digest


def _binding_path(dataset: Path, root: Path, binding: Mapping[str, Any]) -> Path:
    relative = binding.get("path")
    if not isinstance(relative, str) or relative.startswith("/") or ".." in Path(relative).parts:
        raise RepairError("plan contains an unsafe bound path")
    base = root if relative.startswith("src/") else dataset
    return _safe_path(base, relative)


def _verify_binding(path: Path, binding: Mapping[str, Any]) -> None:
    info = _strict_regular(path)
    if info.st_size != binding.get("size") or _sha256(path) != binding.get("sha256"):
        raise RepairError(f"bound input drifted: {path}")


def verify_plan_inputs(
    plan: Mapping[str, Any], *, dataset: Path = DATASET, root: Path = ROOT
) -> None:
    """Verify every state/code/evidence binding. This must precede all network calls."""
    if (
        plan.get("schema_version") != PLAN_SCHEMA
        or plan.get("repair_id") != REPAIR_ID
        or plan.get("endpoint") != REST
        or plan.get("execution_authority") != "OFFLINE_DATA_REPAIR_ONLY"
    ):
        raise RepairError("wrong repair plan identity")
    code = plan.get("code")
    state = plan.get("current_state")
    if not isinstance(code, dict) or not isinstance(state, dict):
        raise RepairError("plan bindings are malformed")
    for key in ("repair", "daily_update"):
        binding = code.get(key)
        if not isinstance(binding, dict):
            raise RepairError("code binding is malformed")
        _verify_binding(_binding_path(dataset, root, binding), binding)
    if code.get("git_commit") != _git_commit(root):
        raise RepairError("source commit drifted")
    for key in ("manifest", "status"):
        binding = state.get(key)
        if not isinstance(binding, dict):
            raise RepairError("state binding is malformed")
        _verify_binding(_binding_path(dataset, root, binding), binding)
    parquets = state.get("parquets")
    if not isinstance(parquets, list) or len(parquets) != 69:
        raise RepairError("plan must bind exactly 69 parquets")
    for binding in parquets:
        if not isinstance(binding, dict):
            raise RepairError("parquet binding is malformed")
        _verify_binding(_binding_path(dataset, root, binding), binding)
    archives = plan.get("archive_manifests")
    if not isinstance(archives, list) or len(archives) != 10:
        raise RepairError("plan must bind exactly ten archives")
    for binding in archives:
        if not isinstance(binding, dict):
            raise RepairError("archive binding is malformed")
        _verify_binding(_binding_path(dataset, root, binding), binding)
    coordinates = plan.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) != 640:
        raise RepairError("plan coordinate set is malformed")
    raw_seen: set[str] = set()
    for coordinate in coordinates:
        if not isinstance(coordinate, dict) or not isinstance(coordinate.get("evidence"), dict):
            raise RepairError("plan coordinate is malformed")
        evidence = coordinate["evidence"]
        if evidence.get("class") == "RETAINED_REST":
            binding = evidence.get("raw")
            if not isinstance(binding, dict):
                raise RepairError("retained raw binding is malformed")
            relative = binding.get("path")
            if not isinstance(relative, str) or relative in raw_seen:
                raise RepairError("retained raw bindings are duplicated or malformed")
            raw_seen.add(relative)
            path = _safe_path(dataset.parents[1], relative)
            _verify_binding(path, binding)
    if len(raw_seen) != 576:
        raise RepairError("plan must bind exactly 576 retained raw files")
    expected_plan, _, _ = build_plan(
        dataset=dataset,
        module_path=root / "src/tios/dataset/repair_normalized_multi.py",
        root=root,
    )
    if _canonical(expected_plan) != _canonical(plan):
        raise RepairError("loaded plan is not the exact current deterministic derivation")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


Fetch = Callable[[str, str, int], bytes]


def fetch_exact(symbol: str, interval: str, open_ms: int) -> bytes:
    """Fetch one exact fixed-endpoint coordinate, rejecting redirects and oversized bodies."""
    query = urllib.parse.urlencode(
        [("symbol", symbol), ("interval", interval), ("startTime", str(open_ms)), ("limit", "1")]
    )
    url = f"{REST}?{query}"
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(url, timeout=30) as response:
            if response.geturl() != url or getattr(response, "status", 200) != 200:
                raise RepairError("REST response redirected or was unsuccessful")
            body = cast(bytes, response.read(MAX_RESPONSE_BYTES + 1))
    except urllib.error.URLError as error:
        raise RepairError("REST fetch failed") from error
    if len(body) > MAX_RESPONSE_BYTES:
        raise RepairError("REST response exceeded byte limit")
    return body


def _validate_fetched(body: bytes, symbol: str, interval: str, open_ms: int) -> pa.Table:
    try:
        rows = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RepairError("REST response is not valid UTF-8 JSON") from error
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], list):
        raise RepairError("REST response must contain exactly one row")
    row = rows[0]
    if len(row) != 12 or isinstance(row[0], bool) or row[0] != open_ms:
        raise RepairError("REST response returned the wrong coordinate")
    expected_close = open_ms + INTERVAL_MS[interval] - 1
    if isinstance(row[6], bool) or row[6] != expected_close:
        raise RepairError("REST response returned the wrong close boundary")
    try:
        return to_canonical(_klines_json_to_raw(rows), "ms", symbol, interval)
    except (TypeError, ValueError, pa.ArrowException) as error:
        raise RepairError("REST response row is malformed") from error


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    except OSError as error:
        raise RepairError(f"directory fsync failed: {path}") from error
    finally:
        os.close(descriptor)


def _fsync_file(path: Path) -> None:
    with path.open("rb") as stream:
        os.fsync(stream.fileno())


def _atomic_bytes(path: Path, value: bytes, *, base: Path | None = None) -> None:
    if base is not None:
        path = _safe_path(base, path.relative_to(base), create_parents=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        parent_info = path.parent.lstat()
        if not stat.S_ISDIR(parent_info.st_mode):
            raise RepairError(f"output parent is not a real directory: {path.parent}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(value)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_parquet(path: Path, table: pa.Table) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        pyarrow.parquet.write_table(table, temporary, compression="zstd")
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _replace_rows(original: pa.Table, replacements: Sequence[pa.Table]) -> pa.Table:
    replacement = pa.concat_tables(replacements).sort_by("timestamp_open_utc")
    target_opens = replacement.column("timestamp_open_utc")
    original_opens = original.column("timestamp_open_utc")
    matched = pc.is_in(original_opens, value_set=target_opens)
    if pc.sum(matched).as_py() != replacement.num_rows:
        raise RepairError("a target coordinate is absent from its parquet")
    retained = original.filter(pc.invert(matched))
    result = pa.concat_tables([retained, replacement]).sort_by("timestamp_open_utc")
    if result.num_rows != original.num_rows or result.schema != original.schema:
        raise RepairError("replacement changed row count or schema")
    if pc.count_distinct(result.column("timestamp_open_utc")).as_py() != result.num_rows:
        raise RepairError("replacement introduced duplicate coordinates")
    return result


def _journal_path(dataset: Path, digest: str) -> Path:
    return dataset / "repair_state" / digest / "journal.json"


def _receipt_path(dataset: Path, digest: str) -> Path:
    return dataset / "repair_receipts" / f"repair_receipt_{digest}.json"


def _rollback(journal: Mapping[str, Any], *, dataset: Path) -> None:
    files = journal.get("files")
    if not isinstance(files, list):
        raise RepairError("repair journal is malformed")
    for item in reversed(files):
        if not isinstance(item, dict):
            raise RepairError("repair journal entry is malformed")
        name = item.get("path")
        before = item.get("before_sha256")
        after = item.get("after_sha256")
        backup_name = item.get("backup")
        if not all(isinstance(value, str) for value in (name, before, after, backup_name)):
            raise RepairError("repair journal binding is malformed")
        target = _safe_path(dataset, cast(str, name))
        backup = _safe_path(dataset, cast(str, backup_name))
        current = _sha256(target)
        if current == before:
            continue
        if current != after:
            raise RepairError(f"unknown third hash during rollback: {name}")
        _verify_binding(backup, {"size": backup.stat().st_size, "sha256": before})
        os.replace(backup, target)
        _fsync_directory(target.parent)


def _verify_receipt_evidence(
    receipt: Mapping[str, Any],
    *,
    dataset: Path,
    plan_digest: str,
    plan: Mapping[str, Any],
) -> None:
    expected_keys = {
        "schema_version",
        "repair_id",
        "status",
        "execution_authority",
        "plan_sha256",
        "audit_sha256",
        "affected_tables",
        "audited_tables",
        "repaired_coordinates",
    }
    if (
        set(receipt) != expected_keys
        or receipt.get("schema_version") != 1
        or receipt.get("repair_id") != REPAIR_ID
        or receipt.get("status") != "COMMITTED"
        or receipt.get("execution_authority") != "NONE"
        or receipt.get("plan_sha256") != plan_digest
        or receipt.get("affected_tables") != 64
        or receipt.get("audited_tables") != 69
        or receipt.get("repaired_coordinates") != 640
    ):
        raise RepairError("repair receipt is corrupt")
    audit_digest = receipt.get("audit_sha256")
    if not _is_sha256(audit_digest):
        raise RepairError("repair receipt has a malformed audit binding")
    audit_path = _safe_path(dataset, Path("repair_audits") / f"repair_audit_{audit_digest}.json")
    audit_bytes = _read_bound(audit_path)
    if _sha256_bytes(audit_bytes) != audit_digest:
        raise RepairError("repair audit digest mismatch")
    audit = _load_json_bytes(audit_bytes, "repair audit")
    tables = audit.get("tables")
    if (
        _canonical(audit) != audit_bytes
        or set(audit) != {"schema_version", "repair_id", "plan_sha256", "coordinates", "tables"}
        or audit.get("schema_version") != 1
        or audit.get("repair_id") != REPAIR_ID
        or audit.get("plan_sha256") != plan_digest
        or audit.get("coordinates") != 640
        or not isinstance(tables, list)
        or len(tables) != 69
        or sum(isinstance(item, dict) and item.get("affected") is True for item in tables) != 64
    ):
        raise RepairError("repair audit is corrupt")
    state = plan.get("current_state")
    if not isinstance(state, dict) or not isinstance(state.get("parquets"), list):
        raise RepairError("repair plan current state is malformed")
    planned: dict[str, Mapping[str, Any]] = {}
    for binding in state["parquets"]:
        if not isinstance(binding, dict) or not isinstance(binding.get("path"), str):
            raise RepairError("repair plan parquet binding is malformed")
        binding_path = cast(str, binding["path"])
        if binding_path in planned:
            raise RepairError("repair plan contains duplicate parquet paths")
        planned[binding_path] = binding
    if len(planned) != 69:
        raise RepairError("repair plan does not bind exactly 69 parquet paths")
    audited: set[str] = set()
    for item in cast(list[object], tables):
        if not isinstance(item, dict):
            raise RepairError("repair audit table entry is malformed")
        audit_table_path = item.get("path")
        affected = item.get("affected")
        expected_keys = {
            "path",
            "affected",
            "before_sha256",
            "after_sha256",
            "rows",
        }
        if affected is True:
            expected_keys |= {"content_sha256", "non_target_content_sha256"}
        if (
            not isinstance(audit_table_path, str)
            or audit_table_path in audited
            or audit_table_path not in planned
            or not isinstance(affected, bool)
            or set(item) != expected_keys
            or item.get("before_sha256") != planned[audit_table_path].get("sha256")
            or item.get("rows") != planned[audit_table_path].get("rows")
        ):
            raise RepairError("repair audit table set or binding is corrupt")
        after = item.get("after_sha256")
        if not _is_sha256(after):
            raise RepairError("repair audit has a malformed post-repair hash")
        target = _safe_path(dataset, audit_table_path)
        _verify_binding(target, {"size": target.stat().st_size, "sha256": after})
        audited.add(audit_table_path)
    if audited != set(planned):
        raise RepairError("repair audit does not cover the exact planned parquet set")
    for key in ("manifest", "status"):
        binding = state.get(key)
        if binding is not None:
            if not isinstance(binding, dict):
                raise RepairError(f"repair plan {key} binding is malformed")
            _verify_binding(_binding_path(dataset, ROOT, binding), binding)


def _validate_recovery_journal(
    journal: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    plan_digest: str,
    dataset: Path,
    root: Path,
) -> None:
    expected_plan, _, _ = build_plan(
        dataset=dataset,
        module_path=root / "src/tios/dataset/repair_normalized_multi.py",
        root=root,
    )
    expected_static = {key: value for key, value in expected_plan.items() if key != "current_state"}
    supplied_static = {key: value for key, value in plan.items() if key != "current_state"}
    if _canonical(expected_static) != _canonical(supplied_static):
        raise RepairError("recovery plan static derivation is not authentic")
    state = plan.get("current_state")
    if not isinstance(state, dict) or not isinstance(state.get("parquets"), list):
        raise RepairError("recovery plan current state is malformed")
    planned: dict[str, Mapping[str, Any]] = {}
    for binding in state["parquets"]:
        if not isinstance(binding, dict) or not isinstance(binding.get("path"), str):
            raise RepairError("recovery plan parquet binding is malformed")
        binding_path = cast(str, binding["path"])
        if binding_path in planned:
            raise RepairError("recovery plan contains duplicate parquet paths")
        planned[binding_path] = binding
    affected = {
        f"{row['table']}.parquet" for row in cast(list[dict[str, Any]], plan["coordinates"])
    }
    files = journal.get("files")
    if (
        set(journal) != {"schema_version", "repair_id", "plan_sha256", "state", "files"}
        or journal.get("schema_version") != 1
        or journal.get("repair_id") != REPAIR_ID
        or journal.get("plan_sha256") != plan_digest
        or journal.get("state") != "PREPARED"
        or not isinstance(files, list)
        or len(files) != 64
        or len(affected) != 64
    ):
        raise RepairError("repair recovery journal envelope is corrupt")
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {
            "path",
            "backup",
            "before_sha256",
            "after_sha256",
        }:
            raise RepairError("repair recovery journal entry is corrupt")
        journal_path = item.get("path")
        if (
            not isinstance(journal_path, str)
            or journal_path in seen
            or journal_path not in affected
            or journal_path not in planned
        ):
            raise RepairError("repair recovery journal path set is corrupt")
        expected_backup = f"repair_state/{plan_digest}/backup/{journal_path}"
        after = item.get("after_sha256")
        if (
            item.get("backup") != expected_backup
            or item.get("before_sha256") != planned[journal_path].get("sha256")
            or not _is_sha256(after)
        ):
            raise RepairError("repair recovery journal binding is corrupt")
        seen.add(journal_path)
    if seen != affected:
        raise RepairError("repair recovery journal does not cover the exact affected set")


def _remove_uncommitted_state(path: Path, *, dataset: Path) -> None:
    relative = path.relative_to(dataset)
    candidate = _safe_path(dataset, relative)
    info = candidate.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise RepairError("uncommitted repair state is not a real directory")
    for item in candidate.rglob("*"):
        child = item.lstat()
        if stat.S_ISDIR(child.st_mode):
            continue
        if not stat.S_ISREG(child.st_mode) or child.st_nlink != 1:
            raise RepairError("uncommitted repair state contains an unsafe entry")
    shutil.rmtree(candidate)
    _fsync_directory(candidate.parent)


def recover(*, plan_path: Path, dataset: Path = DATASET, root: Path = ROOT) -> str:
    """Deterministically finish success or roll back an interrupted pre-receipt apply."""
    plan, digest = _load_bound_plan(plan_path, dataset=dataset)
    with _apply_guard(dataset):
        receipt = _receipt_path(dataset, digest)
        if receipt.exists():
            receipt = _safe_path(dataset, receipt.relative_to(dataset))
            retained = _load_json_bytes(_read_bound(receipt), "repair receipt")
            _verify_receipt_evidence(retained, dataset=dataset, plan_digest=digest, plan=plan)
            return "ALREADY_COMMITTED"
        journal_path = _journal_path(dataset, digest)
        if not journal_path.exists():
            return "NO_RECOVERY_NEEDED"
        journal = _load_json_bytes(_read_bound(journal_path), "repair journal")
        _validate_recovery_journal(
            journal, plan=plan, plan_digest=digest, dataset=dataset, root=root
        )
        _rollback(journal, dataset=dataset)
        return "ROLLED_BACK"


@contextmanager
def _apply_guard(dataset: Path) -> Iterator[None]:
    with _process_lock(dataset):
        yield


def apply_plan(
    *,
    plan_path: Path,
    dataset: Path = DATASET,
    root: Path = ROOT,
    fetch: Fetch = fetch_exact,
) -> dict[str, object]:
    """Apply a bound plan transactionally; success is idempotent and performs zero fetches."""
    plan, digest = _load_bound_plan(plan_path, dataset=dataset)
    receipt_path = _receipt_path(dataset, digest)
    with _apply_guard(dataset):
        if receipt_path.exists():
            receipt_path = _safe_path(dataset, receipt_path.relative_to(dataset))
            retained_receipt = _load_json_bytes(_read_bound(receipt_path), "repair receipt")
            _verify_receipt_evidence(
                retained_receipt, dataset=dataset, plan_digest=digest, plan=plan
            )
            return retained_receipt
        journal_path = _journal_path(dataset, digest)
        if journal_path.exists():
            journal_path = _safe_path(dataset, journal_path.relative_to(dataset))
            recovery_journal = _load_json_bytes(_read_bound(journal_path), "repair journal")
            _validate_recovery_journal(
                recovery_journal,
                plan=plan,
                plan_digest=digest,
                dataset=dataset,
                root=root,
            )
            _rollback(recovery_journal, dataset=dataset)
            _remove_uncommitted_state(journal_path.parent, dataset=dataset)
        elif journal_path.parent.exists():
            _remove_uncommitted_state(journal_path.parent, dataset=dataset)
        verify_plan_inputs(plan, dataset=dataset, root=root)

        coordinates = cast(list[dict[str, Any]], plan["coordinates"])
        fetched: dict[str, list[pa.Table]] = {}
        raw_dir = dataset / "repair_raw" / digest
        # Fetch and retain every exact response before reading any response semantically.
        bodies: list[tuple[dict[str, Any], bytes, Path]] = []
        for row in coordinates:
            body = fetch(row["symbol"], row["interval"], row["open_ms"])
            raw_digest = _sha256_bytes(body)
            raw_path = raw_dir / row["table"] / f"{row['open_ms']}_{raw_digest}.json"
            if raw_path.exists() and _read_bound(raw_path, MAX_RESPONSE_BYTES) != body:
                raise RepairError("content-addressed fetched evidence is corrupt")
            if not raw_path.exists():
                _atomic_bytes(raw_path, body, base=dataset)
            bodies.append((row, body, raw_path))
        for row, body, raw_path in bodies:
            if _sha256(raw_path) != _sha256_bytes(body):
                raise RepairError("retained fetched evidence changed before validation")
            fetched.setdefault(row["table"], []).append(
                _validate_fetched(body, row["symbol"], row["interval"], row["open_ms"])
            )

        state = cast(dict[str, Any], plan["current_state"])
        bindings = {Path(row["path"]).stem: row for row in state["parquets"]}
        stage = _safe_path(
            dataset, Path("repair_state") / digest / "stage" / ".sentinel", create_parents=True
        ).parent
        backup = _safe_path(
            dataset, Path("repair_state") / digest / "backup" / ".sentinel", create_parents=True
        ).parent
        journal_files: list[dict[str, object]] = []
        audit_tables: list[dict[str, object]] = []
        for name in sorted(bindings):
            binding = bindings[name]
            path = _safe_path(dataset, binding["path"])
            original = pyarrow.parquet.read_table(path)
            if name not in fetched:
                audit_tables.append(
                    {
                        "path": binding["path"],
                        "affected": False,
                        "before_sha256": binding["sha256"],
                        "after_sha256": binding["sha256"],
                        "rows": original.num_rows,
                    }
                )
                continue
            repaired = _replace_rows(original, fetched[name])
            if _logical_without(
                repaired,
                frozenset(row["open_ms"] for row in coordinates if row["table"] == name),
            ) != binding.get("non_target_content_sha256"):
                raise RepairError(f"non-target logical content changed for {name}")
            stage_path = stage / path.name
            pyarrow.parquet.write_table(repaired, stage_path, compression="zstd")
            _fsync_file(stage_path)
            reread = pyarrow.parquet.read_table(stage_path)
            if reread.num_rows != original.num_rows or reread.schema != original.schema:
                raise RepairError(f"staged parquet validation failed for {name}")
            backup_path = backup / path.name
            shutil.copyfile(path, backup_path)
            _fsync_file(backup_path)
            if _sha256(backup_path) != binding["sha256"]:
                raise RepairError(f"backup validation failed for {name}")
            after = _sha256(stage_path)
            journal_files.append(
                {
                    "path": path.name,
                    "backup": backup_path.relative_to(dataset).as_posix(),
                    "before_sha256": binding["sha256"],
                    "after_sha256": after,
                }
            )
            audit_tables.append(
                {
                    "path": path.name,
                    "affected": True,
                    "before_sha256": binding["sha256"],
                    "after_sha256": after,
                    "rows": reread.num_rows,
                    "content_sha256": content_sha256(reread.replace_schema_metadata(None)),
                    "non_target_content_sha256": binding["non_target_content_sha256"],
                }
            )
        if len(journal_files) != 64 or len(audit_tables) != 69:
            raise RepairError("staging did not cover the exact table set")
        _fsync_directory(stage)
        _fsync_directory(backup)
        journal: dict[str, object] = {
            "schema_version": 1,
            "repair_id": REPAIR_ID,
            "plan_sha256": digest,
            "state": "PREPARED",
            "files": journal_files,
        }
        _atomic_bytes(journal_path, _canonical(journal), base=dataset)
        try:
            for item in journal_files:
                os.replace(stage / cast(str, item["path"]), dataset / cast(str, item["path"]))
            _fsync_directory(dataset)
            for item in journal_files:
                if _sha256(dataset / cast(str, item["path"])) != item["after_sha256"]:
                    raise RepairError("post-publication parquet audit failed")
            audit: dict[str, object] = {
                "schema_version": 1,
                "repair_id": REPAIR_ID,
                "plan_sha256": digest,
                "coordinates": 640,
                "tables": audit_tables,
            }
            audit_bytes = _canonical(audit)
            audit_digest = _sha256_bytes(audit_bytes)
            audit_path = dataset / "repair_audits" / f"repair_audit_{audit_digest}.json"
            _atomic_bytes(audit_path, audit_bytes, base=dataset)
            receipt: dict[str, object] = {
                "schema_version": 1,
                "repair_id": REPAIR_ID,
                "status": "COMMITTED",
                "execution_authority": "NONE",
                "plan_sha256": digest,
                "audit_sha256": audit_digest,
                "affected_tables": 64,
                "audited_tables": 69,
                "repaired_coordinates": 640,
            }
            # The receipt is deliberately the final publication and sole commit marker.
            _atomic_bytes(receipt_path, _canonical(receipt), base=dataset)
            return receipt
        except BaseException:
            _rollback(journal, dataset=dataset)
            raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("plan")
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--plan", type=Path, required=True)
    recover_parser = subparsers.add_parser("recover")
    recover_parser.add_argument("--plan", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    arguments = _parser().parse_args(argv)
    if arguments.command == "plan":
        print(write_plan())
    elif arguments.command == "apply":
        print(json.dumps(apply_plan(plan_path=arguments.plan), sort_keys=True))
    else:
        print(recover(plan_path=arguments.plan))


if __name__ == "__main__":
    main()
