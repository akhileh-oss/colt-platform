"""`create_or_update_opportunity` (CLAUDE.md §10.14, §11.3, §12.11, Milestone 21) — the one write
`OpportunityAgent` may call. Applies `CreateOrUpdateOpportunity`'s deterministic dedup rule
(at most one open opportunity per company) — never trusts the model to decide whether a
duplicate would result.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel

from colt_agents.tool import Tool
from colt_application.use_cases.create_or_update_opportunity import CreateOrUpdateOpportunity

TOOL_NAME = "create_or_update_opportunity"
TOOL_VERSION = "v1"


class CreateOrUpdateOpportunityInput(BaseModel):
    company_id: UUID
    primary_person_id: UUID | None = None
    lead_id: UUID | None = None
    estimated_value: float | None = None
    currency: str | None = None
    is_estimate: bool = False


class CreateOrUpdateOpportunityOutput(BaseModel):
    opportunity_id: UUID
    pipeline_stage: str
    was_created: bool


def build_create_or_update_opportunity_tool(
    create_or_update_opportunity: CreateOrUpdateOpportunity,
) -> Tool:
    async def handler(validated_input: BaseModel) -> BaseModel:
        assert isinstance(validated_input, CreateOrUpdateOpportunityInput)  # noqa: S101 -
        # guards an internal contract this tool's own `input_model` guarantees.
        result = await create_or_update_opportunity(
            company_id=validated_input.company_id,
            primary_person_id=validated_input.primary_person_id,
            lead_id=validated_input.lead_id,
            source="conversation",
            estimated_value=validated_input.estimated_value,
            currency=validated_input.currency,
            is_estimate=validated_input.is_estimate,
            now=datetime.now(UTC),
        )
        return CreateOrUpdateOpportunityOutput(
            opportunity_id=result.opportunity.id,
            pipeline_stage=result.opportunity.pipeline_stage.value,
            was_created=result.was_created,
        )

    return Tool(
        name=TOOL_NAME,
        version=TOOL_VERSION,
        description=(
            "Create or update an Opportunity for this conversation's company. If an open "
            "(non-WON/LOST) opportunity already exists for this company, the existing one is "
            "returned (optionally gaining the supplied value if it had none) rather than a "
            "duplicate being created."
        ),
        input_model=CreateOrUpdateOpportunityInput,
        handler=handler,
    )
