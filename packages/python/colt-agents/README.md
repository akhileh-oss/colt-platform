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
provider result overwrite higher-confidence data already on file. `SIGNAL_AGENT_DEFINITION`
(§12.6) polls raw trigger events (`poll_signal_sources`) and records the strongest one
(`record_signal`), which returns a deterministically computed `rank` right alongside the
persisted `signal_id`. `SCORING_AGENT_DEFINITION` (§12.7, §21) supplies only the two
judgment-requiring components (`persona_fit`, `model_assessment`) of a hybrid lead score;
`score_lead` computes `overall_score`/`reason_codes`/qualification deterministically from all
five, and appends to the lead's score history rather than overwriting it.
`PERSONALIZATION_AGENT_DEFINITION`/`MESSAGING_AGENT_DEFINITION` (§12.8-§12.9) are next:
`PersonalizationAgent` must call `list_evidence_for_lead` before `select_evidence`, which rejects
any evidence id that call didn't just return (and an empty selection outright) — a strategy with
no cited evidence is structurally impossible, not just discouraged by prompt. `MessagingAgent`'s
one tool, `draft_message`, independently re-validates every evidence id against the real
`EvidenceRepository` before persisting a `Message`, since the evidence ids it receives are not
guaranteed to be the same set `select_evidence` already checked. `EXAMPLE_AGENT_DEFINITION`/
`build_get_lead_tool` remain as Milestone 09's scaffolding.

`REPLY_INTELLIGENCE_AGENT_DEFINITION` (§12.10, Milestone 19) classifies one inbound reply —
`intent`, `sentiment`, `urgency`, `objection`, `asks_question`, `meeting_signal`, a
`recommended_state_transition`, `confidence`, and a `suggested_response` a human reads before
ever sending it. Its one tool, `record_reply_classification`, never applies the model's own
`recommended_state_transition` as-is: `colt_application.reply_classification.determine_
conversation_transition` decides the state actually applied, deterministically — a HIGH-urgency
reply always produces a `HUMAN_HANDOFF` regardless of what the model recommended, and a
conversation already closed (`UNSUBSCRIBED`/`HUMAN_HANDOFF`) never reopens from a later reply.
`ReplyIntent`/`Sentiment` are this milestone's own closed vocabularies, the same documented-
design-decision pattern `CampaignStatus` (Milestone 14) already established where CLAUDE.md
names a field without enumerating its values.

`OPPORTUNITY_AGENT_DEFINITION` (§12.11, Milestone 21) — CLAUDE.md's shortest agent entry, with
no input/output schema or tool list given — judges one thing: whether a `POSITIVE` conversation
carries real commercial intent, and, only then, an optional deal value its own `OpportunityDecision`
validator refuses to accept unlabeled (`is_estimate` must be `true` whenever a value is given —
no configured override source exists anywhere in this codebase to ever let one go unlabeled,
§12.11's "estimates must be labeled estimates"). Its one tool, `create_or_update_opportunity`,
is the only path into `CreateOrUpdateOpportunity`'s deterministic dedup check — at most one open
opportunity per company — so the model deciding "yes, create one" can never itself create a
duplicate.

See [`docs/architecture/AGENT_ARCHITECTURE.md`](../../../docs/architecture/AGENT_ARCHITECTURE.md)
for the full mechanism (permission filtering, persistence, redaction, the evidence pipeline),
and [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how
this package fits into the layering. `CLAUDE.md` §5, §12-§16, §68 are the governing
specification.
