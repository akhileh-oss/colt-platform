"""The EnrichmentAgent (CLAUDE.md §12.4): resolves and enriches company/person data, using
source precedence and confidence rules rather than silently overwriting higher-confidence data
(enforced by `colt_application.use_cases.{EnrichCompany,EnrichPerson}`, not by this agent's
own judgment).
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, model_validator

from colt_agents.definition import AgentDefinition
from colt_config import ModelClass

AGENT_NAME = "enrichment-agent"
AGENT_VERSION = "v1"


class EnrichedCompanySummary(BaseModel):
    company_id: UUID
    industry: str | None
    employee_count: int | None
    country: str | None


class EnrichedPersonSummary(BaseModel):
    person_id: UUID
    title: str | None
    email_status: str | None


class EnrichmentAgentInput(BaseModel):
    """Enriches exactly one target per run: a company (`company_id` + `company_domain`) or a
    person (`person_id` + `person_email`), never both — a `model_validator` enforces this
    rather than letting the model send an ambiguous mix."""

    company_id: UUID | None = None
    company_domain: str | None = None
    person_id: UUID | None = None
    person_email: str | None = None

    @model_validator(mode="after")
    def _exactly_one_target(self) -> EnrichmentAgentInput:
        is_company_target = self.company_id is not None and self.company_domain is not None
        is_person_target = self.person_id is not None and self.person_email is not None
        if is_company_target == is_person_target:
            raise ValueError(
                "Provide exactly one of (company_id + company_domain) or "
                "(person_id + person_email)."
            )
        return self


class EnrichmentAgentOutput(BaseModel):
    company: EnrichedCompanySummary | None = None
    person: EnrichedPersonSummary | None = None


ENRICHMENT_AGENT_DEFINITION = AgentDefinition(
    name=AGENT_NAME,
    version=AGENT_VERSION,
    purpose=(
        "Resolve and enrich company/person data using source precedence and confidence rules "
        "(CLAUDE.md §12.4)."
    ),
    input_schema=EnrichmentAgentInput,
    output_schema=EnrichmentAgentOutput,
    allowed_tools=frozenset({"enrich_company", "enrich_person"}),
    model_policy=ModelClass.FAST,
    max_tool_calls=5,
    timeout_seconds=60.0,
)
