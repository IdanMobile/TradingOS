"""Offline tests for the T-011-05 real-provider layer. No network, no credentials."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "ai_agent"))

from harness.real_provider import (  # noqa: E402
    AnthropicRealProvider,
    OpenAIRealProvider,
    RealProviderError,
    extract_json,
    json_instruction,
)

sys.path.insert(0, str(ROOT / "scripts"))
from run_real_ai_benchmark import load_ai_keys_only  # noqa: E402


def _anthropic_payload(text: str, input_tokens: int = 1000, output_tokens: int = 100) -> dict:
    return {
        "model": "claude-opus-4-8",
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


def test_anthropic_cost_is_computed_from_usage_tokens() -> None:
    """$5/$25 per MTok pinned: 1M input + 1M output would cost exactly $30."""
    provider = AnthropicRealProvider(
        "key", transport=lambda url, h, b: _anthropic_payload('{"label": "supported"}', 1000, 100)
    )
    response = provider.call("T1", "prompt")
    # 1000 in * $5/M + 100 out * $25/M = 0.005 + 0.0025
    assert response.cost_usd == pytest.approx(0.0075)
    assert response.provider == "anthropic"
    assert response.raw_output == {"label": "supported"}


def test_openai_cost_uses_its_own_token_names_and_rates() -> None:
    provider = OpenAIRealProvider(
        "key",
        transport=lambda url, h, b: {
            "model": "gpt-4o",
            "choices": [{"message": {"content": '{"label": "contradicted"}'}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 100},
        },
    )
    response = provider.call("T1", "prompt")
    # 1000 * $2.50/M + 100 * $10/M = 0.0025 + 0.001
    assert response.cost_usd == pytest.approx(0.0035)
    assert response.raw_output == {"label": "contradicted"}


def test_mode_a_sends_the_identical_instruction_to_both_providers() -> None:
    """Provider-specific prompt tuning would be Mode B; Mode A must stay controlled."""
    captured: dict[str, dict] = {}

    def capture(name):
        def transport(url, headers, body):
            captured[name] = body
            if "messages" in body and isinstance(body.get("system"), str):
                return _anthropic_payload("{}")
            return {"choices": [{"message": {"content": "{}"}}], "usage": {}}

        return transport

    AnthropicRealProvider("k", transport=capture("anthropic")).call("T2", "same prompt")
    OpenAIRealProvider("k", transport=capture("openai")).call("T2", "same prompt")

    anthropic_system = captured["anthropic"]["system"]
    openai_system = captured["openai"]["messages"][0]["content"]
    assert anthropic_system == openai_system == json_instruction("T2")
    assert captured["anthropic"]["messages"][0]["content"] == "same prompt"
    assert captured["openai"]["messages"][1]["content"] == "same prompt"


def test_provider_errors_raise_rather_than_fabricate() -> None:
    provider = AnthropicRealProvider(
        "key", transport=lambda url, h, b: {"type": "error", "error": {"message": "overloaded"}}
    )
    with pytest.raises(RealProviderError, match="overloaded"):
        provider.call("T1", "prompt")

    openai = OpenAIRealProvider(
        "key", transport=lambda url, h, b: {"error": {"message": "invalid_api_key"}}
    )
    with pytest.raises(RealProviderError, match="invalid_api_key"):
        openai.call("T1", "prompt")


def test_extract_json_tolerates_fences_but_fails_garbage_honestly() -> None:
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here is the answer: {"a": 1}') == {"a": 1}
    # Garbage is an empty object so every required key registers as a schema error.
    assert extract_json("I cannot answer that.") == {}
    assert extract_json("[1, 2, 3]") == {}


def test_env_loader_imports_only_the_ai_keys(tmp_path: Path) -> None:
    """SUP-011: shared .env loading must not import unrelated values into the process."""
    env = tmp_path / ".env"
    env.write_text(
        "BYBIT_DEMO_API_KEY=venue-secret\n"
        "ANTHROPIC_API_KEY=ant-key\n"
        "TIOS_SIGNALS_WEBHOOK_SECRET=hook\n"
        'OPENAI_API_KEY="oai-key"\n'
        "# ANTHROPIC_API_KEY=commented-out\n",
        encoding="utf-8",
    )

    keys = load_ai_keys_only(env)

    assert keys == {"ANTHROPIC_API_KEY": "ant-key", "OPENAI_API_KEY": "oai-key"}
    assert "BYBIT_DEMO_API_KEY" not in keys
    assert "TIOS_SIGNALS_WEBHOOK_SECRET" not in keys
