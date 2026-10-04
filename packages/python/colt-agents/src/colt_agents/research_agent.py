"""The ResearchAgent (CLAUDE.md §12.5): produces an evidence-backed intelligence dossier.

`DossierClaim.evidence_ids` is validated so that a `FACT` claim can never be empty — this is
what makes Milestone 10's acceptance criterion ("every factual claim produced by the agent is
linked to stored evidence") structurally unviolable rather than merely a prompt instruction the
model might ignore. `INFERENCE`/`HYPOTHESIS` claims may still cite evidence_ids, but are not
required to — an inference is the agent connecting dots across facts, not a new sourced claim.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, model_validator

from colt_agents.definition import AgentDefinition
from colt_config import ModelClass

AGENT_NAME = "research-agent"
AGENT_VERSION = "v1"


class ClaimType(StrEnum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"


class DossierClaim(BaseModel):
    claim_type: ClaimType
    text: str
    evidence_ids: list[UUID] = []

    @model_validator(mode="after")
    def _fact_requires_evidence(self) -> DossierClaim:
        if self.claim_type == ClaimType.FACT and not self.evidence_ids:
            raise ValueError(
                "A FACT claim must cite at least one evidence_id — record it via "
                "record_evidence first (CLAUDE.md §2.6)."
            )
        return self


class ResearchDossier(BaseModel):
    company_id: UUID
    summary: str
    claims: list[DossierClaim]


class ResearchAgentInput(BaseModel):
    company_id: UUID
    company_name: str
    company_domain: str


RESEARCH_AGENT_DEFINITION = AgentDefinition(
    name=AGENT_NAME,
    version=AGENT_VERSION,
    purpose=(
        "Research a company and produce an evidence-backed intelligence dossier, "
        "distinguishing FACT from INFERENCE from HYPOTHESIS (CLAUDE.md §12.5)."
    ),
    input_schema=ResearchAgentInput,
    output_schema=ResearchDossier,
    allowed_tools=frozenset({"search_web", "fetch_page", "record_evidence"}),
    model_policy=ModelClass.STANDARD,
    max_tool_calls=20,
    timeout_seconds=300.0,
)
