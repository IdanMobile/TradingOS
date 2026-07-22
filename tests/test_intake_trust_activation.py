from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
OPS = ROOT / "ops/intake_trust"


def _build(output: Path) -> tuple[dict[str, str], Path]:
    output.chmod(0o700)
    result = subprocess.run(
        [str(OPS / "build_activation_bundle.sh"), "--output-dir", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    metadata = json.loads(result.stdout)
    bundle = output / f"{metadata['bundle_sha256']}.activation-source.bundle"
    return metadata, bundle


def test_activation_script_is_status_plan_only_and_refuses_mutation_commands() -> None:
    status = subprocess.run(
        [str(OPS / "activate.sh"), "status", "--json"], check=True, capture_output=True, text=True
    )
    assert json.loads(status.stdout)["status"] == "SOURCE_ONLY_PENDING_EXTERNAL_ACTIVATION"
    plan = subprocess.run(
        [str(OPS / "activate.sh"), "plan", "--json"], check=True, capture_output=True, text=True
    )
    assert json.loads(plan.stdout)["status"] == "BLOCKED"
    for command in ("activate", "init", "install"):
        refused = subprocess.run([str(OPS / "activate.sh"), command], capture_output=True)
        assert refused.returncode != 0
    text = (OPS / "activate.sh").read_text(encoding="utf-8")
    assert "sudo" not in text and "/bin/mv" not in text and "/bin/cp" not in text
    assert "execution_authority" in text and "NONE" in text


def test_activation_source_bundle_is_deterministic_exact_and_non_authoritative(
    tmp_path: Path,
) -> None:
    first_root, second_root = tmp_path / "one", tmp_path / "two"
    first_root.mkdir()
    second_root.mkdir()
    first_meta, first = _build(first_root)
    second_meta, second = _build(second_root)
    assert first_meta["bundle_sha256"] == second_meta["bundle_sha256"]
    assert first_meta["execution_authority"] == "NONE"
    assert (
        hashlib.sha256((first / "MANIFEST.sha256").read_bytes()).hexdigest()
        == first_meta["bundle_sha256"]
    )
    expected = [
        "MANIFEST.sha256",
        "VERSION",
        "activate.sh",
        "activation_policy.json",
        "authority",
        "authority/main.swift",
    ]
    assert sorted(str(path.relative_to(first)) for path in first.rglob("*")) == expected
    for relative in expected:
        if (first / relative).is_file():
            assert (first / relative).read_bytes() == (second / relative).read_bytes()
    policy = json.loads((first / "activation_policy.json").read_text())
    assert policy["execution_authority"] == "NONE"
    assert policy["require_non_decreasing_time"] is True


def test_builder_refuses_existing_bundle_and_linked_source(tmp_path: Path) -> None:
    _, bundle = _build(tmp_path)
    assert stat.S_IMODE(bundle.stat().st_mode) == 0o555
    again = subprocess.run(
        [str(OPS / "build_activation_bundle.sh"), "--output-dir", str(tmp_path)],
        capture_output=True,
    )
    assert again.returncode != 0
    copied = tmp_path / "ops-copy"
    shutil.copytree(OPS, copied)
    (copied / "authority/main.swift").unlink()
    (copied / "authority/main.swift").symlink_to(OPS / "authority/main.swift")
    output = tmp_path / "linked-output"
    output.mkdir()
    output.chmod(0o700)
    refused = subprocess.run(
        [str(copied / "build_activation_bundle.sh"), "--output-dir", str(output)],
        capture_output=True,
    )
    assert refused.returncode != 0
    assert b"unsafe activation source" in refused.stderr


def test_builder_refuses_nonprivate_output_and_hardlinked_source(tmp_path: Path) -> None:
    public_output = tmp_path / "public"
    public_output.mkdir(mode=0o755)
    refused_output = subprocess.run(
        [str(OPS / "build_activation_bundle.sh"), "--output-dir", str(public_output)],
        capture_output=True,
    )
    assert refused_output.returncode != 0
    assert b"caller-owned mode 0700" in refused_output.stderr

    copied = tmp_path / "hardlinked-ops"
    shutil.copytree(OPS, copied)
    main = copied / "authority/main.swift"
    sibling = copied / "authority/main.hardlink"
    main.rename(sibling)
    os.link(sibling, main)
    private_output = tmp_path / "private"
    private_output.mkdir(mode=0o700)
    refused_link = subprocess.run(
        [str(copied / "build_activation_bundle.sh"), "--output-dir", str(private_output)],
        capture_output=True,
    )
    assert refused_link.returncode != 0
    assert b"unsafe activation source" in refused_link.stderr


def test_builder_json_is_path_independent_and_handles_metacharacter_output(tmp_path: Path) -> None:
    output = tmp_path / 'quoted"\\backslash\nnewline'
    output.mkdir(mode=0o700)
    metadata, bundle = _build(output)
    assert set(metadata) == {"bundle_sha256", "execution_authority", "status"}
    assert bundle.is_dir()
    builder = (OPS / "build_activation_bundle.sh").read_text(encoding="utf-8")
    for required in ("SOURCE_BEFORE", "SOURCE_AFTER", "COPIED", "/bin/mv -n"):
        assert required in builder
    assert "bundle_path" not in builder


def test_activation_docs_define_fail_closed_time_and_root_boundary_without_secrets() -> None:
    docs = (OPS / "ACTIVATION.md").read_text(encoding="utf-8")
    normalized = " ".join(docs.split())
    for required in (
        "any rollback",
        "maximum_forward_jump_seconds",
        "expired",
        "atomic no-replace",
        "malicious root user",
        "operator who can replace",
        "outside this local threat model",
        "contains no such root ceremony",
    ):
        assert required in normalized
    assert "private key never enters" in normalized
    assert "BEGIN OPENSSH PRIVATE KEY" not in docs
    policy = json.loads((OPS / "activation_policy.json").read_text())
    assert os.path.isabs(policy["persisted_time_path"])
