from __future__ import annotations

import dataclasses
import json

import pytest

from tios.approval.intake_external_contracts import (
    ExternalAssessmentReceipt,
    ExternalContractError,
    ReceiptStatus,
    ReviewerCredential,
    canonical_json,
    parse_canonical_json,
    parse_contract,
)

SHA_A = "a" * 64
SHA_B = "b" * 64


def _credential() -> ReviewerCredential:
    return ReviewerCredential(
        "CREDENTIAL-ONE",
        "REVIEWER-ONE",
        "INDEPENDENT_INTAKE_ADMISSION_REVIEWER",
        SHA_A,
        "SHA256:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn12",
        "2026-07-22T00:00:00Z",
        "2027-07-22T00:00:00Z",
        None,
    )


def test_credential_is_immutable_strict_and_domain_separated() -> None:
    credential = _credential()
    assert dataclasses.is_dataclass(credential)
    with pytest.raises(dataclasses.FrozenInstanceError):
        credential.reviewer_id = "REVIEWER-TWO"  # type: ignore[misc]
    assert credential.domain_separated_bytes().startswith(b"TIOS/INTAKE-REVIEWER-CREDENTIAL/v1\0{")
    assert parse_contract(credential.canonical_bytes(), ReviewerCredential) == credential
    changed = credential.to_dict() | {"unknown": "value"}
    with pytest.raises(ExternalContractError, match="fields mismatch"):
        parse_contract(canonical_json(changed), ReviewerCredential)


@pytest.mark.parametrize(
    "raw,match",
    [
        (b'{"a":1,"a":2}', "duplicate"),
        (b'{"a":1.0}', "floating"),
        (b'{"a":NaN}', "non-finite"),
        ('{"a":"bad\\u0000value"}', "control"),
        (b"[]", "top-level"),
        (b'{ "a":1}', "not canonical"),
        (b'{"z":1,"a":2}', "not canonical"),
        (b'{"a":"\\u00e9"}', "not canonical"),
        (b'{"a":"a\\/b"}', "not canonical"),
    ],
)
def test_json_parser_rejects_ambiguous_or_unsafe_values(raw: bytes | str, match: str) -> None:
    with pytest.raises(ExternalContractError, match=match):
        parse_canonical_json(raw)


def test_utf8_canonical_bytes_are_exact_and_substitution_changes_digest() -> None:
    assert canonical_json({"z": "é", "a": 1}) == b'{"a":1,"z":"\xc3\xa9"}'
    first = _credential()
    second = dataclasses.replace(first, reviewer_id="REVIEWER-TWO")
    assert first.sha256() != second.sha256()


def test_receipt_can_only_report_pending_or_failure_and_never_authority() -> None:
    receipt = ExternalAssessmentReceipt(
        "RECEIPT-ONE",
        SHA_A,
        SHA_A,
        SHA_B,
        SHA_B,
        (),
        ReceiptStatus.VERIFIED_PENDING_EXTERNAL_ACTIVATION,
        ("EXTERNAL-ACTIVATION-INCOMPLETE",),
        "2026-07-22T00:00:00Z",
    )
    encoded = receipt.canonical_bytes()
    assert json.loads(encoded)["execution_authority"] == "NONE"
    assert {item.value for item in ReceiptStatus} == {
        "VERIFIED_PENDING_EXTERNAL_ACTIVATION",
        "BLOCKED",
        "VERIFICATION_FAILED",
    }
    assert "campaign" not in encoded.decode().casefold()
