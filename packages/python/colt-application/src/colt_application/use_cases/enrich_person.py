"""`EnrichPerson` (CLAUDE.md §12.4, §16.1's `verify_email`) — the use case `colt-agents`'
`enrich_person` tool calls. See `EnrichCompany` for the record-level confidence-precedence
rationale this mirrors, and `DiscoverCompany` for why this takes plain scalar arguments rather
than a `colt_integrations.enrichment.PersonCandidate`.

`email_verified` is a documented simplification of whatever string a real provider's own email
status actually returns (Apollo's docs confirm `"verified"` as one value, not the full enum):
`True` maps to `EmailStatus.VALID`, and anything else the provider reports maps to
`EmailStatus.UNKNOWN` rather than guessing it means `INVALID` — an email we could not confirm is
not the same claim as one we confirmed is bad.
"""

from __future__ import annotations

from uuid import UUID

from colt_application.identity import normalize_email, normalize_linkedin_url
from colt_application.ports.person_repository import PersonRepository
from colt_domain import EmailStatus, Person


def _email_status(email_verified: bool | None) -> EmailStatus | None:
    if email_verified is None:
        return None
    return EmailStatus.VALID if email_verified else EmailStatus.UNKNOWN


class EnrichPerson:
    def __init__(self, people: PersonRepository) -> None:
        self._people = people

    async def __call__(
        self,
        person_id: UUID,
        *,
        provider: str,
        confidence: float,
        provider_id: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        title: str | None = None,
        email: str | None = None,
        email_verified: bool | None = None,
        linkedin_url: str | None = None,
    ) -> Person:
        existing = await self._people.get(person_id)
        if existing is None:
            raise ValueError(f"No person {person_id} to enrich.")

        stored_confidence = float(existing.source_metadata.get("confidence", 0.0))
        if confidence < stored_confidence:
            return existing

        return await self._people.update(
            person_id,
            first_name=first_name,
            last_name=last_name,
            title=title,
            email=normalize_email(email) if email is not None else None,
            email_status=_email_status(email_verified),
            linkedin_url=normalize_linkedin_url(linkedin_url) if linkedin_url is not None else None,
            source_metadata={
                "provider": provider,
                "provider_id": provider_id,
                "confidence": confidence,
            },
        )
