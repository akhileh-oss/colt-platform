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

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering, and `CLAUDE.md` §5 for the layer rules it must obey.
