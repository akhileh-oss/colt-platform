"""The Analytics + Learning Loop REST surface (CLAUDE.md §68, Milestone 22).

Every route depends on `DbSessionDep` and this module's own `ANALYTICS_READ`-gated principal,
constructs the `SqlAlchemy*Repository`s a given report needs (bound to the caller's own
`organization_id`, the same `campaigns.py`/`opportunities.py` shape), reads every row with that
repository's `list_all()`, and hands the lists straight to the matching pure aggregation
function in `colt_application` — never touching `colt_db` models directly, and never persisting
anything: every route here is read-only.

Milestone 22's acceptance criterion is "dashboard can answer what segments, signals, personas,
channels and message variants produce commercial outcomes" — the five routes below
(`/icp-performance`, `/trigger-performance`, `/message-performance`, `/channel-performance`,
plus `/revenue-outcomes`, reusing Milestone 21's own `summarize_revenue_by_source`) are exactly
that question, one route per dimension. `/funnel`, `/agent-cost`, and `/model-performance` are
the Build list's remaining, purely operational reports.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from colt_api.dependencies import DbSessionDep, require_permission
from colt_application import (
    AgentCostRow,
    ChannelPerformanceRow,
    FunnelStageSummary,
    IcpPerformanceRow,
    MessagePerformanceRow,
    ModelPerformanceRow,
    OrganizationContext,
    RevenueAttributionRow,
    TriggerPerformanceRow,
    summarize_agent_cost,
    summarize_channel_performance,
    summarize_funnel,
    summarize_icp_performance,
    summarize_message_performance,
    summarize_model_performance,
    summarize_revenue_by_source,
    summarize_trigger_performance,
)
from colt_db.repositories import (
    SqlAlchemyAgentRunRepository,
    SqlAlchemyCompanyRepository,
    SqlAlchemyConversationRepository,
    SqlAlchemyLeadRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyOpportunityRepository,
    SqlAlchemyPersonRepository,
    SqlAlchemySignalRepository,
)
from colt_domain import LeadStatus, Permission

router = APIRouter(prefix="/analytics", tags=["analytics"])

ReadPrincipalDep = Annotated[
    OrganizationContext, Depends(require_permission(Permission.ANALYTICS_READ))
]


class FunnelResponse(BaseModel):
    status: LeadStatus
    count: int

    @classmethod
    def from_domain(cls, row: FunnelStageSummary) -> FunnelResponse:
        return cls(status=row.status, count=row.count)


class FunnelListResponse(BaseModel):
    stages: list[FunnelResponse]


class IcpPerformanceResponse(BaseModel):
    industry: str
    company_count: int
    lead_count: int
    qualified_lead_count: int
    won_company_count: int
    won_revenue: float

    @classmethod
    def from_domain(cls, row: IcpPerformanceRow) -> IcpPerformanceResponse:
        return cls(
            industry=row.industry,
            company_count=row.company_count,
            lead_count=row.lead_count,
            qualified_lead_count=row.qualified_lead_count,
            won_company_count=row.won_company_count,
            won_revenue=row.won_revenue,
        )


class IcpPerformanceListResponse(BaseModel):
    rows: list[IcpPerformanceResponse]


class TriggerPerformanceResponse(BaseModel):
    signal_type: str
    signal_count: int
    company_count: int
    won_company_count: int
    average_confidence: float | None

    @classmethod
    def from_domain(cls, row: TriggerPerformanceRow) -> TriggerPerformanceResponse:
        return cls(
            signal_type=row.signal_type,
            signal_count=row.signal_count,
            company_count=row.company_count,
            won_company_count=row.won_company_count,
            average_confidence=row.average_confidence,
        )


class TriggerPerformanceListResponse(BaseModel):
    rows: list[TriggerPerformanceResponse]


class MessagePerformanceResponse(BaseModel):
    prompt_version: str
    persona: str
    drafted_count: int
    sent_count: int
    approved_count: int

    @classmethod
    def from_domain(cls, row: MessagePerformanceRow) -> MessagePerformanceResponse:
        return cls(
            prompt_version=row.prompt_version,
            persona=row.persona,
            drafted_count=row.drafted_count,
            sent_count=row.sent_count,
            approved_count=row.approved_count,
        )


class MessagePerformanceListResponse(BaseModel):
    rows: list[MessagePerformanceResponse]


class ChannelPerformanceResponse(BaseModel):
    channel: str
    message_count: int
    sent_count: int
    conversation_count: int
    positive_count: int
    positive_rate: float

    @classmethod
    def from_domain(cls, row: ChannelPerformanceRow) -> ChannelPerformanceResponse:
        return cls(
            channel=row.channel,
            message_count=row.message_count,
            sent_count=row.sent_count,
            conversation_count=row.conversation_count,
            positive_count=row.positive_count,
            positive_rate=row.positive_rate,
        )


class ChannelPerformanceListResponse(BaseModel):
    rows: list[ChannelPerformanceResponse]


class AgentCostResponse(BaseModel):
    agent_name: str
    run_count: int
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    total_tool_tokens: int

    @classmethod
    def from_domain(cls, row: AgentCostRow) -> AgentCostResponse:
        return cls(
            agent_name=row.agent_name,
            run_count=row.run_count,
            total_cost_usd=row.total_cost_usd,
            total_input_tokens=row.total_input_tokens,
            total_output_tokens=row.total_output_tokens,
            total_tool_tokens=row.total_tool_tokens,
        )


class AgentCostListResponse(BaseModel):
    rows: list[AgentCostResponse]


class ModelPerformanceResponse(BaseModel):
    model_name: str
    run_count: int
    completed_count: int
    failed_count: int
    success_rate: float
    average_cost_usd: float | None

    @classmethod
    def from_domain(cls, row: ModelPerformanceRow) -> ModelPerformanceResponse:
        return cls(
            model_name=row.model_name,
            run_count=row.run_count,
            completed_count=row.completed_count,
            failed_count=row.failed_count,
            success_rate=row.success_rate,
            average_cost_usd=row.average_cost_usd,
        )


class ModelPerformanceListResponse(BaseModel):
    rows: list[ModelPerformanceResponse]


class RevenueOutcomeResponse(BaseModel):
    source: str
    currency: str | None
    total_value: float
    opportunity_count: int
    includes_estimate: bool

    @classmethod
    def from_domain(cls, row: RevenueAttributionRow) -> RevenueOutcomeResponse:
        return cls(
            source=row.source,
            currency=row.currency,
            total_value=row.total_value,
            opportunity_count=row.opportunity_count,
            includes_estimate=row.includes_estimate,
        )


class RevenueOutcomeListResponse(BaseModel):
    rows: list[RevenueOutcomeResponse]


@router.get("/funnel", response_model=FunnelListResponse, summary="Lead counts per funnel stage")
async def get_funnel(principal: ReadPrincipalDep, session: DbSessionDep) -> FunnelListResponse:
    leads = await SqlAlchemyLeadRepository.create(session, principal.organization.id)
    stages = summarize_funnel(await leads.list_all())
    return FunnelListResponse(stages=[FunnelResponse.from_domain(s) for s in stages])


@router.get(
    "/icp-performance",
    response_model=IcpPerformanceListResponse,
    summary="Which segments (by company industry) produce commercial outcomes",
)
async def get_icp_performance(
    principal: ReadPrincipalDep, session: DbSessionDep
) -> IcpPerformanceListResponse:
    companies = await SqlAlchemyCompanyRepository.create(session, principal.organization.id)
    leads = SqlAlchemyLeadRepository(session, principal.organization.id)
    opportunities = SqlAlchemyOpportunityRepository(session, principal.organization.id)
    rows = summarize_icp_performance(
        await companies.list_all(), await leads.list_all(), await opportunities.list_all()
    )
    return IcpPerformanceListResponse(rows=[IcpPerformanceResponse.from_domain(r) for r in rows])


@router.get(
    "/trigger-performance",
    response_model=TriggerPerformanceListResponse,
    summary="Which signals produce commercial outcomes",
)
async def get_trigger_performance(
    principal: ReadPrincipalDep, session: DbSessionDep
) -> TriggerPerformanceListResponse:
    signals = await SqlAlchemySignalRepository.create(session, principal.organization.id)
    opportunities = SqlAlchemyOpportunityRepository(session, principal.organization.id)
    rows = summarize_trigger_performance(await signals.list_all(), await opportunities.list_all())
    return TriggerPerformanceListResponse(
        rows=[TriggerPerformanceResponse.from_domain(r) for r in rows]
    )


@router.get(
    "/message-performance",
    response_model=MessagePerformanceListResponse,
    summary="Which message variants and personas produce commercial outcomes",
)
async def get_message_performance(
    principal: ReadPrincipalDep, session: DbSessionDep
) -> MessagePerformanceListResponse:
    messages = await SqlAlchemyMessageRepository.create(session, principal.organization.id)
    leads = SqlAlchemyLeadRepository(session, principal.organization.id)
    persons = SqlAlchemyPersonRepository(session, principal.organization.id)
    rows = summarize_message_performance(
        await messages.list_all(), await leads.list_all(), await persons.list_all()
    )
    return MessagePerformanceListResponse(
        rows=[MessagePerformanceResponse.from_domain(r) for r in rows]
    )


@router.get(
    "/channel-performance",
    response_model=ChannelPerformanceListResponse,
    summary="Which channels produce commercial outcomes",
)
async def get_channel_performance(
    principal: ReadPrincipalDep, session: DbSessionDep
) -> ChannelPerformanceListResponse:
    messages = await SqlAlchemyMessageRepository.create(session, principal.organization.id)
    conversations = SqlAlchemyConversationRepository(session, principal.organization.id)
    rows = summarize_channel_performance(await messages.list_all(), await conversations.list_all())
    return ChannelPerformanceListResponse(
        rows=[ChannelPerformanceResponse.from_domain(r) for r in rows]
    )


@router.get(
    "/agent-cost", response_model=AgentCostListResponse, summary="Cost and token usage per agent"
)
async def get_agent_cost(
    principal: ReadPrincipalDep, session: DbSessionDep
) -> AgentCostListResponse:
    agent_runs = await SqlAlchemyAgentRunRepository.create(session, principal.organization.id)
    rows = summarize_agent_cost(await agent_runs.list_all())
    return AgentCostListResponse(rows=[AgentCostResponse.from_domain(r) for r in rows])


@router.get(
    "/model-performance",
    response_model=ModelPerformanceListResponse,
    summary="Success rate and average cost per model",
)
async def get_model_performance(
    principal: ReadPrincipalDep, session: DbSessionDep
) -> ModelPerformanceListResponse:
    agent_runs = await SqlAlchemyAgentRunRepository.create(session, principal.organization.id)
    rows = summarize_model_performance(await agent_runs.list_all())
    return ModelPerformanceListResponse(
        rows=[ModelPerformanceResponse.from_domain(r) for r in rows]
    )


@router.get(
    "/revenue-outcomes",
    response_model=RevenueOutcomeListResponse,
    summary="Closed-won revenue grouped by source",
)
async def get_revenue_outcomes(
    principal: ReadPrincipalDep, session: DbSessionDep
) -> RevenueOutcomeListResponse:
    opportunities = await SqlAlchemyOpportunityRepository.create(session, principal.organization.id)
    rows = summarize_revenue_by_source(await opportunities.list_all())
    return RevenueOutcomeListResponse(rows=[RevenueOutcomeResponse.from_domain(r) for r in rows])
