"""The agent runtime (CLAUDE.md §68): drives one agent's tool-use loop and persists its audit
trail.

The loop is intentionally dumb: it does not reason about *which* tool to call — that is the
model's job, inside the separation §2.1 draws ("Claude = reasoning", "Typed tools = controlled
capabilities"). This file only ever does what the model's response says, against the tool set
`ToolRegistry.for_agent` already filtered to what the agent is allowed to use, and it writes
down everything that happened — an `AgentRun` row, and one `ToolCall` row per tool invocation
(§10.15, §10.16) — whether the run succeeds or fails.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from anthropic.types import MessageParam
from pydantic import BaseModel, ValidationError

from colt_agents.definition import AgentDefinition
from colt_agents.errors import (
    AgentError,
    AgentOutputValidationError,
    AgentTimeoutError,
    MaxToolCallsExceededError,
    ToolNotPermittedError,
)
from colt_agents.ports import AgentRunRepository, ToolCallRepository
from colt_agents.registry import ToolRegistry
from colt_agents.tool import Tool
from colt_ai import AnthropicGateway, GatewayError
from colt_observability import get_logger, redact

logger = get_logger(__name__)


def _hash_input(value: BaseModel) -> str:
    canonical = json.dumps(value.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AgentRuntime:
    def __init__(
        self,
        gateway: AnthropicGateway,
        registry: ToolRegistry,
        agent_runs: AgentRunRepository,
        tool_calls: ToolCallRepository,
    ) -> None:
        self._gateway = gateway
        self._registry = registry
        self._agent_runs = agent_runs
        self._tool_calls = tool_calls

    async def run(
        self,
        definition: AgentDefinition,
        *,
        input: BaseModel,
        system_prompt: str | None = None,
        prompt_version: str | None = None,
        workflow_id: str | None = None,
        workflow_run_id: str | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
    ) -> BaseModel:
        if not isinstance(input, definition.input_schema):
            raise ValueError(
                f"{definition.name}: input must be a {definition.input_schema.__name__} "
                f"instance, got {type(input).__name__}."
            )

        tools_by_name = self._registry.for_agent(definition)
        anthropic_tools = [tool.to_anthropic_tool() for tool in tools_by_name.values()] or None
        model_name = self._gateway.model_for(definition.model_policy)

        run = await self._agent_runs.start(
            agent_name=definition.name,
            agent_version=definition.version,
            model_name=model_name,
            input_hash=_hash_input(input),
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            entity_type=entity_type,
            entity_id=entity_id,
            prompt_version=prompt_version,
        )

        messages: list[MessageParam] = [{"role": "user", "content": input.model_dump_json()}]
        deadline = time.monotonic() + definition.timeout_seconds
        total_input_tokens = 0
        total_output_tokens = 0
        tool_tokens = 0
        tool_call_count = 0
        cost_usd: float | None = 0.0

        try:
            while True:
                if time.monotonic() > deadline:
                    raise AgentTimeoutError(
                        f"{definition.name} exceeded {definition.timeout_seconds}s."
                    )

                message = await self._gateway.create_message(
                    model_class=definition.model_policy,
                    messages=messages,
                    system=system_prompt,
                    tools=anthropic_tools,
                    output_model=definition.output_schema,
                    agent_run_id=str(run.id),
                )
                total_input_tokens += message.usage.input_tokens
                total_output_tokens += message.usage.output_tokens
                if cost_usd is not None and message.usage.cost_usd is not None:
                    cost_usd += message.usage.cost_usd
                else:
                    cost_usd = None

                if message.stop_reason != "tool_use":
                    output = self._parse_final_output(message.content, definition.output_schema)
                    await self._agent_runs.complete(
                        run.id,
                        at=datetime.now(UTC),
                        input_tokens=total_input_tokens,
                        output_tokens=total_output_tokens,
                        tool_tokens=tool_tokens,
                        estimated_cost_usd=cost_usd,
                        output_json=output.model_dump(mode="json"),
                    )
                    return output

                tool_tokens += message.usage.input_tokens + message.usage.output_tokens
                tool_use_blocks = [block for block in message.content if block.type == "tool_use"]
                tool_call_count += len(tool_use_blocks)
                if tool_call_count > definition.max_tool_calls:
                    raise MaxToolCallsExceededError(
                        f"{definition.name} exceeded max_tool_calls={definition.max_tool_calls}."
                    )

                messages.append({"role": "assistant", "content": message.content})
                tool_results: list[dict[str, Any]] = []
                for block in tool_use_blocks:
                    tool = tools_by_name.get(block.name)
                    if tool is None:
                        raise ToolNotPermittedError(
                            f"{definition.name} received a call to unpermitted tool {block.name!r}."
                        )
                    result_content, is_error = await self._execute_tool(run.id, tool, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_content,
                            **({"is_error": True} if is_error else {}),
                        }
                    )
                messages.append({"role": "user", "content": cast(Any, tool_results)})
        except GatewayError as exc:
            await self._agent_runs.fail(
                run.id, at=datetime.now(UTC), error_code=str(exc.code), error_message=str(exc)
            )
            raise
        except AgentError as exc:
            await self._agent_runs.fail(
                run.id,
                at=datetime.now(UTC),
                error_code=type(exc).__name__,
                error_message=str(exc),
            )
            raise

    def _parse_final_output(self, content: list[Any], output_schema: type[BaseModel]) -> BaseModel:
        for block in content:
            if block.type == "text":
                try:
                    return output_schema.model_validate_json(block.text)
                except ValidationError as exc:
                    raise AgentOutputValidationError(str(exc)) from exc
        raise AgentOutputValidationError(
            f"model produced no text block to parse as {output_schema.__name__}."
        )

    async def _execute_tool(
        self, run_id: UUID, tool: Tool, raw_input: dict[str, Any]
    ) -> tuple[str, bool]:
        """Run one tool, recording a `ToolCall` row whether it succeeds or fails.

        Returns `(content, is_error)` for the `tool_result` block — a failing tool's error is
        fed back to the model as `is_error: true` rather than crashing the whole agent run (the
        SDK's own documented pattern: "don't drop it").
        """
        started_at = time.monotonic()
        call = await self._tool_calls.start(
            agent_run_id=run_id,
            tool_name=tool.name,
            tool_version=tool.version,
            arguments_redacted=json.dumps(redact(raw_input), default=str, sort_keys=True),
        )
        try:
            validated_input = tool.input_model.model_validate(raw_input)
            result = await tool.handler(validated_input)
        except Exception as exc:  # noqa: BLE001 - a tool is arbitrary handler code; its
            # failure must become a recorded, returned tool_result, not an unhandled crash.
            latency_ms = (time.monotonic() - started_at) * 1000
            await self._tool_calls.fail(
                call.id, at=datetime.now(UTC), error_code=type(exc).__name__, latency_ms=latency_ms
            )
            logger.warning(
                "tool call failed",
                extra={
                    "operation": "tool_call",
                    "tool_name": tool.name,
                    "status": "error",
                    "error_code": type(exc).__name__,
                    "latency_ms": latency_ms,
                },
            )
            return f"Error: {exc}", True

        latency_ms = (time.monotonic() - started_at) * 1000
        result_json = result.model_dump_json()
        await self._tool_calls.succeed(
            call.id,
            at=datetime.now(UTC),
            result_summary=result_json[:500],
            latency_ms=latency_ms,
        )
        logger.info(
            "tool call completed",
            extra={
                "operation": "tool_call",
                "tool_name": tool.name,
                "status": "ok",
                "latency_ms": latency_ms,
            },
        )
        return result_json, False
