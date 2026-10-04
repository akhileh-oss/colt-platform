"""The Campaign engine's REST surface (CLAUDE.md §10.9, §68 Milestone 14).

The first DB-backed CRUD resource in the API: every route depends on `DbSessionDep` and one of
this module's own `require_permission(...)`-backed principal aliases (`ReadPrincipalDep`/
`WritePrincipalDep`/`LaunchPrincipalDep`, following `dependencies.py`'s own
`Depends(require_permission(Permission.X))` convention), constructs a
`SqlAlchemyCampaignRepository` bound to the caller's own `organization_id` (RLS is already
bound on the session by `principal_provider`), and drives it through the application-layer use
cases — never touching `colt_db` models directly. `CAMPAIGN_WRITE` gates creating/editing a
campaign's definition; `CAMPAIGN_LAUNCH` gates controlling a campaign's live state (validating
it into existence, pausing, resuming) — a deliberate split so a MARKETING/MANAGER role can do
both, while a role with only `CAMPAIGN_READ` (e.g. SALES, VIEWER) can inspect but never launch
or edit (CLAUDE.md §26, `colt_domain.roles.DEFAULT_ROLE_PERMISSIONS`).

Application-layer errors are translated to the `ColtError` taxonomy here, at the boundary
(CLAUDE.md §36): `NotFoundError` → 404, `CampaignValidationError` → 422 with every failing rule
in `details`, `InvalidCampaignTransitionError` → 409 (the campaign exists and the request is
otherwise well-formed, but its current state forbids this transition).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from colt_api.dependencies import DbSessionDep, require_permission
from colt_api.errors import ConflictError
from colt_api.errors import NotFoundError as ApiNotFoundError
from colt_api.errors import ValidationError as ApiValidationError
from colt_application import (
    AddSequenceStep,
    CampaignValidationError,
    CreateCampaign,
    GetCampaign,
    InvalidCampaignTransitionError,
    ListCampaigns,
    ListSequenceSteps,
    NotFoundError,
    OrganizationContext,
    PauseCampaign,
    ResumeCampaign,
    ValidateCampaign,
)
from colt_db.repositories import SqlAlchemyCampaignRepository, SqlAlchemySequenceStepRepository
from colt_domain import Campaign, CampaignStatus, Permission, SequenceStep

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

#: `CAMPAIGN_WRITE` gates creating/editing a campaign's definition; `CAMPAIGN_READ` gates
#: inspecting one; `CAMPAIGN_LAUNCH` gates controlling its live state (see module docstring).
ReadPrincipalDep = Annotated[
    OrganizationContext, Depends(require_permission(Permission.CAMPAIGN_READ))
]
WritePrincipalDep = Annotated[
    OrganizationContext, Depends(require_permission(Permission.CAMPAIGN_WRITE))
]
LaunchPrincipalDep = Annotated[
    OrganizationContext, Depends(require_permission(Permission.CAMPAIGN_LAUNCH))
]


class CampaignResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    status: CampaignStatus
    objective: str | None
    icp_definition: dict[str, Any]
    rules: dict[str, Any]
    channels: list[str]
    schedule: dict[str, Any]
    limits: dict[str, Any]
    approval_policy: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, campaign: Campaign) -> CampaignResponse:
        return cls(
            id=campaign.id,
            organization_id=campaign.organization_id,
            name=campaign.name,
            status=campaign.status,
            objective=campaign.objective,
            icp_definition=campaign.icp_definition,
            rules=campaign.rules,
            channels=campaign.channels,
            schedule=campaign.schedule,
            limits=campaign.limits,
            approval_policy=campaign.approval_policy,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
        )


class CampaignListResponse(BaseModel):
    campaigns: list[CampaignResponse]


class CreateCampaignRequest(BaseModel):
    name: str
    objective: str | None = None
    icp_definition: dict[str, Any] | None = None
    rules: dict[str, Any] | None = None
    channels: list[str] | None = None
    schedule: dict[str, Any] | None = None
    limits: dict[str, Any] | None = None
    approval_policy: dict[str, Any] | None = None


class SequenceStepResponse(BaseModel):
    id: UUID
    organization_id: UUID
    campaign_id: UUID
    step_order: int
    channel: str
    delay_after_previous: int
    message_strategy: str
    conditions: dict[str, Any]
    active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, step: SequenceStep) -> SequenceStepResponse:
        return cls(
            id=step.id,
            organization_id=step.organization_id,
            campaign_id=step.campaign_id,
            step_order=step.step_order,
            channel=step.channel,
            delay_after_previous=step.delay_after_previous,
            message_strategy=step.message_strategy,
            conditions=step.conditions,
            active=step.active,
            created_at=step.created_at,
            updated_at=step.updated_at,
        )


class SequenceStepListResponse(BaseModel):
    sequence_steps: list[SequenceStepResponse]


class AddSequenceStepRequest(BaseModel):
    step_order: int
    channel: str
    message_strategy: str
    delay_after_previous: int = 0
    conditions: dict[str, Any] | None = None
    active: bool = True


@router.post(
    "",
    response_model=CampaignResponse,
    status_code=201,
    summary="Create a campaign",
)
async def create_campaign(
    request: CreateCampaignRequest, principal: WritePrincipalDep, session: DbSessionDep
) -> CampaignResponse:
    repo = await SqlAlchemyCampaignRepository.create(session, principal.organization.id)
    create = CreateCampaign(repo)
    campaign = await create(**request.model_dump())
    await session.commit()
    return CampaignResponse.from_domain(campaign)


@router.get(
    "",
    response_model=CampaignListResponse,
    summary="List this organization's campaigns",
)
async def list_campaigns(
    principal: ReadPrincipalDep, session: DbSessionDep
) -> CampaignListResponse:
    repo = await SqlAlchemyCampaignRepository.create(session, principal.organization.id)
    campaigns = await ListCampaigns(repo)()
    return CampaignListResponse(campaigns=[CampaignResponse.from_domain(c) for c in campaigns])


@router.get(
    "/{campaign_id}",
    response_model=CampaignResponse,
    summary="Inspect a single campaign",
)
async def get_campaign(
    campaign_id: UUID, principal: ReadPrincipalDep, session: DbSessionDep
) -> CampaignResponse:
    repo = await SqlAlchemyCampaignRepository.create(session, principal.organization.id)
    try:
        campaign = await GetCampaign(repo)(campaign_id)
    except NotFoundError as exc:
        raise ApiNotFoundError(str(exc)) from exc
    return CampaignResponse.from_domain(campaign)


@router.post(
    "/{campaign_id}/validate",
    response_model=CampaignResponse,
    summary="Validate a draft campaign's definition and activate it",
)
async def validate_campaign(
    campaign_id: UUID, principal: LaunchPrincipalDep, session: DbSessionDep
) -> CampaignResponse:
    repo = await SqlAlchemyCampaignRepository.create(session, principal.organization.id)
    try:
        campaign = await ValidateCampaign(repo)(campaign_id, now=datetime.now(UTC))
    except NotFoundError as exc:
        raise ApiNotFoundError(str(exc)) from exc
    except CampaignValidationError as exc:
        raise ApiValidationError(str(exc), details={"issues": exc.issues}) from exc
    except InvalidCampaignTransitionError as exc:
        raise ConflictError(str(exc)) from exc
    await session.commit()
    return CampaignResponse.from_domain(campaign)


@router.post(
    "/{campaign_id}/pause",
    response_model=CampaignResponse,
    summary="Pause an active campaign",
)
async def pause_campaign(
    campaign_id: UUID, principal: LaunchPrincipalDep, session: DbSessionDep
) -> CampaignResponse:
    repo = await SqlAlchemyCampaignRepository.create(session, principal.organization.id)
    try:
        campaign = await PauseCampaign(repo)(campaign_id, now=datetime.now(UTC))
    except NotFoundError as exc:
        raise ApiNotFoundError(str(exc)) from exc
    except InvalidCampaignTransitionError as exc:
        raise ConflictError(str(exc)) from exc
    await session.commit()
    return CampaignResponse.from_domain(campaign)


@router.post(
    "/{campaign_id}/sequence-steps",
    response_model=SequenceStepResponse,
    status_code=201,
    summary="Add a sequence step to a campaign",
)
async def add_sequence_step(
    campaign_id: UUID,
    request: AddSequenceStepRequest,
    principal: WritePrincipalDep,
    session: DbSessionDep,
) -> SequenceStepResponse:
    campaigns = await SqlAlchemyCampaignRepository.create(session, principal.organization.id)
    sequence_steps = SqlAlchemySequenceStepRepository(session, principal.organization.id)
    try:
        step = await AddSequenceStep(campaigns, sequence_steps)(
            campaign_id=campaign_id, **request.model_dump()
        )
    except NotFoundError as exc:
        raise ApiNotFoundError(str(exc)) from exc
    await session.commit()
    return SequenceStepResponse.from_domain(step)


@router.get(
    "/{campaign_id}/sequence-steps",
    response_model=SequenceStepListResponse,
    summary="List a campaign's sequence steps, in order",
)
async def list_sequence_steps(
    campaign_id: UUID, principal: ReadPrincipalDep, session: DbSessionDep
) -> SequenceStepListResponse:
    campaigns = await SqlAlchemyCampaignRepository.create(session, principal.organization.id)
    sequence_steps = SqlAlchemySequenceStepRepository(session, principal.organization.id)
    try:
        steps = await ListSequenceSteps(campaigns, sequence_steps)(campaign_id)
    except NotFoundError as exc:
        raise ApiNotFoundError(str(exc)) from exc
    return SequenceStepListResponse(
        sequence_steps=[SequenceStepResponse.from_domain(step) for step in steps]
    )


@router.post(
    "/{campaign_id}/resume",
    response_model=CampaignResponse,
    summary="Resume a paused campaign",
)
async def resume_campaign(
    campaign_id: UUID, principal: LaunchPrincipalDep, session: DbSessionDep
) -> CampaignResponse:
    repo = await SqlAlchemyCampaignRepository.create(session, principal.organization.id)
    try:
        campaign = await ResumeCampaign(repo)(campaign_id, now=datetime.now(UTC))
    except NotFoundError as exc:
        raise ApiNotFoundError(str(exc)) from exc
    except InvalidCampaignTransitionError as exc:
        raise ConflictError(str(exc)) from exc
    await session.commit()
    return CampaignResponse.from_domain(campaign)
