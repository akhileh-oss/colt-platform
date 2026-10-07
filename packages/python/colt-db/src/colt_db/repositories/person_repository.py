"""Tenant-scoped repository for `Person` (CLAUDE.md §10.4)."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from colt_db.mappers import person_to_domain
from colt_db.models.person import PersonModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import DuplicateIdentityError, EmailStatus, Person


class SqlAlchemyPersonRepository(TenantScopedRepository):
    async def add(
        self,
        *,
        company_id: UUID,
        full_name: str,
        first_name: str | None = None,
        last_name: str | None = None,
        title: str | None = None,
        seniority: str | None = None,
        department: str | None = None,
        email: str | None = None,
        email_status: EmailStatus | None = None,
        linkedin_url: str | None = None,
        location: str | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> Person:
        model = PersonModel(
            organization_id=self.organization_id,
            company_id=company_id,
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            title=title,
            seniority=seniority,
            department=department,
            email=email,
            email_status=email_status.value if email_status is not None else None,
            linkedin_url=linkedin_url,
            location=location,
            source_metadata=source_metadata or {},
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            if "uq_people_org_email" in str(exc.orig):
                raise DuplicateIdentityError(
                    f"A person with email={email!r} already exists in this organization "
                    "(lost a concurrent insert race)."
                ) from exc
            raise
        await self._session.refresh(model)
        return person_to_domain(model)

    async def get(self, person_id: UUID) -> Person | None:
        stmt = self._select_scoped(PersonModel).where(PersonModel.id == person_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return person_to_domain(model) if model is not None else None

    async def find_by_email(self, email: str) -> Person | None:
        stmt = self._select_scoped(PersonModel).where(PersonModel.email == email)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return person_to_domain(model) if model is not None else None

    async def find_by_linkedin_url(self, linkedin_url: str) -> Person | None:
        stmt = self._select_scoped(PersonModel).where(PersonModel.linkedin_url == linkedin_url)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return person_to_domain(model) if model is not None else None

    async def list_by_company(self, company_id: UUID) -> list[Person]:
        """Identity resolution's §22 layer 4/5 (company + normalized name) compares in Python,
        not SQL — `full_name` is stored as given, display-cased, with no normalized column to
        index on, and a company's contact list is small enough that this is cheap."""
        stmt = self._select_scoped(PersonModel).where(PersonModel.company_id == company_id)
        models = (await self._session.execute(stmt)).scalars().all()
        return [person_to_domain(model) for model in models]

    async def list_all(self) -> list[Person]:
        """Every person in this organization — the message-performance analytics read model
        (Milestone 22) resolves a message's recipient persona (`seniority`) over this."""
        stmt = self._select_scoped(PersonModel)
        models = (await self._session.execute(stmt)).scalars().all()
        return [person_to_domain(model) for model in models]

    async def find_by_provider_id(self, provider: str, provider_id: str) -> Person | None:
        """Identity resolution's top-priority layer (`CLAUDE.md` §22) — see
        `SqlAlchemyCompanyRepository.find_by_provider_id`."""
        stmt = self._select_scoped(PersonModel).where(
            PersonModel.source_metadata["provider"].astext == provider,
            PersonModel.source_metadata["provider_id"].astext == provider_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return person_to_domain(model) if model is not None else None

    async def update(self, person_id: UUID, **fields: Any) -> Person:
        """Set only the given fields; see `SqlAlchemyCompanyRepository.update`. `email_status`
        is accepted as an `EmailStatus` and stored as its `.value`."""
        stmt = self._select_scoped(PersonModel).where(PersonModel.id == person_id)
        model = cast(PersonModel, (await self._session.execute(stmt)).scalar_one())
        for key, value in fields.items():
            if value is None:
                continue
            if key == "email_status" and isinstance(value, EmailStatus):
                value = value.value
            setattr(model, key, value)
        await self._session.flush()
        await self._session.refresh(model)
        return person_to_domain(model)
