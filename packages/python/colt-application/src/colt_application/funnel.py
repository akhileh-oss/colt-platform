"""Deterministic funnel summary (CLAUDE.md §68, Milestone 22's "funnel" Build item) — how many
leads sit at each `LeadStatus`, in the status's own declared order (§11.1's linear progression),
a pure function of `Lead` rows like every other analytics module this milestone adds.
"""

from __future__ import annotations

from dataclasses import dataclass

from colt_domain import Lead, LeadStatus


@dataclass(frozen=True, slots=True)
class FunnelStageSummary:
    status: LeadStatus
    count: int


def summarize_funnel(leads: list[Lead]) -> list[FunnelStageSummary]:
    totals: dict[LeadStatus, int] = dict.fromkeys(LeadStatus, 0)
    for lead in leads:
        totals[lead.status] += 1
    return [FunnelStageSummary(status=status, count=count) for status, count in totals.items()]
