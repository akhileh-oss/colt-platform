# colt-application

Use cases and application services coordinating domain objects and ports.

Ports (`colt_application.ports`) are `typing.Protocol`s, not `colt-db` imports — its concrete
repositories satisfy them structurally. `GetLead` is the use case `colt-agents`' `get_lead` tool
calls, realising `CLAUDE.md` §2.3's required path: Typed Tool → Application Service → Repository
→ PostgreSQL.

`colt_application.research.determine_verification_status()` is deterministic source-freshness
logic (CLAUDE.md §19.2, §2.1): it demotes a claim to `STALE` once its source is older than the
freshness threshold, but cannot promote one to `VERIFIED`/`DISPUTED`/`REJECTED` — those require
independent corroboration or human review, mechanisms a later milestone builds. `RecordEvidence`
is the one use case that writes an `Evidence` row (§10.6, §20); it computes
`verification_status` itself rather than trusting a caller-supplied value, since a tool argument
is attacker-adjacent model-decided input. `colt-agents`' `record_evidence` tool is the only
caller.

`colt_application.identity` (CLAUDE.md §22) holds deterministic normalization (`normalize_domain`/
`normalize_email`/`normalize_linkedin_url`/`normalize_name`) and
`DEFAULT_NAME_MATCH_CONFIDENCE_THRESHOLD`. `DiscoverCompany`/`DiscoverPerson` apply §22's exact
layered matching (provider ID, then email/LinkedIn URL, then confidence-gated name) before ever
creating a row — never on fuzzy name similarity. `EnrichCompany`/`EnrichPerson` apply §12.4's
confidence rule: an incoming candidate only overwrites a record's fields when its own
confidence is at least as high as what is already stored. All four take plain scalar
arguments, never a `colt_integrations.enrichment` candidate object directly — this package
depends only on `colt_domain`/`colt_policy`, never on the provider-adapter layer.

`colt_application.signals.rank_signal()` (CLAUDE.md §12.6) is deterministic signal scoring: a
pure function of `signal_type` (weighted by commercial urgency), `confidence`, and freshness
decay (a shorter window than `research`'s, since a "why now" trigger loses relevance faster) —
not a persisted column, reproducible from a `Signal` row's own fields alone. `RecordSignal`
(the one use case `record_signal` calls) is a thinner wrapper than `RecordEvidence`:
`signal_type`/`confidence`/`business_implication` are the model's own judgment, so nothing here
is server-computed beyond persistence itself.

`colt_application.scoring` (CLAUDE.md §21, §12.7) is the hybrid-score arithmetic: `compute_
overall_score()` is §21's weighted baseline, named and versioned (`DEFAULT_SCORE_WEIGHTS`/
`SCORE_MODEL_VERSION`); `determine_reason_codes()` and `determine_qualification()` are equally
deterministic, the latter reusing `LeadStatus.QUALIFIED`/`NOT_QUALIFIED` rather than a
scoring-specific vocabulary. `ScoreLead` persists one new, immutable `LeadScore` row (§10.8:
"Do not overwrite scoring history") and transitions the `Lead`'s own status accordingly.

`colt_application.campaign_state` (CLAUDE.md §10.9, Milestone 14) is a closed state machine
CLAUDE.md itself never defines for Campaign — §11 covers Lead/Conversation/Opportunity but is
silent on Campaign, so this milestone's own Build list item ("campaign state machine") and
acceptance criterion are the specification. `can_transition()` is the deterministic transition
table (`DRAFT → ACTIVE`, `ACTIVE ⇄ PAUSED`, `ACTIVE`/`PAUSED`/`COMPLETED → ARCHIVED`);
`validate_campaign_definition()` checks a target-audience definition, at least one channel, a
schedule and limits are all present, returning every failing rule rather than just the first.
`CreateCampaign`/`GetCampaign`/`ListCampaigns`/`ValidateCampaign`/`PauseCampaign`/
`ResumeCampaign` are the six use cases realizing "created, validated, paused, resumed, and
inspected." A campaign always starts `DRAFT` (the `CampaignRepository.add()` port does not even
accept a caller-supplied status); `ValidateCampaign` and `ResumeCampaign` both reach `ACTIVE` but
require the campaign be specifically `DRAFT` or `PAUSED` respectively — not merely that
`can_transition()` allows the move — since `DRAFT` and `PAUSED` both reach `ACTIVE` in the
transition table, and letting either use case accept both would let `ResumeCampaign` resurrect
an unvalidated draft, or `ValidateCampaign` re-run checks against an already-launched campaign.

`AddSequenceStep`/`ListSequenceSteps` (CLAUDE.md §10.10, Milestone 14) close a gap this
milestone's own build caught on review: CLAUDE.md defines a full `SequenceStep` entity and
Milestone 14's Build list names "sequence steps" as its own deliverable, separate from
Campaign's `channels` list — initially missed, fixed in the same PR rather than deferred. Both
use cases check the parent campaign exists in this organization first, so an unknown
`campaign_id` surfaces as the same `NotFoundError` every other use case raises for a missing
parent, not a raw database `IntegrityError` or a silently-empty list.

`ListEvidenceForLead`/`SelectPersonalizationEvidence`/`DraftMessage`/`ListMessages` (CLAUDE.md
§12.8-§12.9, Milestone 15) back the `PersonalizationAgent`/`MessagingAgent` pipeline.
`SelectPersonalizationEvidence` raises `MessageValidationError` on an empty selection or on any
`evidence_id` `ListEvidenceForLead` did not itself just return — the §12.8 "no unsupported
personalization" rule enforced as a checked precondition, not a prompt instruction.
`DraftMessage` re-runs that same validation against the real `EvidenceRepository` before calling
`MessageRepository.add()`, since the evidence ids a tool call actually receives are model-decided
input, not guaranteed to be the exact set a prior tool call already checked. `Message` rows are
append-only "versions" per `(lead_id, sequence_step_id)` — the same reasoning that keeps
`LeadScore` (§10.8) append-only: drafting again for the same pair adds a row, never overwrites
one. `get_brand_voice()`/`DEFAULT_BRAND_VOICE` read `Organization.settings["brand_voice"]` with a
documented in-code fallback — CLAUDE.md names brand voice as model input for §12.9 without
specifying its storage, so this is this milestone's own documented design decision.

`DecideMessageApproval`/`AddSuppressionEntry`/`SendMessage` (CLAUDE.md §17, §10.17-§10.18,
Milestone 16) are the policy + approval system. `SendMessage` gathers an `OutboundSendContext`
from its own ports and calls `colt_policy.evaluate_outbound_send()`; it raises
`PolicyDeniedError` _instead of_ calling `MessageSender.send` on anything but `ALLOW` — never
after — which is the literal mechanism behind this milestone's acceptance criterion, "a policy
violation cannot result in an external message send." `DecideMessageApproval` lazily creates
the `Approval` row representing a message's standing approval request the first time a
decision is made (CLAUDE.md names no separate request step), and only an approval — never a
rejection — moves the lead from `PENDING_APPROVAL` to `READY`. `auto_approval_enabled` is a
plain boolean parameter on `SendMessage`, not a config read: this package cannot depend on
`colt_config` (§5's layering), so whether the `ENABLE_AUTO_APPROVAL` feature flag (§51) is on is
the caller's (the API layer's) job to resolve and pass in as data, the same as every other use
case here taking plain scalar arguments.

`ProcessInboundEmail`/`ProcessBounce`/`UnsubscribeByToken` (CLAUDE.md §29, §10.18, Milestone 17)
are the email subsystem's application layer. `ConversationRepository`/`ConversationEventRepository`
(§10.12-§10.13) are this milestone's own new ports — `SqlAlchemyConversationRepository` has
existed since Milestone 05, and `ConversationEvent` is named in §10.5, but no use case needed
either until now. `ProcessInboundEmail` resolves a reply's `In-Reply-To` back to the `Message`
it answers via `MessageRepository.get_by_provider_message_id` (also new), threads it onto that
lead's email `Conversation` (creating one if this is the lead's first reply), and appends a
`message_received` event — deliberately not classifying what the reply means, which is
`ReplyIntelligenceAgent`'s job (Milestone 19). `ProcessBounce` and `UnsubscribeByToken` both
drive `AddSuppressionEntry` (Milestone 16's mechanism, reused rather than duplicated) and
terminate the lead's open conversation (`ConversationRepository.update_state`, this milestone's
own addition to that port); `ProcessBounce` also marks the person's email `INVALID`, and
`UnsubscribeByToken` moves the `Lead` to the terminal `UNSUBSCRIBED` status. `SendMessage` itself
gained the idempotency-key claim §24.4/§29.2 actually asks for: the key
(`campaign_id:lead_id:sequence_step_id`) is computed and checked against every message sharing
that slot, then claimed only at successful send time via `update_send_result` — claiming it
earlier, at draft time, would violate the database's own partial unique index the first time a
second drafted version of the same lead/step existed. `MessageSender.send` gained a `recipient:
Person` parameter (a port Milestone 16 authored, amended here since its PR was still open) — a
real channel adapter needs the recipient's address, which `SendMessage` already resolves.

`colt_application.reply_classification.determine_conversation_transition` (CLAUDE.md §11.2,
§12.10, §23.1, Milestone 19) is the "model judges, code decides" split `ScoringAgent`'s own
`score_lead` already established, applied to conversation state: `ReplyIntelligenceAgent`
recommends a transition, but a HIGH-urgency reply always produces `HUMAN_HANDOFF` regardless of
what was recommended, and a terminal conversation (`UNSUBSCRIBED`/`HUMAN_HANDOFF`) never moves
again from a later reply — two rules no model call can override, which is what makes "high-
intent replies produce the correct handoff" hold deterministically rather than depend on the
model remembering to ask for a handoff itself. `RecordReplyClassification` is the one write
`ReplyIntelligenceAgent`'s tool calls: it applies that transition, records a `reply_classified`
`ConversationEvent` carrying every §12.10 field plus a suggested response (read by a human,
never auto-sent — "suggested response generation" is a Build item, not a send path), and, only
when the transition actually lands on `HUMAN_HANDOFF`, a second, distinct `handoff_created`
event — §10.13 lists both as their own event types.

`RecordCrmSyncOutcome` (CLAUDE.md §30, Milestone 20) upserts a `CrmSyncRecord` by
`(entity_type, entity_id, provider_name)` from a sync attempt's result, mirroring
`RecordReplyClassification`'s role: pure persistence logic, no I/O against the external CRM
provider itself (that belongs to the Temporal activity, the composition root that owns the
actual provider call). `OpportunityRepository` (a new port — Milestone 20 is the first caller
that needs to read an `Opportunity` from the application layer) is a plain `Protocol` matching
`SqlAlchemyOpportunityRepository`'s existing `add()`/`get()` shape.

`colt_application.opportunity_state.OPPORTUNITY_TRANSITIONS` (CLAUDE.md §11.3, Milestone 21) is
this milestone's own documented transition table — CLAUDE.md names the pipeline's seven stages
but not which moves between them are legal, the same gap `campaign_state.py` already fills for
Campaign: a straight line `QUALIFIED` -> ... -> `WON`, `LOST` reachable from any non-terminal
stage, neither terminal stage ever reopening. `TransitionOpportunityStage` is the one use case
that actually changes a row's stage, raising `InvalidOpportunityTransitionError` for anything
the table forbids. `CreateOrUpdateOpportunity` is the literal mechanism behind "positive
conversations can become auditable opportunities without duplicate creation" (Milestone 21's
acceptance criterion): at most one open (non-`WON`/`LOST`) `Opportunity` per `company_id` — a
second call for an already-tracked company updates the existing row (only gaining a value it
didn't have) rather than creating a duplicate. `AssignOpportunityOwner` validates a given
`owner_id` against the tenant-scoped `UserRepository` before writing it — a cross-tenant or
nonexistent id raises the same `NotFoundError` every other use case raises for a missing
reference. `colt_application.pipeline_summary.summarize_pipeline`/`colt_application.
revenue_attribution.summarize_revenue_by_source` are pure, stateless aggregations over
`Opportunity` rows (the same shape `colt_application.signals.rank_signal` already establishes)
backing the pipeline dashboard and closed-won revenue attribution — grouped by `source`, this
milestone's own documented design call for a Build item CLAUDE.md names without a mechanism.

Milestone 22 (CLAUDE.md §68) adds eight read-only report modules — `funnel`, `icp_performance`,
`trigger_performance`, `message_performance`, `channel_performance`, `agent_cost`,
`model_performance` (plus Milestone 21's own `revenue_attribution`, reused unchanged) — each a
pure `summarize_*(rows...) -> list[SomeRow]` function, the same shape `signals.rank_signal`
already establishes: never persisted, always reproducible from the rows passed in. Three of
CLAUDE.md's named dimensions have no stored field anywhere in this codebase, so this package
makes three documented proxy calls: `Company.industry` stands in for "segment" (`icp_
performance.py`), `Message.prompt_version` for "message variant," and `Person.seniority`
(resolved through `Lead.person_id`) for "persona" — the latter two folded into one
`message_performance.py` module since CLAUDE.md's acceptance criterion names "personas" with no
dedicated Build item for it.

Each new analytics `Protocol` lives in its own `ports/analytics.py` — a `list_all()`-only reader
per entity (`LeadAnalyticsReader`, `CompanyAnalyticsReader`, etc.) — rather than adding
`list_all()` to the existing `LeadRepository`/`CompanyRepository`/etc. ports. The first attempt
did widen those existing ports directly; because `Protocol` conformance is structural, every
other use case's `Fake*Repository` test double across the codebase immediately stopped
satisfying its own constructor's `Protocol` type the moment that `Protocol` gained a method the
fake didn't implement, breaking mypy in over twenty unrelated test files. **Never widen an
existing, widely-depended-on `Protocol` for one new, narrow need — define a new, separate
`Protocol` instead**, the same concrete class satisfying both without either ever touching the
other.

`ValidateCampaign`, `PauseCampaign`, and `ResumeCampaign` (CLAUDE.md §48, Milestone 24) now each
take an `AuditLogRepository` and an `actor_id: UUID`, writing one `AuditLog` row
(`campaign_launched`/`campaign_paused`/`campaign_resumed`) after a successful state transition,
closing the two campaign-lifecycle audit gaps a security audit found still missing (message
approval, message send, and suppression were already wired). This codebase has no use case
separately named "launch" — a `DRAFT` campaign's `ValidateCampaign` call *is* its launch, the
only way a campaign ever first reaches `ACTIVE` — and `ResumeCampaign` is audited the same way,
since §48 treats resuming as the same kind of action as launching.

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering, and `CLAUDE.md` §5 for the layer rules it must obey.
