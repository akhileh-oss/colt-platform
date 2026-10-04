"""`FakeSignalTriggerSource` — the mock trigger (CLAUDE.md §12.6, §0.4, §28.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from colt_integrations.signals.fake import FakeSignalTriggerSource
from colt_integrations.signals.port import SignalTriggerPayload


async def test_poll_returns_the_configured_payloads() -> None:
    payload = SignalTriggerPayload(company_id=uuid4(), source="mock", observed_at=datetime.now(UTC))
    source = FakeSignalTriggerSource([payload])

    assert await source.poll() == [payload]


async def test_poll_drains_the_queue() -> None:
    payload = SignalTriggerPayload(company_id=uuid4(), source="mock", observed_at=datetime.now(UTC))
    source = FakeSignalTriggerSource([payload])

    await source.poll()

    assert await source.poll() == []


async def test_an_empty_source_returns_no_payloads() -> None:
    source = FakeSignalTriggerSource()

    assert await source.poll() == []
