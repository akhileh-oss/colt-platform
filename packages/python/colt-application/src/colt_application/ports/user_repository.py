"""User repository ports.

Two ports, deliberately not one, because they have different trust boundaries (ADR-0005):

* ``UserDirectory`` looks a user up by the identity provider's subject claim, *before* an
  organization is known — this is how tenant resolution begins. It must only ever be called
  with a value that came from a verified JWT, never from client-supplied input.
* ``UserRepository`` is tenant-scoped: every implementation is bound to one organization at
  construction and cannot be asked for a user outside it.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from colt_domain import User


class UserDirectory(Protocol):
    """Looks up a user across all organizations, by verified external identity only."""

    async def find_by_external_auth_id(self, external_auth_id: str) -> User | None: ...


class UserRepository(Protocol):
    """Tenant-scoped. An implementation is bound to one organization_id at construction."""

    async def get(self, user_id: UUID) -> User | None: ...

    async def list_active(self) -> list[User]: ...
