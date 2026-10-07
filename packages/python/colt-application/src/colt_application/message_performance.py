"""Deterministic message-performance summary (CLAUDE.md §68, Milestone 22's "message
performance" Build item), grouped by `(prompt_version, persona)` — CLAUDE.md names "message
variants" (the acceptance criterion's own phrase) without defining one; `Message.prompt_version`
(already recorded by `DraftMessage`, Milestone 15) is this milestone's own documented choice of
variant dimension, the same "the milestone building it makes the documented call" pattern
`CampaignStatus`/`Urgency` already establish. `persona` resolves a message's recipient's
`Person.seniority` through `Lead.person_id` — the acceptance criterion's own "personas" word,
answered here since no dedicated Build item names it separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from colt_domain import Lead, Message, Person

_UNKNOWN_VARIANT = "unknown"
_UNKNOWN_PERSONA = "unknown"


@dataclass(frozen=True, slots=True)
class MessagePerformanceRow:
    prompt_version: str
    persona: str
    drafted_count: int
    sent_count: int
    approved_count: int


@dataclass(slots=True)
class _Bucket:
    drafted_count: int = 0
    sent_count: int = 0
    approved_count: int = 0


def summarize_message_performance(
    messages: list[Message], leads: list[Lead], persons: list[Person]
) -> list[MessagePerformanceRow]:
    person_id_by_lead: dict[UUID, UUID] = {lead.id: lead.person_id for lead in leads}
    seniority_by_person: dict[UUID, str] = {
        person.id: (person.seniority or _UNKNOWN_PERSONA) for person in persons
    }

    totals: dict[tuple[str, str], _Bucket] = {}
    for message in messages:
        variant = message.prompt_version or _UNKNOWN_VARIANT
        person_id = person_id_by_lead.get(message.lead_id)
        persona = (
            seniority_by_person.get(person_id, _UNKNOWN_PERSONA)
            if person_id
            else (_UNKNOWN_PERSONA)
        )
        bucket = totals.setdefault((variant, persona), _Bucket())
        bucket.drafted_count += 1
        if message.status == "SENT":
            bucket.sent_count += 1
        if message.approval_status == "APPROVED":
            bucket.approved_count += 1

    return [
        MessagePerformanceRow(
            prompt_version=variant,
            persona=persona,
            drafted_count=bucket.drafted_count,
            sent_count=bucket.sent_count,
            approved_count=bucket.approved_count,
        )
        for (variant, persona), bucket in sorted(totals.items())
    ]
