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


class MessageValidationError(ApplicationError):
    """Raised when a message's personalization fails Milestone 15's acceptance rule: "Generated
    messages contain only supported factual personalization and retain evidence IDs."

    Carries every failing rule, not just the first — same shape as `CampaignValidationError`.
    Covers both an empty `evidence_ids` list (no personalization is "supported" with no
    evidence at all) and an `evidence_ids` entry that does not resolve to a real `Evidence` row
    in this organization (a model cannot assert support that was never actually recorded).
    """

    def __init__(self, issues: list[str]) -> None:
        super().__init__("Message personalization is invalid: " + "; ".join(issues))
        self.issues = issues


class PolicyDeniedError(ApplicationError):
    """Raised when `colt_policy.evaluate_outbound_send` returns anything other than `ALLOW`.

    `SendMessage` raises this *instead of* calling `MessageSender.send` — never after. This is
    the literal mechanism behind Milestone 16's acceptance criterion: "a policy violation cannot
    result in an external message send."
    """

    def __init__(self, decision: str, failed_checks: tuple[str, ...]) -> None:
        super().__init__(
            f"Outbound send denied by policy ({decision}): " + ", ".join(failed_checks)
        )
        self.decision = decision
        self.failed_checks = failed_checks


class InvalidApprovalTransitionError(ApplicationError):
    """Raised when a use case asks to decide an `Approval` that is not `PENDING`.

    An approval decision, once made, is final — re-deciding an already-decided approval would
    silently rewrite history that an `AuditLog` row elsewhere already recorded as fact.
    """

    def __init__(self, current: str) -> None:
        super().__init__(f"Cannot decide an approval that is already {current}.")
        self.current = current
