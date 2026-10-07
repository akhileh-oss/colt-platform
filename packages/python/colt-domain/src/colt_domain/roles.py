"""Roles and capability-based permissions (CLAUDE.md §26.2).

A closed set, not something an agent or a migration invents. Adding a role or permission is a
code change, reviewed like any other authorization change.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class Role(StrEnum):
    """The minimum roles CLAUDE.md §26.2 requires."""

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    SALES = "SALES"
    MARKETING = "MARKETING"
    VIEWER = "VIEWER"
    SERVICE_AGENT = "SERVICE_AGENT"


class Permission(StrEnum):
    """Capability strings (CLAUDE.md §26.2). Checked, never inferred from a role name."""

    COMPANY_READ = "company:read"
    COMPANY_WRITE = "company:write"
    LEAD_READ = "lead:read"
    LEAD_WRITE = "lead:write"
    CAMPAIGN_READ = "campaign:read"
    CAMPAIGN_WRITE = "campaign:write"
    CAMPAIGN_LAUNCH = "campaign:launch"
    MESSAGE_APPROVE = "message:approve"
    MESSAGE_SEND = "message:send"
    OPPORTUNITY_READ = "opportunity:read"
    OPPORTUNITY_WRITE = "opportunity:write"
    CRM_WRITE = "crm:write"
    AGENT_RUN = "agent:run"
    AGENT_CONFIGURE = "agent:configure"
    SETTINGS_ADMIN = "settings:admin"


#: Default role → permission matrix. Additive only: a role has exactly the permissions listed
#: here, nothing implied by name. VIEWER is read-only everywhere; OWNER has everything.
DEFAULT_ROLE_PERMISSIONS: Final[dict[Role, frozenset[Permission]]] = {
    Role.OWNER: frozenset(Permission),
    Role.ADMIN: frozenset(Permission) - {Permission.SETTINGS_ADMIN},
    Role.MANAGER: frozenset(
        {
            Permission.COMPANY_READ,
            Permission.COMPANY_WRITE,
            Permission.LEAD_READ,
            Permission.LEAD_WRITE,
            Permission.CAMPAIGN_READ,
            Permission.CAMPAIGN_WRITE,
            Permission.CAMPAIGN_LAUNCH,
            Permission.MESSAGE_APPROVE,
            Permission.OPPORTUNITY_READ,
            Permission.OPPORTUNITY_WRITE,
            Permission.CRM_WRITE,
            Permission.AGENT_RUN,
        }
    ),
    Role.SALES: frozenset(
        {
            Permission.COMPANY_READ,
            Permission.LEAD_READ,
            Permission.LEAD_WRITE,
            Permission.CAMPAIGN_READ,
            Permission.MESSAGE_APPROVE,
            Permission.OPPORTUNITY_READ,
            Permission.OPPORTUNITY_WRITE,
            Permission.CRM_WRITE,
        }
    ),
    Role.MARKETING: frozenset(
        {
            Permission.COMPANY_READ,
            Permission.LEAD_READ,
            Permission.CAMPAIGN_READ,
            Permission.CAMPAIGN_WRITE,
            Permission.CAMPAIGN_LAUNCH,
            Permission.MESSAGE_APPROVE,
            Permission.OPPORTUNITY_READ,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Permission.COMPANY_READ,
            Permission.LEAD_READ,
            Permission.CAMPAIGN_READ,
            Permission.OPPORTUNITY_READ,
        }
    ),
    # A service identity is granted exactly what its workflow needs, never a human role
    # (CLAUDE.md §26.3). No standing permissions by default.
    Role.SERVICE_AGENT: frozenset(),
}


def permissions_for(role: Role) -> frozenset[Permission]:
    """The permissions a role carries. Every ``Role`` is covered; a missing entry is a bug."""
    return DEFAULT_ROLE_PERMISSIONS[role]


def role_has_permission(role: Role, permission: Permission) -> bool:
    return permission in permissions_for(role)
