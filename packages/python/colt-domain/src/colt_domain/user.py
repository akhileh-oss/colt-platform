"""The User entity (CLAUDE.md §10.2).

Organization membership and role live here, not in the identity provider's token — Keycloak
proves *who* is asking; this table is the sole authority on *which organization* they belong to
and *what they can do there* (ADR-0005). Never trust an organization_id from anywhere else.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from colt_domain.roles import Permission, Role, role_has_permission


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INVITED = "INVITED"
    SUSPENDED = "SUSPENDED"
    DEACTIVATED = "DEACTIVATED"


class User(BaseModel):
    """A person or service identity within one organization."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    #: The identity provider's subject claim (Keycloak `sub`). Unique per provider, not
    #: necessarily meaningful outside it.
    external_auth_id: str
    email: EmailStr
    name: str
    role: Role
    status: UserStatus = UserStatus.ACTIVE
    created_at: datetime
    updated_at: datetime

    @field_validator("external_auth_id")
    @classmethod
    def _external_auth_id_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("external_auth_id must not be blank.")
        return value

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("User name must not be blank.")
        return value

    @property
    def is_active(self) -> bool:
        return self.status is UserStatus.ACTIVE

    @property
    def is_service_identity(self) -> bool:
        return self.role is Role.SERVICE_AGENT

    def has_permission(self, permission: Permission) -> bool:
        """Whether this user's role carries the given permission.

        Does not check ``is_active``: an authorization check on a suspended user's stale role is
        meaningless, and callers must reject an inactive user before reaching this — see
        ``PolicyDeniedError`` usage in colt-api's auth dependencies.
        """
        return role_has_permission(self.role, permission)

    def with_role(self, role: Role, *, at: datetime) -> Self:
        return self.model_copy(update={"role": role, "updated_at": at})

    def with_status(self, status: UserStatus, *, at: datetime) -> Self:
        return self.model_copy(update={"status": status, "updated_at": at})
