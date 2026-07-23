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


def _digest_valid(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _build(root: Path) -> tuple[dict[str, str], Path]:
    result = subprocess.run(
        [str(OPS / "build_bundle.sh"), "--output-dir", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    metadata = json.loads(result.stdout)
    return metadata, Path(metadata["bundle_path"])


def test_bundle_is_deterministic_exact_directory(tmp_path: Path) -> None:
    first_root, second_root = tmp_path / "one", tmp_path / "two"
    first_root.mkdir()
    second_root.mkdir()
    first_meta, first = _build(first_root)
    second_meta, second = _build(second_root)
    assert first_meta["bundle_sha256"] == second_meta["bundle_sha256"]
    assert (
        first_meta["installer_sha256"]
        == hashlib.sha256((first / "install.sh").read_bytes()).hexdigest()
    )
    assert (
        first_meta["bundle_sha256"]
        == hashlib.sha256((first / "MANIFEST.sha256").read_bytes()).hexdigest()
    )
    assert sorted(str(item.relative_to(first)) for item in first.rglob("*")) == [
        "MANIFEST.sha256",
        "VERSION",
        "install.sh",
        "verifier",
        "verifier/main.swift",
    ]
    for relative in ("MANIFEST.sha256", "VERSION", "install.sh", "verifier/main.swift"):
        assert (first / relative).read_bytes() == (second / relative).read_bytes()


def test_builder_refuses_existing_output_and_real_source_symlink(tmp_path: Path) -> None:
    metadata, _ = _build(tmp_path)
    result = subprocess.run(
        [str(OPS / "build_bundle.sh"), "--output-dir", str(tmp_path)], capture_output=True
    )
    assert result.returncode != 0
    assert Path(metadata["bundle_path"]).is_dir()
    copied = tmp_path / "copied-ops"
    shutil.copytree(OPS, copied)
    (copied / "verifier/main.swift").unlink()
    (copied / "verifier/main.swift").symlink_to(OPS / "verifier/main.swift")
    output = tmp_path / "symlink-output"
    output.mkdir()
    symlink_result = subprocess.run(
        [str(copied / "build_bundle.sh"), "--output-dir", str(output)], capture_output=True
    )
    assert symlink_result.returncode != 0
    assert b"unsafe source" in symlink_result.stderr


def _preflight_model(bundle: Path, expected_bundle: str, expected_installer: str) -> bool:
    expected = {
        "MANIFEST.sha256": 0o444,
        "VERSION": 0o444,
        "install.sh": 0o555,
        "verifier/main.swift": 0o444,
    }
    members = {str(path.relative_to(bundle)) for path in bundle.rglob("*")}
    if members != {*expected, "verifier"}:
        return False
    if stat.S_IMODE(bundle.lstat().st_mode) != 0o555 or bundle.is_symlink():
        return False
    if stat.S_IMODE((bundle / "verifier").lstat().st_mode) != 0o555:
        return False
    for relative, mode in expected.items():
        info = (bundle / relative).lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != mode
        ):
            return False
    manifest = bundle / "MANIFEST.sha256"
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != expected_bundle:
        return False
    if hashlib.sha256((bundle / "install.sh").read_bytes()).hexdigest() != expected_installer:
        return False
    rows = [line.split("  ") for line in manifest.read_text().splitlines()]
    if {row[1] for row in rows if len(row) == 2} != {
        "VERSION",
        "install.sh",
        "verifier/main.swift",
    }:
        return False
    return all(
        len(row) == 2
        and len(row[0]) == 64
        and hashlib.sha256((bundle / row[1]).read_bytes()).hexdigest() == row[0]
        for row in rows
    )


def _copied_types_safe(bundle: Path) -> bool:
    expected = {"MANIFEST.sha256", "VERSION", "install.sh", "verifier", "verifier/main.swift"}
    if {str(path.relative_to(bundle)) for path in bundle.rglob("*")} != expected:
        return False
    if bundle.is_symlink() or not bundle.is_dir():
        return False
    verifier = bundle / "verifier"
    if verifier.is_symlink() or not verifier.is_dir():
        return False
    for relative in expected - {"verifier"}:
        info = (bundle / relative).lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            return False
    return True


def test_documented_preflight_model_refuses_member_installer_and_link_substitution(
    tmp_path: Path,
) -> None:
    metadata, bundle = _build(tmp_path)
    assert _preflight_model(bundle, metadata["bundle_sha256"], metadata["installer_sha256"])
    (bundle / "verifier/main.swift").chmod(0o644)
    assert not _preflight_model(bundle, metadata["bundle_sha256"], metadata["installer_sha256"])
    (bundle / "verifier/main.swift").chmod(0o444)
    (bundle / "install.sh").chmod(0o755)
    (bundle / "install.sh").write_text("#!/bin/sh\nexit 0\n")
    (bundle / "install.sh").chmod(0o555)
    assert not _preflight_model(bundle, metadata["bundle_sha256"], metadata["installer_sha256"])
    (bundle / "verifier").chmod(0o755)
    (bundle / "verifier/main.swift").unlink()
    (bundle / "verifier/main.swift").symlink_to(OPS / "verifier/main.swift")
    (bundle / "verifier").chmod(0o555)
    assert not _preflight_model(bundle, metadata["bundle_sha256"], metadata["installer_sha256"])


def test_copied_symlink_is_refused_before_any_mutation_model(tmp_path: Path) -> None:
    _, bundle = _build(tmp_path)
    sentinel = tmp_path / "sentinel"
    sentinel.write_text("must-not-change", encoding="utf-8")
    sentinel.chmod(0o640)
    before = (sentinel.read_bytes(), sentinel.stat().st_mode, sentinel.stat().st_uid)
    (bundle / "verifier").chmod(0o755)
    (bundle / "verifier/main.swift").unlink()
    (bundle / "verifier/main.swift").symlink_to(sentinel)
    mutation_ran = _copied_types_safe(bundle)
    assert not mutation_ran
    after = (sentinel.read_bytes(), sentinel.stat().st_mode, sentinel.stat().st_uid)
    assert after == before


def test_installer_refuses_non_root_before_any_install() -> None:
    result = subprocess.run(
        [str(OPS / "install.sh"), "install", "--expected-bundle-sha256", "0" * 64],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "install requires root" in result.stderr


def test_installer_fixed_staging_type_digest_race_and_atomic_guards() -> None:
    text = (OPS / "install.sh").read_text(encoding="utf-8")
    assert "STAGING_ROOT=/private/var/db/tios-intake-staging" in text
    assert 'STAGED="$STAGING_ROOT/$EXPECTED.bundle"' in text
    assert "installer must execute from exact staged bundle" in text
    assert '"$STAGED/verifier/main.swift" "$WORK/source/main.swift"' in text
    assert "staged bytes changed during copy" in text
    assert "staged file set mismatch" in text and "bundle manifest mismatch" in text
    assert "-L" in text and "'%u:%g:%Lp:%l'" in text
    assert "TARGET=/Library/PrivilegedHelperTools/com.tios.intake-verifier.d" in text
    assert '/bin/mv "$WORK" "$TARGET"' in text
    assert "installed target already exists" in text
    assert "--source" not in text and "--destination" not in text


def test_installer_ancestor_stat_uses_bsd_numeric_mode_contract() -> None:
    installer = (OPS / "install.sh").read_text(encoding="utf-8")
    ancestor_check = next(
        line for line in installer.splitlines() if line.startswith("check_ancestor()")
    )
    assert "/bin/test -d" in ancestor_check
    assert "/bin/test ! -L" in ancestor_check
    assert "stat -f '%u:%g:%Lp'" in ancestor_check
    assert '= "0:0:755"' in ancestor_check
    assert "%OLp" not in ancestor_check
    assert "drwxr-xr-x" not in ancestor_check


def test_bundle_version_requires_portable_installer_v2() -> None:
    builder = (OPS / "build_bundle.sh").read_text(encoding="utf-8")
    assert "/usr/bin/printf '2\\n' > \"$WORK/bundle/VERSION\"" in builder
    assert "/usr/bin/printf '1\\n' > \"$WORK/bundle/VERSION\"" not in builder


def test_installer_public_status_and_documentation_are_hygienic() -> None:
    result = subprocess.run(
        [str(OPS / "install.sh"), "status", "--json"], check=True, capture_output=True, text=True
    )
    status = json.loads(result.stdout)
    assert status["execution_authority"] == "NONE"
    assert status["status"] == "SETUP_ONLY_NOT_INSTALLED"
    assert os.path.isabs(status["install_path"])
    readme = (OPS / "README.md").read_text(encoding="utf-8")
    assert 'exec "$TIOS_FINAL/install.sh" install' in readme
    assert "/absolute/reviewed/repository/ops/intake_trust/install.sh install" not in readme
    assert "stat -f '%Su:%Sg:%HT:%Lp:%l'" in readme
    assert 'shasum -a 256 "$TIOS_WORK/bundle/install.sh"' in readme
    source = (readme + (OPS / "reviewer_enrollment.example.json").read_text()).casefold()
    for secret_marker in ("private_key", "begin openssh private key", "seed phrase"):
        assert secret_marker not in source


def test_documented_ceremony_rejects_digest_injection_before_path_or_exec() -> None:
    readme = (OPS / "README.md").read_text(encoding="utf-8")
    ceremony = readme.split("/usr/bin/printf 'Reviewed bundle SHA-256: '", 1)[1].split(
        "TIOS_ROOT_CEREMONY\n```", 1
    )[0]
    assert "eval" not in ceremony
    assert "`" not in ceremony
    assert "REPLACE_WITH" not in ceremony
    assert "<<'TIOS_ROOT_CEREMONY'" in ceremony
    assert ceremony.count("*[!0-9a-f]*|''") == 4
    assert ceremony.count('"${#') == 4
    assert ceremony.index('case "$TIOS_BUNDLE_SHA256"') < ceremony.index("TIOS_SOURCE=")
    assert ceremony.index("TIOS_INTAKE_PRECHECK_OK") < ceremony.index(
        'exec "$TIOS_FINAL/install.sh"'
    )
    assert (
        ceremony.split("TIOS_INTAKE_PRECHECK_OK", 1)[1]
        .strip()
        .startswith('exec "$TIOS_FINAL/install.sh"')
    )
    copy_at = ceremony.index('/bin/cp -R "$TIOS_SOURCE" "$TIOS_WORK/bundle"')
    work_check_at = ceremony.index("'root:wheel:Directory:700'")
    member_check_at = ceremony.index('/usr/bin/diff -u "$TIOS_WORK/expected-members"')
    type_check_at = ceremony.index("'%HT:%l'")
    chown_at = ceremony.index("/usr/sbin/chown root:wheel")
    chmod_at = ceremony.index("/bin/chmod 0555")
    assert work_check_at < copy_at < member_check_at < type_check_at < chown_at < chmod_at
    assert "/usr/sbin/chown -R" not in ceremony
    assert "/bin/chmod -R" not in ceremony
    attacks = (
        "$(/usr/bin/id)",
        "`/usr/bin/id`",
        "a" * 63,
        "a" * 65,
        "a" * 32 + " " + "b" * 31,
        "a" * 32 + "\n" + "b" * 31,
        "a" * 63 + ";",
        "A" * 64,
    )
    assert all(not _digest_valid(value) for value in attacks)
    assert _digest_valid("a" * 64)


def test_ceremony_model_never_marks_or_executes_after_precheck_failure() -> None:
    def events(bundle_digest: str, installer_digest: str, preflight_ok: bool) -> list[str]:
        if not _digest_valid(bundle_digest) or not _digest_valid(installer_digest):
            return []
        if not preflight_ok:
            return []
        return ["PRECHECK_OK", "EXEC_STAGED_INSTALLER"]

    assert events("a" * 64, "b" * 64, False) == []
    assert events("$(id)", "b" * 64, True) == []
    assert events("a" * 64, "b" * 64, True) == ["PRECHECK_OK", "EXEC_STAGED_INSTALLER"]
