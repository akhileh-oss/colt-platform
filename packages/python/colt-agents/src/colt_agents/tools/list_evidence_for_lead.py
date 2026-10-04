"""`list_evidence_for_lead` (CLAUDE.md §12.8) — the read-only tool `PersonalizationAgent` calls
to see what evidence actually exists before selecting any of it."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from colt_agents.tool import Tool
from colt_application.use_cases.list_evidence_for_lead import ListEvidenceForLead

TOOL_NAME = "list_evidence_for_lead"
TOOL_VERSION = "v1"


class ListEvidenceForLeadInput(BaseModel):
    lead_id: UUID


class EvidenceSummary(BaseModel):
    evidence_id: UUID
    claim: str
    confidence: float | None
    verification_status: str


class ListEvidenceForLeadOutput(BaseModel):
    evidence: list[EvidenceSummary]


def build_list_evidence_for_lead_tool(list_evidence_for_lead: ListEvidenceForLead) -> Tool:
    async def handler(validated_input: BaseModel) -> BaseModel:
        assert isinstance(validated_input, ListEvidenceForLeadInput)  # noqa: S101 - guards an
        # internal contract this tool's own `input_model` guarantees; never reachable with real
        # input.
        evidence = await list_evidence_for_lead(validated_input.lead_id)
        return ListEvidenceForLeadOutput(
            evidence=[
                EvidenceSummary(
                    evidence_id=item.id,
                    claim=item.claim,
                    confidence=item.confidence,
                    verification_status=item.verification_status.value,
                )
                for item in evidence
            ]
        )

    return Tool(
        name=TOOL_NAME,
        version=TOOL_VERSION,
        description=(
            "List every piece of recorded evidence about this lead's company and person. "
            "Call this before select_evidence - you can only select evidence_ids that appear "
            "here."
        ),
        input_model=ListEvidenceForLeadInput,
        handler=handler,
    )
