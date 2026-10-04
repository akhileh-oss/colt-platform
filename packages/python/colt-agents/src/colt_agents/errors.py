"""Agent-runtime errors (CLAUDE.md §16.2, §36, §68)."""

from __future__ import annotations


class AgentError(Exception):
    """Base for every agent-runtime failure."""


class ToolNotRegisteredError(AgentError):
    """An `AgentDefinition` allows a tool name the registry has nothing registered for.

    A misconfiguration, not a runtime condition — raised when the agent is assembled, before any
    model call, so a typo in `allowed_tools` fails loud instead of silently granting no tools.
    """


class ToolNotPermittedError(AgentError):
    """The model asked to call a tool outside the agent's `allowed_tools` (CLAUDE.md §16.2).

    Tool permission filtering is static and server-side: the model only ever sees the tools it is
    allowed to see (`ToolRegistry.for_agent`), so this should never actually fire against a real
    model response — it exists as the defense that makes that guarantee load-bearing rather than
    assumed, the same reasoning `TenantScopedRepository._select_scoped` applies to tenant scoping.
    """


class MaxToolCallsExceededError(AgentError):
    """The agent made more tool calls than `AgentDefinition.max_tool_calls` permits."""


class AgentTimeoutError(AgentError):
    """The agent run exceeded `AgentDefinition.timeout_seconds`."""


class AgentOutputValidationError(AgentError):
    """The model's final structured output did not validate against the agent's output schema."""


class PromptNotFoundError(AgentError):
    """No prompt file exists at the expected `prompts/<agent>/<version>.md` path (CLAUDE.md §15)."""
