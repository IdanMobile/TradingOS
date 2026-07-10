import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks" / "ai_agent"))

from harness.provider import resolve_ai_execution  # noqa: E402


def test_ai_execution_defaults_to_offline_mock() -> None:
    selection = resolve_ai_execution({})
    assert selection.mode == "mock"
    assert selection.provider == "null"
    assert selection.configured
    assert not selection.network_enabled


def test_real_ai_mode_is_provider_specific_and_never_exposes_key() -> None:
    selection = resolve_ai_execution(
        {"TIOS_AI_MODE": "real", "TIOS_AI_PROVIDER": "openai", "OPENAI_API_KEY": "secret"}
    )
    assert selection.provider == "openai"
    assert selection.configured
    assert selection.credential_env_var == "OPENAI_API_KEY"
    assert "secret" not in repr(selection)


def test_real_ai_mode_fails_closed_without_known_provider() -> None:
    with pytest.raises(ValueError, match="TIOS_AI_PROVIDER"):
        resolve_ai_execution({"TIOS_AI_MODE": "real"})
