import hashlib
import json
from pathlib import Path

from tios.evidence.provenance import ARTIFACT_SCHEMA
from tios.evidence.staleness import (
    BROKEN,
    CURRENT,
    REPORT_PATH,
    STALE,
    check_artifact,
    scan,
    stale_artifact_refs,
    write_report,
)


def _artifact(root: Path, modules: dict[str, str], artifact_id: str = "ART-1") -> Path:
    payload = {
        "artifact_schema": ARTIFACT_SCHEMA,
        "artifact_id": artifact_id,
        "generated_at": "2026-07-13T10:40:35+00:00",
        "code": {
            "git_commit": "6bac8bfa64ac38af2425e33fbb42fb73d90d79e3",
            "dirty": False,
            "module_sha256_by_path": modules,
        },
    }
    target = root / "artifacts" / f"{artifact_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def _module(root: Path, path: str, content: str) -> str:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode()).hexdigest()


def test_unchanged_modules_are_current(tmp_path: Path) -> None:
    digest = _module(tmp_path, "src/engine.py", "VALUE = 1\n")
    path = _artifact(tmp_path, {"src/engine.py": digest})
    payload = json.loads(path.read_text())

    status = check_artifact(tmp_path, path, payload)

    assert status.state == CURRENT
    assert status.drifted_modules == ()


def test_changed_module_marks_the_artifact_stale(tmp_path: Path) -> None:
    """A result computed with code that has since changed is no longer current evidence."""
    digest = _module(tmp_path, "src/engine.py", "VALUE = 1\n")
    path = _artifact(tmp_path, {"src/engine.py": digest})
    # The engine is rewritten after the artifact was produced.
    _module(tmp_path, "src/engine.py", "VALUE = 2\n")

    status = check_artifact(tmp_path, path, json.loads(path.read_text()))

    assert status.state == STALE
    assert len(status.drifted_modules) == 1
    assert status.drifted_modules[0].path == "src/engine.py"
    assert not status.drifted_modules[0].missing


def test_deleted_module_marks_the_artifact_broken(tmp_path: Path) -> None:
    digest = _module(tmp_path, "src/engine.py", "VALUE = 1\n")
    path = _artifact(tmp_path, {"src/engine.py": digest})
    (tmp_path / "src" / "engine.py").unlink()

    status = check_artifact(tmp_path, path, json.loads(path.read_text()))

    assert status.state == BROKEN
    assert status.drifted_modules[0].missing


def test_artifact_without_a_path_map_cannot_be_verified(tmp_path: Path) -> None:
    """An unverifiable artifact is a provenance gap, not a pass."""
    path = _artifact(tmp_path, {})
    status = check_artifact(tmp_path, path, json.loads(path.read_text()))
    assert status.state == BROKEN


def test_one_byte_of_drift_is_detected(tmp_path: Path) -> None:
    """Deliberate byte drift must fail, per SUP-007's acceptance criteria."""
    digest = _module(tmp_path, "src/engine.py", "VALUE = 1\n")
    path = _artifact(tmp_path, {"src/engine.py": digest})
    _module(tmp_path, "src/engine.py", "VALUE = 1\n ")  # one trailing space

    assert check_artifact(tmp_path, path, json.loads(path.read_text())).state == STALE


def test_scan_and_report_summarise_the_estate(tmp_path: Path) -> None:
    good = _module(tmp_path, "src/good.py", "OK = 1\n")
    _artifact(tmp_path, {"src/good.py": good}, artifact_id="ART-GOOD")

    bad = _module(tmp_path, "src/bad.py", "OK = 1\n")
    _artifact(tmp_path, {"src/bad.py": bad}, artifact_id="ART-BAD")
    _module(tmp_path, "src/bad.py", "OK = 2\n")

    statuses = scan(tmp_path)
    assert len(statuses) == 2

    report = write_report(tmp_path, statuses)
    assert report == tmp_path / REPORT_PATH
    payload = json.loads(report.read_text())
    assert payload["counts"][CURRENT] == 1
    assert payload["counts"][STALE] == 1
    assert "ART-BAD" in stale_artifact_refs(tmp_path)
    assert "ART-GOOD" not in stale_artifact_refs(tmp_path)


def test_non_research_json_is_ignored(tmp_path: Path) -> None:
    other = tmp_path / "artifacts" / "unrelated.json"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    assert scan(tmp_path) == ()


def test_malformed_json_does_not_abort_the_scan(tmp_path: Path) -> None:
    broken = tmp_path / "artifacts" / "broken.json"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("{not json", encoding="utf-8")
    digest = _module(tmp_path, "src/engine.py", "VALUE = 1\n")
    _artifact(tmp_path, {"src/engine.py": digest})

    statuses = scan(tmp_path)
    assert len(statuses) == 1
    assert statuses[0].state == CURRENT


def test_shipped_campaign_artifacts_are_verifiable() -> None:
    """The six real G10 campaign artifacts must remain checkable against live code."""
    root = Path()
    if not (root / "artifacts" / "validation" / "campaigns").is_dir():
        return
    statuses = scan(root)
    assert statuses, "expected the shipped research artifacts to be discoverable"
    # Every shipped artifact carries a per-path module map, so none is unverifiable.
    assert all(status.state in {CURRENT, STALE} for status in statuses)
