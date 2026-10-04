"""The AI Gateway (CLAUDE.md §68): the one place in Colt allowed to import the Anthropic SDK.

§8.2 forbids "service code importing provider-specific implementations directly"; §2.7
requires provider abstraction. Agents and application services call `AnthropicGateway`, never
`anthropic.*` — a provider change is a change to this file, not a grep across the codebase.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, cast

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import MessageParam
from pydantic import BaseModel

from colt_ai.errors import GatewayErrorCode, GatewayInternalError, classify
from colt_ai.pricing import estimate_cost_usd
from colt_ai.usage import GenerationResult, RawMessage, Usage
from colt_config import AnthropicSettings, ModelClass
from colt_observability import get_logger, get_meter, get_tracer

logger = get_logger(__name__)
_tracer = get_tracer(__name__)
_meter = get_meter(__name__)

_input_tokens_counter = _meter.create_counter(
    "llm_input_tokens", description="Input tokens sent to the LLM provider (CLAUDE.md §35.2)."
)
_output_tokens_counter = _meter.create_counter(
    "llm_output_tokens",
    description="Output tokens received from the LLM provider (CLAUDE.md §35.2).",
)
_provider_latency_histogram = _meter.create_histogram(
    "provider_latency",
    unit="ms",
    description="LLM provider call latency (CLAUDE.md §35.2).",
)
_provider_rate_limits_counter = _meter.create_counter(
    "provider_rate_limits",
    description="LLM provider rate-limit responses (CLAUDE.md §35.2).",
)


def create_client(settings: AnthropicSettings) -> AsyncAnthropic:
    """Build the SDK client from settings — never a module-level client (CLAUDE.md §7)."""
    return AsyncAnthropic(
        api_key=settings.api_key.get_secret_value(),
        timeout=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )


class AnthropicGateway:
    """Model routing, structured generation, usage/cost tracking and telemetry over the
    Anthropic SDK.

    `client` is injectable so tests exercise this class's routing, error classification, usage
    accounting and telemetry against a fake `AsyncAnthropic` — deterministically, with no
    network call and no API key — rather than mocking at the HTTP transport layer. This mirrors
    `colt_observability.configure_tracing`'s injectable `exporter` param.
    """

    def __init__(
        self, settings: AnthropicSettings, *, client: AsyncAnthropic | None = None
    ) -> None:
        self._settings = settings
        self._client = client if client is not None else create_client(settings)

    def model_for(self, model_class: ModelClass) -> str:
        """The concrete model ID `model_class` currently routes to (§14.1).

        Exposed so a caller that must record the model before any call completes (an agent
        runtime writing its `AgentRun` row before the first turn) doesn't need its own copy of
        `AnthropicSettings` just to ask the same question this gateway already answers.
        """
        return self._settings.model_id_for(model_class)

    async def generate_structured[OutputT: BaseModel](
        self,
        *,
        model_class: ModelClass,
        output_model: type[OutputT],
        prompt: str,
        system: str | None = None,
        max_tokens: int = 4096,
        agent_run_id: str | None = None,
    ) -> GenerationResult[OutputT]:
        """Run one call and return a validated `output_model` instance plus its usage.

        Routes `model_class` to a concrete model ID through configuration (§14.1/§14.2) rather
        than a literal model string in calling code, and validates the response against
        `output_model`'s schema server-side (`client.messages.parse`) rather than trusting
        free-text JSON.

        Deliberately never logs or traces `prompt`/`system`/the parsed content: only metadata
        (model, tokens, latency, ids) reaches logs and spans (§35.1 — "do not log ... sensitive
        personal information unnecessarily"; §93's redaction only catches sensitive *keys*, not
        free text, so the one reliable control here is to never pass call content to a logger
        or span attribute in the first place).
        """
        model = self._settings.model_id_for(model_class)
        messages: list[MessageParam] = [{"role": "user", "content": prompt}]

        async def invoke() -> Any:
            return await self._client.messages.parse(
                model=model,
                max_tokens=max_tokens,
                system=system if system is not None else anthropic.omit,
                messages=messages,
                output_format=output_model,
            )

        response, usage = await self._call(
            operation="generate_structured",
            model=model,
            model_class=model_class,
            agent_run_id=agent_run_id,
            invoke=invoke,
        )

        if response.parsed_output is None:
            raise GatewayInternalError(
                f"model {model} did not return a response matching {output_model.__name__}"
            )
        return GenerationResult(
            output=response.parsed_output, usage=usage, stop_reason=response.stop_reason
        )

    async def create_message(
        self,
        *,
        model_class: ModelClass,
        messages: list[MessageParam],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        output_model: type[BaseModel] | None = None,
        max_tokens: int = 4096,
        agent_run_id: str | None = None,
    ) -> RawMessage:
        """Run one raw `messages.create()` turn, for callers that drive a tool-use loop
        themselves (`colt_agents.AgentRuntime`) rather than wanting one validated final result.

        Unlike `generate_structured`, this returns the SDK's own content blocks unparsed — the
        caller needs to see `tool_use` blocks to decide whether to call a tool or stop, which
        `messages.parse()`'s single-validated-result contract has no way to express. `tools`
        and `output_model` may both be set in the same call (the Anthropic API supports this
        directly): the model may still call a tool, but once it stops calling tools, its final
        text response is constrained to `output_model`'s schema.
        """
        model = self._settings.model_id_for(model_class)

        async def invoke() -> Any:
            return await self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system if system is not None else anthropic.omit,
                messages=messages,
                tools=cast(Any, tools) if tools is not None else anthropic.omit,
                output_config=(
                    {"format": {"type": "json_schema", "schema": output_model.model_json_schema()}}
                    if output_model is not None
                    else anthropic.omit
                ),
            )

        response, usage = await self._call(
            operation="create_message",
            model=model,
            model_class=model_class,
            agent_run_id=agent_run_id,
            invoke=invoke,
        )
        return RawMessage(
            content=list(response.content), stop_reason=response.stop_reason, usage=usage
        )

    async def _call(
        self,
        *,
        operation: str,
        model: str,
        model_class: ModelClass,
        agent_run_id: str | None,
        invoke: Callable[[], Awaitable[Any]],
    ) -> tuple[Any, Usage]:
        """Shared call/error-classify/usage-record/telemetry path for every gateway method.

        Deliberately never logs or traces call content — see `generate_structured`'s docstring
        for why that is this file's one reliable redaction control (§35.1, §93).
        """
        start = time.monotonic()
        with _tracer.start_as_current_span(
            f"ai_gateway.{operation}",
            attributes={
                "provider": "anthropic",
                "operation": operation,
                "model": model,
                "model_class": str(model_class),
            },
        ) as span:
            try:
                response = await invoke()
            except anthropic.APIError as exc:
                latency_ms = (time.monotonic() - start) * 1000
                error = classify(exc)
                span.set_attribute("error_code", str(error.code))
                span.record_exception(error)
                if error.code == GatewayErrorCode.RATE_LIMITED:
                    _provider_rate_limits_counter.add(1, {"model": model})
                logger.warning(
                    "ai gateway call failed",
                    extra={
                        "operation": operation,
                        "provider": "anthropic",
                        "status": "error",
                        "error_code": str(error.code),
                        "latency_ms": latency_ms,
                        "model": model,
                        "model_class": str(model_class),
                        "agent_run_id": agent_run_id,
                    },
                )
                raise error from exc

            latency_ms = (time.monotonic() - start) * 1000
            usage = self._record_usage(
                model=model,
                model_class=model_class,
                raw_usage=response.usage,
                latency_ms=latency_ms,
                request_id=getattr(response, "_request_id", None),
            )
            span.set_attribute("llm.input_tokens", usage.input_tokens)
            span.set_attribute("llm.output_tokens", usage.output_tokens)
            if usage.cost_usd is not None:
                span.set_attribute("llm.cost_usd", usage.cost_usd)

            logger.info(
                "ai gateway call completed",
                extra={
                    "operation": operation,
                    "provider": "anthropic",
                    "status": "ok",
                    "latency_ms": latency_ms,
                    "model": model,
                    "model_class": str(model_class),
                    "agent_run_id": agent_run_id,
                },
            )
            return response, usage

    def _record_usage(
        self,
        *,
        model: str,
        model_class: ModelClass,
        raw_usage: anthropic.types.Usage,
        latency_ms: float,
        request_id: str | None,
    ) -> Usage:
        cost_usd = estimate_cost_usd(
            model=model,
            input_tokens=raw_usage.input_tokens,
            output_tokens=raw_usage.output_tokens,
        )
        attributes = {"model": model, "model_class": str(model_class)}
        _input_tokens_counter.add(raw_usage.input_tokens, attributes)
        _output_tokens_counter.add(raw_usage.output_tokens, attributes)
        _provider_latency_histogram.record(latency_ms, attributes)
        return Usage(
            model=model,
            model_class=model_class,
            input_tokens=raw_usage.input_tokens,
            output_tokens=raw_usage.output_tokens,
            cache_creation_input_tokens=raw_usage.cache_creation_input_tokens or 0,
            cache_read_input_tokens=raw_usage.cache_read_input_tokens or 0,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            request_id=request_id,
        )
