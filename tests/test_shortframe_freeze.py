"""Offline, tiny contract tests for the fixed short-frame certification boundary."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet
import pytest

from tios.dataset import normalize_multi
from tios.dataset import shortframe_freeze as sf
from tios.dataset.normalize import TS, content_sha256


def _write_zip(path: Path, opens_ms: list[int], interval_ms: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = "".join(
        f"{opened},1,2,0.5,1.5,3,{opened + interval_ms - 1},4,5,1,2,0\n" for opened in opens_ms
    ).encode()
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(path.with_suffix(".csv").name, rows)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_content_addressed(root: Path, payload: dict[str, object]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2) + "\n").encode()
    digest = hashlib.sha256(encoded).hexdigest()
    path = root / f"raw_manifest_{digest}.json"
    path.write_bytes(encoded)
    return path


@pytest.fixture
def tiny(tmp_path: Path) -> tuple[sf.FreezePaths, sf.FreezeScope, Path]:
    raw = tmp_path / "raw"
    one_root = raw / "manifests" / "klines"
    bake_raw = tmp_path / "bake_raw"
    bake_norm = tmp_path / "bake_norm"
    authority_git = tmp_path / "authority-repo"
    authority_root = authority_git / "artifacts" / "datasets"
    reports = tmp_path / "reports"
    cutoff = datetime(2021, 2, 1, tzinfo=UTC)
    scope = sf.FreezeScope(
        ("BTCUSDT",),
        ("1m", "5m", "15m"),
        "2021-01",
        "2021-01",
        cutoff,
    )
    interval_ms = {"1m": 60_000, "5m": 300_000, "15m": 900_000}
    start = 1_609_459_200_000
    for interval in scope.timeframes:
        step = interval_ms[interval]
        last = int((cutoff - timedelta(milliseconds=step)).timestamp() * 1000)
        name = f"BTCUSDT-{interval}-2021-01.zip"
        local = raw / "klines" / "BTCUSDT" / interval / name
        _write_zip(local, [start, last], step)
        if interval != "1m":
            canonical = bake_raw / "BTCUSDT" / interval / name
            canonical.parent.mkdir(parents=True, exist_ok=True)
            canonical.write_bytes(local.read_bytes())

    bake_files = []
    for interval in ("5m", "15m"):
        name = f"BTCUSDT-{interval}-2021-01.zip"
        path = bake_raw / "BTCUSDT" / interval / name
        bake_files.append(
            {
                "file": f"BTCUSDT/{interval}/{name}",
                "sha256": _sha(path),
                "size": path.stat().st_size,
                "checksum_verified": True,
            }
        )
    bake_raw_manifest = bake_raw / "raw_manifest.json"
    bake_raw_manifest.write_text(
        json.dumps({"dataset_id": "DS-CRYPTO-SPOT-BAKEOFF-V1", "files": bake_files})
    )

    authority_tables: dict[str, dict[str, object]] = {}
    quality_tables: dict[str, dict[str, object]] = {}
    regeneration: dict[str, str] = {}
    for interval in ("5m", "15m"):
        info = normalize_multi.normalize_pair(
            "BTCUSDT",
            interval,
            output_root=bake_norm,
            raw_root=raw,
            selected_months=["2021-01"],
        )
        assert info is not None
        key = f"BTCUSDT_{interval}"
        authority_tables[key] = {
            "parquet": f"{key}.parquet",
            "rows": info["rows"],
            "parquet_sha256": info["parquet_sha256"],
            "content_sha256": info["content_sha256"],
        }
        regeneration[key] = str(info["content_sha256"])
        quality_tables[key] = {
            "checks": [{"name": "fixture", "status": "PASS"}],
            "dropped_duplicate_open_timestamps": 0,
        }
    authority_root.mkdir(parents=True)
    quality_report = authority_root / "QUALITY_REPORT.json"
    quality_report.write_text(
        json.dumps(
            {
                "dataset_id": "DS-CRYPTO-SPOT-BAKEOFF-V1",
                "overall": "PASS",
                "tables": quality_tables,
            }
        )
    )
    dataset_manifest = authority_root / "DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"
    dataset_manifest.write_text(
        json.dumps(
            {
                "dataset_id": "DS-CRYPTO-SPOT-BAKEOFF-V1",
                "raw_manifest": {"sha256": _sha(bake_raw_manifest)},
                "quality_report_sha256": _sha(quality_report),
                "tables": authority_tables,
                "regeneration_proof": {
                    "runs": 2,
                    "identical_content_hashes": True,
                    "content_sha256_by_table": regeneration,
                },
            }
        )
    )
    subprocess.run(["git", "init", "-q"], cwd=authority_git, check=True)
    subprocess.run(
        ["git", "config", "user.email", "fixture@example.invalid"],
        cwd=authority_git,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=authority_git, check=True)
    subprocess.run(["git", "add", "artifacts/datasets"], cwd=authority_git, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture authority"], cwd=authority_git, check=True
    )

    one_path = raw / "klines" / "BTCUSDT" / "1m" / "BTCUSDT-1m-2021-01.zip"
    one_manifest = _write_content_addressed(
        one_root,
        {
            "schema_version": 3,
            "dataset_id": "DS-CRYPTO-MULTI-V1",
            "kinds": ["klines"],
            "window": {"start": "2021-01", "end": "2021-01"},
            "scope": {
                "symbols": ["BTCUSDT"],
                "timeframes": ["1m"],
                "planned_file_count": 1,
                "require_official_checksums": True,
            },
            "files": [
                {
                    "rel": "klines/BTCUSDT/1m/BTCUSDT-1m-2021-01.zip",
                    "size": one_path.stat().st_size,
                    "sha256": _sha(one_path),
                    "checksum_verified": True,
                    "official_sha256": _sha(one_path),
                    "status": "reused",
                }
            ],
        },
    )
    normalized_root = tmp_path / "published"
    paths = sf.FreezePaths(
        output_root=normalized_root / sf.DATASET_ID,
        normalized_root=normalized_root,
        report_root=reports,
        multi_raw_root=raw,
        one_minute_manifest_root=one_root,
        bakeoff_raw_root=bake_raw,
        bakeoff_raw_manifest=bake_raw_manifest,
        bakeoff_norm_root=bake_norm,
        bakeoff_authority_root=authority_root,
        bakeoff_dataset_manifest=dataset_manifest,
        bakeoff_quality_report=quality_report,
        authority_git_root=authority_git,
        repo_root=sf.ROOT,
    )
    return paths, scope, one_manifest


def test_production_scope_is_exact_six_table_grid() -> None:
    assert sf.FIXED_SCOPE.keys == {
        "BTCUSDT_1m",
        "BTCUSDT_5m",
        "BTCUSDT_15m",
        "ETHUSDT_1m",
        "ETHUSDT_5m",
        "ETHUSDT_15m",
    }
    assert sf.OUTPUT_ROOT.as_posix().endswith("data/normalized/DS-CRYPTO-SPOT-SHORTFRAMES-V1")


def test_raw_proof_binds_official_1m_and_canonical_authority_chain(tiny) -> None:
    paths, scope, manifest = tiny
    proof = sf.verify_raw_proof(manifest, paths=paths, scope=scope)
    assert proof["one_minute_manifest"]["official_checksum_verified_files"] == 1
    assert proof["canonical_bakeoff_raw_manifest"]["matched_files"] == 2
    assert proof["canonical_bakeoff_authority"]["regeneration_runs"] == 2
    assert len(proof["files"]) == 3


def test_parquet_reread_hashes_ignore_row_group_chunking(tiny, tmp_path) -> None:
    paths, scope, manifest = tiny
    canonical_path = paths.bakeoff_norm_root / "BTCUSDT_5m.parquet"
    canonical_table = pyarrow.parquet.read_table(canonical_path).combine_chunks()
    canonical_logical = sf._parquet_logical_content_sha256(canonical_table)
    pyarrow.parquet.write_table(canonical_table, canonical_path, row_group_size=1)
    reread = pyarrow.parquet.read_table(canonical_path)
    assert content_sha256(reread) != canonical_logical
    assert sf._parquet_logical_content_sha256(reread) == canonical_logical

    authority = json.loads(paths.bakeoff_dataset_manifest.read_text())
    authority["tables"]["BTCUSDT_5m"]["parquet_sha256"] = _sha(canonical_path)
    assert authority["tables"]["BTCUSDT_5m"]["content_sha256"] == canonical_logical
    paths.bakeoff_dataset_manifest.write_text(json.dumps(authority))
    subprocess.run(
        ["git", "add", "artifacts/datasets/DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"],
        cwd=paths.authority_git_root,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "re-encode canonical parquet"],
        cwd=paths.authority_git_root,
        check=True,
    )
    sf.verify_raw_proof(manifest, paths=paths, scope=scope)

    stage = tmp_path / "row-group-stage"
    normalized = sf._regenerate(stage, paths=paths, scope=scope)
    staged_path = stage / "BTCUSDT_1m.parquet"
    staged_table = pyarrow.parquet.read_table(staged_path).combine_chunks()
    staged_logical = sf._parquet_logical_content_sha256(staged_table)
    pyarrow.parquet.write_table(staged_table, staged_path, row_group_size=1)
    staged_reread = pyarrow.parquet.read_table(staged_path)
    assert content_sha256(staged_reread) != staged_logical
    normalized["BTCUSDT_1m"]["parquet_sha256"] = _sha(staged_path)
    assert normalized["BTCUSDT_1m"]["content_sha256"] == staged_logical
    assert sf.validate_run(stage, normalized, paths=paths, scope=scope)["overall"] == "PASS"


@pytest.mark.parametrize("broken_link", ["raw", "quality", "regeneration", "table"])
def test_canonical_authority_link_corruption_is_refused(tiny, broken_link: str) -> None:
    paths, scope, manifest = tiny
    authority = json.loads(paths.bakeoff_dataset_manifest.read_text())
    if broken_link == "raw":
        authority["raw_manifest"]["sha256"] = "0" * 64
    elif broken_link == "quality":
        authority["quality_report_sha256"] = "0" * 64
    elif broken_link == "regeneration":
        authority["regeneration_proof"]["identical_content_hashes"] = False
    else:
        authority["tables"]["BTCUSDT_5m"]["content_sha256"] = "0" * 64
    paths.bakeoff_dataset_manifest.write_text(json.dumps(authority))
    with pytest.raises(ValueError, match="canonical"):
        sf.verify_raw_proof(manifest, paths=paths, scope=scope)


def test_coherent_working_tree_authority_replacement_is_not_trusted(tiny) -> None:
    paths, scope, manifest = tiny
    quality = json.loads(paths.bakeoff_quality_report.read_text())
    quality["replacement_note"] = "internally coherent but not committed authority"
    paths.bakeoff_quality_report.write_text(json.dumps(quality))
    authority = json.loads(paths.bakeoff_dataset_manifest.read_text())
    authority["quality_report_sha256"] = _sha(paths.bakeoff_quality_report)
    paths.bakeoff_dataset_manifest.write_text(json.dumps(authority))

    with pytest.raises(ValueError, match="committed HEAD"):
        sf.verify_raw_proof(manifest, paths=paths, scope=scope)


def test_one_minute_manifest_location_name_and_symlinks_are_refused(tiny, tmp_path) -> None:
    paths, scope, manifest = tiny
    arbitrary = tmp_path / manifest.name
    arbitrary.write_bytes(manifest.read_bytes())
    with pytest.raises(ValueError, match="directly under"):
        sf.verify_raw_proof(arbitrary, paths=paths, scope=scope)

    wrong_name = manifest.with_name("raw_manifest_wrong.json")
    wrong_name.write_bytes(manifest.read_bytes())
    with pytest.raises(ValueError, match="not content-addressed"):
        sf.verify_raw_proof(wrong_name, paths=paths, scope=scope)

    retained = tmp_path / "retained.json"
    retained.write_bytes(manifest.read_bytes())
    manifest.unlink()
    manifest.symlink_to(retained)
    with pytest.raises(ValueError, match="regular non-symlink"):
        sf.verify_raw_proof(manifest, paths=paths, scope=scope)

    manifest.unlink()
    manifest.write_bytes(retained.read_bytes())
    alias = tmp_path / "manifest-root-alias"
    alias.symlink_to(paths.one_minute_manifest_root, target_is_directory=True)
    aliased_paths = replace(paths, one_minute_manifest_root=alias)
    with pytest.raises(ValueError, match="exact non-symlink directory"):
        sf.verify_raw_proof(alias / manifest.name, paths=aliased_paths, scope=scope)


def test_symlinked_raw_archive_is_refused(tiny, tmp_path) -> None:
    paths, scope, manifest = tiny
    value = json.loads(manifest.read_text())
    local = paths.multi_raw_root / value["files"][0]["rel"]
    retained = tmp_path / "retained.zip"
    retained.write_bytes(local.read_bytes())
    local.unlink()
    local.symlink_to(retained)
    with pytest.raises(ValueError, match="regular non-symlink"):
        sf.verify_raw_proof(manifest, paths=paths, scope=scope)


def test_symlinked_canonical_authority_ancestor_is_refused(tiny, tmp_path) -> None:
    paths, scope, manifest = tiny
    alias = tmp_path / "authority-alias"
    alias.symlink_to(paths.bakeoff_authority_root, target_is_directory=True)
    aliased = replace(
        paths,
        bakeoff_authority_root=alias,
        bakeoff_dataset_manifest=alias / paths.bakeoff_dataset_manifest.name,
        bakeoff_quality_report=alias / paths.bakeoff_quality_report.name,
    )
    with pytest.raises(ValueError, match="exact non-symlink directory"):
        sf.verify_raw_proof(manifest, paths=aliased, scope=scope)


@pytest.mark.parametrize("target_kind", ["normalized_root", "dataset", "artifact_root"])
def test_symlinked_publication_roots_are_refused(tiny, tmp_path, target_kind: str) -> None:
    paths, scope, manifest = tiny
    if target_kind == "normalized_root":
        real = tmp_path / "real-normalized"
        real.mkdir()
        alias = tmp_path / "normalized-alias"
        alias.symlink_to(real, target_is_directory=True)
        paths = replace(paths, normalized_root=alias, output_root=alias / sf.DATASET_ID)
    elif target_kind == "dataset":
        paths.normalized_root.mkdir()
        real = tmp_path / "real-dataset"
        real.mkdir()
        paths.output_root.symlink_to(real, target_is_directory=True)
    else:
        real = tmp_path / "real-artifacts"
        real.mkdir()
        alias = tmp_path / "artifact-alias"
        alias.symlink_to(real, target_is_directory=True)
        paths = replace(paths, report_root=alias)
    with pytest.raises(ValueError, match="non-symlink"):
        sf._freeze(manifest, paths=paths, scope=scope, require_committed_code=False)


def test_raw_proof_refuses_unverified_manifest_and_corrupt_retained_bytes(tiny) -> None:
    paths, scope, manifest = tiny
    value = json.loads(manifest.read_text())
    value["files"][0]["checksum_verified"] = False
    replacement = _write_content_addressed(paths.one_minute_manifest_root, value)
    with pytest.raises(ValueError, match="official checksum proof"):
        sf.verify_raw_proof(replacement, paths=paths, scope=scope)

    local = paths.multi_raw_root / value["files"][0]["rel"]
    local.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="retained bytes"):
        sf.verify_raw_proof(manifest, paths=paths, scope=scope)


def test_quality_refuses_incomplete_open_duplicate_and_detection_coverage(tiny, tmp_path) -> None:
    paths, scope, _manifest = tiny
    stage = tmp_path / "stage"
    normalized = sf._regenerate(stage, paths=paths, scope=scope)
    missing = stage / "BTCUSDT_1m.parquet"
    missing.unlink()
    with pytest.raises(ValueError, match="grid is incomplete"):
        sf.validate_run(stage, normalized, paths=paths, scope=scope)

    normalized = sf._regenerate(stage, paths=paths, scope=scope)
    path = stage / "BTCUSDT_1m.parquet"
    table = pyarrow.parquet.read_table(path)
    table = table.set_column(
        table.schema.get_field_index("close_timestamp_utc"),
        "close_timestamp_utc",
        pa.array(
            [table["close_timestamp_utc"][0].as_py(), datetime(2021, 3, 1, tzinfo=UTC)],
            type=TS,
        ),
    )
    pyarrow.parquet.write_table(table, path)
    normalized["BTCUSDT_1m"]["parquet_sha256"] = _sha(path)
    normalized["BTCUSDT_1m"]["content_sha256"] = content_sha256(table)
    with pytest.raises(ValueError, match="closed_by_cutoff"):
        sf.validate_run(stage, normalized, paths=paths, scope=scope)

    normalized = sf._regenerate(stage, paths=paths, scope=scope)
    normalized["BTCUSDT_1m"]["dropped_duplicate_open_timestamps"] = 1
    with pytest.raises(ValueError, match="dropped_duplicate_open_timestamps"):
        sf.validate_run(stage, normalized, paths=paths, scope=scope)

    normalized["BTCUSDT_1m"]["dropped_duplicate_open_timestamps"] = 0
    normalized["BTCUSDT_1m"]["file_unit_detections"] = []
    with pytest.raises(ValueError, match="file_unit_detection_coverage"):
        sf.validate_run(stage, normalized, paths=paths, scope=scope)


def test_nondeterminism_is_refused() -> None:
    run1 = {"tables": {"BTCUSDT_1m": {"content_sha256": "a"}}}
    run2 = {"tables": {"BTCUSDT_1m": {"content_sha256": "b"}}}
    with pytest.raises(ValueError, match="nondeterministic"):
        sf._require_deterministic(run1, run2)


def test_tiny_double_regeneration_is_idempotently_verified(tiny) -> None:
    paths, scope, manifest = tiny
    result = sf._freeze(manifest, paths=paths, scope=scope, require_committed_code=False)
    again = sf._freeze(manifest, paths=paths, scope=scope, require_committed_code=False)

    assert result["execution_authority"] == "NONE"
    assert result["status"] == "PUBLISHED_OR_RECOVERED"
    assert again["status"] == "VERIFIED_EXISTING"
    assert {path.stem for path in paths.output_root.glob("*.parquet")} == scope.keys
    quality = json.loads(Path(result["quality_report"]).read_text())
    dataset = json.loads(Path(result["manifest"]).read_text())
    assert quality["overall"] == "PASS"
    assert quality["double_regeneration"]["status"] == "PASS"
    assert quality["quality_run2"]["tables"]["BTCUSDT_1m"]["row_counts_by_month"] == {"2021-01": 2}
    assert dataset["lineage_status"] == "recorded_at_normalization"
    assert dataset["execution_authority"] == "NONE"
    assert "not evidence of strategy validity" in dataset["limitation"]


def test_stranded_output_is_recovered_without_replacing_data(tiny, monkeypatch) -> None:
    paths, scope, manifest = tiny
    original_publish = sf._publish_json

    def fail_publication(*_args, **_kwargs):
        raise RuntimeError("injected artifact failure")

    monkeypatch.setattr(sf, "_publish_json", fail_publication)
    with pytest.raises(RuntimeError, match="injected artifact failure"):
        sf._freeze(manifest, paths=paths, scope=scope, require_committed_code=False)
    target = paths.output_root / "BTCUSDT_1m.parquet"
    original_physical = _sha(target)
    logical = sf._parquet_logical_content_sha256(pyarrow.parquet.read_table(target))
    differently_encoded = target.with_suffix(".alternate.parquet")
    pyarrow.parquet.write_table(
        pyarrow.parquet.read_table(target).combine_chunks(),
        differently_encoded,
        compression=None,
        row_group_size=1,
    )
    differently_encoded.replace(target)
    assert _sha(target) != original_physical
    assert content_sha256(pyarrow.parquet.read_table(target)) != logical
    assert sf._parquet_logical_content_sha256(pyarrow.parquet.read_table(target)) == logical
    before = {path.name: _sha(path) for path in paths.output_root.glob("*.parquet")}
    monkeypatch.setattr(sf, "_publish_json", original_publish)

    recovered = sf._freeze(manifest, paths=paths, scope=scope, require_committed_code=False)
    after = {path.name: _sha(path) for path in paths.output_root.glob("*.parquet")}
    assert recovered["status"] == "PUBLISHED_OR_RECOVERED"
    assert after == before


@pytest.mark.parametrize("result_key", ["quality_report", "manifest"])
def test_symlinked_existing_artifact_file_is_refused(tiny, tmp_path, result_key: str) -> None:
    paths, scope, manifest = tiny
    result = sf._freeze(manifest, paths=paths, scope=scope, require_committed_code=False)
    artifact = Path(result[result_key])
    retained = tmp_path / f"retained-{result_key}.json"
    retained.write_bytes(artifact.read_bytes())
    artifact.unlink()
    artifact.symlink_to(retained)

    with pytest.raises(ValueError, match="regular non-symlink"):
        sf._freeze(manifest, paths=paths, scope=scope, require_committed_code=False)


def test_mismatching_existing_output_is_not_mutated(tiny) -> None:
    paths, scope, manifest = tiny
    sf._freeze(manifest, paths=paths, scope=scope, require_committed_code=False)
    target = paths.output_root / "BTCUSDT_1m.parquet"
    target.write_bytes(b"corrupt")
    before = target.read_bytes()
    with pytest.raises((ValueError, OSError, pa.ArrowInvalid)):
        sf._freeze(manifest, paths=paths, scope=scope, require_committed_code=False)
    assert target.read_bytes() == before


@pytest.mark.parametrize("failure_root", ["normalized", "artifacts"])
def test_recovery_retries_persistent_directory_fsync_failures(
    tiny, monkeypatch, failure_root: str
) -> None:
    paths, scope, manifest = tiny
    original_fsync = sf._fsync_directory
    target = (
        paths.normalized_root.absolute()
        if failure_root == "normalized"
        else paths.report_root.absolute()
    )
    failures = 0

    def fail_target(path: Path) -> bool:
        nonlocal failures
        if path.absolute() == target:
            failures += 1
            return False
        return original_fsync(path)

    monkeypatch.setattr(sf, "_fsync_directory", fail_target)
    with pytest.raises(RuntimeError, match="fsync failed"):
        sf._freeze(manifest, paths=paths, scope=scope, require_committed_code=False)
    assert paths.output_root.is_dir()
    before = {path.name: _sha(path) for path in paths.output_root.glob("*.parquet")}

    with pytest.raises(RuntimeError, match="fsync failed"):
        sf._freeze(manifest, paths=paths, scope=scope, require_committed_code=False)
    assert failures >= 2
    assert {path.name: _sha(path) for path in paths.output_root.glob("*.parquet")} == before

    monkeypatch.setattr(sf, "_fsync_directory", original_fsync)
    recovered = sf._freeze(manifest, paths=paths, scope=scope, require_committed_code=False)
    assert recovered["status"] == "PUBLISHED_OR_RECOVERED"
    assert {path.name: _sha(path) for path in paths.output_root.glob("*.parquet")} == before
