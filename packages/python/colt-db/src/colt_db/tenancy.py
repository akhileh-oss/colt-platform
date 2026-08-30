"""Tenant scoping (CLAUDE.md §27, §9.7, ADR-0005).

Two independent layers enforce the same boundary. Every repository built on
``TenantScopedRepository`` must filter by ``self.organization_id`` explicitly — enforced by
routing every query through ``_select_scoped``, which adds that filter itself, rather than
subclasses calling ``select()`` directly. Separately, the session's PostgreSQL transaction has
``app.current_organization_id`` set, and Row-Level Security policies (defined in the Alembic
migration) deny any row that does not match it — so a bug that manages to skip the first layer
still returns nothing, not someone else's data.
"""

from __future__ import annotations

from typing import Any, Self
from uuid import UUID

from sqlalchemy import Select, select, text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_tenant_context(session: AsyncSession, organization_id: UUID) -> None:
    """Bind ``app.current_organization_id`` for the session's current transaction.

    ``SET LOCAL`` rather than ``SET``: it resets automatically at COMMIT/ROLLBACK, so a pooled
    connection can never carry one request's organization into another's.

    PostgreSQL's ``SET`` family does not accept bind parameters over the wire protocol at all —
    the value must be inlined. This is safe here specifically because the input is a
    ``uuid.UUID`` object, whose ``str()`` is always exactly 36 well-formed hex/hyphen
    characters; the ``isinstance`` check exists so a future caller cannot pass an unvalidated
    string through this function and reintroduce that risk.
    """
    if not isinstance(organization_id, UUID):
        raise TypeError(f"organization_id must be a UUID, got {type(organization_id).__name__}.")
    await session.execute(text(f"SET LOCAL app.current_organization_id = '{organization_id}'"))


class TenantScopedRepository:
    """Base for every repository scoped to one organization.

    Never construct a subclass with ``__init__`` directly in production code — use ``create()``,
    which also binds the RLS session variable. A repository built without it leaves RLS unset
    for the session, which the policies defined in the Alembic migration treat as deny-all: the
    failure mode of skipping this is "no rows", not "wrong rows".
    """

    def __init__(self, session: AsyncSession, organization_id: UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    @classmethod
    async def create(cls, session: AsyncSession, organization_id: UUID) -> Self:
        await set_tenant_context(session, organization_id)
        return cls(session, organization_id)

    @property
    def organization_id(self) -> UUID:
        return self._organization_id

    def _select_scoped(self, model: type[Any]) -> Select[Any]:
        """``select(model)`` pre-filtered to this repository's organization.

        Subclasses should always query through this rather than a bare ``select()`` — it is the
        structural half of the enforcement this class exists for.
        """
        if not hasattr(model, "organization_id"):
            raise TypeError(
                f"{model.__name__} has no organization_id column — it cannot be tenant-scoped. "
                "Use a plain select() if this model is genuinely not tenant-owned."
            )
        return select(model).where(model.organization_id == self._organization_id)


class RlsBypassRoleError(RuntimeError):
    """The application's database connection can bypass Row-Level Security.

    Raised at startup, not discovered later as a data leak. A Postgres superuser, or any role
    granted BYPASSRLS, ignores every RLS policy unconditionally — this was the actual root cause
    the first time this was tested (see ADR-0005), and it fails silently: queries keep working,
    they just stop being tenant-isolated. This check exists so a misconfigured DATABASE_URL
    (pointed at the migration role, for instance) is a hard failure instead of a quiet one.
    """


async def assert_not_bypassing_rls(session: AsyncSession) -> None:
    """Raise ``RlsBypassRoleError`` if the current connection's role bypasses RLS."""
    result = await session.execute(
        text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
    )
    bypasses = result.scalar_one()
    if bypasses:
        raise RlsBypassRoleError(
            "The database role this connection uses can bypass Row-Level Security "
            "(it is a superuser or has BYPASSRLS). Row-Level Security policies would be "
            "silently inert. Point DATABASE_URL at a restricted application role instead."
        )
