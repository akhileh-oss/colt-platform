"""`enrich_person` (CLAUDE.md §12.4, §16.1's `verify_email`)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from colt_agents.tool import Tool
from colt_application.use_cases.enrich_person import EnrichPerson
from colt_integrations.enrichment.port import EnrichmentProvider

TOOL_NAME = "enrich_person"
TOOL_VERSION = "v1"


class EnrichPersonInput(BaseModel):
    person_id: UUID
    email: str


class EnrichPersonOutput(BaseModel):
    person_id: UUID
    title: str | None
    email_status: str | None


def build_enrich_person_tool(provider: EnrichmentProvider, enrich_person: EnrichPerson) -> Tool:
    async def handler(validated_input: BaseModel) -> BaseModel:
        assert isinstance(validated_input, EnrichPersonInput)  # noqa: S101 - guards an
        # internal contract this tool's own `input_model` guarantees; never reachable with
        # real input.
        candidate = await provider.enrich_person(validated_input.email)
        if candidate is None:
            person = await enrich_person(validated_input.person_id, provider="none", confidence=0.0)
        else:
            person = await enrich_person(
                validated_input.person_id,
                provider=candidate.provider,
                confidence=candidate.confidence,
                provider_id=candidate.provider_id,
                first_name=candidate.first_name,
                last_name=candidate.last_name,
                title=candidate.title,
                email=candidate.email,
                email_verified=candidate.email_verified,
                linkedin_url=candidate.linkedin_url,
            )
        return EnrichPersonOutput(
            person_id=person.id,
            title=person.title,
            email_status=person.email_status.value if person.email_status is not None else None,
        )

    return Tool(
        name=TOOL_NAME,
        version=TOOL_VERSION,
        description=(
            "Enrich a known person by email, including email verification status. Never "
            "silently overwrites higher-confidence data with a lower-confidence result "
            "(CLAUDE.md §12.4)."
        ),
        input_model=EnrichPersonInput,
        handler=handler,
    )
