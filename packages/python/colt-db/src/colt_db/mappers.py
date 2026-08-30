"""ORM row ↔ domain entity conversion.

The only place that knows both the SQLAlchemy model shape and the domain entity shape. Kept
tiny and boring on purpose: if this function grows business logic, that logic is in the wrong
layer.
"""

from __future__ import annotations

from colt_db.models.organization import OrganizationModel
from colt_db.models.user import UserModel
from colt_domain import Organization, OrganizationStatus, Role, User, UserStatus


def organization_to_domain(model: OrganizationModel) -> Organization:
    return Organization(
        id=model.id,
        name=model.name,
        slug=model.slug,
        status=OrganizationStatus(model.status),
        settings=model.settings,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def user_to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        organization_id=model.organization_id,
        external_auth_id=model.external_auth_id,
        email=model.email,
        name=model.name,
        role=Role(model.role),
        status=UserStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
