"""`evaluate_opportunity_activity` (CLAUDE.md §12.11, §11.3, Milestone 21) — wires a real
`AgentRuntime` running `OpportunityAgent` behind Temporal, the same composition-root shape
`classify_reply_activity` (Milestone 19) already established for the agent right before this
one in the pipeline.

Called only once a reply has already been classified `POSITIVE` (§11.2) — this activity does
not re-derive that itself, the same way `classify_reply_activity` does not re-derive which
`ConversationEvent` to classify. Reads the same most-recent `message_received` content
`classify_reply_activity` reads, since the positive-conversation content is exactly what
`OpportunityAgent` needs to judge commercial intent.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from colt_agents import AgentRuntime, ToolRegistry
from colt_agents.errors import AgentError, AgentTimeoutError
from colt_agents.opportunity_agent import (
    OPPORTUNITY_AGENT_DEFINITION,
    OpportunityAgentInput,
    OpportunityDecision,
)
from colt_agents.prompts import load_prompt
from colt_agents.tools import build_create_or_update_opportunity_tool
from colt_ai import AnthropicGateway
from colt_ai.errors import GatewayError
from colt_application.errors import NotFoundError
from colt_application.use_cases.create_or_update_opportunity import CreateOrUpdateOpportunity
from colt_config import get_settings
from colt_db import get_default_engine, make_session_factory
from colt_db.repositories import (
    SqlAlchemyAgentRunRepository,
    SqlAlchemyCompanyRepository,
    SqlAlchemyConversationEventRepository,
    SqlAlchemyConversationRepository,
    SqlAlchemyLeadRepository,
    SqlAlchemyOpportunityRepository,
    SqlAlchemyPersonRepository,
    SqlAlchemyToolCallRepository,
)


@dataclass(frozen=True)
class EvaluateOpportunityActivityInput:
    organization_id: str
    conversation_id: str


@dataclass(frozen=True)
class EvaluateOpportunityActivityOutput:
    has_commercial_intent: bool


@activity.defn
async def evaluate_opportunity_activity(
    input: EvaluateOpportunityActivityInput,
) -> EvaluateOpportunityActivityOutput:
    settings = get_settings()
    organization_id = UUID(input.organization_id)
    conversation_id = UUID(input.conversation_id)
    info = activity.info()

    factory = make_session_factory(get_default_engine())
    async with factory() as session:
        conversations = await SqlAlchemyConversationRepository.create(session, organization_id)
        conversation = await conversations.get(conversation_id)
        if conversation is None:
            raise ApplicationError(f"No conversation {conversation_id}.", non_retryable=True)

        leads = SqlAlchemyLeadRepository(session, organization_id)
        lead = await leads.get(conversation.lead_id)
        if lead is None:
            raise ApplicationError(
                f"Conversation {conversation_id} has no resolvable lead.", non_retryable=True
            )
        companies = SqlAlchemyCompanyRepository(session, organization_id)
        company = await companies.get(lead.company_id)
        persons = SqlAlchemyPersonRepository(session, organization_id)
        person = await persons.get(lead.person_id)
        if company is None or person is None:
            raise ApplicationError(
                f"Lead {lead.id} has no resolvable company/person.", non_retryable=True
            )

        conversation_events = await SqlAlchemyConversationEventRepository.create(
            session, organization_id
        )
        events = await conversation_events.list_by_conversation(conversation_id)
        latest_reply = next(
            (e for e in reversed(events) if e.event_type == "message_received"), None
        )
        if latest_reply is None:
            raise ApplicationError(
                f"Conversation {conversation_id} has no message_received event to evaluate.",
                non_retryable=True,
            )

        opportunities = SqlAlchemyOpportunityRepository(session, organization_id)
        agent_runs = SqlAlchemyAgentRunRepository(session, organization_id)
        tool_calls = SqlAlchemyToolCallRepository(session, organization_id)
        create_or_update_opportunity = CreateOrUpdateOpportunity(opportunities)

        registry = ToolRegistry()
        registry.register(build_create_or_update_opportunity_tool(create_or_update_opportunity))
        runtime = AgentRuntime(
            AnthropicGateway(settings.anthropic), registry, agent_runs, tool_calls
        )

        try:
            decision = await runtime.run(
                OPPORTUNITY_AGENT_DEFINITION,
                input=OpportunityAgentInput(
                    conversation_id=conversation_id,
                    company_id=company.id,
                    company_name=company.name,
                    person_name=person.full_name,
                    lead_id=lead.id,
                    primary_person_id=person.id,
                    subject=latest_reply.metadata.get("subject"),
                    body=str(latest_reply.metadata.get("body", "")),
                ),
                system_prompt=load_prompt("opportunity", "v1"),
                prompt_version="v1",
                workflow_id=info.workflow_id,
                workflow_run_id=info.workflow_run_id,
                entity_type="Conversation",
                entity_id=conversation_id,
            )
        except GatewayError as exc:
            raise ApplicationError(str(exc), non_retryable=not exc.retryable) from exc
        except AgentError as exc:
            raise ApplicationError(
                str(exc), non_retryable=not isinstance(exc, AgentTimeoutError)
            ) from exc
        except NotFoundError as exc:
            raise ApplicationError(str(exc), non_retryable=True) from exc

        assert isinstance(decision, OpportunityDecision)  # noqa: S101 - guards an internal
        # contract `AgentDefinition.output_schema` already guarantees.
        await session.commit()

    return EvaluateOpportunityActivityOutput(has_commercial_intent=decision.has_commercial_intent)
