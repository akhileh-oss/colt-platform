"""The signal trigger source port (CLAUDE.md §12.6's "source ingestion").

A "why now" signal arrives from outside Colt — a webhook, a scheduled feed poll, a manual
trigger — as one raw event. `SignalAgent` never trusts this payload's content directly (§41.1:
retrieved content is data, not instructions); it reasons over it and decides what, if anything,
to record as a `Signal` via `record_signal`.

CLAUDE.md names no specific real signal-source provider (unlike `SearchProvider`/
`EnrichmentProvider`, both named in §28.2) — Milestone 12's acceptance criterion explicitly
accepts "a real/mock trigger," so only the port and its test double are built this milestone; a
real adapter (a specific news feed, webhook, or CRM-event source) is a natural follow-up once
one is chosen, not a gap in this one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SignalTriggerPayload:
    company_id: UUID
    source: str
    observed_at: datetime
    source_url: str | None = None
    source_type: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


class SignalTriggerSource(Protocol):
    async def poll(self) -> list[SignalTriggerPayload]: ...
