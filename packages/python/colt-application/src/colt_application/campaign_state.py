"""The campaign state machine and definition validation (CLAUDE.md §10.9, Milestone 14).

CLAUDE.md §11 defines a status machine for Lead, Conversation and Opportunity but never one
for Campaign — this milestone's own Build list item ("campaign state machine") and acceptance
criterion ("can be created, validated, paused, resumed, and inspected") are the specification
for what's built here, a documented design decision rather than an unstated guess:

* `DRAFT` — freshly created, not yet validated. Can only move to `ACTIVE`, and only by passing
  validation (`ValidateCampaign`).
* `ACTIVE` — launched and running. Can be `PAUSED`, marked `COMPLETED`, or `ARCHIVED`.
* `PAUSED` — temporarily halted. Can `ACTIVE` resume or be `ARCHIVED`.
* `COMPLETED` — finished its run. Can only be `ARCHIVED`.
* `ARCHIVED` — terminal; no transitions out.

`validate_campaign_definition` checks the Build list's own required configuration surface
("target audiences, exclusions, sequence steps, limits, scheduling config"): a target-audience
definition, at least one channel, a schedule and limits must all be present before a campaign
may activate. `rules` (exclusions) is deliberately not required here — a campaign with no
exclusions is a valid campaign, just one that excludes nothing.
"""

from __future__ import annotations

from typing import Any

from colt_domain import CampaignStatus

CAMPAIGN_TRANSITIONS: dict[CampaignStatus, frozenset[CampaignStatus]] = {
    CampaignStatus.DRAFT: frozenset({CampaignStatus.ACTIVE}),
    CampaignStatus.ACTIVE: frozenset(
        {CampaignStatus.PAUSED, CampaignStatus.COMPLETED, CampaignStatus.ARCHIVED}
    ),
    CampaignStatus.PAUSED: frozenset({CampaignStatus.ACTIVE, CampaignStatus.ARCHIVED}),
    CampaignStatus.COMPLETED: frozenset({CampaignStatus.ARCHIVED}),
    CampaignStatus.ARCHIVED: frozenset(),
}


def can_transition(current: CampaignStatus, target: CampaignStatus) -> bool:
    return target in CAMPAIGN_TRANSITIONS[current]


def validate_campaign_definition(
    *,
    icp_definition: dict[str, Any],
    channels: list[str],
    schedule: dict[str, Any],
    limits: dict[str, Any],
) -> list[str]:
    """Return every rule a campaign's definition fails. Empty means the definition is valid."""
    issues: list[str] = []
    if not icp_definition:
        issues.append("icp_definition must define at least one target-audience criterion.")
    if not channels:
        issues.append("channels must list at least one outreach channel.")
    if not schedule:
        issues.append("schedule must define a sending/sequencing configuration.")
    if not limits:
        issues.append("limits must define at least one sending or pacing limit.")
    return issues
