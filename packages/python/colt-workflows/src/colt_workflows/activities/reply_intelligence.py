"""`classify_reply_activity` (CLAUDE.md §12.10, §23.1, Milestone 19) — wires a real
`AgentRuntime` running `ReplyIntelligenceAgent` behind Temporal, the same composition-root shape
`research_company_activity`/`draft_next_message_activity` (Milestone 18) already established.

Reads the inbound reply's own content from the most recent `message_received` `ConversationEvent`
(`ProcessInboundEmail`, Milestone 17, already stores `from_email`/`subject`/`body` there) rather
than taking it as activity input directly — the workflow that calls this only knows a reply
arrived, not what it said.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from colt_agents import AgentRuntime, ToolRegistry
from colt_agents.errors import AgentError, AgentTimeoutError
from colt_agents.prompts import load_prompt
from colt_agents.reply_intelligence_agent import (
    REPLY_INTELLIGENCE_AGENT_DEFINITION,
    ReplyClassification,
    ReplyIntelligenceAgentInput,
)
from colt_agents.tools import build_record_reply_classification_tool
from colt_ai import AnthropicGateway
from colt_ai.errors import GatewayError
from colt_application.errors import NotFoundError
from colt_application.use_cases.record_reply_classification import RecordReplyClassification
from colt_config import get_settings
from colt_db import get_default_engine, make_session_factory
from colt_db.repositories import (
    SqlAlchemyAgentRunRepository,
    SqlAlchemyCompanyRepository,
    SqlAlchemyConversationEventRepository,
    SqlAlchemyConversationRepository,
    SqlAlchemyLeadRepository,
    SqlAlchemyPersonRepository,
    SqlAlchemyToolCallRepository,
)


@dataclass(frozen=True)
class ClassifyReplyActivityInput:
    organization_id: str
    conversation_id: str


@dataclass(frozen=True)
class ClassifyReplyActivityOutput:
    applied_state: str


@activity.defn
async def classify_reply_activity(input: ClassifyReplyActivityInput) -> ClassifyReplyActivityOutput:
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
                f"Conversation {conversation_id} has no message_received event to classify.",
                non_retryable=True,
            )

        agent_runs = SqlAlchemyAgentRunRepository(session, organization_id)
        tool_calls = SqlAlchemyToolCallRepository(session, organization_id)
        record_reply_classification = RecordReplyClassification(conversations, conversation_events)

        registry = ToolRegistry()
        registry.register(build_record_reply_classification_tool(record_reply_classification))
        runtime = AgentRuntime(
            AnthropicGateway(settings.anthropic), registry, agent_runs, tool_calls
        )

        try:
            classification = await runtime.run(
                REPLY_INTELLIGENCE_AGENT_DEFINITION,
                input=ReplyIntelligenceAgentInput(
                    conversation_id=conversation_id,
                    company_name=company.name,
                    person_name=person.full_name,
                    subject=latest_reply.metadata.get("subject"),
                    body=str(latest_reply.metadata.get("body", "")),
                ),
                system_prompt=load_prompt("reply_intelligence", "v1"),
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

        assert isinstance(classification, ReplyClassification)  # noqa: S101 - guards an
        # internal contract `AgentDefinition.output_schema` already guarantees.
        await session.commit()

        refreshed = await conversations.get(conversation_id)
        assert refreshed is not None  # noqa: S101 - the row we just classified cannot have
        # vanished between the classification commit above and this re-read.
        return ClassifyReplyActivityOutput(applied_state=refreshed.state.value)
