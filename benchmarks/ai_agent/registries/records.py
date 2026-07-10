"""MDL/AGT/PRM registry records (T-011-01, REQ-042).

Model/agent/prompt records with snapshot pinning and per-provider deprecation
watch fields (REG §7 / docs/architecture/AD.md L176): providers do not
guarantee determinism and pin/deprecate model snapshots on different notice
windows (Anthropic >=60d, OpenAI as little as 2 weeks for previews). Parsing
is strict, mirroring `tios.strategy.spec`: any structural problem raises
RegistryError with a precise path. Hashing is canonical-JSON sha256.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

PROVIDERS = ("anthropic", "openai", "google", "other")


class RegistryError(ValueError):
    """Structural/semantic registry problem with a precise location path."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        super().__init__(f"{path}: {message}")


def _require(data: dict[str, Any], key: str, typ: type, path: str) -> Any:
    if key not in data:
        raise RegistryError(f"{path}.{key}", "missing required field")
    val = data[key]
    if not isinstance(val, typ):
        raise RegistryError(f"{path}.{key}", f"expected {typ.__name__}, got {type(val).__name__}")
    return val


def _str_list(data: dict[str, Any], key: str, path: str) -> tuple[str, ...]:
    val = data.get(key, [])
    if not isinstance(val, list) or any(not isinstance(x, str) for x in val):
        raise RegistryError(f"{path}.{key}", "must be a list of strings")
    return tuple(val)


def _canonical_hash(obj: dict[str, Any]) -> str:
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class ModelRecord:
    """A pinned (or explicitly unresolved) model snapshot plus provider policy."""

    model_key: str  # 'MDL-<slug>'
    provider: str
    display_name: str
    snapshot_id: str  # exact resolved snapshot id, or 'UNRESOLVED' pre-run
    snapshot_resolved_at: str | None  # ISO date snapshot_id was confirmed
    deprecation_notice_days: int  # provider policy minimum notice window
    deprecation_notice_source: str  # citation, e.g. 'REG §7 / AD.md L176'
    supports_snapshot_pinning: bool
    notes: tuple[str, ...] = ()

    def to_obj(self) -> dict[str, Any]:
        return {
            "model_key": self.model_key,
            "provider": self.provider,
            "display_name": self.display_name,
            "snapshot_id": self.snapshot_id,
            "snapshot_resolved_at": self.snapshot_resolved_at,
            "deprecation_notice_days": self.deprecation_notice_days,
            "deprecation_notice_source": self.deprecation_notice_source,
            "supports_snapshot_pinning": self.supports_snapshot_pinning,
            "notes": list(self.notes),
        }

    def record_hash(self) -> str:
        return _canonical_hash(self.to_obj())


@dataclass(frozen=True)
class AgentRecord:
    """An agent configuration: workflow + tools + reasoning/budget settings."""

    agent_key: str  # 'AGT-<slug>'
    version: str
    workflow_ref: str
    tools: tuple[str, ...]
    reasoning_settings: dict[str, Any]
    budget: dict[str, Any]
    notes: tuple[str, ...] = ()

    def to_obj(self) -> dict[str, Any]:
        return {
            "agent_key": self.agent_key,
            "version": self.version,
            "workflow_ref": self.workflow_ref,
            "tools": list(self.tools),
            "reasoning_settings": self.reasoning_settings,
            "budget": self.budget,
            "notes": list(self.notes),
        }

    def record_hash(self) -> str:
        return _canonical_hash(self.to_obj())


@dataclass(frozen=True)
class PromptRecord:
    """A versioned prompt template pinned to a task class."""

    prompt_key: str  # 'PRM-<slug>'
    version: str
    task_class: str  # 'T1'..'T8'
    template: str
    notes: tuple[str, ...] = ()

    def to_obj(self) -> dict[str, Any]:
        return {
            "prompt_key": self.prompt_key,
            "version": self.version,
            "task_class": self.task_class,
            "template": self.template,
            "notes": list(self.notes),
        }

    def template_hash(self) -> str:
        return hashlib.sha256(self.template.encode()).hexdigest()

    def record_hash(self) -> str:
        return _canonical_hash(self.to_obj())


def parse_model(data: object, path: str = "$") -> ModelRecord:
    if not isinstance(data, dict):
        raise RegistryError(path, "model record must be a mapping")
    model_key = _require(data, "model_key", str, path)
    if not re.fullmatch(r"MDL-[A-Za-z0-9_-]+", model_key):
        raise RegistryError(f"{path}.model_key", f"must match 'MDL-<slug>', got {model_key!r}")
    provider = _require(data, "provider", str, path)
    if provider not in PROVIDERS:
        raise RegistryError(
            f"{path}.provider", f"unknown provider {provider!r} (allowed: {PROVIDERS})"
        )
    return ModelRecord(
        model_key=model_key,
        provider=provider,
        display_name=_require(data, "display_name", str, path),
        snapshot_id=_require(data, "snapshot_id", str, path),
        snapshot_resolved_at=data.get("snapshot_resolved_at"),
        deprecation_notice_days=_require(data, "deprecation_notice_days", int, path),
        deprecation_notice_source=_require(data, "deprecation_notice_source", str, path),
        supports_snapshot_pinning=bool(_require(data, "supports_snapshot_pinning", bool, path)),
        notes=_str_list(data, "notes", path),
    )


def parse_agent(data: object, path: str = "$") -> AgentRecord:
    if not isinstance(data, dict):
        raise RegistryError(path, "agent record must be a mapping")
    agent_key = _require(data, "agent_key", str, path)
    if not re.fullmatch(r"AGT-[A-Za-z0-9_-]+", agent_key):
        raise RegistryError(f"{path}.agent_key", f"must match 'AGT-<slug>', got {agent_key!r}")
    return AgentRecord(
        agent_key=agent_key,
        version=_require(data, "version", str, path),
        workflow_ref=_require(data, "workflow_ref", str, path),
        tools=_str_list(data, "tools", path),
        reasoning_settings=_require(data, "reasoning_settings", dict, path),
        budget=_require(data, "budget", dict, path),
        notes=_str_list(data, "notes", path),
    )


def parse_prompt(data: object, path: str = "$") -> PromptRecord:
    if not isinstance(data, dict):
        raise RegistryError(path, "prompt record must be a mapping")
    prompt_key = _require(data, "prompt_key", str, path)
    if not re.fullmatch(r"PRM-[A-Za-z0-9_-]+", prompt_key):
        raise RegistryError(f"{path}.prompt_key", f"must match 'PRM-<slug>', got {prompt_key!r}")
    task_class = _require(data, "task_class", str, path)
    if not re.fullmatch(r"T[1-8]", task_class):
        raise RegistryError(f"{path}.task_class", f"must be one of T1..T8, got {task_class!r}")
    return PromptRecord(
        prompt_key=prompt_key,
        version=_require(data, "version", str, path),
        task_class=task_class,
        template=_require(data, "template", str, path),
        notes=_str_list(data, "notes", path),
    )


def load_registry(items: list[object], parse_fn: Any) -> list[Any]:
    """Parse a list of raw registry records, raising on the first bad one."""
    out = []
    for i, raw in enumerate(items):
        out.append(parse_fn(raw, f"$[{i}]"))
    return out
