"""`record_evidence` (CLAUDE.md §16.2: Research agents may write "Evidence only").

The one write tool a `ResearchAgent` may call — writing an `Evidence` row is not the kind of
dangerous external side effect §41.2 warns against exposing during untrusted-content
interpretation (sending email, mutating a CRM record); it is the agent's actual job output,
scoped exactly as narrowly as the permission matrix allows.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from pydantic import BaseModel

from colt_agents.tool import Tool
from colt_application import RecordEvidence

TOOL_NAME = "record_evidence"
TOOL_VERSION = "v1"


class RecordEvidenceInput(BaseModel):
    entity_type: str
    entity_id: UUID
    claim: str
    source_url: str
    source_date: date | None = None
    excerpt: str | None = None
    confidence: float | None = None


class RecordEvidenceOutput(BaseModel):
    evidence_id: UUID
    verification_status: str


def build_record_evidence_tool(record_evidence: RecordEvidence) -> Tool:
    async def handler(validated_input: BaseModel) -> BaseModel:
        assert isinstance(validated_input, RecordEvidenceInput)  # noqa: S101 - guards an
        # internal contract this tool's own `input_model` guarantees; never reachable with
        # real input.
        evidence = await record_evidence(
            entity_type=validated_input.entity_type,
            entity_id=validated_input.entity_id,
            claim=validated_input.claim,
            source_url=validated_input.source_url,
            observed_at=datetime.now(UTC),
            source_date=validated_input.source_date,
            excerpt=validated_input.excerpt,
            confidence=validated_input.confidence,
        )
        return RecordEvidenceOutput(
            evidence_id=evidence.id, verification_status=evidence.verification_status.value
        )

    return Tool(
        name=TOOL_NAME,
        version=TOOL_VERSION,
        description=(
            "Record one sourced, dated claim as evidence. Call this before referencing a FACT "
            "claim's evidence_id in your final dossier — a claim is not stored evidence until "
            "this tool returns its evidence_id. Never invent a source URL (CLAUDE.md §2.6)."
        ),
        input_model=RecordEvidenceInput,
        handler=handler,
    )
