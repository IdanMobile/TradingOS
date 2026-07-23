"""Fail-closed short-frame bar hierarchy and availability conformance.

This module performs timing and data-structure checks only.  It has no venue
connection and computes no execution price or outcome measure.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq
import yaml

from tios.dataset.normalize import content_sha256
from tios.trading_domain import Timeframe

PROTOCOL_ID = "SHORTFRAME-BAR-HIERARCHY-AND-FILL-AVAILABILITY-V1"
DATASET_ID = "DS-CRYPTO-SPOT-SHORTFRAMES-V1"
MANIFEST_SHA256 = "05ccd69008c54f14f3b3299226e27c313d60fa224bf9b701e11ecc92beec7ce4"
QUALITY_SHA256 = "cd281975e187f8e1cf43fd62fe03585891cf8c02cd44baf319575e42837f1186"
ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_RELATIVE = Path("research/SHORTFRAME_BAR_HIERARCHY_AND_FILL_AVAILABILITY_V1.yaml")
SOURCE_RELATIVE = Path("src/tios/dataset/shortframe_execution_conformance.py")
SCRIPT_RELATIVE = Path("scripts/verify_shortframe_execution_conformance.py")
COMMITTED_SURFACE = (PROTOCOL_RELATIVE, SOURCE_RELATIVE, SCRIPT_RELATIVE)
SYMBOLS = ("BTCUSDT", "ETHUSDT")
MAPPINGS = (("1m", "5m", 5), ("1m", "15m", 15), ("5m", "15m", 3))
TABLE_KEYS = tuple(f"{symbol}_{interval}" for symbol in SYMBOLS for interval in ("1m", "5m", "15m"))
ADDITIVE_FIELDS = (
    "volume_base",
    "quote_volume",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
)
STORED_DECIMAL_UNIT = Decimal("0.00000001")
VOLUME_TOLERANCE = Decimal("0")
START_MONTH = "2021-01"
END_MONTH = "2026-06"
CUTOFF_UTC = datetime(2026, 7, 1, tzinfo=UTC)
DETAIL_LIMIT = 50
PROTOCOL_OBJECTIVE = (
    "Verify that frozen lower-frame bars reproduce their aligned native higher-frame "
    "parents, and that an observation is never available before its nominal aligned "
    "interval boundary."
)
COMPLETE_WINDOW_RULE = (
    "Every exact aligned child-interval open from the parent open through the parent "
    "boundary minus one child interval is present. Missing children are never imputed."
)
EARLY_CLOSE_CHECK = {
    "evidence": "dataset quality report close_time_semantics inventories",
    "requirement": ("early source closes must not advance the aligned availability boundary"),
}
LIMITATIONS = [
    "One-minute bars cannot resolve intraminute path.",
    "One-minute bars cannot resolve spread.",
    "One-minute bars cannot resolve market impact.",
    "One-minute bars cannot resolve latency.",
    "One-minute bars cannot resolve queue priority.",
    "One-minute bars cannot resolve partial fill.",
]
OUTPUT_SCHEMA_KEYS = {
    "schema_version",
    "protocol_id",
    "protocol_sha256",
    "dataset",
    "verification",
    "limitations",
    "execution_authority",
    "verification_status",
    "hierarchy_status",
    "status",
}
PROHIBITED_OUTPUT_LIST = [
    "signals",
    "trades",
    "returns",
    "pnl",
    "sharpe",
    "drawdown",
    "win_rate",
    "ranking",
    "selection",
    "campaign",
    "trial_budget",
]
PROHIBITED_OUTPUT_KEYS = set(PROHIBITED_OUTPUT_LIST)
INVENTORY_BINDINGS = {
    "source_divergence_records": {
        "count": 128,
        "sha256": "f2bd636818eca622bf2eef0bde9caecfc63eb86bcc0f17bec85f711ef9884c86",
    },
    "incomplete_child_records": {
        "count": 14,
        "sha256": "903ba077846d3ceef579d858322d04e4ffcfc010443cd1f43b07ce32aa52336b",
    },
    "unavailable_gap_fill_records": {
        "count": 42,
        "sha256": "c832af4617df0a4495b639ae73629d34ddb4f7cf03dc998c0a526486d25e87b8",
    },
    "outside_window_fill_records": {
        "count": 6,
        "sha256": "e001fb8ec98c610637b03da01dd20b58e3a130e5a6042e277f6c7cbe094e9457",
    },
}


@dataclass(frozen=True, slots=True)
class ConformancePaths:
    """Fixed relative layout rooted at one real repository directory."""

    repo_root: Path
    expected_manifest_sha256: str = MANIFEST_SHA256
    expected_quality_sha256: str = QUALITY_SHA256

    @property
    def protocol(self) -> Path:
        return self.repo_root / PROTOCOL_RELATIVE

    @property
    def stable_manifest(self) -> Path:
        return self.repo_root / f"artifacts/datasets/{DATASET_ID}.manifest.json"

    @property
    def archived_manifest(self) -> Path:
        return self.repo_root / (
            f"artifacts/datasets/{DATASET_ID}.manifest_{self.expected_manifest_sha256}.json"
        )

    @property
    def stable_quality(self) -> Path:
        return self.repo_root / f"artifacts/datasets/{DATASET_ID}.QUALITY_REPORT.json"

    @property
    def archived_quality(self) -> Path:
        return self.repo_root / (
            f"artifacts/datasets/{DATASET_ID}.QUALITY_REPORT_{self.expected_quality_sha256}.json"
        )

    @property
    def dataset_root(self) -> Path:
        return self.repo_root / f"data/normalized/{DATASET_ID}"

    @property
    def output_root(self) -> Path:
        return self.repo_root / "artifacts/datasets/shortframe_execution_conformance"


DEFAULT_PATHS = ConformancePaths(ROOT)


def interval_microseconds(interval: str) -> int:
    """Return the canonical interval duration for every supported timeframe."""
    return Timeframe(interval).seconds * 1_000_000


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _canonical_array(value: list[dict[str, Any]]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _require_real_root(path: Path) -> Path:
    absolute = path.absolute()
    if not absolute.is_dir() or absolute.is_symlink() or absolute.resolve() != absolute:
        raise ValueError("repository root must be a real non-symlink directory")
    return absolute


def _require_confined_file(path: Path, *, root: Path, label: str) -> Path:
    exact_root = _require_real_root(root)
    absolute = path.absolute()
    try:
        relative = absolute.relative_to(exact_root)
    except ValueError as error:
        raise ValueError(f"{label} escapes the fixed repository root") from error
    current = exact_root
    for part in relative.parts:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError as error:
            raise ValueError(f"{label} is missing") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"{label} has a symlinked ancestor or final path")
    metadata = absolute.lstat()
    if not stat.S_ISREG(metadata.st_mode) or absolute.resolve() != absolute:
        raise ValueError(f"{label} must be a real regular file")
    return absolute


def _require_confined_directory(path: Path, *, root: Path, label: str) -> Path:
    exact_root = _require_real_root(root)
    absolute = path.absolute()
    try:
        relative = absolute.relative_to(exact_root)
    except ValueError as error:
        raise ValueError(f"{label} escapes the fixed repository root") from error
    current = exact_root
    for part in relative.parts:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError as error:
            raise ValueError(f"{label} is missing") from error
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"{label} has a symlinked or non-directory component")
    if absolute.resolve() != absolute:
        raise ValueError(f"{label} is not a real directory")
    return absolute


def _load_mapping(path: Path, *, root: Path, label: str) -> dict[str, Any]:
    retained = _require_confined_file(path, root=root, label=label)
    loaded = yaml.safe_load(retained.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{label} must contain one mapping")
    return loaded


def _validate_protocol(
    protocol: Mapping[str, Any], *, require_production_inventory: bool = True
) -> None:
    expected_top = {
        "schema",
        "protocol_id",
        "mode",
        "objective",
        "dataset",
        "scope",
        "aggregation",
        "availability",
        "authenticated_early_close_check",
        "expected_inventory",
        "output",
        "limitations",
        "governance",
        "committed_surface",
    }
    if set(protocol) != expected_top:
        raise ValueError("protocol top-level schema drift")
    dataset = protocol.get("dataset")
    scope = protocol.get("scope")
    aggregation = protocol.get("aggregation")
    availability = protocol.get("availability")
    output = protocol.get("output")
    governance = protocol.get("governance")
    expected_inventory = protocol.get("expected_inventory")
    if (
        protocol.get("schema") != "tios-shortframe-bar-hierarchy-and-fill-availability-v1"
        or protocol.get("protocol_id") != PROTOCOL_ID
        or protocol.get("mode") != "NON_PERFORMANCE_TIMING_CONFORMANCE"
        or protocol.get("objective") != PROTOCOL_OBJECTIVE
        or not isinstance(dataset, dict)
        or not isinstance(scope, dict)
        or not isinstance(aggregation, dict)
        or not isinstance(availability, dict)
        or not isinstance(output, dict)
        or not isinstance(governance, dict)
        or not isinstance(expected_inventory, dict)
    ):
        raise ValueError("protocol identity or structure drift")
    expected_dataset = {
        "dataset_id": DATASET_ID,
        "stable_manifest_path": f"artifacts/datasets/{DATASET_ID}.manifest.json",
        "manifest_sha256": MANIFEST_SHA256,
        "content_addressed_manifest_path": (
            f"artifacts/datasets/{DATASET_ID}.manifest_{MANIFEST_SHA256}.json"
        ),
        "stable_quality_path": f"artifacts/datasets/{DATASET_ID}.QUALITY_REPORT.json",
        "quality_sha256": QUALITY_SHA256,
        "content_addressed_quality_path": (
            f"artifacts/datasets/{DATASET_ID}.QUALITY_REPORT_{QUALITY_SHA256}.json"
        ),
        "normalized_root": f"data/normalized/{DATASET_ID}",
    }
    if dataset != expected_dataset:
        raise ValueError("protocol dataset binding drift")
    if (
        set(scope) != {"instruments", "mappings", "start_month", "end_month", "cutoff_utc"}
        or scope.get("instruments") != list(SYMBOLS)
        or scope.get("mappings")
        != [
            {"child_interval": child, "parent_interval": parent, "expected_children": count}
            for child, parent, count in MAPPINGS
        ]
        or scope.get("start_month") != START_MONTH
        or scope.get("end_month") != END_MONTH
        or scope.get("cutoff_utc") != CUTOFF_UTC.isoformat()
    ):
        raise ValueError("protocol scope drift")
    tolerance = aggregation.get("decimal_tolerance")
    if (
        set(aggregation)
        != {
            "complete_window",
            "exact_fields",
            "additive_decimal_fields",
            "decimal_tolerance",
            "classification",
            "source_truth",
        }
        or aggregation.get("complete_window") != COMPLETE_WINDOW_RULE
        or aggregation.get("exact_fields")
        != {
            "open": "first",
            "high": "maximum",
            "low": "minimum",
            "close": "last",
            "close_timestamp_utc": "last",
            "trade_count": "sum",
        }
        or aggregation.get("additive_decimal_fields") != list(ADDITIVE_FIELDS)
        or aggregation.get("classification")
        != [
            "EXACT_CONFORMANT",
            "SOURCE_DIVERGENCE",
            "INCOMPLETE_CHILDREN",
            "PARENT_MISSING",
        ]
        or aggregation.get("source_truth") != "native_higher_frame_bar"
        or not isinstance(tolerance, dict)
        or set(tolerance) != {"unit", "maximum_absolute_difference", "rationale"}
        or Decimal(str(tolerance.get("unit"))) != STORED_DECIMAL_UNIT
        or Decimal(str(tolerance.get("maximum_absolute_difference"))) != VOLUME_TOLERANCE
        or tolerance.get("rationale")
        != (
            "No tolerance. Both sides use frozen decimal128(38,8) values, and native "
            "higher-frame bars remain source truth when exact stored values diverge."
        )
    ):
        raise ValueError("protocol aggregation drift")
    if (
        set(availability)
        != {
            "rule",
            "raw_close_timestamp_may_advance_availability",
            "exact_one_minute_open_required",
            "absent_open_action",
            "gap_action",
            "at_or_after_cutoff_action",
            "hypothetical_only",
            "execution_price_computed",
        }
        or availability.get("rule") != "aligned_parent_open_plus_parent_interval"
        or availability.get("raw_close_timestamp_may_advance_availability") is not False
        or availability.get("exact_one_minute_open_required") is not True
        or availability.get("absent_open_action") != "BLOCK"
        or availability.get("gap_action") != "BLOCK"
        or availability.get("at_or_after_cutoff_action") != "BLOCK"
        or availability.get("hypothetical_only") is not True
        or availability.get("execution_price_computed") is not False
    ):
        raise ValueError("protocol availability drift")
    if (
        set(expected_inventory) != {"canonical_encoding", "arrays"}
        or expected_inventory.get("canonical_encoding")
        != "UTF-8 JSON, recursively sorted object keys, compact separators, no trailing newline"
        or (require_production_inventory and expected_inventory.get("arrays") != INVENTORY_BINDINGS)
    ):
        raise ValueError("protocol expected inventory drift")
    if (
        set(output)
        != {
            "schema_version",
            "bounded_detail_limit",
            "deterministic_fresh_reads",
            "publish_root",
            "current_name",
            "content_addressed_prefix",
            "prohibited_fields",
        }
        or output.get("schema_version") != 1
        or output.get("bounded_detail_limit") != DETAIL_LIMIT
        or output.get("deterministic_fresh_reads") != 2
        or output.get("publish_root") != "artifacts/datasets/shortframe_execution_conformance"
        or output.get("current_name") != "CURRENT.json"
        or output.get("content_addressed_prefix") != "shortframe_execution_conformance_"
        or output.get("prohibited_fields") != PROHIBITED_OUTPUT_LIST
    ):
        raise ValueError("protocol output contract drift")
    if protocol.get("authenticated_early_close_check") != EARLY_CLOSE_CHECK:
        raise ValueError("protocol authenticated early-close contract drift")
    if protocol.get("limitations") != LIMITATIONS:
        raise ValueError("protocol limitations drift")
    if governance != {
        "family_id": "NONE",
        "trial_budget_effect": "NONE",
        "execution_authority": "NONE",
        "strategy_authority": "NONE",
    } or protocol.get("committed_surface") != [
        relative.as_posix() for relative in COMMITTED_SURFACE
    ]:
        raise ValueError("protocol governance drift")


def _require_head_blob(path: Path, *, paths: ConformancePaths) -> None:
    root = _require_real_root(paths.repo_root)
    retained = _require_confined_file(path, root=root, label="committed surface")
    relative = retained.relative_to(root).as_posix()
    tree = subprocess.run(
        ["git", "ls-tree", "HEAD", "--", relative],
        cwd=root,
        capture_output=True,
        text=True,
    )
    fields = tree.stdout.strip().split(maxsplit=3)
    if tree.returncode != 0 or len(fields) != 4 or fields[1] != "blob":
        raise ValueError(f"untracked committed surface: {relative}")
    shown = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=root, capture_output=True)
    if shown.returncode != 0 or shown.stdout != retained.read_bytes():
        raise ValueError(f"committed surface bytes differ from HEAD: {relative}")


def _committed_identity(paths: ConformancePaths) -> dict[str, Any]:
    for relative in COMMITTED_SURFACE:
        _require_head_blob(paths.repo_root / relative, paths=paths)
    state = subprocess.run(
        ["git", "status", "--porcelain", "--", *(path.as_posix() for path in COMMITTED_SURFACE)],
        cwd=paths.repo_root,
        capture_output=True,
        text=True,
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=paths.repo_root, capture_output=True, text=True
    )
    commit_id = commit.stdout.strip()
    if (
        state.returncode != 0
        or state.stdout
        or commit.returncode != 0
        or re.fullmatch(r"[0-9a-f]{40}", commit_id) is None
    ):
        raise ValueError("production conformance requires committed source and protocol bytes")
    return {
        "git_commit": commit_id,
        "surface": [
            {
                "path": relative.as_posix(),
                "sha256": _sha256_file(paths.repo_root / relative),
            }
            for relative in COMMITTED_SURFACE
        ],
    }


def _load_exact_pair(
    stable: Path,
    archived: Path,
    expected_sha: str,
    *,
    paths: ConformancePaths,
    label: str,
) -> dict[str, Any]:
    stable_file = _require_confined_file(stable, root=paths.repo_root, label=f"stable {label}")
    archived_file = _require_confined_file(
        archived, root=paths.repo_root, label=f"content-addressed {label}"
    )
    stable_bytes = stable_file.read_bytes()
    if (
        _sha256_bytes(stable_bytes) != expected_sha
        or archived_file.read_bytes() != stable_bytes
        or _sha256_file(archived_file) != expected_sha
    ):
        raise ValueError(f"stable/content-addressed {label} binding drift")
    loaded = json.loads(stable_bytes)
    if not isinstance(loaded, dict):
        raise ValueError(f"{label} must be one JSON object")
    return loaded


def _verify_evidence(paths: ConformancePaths) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _load_exact_pair(
        paths.stable_manifest,
        paths.archived_manifest,
        paths.expected_manifest_sha256,
        paths=paths,
        label="dataset manifest",
    )
    quality = _load_exact_pair(
        paths.stable_quality,
        paths.archived_quality,
        paths.expected_quality_sha256,
        paths=paths,
        label="quality report",
    )
    manifest_tables = manifest.get("tables")
    quality_tables = quality.get("quality_run2", {}).get("tables")
    if (
        manifest.get("dataset_id") != DATASET_ID
        or manifest.get("execution_authority") != "NONE"
        or manifest.get("cutoff_utc") != CUTOFF_UTC.isoformat()
        or manifest.get("quality_report_sha256") != paths.expected_quality_sha256
        or quality.get("dataset_id") != DATASET_ID
        or quality.get("overall") != "PASS"
        or quality.get("execution_authority") != "NONE"
        or not isinstance(manifest_tables, dict)
        or not isinstance(quality_tables, dict)
        or set(manifest_tables) != set(TABLE_KEYS)
        or set(quality_tables) != set(TABLE_KEYS)
        or manifest_tables != quality_tables
        or any(record.get("status") != "PASS" for record in manifest_tables.values())
    ):
        raise ValueError("dataset evidence identity, grid, or PASS status drift")
    return manifest, quality


def _verify_actual_tables(paths: ConformancePaths, manifest: Mapping[str, Any]) -> None:
    dataset_root = _require_confined_directory(
        paths.dataset_root, root=paths.repo_root, label="normalized dataset root"
    )
    expected_names = {f"{key}.parquet" for key in TABLE_KEYS}
    if {entry.name for entry in dataset_root.iterdir()} != expected_names:
        raise ValueError("normalized dataset file grid drift")
    manifest_tables = manifest["tables"]
    for key in TABLE_KEYS:
        path = _require_confined_file(
            dataset_root / f"{key}.parquet",
            root=paths.repo_root,
            label=f"normalized table {key}",
        )
        record = manifest_tables[key]
        if _sha256_file(path) != record.get("parquet_sha256"):
            raise ValueError(f"Parquet byte hash drift: {key}")
        table = pq.read_table(path)
        logical_hash = content_sha256(table.combine_chunks())
        if (
            table.num_rows != record.get("rows")
            or str(table.schema) != record.get("schema")
            or logical_hash != record.get("content_sha256")
        ):
            raise ValueError(f"Parquet logical identity drift: {key}")


def _verify_actual_table_bytes(paths: ConformancePaths, manifest: Mapping[str, Any]) -> None:
    """Recheck immutable bytes between analyses without rematerializing Arrow tables."""
    dataset_root = _require_confined_directory(
        paths.dataset_root, root=paths.repo_root, label="normalized dataset root"
    )
    expected_names = {f"{key}.parquet" for key in TABLE_KEYS}
    if {entry.name for entry in dataset_root.iterdir()} != expected_names:
        raise ValueError("normalized dataset file grid drift")
    for key in TABLE_KEYS:
        path = _require_confined_file(
            dataset_root / f"{key}.parquet",
            root=paths.repo_root,
            label=f"normalized table {key}",
        )
        if _sha256_file(path) != manifest["tables"][key].get("parquet_sha256"):
            raise ValueError(f"Parquet byte hash drift: {key}")


def _utc_from_microseconds(value: int) -> str:
    return (
        datetime.fromtimestamp(value / 1_000_000, tz=UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _bounded_gap_inventory(
    connection: duckdb.DuckDBPyConnection,
    child_path: Path,
    child_interval: str,
) -> dict[str, Any]:
    step = interval_microseconds(child_interval)
    summary = connection.execute(
        """
        WITH ordered AS (
          SELECT
            epoch_us(timestamp_open_utc) AS opened_us,
            lag(epoch_us(timestamp_open_utc)) OVER (ORDER BY timestamp_open_utc) AS prior_us
          FROM read_parquet(?)
        ),
        gaps AS (
          SELECT prior_us, opened_us, CAST((opened_us - prior_us) / ? - 1 AS BIGINT)
            AS absent_open_count
          FROM ordered
          WHERE prior_us IS NOT NULL AND opened_us - prior_us > ?
        )
        SELECT count(*), coalesce(sum(absent_open_count), 0)
        FROM gaps
        """,
        [str(child_path), step, step],
    ).fetchone()
    if summary is None:
        raise ValueError("gap summary query returned no row")
    rows = connection.execute(
        """
        WITH ordered AS (
          SELECT
            epoch_us(timestamp_open_utc) AS opened_us,
            lag(epoch_us(timestamp_open_utc)) OVER (ORDER BY timestamp_open_utc) AS prior_us
          FROM read_parquet(?)
        )
        SELECT prior_us, opened_us, CAST((opened_us - prior_us) / ? - 1 AS BIGINT)
        FROM ordered
        WHERE prior_us IS NOT NULL AND opened_us - prior_us > ?
        ORDER BY opened_us
        LIMIT ?
        """,
        [str(child_path), step, step, DETAIL_LIMIT],
    ).fetchall()
    boundary_count = int(summary[0])
    return {
        "boundary_count": boundary_count,
        "absent_open_count": int(summary[1]),
        "details": [
            {
                "left_open_utc": _utc_from_microseconds(int(left)),
                "right_open_utc": _utc_from_microseconds(int(right)),
                "absent_open_count": int(count),
            }
            for left, right, count in rows
        ],
        "details_truncated": boundary_count > DETAIL_LIMIT,
    }


def _format_comparison_value(field: str, value: Any) -> str | int:
    if field == "trade_count":
        return int(value)
    if field == "close_timestamp_utc":
        return _utc_from_microseconds(int(value))
    return f"{Decimal(value):.8f}"


def _has_early_child(
    early_opens: set[str],
    *,
    parent_open_us: int,
    parent_us: int,
) -> bool:
    left = _utc_from_microseconds(parent_open_us)
    right = _utc_from_microseconds(parent_open_us + parent_us)
    return any(left <= opened < right for opened in early_opens)


def _analyze_mapping(
    *,
    symbol: str,
    child_interval: str,
    parent_interval: str,
    expected_children: int,
    child_early_opens: set[str],
    parent_early_opens: set[str],
    paths: ConformancePaths,
) -> dict[str, Any]:
    child_path = _require_confined_file(
        paths.dataset_root / f"{symbol}_{child_interval}.parquet",
        root=paths.repo_root,
        label=f"analysis child {symbol}_{child_interval}",
    )
    parent_path = _require_confined_file(
        paths.dataset_root / f"{symbol}_{parent_interval}.parquet",
        root=paths.repo_root,
        label=f"analysis parent {symbol}_{parent_interval}",
    )
    child_us = interval_microseconds(child_interval)
    parent_us = interval_microseconds(parent_interval)
    connection = duckdb.connect()
    complete = 0
    incomplete = 0
    divergences = 0
    incomplete_inventory: list[dict[str, Any]] = []
    divergence_inventory: list[dict[str, Any]] = []
    try:
        child_shape = connection.execute(
            """
            SELECT
              count(*) AS rows,
              count(DISTINCT epoch_us(timestamp_open_utc)) AS unique_opens,
              count(*) FILTER (WHERE epoch_us(timestamp_open_utc) % ? != 0) AS misaligned
            FROM read_parquet(?)
            """,
            [child_us, str(child_path)],
        ).fetchone()
        parent_shape = connection.execute(
            """
            SELECT
              count(*) AS rows,
              count(DISTINCT epoch_us(timestamp_open_utc)) AS unique_opens,
              count(*) FILTER (WHERE epoch_us(timestamp_open_utc) % ? != 0) AS misaligned
            FROM read_parquet(?)
            """,
            [parent_us, str(parent_path)],
        ).fetchone()
        if (
            child_shape is None
            or parent_shape is None
            or child_shape[0] != child_shape[1]
            or parent_shape[0] != parent_shape[1]
            or child_shape[2]
            or parent_shape[2]
        ):
            raise ValueError(f"duplicate or misaligned opens: {symbol} {parent_interval}")
        parent_missing = connection.execute(
            """
            WITH child_buckets AS (
              SELECT DISTINCT
                CAST(floor(epoch_us(timestamp_open_utc) / ?) * ? AS BIGINT) AS bucket_us
              FROM read_parquet(?)
            ),
            parent_opens AS (
              SELECT epoch_us(timestamp_open_utc) AS opened_us
              FROM read_parquet(?)
            )
            SELECT count(*)
            FROM child_buckets
            LEFT JOIN parent_opens ON parent_opens.opened_us = child_buckets.bucket_us
            WHERE parent_opens.opened_us IS NULL
            """,
            [parent_us, parent_us, str(child_path), str(parent_path)],
        ).fetchone()
        if parent_missing is None or int(parent_missing[0]) != 0:
            raise ValueError(
                f"PARENT_MISSING classification present: {symbol} "
                f"{child_interval}->{parent_interval}"
            )
        cursor = connection.execute(
            """
            WITH children AS (
              SELECT
                CAST(floor(epoch_us(timestamp_open_utc) / ?) * ? AS BIGINT) AS bucket_us,
                count(*) AS child_count,
                min(epoch_us(timestamp_open_utc)) AS first_child_open_us,
                max(epoch_us(timestamp_open_utc)) AS last_child_open_us,
                arg_min(open, timestamp_open_utc) AS derived_open,
                max(high) AS derived_high,
                min(low) AS derived_low,
                arg_max(close, timestamp_open_utc) AS derived_close,
                arg_max(epoch_us(close_timestamp_utc), timestamp_open_utc)
                  AS derived_close_timestamp_utc,
                sum(volume_base) AS derived_volume_base,
                sum(quote_volume) AS derived_quote_volume,
                sum(taker_buy_base_volume) AS derived_taker_buy_base_volume,
                sum(taker_buy_quote_volume) AS derived_taker_buy_quote_volume,
                sum(trade_count) AS derived_activity_count
              FROM read_parquet(?)
              GROUP BY bucket_us
            )
            SELECT
              epoch_us(parent.timestamp_open_utc) AS parent_open_us,
              parent.open,
              parent.high,
              parent.low,
              parent.close,
              epoch_us(parent.close_timestamp_utc),
              parent.volume_base,
              parent.quote_volume,
              parent.taker_buy_base_volume,
              parent.taker_buy_quote_volume,
              parent.trade_count,
              coalesce(children.child_count, 0),
              children.first_child_open_us,
              children.last_child_open_us,
              children.derived_open,
              children.derived_high,
              children.derived_low,
              children.derived_close,
              children.derived_close_timestamp_utc,
              children.derived_volume_base,
              children.derived_quote_volume,
              children.derived_taker_buy_base_volume,
              children.derived_taker_buy_quote_volume,
              children.derived_activity_count
            FROM read_parquet(?) AS parent
            LEFT JOIN children
              ON children.bucket_us = epoch_us(parent.timestamp_open_utc)
            ORDER BY parent.timestamp_open_utc
            """,
            [
                parent_us,
                parent_us,
                str(child_path),
                str(parent_path),
            ],
        )
        while batch := cursor.fetchmany(4096):
            for row in batch:
                opened_us = int(row[0])
                child_count = int(row[11])
                first_child_open = (
                    _utc_from_microseconds(int(row[12])) if row[12] is not None else None
                )
                last_child_open = (
                    _utc_from_microseconds(int(row[13])) if row[13] is not None else None
                )
                common = {
                    "record_type": "HIERARCHY_EXCEPTION",
                    "instrument": symbol,
                    "child_timeframe": child_interval,
                    "parent_timeframe": parent_interval,
                    "parent_open_utc": _utc_from_microseconds(opened_us),
                    "expected_child_count": expected_children,
                    "actual_child_count": child_count,
                    "first_child_open_utc": first_child_open,
                    "last_child_open_utc": last_child_open,
                    "parent_early_close": _utc_from_microseconds(opened_us) in parent_early_opens,
                    "any_child_early_close": _has_early_child(
                        child_early_opens,
                        parent_open_us=opened_us,
                        parent_us=parent_us,
                    ),
                }
                if child_count != expected_children:
                    incomplete += 1
                    incomplete_inventory.append(
                        {
                            **common,
                            "status": "INCOMPLETE_CHILDREN",
                            "mismatch_fields": [],
                            "native_values": None,
                            "aggregated_child_values": None,
                        }
                    )
                    continue
                complete += 1
                differing: list[str] = []
                comparisons = (
                    ("open", row[1], row[14]),
                    ("high", row[2], row[15]),
                    ("low", row[3], row[16]),
                    ("close", row[4], row[17]),
                    ("volume_base", row[6], row[19]),
                    ("close_timestamp_utc", row[5], row[18]),
                    ("quote_volume", row[7], row[20]),
                    ("trade_count", row[10], row[23]),
                    ("taker_buy_base_volume", row[8], row[21]),
                    ("taker_buy_quote_volume", row[9], row[22]),
                )
                for field, parent_value, child_value in comparisons:
                    if parent_value != child_value:
                        differing.append(field)
                if differing:
                    divergences += 1
                    native = {
                        field: _format_comparison_value(field, parent_value)
                        for field, parent_value, _child_value in comparisons
                        if field in differing
                    }
                    aggregated = {
                        field: _format_comparison_value(field, child_value)
                        for field, _parent_value, child_value in comparisons
                        if field in differing
                    }
                    divergence_inventory.append(
                        {
                            **common,
                            "status": "SOURCE_DIVERGENCE",
                            "mismatch_fields": differing,
                            "native_values": native,
                            "aggregated_child_values": aggregated,
                        }
                    )
        return {
            "instrument": symbol,
            "child_interval": child_interval,
            "parent_interval": parent_interval,
            "expected_children": expected_children,
            "parent_rows": int(parent_shape[0]),
            "complete_windows": complete,
            "incomplete_windows": incomplete,
            "source_divergence_windows": divergences,
            "classification_counts": {
                "EXACT_CONFORMANT": complete - divergences,
                "SOURCE_DIVERGENCE": divergences,
                "INCOMPLETE_CHILDREN": incomplete,
                "PARENT_MISSING": 0,
            },
            "source_divergence_records": divergence_inventory,
            "incomplete_child_records": incomplete_inventory,
            "child_gap_inventory": _bounded_gap_inventory(connection, child_path, child_interval),
            "status": "PASS",
        }
    finally:
        connection.close()


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("early-close timestamp is not timezone-aware")
    return parsed.astimezone(UTC)


def _early_open_sets(quality: Mapping[str, Any]) -> dict[tuple[str, str], set[str]]:
    tables = quality["quality_run2"]["tables"]
    result: dict[tuple[str, str], set[str]] = {}
    for symbol in SYMBOLS:
        for interval in ("1m", "5m", "15m"):
            anomalies = tables[f"{symbol}_{interval}"]["close_time_semantics"]["anomalies"]
            result[(symbol, interval)] = {
                _parse_utc(item["timestamp_open_utc"])
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z")
                for item in anomalies
            }
    return result


def _analyze_availability(
    *, symbol: str, signal_interval: str, paths: ConformancePaths
) -> dict[str, Any]:
    signal_path = _require_confined_file(
        paths.dataset_root / f"{symbol}_{signal_interval}.parquet",
        root=paths.repo_root,
        label=f"availability signal table {symbol}_{signal_interval}",
    )
    minute_path = _require_confined_file(
        paths.dataset_root / f"{symbol}_1m.parquet",
        root=paths.repo_root,
        label=f"availability one-minute table {symbol}",
    )
    interval_us = interval_microseconds(signal_interval)
    cutoff_us = int(CUTOFF_UTC.timestamp() * 1_000_000)
    unavailable: list[dict[str, Any]] = []
    outside: list[dict[str, Any]] = []
    mapped = 0
    connection = duckdb.connect()
    try:
        cursor = connection.execute(
            """
            WITH minute_opens AS (
              SELECT epoch_us(timestamp_open_utc) AS opened_us
              FROM read_parquet(?)
            )
            SELECT
              epoch_us(signal.timestamp_open_utc) AS signal_open_us,
              minute_opens.opened_us IS NOT NULL AS exact_open_exists
            FROM read_parquet(?) AS signal
            LEFT JOIN minute_opens
              ON minute_opens.opened_us = epoch_us(signal.timestamp_open_utc) + ?
            ORDER BY signal.timestamp_open_utc
            """,
            [str(minute_path), str(signal_path), interval_us],
        )
        while batch := cursor.fetchmany(8192):
            for opened, exists in batch:
                signal_open_us = int(opened)
                boundary_us = signal_open_us + interval_us
                common = {
                    "record_type": "FILL_EXCEPTION",
                    "instrument": symbol,
                    "signal_timeframe": signal_interval,
                    "signal_open_utc": _utc_from_microseconds(signal_open_us),
                    "nominal_boundary_utc": _utc_from_microseconds(boundary_us),
                    "fill_open_utc": None,
                }
                if boundary_us >= cutoff_us:
                    outside.append({**common, "status": "OUTSIDE_FROZEN_WINDOW"})
                elif bool(exists):
                    mapped += 1
                else:
                    unavailable.append({**common, "status": "UNAVAILABLE_GAP"})
        return {
            "instrument": symbol,
            "signal_timeframe": signal_interval,
            "mapped_exact_open": mapped,
            "unavailable_gap_records": unavailable,
            "outside_window_records": outside,
            "status": "PASS",
        }
    finally:
        connection.close()


def _inventory_result(
    name: str,
    records: list[dict[str, Any]],
    *,
    enforce_binding: bool,
) -> dict[str, Any]:
    binding = INVENTORY_BINDINGS[name]
    digest = _sha256_bytes(_canonical_array(records))
    if enforce_binding and (len(records) != binding["count"] or digest != binding["sha256"]):
        raise ValueError(
            f"{name} drift: "
            + json.dumps(
                {
                    "expected_count": binding["count"],
                    "actual_count": len(records),
                    "expected_sha256": binding["sha256"],
                    "actual_sha256": digest,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    return {
        "count": len(records),
        "sha256": digest,
        "details": records[:DETAIL_LIMIT],
        "details_truncated": len(records) > DETAIL_LIMIT,
    }


def _verify_early_close_availability(quality: Mapping[str, Any]) -> dict[str, Any]:
    tables = quality["quality_run2"]["tables"]
    checked = 0
    details: list[dict[str, str]] = []
    for symbol in SYMBOLS:
        for interval in ("1m", "5m", "15m"):
            semantics = tables[f"{symbol}_{interval}"].get("close_time_semantics")
            if (
                not isinstance(semantics, dict)
                or semantics.get("status") != "PASS"
                or semantics.get("inventory", {}).get("status") != "PASS"
                or semantics.get("anomaly_count") != len(semantics.get("anomalies", []))
            ):
                raise ValueError("authenticated early-close inventory drift")
            for anomaly in semantics["anomalies"]:
                opened = _parse_utc(anomaly["timestamp_open_utc"])
                closed = _parse_utc(anomaly["close_timestamp_utc"])
                available = opened.timestamp() + Timeframe(interval).seconds
                availability = datetime.fromtimestamp(available, tz=UTC)
                if not opened <= closed < availability:
                    raise ValueError("early close violates aligned availability boundary")
                checked += 1
                if len(details) < DETAIL_LIMIT:
                    details.append(
                        {
                            "instrument": symbol,
                            "interval": interval,
                            "parent_open_utc": opened.isoformat(timespec="microseconds"),
                            "source_close_utc": closed.isoformat(timespec="microseconds"),
                            "availability_utc": availability.isoformat(timespec="microseconds"),
                        }
                    )
    return {
        "rule": "SOURCE_CLOSE_CANNOT_ADVANCE_ALIGNED_BOUNDARY",
        "audited_rows": checked,
        "details": details,
        "details_truncated": checked > DETAIL_LIMIT,
        "status": "PASS",
    }


def _analyze_once(
    paths: ConformancePaths,
    quality: Mapping[str, Any],
    protocol: Mapping[str, Any],
    *,
    enforce_inventory_bindings: bool,
) -> dict[str, Any]:
    del protocol
    early_opens = _early_open_sets(quality)
    mappings = [
        _analyze_mapping(
            symbol=symbol,
            child_interval=child,
            parent_interval=parent,
            expected_children=expected_children,
            child_early_opens=early_opens[(symbol, child)],
            parent_early_opens=early_opens[(symbol, parent)],
            paths=paths,
        )
        for symbol in SYMBOLS
        for child, parent, expected_children in MAPPINGS
    ]
    availability = [
        _analyze_availability(symbol=symbol, signal_interval=interval, paths=paths)
        for symbol in SYMBOLS
        for interval in ("1m", "5m", "15m")
    ]
    divergence_records = sorted(
        (record for mapping in mappings for record in mapping.pop("source_divergence_records")),
        key=lambda item: (
            item["instrument"],
            item["child_timeframe"],
            item["parent_timeframe"],
            item["parent_open_utc"],
        ),
    )
    incomplete_records = sorted(
        (record for mapping in mappings for record in mapping.pop("incomplete_child_records")),
        key=lambda item: (
            item["instrument"],
            item["child_timeframe"],
            item["parent_timeframe"],
            item["parent_open_utc"],
        ),
    )
    unavailable_records = sorted(
        (record for item in availability for record in item.pop("unavailable_gap_records")),
        key=lambda item: (
            item["instrument"],
            item["signal_timeframe"],
            item["signal_open_utc"],
        ),
    )
    outside_records = sorted(
        (record for item in availability for record in item.pop("outside_window_records")),
        key=lambda item: (
            item["instrument"],
            item["signal_timeframe"],
            item["signal_open_utc"],
        ),
    )
    return {
        "mappings": mappings,
        "availability": availability,
        "pinned_inventories": {
            "source_divergence_records": _inventory_result(
                "source_divergence_records",
                divergence_records,
                enforce_binding=enforce_inventory_bindings,
            ),
            "incomplete_child_records": _inventory_result(
                "incomplete_child_records",
                incomplete_records,
                enforce_binding=enforce_inventory_bindings,
            ),
            "unavailable_gap_fill_records": _inventory_result(
                "unavailable_gap_fill_records",
                unavailable_records,
                enforce_binding=enforce_inventory_bindings,
            ),
            "outside_window_fill_records": _inventory_result(
                "outside_window_fill_records",
                outside_records,
                enforce_binding=enforce_inventory_bindings,
            ),
        },
        "aggregate": {
            "mapping_count": len(mappings),
            "parent_rows": sum(item["parent_rows"] for item in mappings),
            "complete_windows": sum(item["complete_windows"] for item in mappings),
            "incomplete_windows": sum(item["incomplete_windows"] for item in mappings),
            "source_divergence_windows": sum(
                item["source_divergence_windows"] for item in mappings
            ),
            "mapped_exact_open": sum(item["mapped_exact_open"] for item in availability),
            "blocked_absent_open": len(unavailable_records),
            "blocked_cutoff": len(outside_records),
        },
        "early_close_availability": _verify_early_close_availability(quality),
        "verification_status": ("PASS" if enforce_inventory_bindings else "NON_PRODUCTION_FIXTURE"),
        "hierarchy_status": (
            "SOURCE_DIVERGENCES_PRESENT"
            if enforce_inventory_bindings
            else "UNBOUND_FIXTURE_ANALYSIS"
        ),
    }


def _validate_output_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower()
            if normalized in PROHIBITED_OUTPUT_KEYS:
                raise ValueError(f"prohibited output field: {key}")
            _validate_output_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _validate_output_keys(nested)


def _build_result(
    *,
    paths: ConformancePaths,
    protocol_sha: str,
    identity: Mapping[str, Any] | None,
    analysis: dict[str, Any],
    analysis_sha: str,
    strict_production: bool,
) -> dict[str, Any]:
    dataset: dict[str, Any] = {
        "dataset_id": DATASET_ID,
        "manifest_sha256": paths.expected_manifest_sha256,
        "quality_sha256": paths.expected_quality_sha256,
        "validated_table_count": len(TABLE_KEYS),
    }
    if identity is not None:
        dataset["committed_identity"] = identity
    verification_status = "PASS" if strict_production else "NON_PRODUCTION_FIXTURE"
    hierarchy_status = (
        "SOURCE_DIVERGENCES_PRESENT" if strict_production else "UNBOUND_FIXTURE_ANALYSIS"
    )
    status = "PASS" if strict_production else "NON_PRODUCTION"
    result = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": protocol_sha,
        "dataset": dataset,
        "verification": {
            "fresh_read_count": 2,
            "canonical_analysis_sha256": analysis_sha,
            "deterministic_equality": "PASS",
            "analysis": analysis,
            "status": verification_status,
        },
        "limitations": LIMITATIONS,
        "execution_authority": "NONE",
        "verification_status": verification_status,
        "hierarchy_status": hierarchy_status,
        "status": status,
    }
    if set(result) != OUTPUT_SCHEMA_KEYS:
        raise AssertionError("internal output schema drift")
    _validate_output_keys(result)
    return result


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _prepare_output_root(paths: ConformancePaths) -> Path:
    parent = _require_confined_directory(
        paths.output_root.parent, root=paths.repo_root, label="output parent"
    )
    if paths.output_root.exists() or paths.output_root.is_symlink():
        return _require_confined_directory(
            paths.output_root, root=paths.repo_root, label="output root"
        )
    paths.output_root.mkdir(mode=0o755)
    _fsync_directory(parent)
    return _require_confined_directory(paths.output_root, root=paths.repo_root, label="output root")


def _atomic_create(path: Path, content: bytes, *, root: Path) -> None:
    if path.exists() or path.is_symlink():
        retained = _require_confined_file(path, root=root, label="existing output")
        if retained.read_bytes() != content:
            raise ValueError("existing output differs; refusing overwrite")
        return
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            retained = _require_confined_file(path, root=root, label="raced output")
            if retained.read_bytes() != content:
                raise ValueError("raced output differs; refusing overwrite") from None
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _require_current_archive(current: Path, *, output_root: Path, root: Path) -> None:
    retained = _require_confined_file(current, root=root, label="existing CURRENT")
    content = retained.read_bytes()
    digest = _sha256_bytes(content)
    archived = output_root / f"shortframe_execution_conformance_{digest}.json"
    archive = _require_confined_file(archived, root=root, label="archive bound by existing CURRENT")
    if archive.read_bytes() != content:
        raise ValueError("existing CURRENT does not match its immutable archive")


def _atomic_replace_current(
    path: Path,
    content: bytes,
    *,
    output_root: Path,
    root: Path,
) -> None:
    if path.exists() or path.is_symlink():
        _require_current_archive(path, output_root=output_root, root=root)
        if path.read_bytes() == content:
            return
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _publish(paths: ConformancePaths, result: dict[str, Any]) -> dict[str, Any]:
    if (
        result.get("verification_status") != "PASS"
        or result.get("hierarchy_status") != "SOURCE_DIVERGENCES_PRESENT"
        or result.get("status") != "PASS"
    ):
        raise ValueError("only strict production PASS results may be published")
    output_root = _prepare_output_root(paths)
    encoded = _canonical_json(result)
    digest = _sha256_bytes(encoded)
    archived = output_root / f"shortframe_execution_conformance_{digest}.json"
    current = output_root / "CURRENT.json"
    _atomic_create(archived, encoded, root=paths.repo_root)
    _atomic_replace_current(
        current,
        encoded,
        output_root=output_root,
        root=paths.repo_root,
    )
    return {
        "status": "PUBLISHED_OR_VERIFIED_EXISTING",
        "current": str(current),
        "content_addressed": str(archived),
        "sha256": digest,
        "execution_authority": "NONE",
    }


@contextmanager
def _process_lock(paths: ConformancePaths) -> Iterator[None]:
    identity = hashlib.sha256(os.fsencode(paths.output_root.absolute())).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / f"tios-shortframe-conformance-{identity}.lock"
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("short-frame conformance is already running") from error
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _verify(
    paths: ConformancePaths,
    *,
    require_committed_surface: bool,
    enforce_production_inventory: bool = False,
    publish: bool,
) -> dict[str, Any]:
    """Internal fixture-aware verifier; production uses only ``DEFAULT_PATHS``."""
    if publish and not (require_committed_surface and enforce_production_inventory):
        raise ValueError(
            "publication requires committed surfaces and production inventory enforcement"
        )
    strict_production = require_committed_surface and enforce_production_inventory
    root = _require_real_root(paths.repo_root)
    protocol = _load_mapping(paths.protocol, root=root, label="protocol")
    _validate_protocol(protocol, require_production_inventory=enforce_production_inventory)
    protocol_sha = _sha256_file(paths.protocol)
    identity = _committed_identity(paths) if require_committed_surface else None
    manifest, quality = _verify_evidence(paths)
    _verify_actual_tables(paths, manifest)
    first = _analyze_once(
        paths,
        quality,
        protocol,
        enforce_inventory_bindings=enforce_production_inventory,
    )
    repeated_manifest, repeated_quality = _verify_evidence(paths)
    if repeated_manifest != manifest or repeated_quality != quality:
        raise ValueError("dataset evidence changed between fresh reads")
    _verify_actual_table_bytes(paths, repeated_manifest)
    second = _analyze_once(
        paths,
        quality,
        protocol,
        enforce_inventory_bindings=enforce_production_inventory,
    )
    final_manifest, final_quality = _verify_evidence(paths)
    if final_manifest != manifest or final_quality != quality:
        raise ValueError("dataset evidence changed during second fresh read")
    _verify_actual_table_bytes(paths, final_manifest)
    if require_committed_surface and _committed_identity(paths) != identity:
        raise ValueError("committed source or protocol identity changed during verification")
    first_bytes = _canonical_json(first)
    if first_bytes != _canonical_json(second):
        raise ValueError("fresh-read conformance analyses are nondeterministic")
    result = _build_result(
        paths=paths,
        protocol_sha=protocol_sha,
        identity=identity,
        analysis=first,
        analysis_sha=_sha256_bytes(first_bytes),
        strict_production=strict_production,
    )
    return _publish(paths, result) if publish else result


def verify_shortframe_execution_conformance() -> dict[str, Any]:
    """Run and publish the fixed production conformance protocol."""
    with _process_lock(DEFAULT_PATHS):
        return _verify(
            DEFAULT_PATHS,
            require_committed_surface=True,
            enforce_production_inventory=True,
            publish=True,
        )


def parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description=__doc__)


def main() -> int:
    parser().parse_args()
    print(json.dumps(verify_shortframe_execution_conformance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
