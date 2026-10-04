# colt-agents

Agent definitions, the typed tool interface, and the agent runtime.

`AgentRuntime` drives one agent's tool-use loop over `colt_ai.AnthropicGateway` and persists its
audit trail:

```python
from colt_agents import AgentRuntime, ToolRegistry
from colt_agents.research_agent import RESEARCH_AGENT_DEFINITION, ResearchAgentInput
from colt_agents.tools import build_fetch_page_tool, build_record_evidence_tool, build_search_web_tool

registry = ToolRegistry()
registry.register(build_search_web_tool(search_provider))
registry.register(build_fetch_page_tool(fetch_provider))
registry.register(build_record_evidence_tool(record_evidence_use_case))

runtime = AgentRuntime(gateway, registry, agent_run_repository, tool_call_repository)
output = await runtime.run(
    RESEARCH_AGENT_DEFINITION,
    input=ResearchAgentInput(
        company_id=company_id, company_name="Acme Rockets", company_domain="acme.example.com"
    ),
)
```

`RESEARCH_AGENT_DEFINITION` (CLAUDE.md §12.5) is the first of the ten product agents actually
built: it returns a `ResearchDossier` whose `DossierClaim`s are labeled `FACT`/`INFERENCE`/
`HYPOTHESIS`, and a validator makes a `FACT` claim with no linked `evidence_id` impossible to
construct. `DISCOVERY_AGENT_DEFINITION`/`ENRICHMENT_AGENT_DEFINITION` (§12.3-§12.4) are next:
`search_companies`/`search_people` deduplicate every candidate against already-known records
(§22) before creating anything; `enrich_company`/`enrich_person` never let a lower-confidence
provider result overwrite higher-confidence data already on file. `EXAMPLE_AGENT_DEFINITION`/
`build_get_lead_tool` remain as Milestone 09's scaffolding.

See [`docs/architecture/AGENT_ARCHITECTURE.md`](../../../docs/architecture/AGENT_ARCHITECTURE.md)
for the full mechanism (permission filtering, persistence, redaction, the evidence pipeline),
and [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how
this package fits into the layering. `CLAUDE.md` §5, §12-§16, §68 are the governing
specification.
