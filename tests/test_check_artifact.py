import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tios.services.dashboard_api.status import build_status


def _project(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    root = tmp_path / "project"
    root.mkdir()
    shutil.copy2(Path(__file__).resolve().parents[1] / "Makefile", root / "Makefile")
    fake_bin = root / "bin"
    fake_bin.mkdir()
    uv = fake_bin / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        'if [ -n "$INTERRUPT_COMMAND" ] && echo "$*" | grep -q "$INTERRUPT_COMMAND"; then\n'
        ' kill -TERM "$PPID"\n'
        " exit 9\n"
        "fi\n"
        'if [ -n "$FAIL_COMMAND" ] && echo "$*" | grep -q "$FAIL_COMMAND"; then exit 7; fi\n'
        'if [ "$1" = run ] && [ "$2" = python ] && [ "$3" = -c ]; then\n'
        " shift 3\n"
        ' exec "$TEST_PYTHON" -c "$1"\n'
        "fi\n"
        "exit 0\n"
    )
    uv.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "TEST_PYTHON": sys.executable,
        "FAIL_COMMAND": "",
        "INTERRUPT_COMMAND": "",
    }
    return root, environment


def test_make_check_atomically_replaces_artifact(tmp_path: Path) -> None:
    root, environment = _project(tmp_path)
    artifact = root / "artifacts/quality/check.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("truncated")

    result = subprocess.run(
        ["make", "check"], cwd=root, env=environment, capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(artifact.read_text())
    generated_at = payload.pop("generated_at")
    assert datetime.fromisoformat(generated_at).tzinfo is not None
    assert payload == {
        "schema_version": 2,
        "gate": "check",
        "command": "make check",
        "status": "PASS",
        "includes_dependency_audit": False,
    }
    assert not list(artifact.parent.glob("check.json.tmp.*"))


def test_failed_check_removes_old_pass_and_temporary_artifacts(tmp_path: Path) -> None:
    root, environment = _project(tmp_path)
    artifact = root / "artifacts/quality/check.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"status":"PASS"}')
    environment["FAIL_COMMAND"] = "pytest"

    result = subprocess.run(
        ["make", "check"], cwd=root, env=environment, capture_output=True, text=True, check=False
    )

    assert result.returncode != 0
    assert not artifact.exists()
    assert not list(artifact.parent.glob("check.json.tmp.*"))


def test_interrupted_check_removes_old_pass_and_temporary_artifacts(tmp_path: Path) -> None:
    root, environment = _project(tmp_path)
    artifact = root / "artifacts/quality/check.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"status":"PASS"}')
    environment["INTERRUPT_COMMAND"] = "pytest"

    result = subprocess.run(
        ["make", "check"], cwd=root, env=environment, capture_output=True, text=True, check=False
    )

    assert result.returncode != 0
    assert not artifact.exists()
    assert not list(artifact.parent.glob("check.json.tmp.*"))


@pytest.mark.parametrize(
    ("target_contents", "temporary_contents"),
    [
        (
            None,
            json.dumps(
                {
                    "schema_version": 2,
                    "gate": "check",
                    "command": "make check",
                    "status": "PASS",
                    "includes_dependency_audit": False,
                    "generated_at": datetime.now(tz=UTC).isoformat(),
                }
            ),
        ),
        ('{"schema_version":2,"gate":"check"', None),
        (
            json.dumps(
                {
                    "schema_version": 1,
                    "command": "make check",
                    "status": "PASS",
                    "generated_at": datetime.now(tz=UTC).isoformat(),
                }
            ),
            None,
        ),
    ],
)
def test_malformed_or_interrupted_artifacts_are_never_pass(
    tmp_path: Path, target_contents: str | None, temporary_contents: str | None
) -> None:
    quality = tmp_path / "artifacts/quality"
    quality.mkdir(parents=True)
    if target_contents is not None:
        (quality / "check.json").write_text(target_contents)
    if temporary_contents is not None:
        (quality / "check.json.tmp.interrupted").write_text(temporary_contents)

    checks = build_status(tmp_path)["checks"]

    assert checks["status"] == "UNKNOWN"
    assert checks["known_passing"] is False
    assert checks["required_gate"]["status"] == "UNKNOWN"
