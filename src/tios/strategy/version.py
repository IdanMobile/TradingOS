"""StrategyVersion (T-005-02, REQ-012): immutable snapshot of spec + resolved params.

Invariant (type catalog §2): any change ⇒ new SV; an SV referenced by any
experiment is permanently immutable. Enforced by frozen dataclasses and a
content-derived sv_id — the identity IS the content, so mutation is meaningless.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from tios.strategy.spec import CanonicalStrategySpec


@dataclass(frozen=True, slots=True)
class StrategyVersion:
    sv_id: str
    strategy_id: str
    spec_hash: str
    resolved_parameters: Mapping[str, Any]
    created_utc: str

    def __post_init__(self) -> None:
        # deep-freeze parameters: mapping proxy rejects writes at runtime
        object.__setattr__(
            self, "resolved_parameters", MappingProxyType(dict(self.resolved_parameters))
        )


def create_version(
    spec: CanonicalStrategySpec, resolved_parameters: dict[str, Any]
) -> StrategyVersion:
    spec_hash = spec.spec_hash()
    content = json.dumps(
        {"spec_hash": spec_hash, "params": resolved_parameters},
        sort_keys=True,
        separators=(",", ":"),
    )
    sv_id = "SV-" + hashlib.sha256(content.encode()).hexdigest()[:16]
    return StrategyVersion(
        sv_id=sv_id,
        strategy_id=spec.strategy_id,
        spec_hash=spec_hash,
        resolved_parameters=resolved_parameters,
        created_utc=datetime.now(tz=UTC).isoformat(),
    )
