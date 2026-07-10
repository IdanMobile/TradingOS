"""Provider layer (T-011-03, REQ-044): null provider + credential-gated real provider.

The null provider never imports a networking library and returns a fixed,
clearly-labeled stub output — it exists to prove the pipeline plumbing
(fixtures -> prompt assembly -> schema validation -> scoring) end-to-end with
zero fabricated model output and zero cost.

`RealProviderGate` is the credential check for T-011-05: it never fabricates
a run. If the named provider's API-key env var is absent, it raises
`CredentialNotConfiguredError` instead of proceeding.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

PROVIDER_ENV_VARS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


class CredentialNotConfiguredError(RuntimeError):
    """Raised when a real-provider run is attempted with no credential present."""


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    model_identifier: str
    raw_output: dict[str, Any]
    cost_usd: float
    latency_ms: float


@dataclass(frozen=True)
class AIExecutionSelection:
    mode: str
    provider: str
    configured: bool
    network_enabled: bool
    credential_env_var: str | None


def resolve_ai_execution(
    environment: Mapping[str, str] | None = None,
) -> AIExecutionSelection:
    """Resolve mock/real mode without loading or exposing any credential value."""
    environment = environment or os.environ
    mode = environment.get("TIOS_AI_MODE", "mock").lower()
    if mode == "mock":
        return AIExecutionSelection("mock", "null", True, False, None)
    if mode != "real":
        raise ValueError("TIOS_AI_MODE must be 'mock' or 'real'")
    provider = environment.get("TIOS_AI_PROVIDER", "").lower()
    if provider not in PROVIDER_ENV_VARS:
        raise ValueError(f"TIOS_AI_PROVIDER must be one of {sorted(PROVIDER_ENV_VARS)}")
    variable = PROVIDER_ENV_VARS[provider]
    return AIExecutionSelection("real", provider, bool(environment.get(variable)), True, variable)


class NullProvider:
    """Deterministic, zero-cost, zero-network stub provider for harness self-test."""

    provider = "null"
    model_identifier = "null-v1"

    # Minimal structurally-valid stub per task class, matching pipeline.TASK_SCHEMAS.
    _STUBS: dict[str, dict[str, Any]] = {
        "T1": {"label": "insufficient", "evidence_span": ""},
        "T2": {"family": "other", "entry_rule": "", "exit_rule": "", "ambiguities": []},
        "T3": {"mismatches": []},
        "T4": {"plan": {}},
        "T5": {"failure_modes": [], "recommended_tests": []},
        "T6": {"matrix": {}, "decision": ""},
        "T7": {"concepts": []},
        "T8": {"asset": {}, "contradictions": []},
    }

    def call(self, task_class: str, prompt: str) -> ProviderResponse:
        stub = self._STUBS.get(task_class)
        if stub is None:
            raise ValueError(f"unknown task_class {task_class!r}")
        return ProviderResponse(
            provider=self.provider,
            model_identifier=self.model_identifier,
            raw_output=dict(stub),
            cost_usd=0.0,
            latency_ms=0.0,
        )


class RealProviderGate:
    """Credential gate for T-011-05. Raises rather than fabricating a run."""

    def __init__(self, provider: str) -> None:
        if provider not in PROVIDER_ENV_VARS:
            raise ValueError(f"unknown provider {provider!r} (allowed: {list(PROVIDER_ENV_VARS)})")
        self.provider = provider

    def is_configured(self) -> bool:
        return bool(os.environ.get(PROVIDER_ENV_VARS[self.provider]))

    def require_configured(self) -> None:
        if not self.is_configured():
            raise CredentialNotConfiguredError(
                f"{PROVIDER_ENV_VARS[self.provider]} is not set; T-011-05 real runs for "
                f"provider={self.provider!r} are deferred until the credential is configured "
                "(intake-gate 'add later' AI-key disposition)."
            )
