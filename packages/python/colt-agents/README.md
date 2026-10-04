# colt-agents

Agent definitions, the typed tool interface, and the agent runtime.

`AgentRuntime` drives one agent's tool-use loop over `colt_ai.AnthropicGateway` and persists its
audit trail:

```python
from colt_agents import AgentRuntime, ToolRegistry
from colt_agents.example_agent import EXAMPLE_AGENT_DEFINITION, ExampleAgentInput
from colt_agents.tools import build_get_lead_tool

registry = ToolRegistry()
registry.register(build_get_lead_tool(get_lead_use_case))

runtime = AgentRuntime(gateway, registry, agent_run_repository, tool_call_repository)
output = await runtime.run(EXAMPLE_AGENT_DEFINITION, input=ExampleAgentInput(lead_id=lead_id))
```

See [`docs/architecture/AGENT_ARCHITECTURE.md`](../../../docs/architecture/AGENT_ARCHITECTURE.md)
for the full mechanism (permission filtering, persistence, redaction), and
[`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering. `CLAUDE.md` §5, §12-§16, §68 are the governing specification.
