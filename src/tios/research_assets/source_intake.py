"""Offline intake plans for external strategy/source surfaces."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from tios.research_assets.registry import ResearchSourceRegistry

_PLAN_ID = re.compile(r"INTAKE-[A-Z0-9]+(?:-[A-Z0-9]+)*\Z")
_REPLAY_ID = re.compile(r"RPH-[A-Z0-9]+(?:-[A-Z0-9]+)*\Z")
_REQUIRED_PROHIBITIONS = frozenset(
    {
        "credential_request",
        "account_connection",
        "subscription_or_copy_action",
        "order_routing",
        "paper_demo_or_live_activation",
        "profit_claim_inheritance",
    }
)


class SourceIntakePlanError(ValueError):
    """Raised when an external source-intake plan violates the S2 boundary."""


class CaptureMode(StrEnum):
    PUBLIC_METADATA_SNAPSHOT = "public_metadata_snapshot"
    CONFIG_RECONSTRUCTION = "config_reconstruction"
    HISTORICAL_SIGNAL_REPLAY = "historical_signal_replay"
    ALLOCATION_REPLAY = "allocation_replay"


class IntakeStatus(StrEnum):
    DESIGN_ONLY = "design_only"
    READY_FOR_OFFLINE_CAPTURE = "ready_for_offline_capture"


class ReplayHypothesisStatus(StrEnum):
    SPEC_CANDIDATE = "spec_candidate"
    REPLAY_CANDIDATE = "replay_candidate"
    NON_RECONSTRUCTABLE = "non_reconstructable"


class ReplayHypothesisKind(StrEnum):
    CONFIG_RECONSTRUCTION = "config_reconstruction"
    HISTORICAL_SIGNAL_REPLAY = "historical_signal_replay"
    ALLOCATION_REPLAY = "allocation_replay"


def _nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise SourceIntakePlanError(f"{field} must be a non-empty trimmed string")
    return value


def _strings(value: object, field: str, *, nonempty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SourceIntakePlanError(f"{field} must be a list of strings")
    result = tuple(_nonempty_string(item, field) for item in value)
    if nonempty and not result:
        raise SourceIntakePlanError(f"{field} must not be empty")
    return result


@dataclass(frozen=True)
class SourceIntakePlan:
    """A non-executable capture/replay plan for one untrusted research source."""

    plan_id: str
    source_ref: str
    capture_mode: CaptureMode
    status: IntakeStatus
    target_artifact: str
    allowed_uses: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    required_capture_fields: tuple[str, ...]
    bias_risks: tuple[str, ...]
    validation_prerequisites: tuple[str, ...]
    notes: tuple[str, ...]
    approval_eligible: bool

    def __post_init__(self) -> None:
        if not _PLAN_ID.fullmatch(_nonempty_string(self.plan_id, "plan_id")):
            raise SourceIntakePlanError(f"invalid plan_id: {self.plan_id}")
        _nonempty_string(self.source_ref, "source_ref")
        _nonempty_string(self.target_artifact, "target_artifact")
        if not self.target_artifact.startswith("artifacts/"):
            raise SourceIntakePlanError("target_artifact must be under artifacts/")
        if not isinstance(self.capture_mode, CaptureMode):
            raise SourceIntakePlanError("capture_mode must be a CaptureMode")
        if not isinstance(self.status, IntakeStatus):
            raise SourceIntakePlanError("status must be an IntakeStatus")
        for field in (
            "allowed_uses",
            "prohibited_actions",
            "required_capture_fields",
            "bias_risks",
            "validation_prerequisites",
            "notes",
        ):
            value = getattr(self, field)
            if not isinstance(value, tuple) or not value:
                raise SourceIntakePlanError(f"{field} must be a non-empty tuple")
            for item in value:
                _nonempty_string(item, field)
        missing = _REQUIRED_PROHIBITIONS - set(self.prohibited_actions)
        if missing:
            raise SourceIntakePlanError(
                f"prohibited_actions missing required S2 boundary items: {sorted(missing)}"
            )
        if not isinstance(self.approval_eligible, bool):
            raise SourceIntakePlanError("approval_eligible must be a boolean")
        if self.approval_eligible:
            raise SourceIntakePlanError("source-intake plans cannot be approval eligible")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> SourceIntakePlan:
        expected = set(cls.__dataclass_fields__)
        missing, extra = expected - raw.keys(), raw.keys() - expected
        if missing or extra:
            raise SourceIntakePlanError(
                f"plan fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
            )
        capture_mode = raw["capture_mode"]
        status = raw["status"]
        if not isinstance(capture_mode, str) or not isinstance(status, str):
            raise SourceIntakePlanError("capture_mode and status must be strings")
        approval_eligible = raw["approval_eligible"]
        if not isinstance(approval_eligible, bool):
            raise SourceIntakePlanError("approval_eligible must be a boolean")
        return cls(
            plan_id=_nonempty_string(raw["plan_id"], "plan_id"),
            source_ref=_nonempty_string(raw["source_ref"], "source_ref"),
            capture_mode=CaptureMode(capture_mode),
            status=IntakeStatus(status),
            target_artifact=_nonempty_string(raw["target_artifact"], "target_artifact"),
            allowed_uses=_strings(raw["allowed_uses"], "allowed_uses"),
            prohibited_actions=_strings(raw["prohibited_actions"], "prohibited_actions"),
            required_capture_fields=_strings(
                raw["required_capture_fields"], "required_capture_fields"
            ),
            bias_risks=_strings(raw["bias_risks"], "bias_risks"),
            validation_prerequisites=_strings(
                raw["validation_prerequisites"], "validation_prerequisites"
            ),
            notes=_strings(raw["notes"], "notes"),
            approval_eligible=approval_eligible,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class SourceIntakePlanRegistry:
    """Validated set of offline external-source capture/replay plans."""

    def __init__(
        self,
        plans: Iterable[SourceIntakePlan],
        *,
        source_registry: ResearchSourceRegistry,
    ) -> None:
        ordered = tuple(sorted(plans, key=lambda plan: plan.plan_id))
        ids = [plan.plan_id for plan in ordered]
        if len(ids) != len(set(ids)):
            raise SourceIntakePlanError("duplicate plan_id")
        for plan in ordered:
            try:
                source_registry.get(plan.source_ref)
            except ValueError as exc:
                raise SourceIntakePlanError(f"unknown source_ref: {plan.source_ref}") from exc
        self._plans = ordered
        self._by_id = {plan.plan_id: plan for plan in ordered}

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        source_registry: ResearchSourceRegistry,
    ) -> SourceIntakePlanRegistry:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or set(raw) != {"registry_version", "plans"}:
            raise SourceIntakePlanError("registry must contain registry_version and plans")
        if raw["registry_version"] != 1 or not isinstance(raw["plans"], list):
            raise SourceIntakePlanError("registry_version must be 1 and plans must be a list")
        plans: list[SourceIntakePlan] = []
        for plan in raw["plans"]:
            if not isinstance(plan, dict):
                raise SourceIntakePlanError("each plan must be a mapping")
            plans.append(SourceIntakePlan.from_mapping(plan))
        return cls(plans, source_registry=source_registry)

    def get(self, plan_id: str) -> SourceIntakePlan:
        try:
            return self._by_id[plan_id]
        except KeyError as exc:
            raise SourceIntakePlanError(f"unknown plan: {plan_id}") from exc

    def list(self) -> tuple[SourceIntakePlan, ...]:
        return self._plans

    def for_source(self, source_ref: str) -> tuple[SourceIntakePlan, ...]:
        return tuple(plan for plan in self._plans if plan.source_ref == source_ref)

    def digest(self) -> str:
        payload = json.dumps(
            [plan.to_dict() for plan in self._plans],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ReplayHypothesis:
    """A source-linked offline replay hypothesis, not an approved strategy."""

    hypothesis_id: str
    source_ref: str
    intake_plan_ref: str
    kind: ReplayHypothesisKind
    status: ReplayHypothesisStatus
    title: str
    statement: str
    reconstruction_scope: tuple[str, ...]
    required_inputs: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    assumptions: tuple[str, ...]
    validation_plan: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    execution_authority: str
    profit_claims_inherited: bool
    approval_eligible: bool

    def __post_init__(self) -> None:
        if not _REPLAY_ID.fullmatch(_nonempty_string(self.hypothesis_id, "hypothesis_id")):
            raise SourceIntakePlanError(f"invalid hypothesis_id: {self.hypothesis_id}")
        _nonempty_string(self.source_ref, "source_ref")
        _nonempty_string(self.intake_plan_ref, "intake_plan_ref")
        for field in ("title", "statement", "execution_authority"):
            _nonempty_string(getattr(self, field), field)
        if not isinstance(self.kind, ReplayHypothesisKind):
            raise SourceIntakePlanError("kind must be a ReplayHypothesisKind")
        if not isinstance(self.status, ReplayHypothesisStatus):
            raise SourceIntakePlanError("status must be a ReplayHypothesisStatus")
        for field in (
            "reconstruction_scope",
            "required_inputs",
            "assumptions",
            "validation_plan",
            "artifact_refs",
        ):
            value = getattr(self, field)
            if not isinstance(value, tuple) or not value:
                raise SourceIntakePlanError(f"{field} must be a non-empty tuple")
            for item in value:
                _nonempty_string(item, field)
        if not isinstance(self.missing_inputs, tuple):
            raise SourceIntakePlanError("missing_inputs must be a tuple")
        for item in self.missing_inputs:
            _nonempty_string(item, "missing_inputs")
        if self.status is ReplayHypothesisStatus.NON_RECONSTRUCTABLE and not self.missing_inputs:
            raise SourceIntakePlanError("non_reconstructable hypotheses must list missing inputs")
        if self.execution_authority != "NONE":
            raise SourceIntakePlanError("replay hypotheses must have execution_authority=NONE")
        if not isinstance(self.profit_claims_inherited, bool) or not isinstance(
            self.approval_eligible, bool
        ):
            raise SourceIntakePlanError(
                "profit_claims_inherited and approval_eligible must be bool"
            )
        if self.profit_claims_inherited:
            raise SourceIntakePlanError("replay hypotheses cannot inherit profit claims")
        if self.approval_eligible:
            raise SourceIntakePlanError("replay hypotheses cannot be approval eligible")
        for artifact_ref in self.artifact_refs:
            if not artifact_ref.startswith("artifacts/"):
                raise SourceIntakePlanError("artifact_refs must be under artifacts/")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> ReplayHypothesis:
        expected = set(cls.__dataclass_fields__)
        missing, extra = expected - raw.keys(), raw.keys() - expected
        if missing or extra:
            raise SourceIntakePlanError(
                f"replay fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
            )
        kind = raw["kind"]
        status = raw["status"]
        if not isinstance(kind, str) or not isinstance(status, str):
            raise SourceIntakePlanError("kind and status must be strings")
        profit_claims = raw["profit_claims_inherited"]
        approval = raw["approval_eligible"]
        if not isinstance(profit_claims, bool) or not isinstance(approval, bool):
            raise SourceIntakePlanError(
                "profit_claims_inherited and approval_eligible must be bool"
            )
        return cls(
            hypothesis_id=_nonempty_string(raw["hypothesis_id"], "hypothesis_id"),
            source_ref=_nonempty_string(raw["source_ref"], "source_ref"),
            intake_plan_ref=_nonempty_string(raw["intake_plan_ref"], "intake_plan_ref"),
            kind=ReplayHypothesisKind(kind),
            status=ReplayHypothesisStatus(status),
            title=_nonempty_string(raw["title"], "title"),
            statement=_nonempty_string(raw["statement"], "statement"),
            reconstruction_scope=_strings(raw["reconstruction_scope"], "reconstruction_scope"),
            required_inputs=_strings(raw["required_inputs"], "required_inputs"),
            missing_inputs=_strings(raw["missing_inputs"], "missing_inputs", nonempty=False),
            assumptions=_strings(raw["assumptions"], "assumptions"),
            validation_plan=_strings(raw["validation_plan"], "validation_plan"),
            artifact_refs=_strings(raw["artifact_refs"], "artifact_refs"),
            execution_authority=_nonempty_string(raw["execution_authority"], "execution_authority"),
            profit_claims_inherited=profit_claims,
            approval_eligible=approval,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ReplayHypothesisRegistry:
    """Validated, source-linked replay hypotheses for future offline testing."""

    def __init__(
        self,
        hypotheses: Iterable[ReplayHypothesis],
        *,
        source_registry: ResearchSourceRegistry,
        intake_registry: SourceIntakePlanRegistry,
    ) -> None:
        ordered = tuple(sorted(hypotheses, key=lambda item: item.hypothesis_id))
        ids = [item.hypothesis_id for item in ordered]
        if len(ids) != len(set(ids)):
            raise SourceIntakePlanError("duplicate hypothesis_id")
        for item in ordered:
            source_registry.get(item.source_ref)
            plan = intake_registry.get(item.intake_plan_ref)
            if plan.source_ref != item.source_ref:
                raise SourceIntakePlanError(
                    f"{item.hypothesis_id} source_ref does not match intake plan"
                )
        self._hypotheses = ordered
        self._by_id = {item.hypothesis_id: item for item in ordered}

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        source_registry: ResearchSourceRegistry,
        intake_registry: SourceIntakePlanRegistry,
    ) -> ReplayHypothesisRegistry:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or set(raw) != {"registry_version", "hypotheses"}:
            raise SourceIntakePlanError("registry must contain registry_version and hypotheses")
        if raw["registry_version"] != 1 or not isinstance(raw["hypotheses"], list):
            raise SourceIntakePlanError("registry_version must be 1 and hypotheses must be a list")
        hypotheses: list[ReplayHypothesis] = []
        for item in raw["hypotheses"]:
            if not isinstance(item, dict):
                raise SourceIntakePlanError("each replay hypothesis must be a mapping")
            hypotheses.append(ReplayHypothesis.from_mapping(item))
        return cls(
            hypotheses,
            source_registry=source_registry,
            intake_registry=intake_registry,
        )

    def get(self, hypothesis_id: str) -> ReplayHypothesis:
        try:
            return self._by_id[hypothesis_id]
        except KeyError as exc:
            raise SourceIntakePlanError(f"unknown replay hypothesis: {hypothesis_id}") from exc

    def list(self) -> tuple[ReplayHypothesis, ...]:
        return self._hypotheses

    def digest(self) -> str:
        payload = json.dumps(
            [item.to_dict() for item in self._hypotheses],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(payload).hexdigest()
