from __future__ import annotations

import base64
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tios.approval.intake_external_contracts import canonical_json

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "ops/intake_trust/verifier/main.swift"
BUILDER = ROOT / "ops/intake_trust/build_bundle.sh"


def test_swift_verifier_has_fixed_fail_closed_surface() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    assert '"/usr/bin/ssh-keygen"' in text
    assert '"/private/var/db/tios-intake"' in text
    assert '"/Library/PrivilegedHelperTools/com.tios.intake-verifier.d"' in text
    assert "Process()" in text and "process.arguments =" in text
    assert "shell" not in text.casefold()
    assert "CommandLine.arguments" in text
    assert 'arguments == ["status", "--json"]' in text
    assert 'arguments == ["verify-decision"]' in text
    for forbidden in ("--root", "--path", "--clock", "--command", "--config", "--executable"):
        assert forbidden not in text
    assert "geteuid() == 0" in text
    assert "lstat(" in text and "st_nlink != 1" in text
    assert 'temporaryRoot + "/signature.XXXXXXXX"' in text
    assert '"-I", reviewer' in text
    assert '"-r", revocationKRLPath' in text
    assert "while value.count <= maximumInputBytes" in text
    assert "read(upToCount: min(65_536, remaining))" in text
    assert "SIGNATURE_VERIFIED_SEMANTICS_UNVERIFIED" in text
    assert "VERIFIED_PENDING_EXTERNAL_ACTIVATION" not in text


def test_swift_and_python_canonical_golden_vector(tmp_path: Path) -> None:
    swift = shutil.which("swift")
    if swift is None:
        pytest.skip("Swift toolchain unavailable")
    program = tmp_path / "golden.swift"
    program.write_text(
        """import Foundation
let value: [String: Any] = ["z":"é", "nested":["b":true,"a":1]]
let options: JSONSerialization.WritingOptions = [.sortedKeys,.withoutEscapingSlashes]
let data = try JSONSerialization.data(withJSONObject:value, options:options)
FileHandle.standardOutput.write(data)
""",
        encoding="utf-8",
    )
    result = subprocess.run([swift, str(program)], check=True, capture_output=True)
    assert result.stdout == canonical_json({"z": "é", "nested": {"b": True, "a": 1}})


def test_swift_compiles_and_uninstalled_copy_fails_closed(tmp_path: Path) -> None:
    swiftc = Path("/usr/bin/swiftc")
    if not swiftc.exists():
        pytest.skip("fixed Swift compiler unavailable")
    binary = tmp_path / "verifier"
    subprocess.run([str(swiftc), "-o", str(binary), str(SOURCE)], check=True)
    result = subprocess.run([str(binary), "status", "--json"], capture_output=True)
    assert result.returncode != 0
    assert b"refused" in result.stderr


def test_signature_failure_modes_are_structurally_fail_closed() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    assert "DECISION_SEMANTICS_UNVERIFIED" in text
    assert "signature verification failed" in text
    assert "wrong namespace" not in text  # namespace is fixed, never caller-provided
    assert "process.terminationStatus == 0" in text
    assert "allowedSignersPath" in text and "revocationKRLPath" in text
    assert "JSON is not canonical" in text


def test_signature_only_behavior_with_private_compile_time_fixture(tmp_path: Path) -> None:
    swiftc = Path("/usr/bin/swiftc")
    ssh_keygen = Path("/usr/bin/ssh-keygen")
    if not swiftc.exists() or not ssh_keygen.exists():
        pytest.skip("fixed native tools unavailable")
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    built = subprocess.run(
        [str(BUILDER), "--output-dir", str(bundles)],
        check=True,
        capture_output=True,
        text=True,
    )
    bundle = Path(json.loads(built.stdout)["bundle_path"])
    metadata = tmp_path / "helper.d"
    state = tmp_path / "state"
    trust = state / "trust"
    temporary = state / "tmp"
    history = state / "history"
    checkpoints = state / "checkpoints"
    for directory in (metadata, state, trust, temporary, history, checkpoints):
        directory.mkdir()
    binary = metadata / "tios-intake-verifier"
    transformed = (bundle / "verifier/main.swift").read_text(encoding="utf-8")
    transformed = transformed.replace(
        '"/Library/PrivilegedHelperTools/com.tios.intake-verifier.d"', f'"{metadata}"'
    ).replace('"/private/var/db/tios-intake"', f'"{state}"')
    transformed = transformed.replace("geteuid() == 0", "true")
    transformed = transformed.replace("info.st_uid != owner", "info.st_uid != getuid()")
    transformed = transformed.replace("info.st_uid != 0", "info.st_uid != getuid()")
    transformed = transformed.replace("info.st_gid != 0", "info.st_gid != getgid()")
    fixture_source = tmp_path / "fixture.swift"
    fixture_source.write_text(transformed, encoding="utf-8")
    subprocess.run([str(swiftc), "-o", str(binary), str(fixture_source)], check=True)
    binary.chmod(0o555)
    shutil.copyfile(bundle / "MANIFEST.sha256", metadata / "MANIFEST.sha256")
    shutil.copyfile(bundle / "VERSION", metadata / "VERSION")
    (metadata / "MANIFEST.sha256").chmod(0o444)
    (metadata / "VERSION").chmod(0o444)
    for directory in (metadata,):
        directory.chmod(0o555)
    for directory in (state, trust, temporary, history, checkpoints):
        directory.chmod(0o700)

    key = tmp_path / "reviewer"
    other = tmp_path / "other"
    subprocess.run([str(ssh_keygen), "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    subprocess.run([str(ssh_keygen), "-q", "-t", "ed25519", "-N", "", "-f", str(other)], check=True)
    public = (tmp_path / "reviewer.pub").read_text(encoding="utf-8").split()
    allowed = trust / "allowed_signers"
    allowed.write_text(f"REVIEWER-ONE {public[0]} {public[1]}\n", encoding="utf-8")
    krl = trust / "revoked.krl"
    subprocess.run([str(ssh_keygen), "-q", "-k", "-f", str(krl), str(other) + ".pub"], check=True)
    allowed.chmod(0o444)
    krl.chmod(0o444)

    helper_status = subprocess.run(
        [str(binary), "status", "--json"], check=True, capture_output=True
    )
    assert json.loads(helper_status.stdout)["status"] == "SETUP_ONLY_PENDING_EXTERNAL_ACTIVATION"

    payload = tmp_path / "malformed-decision"
    payload.write_bytes(b"this is deliberately not JSON")
    subprocess.run(
        [
            str(ssh_keygen),
            "-Y",
            "sign",
            "-f",
            str(key),
            "-n",
            "tios-intake-decision-v1",
            str(payload),
        ],
        check=True,
        capture_output=True,
    )
    envelope = canonical_json(
        {
            "payload_base64": base64.b64encode(payload.read_bytes()).decode(),
            "reviewer_id": "REVIEWER-ONE",
            "signature_base64": base64.b64encode(Path(str(payload) + ".sig").read_bytes()).decode(),
        }
    )
    chunked = subprocess.Popen(
        [str(binary), "verify-decision"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert chunked.stdin is not None and chunked.stdout is not None and chunked.stderr is not None
    for offset in range(0, len(envelope), 7):
        chunked.stdin.write(envelope[offset : offset + 7])
        chunked.stdin.flush()
    chunked.stdin.close()
    output, error = chunked.stdout.read(), chunked.stderr.read()
    assert chunked.wait() == 0, error
    assert json.loads(output)["status"] == "SIGNATURE_VERIFIED_SEMANTICS_UNVERIFIED"
    oversized = subprocess.run(
        [str(binary), "verify-decision"], input=b"x" * 1_048_577, capture_output=True
    )
    assert oversized.returncode != 0
    assert b"too large" in oversized.stderr
