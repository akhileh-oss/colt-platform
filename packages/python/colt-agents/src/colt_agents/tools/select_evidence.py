"""`select_evidence` (CLAUDE.md §12.8) — the one validating tool `PersonalizationAgent` must
call before it can finalize a `PersonalizationStrategy`.

Re-checks every claimed `evidence_id` against this organization's real `Evidence` rows -
fails loud (the tool result becomes an `is_error` result the model sees and must correct) if
any cited id was hallucinated or belongs to a different organization.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from colt_agents.tool import Tool
from colt_application.use_cases.select_personalization_evidence import (
    SelectPersonalizationEvidence,
)

TOOL_NAME = "select_evidence"
TOOL_VERSION = "v1"


class SelectEvidenceInput(BaseModel):
    evidence_ids: list[UUID]


class SelectEvidenceOutput(BaseModel):
    verified_evidence_ids: list[UUID]


def build_select_evidence_tool(select_evidence: SelectPersonalizationEvidence) -> Tool:
    async def handler(validated_input: BaseModel) -> BaseModel:
        assert isinstance(validated_input, SelectEvidenceInput)  # noqa: S101 - guards an
        # internal contract this tool's own `input_model` guarantees; never reachable with real
        # input.
        verified = await select_evidence(validated_input.evidence_ids)
        return SelectEvidenceOutput(verified_evidence_ids=[item.id for item in verified])

    return Tool(
        name=TOOL_NAME,
        version=TOOL_VERSION,
        description=(
            "Confirm that the evidence_ids you intend to personalize with actually exist. "
            "Fails if evidence_ids is empty, or if any id does not resolve to a real recorded "
            "Evidence row - a personalization strategy must never cite evidence that was not "
            "actually recorded (CLAUDE.md §12.8: 'no unsupported claims')."
        ),
        input_model=SelectEvidenceInput,
        handler=handler,
    )
