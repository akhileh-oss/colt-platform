"""Domain-level errors every layer above the database can depend on without depending on
SQLAlchemy itself (CLAUDE.md §5's layering) — `colt_db`'s own repository implementations
translate a real database-level failure into one of these before it ever reaches
`colt_application`/`colt_agents`/`colt_api`.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base for every domain-level failure raised outside the database layer's own types."""


class DuplicateIdentityError(DomainError):
    """Raised when a repository's `add()` loses a race against a concurrent insert of the same
    identity (CLAUDE.md §22, §27, §96, Milestone 27): two callers both found no existing row for
    the same normalized domain/email/etc. and both tried to create one, but only one commit can
    win a real unique constraint. The loser gets this instead of a duplicate row — the caller
    (a Temporal activity's own retry, in practice) is expected to simply try again, at which
    point the winner's row is already there to be found instead of inserted.
    """
