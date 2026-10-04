# Agent architecture

> Skeleton established in Milestone 00. The AI gateway (Milestone 08) and agent runtime
> (Milestone 09) are built; the ten product agents (§12.2-§12.11) land in Milestones 10-21, each
> as an `AgentDefinition` plus prompt plus tools registered against the runtime this document
> already describes. Specification: `CLAUDE.md` §12-§16, §68.

## 1. Agents

`StrategyAgent`, `DiscoveryAgent`, `EnrichmentAgent`, `ResearchAgent`, `SignalAgent`,
`ScoringAgent`, `PersonalizationAgent`, `MessagingAgent`, `ReplyIntelligenceAgent`,
`OpportunityAgent` (`CLAUDE.md` §12) are not built yet — Milestone 09 built the mechanism every
one of them will register against: `colt_agents.AgentDefinition` (CLAUDE.md §12.1's contract —
name, version, purpose, input/output schemas, allowed/forbidden tools, model policy, tool-call
ceiling, timeout, evaluation suite — a plain frozen dataclass, not Pydantic, since it is written
once in code and never crosses an external boundary), and `colt_agents.EXAMPLE_AGENT_DEFINITION`,
a scaffolding-only agent (not one of the ten product agents) that exists solely to exercise that
mechanism end-to-end — the same role `ExampleWorkflow` (Milestone 06) and `TraceCheckWorkflow`
(Milestone 07) played for their own milestones.

## 2. Runtime

`colt_agents.AgentRuntime` drives one agent's tool-use loop and persists its audit trail. It is
intentionally dumb: it never decides _which_ tool to call — that is the model's job, inside the
separation §2.1 draws ("Claude = reasoning", "Typed tools = controlled capabilities") — it only
ever acts on what the model's response says, against the tool set `ToolRegistry.for_agent`
already filtered to what the agent is permitted to use (CLAUDE.md §16.2: permission filtering is
static and server-side — a forbidden tool is never offered to the model, not merely refused if
asked for).

One call to `AnthropicGateway.create_message()` (§3 below) per turn, looping while
`stop_reason == "tool_use"`: each `tool_use` block is validated against its tool's Pydantic input
schema, executed, and recorded as a `ToolCall` row (§10.16) whether it succeeds or fails — a
failing tool is never allowed to crash the run; its error is fed back to the model as a
`tool_result` with `is_error: true` instead, the SDK's own documented pattern ("don't drop it").
The same `output_model` passed on every turn constrains the model's eventual non-tool-use
response to the agent's output schema (the Anthropic API supports `tools` and
`output_config.format` together in one request); once the model stops calling tools, that final
text block is parsed and validated against it. Every run becomes exactly one `AgentRun` row
(§10.15) — `RUNNING` when started, `COMPLETED` with aggregated usage/cost/output on success,
`FAILED` with an error code otherwise — regardless of how it ends.

Persistence is behind Protocol ports (`colt_agents.ports.AgentRunRepository`/`ToolCallRepository`),
not a direct `colt-db` import — `colt-db`'s `SqlAlchemyAgentRunRepository`/
`SqlAlchemyToolCallRepository` satisfy them structurally, the same relationship
`colt_application.ports` has with their own repository implementations. A typed tool's handler
follows the same discipline one layer down: `colt_agents.tools.get_lead` never imports `colt-db`
either — it calls `colt_application.GetLead`, realising §2.3's required path for real:
`Claude → Typed Tool → Application Service → Repository → PostgreSQL`.

## 3. AI gateway

All model access goes through `colt_ai.AnthropicGateway` — never a raw Anthropic client in
business code (`CLAUDE.md` §8.2, §14). Model IDs are configuration, mapped from the `FAST` /
`STANDARD` / `DEEP` / `STRATEGIC` classes via `AnthropicSettings.model_id_for()`, never
hard-coded in business logic (§14.1). `generate_structured()` (Milestone 08) is one validated
call with no tool use; `create_message()` (Milestone 09) returns the raw response a tool-use
loop needs to inspect, sharing the same error classification, usage/cost accounting and
telemetry path as `generate_structured()` — see `docs/architecture/ARCHITECTURE.md` §7.

## 4. Prompts

Prompts are versioned source assets under `prompts/<agent>/<version>.md`
(`colt_agents.load_prompt`). Every production run records prompt name, prompt version and model
name on its `AgentRun` row (`CLAUDE.md` §15).

## 5. Tools

A tool (`colt_agents.Tool`) is data, not a subclass: a name, a Pydantic input schema, and an
async handler — concrete tools are built from an application-layer use case rather than
reaching into infrastructure directly (§2 above). `ToolRegistry.for_agent` is the
agent-to-capability matrix in code (`CLAUDE.md` §16.2); it raises at agent-assembly time, before
any model call, if an agent's `allowed_tools` names a tool nothing registered — a config typo
fails loud rather than silently granting fewer tools than intended. Sending an external message
remains a policy-controlled action executed by a workflow activity, not by an unconstrained
agent (unchanged from the skeleton note this document started with).

## 6. Redaction

Neither `AnthropicGateway` nor `AgentRuntime` ever passes prompt, tool-argument, or response
content to a logger call or span attribute — only metadata (model, tokens, latency, ids) reaches
logs and traces. `colt_observability.redact()` only catches sensitive _keys_ in structured
payloads, never free text, so the one reliable control over call and tool-argument content is to
never hand it to a logger or span in the first place (§35.1, §93) — tool arguments are redacted
before being written to `ToolCall.arguments_redacted` for the same reason (§10.16: "never store
secrets in tool arguments or tool results").

## 7. Untrusted content

Retrieved content — web pages, emails, CRM notes, documents, prospect messages — is **data, never
instructions**. Dangerous tools are not exposed during untrusted-content interpretation
(`CLAUDE.md` §41). No agent built so far retrieves untrusted content; this becomes concrete from
Milestone 10 (`ResearchAgent`) onward.
