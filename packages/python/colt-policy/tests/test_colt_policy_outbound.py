"""`evaluate_outbound_send` (CLAUDE.md §17, §17.1) — the pure policy-decision function every
mandatory outbound check runs through. Table-driven: one context field flipped false at a time
proves that check alone blocks the send, and that every other field stays irrelevant to the
verdict once one check has already failed.
"""

from __future__ import annotations

import pytest

from colt_domain import ApprovalStatus
from colt_policy import OutboundSendContext, PolicyDecision, evaluate_outbound_send


def _allowing_context(**overrides: object) -> OutboundSendContext:
    base = {
        "lead_belongs_to_organization": True,
        "target_identity_valid": True,
        "is_suppressed": False,
        "channel_allowed": True,
        "campaign_active": True,
        "rate_limit_ok": True,
        "message_matches_target": True,
        "evidence_valid": True,
        "no_duplicate_send": True,
        "approval_required": False,
        "approval_status": ApprovalStatus.PENDING,
        "send_window_ok": True,
    }
    base.update(overrides)
    return OutboundSendContext.model_validate(base)


def test_a_fully_satisfied_context_is_allowed() -> None:
    evaluation = evaluate_outbound_send(_allowing_context())
    assert evaluation.decision == PolicyDecision.ALLOW
    assert evaluation.failed_checks == ()


@pytest.mark.parametrize(
    "field",
    [
        "lead_belongs_to_organization",
        "target_identity_valid",
        "channel_allowed",
        "campaign_active",
        "rate_limit_ok",
        "message_matches_target",
        "evidence_valid",
        "no_duplicate_send",
        "send_window_ok",
    ],
)
def test_a_single_failing_boolean_check_denies_the_send(field: str) -> None:
    evaluation = evaluate_outbound_send(_allowing_context(**{field: False}))
    assert evaluation.decision == PolicyDecision.DENY
    assert evaluation.failed_checks == (field,)


def test_suppression_denies_the_send_even_when_every_other_check_passes() -> None:
    evaluation = evaluate_outbound_send(_allowing_context(is_suppressed=True))
    assert evaluation.decision == PolicyDecision.DENY
    assert evaluation.failed_checks == ("is_suppressed",)


def test_every_failing_check_is_reported_not_just_the_first() -> None:
    evaluation = evaluate_outbound_send(
        _allowing_context(channel_allowed=False, campaign_active=False, is_suppressed=True)
    )
    assert evaluation.decision == PolicyDecision.DENY
    assert set(evaluation.failed_checks) == {"channel_allowed", "campaign_active", "is_suppressed"}


def test_approval_required_and_not_yet_approved_requires_approval() -> None:
    evaluation = evaluate_outbound_send(
        _allowing_context(approval_required=True, approval_status=ApprovalStatus.PENDING)
    )
    assert evaluation.decision == PolicyDecision.REQUIRE_APPROVAL
    assert evaluation.failed_checks == ("approval_status",)


def test_approval_required_and_rejected_requires_approval_not_allow() -> None:
    evaluation = evaluate_outbound_send(
        _allowing_context(approval_required=True, approval_status=ApprovalStatus.REJECTED)
    )
    assert evaluation.decision == PolicyDecision.REQUIRE_APPROVAL


def test_approval_required_and_approved_is_allowed() -> None:
    evaluation = evaluate_outbound_send(
        _allowing_context(approval_required=True, approval_status=ApprovalStatus.APPROVED)
    )
    assert evaluation.decision == PolicyDecision.ALLOW


def test_a_mandatory_check_failure_takes_priority_over_a_pending_approval() -> None:
    evaluation = evaluate_outbound_send(
        _allowing_context(
            is_suppressed=True, approval_required=True, approval_status=ApprovalStatus.PENDING
        )
    )
    assert evaluation.decision == PolicyDecision.DENY
    assert evaluation.failed_checks == ("is_suppressed",)


def test_approval_not_required_is_allowed_regardless_of_approval_status() -> None:
    evaluation = evaluate_outbound_send(
        _allowing_context(approval_required=False, approval_status=ApprovalStatus.PENDING)
    )
    assert evaluation.decision == PolicyDecision.ALLOW
