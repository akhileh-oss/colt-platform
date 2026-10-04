"""The tool registry and per-agent tool permission filtering (CLAUDE.md §16.2, §68).

Permission filtering is static and happens here, before any model call: `for_agent` is the only
way `AgentRuntime` learns which tools exist for a given run, so a tool outside
`AgentDefinition.allowed_tools` is never even offered to the model — it is not merely refused
if asked for.
"""

from __future__ import annotations

from colt_agents.definition import AgentDefinition
from colt_agents.errors import ToolNotRegisteredError
from colt_agents.tool import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name!r} is already registered.")
        self._tools[tool.name] = tool

    def for_agent(self, definition: AgentDefinition) -> dict[str, Tool]:
        """The tools `definition` may use: its `allowed_tools`, minus `forbidden_tools`.

        Raises if `allowed_tools` names a tool nothing has registered — a configuration bug
        (a typo'd tool name), caught when the agent is assembled rather than silently granting
        fewer tools than intended.
        """
        selected: dict[str, Tool] = {}
        for name in definition.allowed_tools:
            if name in definition.forbidden_tools:
                continue
            tool = self._tools.get(name)
            if tool is None:
                raise ToolNotRegisteredError(
                    f"{definition.name} allows tool {name!r}, but nothing registered it."
                )
            selected[name] = tool
        return selected
