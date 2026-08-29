# Agent architecture

> Skeleton established in Milestone 00; populated across Milestones 08–09 (AI gateway and agent
> runtime) and 10–21 (individual agents). Specification: `CLAUDE.md` §12–§16.

## 1. Agents

`StrategyAgent`, `DiscoveryAgent`, `EnrichmentAgent`, `ResearchAgent`, `SignalAgent`,
`ScoringAgent`, `PersonalizationAgent`, `MessagingAgent`, `ReplyIntelligenceAgent`,
`OpportunityAgent` (`CLAUDE.md` §12).

Every agent declares name, version, purpose, input and output schemas, allowed and forbidden tools,
model policy, tool-call ceiling, timeout and evaluation suite (`CLAUDE.md` §12.1).

## 2. Runtime

A single `AgentRuntime` owns prompt loading and versioning, model selection, tool registration and
permission filtering, structured output validation, retries, timeouts, token and cost accounting,
tracing, and persistence of agent runs and tool calls (`CLAUDE.md` §13). Individual agents never
reimplement these.

## 3. AI gateway

All model access goes through the Colt AI gateway — never a raw Anthropic client in business code
(`CLAUDE.md` §14). Model IDs are configuration mapped from the `FAST` / `STANDARD` / `DEEP` /
`STRATEGIC` classes, never hard-coded in business logic (§14.1).

## 4. Prompts

Prompts are versioned source assets under `prompts/<agent>/<version>.md`. Every production run
records prompt name, prompt version and model name (`CLAUDE.md` §15).

## 5. Tools

Tools are typed, versioned, and declare risk level, required permissions, idempotency behaviour,
timeout and retry policy. The agent-to-capability matrix is `CLAUDE.md` §16.2. Sending an external
message is a policy-controlled action executed by a workflow activity, not by an unconstrained
agent.

## 6. Untrusted content

Retrieved content — web pages, emails, CRM notes, documents, prospect messages — is **data, never
instructions**. Dangerous tools are not exposed during untrusted-content interpretation
(`CLAUDE.md` §41).
