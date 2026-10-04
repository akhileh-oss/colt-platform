"""`AgentRuntime` (CLAUDE.md §68) — hermetic: fake repositories (in-memory, over the same
`colt_agents.ports` Protocols `colt-db`'s real repositories satisfy) and a fake Anthropic
client (a real `AsyncAnthropic` instance with only `.messages.create` replaced — the same
pattern `colt-ai`'s own Milestone 08 tests established). `tests/integration/test_agent_runtime.py`
separately proves the same mechanism against real Postgres.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock
from anthropic.types import Usage as AnthropicUsage
from pydantic import BaseModel, SecretStr

from colt_agents.definition import AgentDefinition
from colt_agents.errors import (
    AgentOutputValidationError,
    AgentTimeoutError,
    MaxToolCallsExceededError,
    ToolNotPermittedError,
)
from colt_agents.registry import ToolRegistry
from colt_agents.runtime import AgentRuntime
from colt_agents.tool import Tool
from colt_ai import AnthropicGateway
from colt_config import AnthropicSettings, ModelClass
from colt_domain import AgentRun, AgentRunStatus, ToolCall, ToolCallStatus


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    text: str


class AgentInput(BaseModel):
    message: str


class AgentOutput(BaseModel):
    answer: str


class FakeAgentRunRepository:
    def __init__(self) -> None:
        self.organization_id = uuid4()
        self.runs: dict[UUID, AgentRun] = {}

    async def start(self, **kwargs: Any) -> AgentRun:
        run = AgentRun(
            id=uuid4(),
            organization_id=self.organization_id,
            started_at=datetime.now(UTC),
            **kwargs,
        )
        self.runs[run.id] = run
        return run

    async def complete(self, run_id: UUID, **kwargs: Any) -> AgentRun:
        self.runs[run_id] = self.runs[run_id].completed(**kwargs)
        return self.runs[run_id]

    async def fail(self, run_id: UUID, **kwargs: Any) -> AgentRun:
        self.runs[run_id] = self.runs[run_id].failed(**kwargs)
        return self.runs[run_id]


class FakeToolCallRepository:
    def __init__(self, organization_id: UUID) -> None:
        self.organization_id = organization_id
        self.calls: dict[UUID, ToolCall] = {}

    async def start(self, **kwargs: Any) -> ToolCall:
        call = ToolCall(
            id=uuid4(),
            organization_id=self.organization_id,
            started_at=datetime.now(UTC),
            **kwargs,
        )
        self.calls[call.id] = call
        return call

    async def succeed(self, tool_call_id: UUID, **kwargs: Any) -> ToolCall:
        self.calls[tool_call_id] = self.calls[tool_call_id].succeeded(**kwargs)
        return self.calls[tool_call_id]

    async def fail(self, tool_call_id: UUID, **kwargs: Any) -> ToolCall:
        self.calls[tool_call_id] = self.calls[tool_call_id].failed(**kwargs)
        return self.calls[tool_call_id]


def _usage(input_tokens: int = 10, output_tokens: int = 5) -> AnthropicUsage:
    return AnthropicUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


def _text_message(output: BaseModel, *, usage: AnthropicUsage | None = None) -> Message:
    return Message(
        id="msg_" + str(uuid4()),
        content=[TextBlock(text=output.model_dump_json(), type="text")],
        model="claude-haiku-4-5-20251001",
        role="assistant",
        stop_reason="end_turn",
        stop_sequence=None,
        type="message",
        usage=usage or _usage(),
    )


def _tool_use_message(
    *, tool_name: str, tool_input: dict[str, Any], usage: AnthropicUsage | None = None
) -> Message:
    return Message(
        id="msg_" + str(uuid4()),
        content=[
            ToolUseBlock(
                id="toolu_" + str(uuid4()), input=tool_input, name=tool_name, type="tool_use"
            )
        ],
        model="claude-haiku-4-5-20251001",
        role="assistant",
        stop_reason="tool_use",
        stop_sequence=None,
        type="message",
        usage=usage or _usage(),
    )


def _echo_tool() -> Tool:
    async def handler(validated: BaseModel) -> BaseModel:
        assert isinstance(validated, EchoInput)
        return EchoOutput(text=validated.text)

    return Tool(
        name="echo", version="v1", description="echoes text", input_model=EchoInput, handler=handler
    )


def _failing_tool() -> Tool:
    async def handler(_: BaseModel) -> BaseModel:
        raise ValueError("boom")

    return Tool(
        name="echo",
        version="v1",
        description="always fails",
        input_model=EchoInput,
        handler=handler,
    )


def _definition(**overrides: Any) -> AgentDefinition:
    defaults: dict[str, Any] = {
        "name": "test-agent",
        "version": "v1",
        "purpose": "test",
        "input_schema": AgentInput,
        "output_schema": AgentOutput,
        "allowed_tools": frozenset({"echo"}),
        "model_policy": ModelClass.FAST,
        "max_tool_calls": 10,
        "timeout_seconds": 120.0,
    }
    defaults.update(overrides)
    return AgentDefinition(**defaults)


def _gateway(fake_create: Any) -> AnthropicGateway:
    client = AsyncAnthropic(api_key="sk-ant-test-key-not-real")
    client.messages.create = fake_create  # type: ignore[method-assign]
    return AnthropicGateway(
        AnthropicSettings(api_key=SecretStr("sk-ant-test-key-not-real")), client=client
    )


async def test_executes_a_tool_then_returns_schema_valid_output_and_a_complete_audit_trail() -> (
    None
):
    responses = [
        _tool_use_message(tool_name="echo", tool_input={"text": "hi"}, usage=_usage(50, 10)),
        _text_message(AgentOutput(answer="hi"), usage=_usage(80, 20)),
    ]

    async def fake_create(**kwargs: Any) -> Message:
        return responses.pop(0)

    registry = ToolRegistry()
    registry.register(_echo_tool())
    agent_runs = FakeAgentRunRepository()
    tool_calls = FakeToolCallRepository(agent_runs.organization_id)
    runtime = AgentRuntime(_gateway(fake_create), registry, agent_runs, tool_calls)

    output = await runtime.run(_definition(), input=AgentInput(message="hi"))

    assert output == AgentOutput(answer="hi")
    (run,) = agent_runs.runs.values()
    assert run.status == AgentRunStatus.COMPLETED
    assert run.input_tokens == 130
    assert run.output_tokens == 30
    assert run.tool_tokens == 60
    assert run.output_json == {"answer": "hi"}

    (call,) = tool_calls.calls.values()
    assert call.status == ToolCallStatus.SUCCEEDED
    assert call.tool_name == "echo"
    assert call.result_summary is not None


async def test_a_failing_tool_is_recorded_and_fed_back_as_an_error_result() -> None:
    responses = [
        _tool_use_message(tool_name="echo", tool_input={"text": "hi"}),
        _text_message(AgentOutput(answer="recovered")),
    ]
    seen_messages: list[Any] = []

    async def fake_create(**kwargs: Any) -> Message:
        seen_messages.append(kwargs["messages"])
        return responses.pop(0)

    registry = ToolRegistry()
    registry.register(_failing_tool())
    agent_runs = FakeAgentRunRepository()
    tool_calls = FakeToolCallRepository(agent_runs.organization_id)
    runtime = AgentRuntime(_gateway(fake_create), registry, agent_runs, tool_calls)

    output = await runtime.run(_definition(), input=AgentInput(message="hi"))

    assert output == AgentOutput(answer="recovered")
    (call,) = tool_calls.calls.values()
    assert call.status == ToolCallStatus.FAILED
    assert call.error_code == "ValueError"

    # the second call's messages include the tool_result marked is_error
    second_call_messages = seen_messages[1]
    tool_result_message = second_call_messages[-1]
    assert tool_result_message["content"][0]["is_error"] is True


async def test_exceeding_max_tool_calls_fails_the_run() -> None:
    two_tool_calls = Message(
        id="msg_1",
        content=[
            ToolUseBlock(id="toolu_1", input={"text": "a"}, name="echo", type="tool_use"),
            ToolUseBlock(id="toolu_2", input={"text": "b"}, name="echo", type="tool_use"),
        ],
        model="claude-haiku-4-5-20251001",
        role="assistant",
        stop_reason="tool_use",
        stop_sequence=None,
        type="message",
        usage=_usage(),
    )

    async def fake_create(**kwargs: Any) -> Message:
        return two_tool_calls

    registry = ToolRegistry()
    registry.register(_echo_tool())
    agent_runs = FakeAgentRunRepository()
    tool_calls = FakeToolCallRepository(agent_runs.organization_id)
    runtime = AgentRuntime(_gateway(fake_create), registry, agent_runs, tool_calls)

    with pytest.raises(MaxToolCallsExceededError):
        await runtime.run(_definition(max_tool_calls=1), input=AgentInput(message="hi"))

    (run,) = agent_runs.runs.values()
    assert run.status == AgentRunStatus.FAILED
    assert run.error_code == "MaxToolCallsExceededError"


async def test_a_call_to_an_unpermitted_tool_fails_the_run() -> None:
    async def fake_create(**kwargs: Any) -> Message:
        return _tool_use_message(tool_name="send_email", tool_input={})

    registry = ToolRegistry()
    registry.register(_echo_tool())
    agent_runs = FakeAgentRunRepository()
    tool_calls = FakeToolCallRepository(agent_runs.organization_id)
    runtime = AgentRuntime(_gateway(fake_create), registry, agent_runs, tool_calls)

    with pytest.raises(ToolNotPermittedError):
        await runtime.run(_definition(), input=AgentInput(message="hi"))

    (run,) = agent_runs.runs.values()
    assert run.status == AgentRunStatus.FAILED
    assert run.error_code == "ToolNotPermittedError"


async def test_exceeding_the_timeout_fails_the_run() -> None:
    async def fake_create(**kwargs: Any) -> Message:
        return _text_message(AgentOutput(answer="too slow"))

    registry = ToolRegistry()
    agent_runs = FakeAgentRunRepository()
    tool_calls = FakeToolCallRepository(agent_runs.organization_id)
    runtime = AgentRuntime(_gateway(fake_create), registry, agent_runs, tool_calls)

    with pytest.raises(AgentTimeoutError):
        await runtime.run(
            _definition(allowed_tools=frozenset(), timeout_seconds=0.0),
            input=AgentInput(message="hi"),
        )

    (run,) = agent_runs.runs.values()
    assert run.status == AgentRunStatus.FAILED
    assert run.error_code == "AgentTimeoutError"


async def test_an_unparseable_final_output_fails_the_run() -> None:
    bad_message = Message(
        id="msg_1",
        content=[TextBlock(text="not valid json for the schema", type="text")],
        model="claude-haiku-4-5-20251001",
        role="assistant",
        stop_reason="end_turn",
        stop_sequence=None,
        type="message",
        usage=_usage(),
    )

    async def fake_create(**kwargs: Any) -> Message:
        return bad_message

    registry = ToolRegistry()
    agent_runs = FakeAgentRunRepository()
    tool_calls = FakeToolCallRepository(agent_runs.organization_id)
    runtime = AgentRuntime(_gateway(fake_create), registry, agent_runs, tool_calls)

    with pytest.raises(AgentOutputValidationError):
        await runtime.run(_definition(allowed_tools=frozenset()), input=AgentInput(message="hi"))

    (run,) = agent_runs.runs.values()
    assert run.status == AgentRunStatus.FAILED
    assert run.error_code == "AgentOutputValidationError"


async def test_rejects_input_of_the_wrong_type() -> None:
    async def fake_create(**kwargs: Any) -> Message:
        raise AssertionError("should never be called")

    registry = ToolRegistry()
    agent_runs = FakeAgentRunRepository()
    tool_calls = FakeToolCallRepository(agent_runs.organization_id)
    runtime = AgentRuntime(_gateway(fake_create), registry, agent_runs, tool_calls)

    with pytest.raises(ValueError, match="AgentInput"):
        await runtime.run(_definition(allowed_tools=frozenset()), input=EchoInput(text="wrong"))

    assert agent_runs.runs == {}
