"""Application-layer errors.

Raised by use cases, caught at the API boundary and mapped to the CLAUDE.md §36 error taxonomy
there — this package does not know about HTTP status codes.
"""

from __future__ import annotations


class ApplicationError(Exception):
    """Base for every application-layer failure."""


class OrganizationContextError(ApplicationError):
    """Raised when a request's organization context cannot be resolved.

    Deliberately one exception type for several distinct causes (unknown identity, inactive
    user, inactive organization): the API boundary should fail every one of them closed the
    same way — reject the request — rather than leaking which specific case occurred, which
    would let an attacker enumerate valid external_auth_ids.
    """


class NotFoundError(ApplicationError):
    """Raised when a use case's target entity does not exist in the caller's organization.

    Covers both "truly doesn't exist" and "exists, but in a different organization" — the
    tenant-scoped repository ports this package depends on return the same `None` for both
    (CLAUDE.md §2.8), so a use case cannot distinguish them, and should not try to.
    """


class CampaignValidationError(ApplicationError):
    """Raised when a campaign's definition fails `campaign_state.validate_campaign_definition`.

    Carries every failing rule, not just the first, so a caller can report all of them at once
    rather than making the user fix one field at a time.
    """

    def __init__(self, issues: list[str]) -> None:
        super().__init__("Campaign definition is invalid: " + "; ".join(issues))
        self.issues = issues


class InvalidCampaignTransitionError(ApplicationError):
    """Raised when a use case asks for a `CampaignStatus` transition `campaign_state` forbids."""

    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"Cannot transition a campaign from {current} to {target}.")
        self.current = current
        self.target = target
