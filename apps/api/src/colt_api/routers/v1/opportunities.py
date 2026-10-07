"""The Opportunity engine's REST surface (CLAUDE.md §10.14, §11.3, §68 Milestone 21).

Follows `campaigns.py`'s own established shape: every route depends on `DbSessionDep` and one
of this module's own `require_permission(...)`-backed principal aliases, constructs a
`SqlAlchemyOpportunityRepository` bound to the caller's own `organization_id`, and drives it
through the application-layer use cases — never touching `colt_db` models directly.
`OPPORTUNITY_READ` gates the pipeline/revenue-attribution dashboard and inspecting a single
opportunity; `OPPORTUNITY_WRITE` gates changing one (stage transition, owner assignment).

Application-layer errors are translated to the `ColtError` taxonomy here, at the boundary
(CLAUDE.md §36): `NotFoundError` → 404, `InvalidOpportunityTransitionError` → 409 (the
opportunity exists and the request is otherwise well-formed, but its current stage forbids this
transition).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from colt_api.dependencies import DbSessionDep, require_permission
from colt_api.errors import ConflictError
from colt_api.errors import NotFoundError as ApiNotFoundError
from colt_application import (
    AssignOpportunityOwner,
    InvalidOpportunityTransitionError,
    NotFoundError,
    OrganizationContext,
    PipelineStageSummary,
    RevenueAttributionRow,
    TransitionOpportunityStage,
    summarize_pipeline,
    summarize_revenue_by_source,
)
from colt_db.repositories import SqlAlchemyOpportunityRepository, SqlAlchemyUserRepository
from colt_domain import Opportunity, Permission, PipelineStage

router = APIRouter(prefix="/opportunities", tags=["opportunities"])

ReadPrincipalDep = Annotated[
    OrganizationContext, Depends(require_permission(Permission.OPPORTUNITY_READ))
]
WritePrincipalDep = Annotated[
    OrganizationContext, Depends(require_permission(Permission.OPPORTUNITY_WRITE))
]


class OpportunityResponse(BaseModel):
    id: UUID
    organization_id: UUID
    company_id: UUID
    primary_person_id: UUID | None
    lead_id: UUID | None
    pipeline_stage: PipelineStage
    estimated_value: float | None
    currency: str | None
    probability: float | None
    owner_id: UUID | None
    source: str | None
    is_estimated_value: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, opportunity: Opportunity) -> OpportunityResponse:
        return cls(
            id=opportunity.id,
            organization_id=opportunity.organization_id,
            company_id=opportunity.company_id,
            primary_person_id=opportunity.primary_person_id,
            lead_id=opportunity.lead_id,
            pipeline_stage=opportunity.pipeline_stage,
            estimated_value=opportunity.estimated_value,
            currency=opportunity.currency,
            probability=opportunity.probability,
            owner_id=opportunity.owner_id,
            source=opportunity.source,
            is_estimated_value=opportunity.is_estimated_value,
            created_at=opportunity.created_at,
            updated_at=opportunity.updated_at,
        )


class OpportunityListResponse(BaseModel):
    opportunities: list[OpportunityResponse]


class PipelineStageSummaryResponse(BaseModel):
    stage: PipelineStage
    count: int
    total_value: float

    @classmethod
    def from_domain(cls, summary: PipelineStageSummary) -> PipelineStageSummaryResponse:
        return cls(stage=summary.stage, count=summary.count, total_value=summary.total_value)


class PipelineSummaryResponse(BaseModel):
    stages: list[PipelineStageSummaryResponse]


class RevenueAttributionRowResponse(BaseModel):
    source: str
    currency: str | None
    total_value: float
    opportunity_count: int
    includes_estimate: bool

    @classmethod
    def from_domain(cls, row: RevenueAttributionRow) -> RevenueAttributionRowResponse:
        return cls(
            source=row.source,
            currency=row.currency,
            total_value=row.total_value,
            opportunity_count=row.opportunity_count,
            includes_estimate=row.includes_estimate,
        )


class RevenueAttributionResponse(BaseModel):
    rows: list[RevenueAttributionRowResponse]


class TransitionOpportunityStageRequest(BaseModel):
    target_stage: PipelineStage


class AssignOpportunityOwnerRequest(BaseModel):
    owner_id: UUID


@router.get(
    "",
    response_model=OpportunityListResponse,
    summary="List this organization's opportunities",
)
async def list_opportunities(
    principal: ReadPrincipalDep, session: DbSessionDep
) -> OpportunityListResponse:
    repo = await SqlAlchemyOpportunityRepository.create(session, principal.organization.id)
    opportunities = await repo.list_all()
    return OpportunityListResponse(
        opportunities=[OpportunityResponse.from_domain(o) for o in opportunities]
    )


@router.get(
    "/pipeline",
    response_model=PipelineSummaryResponse,
    summary="Per-stage opportunity counts and open value — the pipeline dashboard's read model",
)
async def get_pipeline_summary(
    principal: ReadPrincipalDep, session: DbSessionDep
) -> PipelineSummaryResponse:
    repo = await SqlAlchemyOpportunityRepository.create(session, principal.organization.id)
    opportunities = await repo.list_all()
    stages = summarize_pipeline(opportunities)
    return PipelineSummaryResponse(
        stages=[PipelineStageSummaryResponse.from_domain(s) for s in stages]
    )


@router.get(
    "/revenue-attribution",
    response_model=RevenueAttributionResponse,
    summary="Closed-won revenue grouped by source",
)
async def get_revenue_attribution(
    principal: ReadPrincipalDep, session: DbSessionDep
) -> RevenueAttributionResponse:
    repo = await SqlAlchemyOpportunityRepository.create(session, principal.organization.id)
    opportunities = await repo.list_all()
    rows = summarize_revenue_by_source(opportunities)
    return RevenueAttributionResponse(
        rows=[RevenueAttributionRowResponse.from_domain(r) for r in rows]
    )


@router.get(
    "/{opportunity_id}",
    response_model=OpportunityResponse,
    summary="Inspect a single opportunity",
)
async def get_opportunity(
    opportunity_id: UUID, principal: ReadPrincipalDep, session: DbSessionDep
) -> OpportunityResponse:
    repo = await SqlAlchemyOpportunityRepository.create(session, principal.organization.id)
    opportunity = await repo.get(opportunity_id)
    if opportunity is None:
        raise ApiNotFoundError(f"No opportunity found with id {opportunity_id}.")
    return OpportunityResponse.from_domain(opportunity)


@router.post(
    "/{opportunity_id}/transition",
    response_model=OpportunityResponse,
    summary="Move an opportunity to another pipeline stage",
)
async def transition_opportunity_stage(
    opportunity_id: UUID,
    request: TransitionOpportunityStageRequest,
    principal: WritePrincipalDep,
    session: DbSessionDep,
) -> OpportunityResponse:
    repo = await SqlAlchemyOpportunityRepository.create(session, principal.organization.id)
    try:
        opportunity = await TransitionOpportunityStage(repo)(
            opportunity_id, request.target_stage, now=datetime.now(UTC)
        )
    except NotFoundError as exc:
        raise ApiNotFoundError(str(exc)) from exc
    except InvalidOpportunityTransitionError as exc:
        raise ConflictError(str(exc)) from exc
    await session.commit()
    return OpportunityResponse.from_domain(opportunity)


@router.post(
    "/{opportunity_id}/assign-owner",
    response_model=OpportunityResponse,
    summary="Assign an opportunity's owner to a user in this organization",
)
async def assign_opportunity_owner(
    opportunity_id: UUID,
    request: AssignOpportunityOwnerRequest,
    principal: WritePrincipalDep,
    session: DbSessionDep,
) -> OpportunityResponse:
    opportunities = await SqlAlchemyOpportunityRepository.create(session, principal.organization.id)
    users = SqlAlchemyUserRepository(session, principal.organization.id)
    try:
        opportunity = await AssignOpportunityOwner(opportunities, users)(
            opportunity_id, request.owner_id, now=datetime.now(UTC)
        )
    except NotFoundError as exc:
        raise ApiNotFoundError(str(exc)) from exc
    await session.commit()
    return OpportunityResponse.from_domain(opportunity)
