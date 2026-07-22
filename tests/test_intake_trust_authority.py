from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tios.approval.intake_activation_contracts import (
    ActivationContractError,
    ActivationStatus,
    ActivationStatusReceipt,
    AuthorityGenesis,
    parse_activation_contract,
)
from tios.approval.intake_external_contracts import canonical_json

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "ops/intake_trust/authority/main.swift"
SHA_A = "a" * 64
SHA_B = "b" * 64


@pytest.fixture(scope="module")
def authority_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    swiftc = Path("/usr/bin/swiftc")
    if not swiftc.exists():
        pytest.skip("fixed Swift compiler unavailable")
    binary = tmp_path_factory.mktemp("authority") / "authority"
    subprocess.run([str(swiftc), "-o", str(binary), str(SOURCE)], check=True)
    return binary


def _genesis() -> AuthorityGenesis:
    return AuthorityGenesis(
        "GENESIS-ONE", SHA_A, SHA_B, SHA_A, SHA_B, SHA_A, SHA_B, "2026-07-22T00:00:00Z"
    )


def test_authority_source_has_bounded_validation_only_surface() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    assert "while data.count <= maximumInputBytes" in text
    assert "read(upToCount: min(65_536, remaining))" in text
    assert 'arguments == ["status", "--json"]' in text
    assert 'arguments == ["validate-authority-genesis"]' in text
    assert 'arguments == ["validate-activation-receipt"]' in text
    for forbidden in ("Process()", "/bin/sh", "sudo", '["activate"]', '["install"]'):
        assert forbidden not in text.casefold()
    assert "execution_authority" in text and "NONE" in text


def test_compiled_authority_validates_canonical_genesis_syntax_only(
    authority_binary: Path,
) -> None:
    status = subprocess.run(
        [str(authority_binary), "status", "--json"], check=True, capture_output=True
    )
    assert json.loads(status.stdout)["status"] == "SOURCE_ONLY_PENDING_EXTERNAL_ACTIVATION"
    valid = subprocess.run(
        [str(authority_binary), "validate-authority-genesis"],
        input=_genesis().canonical_bytes(),
        check=True,
        capture_output=True,
    )
    result = json.loads(valid.stdout)
    assert result["status"] == "CONTRACT_SYNTAX_VALID_PENDING_EXTERNAL_ACTIVATION"
    assert "SEMANTIC_BINDINGS_NOT_EXTERNALLY_VERIFIED" in result["blockers"]
    noncanonical = subprocess.run(
        [str(authority_binary), "validate-authority-genesis"],
        input=b" " + _genesis().canonical_bytes(),
        capture_output=True,
    )
    assert noncanonical.returncode != 0
    oversized = subprocess.run(
        [str(authority_binary), "validate-authority-genesis"],
        input=b"x" * 1_048_577,
        capture_output=True,
    )
    assert oversized.returncode != 0 and b"too large" in oversized.stderr


def test_compiled_authority_rejects_status_blocker_substitution(authority_binary: Path) -> None:
    genesis = _genesis()
    receipt = ActivationStatusReceipt(
        "RECEIPT-ONE",
        genesis.sha256(),
        SHA_A,
        SHA_A,
        SHA_B,
        ActivationStatus.ACTIVE_NO_DECISIONS,
        (),
        "2026-07-22T00:01:00Z",
        "2026-07-22T01:01:00Z",
    )
    accepted = subprocess.run(
        [str(authority_binary), "validate-activation-receipt"],
        input=receipt.canonical_bytes(),
        capture_output=True,
    )
    assert accepted.returncode == 0
    substituted = receipt.canonical_bytes().replace(b'"blockers":[]', b'"blockers":["X"]')
    refused = subprocess.run(
        [str(authority_binary), "validate-activation-receipt"],
        input=substituted,
        capture_output=True,
    )
    assert refused.returncode != 0

    invalid_time = receipt.canonical_bytes().replace(
        b'"issued_at":"2026-07-22T00:01:00Z"', b'"issued_at":"NOT-A-TIME"'
    )
    refused_time = subprocess.run(
        [str(authority_binary), "validate-activation-receipt"],
        input=invalid_time,
        capture_output=True,
    )
    assert refused_time.returncode != 0

    invalid_token = receipt.canonical_bytes().replace(b"RECEIPT-ONE", b"receipt one")
    refused_token = subprocess.run(
        [str(authority_binary), "validate-activation-receipt"],
        input=invalid_token,
        capture_output=True,
    )
    assert refused_token.returncode != 0


def test_swift_and_python_canonical_policy_vector(tmp_path: Path) -> None:
    swift = shutil.which("swift")
    if swift is None:
        pytest.skip("Swift toolchain unavailable")
    policy = (ROOT / "ops/intake_trust/activation_policy.json").read_bytes()
    assert policy.endswith(b"\n")
    canonical = json.dumps(json.loads(policy), sort_keys=True, separators=(",", ":")).encode()
    assert canonical + b"\n" == policy


@pytest.mark.parametrize(
    "token,accepted",
    [
        ("A", True),
        ("A1-B_C.D9", True),
        ("A" * 128, True),
        ("-", False),
        (".", False),
        ("A-", False),
        ("A..B", False),
        ("A" * 129, False),
    ],
)
def test_swift_python_token_grammar_is_identical(
    authority_binary: Path, token: str, accepted: bool
) -> None:
    receipt = ActivationStatusReceipt(
        "RECEIPT-ONE",
        SHA_A,
        SHA_B,
        SHA_A,
        SHA_B,
        ActivationStatus.ACTIVE_NO_DECISIONS,
        (),
        "2026-07-22T00:01:00Z",
        "2026-07-22T01:01:00Z",
    )
    wire = canonical_json(receipt.to_dict() | {"receipt_id": token})
    try:
        parse_activation_contract(wire, ActivationStatusReceipt)
        python_accepted = True
    except ActivationContractError:
        python_accepted = False
    swift = subprocess.run(
        [str(authority_binary), "validate-activation-receipt"], input=wire, capture_output=True
    )
    assert python_accepted is accepted
    assert (swift.returncode == 0) is accepted
