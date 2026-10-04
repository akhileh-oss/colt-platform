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
