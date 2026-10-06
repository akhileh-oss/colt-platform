"""Activities behind `LeadOutreachWorkflow` (CLAUDE.md §24.3, Milestone 18).

Each activity is a thin composition root, exactly like `send_email_activity` (Milestone 17):
it opens its own tenant-scoped session, wires the real `colt_application`/`colt_agents`/
`colt_integrations` pieces, and does nothing the workflow itself could not have asked any one of
those packages to do directly. The workflow orchestrates; these activities are where every
side effect (DB, HTTP, the Anthropic API) actually happens (§24.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from colt_agents import AgentRuntime, ToolRegistry
from colt_agents.errors import AgentError, AgentTimeoutError
from colt_agents.messaging_agent import (
    MESSAGING_AGENT_DEFINITION,
    MessagingAgentInput,
    MessagingAgentOutput,
)
from colt_agents.personalization_agent import (
    PERSONALIZATION_AGENT_DEFINITION,
    PersonalizationAgentInput,
    PersonalizationStrategy,
)
from colt_agents.prompts import load_prompt
from colt_agents.research_agent import (
    RESEARCH_AGENT_DEFINITION,
    ResearchAgentInput,
    ResearchDossier,
)
from colt_agents.tools import (
    build_draft_message_tool,
    build_fetch_page_tool,
    build_list_evidence_for_lead_tool,
    build_record_evidence_tool,
    build_search_web_tool,
    build_select_evidence_tool,
)
from colt_ai import AnthropicGateway
from colt_ai.errors import GatewayError
from colt_application import RecordEvidence
from colt_application.brand_voice import get_brand_voice
from colt_application.research import DEFAULT_FRESHNESS_THRESHOLD_DAYS
from colt_application.use_cases.draft_message import DraftMessage
from colt_application.use_cases.list_evidence_for_lead import ListEvidenceForLead
from colt_application.use_cases.select_personalization_evidence import (
    SelectPersonalizationEvidence,
)
from colt_config import get_settings
from colt_db import get_default_engine, make_session_factory
from colt_db.repositories import (
    SqlAlchemyAgentRunRepository,
    SqlAlchemyCampaignRepository,
    SqlAlchemyCompanyRepository,
    SqlAlchemyConversationRepository,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyLeadRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyOrganizationRepository,
    SqlAlchemyPersonRepository,
    SqlAlchemySequenceStepRepository,
    SqlAlchemySuppressionRepository,
    SqlAlchemyToolCallRepository,
)
from colt_domain import Evidence, LeadStatus
from colt_integrations.fetch.http import HttpFetchProvider
from colt_integrations.search.brave import BraveSearchProvider
from colt_integrations.search.fake import FakeSearchProvider
from colt_observability import get_logger

logger = get_logger(__name__)

#: §11.1's progression: a lead must have passed qualification to be worth outreach, and must not
#: be in a terminal/stop state (`NOT_QUALIFIED`/`NOT_INTERESTED`/`UNSUBSCRIBED`/`SUPPRESSED`/
#: `NURTURE`/`CONVERTED`) — the workflow's own "validate qualification" step.
_ELIGIBLE_LEAD_STATUSES = frozenset(
    {
        LeadStatus.QUALIFIED,
        LeadStatus.PERSONALIZED,
        LeadStatus.PENDING_APPROVAL,
        LeadStatus.READY,
        LeadStatus.CONTACTED,
        LeadStatus.ENGAGED,
    }
)


@dataclass(frozen=True)
class LoadOutreachStateInput:
    organization_id: str
    lead_id: str
    campaign_id: str


@dataclass(frozen=True)
class OutreachState:
    eligible: bool
    ineligible_reason: str | None
    needs_research: bool
    company_id: str
    company_name: str
    company_domain: str
    person_id: str
    person_name: str
    next_sequence_step_id: str | None
    next_sequence_step_channel: str | None
    next_sequence_step_message_strategy: str | None
    next_sequence_step_delay_minutes: int
    sequence_exhausted: bool


def _needs_research(evidence: list[Evidence], *, now: datetime) -> bool:
    """ "Research if stale/missing" (§24.3) — missing means no evidence at all; stale reuses the
    same freshness threshold `colt_application.research` already defines for individual claims,
    applied here to the company's most recently observed evidence as a whole."""
    if not evidence:
        return True
    most_recent = max(item.observed_at for item in evidence)
    return (now - most_recent).days > DEFAULT_FRESHNESS_THRESHOLD_DAYS


@activity.defn
async def load_outreach_state_activity(input: LoadOutreachStateInput) -> OutreachState:
    organization_id = UUID(input.organization_id)
    lead_id = UUID(input.lead_id)
    campaign_id = UUID(input.campaign_id)

    factory = make_session_factory(get_default_engine())
    async with factory() as session:
        leads = await SqlAlchemyLeadRepository.create(session, organization_id)
        lead = await leads.get(lead_id)
        if lead is None:
            raise ApplicationError(
                f"No lead {lead_id} in organization {organization_id}.", non_retryable=True
            )

        campaigns = SqlAlchemyCampaignRepository(session, organization_id)
        campaign = await campaigns.get(campaign_id)
        if campaign is None:
            raise ApplicationError(f"No campaign {campaign_id}.", non_retryable=True)

        companies = SqlAlchemyCompanyRepository(session, organization_id)
        company = await companies.get(lead.company_id)
        persons = SqlAlchemyPersonRepository(session, organization_id)
        person = await persons.get(lead.person_id)
        if company is None or person is None:
            raise ApplicationError(
                f"Lead {lead_id} has no resolvable company/person.", non_retryable=True
            )

        suppressions = SqlAlchemySuppressionRepository(session, organization_id)
        is_suppressed = (
            await suppressions.is_suppressed("email", person.email) if person.email else False
        )

        ineligible_reason: str | None = None
        if is_suppressed or lead.status in (LeadStatus.UNSUBSCRIBED, LeadStatus.SUPPRESSED):
            ineligible_reason = "suppressed"
        elif lead.status not in _ELIGIBLE_LEAD_STATUSES:
            ineligible_reason = f"lead status {lead.status.value} is not eligible for outreach"
        elif campaign.status.value != "ACTIVE":
            ineligible_reason = "campaign is not ACTIVE"

        evidence_repo = SqlAlchemyEvidenceRepository(session, organization_id)
        company_evidence = await evidence_repo.list_by_entity("Company", company.id)
        needs_research = _needs_research(company_evidence, now=datetime.now(UTC))

        sequence_steps = SqlAlchemySequenceStepRepository(session, organization_id)
        steps = sorted(
            (s for s in await sequence_steps.list_by_campaign(campaign_id) if s.active),
            key=lambda s: s.step_order,
        )
        messages = SqlAlchemyMessageRepository(session, organization_id)
        campaign_messages = await messages.list_by_campaign(campaign_id)
        sent_step_ids = {
            m.sequence_step_id
            for m in campaign_messages
            if m.lead_id == lead_id and m.status == "SENT" and m.sequence_step_id is not None
        }
        next_step = next((s for s in steps if s.id not in sent_step_ids), None)

        return OutreachState(
            eligible=ineligible_reason is None,
            ineligible_reason=ineligible_reason,
            needs_research=needs_research,
            company_id=str(company.id),
            company_name=company.name,
            company_domain=company.domain or "",
            person_id=str(person.id),
            person_name=person.full_name,
            next_sequence_step_id=str(next_step.id) if next_step else None,
            next_sequence_step_channel=next_step.channel if next_step else None,
            next_sequence_step_message_strategy=next_step.message_strategy if next_step else None,
            next_sequence_step_delay_minutes=next_step.delay_after_previous if next_step else 0,
            sequence_exhausted=next_step is None,
        )


@dataclass(frozen=True)
class ResearchCompanyInput:
    organization_id: str
    company_id: str
    company_name: str
    company_domain: str


@dataclass(frozen=True)
class ResearchCompanyOutput:
    claims_recorded: int


@activity.defn
async def research_company_activity(input: ResearchCompanyInput) -> ResearchCompanyOutput:
    settings = get_settings()
    organization_id = UUID(input.organization_id)
    info = activity.info()

    factory = make_session_factory(get_default_engine())
    async with factory() as session:
        evidence_repo = await SqlAlchemyEvidenceRepository.create(session, organization_id)
        agent_runs = SqlAlchemyAgentRunRepository(session, organization_id)
        tool_calls = SqlAlchemyToolCallRepository(session, organization_id)

        search_provider = (
            BraveSearchProvider(settings.search)
            if settings.search.provider == "brave"
            else FakeSearchProvider()
        )
        registry = ToolRegistry()
        registry.register(build_search_web_tool(search_provider))
        registry.register(build_fetch_page_tool(HttpFetchProvider(settings.security)))
        registry.register(build_record_evidence_tool(RecordEvidence(evidence_repo)))

        runtime = AgentRuntime(
            AnthropicGateway(settings.anthropic), registry, agent_runs, tool_calls
        )
        try:
            dossier = await runtime.run(
                RESEARCH_AGENT_DEFINITION,
                input=ResearchAgentInput(
                    company_id=UUID(input.company_id),
                    company_name=input.company_name,
                    company_domain=input.company_domain,
                ),
                system_prompt=load_prompt("research", "v1"),
                prompt_version="v1",
                workflow_id=info.workflow_id,
                workflow_run_id=info.workflow_run_id,
                entity_type="Company",
                entity_id=UUID(input.company_id),
            )
        except GatewayError as exc:
            raise ApplicationError(str(exc), non_retryable=not exc.retryable) from exc
        except AgentError as exc:
            raise ApplicationError(
                str(exc), non_retryable=not isinstance(exc, AgentTimeoutError)
            ) from exc

        assert isinstance(dossier, ResearchDossier)  # noqa: S101 - guards an internal contract
        # `AgentDefinition.output_schema` already guarantees.
        await session.commit()
        return ResearchCompanyOutput(claims_recorded=len(dossier.claims))


@dataclass(frozen=True)
class DraftNextMessageInput:
    organization_id: str
    lead_id: str
    campaign_id: str
    sequence_step_id: str
    channel: str
    message_strategy: str
    company_name: str
    person_name: str


@dataclass(frozen=True)
class DraftNextMessageOutput:
    message_id: str


@activity.defn
async def draft_next_message_activity(input: DraftNextMessageInput) -> DraftNextMessageOutput:
    settings = get_settings()
    organization_id = UUID(input.organization_id)
    lead_id = UUID(input.lead_id)
    info = activity.info()

    factory = make_session_factory(get_default_engine())
    async with factory() as session:
        leads = await SqlAlchemyLeadRepository.create(session, organization_id)
        lead = await leads.get(lead_id)
        if lead is None:
            raise ApplicationError(f"No lead {lead_id}.", non_retryable=True)

        evidence_repo = SqlAlchemyEvidenceRepository(session, organization_id)
        messages = SqlAlchemyMessageRepository(session, organization_id)
        agent_runs = SqlAlchemyAgentRunRepository(session, organization_id)
        tool_calls = SqlAlchemyToolCallRepository(session, organization_id)
        organizations = SqlAlchemyOrganizationRepository(session)
        organization = await organizations.get(organization_id)
        if organization is None:
            raise ApplicationError(f"No organization {organization_id}.", non_retryable=True)

        gateway = AnthropicGateway(settings.anthropic)

        personalization_registry = ToolRegistry()
        personalization_registry.register(
            build_list_evidence_for_lead_tool(ListEvidenceForLead(leads, evidence_repo))
        )
        personalization_registry.register(
            build_select_evidence_tool(SelectPersonalizationEvidence(evidence_repo))
        )
        personalization_runtime = AgentRuntime(
            gateway, personalization_registry, agent_runs, tool_calls
        )
        try:
            strategy_output = await personalization_runtime.run(
                PERSONALIZATION_AGENT_DEFINITION,
                input=PersonalizationAgentInput(
                    lead_id=lead_id, company_name=input.company_name, person_name=input.person_name
                ),
                system_prompt=load_prompt("personalization", "v1"),
                prompt_version="v1",
                workflow_id=info.workflow_id,
                workflow_run_id=info.workflow_run_id,
                entity_type="Lead",
                entity_id=lead_id,
            )
            assert isinstance(strategy_output, PersonalizationStrategy)  # noqa: S101 - guards
            # an internal contract `AgentDefinition.output_schema` already guarantees.

            messaging_registry = ToolRegistry()
            messaging_registry.register(
                build_draft_message_tool(DraftMessage(messages, evidence_repo))
            )
            messaging_runtime = AgentRuntime(gateway, messaging_registry, agent_runs, tool_calls)
            draft_output = await messaging_runtime.run(
                MESSAGING_AGENT_DEFINITION,
                input=MessagingAgentInput(
                    lead_id=lead_id,
                    campaign_id=UUID(input.campaign_id),
                    channel=input.channel,
                    angle=strategy_output.angle,
                    business_relevance=strategy_output.business_relevance,
                    evidence_ids=strategy_output.evidence_ids,
                    sequence_step_id=UUID(input.sequence_step_id),
                    brand_voice=get_brand_voice(organization),
                ),
                system_prompt=load_prompt("messaging", "v1"),
                prompt_version="v1",
                workflow_id=info.workflow_id,
                workflow_run_id=info.workflow_run_id,
                entity_type="Lead",
                entity_id=lead_id,
            )
        except GatewayError as exc:
            raise ApplicationError(str(exc), non_retryable=not exc.retryable) from exc
        except AgentError as exc:
            raise ApplicationError(
                str(exc), non_retryable=not isinstance(exc, AgentTimeoutError)
            ) from exc

        assert isinstance(draft_output, MessagingAgentOutput)  # noqa: S101 - same guarantee
        # as above, via `AgentDefinition.output_schema`.
        await session.commit()
        return DraftNextMessageOutput(message_id=str(draft_output.message_id))


@dataclass(frozen=True)
class CheckConversationInput:
    organization_id: str
    lead_id: str
    since: str


@dataclass(frozen=True)
class CheckConversationOutput:
    replied: bool
    unsubscribed: bool


@activity.defn
async def check_conversation_activity(input: CheckConversationInput) -> CheckConversationOutput:
    organization_id = UUID(input.organization_id)
    lead_id = UUID(input.lead_id)
    since = datetime.fromisoformat(input.since)

    factory = make_session_factory(get_default_engine())
    async with factory() as session:
        leads = await SqlAlchemyLeadRepository.create(session, organization_id)
        lead = await leads.get(lead_id)
        if lead is None:
            raise ApplicationError(f"No lead {lead_id}.", non_retryable=True)
        if lead.status in (LeadStatus.UNSUBSCRIBED, LeadStatus.SUPPRESSED):
            return CheckConversationOutput(replied=False, unsubscribed=True)

        persons = SqlAlchemyPersonRepository(session, organization_id)
        person = await persons.get(lead.person_id)
        suppressions = SqlAlchemySuppressionRepository(session, organization_id)
        if person and person.email and await suppressions.is_suppressed("email", person.email):
            return CheckConversationOutput(replied=False, unsubscribed=True)

        conversations = SqlAlchemyConversationRepository(session, organization_id)
        conversation = await conversations.get_by_lead_and_channel(lead_id, "email")
        replied = bool(
            conversation
            and conversation.last_activity_at is not None
            and conversation.last_activity_at > since
        )
        return CheckConversationOutput(replied=replied, unsubscribed=False)
