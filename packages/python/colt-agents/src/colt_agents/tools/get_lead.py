"""`get_lead` (CLAUDE.md §16.1's Internal category): look up one lead by id.

The handler calls `colt_application.GetLead`, never `colt-db` — this is the one tool this
milestone builds that proves §2.3's required path for real: Claude → Typed Tool → Application
Service → Repository → PostgreSQL.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from colt_agents.tool import Tool
from colt_application import GetLead
from colt_domain import Lead

TOOL_NAME = "get_lead"
TOOL_VERSION = "v1"


class GetLeadInput(BaseModel):
    lead_id: UUID


class GetLeadOutput(BaseModel):
    id: UUID
    company_id: UUID
    person_id: UUID
    status: str
    source: str | None = None
    current_stage: str | None = None
    priority: str | None = None

    @classmethod
    def from_domain(cls, lead: Lead) -> GetLeadOutput:
        return cls(
            id=lead.id,
            company_id=lead.company_id,
            person_id=lead.person_id,
            status=lead.status.value,
            source=lead.source,
            current_stage=lead.current_stage,
            priority=lead.priority,
        )


def build_get_lead_tool(get_lead: GetLead) -> Tool:
    """Build the `get_lead` tool bound to one organization's already-constructed `GetLead`
    use case (itself already bound to a tenant-scoped repository, CLAUDE.md §2.8)."""

    async def handler(validated_input: BaseModel) -> BaseModel:
        assert isinstance(validated_input, GetLeadInput)  # noqa: S101 - guards an internal
        # contract this tool's own `input_model` guarantees; never reachable with real input.
        lead = await get_lead(validated_input.lead_id)
        return GetLeadOutput.from_domain(lead)

    return Tool(
        name=TOOL_NAME,
        version=TOOL_VERSION,
        description=(
            "Look up a single lead by its id. Returns the lead's status, associated company "
            "and person ids, and funnel metadata. Fails if the lead does not exist."
        ),
        input_model=GetLeadInput,
        handler=handler,
    )
