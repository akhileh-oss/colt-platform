"""`AnthropicGateway` (CLAUDE.md §68): model routing, structured generation, usage/cost
tracking, redaction and error classification — proven deterministically against a fake
response, because no real Anthropic API key exists in this environment. The real network
call this milestone's acceptance criterion describes is explicitly unverified; see the PR.

The fake is injected at the `AsyncAnthropic.messages.parse` boundary (a real client instance
with that one method replaced), not at the HTTP transport — so every line of this module's
own logic (routing, usage accounting, error classification, telemetry, redaction) runs for
real, and only the actual network round-trip is stood in for.
"""

from __future__ import annotations

import logging

import httpx2
import pytest
from anthropic import AsyncAnthropic, BadRequestError, RateLimitError
from anthropic.types import Usage as AnthropicUsage
from anthropic.types.parsed_message import ParsedMessage, ParsedTextBlock
from pydantic import BaseModel, SecretStr

from colt_ai.client import AnthropicGateway
from colt_ai.errors import (
    GatewayErrorCode,
    GatewayInternalError,
    GatewayProviderRejectedError,
    GatewayRateLimitedError,
)
from colt_config import AnthropicSettings, ModelClass

_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


class _Answer(BaseModel):
    answer: str


def _parsed_response(
    *, model: str, answer: str | None, input_tokens: int, output_tokens: int
) -> ParsedMessage[_Answer]:
    """Build a real `ParsedMessage` the way the SDK would, rather than a loose mock — so this
    test exercises the actual `.parsed_output`/`.usage` attribute access `client.py` performs.
    `answer=None` produces a response with no parsed content, for the not-parsed branch.
    """
    if answer is None:
        block = ParsedTextBlock[_Answer](type="text", text="not valid json")
    else:
        parsed = _Answer(answer=answer)
        block = ParsedTextBlock[_Answer](
            type="text", text=parsed.model_dump_json(), parsed_output=parsed
        )
    usage = AnthropicUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    return ParsedMessage[_Answer](
        id="msg_test",
        content=[block],
        model=model,
        role="assistant",
        stop_reason="end_turn",
        stop_sequence=None,
        type="message",
        usage=usage,
    )


@pytest.fixture
def settings() -> AnthropicSettings:
    return AnthropicSettings(api_key=SecretStr("sk-ant-test-key-not-real"))


@pytest.fixture
def client() -> AsyncAnthropic:
    """A real `AsyncAnthropic` instance — tests replace `.messages.parse` below, so
    constructing it never makes a network call."""
    return AsyncAnthropic(api_key="sk-ant-test-key-not-real")


async def test_generate_structured_returns_validated_output_and_records_usage(
    settings: AnthropicSettings, client: AsyncAnthropic
) -> None:
    response = _parsed_response(
        model=settings.model_fast, answer="42", input_tokens=120, output_tokens=30
    )
    calls: list[dict[str, object]] = []

    async def fake_parse(**kwargs: object) -> ParsedMessage[_Answer]:
        calls.append(kwargs)
        return response

    client.messages.parse = fake_parse  # type: ignore[assignment]

    gateway = AnthropicGateway(settings, client=client)
    result = await gateway.generate_structured(
        model_class=ModelClass.FAST,
        output_model=_Answer,
        prompt="What is the answer to everything?",
    )

    assert result.output == _Answer(answer="42")
    assert result.stop_reason == "end_turn"
    assert result.usage.model == settings.model_fast
    assert result.usage.model_class == ModelClass.FAST
    assert result.usage.input_tokens == 120
    assert result.usage.output_tokens == 30
    assert result.usage.cost_usd == pytest.approx(120 / 1_000_000 * 1.00 + 30 / 1_000_000 * 5.00)

    assert len(calls) == 1
    assert calls[0]["model"] == settings.model_fast
    assert calls[0]["output_format"] is _Answer


async def test_generate_structured_routes_each_model_class_through_configuration(
    settings: AnthropicSettings, client: AsyncAnthropic
) -> None:
    seen_models: list[object] = []

    async def fake_parse(**kwargs: object) -> ParsedMessage[_Answer]:
        seen_models.append(kwargs["model"])
        return _parsed_response(
            model=str(kwargs["model"]), answer="ok", input_tokens=1, output_tokens=1
        )

    client.messages.parse = fake_parse  # type: ignore[assignment]
    gateway = AnthropicGateway(settings, client=client)

    for model_class, expected_model in (
        (ModelClass.FAST, settings.model_fast),
        (ModelClass.STANDARD, settings.model_standard),
        (ModelClass.DEEP, settings.model_deep),
        (ModelClass.STRATEGIC, settings.model_strategic),
    ):
        await gateway.generate_structured(
            model_class=model_class, output_model=_Answer, prompt="hi"
        )
        assert seen_models[-1] == expected_model


async def test_generate_structured_raises_when_the_model_returns_unparseable_content(
    settings: AnthropicSettings, client: AsyncAnthropic
) -> None:
    response = _parsed_response(
        model=settings.model_fast, answer=None, input_tokens=5, output_tokens=5
    )

    async def fake_parse(**kwargs: object) -> ParsedMessage[_Answer]:
        return response

    client.messages.parse = fake_parse  # type: ignore[assignment]
    gateway = AnthropicGateway(settings, client=client)

    with pytest.raises(GatewayInternalError):
        await gateway.generate_structured(
            model_class=ModelClass.FAST, output_model=_Answer, prompt="hi"
        )


async def test_generate_structured_classifies_rate_limit_as_retryable(
    settings: AnthropicSettings, client: AsyncAnthropic
) -> None:
    http_response = httpx2.Response(429, request=_REQUEST, headers={"retry-after": "1"})
    error = RateLimitError("rate limited", response=http_response, body=None)

    async def fake_parse(**kwargs: object) -> ParsedMessage[_Answer]:
        raise error

    client.messages.parse = fake_parse  # type: ignore[assignment]
    gateway = AnthropicGateway(settings, client=client)

    with pytest.raises(GatewayRateLimitedError) as exc_info:
        await gateway.generate_structured(
            model_class=ModelClass.FAST, output_model=_Answer, prompt="hi"
        )

    assert exc_info.value.code == GatewayErrorCode.RATE_LIMITED
    assert exc_info.value.retryable is True


async def test_generate_structured_classifies_bad_request_as_not_retryable(
    settings: AnthropicSettings, client: AsyncAnthropic
) -> None:
    http_response = httpx2.Response(400, request=_REQUEST)
    error = BadRequestError("invalid request", response=http_response, body=None)

    async def fake_parse(**kwargs: object) -> ParsedMessage[_Answer]:
        raise error

    client.messages.parse = fake_parse  # type: ignore[assignment]
    gateway = AnthropicGateway(settings, client=client)

    with pytest.raises(GatewayProviderRejectedError) as exc_info:
        await gateway.generate_structured(
            model_class=ModelClass.FAST, output_model=_Answer, prompt="hi"
        )

    assert exc_info.value.retryable is False


async def test_generate_structured_never_logs_or_traces_the_prompt(
    settings: AnthropicSettings, client: AsyncAnthropic, caplog: pytest.LogCaptureFixture
) -> None:
    """§35.1 ("do not log ... sensitive personal information unnecessarily") combined with
    §93's redaction only catching sensitive *keys*, not free text, means the gateway's own
    logging must never pass prompt/response content to the logger in the first place — this
    proves that holds for both the success and the failure path."""
    secret = "the secret launch codes are 19-84-ORWELL"  # noqa: S105 - test fixture, not a credential
    caplog.set_level(logging.INFO, logger="colt_ai.client")

    response = _parsed_response(
        model=settings.model_fast, answer="ok", input_tokens=1, output_tokens=1
    )

    async def fake_parse_ok(**kwargs: object) -> ParsedMessage[_Answer]:
        return response

    client.messages.parse = fake_parse_ok  # type: ignore[assignment]
    gateway = AnthropicGateway(settings, client=client)
    await gateway.generate_structured(
        model_class=ModelClass.FAST, output_model=_Answer, prompt=secret, system=secret
    )

    http_response = httpx2.Response(400, request=_REQUEST)
    error = BadRequestError(secret, response=http_response, body=None)

    async def fake_parse_error(**kwargs: object) -> ParsedMessage[_Answer]:
        raise error

    client.messages.parse = fake_parse_error  # type: ignore[assignment]
    with pytest.raises(GatewayProviderRejectedError):
        await gateway.generate_structured(
            model_class=ModelClass.FAST, output_model=_Answer, prompt=secret, system=secret
        )

    for record in caplog.records:
        assert secret not in record.getMessage()
        for value in vars(record).values():
            assert secret not in str(value)
