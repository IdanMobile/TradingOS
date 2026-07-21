"""Real-provider callers for T-011-05 Mode A runs (Anthropic + OpenAI, raw HTTP).

Raw `urllib` rather than provider SDKs, deliberately: this harness is dependency-free and
provider-neutral by design (the null provider proves the pipeline without any networking
import), and adding two vendor SDKs for a bounded benchmark would fight that. Both
providers get the same treatment — one request shape each, cost computed from the usage
tokens the venue itself reports.

Mode A discipline: both providers receive the *same* frozen prompt and the same JSON-only
system instruction derived from the task schema. No provider-specific prompt tuning here —
that is Mode B by definition.

Costs are computed from a pinned pricing table recorded into every run record, so a later
price change cannot silently rewrite historical cost evidence.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from harness.pipeline import TASK_SCHEMAS
from harness.provider import ProviderResponse

REQUEST_TIMEOUT_SECONDS = 120
MAX_OUTPUT_TOKENS = 1024  # outputs are small schema-bound JSON; a cost cap, not a guess

# USD per million tokens (input, output), pinned at run time and recorded per record.
PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.00, 25.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "gpt-4o": (2.50, 10.00),
}

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


class RealProviderError(RuntimeError):
    """A real-provider call failed; the record stays honest rather than fabricated."""


RETRYABLE_STATUS = {429, 500, 529}  # rate limit / server error / overloaded
MAX_ATTEMPTS = 4


def _post_json(url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    """POST with bounded exponential backoff on retryable statuses.

    Both providers return JSON error bodies on non-2xx; those are parsed and returned so
    the caller's error path fires with the real message instead of a bare HTTPError.
    529 (overloaded) is transient by definition — failing a benchmark run on it would
    measure Anthropic's load balancer, not the model.
    """
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        request = urllib.request.Request(  # noqa: S310 - fixed https provider endpoints
            url,
            data=json.dumps(body).encode(),
            headers={**headers, "content-type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(  # noqa: S310
                request, timeout=REQUEST_TIMEOUT_SECONDS
            ) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            if error.code in RETRYABLE_STATUS and attempt < MAX_ATTEMPTS - 1:
                last_error = error
                time.sleep(2**attempt)  # 1s, 2s, 4s
                continue
            try:
                return json.loads(error.read())  # provider's JSON error body
            except (json.JSONDecodeError, ValueError):
                raise RealProviderError(f"HTTP {error.code} from {url}") from error
    raise RealProviderError(f"retries exhausted against {url}") from last_error


def json_instruction(task_class: str) -> str:
    """The same schema instruction for every provider — identical prompt is what Mode A means."""
    required = TASK_SCHEMAS.get(task_class, ())
    return (
        "Respond with a single JSON object and nothing else - no prose, no code fences. "
        f"The object must contain exactly these keys: {sorted(required)}."
    )


def extract_json(text: str) -> dict[str, Any]:
    """Parse the model's text into a JSON object, tolerating code fences.

    A model that wraps valid JSON in ``` fences gave a correct answer in the wrong
    envelope; failing it on the envelope would measure formatting, not the task.
    Anything that still does not parse is a genuine schema failure and is returned
    as an empty object so `validate_output` records every missing key.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        cleaned = cleaned.removeprefix("json").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return {}
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _cost(model: str, input_tokens: int, output_tokens: int) -> float:
    input_rate, output_rate = PRICING_USD_PER_MTOK[model]
    return input_tokens / 1_000_000 * input_rate + output_tokens / 1_000_000 * output_rate


class AnthropicRealProvider:
    """Messages API, raw HTTP. Default model per the API guidance: claude-opus-4-8.

    `model` is parameterised because comparing models is what Mode A is for — the
    always-use-Opus default governs doing work with a model, not measuring them.
    """

    provider = "anthropic"

    def __init__(
        self, api_key: str, model: str = "claude-opus-4-8", transport: Any = _post_json
    ) -> None:
        if model not in PRICING_USD_PER_MTOK:
            raise RealProviderError(f"no pinned pricing for {model!r}; refusing to guess cost")
        self._api_key = api_key
        self.model_identifier = model
        self._transport = transport

    def call(self, task_class: str, prompt: str) -> ProviderResponse:
        started = time.monotonic()
        payload = self._transport(
            ANTHROPIC_URL,
            {
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
            },
            {
                "model": self.model_identifier,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "system": json_instruction(task_class),
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        latency_ms = (time.monotonic() - started) * 1000

        if payload.get("type") == "error":
            raise RealProviderError(f"anthropic error: {payload.get('error', {}).get('message')}")

        text = "".join(
            block.get("text", "")
            for block in payload.get("content", [])
            if block.get("type") == "text"
        )
        usage = payload.get("usage", {})
        return ProviderResponse(
            provider=self.provider,
            model_identifier=str(payload.get("model", self.model_identifier)),
            raw_output=extract_json(text),
            cost_usd=_cost(
                self.model_identifier,
                int(usage.get("input_tokens", 0)),
                int(usage.get("output_tokens", 0)),
            ),
            latency_ms=latency_ms,
        )


class OpenAIRealProvider:
    """Chat Completions API, raw HTTP, stable long-served model id."""

    provider = "openai"
    model_identifier = "gpt-4o"

    def __init__(self, api_key: str, transport: Any = _post_json) -> None:
        self._api_key = api_key
        self._transport = transport

    def call(self, task_class: str, prompt: str) -> ProviderResponse:
        started = time.monotonic()
        payload = self._transport(
            OPENAI_URL,
            {"Authorization": f"Bearer {self._api_key}"},
            {
                "model": self.model_identifier,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "messages": [
                    {"role": "system", "content": json_instruction(task_class)},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        latency_ms = (time.monotonic() - started) * 1000

        if "error" in payload:
            raise RealProviderError(f"openai error: {payload['error'].get('message')}")

        choices = payload.get("choices", [])
        text = choices[0].get("message", {}).get("content", "") if choices else ""
        usage = payload.get("usage", {})
        return ProviderResponse(
            provider=self.provider,
            model_identifier=str(payload.get("model", self.model_identifier)),
            raw_output=extract_json(text or ""),
            cost_usd=_cost(
                self.model_identifier,
                int(usage.get("prompt_tokens", 0)),
                int(usage.get("completion_tokens", 0)),
            ),
            latency_ms=latency_ms,
        )
