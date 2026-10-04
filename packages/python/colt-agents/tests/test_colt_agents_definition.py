from __future__ import annotations

from pydantic import BaseModel

from colt_agents.definition import AgentDefinition
from colt_config import ModelClass


class _Input(BaseModel):
    pass


class _Output(BaseModel):
    pass


def test_forbidden_tools_may_narrow_a_broader_allowed_set() -> None:
    """`forbidden_tools` carves exceptions out of `allowed_tools` — a tool named in both is the
    normal way to express "generally allowed, but not for this agent" (see
    `ToolRegistry.for_agent`, which is what actually excludes it)."""
    definition = AgentDefinition(
        name="agent",
        version="v1",
        purpose="test",
        input_schema=_Input,
        output_schema=_Output,
        allowed_tools=frozenset({"get_lead", "send_email"}),
        forbidden_tools=frozenset({"send_email"}),
        model_policy=ModelClass.FAST,
    )

    assert definition.allowed_tools == frozenset({"get_lead", "send_email"})
    assert definition.forbidden_tools == frozenset({"send_email"})


def test_defaults_are_applied() -> None:
    definition = AgentDefinition(
        name="agent",
        version="v1",
        purpose="test",
        input_schema=_Input,
        output_schema=_Output,
        allowed_tools=frozenset({"get_lead"}),
        model_policy=ModelClass.FAST,
    )

    assert definition.forbidden_tools == frozenset()
    assert definition.max_tool_calls == 10
    assert definition.timeout_seconds == 120.0
    assert definition.evaluation_suite is None
