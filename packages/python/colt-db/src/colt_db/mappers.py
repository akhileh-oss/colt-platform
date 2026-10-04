"""ORM row ↔ domain entity conversion.

The only place that knows both the SQLAlchemy model shape and the domain entity shape. Kept
tiny and boring on purpose: if this function grows business logic, that logic is in the wrong
layer.
"""

from __future__ import annotations

from uuid import UUID

from colt_db.models.agent_run import AgentRunModel
from colt_db.models.audit_log import AuditLogModel
from colt_db.models.campaign import CampaignModel
from colt_db.models.company import CompanyModel
from colt_db.models.conversation import ConversationModel
from colt_db.models.evidence import EvidenceModel
from colt_db.models.lead import LeadModel
from colt_db.models.message import MessageModel
from colt_db.models.opportunity import OpportunityModel
from colt_db.models.organization import OrganizationModel
from colt_db.models.person import PersonModel
from colt_db.models.signal import SignalModel
from colt_db.models.tool_call import ToolCallModel
from colt_db.models.user import UserModel
from colt_domain import (
    AgentRun,
    AgentRunStatus,
    AuditLog,
    Campaign,
    Company,
    Conversation,
    ConversationState,
    EmailStatus,
    Evidence,
    Lead,
    LeadStatus,
    Message,
    Opportunity,
    Organization,
    OrganizationStatus,
    Person,
    PipelineStage,
    Role,
    Signal,
    ToolCall,
    ToolCallStatus,
    User,
    UserStatus,
    VerificationStatus,
)


def organization_to_domain(model: OrganizationModel) -> Organization:
    return Organization(
        id=model.id,
        name=model.name,
        slug=model.slug,
        status=OrganizationStatus(model.status),
        settings=model.settings,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def user_to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        organization_id=model.organization_id,
        external_auth_id=model.external_auth_id,
        email=model.email,
        name=model.name,
        role=Role(model.role),
        status=UserStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def company_to_domain(model: CompanyModel) -> Company:
    return Company(
        id=model.id,
        organization_id=model.organization_id,
        name=model.name,
        domain=model.domain,
        normalized_domain=model.normalized_domain,
        industry=model.industry,
        employee_count=model.employee_count,
        revenue_range=model.revenue_range,
        country=model.country,
        region=model.region,
        city=model.city,
        description=model.description,
        website_url=model.website_url,
        linkedin_url=model.linkedin_url,
        source_metadata=model.source_metadata,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def person_to_domain(model: PersonModel) -> Person:
    return Person(
        id=model.id,
        organization_id=model.organization_id,
        company_id=model.company_id,
        first_name=model.first_name,
        last_name=model.last_name,
        full_name=model.full_name,
        title=model.title,
        seniority=model.seniority,
        department=model.department,
        email=model.email,
        email_status=EmailStatus(model.email_status) if model.email_status is not None else None,
        linkedin_url=model.linkedin_url,
        location=model.location,
        source_metadata=model.source_metadata,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def signal_to_domain(model: SignalModel) -> Signal:
    return Signal(
        id=model.id,
        organization_id=model.organization_id,
        company_id=model.company_id,
        person_id=model.person_id,
        signal_type=model.signal_type,
        source_url=model.source_url,
        source_type=model.source_type,
        observed_at=model.observed_at,
        event_at=model.event_at,
        confidence=model.confidence,
        summary=model.summary,
        business_implication=model.business_implication,
        raw_payload=model.raw_payload,
        created_at=model.created_at,
    )


def evidence_to_domain(model: EvidenceModel) -> Evidence:
    return Evidence(
        id=model.id,
        organization_id=model.organization_id,
        entity_type=model.entity_type,
        entity_id=model.entity_id,
        claim=model.claim,
        source_url=model.source_url,
        source_type=model.source_type,
        source_date=model.source_date,
        observed_at=model.observed_at,
        excerpt=model.excerpt,
        confidence=model.confidence,
        verification_status=VerificationStatus(model.verification_status),
        created_at=model.created_at,
    )


def lead_to_domain(model: LeadModel) -> Lead:
    return Lead(
        id=model.id,
        organization_id=model.organization_id,
        company_id=model.company_id,
        person_id=model.person_id,
        status=LeadStatus(model.status),
        source=model.source,
        current_stage=model.current_stage,
        priority=model.priority,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def campaign_to_domain(model: CampaignModel) -> Campaign:
    return Campaign(
        id=model.id,
        organization_id=model.organization_id,
        name=model.name,
        status=model.status,
        objective=model.objective,
        icp_definition=model.icp_definition,
        rules=model.rules,
        channels=model.channels,
        schedule=model.schedule,
        limits=model.limits,
        approval_policy=model.approval_policy,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def message_to_domain(model: MessageModel) -> Message:
    return Message(
        id=model.id,
        organization_id=model.organization_id,
        campaign_id=model.campaign_id,
        lead_id=model.lead_id,
        conversation_id=model.conversation_id,
        sequence_step_id=model.sequence_step_id,
        channel=model.channel,
        subject=model.subject,
        body=model.body,
        status=model.status,
        approval_status=model.approval_status,
        evidence_ids=[UUID(value) for value in model.evidence_ids],
        model_name=model.model_name,
        prompt_version=model.prompt_version,
        idempotency_key=model.idempotency_key,
        scheduled_at=model.scheduled_at,
        sent_at=model.sent_at,
        provider_message_id=model.provider_message_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def conversation_to_domain(model: ConversationModel) -> Conversation:
    return Conversation(
        id=model.id,
        organization_id=model.organization_id,
        lead_id=model.lead_id,
        channel=model.channel,
        state=ConversationState(model.state),
        last_activity_at=model.last_activity_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def opportunity_to_domain(model: OpportunityModel) -> Opportunity:
    return Opportunity(
        id=model.id,
        organization_id=model.organization_id,
        company_id=model.company_id,
        primary_person_id=model.primary_person_id,
        lead_id=model.lead_id,
        pipeline_stage=PipelineStage(model.pipeline_stage),
        estimated_value=(
            float(model.estimated_value) if model.estimated_value is not None else None
        ),
        currency=model.currency,
        probability=float(model.probability) if model.probability is not None else None,
        owner_id=model.owner_id,
        source=model.source,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def audit_log_to_domain(model: AuditLogModel) -> AuditLog:
    return AuditLog(
        id=model.id,
        organization_id=model.organization_id,
        actor_type=model.actor_type,
        actor_id=model.actor_id,
        action=model.action,
        entity_type=model.entity_type,
        entity_id=model.entity_id,
        metadata=model.audit_metadata,
        created_at=model.created_at,
        request_id=model.request_id,
        trace_id=model.trace_id,
    )


def agent_run_to_domain(model: AgentRunModel) -> AgentRun:
    return AgentRun(
        id=model.id,
        organization_id=model.organization_id,
        agent_name=model.agent_name,
        agent_version=model.agent_version,
        model_name=model.model_name,
        workflow_id=model.workflow_id,
        workflow_run_id=model.workflow_run_id,
        entity_type=model.entity_type,
        entity_id=model.entity_id,
        prompt_version=model.prompt_version,
        input_hash=model.input_hash,
        started_at=model.started_at,
        completed_at=model.completed_at,
        status=AgentRunStatus(model.status),
        input_tokens=model.input_tokens,
        output_tokens=model.output_tokens,
        tool_tokens=model.tool_tokens,
        estimated_cost_usd=model.estimated_cost_usd,
        output_json=model.output_json,
        error_code=model.error_code,
        error_message=model.error_message,
    )


def tool_call_to_domain(model: ToolCallModel) -> ToolCall:
    return ToolCall(
        id=model.id,
        agent_run_id=model.agent_run_id,
        organization_id=model.organization_id,
        tool_name=model.tool_name,
        tool_version=model.tool_version,
        arguments_redacted=model.arguments_redacted,
        result_summary=model.result_summary,
        provider=model.provider,
        started_at=model.started_at,
        completed_at=model.completed_at,
        status=ToolCallStatus(model.status),
        error_code=model.error_code,
        latency_ms=model.latency_ms,
    )
