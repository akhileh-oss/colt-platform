"""`record_signal` (CLAUDE.md §10.5, §12.6) — the one write tool `SignalAgent` may call.

Computes and returns `rank` right after persisting, via `colt_application.signals.rank_signal`
— a deterministic function of the signal's own stored fields, not re-derived by the model.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from pydantic import BaseModel

from colt_agents.tool import Tool
from colt_application.signals import rank_signal
from colt_application.use_cases.record_signal import RecordSignal

TOOL_NAME = "record_signal"
TOOL_VERSION = "v1"


class RecordSignalInput(BaseModel):
    company_id: UUID
    signal_type: str
    source_url: str | None = None
    source_type: str | None = None
    event_date: date | None = None
    confidence: float | None = None
    summary: str | None = None
    business_implication: str | None = None


class RecordSignalOutput(BaseModel):
    signal_id: UUID
    rank: float


def build_record_signal_tool(record_signal: RecordSignal) -> Tool:
    async def handler(validated_input: BaseModel) -> BaseModel:
        assert isinstance(validated_input, RecordSignalInput)  # noqa: S101 - guards an
        # internal contract this tool's own `input_model` guarantees; never reachable with
        # real input.
        now = datetime.now(UTC)
        event_at = (
            datetime.combine(validated_input.event_date, datetime.min.time(), tzinfo=UTC)
            if validated_input.event_date is not None
            else None
        )
        signal = await record_signal(
            company_id=validated_input.company_id,
            signal_type=validated_input.signal_type,
            observed_at=now,
            source_url=validated_input.source_url,
            source_type=validated_input.source_type,
            event_at=event_at,
            confidence=validated_input.confidence,
            summary=validated_input.summary,
            business_implication=validated_input.business_implication,
        )
        rank = rank_signal(
            signal_type=signal.signal_type,
            confidence=signal.confidence,
            event_at=signal.event_at,
            observed_at=signal.observed_at,
            now=now,
        )
        return RecordSignalOutput(signal_id=signal.id, rank=rank)

    return Tool(
        name=TOOL_NAME,
        version=TOOL_VERSION,
        description=(
            "Record one 'why now' signal about a company. Call this once you have decided "
            "signal_type, confidence, summary, and business_implication from a polled event - "
            "never fabricate a signal with no polled event behind it."
        ),
        input_model=RecordSignalInput,
        handler=handler,
    )
