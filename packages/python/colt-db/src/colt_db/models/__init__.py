"""SQLAlchemy ORM models.

Import every model module here so Alembic's autogenerate (and `Base.metadata.create_all` in
tests) sees the full schema from one import.
"""

from colt_db.models.organization import OrganizationModel
from colt_db.models.user import UserModel

__all__ = ["OrganizationModel", "UserModel"]
