"""Record one observed `Signal` (CLAUDE.md §10.5, §12.6) — the use case `colt-agents`'
`record_signal` tool calls.

Unlike `RecordEvidence`, nothing here is server-computed: `signal_type`/`confidence`/
`business_implication` are the judgment `SignalAgent` already formed from the raw trigger
payload it was given (§2.1 reserves deterministic computation for application code, not the
reverse) — this use case's only job is persistence through the repository port.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from colt_application.ports.signal_repository import SignalRepository
from colt_domain import Signal


class RecordSignal:
    def __init__(self, signals: SignalRepository) -> None:
        self._signals = signals

    async def __call__(
        self,
        *,
        company_id: UUID,
        signal_type: str,
        observed_at: datetime,
        person_id: UUID | None = None,
        source_url: str | None = None,
        source_type: str | None = None,
        event_at: datetime | None = None,
        confidence: float | None = None,
        summary: str | None = None,
        business_implication: str | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> Signal:
        return await self._signals.add(
            company_id=company_id,
            person_id=person_id,
            signal_type=signal_type,
            source_url=source_url,
            source_type=source_type,
            observed_at=observed_at,
            event_at=event_at,
            confidence=confidence,
            summary=summary,
            business_implication=business_implication,
            raw_payload=raw_payload,
        )
