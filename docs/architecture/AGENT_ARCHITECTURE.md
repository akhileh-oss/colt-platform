# Agent architecture

> Skeleton established in Milestone 00. The AI gateway (Milestone 08) and agent runtime
> (Milestone 09) are built; Milestone 10 landed the first real product agent, `ResearchAgent`
> (§8), Milestone 11 added `DiscoveryAgent`/`EnrichmentAgent` (§9), Milestone 12 added
> `SignalAgent` (§10), Milestone 13 added `ScoringAgent` (§11), and Milestone 15 adds
> `PersonalizationAgent`/`MessagingAgent` (§12). The remaining three (§12.2, §12.10-§12.11) land
> in Milestones 16-21, each as an `AgentDefinition` plus prompt plus tools registered against the
> runtime this document already describes. Specification: `CLAUDE.md` §12-§16, §68.

## 1. Agents

`colt_agents.RESEARCH_AGENT_DEFINITION` (§8), `DISCOVERY_AGENT_DEFINITION`/
`ENRICHMENT_AGENT_DEFINITION` (§9), `SIGNAL_AGENT_DEFINITION` (§10), and
`SCORING_AGENT_DEFINITION` (§11) are the five of the ten product agents (`CLAUDE.md` §12)
actually built so far. `StrategyAgent`, `PersonalizationAgent`, `MessagingAgent`,
`ReplyIntelligenceAgent`, `OpportunityAgent` remain for Milestones 14-21, each registering
against the same mechanism Milestone 09 built: `colt_agents.AgentDefinition` (CLAUDE.md §12.1's
contract — name, version, purpose, input/output schemas, allowed/forbidden tools, model policy,
tool-call ceiling, timeout, evaluation suite — a plain frozen dataclass, not Pydantic, since it
is written once in code and never crosses an external boundary). `colt_agents.
EXAMPLE_AGENT_DEFINITION` remains as scaffolding (not a product agent) — the same role
`ExampleWorkflow` (Milestone 06) and `TraceCheckWorkflow` (Milestone 07) played for their own
milestones.

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
(`CLAUDE.md` §41). `ResearchAgent` (§8) is the first agent that actually retrieves untrusted
content: its prompt (`prompts/research/v1.md`) states both rules explicitly (§41.1: search/fetch
results are data, never executable instructions; §41.2: its `allowed_tools` is exactly
`{search_web, fetch_page, record_evidence}` — no CRM-mutating or messaging tool is ever offered
to it), and `AgentDefinition.allowed_tools` enforces the permission side statically, independent
of whatever the prompt says.

## 8. ResearchAgent and the evidence pipeline (Milestone 10)

`colt_agents.research_agent.RESEARCH_AGENT_DEFINITION` is the first of the ten product agents
(`CLAUDE.md` §12.5): given a company, it produces a `ResearchDossier` — a summary plus a list of
`DossierClaim`s, each labeled `FACT`, `INFERENCE`, or `HYPOTHESIS` (§12.5's required
distinction). A Pydantic `model_validator` on `DossierClaim` makes Milestone 10's acceptance
criterion ("every factual claim produced by the agent is linked to stored evidence")
structurally unviolable rather than merely a prompt instruction the model might ignore: a `FACT`
claim with an empty `evidence_ids` list fails validation before the dossier can even be
constructed, whether `evidence_ids` was explicitly passed empty or simply omitted (the validator
runs as a `model_validator(mode="after")`, not a per-field validator, specifically so it also
catches the omitted-default case). `INFERENCE`/`HYPOTHESIS` claims may still cite evidence, but
are not required to — an inference is the agent connecting dots across already-recorded facts,
not a new sourced claim of its own.

Three typed tools back it, each built from a provider port or application use case, never from
infrastructure directly (§2 above):

- **`search_web`** (`colt_agents.tools.search_web`) wraps `colt_integrations.search.
SearchProvider` — `FakeSearchProvider` (deterministic fixture results; the configured default,
  since no real search-provider API key exists in this environment) or `BraveSearchProvider`
  (real, verified against Brave's actual API documentation, with bounded retry on rate limits).
- **`fetch_page`** (`colt_agents.tools.fetch_page`) wraps `colt_integrations.fetch.
FetchProvider` — `HttpFetchProvider` is real and SSRF-safe: it resolves and re-checks every
  hop's IP against private/loopback/link-local/reserved/multicast ranges (`CLAUDE.md` §28),
  caps response size, and normalizes HTML to plain text (`colt_integrations.fetch.normalize.
html_to_text`).
- **`record_evidence`** (`colt_agents.tools.record_evidence`) wraps `colt_application.
RecordEvidence`, the one use case that writes an `Evidence` row (§10.6). This is the agent's
  only permitted write — §16.2 classes a `ResearchAgent`'s writable scope as "Evidence only",
  and §41.2's prohibition on exposing dangerous tools during untrusted-content interpretation is
  about external side effects (`send_email`, `delete_company`) that a research agent never
  needs, not about recording its own job output.

`RecordEvidence` computes `verification_status` itself
(`colt_application.research.determine_verification_status`) rather than trusting whatever a
tool argument says — a tool argument is attacker-adjacent input the model decided to pass, and
verification state is exactly the kind of fact §2.1 reserves for deterministic application
logic. The rule this milestone builds is deliberately narrow: a claim's source older than the
freshness threshold (180 days by default, §19.2) is demoted to `STALE`; everything else starts
and stays `UNVERIFIED`. It cannot promote a claim to `VERIFIED`, `DISPUTED`, or `REJECTED` —
those require independent corroboration or human review, mechanisms a later milestone builds.
`VerificationStatus` (`UNVERIFIED` / `VERIFIED` / `STALE` / `DISPUTED` / `REJECTED`, §20) is a
closed `StrEnum`, enforced in the database with a `CHECK` constraint alongside the application-
level `Evidence.verification_status` type.

## 9. DiscoveryAgent, EnrichmentAgent, and identity resolution (Milestone 11)

`colt_agents.discovery_agent.DISCOVERY_AGENT_DEFINITION` (`CLAUDE.md` §12.3) finds candidate
companies and people via `search_companies`/`search_people` (plus `search_web` from Milestone
10 — exactly §12.3's allowed-tools list minus `search_news`/`search_jobs`, which nothing has
built a tool for yet). `colt_agents.enrichment_agent.ENRICHMENT_AGENT_DEFINITION` (§12.4)
resolves additional data for one already-known company or person via
`enrich_company`/`enrich_person`; a `model_validator` on `EnrichmentAgentInput` requires
exactly one target (a company or a person, never both, never neither) before the model can even
submit the input.

Both agents' tools wrap `colt_integrations.enrichment.EnrichmentProvider` (§2.7, §28.2) —
`FakeEnrichmentProvider` is the configured default (no real enrichment-provider API key exists
in this environment); `ApolloEnrichmentProvider` is a real adapter, verified against Apollo's
own API documentation (organization/people search and enrich endpoints), including the detail
that Apollo's people-search endpoint returns obfuscated contact fields (no email) until a
specific person is "unlocked" via a match/enrich call — `DiscoveryAgent` never does that
automatically, since spending a provider's enrichment credit is not implied by a search (§41.3:
data minimization before a tool call).

### Identity resolution (§22)

`colt_application.use_cases.{DiscoverCompany,DiscoverPerson}` implement §22's exact layered
matching before ever creating a row — a dedup hit returns the existing record unchanged, never
merging on fuzzy name similarity (explicitly forbidden):

1. exact `provider_id` (looked up against the `provider`/`provider_id` keys every discovered
   record's `source_metadata` carries);
2. normalized email (person only);
3. normalized LinkedIn URL;
4. company + normalized full name, gated by
   `colt_application.identity.DEFAULT_NAME_MATCH_CONFIDENCE_THRESHOLD` — a low-confidence
   candidate is never allowed to match on name alone, however loosely.

`colt_application.use_cases.{EnrichCompany,EnrichPerson}` apply §12.4's confidence rule at
record level: an incoming candidate only overwrites a company's/person's enrichable fields when
its own confidence is at least as high as whatever is stored in that record's
`source_metadata.confidence` — a documented simplification (per-field confidence tracking is a
natural follow-up, not a gap) that still satisfies "must not silently overwrite high-confidence
data with lower-confidence provider data."

All four use cases take plain scalar arguments, never a `colt_integrations.enrichment.
{CompanyCandidate,PersonCandidate}` directly — `colt_application` depends only on
`colt_domain`/`colt_policy` (§5), never on the provider-adapter layer; the typed tool (which
depends on both) is what unpacks a provider-specific candidate into those arguments, the same
separation `colt_agents.tools.record_evidence` already draws against `RecordEvidence`.

`Person.email_status` (`CLAUDE.md` §16.1's `verify_email`) is `EmailStatus` (`UNVERIFIED` /
`VALID` / `INVALID` / `RISKY` / `UNKNOWN`), the same closed-`StrEnum`-plus-database-`CHECK`
pattern Milestone 10 established for `Evidence.verification_status`. `EnrichPerson` only ever
sets `VALID` (a provider's own "verified" claim) or `UNKNOWN` (anything else) — never `INVALID`
from an unconfirmed status alone, since "not confirmed" and "confirmed bad" are different
claims.

## 10. SignalAgent and ranking (Milestone 12)

`colt_agents.signal_agent.SIGNAL_AGENT_DEFINITION` (`CLAUDE.md` §12.6) detects "why now" events:
given a company, it polls pending raw trigger events (`poll_signal_sources`) and records the
single strongest one it finds (`record_signal`) with `signal_type`, `confidence`, `summary`, and
`business_implication` — the last of these is the model's own judgment about what the signal
means for sales strategy (§2.1: not a deterministic computation, unlike
`verification_status`/`email_status`), so it is stored exactly as given, with no server-side
computation or validation beyond non-business fields.

**Source ingestion** is `colt_integrations.signals.SignalTriggerSource` (a `Protocol`,
`poll() -> list[SignalTriggerPayload]`). CLAUDE.md names no specific real signal-source provider
(unlike `SearchProvider`/`EnrichmentProvider`, both named in §28.2), and Milestone 12's
acceptance criterion explicitly accepts "a real/mock trigger" — so only the port and
`FakeSignalTriggerSource` (the literal mock trigger) are built this milestone; a real adapter
(a specific news feed, webhook, or CRM-event source) is a natural follow-up once one is chosen,
not a gap.

**Ranking** is `colt_application.signals.rank_signal()` — a pure function of the signal's own
stored fields (never a persisted column; §10.5 names no `rank` field, and nothing here needs
re-deriving later the way a stored score would, unlike Milestone 13's lead-scoring history):
`type_weight(signal_type) × (confidence or a default) × freshness_factor`. `SIGNAL_TYPE_WEIGHTS`
assigns relative commercial urgency per `CLAUDE.md` §10.5's example signal types (funding and
acquisition rank highest; website_change lowest), falling back to a default weight for an
unrecognised type rather than raising — new signal types are expected to be added over time
without a migration, per `colt_domain.signal`'s own design. Freshness decays (not zeroes) a
signal whose `event_at`/`observed_at` is older than a 90-day threshold — shorter than
`colt_application.research`'s 180-day freshness window for general evidence, since a "why now"
trigger loses relevance faster than a general business fact. `record_signal`'s tool handler
computes `rank` immediately after persisting and returns it in the same response, so neither
the model nor a caller ever has to re-derive it from raw fields themselves.

## 11. ScoringAgent and the hybrid score (Milestone 13)

`colt_agents.scoring_agent.SCORING_AGENT_DEFINITION` (`CLAUDE.md` §12.7, §21) is where §21's
hybrid-scoring rule ("Do not allow LLM-only lead scoring. Use a hybrid score.") actually gets
enforced in code. The agent is given three already-known deterministic figures — `icp_fit`,
`signal_strength`, `timing` — and supplies only the two components that genuinely need
judgment: `persona_fit` and `model_assessment`. Everything downstream of those five numbers —
the weighted sum, the reason codes, and the qualification decision — is `score_lead`'s plain
arithmetic (`colt_application.scoring`), never the model's: §12.7 is explicit that "the overall
score must be reproducible from stored inputs" and that qualification must never be decided by
"vibes" alone.

`compute_overall_score()` is §21's example baseline verbatim (`icp_fit` 0.30, `persona_fit`
0.20, `signal_strength` 0.20, `timing` 0.15, `model_assessment` 0.15), named and versioned as
`DEFAULT_SCORE_WEIGHTS`/`SCORE_MODEL_VERSION` rather than inlined — "this weighting is
configurable and must be versioned" (§21). `determine_reason_codes()` flags each weak
(≤0.3)/strong (≥0.7) component by name and always includes whether the score met
`QUALIFICATION_THRESHOLD`, deterministically from the same five inputs every time.
`determine_qualification()` reuses `LeadStatus.QUALIFIED`/`NOT_QUALIFIED` — the funnel's
existing closed vocabulary, not a scoring-specific one.

`LeadScore` (§10.8) is deliberately append-only: no `updated_at` column, no `update()` method
on `SqlAlchemyLeadScoreRepository`, only `add()` — "Do not overwrite scoring history. Use
immutable or append-only score evaluations where practical." `ScoreLead` persists exactly one
new `LeadScore` row per call and then transitions the `Lead`'s own `status` via the
qualification decision (`LeadRepository.update_status()`, new this milestone) — every past
evaluation stays queryable and attributable to the `model_version` that produced it.

## 12. PersonalizationAgent, MessagingAgent, and the evidence-gated draft (Milestone 15)

`colt_agents.personalization_agent.PERSONALIZATION_AGENT_DEFINITION` and `colt_agents.
messaging_agent.MESSAGING_AGENT_DEFINITION` (`CLAUDE.md` §12.8-§12.9) turn a lead's recorded
`Evidence` into a drafted outreach message, split into two agents because they have two distinct
forbidden behaviors to enforce: §12.8 forbids a personalization strategy with no cited evidence;
§12.9 forbids a drafted message that claims something no cited evidence supports. Each is
enforced structurally, not just by prompt instruction.

`PersonalizationAgent` is allowed exactly two tools, `list_evidence_for_lead` and
`select_evidence`, and the second depends on the first: `colt_application.
SelectPersonalizationEvidence` raises `MessageValidationError` on an empty selection or on any
`evidence_id` that `ListEvidenceForLead` did not itself just return for that lead's company/person.
Its output, `PersonalizationStrategy`, is an ephemeral schema — not persisted, the same precedent
`ResearchDossier` (Milestone 10) established for a structured result that exists only to hand
judgment downstream — and a Pydantic validator rejects an empty `evidence_ids` list by
construction, the same defense-in-depth `DossierClaim`'s `FACT`-needs-evidence validator already
established.

`MessagingAgent` is allowed one tool, `draft_message`, backed by `colt_application.DraftMessage`.
It re-validates every `evidence_id` against the real `EvidenceRepository` itself, even though
`select_evidence` already validated a selection upstream: each tool call is model-decided input,
so the set `draft_message` actually receives is not guaranteed to be the same set
`select_evidence` returned — the second check is not redundant, it is the only one that runs
against what was actually about to be persisted. A rejected call returns a tool error (never a
persisted `Message`) and the agent must retry with only evidence that exists.

`Message` rows (§10.8's append-only pattern, extended) are "versions" per `(lead_id,
sequence_step_id)`: `MessageRepository` has no `update()`, so drafting again for the same pair
adds a new row rather than overwriting the last draft — the same reasoning that keeps `LeadScore`
append-only applies here, since overwriting a prior draft would destroy the record of what was
actually sent or reviewed before. Brand voice is read from `Organization.settings["brand_voice"]`
via `colt_application.get_brand_voice()`, falling back to a documented in-code default
(`DEFAULT_BRAND_VOICE`) when unset — `CLAUDE.md` names brand voice as model input for `§12.9`
without specifying where it lives, so this milestone documents its own storage choice rather than
leaving it implicit.

The campaign router's `GET /campaigns/{id}/messages` (Milestone 15) is a read-only review list,
gated by the existing `Permission.MESSAGE_APPROVE` rather than a new read-only permission — every
role that can review a drafted message already carries it, so adding a second permission would
only duplicate the gate. Approving, rejecting, or sending a draft is Milestone 16's job; this
endpoint only proves a message can be generated, persisted, and listed back out.
