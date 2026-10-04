"""`DiscoverPerson` (CLAUDE.md §12.3, §22) — the use case `colt-agents`' `search_people` tool
calls to turn one discovered candidate into a deduplicated `Person` row, scoped to an
already-discovered `Company`.

Plain scalar arguments, not a `colt_integrations.enrichment.PersonCandidate` — see
`DiscoverCompany`'s docstring for why.

Matches in §22's priority order: exact `provider_id`, then normalized email, then normalized
LinkedIn URL, then — only once those trustworthy identifiers are exhausted, and only when the
candidate's own confidence clears `DEFAULT_NAME_MATCH_CONFIDENCE_THRESHOLD` — company +
normalized full name. Never a fuzzy name comparison (§22 explicitly forbids it); "normalized"
here means exact-equal after `normalize_name`, nothing more.
"""

from __future__ import annotations

from uuid import UUID

from colt_application.identity import (
    DEFAULT_NAME_MATCH_CONFIDENCE_THRESHOLD,
    normalize_email,
    normalize_linkedin_url,
    normalize_name,
)
from colt_application.ports.person_repository import PersonRepository
from colt_domain import Person


class DiscoverPerson:
    def __init__(
        self,
        people: PersonRepository,
        *,
        name_match_confidence_threshold: float = DEFAULT_NAME_MATCH_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._people = people
        self._name_match_confidence_threshold = name_match_confidence_threshold

    async def __call__(
        self,
        *,
        company_id: UUID,
        full_name: str,
        provider: str,
        confidence: float,
        provider_id: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        title: str | None = None,
        email: str | None = None,
        linkedin_url: str | None = None,
    ) -> tuple[Person, bool]:
        """Returns `(person, created)` — `created` is `False` on a dedup hit."""
        if provider_id is not None:
            existing = await self._people.find_by_provider_id(provider, provider_id)
            if existing is not None:
                return existing, False

        normalized_email = normalize_email(email) if email is not None else None
        if normalized_email is not None:
            existing = await self._people.find_by_email(normalized_email)
            if existing is not None:
                return existing, False

        normalized_linkedin = (
            normalize_linkedin_url(linkedin_url) if linkedin_url is not None else None
        )
        if normalized_linkedin is not None:
            existing = await self._people.find_by_linkedin_url(normalized_linkedin)
            if existing is not None:
                return existing, False

        if confidence >= self._name_match_confidence_threshold:
            normalized_candidate_name = normalize_name(full_name)
            for person in await self._people.list_by_company(company_id):
                if normalize_name(person.full_name) == normalized_candidate_name:
                    return person, False

        person = await self._people.add(
            company_id=company_id,
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            title=title,
            email=normalized_email,
            linkedin_url=normalized_linkedin,
            source_metadata={
                "provider": provider,
                "provider_id": provider_id,
                "confidence": confidence,
            },
        )
        return person, True
