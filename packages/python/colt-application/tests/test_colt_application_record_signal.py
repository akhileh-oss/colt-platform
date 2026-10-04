from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from colt_application.use_cases.record_signal import RecordSignal
from colt_domain import Signal


class FakeSignalRepository:
    def __init__(self) -> None:
        self.added: list[Signal] = []

    async def add(self, **kwargs: object) -> Signal:
        kwargs["raw_payload"] = kwargs.get("raw_payload") or {}
        signal = Signal(
            id=uuid4(),
            organization_id=uuid4(),
            created_at=datetime.now(UTC),
            **kwargs,  # type: ignore[arg-type]
        )
        self.added.append(signal)
        return signal

    async def get(self, signal_id: object) -> Signal | None:
        return next((s for s in self.added if s.id == signal_id), None)


@pytest.mark.asyncio
async def test_records_a_signal_with_the_judgment_fields_passed_through_unchanged() -> None:
    repo = FakeSignalRepository()
    record = RecordSignal(repo)

    signal = await record(
        company_id=uuid4(),
        signal_type="funding",
        observed_at=datetime.now(UTC),
        event_at=datetime.now(UTC),
        confidence=0.85,
        summary="Acme Rockets raised a $20M Series B.",
        business_implication="Likely to expand its engineering team and budget for new tooling.",
    )

    assert signal.signal_type == "funding"
    assert signal.confidence == 0.85
    assert signal.business_implication == (
        "Likely to expand its engineering team and budget for new tooling."
    )
    assert repo.added == [signal]
