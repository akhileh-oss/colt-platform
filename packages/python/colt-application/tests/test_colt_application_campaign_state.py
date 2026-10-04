"""The campaign state machine and definition validation (CLAUDE.md §10.9, Milestone 14)."""

from __future__ import annotations

import pytest

from colt_application.campaign_state import can_transition, validate_campaign_definition
from colt_domain import CampaignStatus


@pytest.mark.parametrize(
    ("current", "target", "expected"),
    [
        (CampaignStatus.DRAFT, CampaignStatus.ACTIVE, True),
        (CampaignStatus.DRAFT, CampaignStatus.PAUSED, False),
        (CampaignStatus.DRAFT, CampaignStatus.ARCHIVED, False),
        (CampaignStatus.ACTIVE, CampaignStatus.PAUSED, True),
        (CampaignStatus.ACTIVE, CampaignStatus.COMPLETED, True),
        (CampaignStatus.ACTIVE, CampaignStatus.ARCHIVED, True),
        (CampaignStatus.ACTIVE, CampaignStatus.DRAFT, False),
        (CampaignStatus.PAUSED, CampaignStatus.ACTIVE, True),
        (CampaignStatus.PAUSED, CampaignStatus.ARCHIVED, True),
        (CampaignStatus.PAUSED, CampaignStatus.COMPLETED, False),
        (CampaignStatus.COMPLETED, CampaignStatus.ARCHIVED, True),
        (CampaignStatus.COMPLETED, CampaignStatus.ACTIVE, False),
        (CampaignStatus.ARCHIVED, CampaignStatus.ACTIVE, False),
        (CampaignStatus.ARCHIVED, CampaignStatus.DRAFT, False),
    ],
)
def test_can_transition_matches_the_documented_state_machine(
    current: CampaignStatus, target: CampaignStatus, expected: bool
) -> None:
    assert can_transition(current, target) is expected


def test_validate_campaign_definition_passes_a_fully_configured_campaign() -> None:
    issues = validate_campaign_definition(
        icp_definition={"industry": "SaaS"},
        channels=["email"],
        schedule={"timezone": "UTC"},
        limits={"max_sends_per_day": 50},
    )
    assert issues == []


def test_validate_campaign_definition_reports_every_missing_field_at_once() -> None:
    issues = validate_campaign_definition(icp_definition={}, channels=[], schedule={}, limits={})
    assert len(issues) == 4


@pytest.mark.parametrize(
    ("kwargs", "expected_substring"),
    [
        ({"icp_definition": {}}, "icp_definition"),
        ({"channels": []}, "channels"),
        ({"schedule": {}}, "schedule"),
        ({"limits": {}}, "limits"),
    ],
)
def test_validate_campaign_definition_reports_each_missing_field_individually(
    kwargs: dict[str, object], expected_substring: str
) -> None:
    base: dict[str, object] = {
        "icp_definition": {"industry": "SaaS"},
        "channels": ["email"],
        "schedule": {"timezone": "UTC"},
        "limits": {"max_sends_per_day": 50},
    }
    base.update(kwargs)
    issues = validate_campaign_definition(**base)  # type: ignore[arg-type]
    assert any(expected_substring in issue for issue in issues)
