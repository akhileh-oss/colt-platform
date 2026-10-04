"""`score_lead` (CLAUDE.md §10.8, §12.7, §21) — the one write tool `ScoringAgent` may call."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel

from colt_agents.tool import Tool
from colt_application.use_cases.score_lead import ScoreLead

TOOL_NAME = "score_lead"
TOOL_VERSION = "v1"


class ScoreLeadInput(BaseModel):
    lead_id: UUID
    icp_fit: float
    persona_fit: float
    signal_strength: float
    timing: float
    model_assessment: float
    confidence: float | None = None


class ScoreLeadOutput(BaseModel):
    lead_score_id: UUID
    overall_score: float
    reason_codes: list[str]
    qualified: bool


def build_score_lead_tool(score_lead: ScoreLead) -> Tool:
    async def handler(validated_input: BaseModel) -> BaseModel:
        assert isinstance(validated_input, ScoreLeadInput)  # noqa: S101 - guards an internal
        # contract this tool's own `input_model` guarantees; never reachable with real input.
        score, lead = await score_lead(
            lead_id=validated_input.lead_id,
            icp_fit=validated_input.icp_fit,
            persona_fit=validated_input.persona_fit,
            signal_strength=validated_input.signal_strength,
            timing=validated_input.timing,
            model_assessment=validated_input.model_assessment,
            confidence=validated_input.confidence,
            now=datetime.now(UTC),
        )
        return ScoreLeadOutput(
            lead_score_id=score.id,
            overall_score=score.overall_score,
            reason_codes=score.reason_codes,
            qualified=lead.status.value == "QUALIFIED",
        )

    return Tool(
        name=TOOL_NAME,
        version=TOOL_VERSION,
        description=(
            "Score a lead. Computes the deterministic overall_score and qualification "
            "decision from your five component scores - these are never the model's own "
            "free-text judgment (CLAUDE.md §12.7: 'Never allow vibes alone to determine "
            "qualification'). Appends a new history row; never overwrites a prior score."
        ),
        input_model=ScoreLeadInput,
        handler=handler,
    )
