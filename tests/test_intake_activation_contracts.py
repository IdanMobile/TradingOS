from __future__ import annotations

import dataclasses

import pytest

from tios.approval.intake_activation_contracts import (
    ACTIVATION_STREAM_ID,
    AccessEvidence,
    ActivationContractError,
    ActivationStatus,
    ActivationStatusReceipt,
    AuthorityGenesis,
    DataEvidence,
    MonotonicHead,
    OperatorEvidence,
    parse_activation_contract,
    validate_activation_snapshot,
    validate_head_advance,
)
from tios.approval.intake_external_contracts import canonical_json

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
T0 = "2026-07-22T00:00:00Z"
T1 = "2026-07-22T00:01:00Z"
T2 = "2026-07-22T00:02:00Z"


def _genesis() -> AuthorityGenesis:
    return AuthorityGenesis("GENESIS-ONE", SHA_A, SHA_B, SHA_C, SHA_A, SHA_B, SHA_C, T0)


def _head(genesis: AuthorityGenesis) -> MonotonicHead:
    return MonotonicHead(ACTIVATION_STREAM_ID, 0, "0" * 64, genesis.sha256(), T0)


def _receipt(genesis: AuthorityGenesis, head: MonotonicHead) -> ActivationStatusReceipt:
    return ActivationStatusReceipt(
        "RECEIPT-ONE",
        genesis.sha256(),
        head.sha256(),
        SHA_C,
        SHA_C,
        ActivationStatus.ACTIVE_NO_DECISIONS,
        (),
        T1,
        T2,
    )


def test_genesis_is_immutable_exact_wire_and_none_only() -> None:
    genesis = _genesis()
    assert parse_activation_contract(genesis.canonical_bytes(), AuthorityGenesis) == genesis
    with pytest.raises(dataclasses.FrozenInstanceError):
        genesis.genesis_id = "CHANGED"  # type: ignore[misc]
    changed = genesis.to_dict() | {"unknown": "x"}
    with pytest.raises(ActivationContractError, match="fields mismatch"):
        parse_activation_contract(canonical_json(changed), AuthorityGenesis)
    with pytest.raises(ActivationContractError, match="execution_authority"):
        dataclasses.replace(genesis, execution_authority="LIVE")


@pytest.mark.parametrize(
    "raw,match",
    [
        (b'{"a":1,"a":2}', "duplicate"),
        (b'{"a":1.0}', "floating"),
        (b'{"a":"bad\\u0000"}', "control"),
        (b'{ "a":1}', "not canonical"),
        (b'{"z":1,"a":2}', "not canonical"),
        (b"x" * 1_048_577, "too large"),
    ],
)
def test_parser_rejects_ambiguous_unbounded_or_noncanonical_wire(raw: bytes, match: str) -> None:
    with pytest.raises(ActivationContractError, match=match):
        parse_activation_contract(raw, AuthorityGenesis)


def test_evidence_domains_are_distinct_and_substitution_changes_digest() -> None:
    arguments = ("EVIDENCE-ONE", SHA_A, (SHA_B,), SHA_C, T0, T2, "SATISFIED")
    access = AccessEvidence(*arguments)
    data = DataEvidence(*arguments)
    operator = OperatorEvidence(*arguments)
    assert len({access.DOMAIN, data.DOMAIN, operator.DOMAIN}) == 3
    assert len({access.sha256(), data.sha256(), operator.sha256()}) == 3
    assert parse_activation_contract(access.canonical_bytes(), AccessEvidence) == access
    with pytest.raises(ActivationContractError, match="sorted and unique"):
        dataclasses.replace(access, artifact_sha256s=(SHA_B, SHA_B))
    with pytest.raises(ActivationContractError, match="validity"):
        dataclasses.replace(access, valid_until=T0)


def test_monotonic_head_rejects_gaps_predecessor_substitution_and_rollback() -> None:
    first = _head(_genesis())
    second = MonotonicHead(ACTIVATION_STREAM_ID, 1, first.sha256(), SHA_A, T1)
    validate_head_advance(first, second)
    with pytest.raises(ActivationContractError, match="sequence"):
        validate_head_advance(first, dataclasses.replace(second, sequence=2))
    with pytest.raises(ActivationContractError, match="predecessor"):
        validate_head_advance(first, dataclasses.replace(second, previous_head_sha256=SHA_B))
    with pytest.raises(ActivationContractError, match="rollback"):
        validate_head_advance(
            first, dataclasses.replace(second, observed_at="2026-07-21T23:59:59Z")
        )


def test_status_vocabulary_and_blocker_combinations_are_closed() -> None:
    genesis = _genesis()
    head = _head(genesis)
    active = _receipt(genesis, head)
    assert {status.value for status in ActivationStatus} == {"ACTIVE_NO_DECISIONS", "BLOCKED"}
    assert active.execution_authority == "NONE"
    with pytest.raises(ActivationContractError, match="cannot carry blockers"):
        dataclasses.replace(active, blockers=("NOT-READY",))
    blocked = dataclasses.replace(active, status=ActivationStatus.BLOCKED, blockers=("NOT-READY",))
    assert parse_activation_contract(blocked.canonical_bytes(), ActivationStatusReceipt) == blocked
    with pytest.raises(ActivationContractError, match="requires blockers"):
        dataclasses.replace(blocked, blockers=())


def test_active_snapshot_requires_exact_initialized_bindings_and_time() -> None:
    genesis = _genesis()
    head = _head(genesis)
    receipt = _receipt(genesis, head)
    validate_activation_snapshot(
        receipt,
        genesis,
        head,
        policy_sha256=SHA_C,
        trust_snapshot_sha256=SHA_C,
        observed_at=T1,
    )
    with pytest.raises(ActivationContractError, match="genesis"):
        validate_activation_snapshot(
            dataclasses.replace(receipt, authority_genesis_sha256=SHA_A),
            genesis,
            head,
            policy_sha256=SHA_C,
            trust_snapshot_sha256=SHA_C,
            observed_at=T1,
        )
    with pytest.raises(ActivationContractError, match="expired"):
        validate_activation_snapshot(
            receipt,
            genesis,
            head,
            policy_sha256=SHA_C,
            trust_snapshot_sha256=SHA_C,
            observed_at=T2,
        )
    blocked = dataclasses.replace(
        receipt, status=ActivationStatus.BLOCKED, blockers=("EXTERNAL-REVIEW-PENDING",)
    )
    with pytest.raises(ActivationContractError, match="ACTIVE_NO_DECISIONS"):
        validate_activation_snapshot(
            blocked,
            genesis,
            head,
            policy_sha256=SHA_C,
            trust_snapshot_sha256=SHA_C,
            observed_at=T1,
        )


def test_active_snapshot_rejects_arbitrary_stream_and_inverted_time_chain() -> None:
    genesis = _genesis()
    wrong_stream = dataclasses.replace(_head(genesis), stream_id="OTHER-STREAM")
    wrong_stream_receipt = _receipt(genesis, wrong_stream)
    with pytest.raises(ActivationContractError, match="stream identity"):
        validate_activation_snapshot(
            wrong_stream_receipt,
            genesis,
            wrong_stream,
            policy_sha256=SHA_C,
            trust_snapshot_sha256=SHA_C,
            observed_at=T1,
        )

    late_genesis = dataclasses.replace(genesis, initialized_at=T1)
    early_head = _head(late_genesis)
    inverted_receipt = _receipt(late_genesis, early_head)
    with pytest.raises(ActivationContractError, match="time chain"):
        validate_activation_snapshot(
            inverted_receipt,
            late_genesis,
            early_head,
            policy_sha256=SHA_C,
            trust_snapshot_sha256=SHA_C,
            observed_at=T1,
        )


def test_no_contract_exposes_admitted_or_execution_authority() -> None:
    source = _receipt(_genesis(), _head(_genesis())).canonical_bytes().decode().casefold()
    assert "admitted" not in source
    assert '"execution_authority":"none"' in source
