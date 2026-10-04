from __future__ import annotations

import pytest
from pydantic import BaseModel

from colt_agents.definition import AgentDefinition
from colt_agents.errors import ToolNotRegisteredError
from colt_agents.registry import ToolRegistry
from colt_agents.tool import Tool
from colt_config import ModelClass


class _Input(BaseModel):
    pass


class _Output(BaseModel):
    pass


async def _handler(_: BaseModel) -> BaseModel:
    return _Output()


def _tool(name: str) -> Tool:
    return Tool(name=name, version="v1", description="d", input_model=_Input, handler=_handler)


def _definition(
    *, allowed: frozenset[str], forbidden: frozenset[str] = frozenset()
) -> AgentDefinition:
    return AgentDefinition(
        name="agent",
        version="v1",
        purpose="test",
        input_schema=_Input,
        output_schema=_Output,
        allowed_tools=allowed,
        forbidden_tools=forbidden,
        model_policy=ModelClass.FAST,
    )


def test_for_agent_returns_only_allowed_tools() -> None:
    registry = ToolRegistry()
    registry.register(_tool("get_lead"))
    registry.register(_tool("send_email"))

    tools = registry.for_agent(_definition(allowed=frozenset({"get_lead"})))

    assert set(tools) == {"get_lead"}


def test_for_agent_excludes_forbidden_tools_even_if_allowed() -> None:
    registry = ToolRegistry()
    registry.register(_tool("get_lead"))

    tools = registry.for_agent(
        _definition(allowed=frozenset({"get_lead"}), forbidden=frozenset({"get_lead"}))
    )

    assert tools == {}


def test_for_agent_raises_when_an_allowed_tool_was_never_registered() -> None:
    registry = ToolRegistry()

    with pytest.raises(ToolNotRegisteredError, match="get_lead"):
        registry.for_agent(_definition(allowed=frozenset({"get_lead"})))


def test_registering_the_same_tool_name_twice_is_rejected() -> None:
    registry = ToolRegistry()
    registry.register(_tool("get_lead"))

    with pytest.raises(ValueError, match="get_lead"):
        registry.register(_tool("get_lead"))
