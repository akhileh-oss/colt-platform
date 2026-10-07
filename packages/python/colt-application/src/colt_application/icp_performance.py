"""Deterministic ICP-performance summary (CLAUDE.md §68, Milestone 22's "ICP performance" Build
item). No per-`Company`/per-`Lead` "ICP segment" field exists anywhere in this codebase —
`Campaign.icp_definition` is a per-campaign targeting dict, not a label stored on a company —
so `Company.industry` is this milestone's own documented proxy for "which segment," the same
"the milestone building it makes the documented call" pattern `CampaignStatus`/`Urgency`
already establish where CLAUDE.md names a concept without a stored representation.

Grouped by `industry` (falling back to `"unknown"` when unset); correlates each segment's leads
and companies against real commercial outcomes — qualified leads and closed-won revenue — via
`Opportunity.company_id`, the same join `icp_performance`'s acceptance criterion ("what
segments ... produce commercial outcomes") actually asks for.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from colt_domain import Company, Lead, LeadStatus, Opportunity, PipelineStage

_UNKNOWN_INDUSTRY = "unknown"

#: A lead counts as "qualified" for this report from the point a human scoring/qualification
#: decision actually happened (§13's `QUALIFIED`) through to `CONVERTED` — every status in the
#: funnel that is not still pre-qualification and not a terminal rejection/suppression.
_QUALIFIED_STATUSES = frozenset(
    {
        LeadStatus.QUALIFIED,
        LeadStatus.PERSONALIZED,
        LeadStatus.PENDING_APPROVAL,
        LeadStatus.READY,
        LeadStatus.CONTACTED,
        LeadStatus.ENGAGED,
        LeadStatus.CONVERTED,
    }
)


@dataclass(frozen=True, slots=True)
class IcpPerformanceRow:
    industry: str
    company_count: int
    lead_count: int
    qualified_lead_count: int
    won_company_count: int
    won_revenue: float


@dataclass(slots=True)
class _Bucket:
    company_count: int = 0
    lead_count: int = 0
    qualified_lead_count: int = 0
    won_company_count: int = 0
    won_revenue: float = 0.0


def summarize_icp_performance(
    companies: list[Company], leads: list[Lead], opportunities: list[Opportunity]
) -> list[IcpPerformanceRow]:
    won_revenue_by_company: dict[UUID, float] = {}
    for opportunity in opportunities:
        if opportunity.pipeline_stage is PipelineStage.WON:
            won_revenue_by_company[opportunity.company_id] = won_revenue_by_company.get(
                opportunity.company_id, 0.0
            ) + (opportunity.estimated_value or 0.0)

    industry_by_company: dict[UUID, str] = {}
    totals: dict[str, _Bucket] = {}

    for company in companies:
        industry = company.industry or _UNKNOWN_INDUSTRY
        industry_by_company[company.id] = industry
        bucket = totals.setdefault(industry, _Bucket())
        bucket.company_count += 1
        if company.id in won_revenue_by_company:
            bucket.won_company_count += 1
            bucket.won_revenue += won_revenue_by_company[company.id]

    for lead in leads:
        industry = industry_by_company.get(lead.company_id, _UNKNOWN_INDUSTRY)
        bucket = totals.setdefault(industry, _Bucket())
        bucket.lead_count += 1
        if lead.status in _QUALIFIED_STATUSES:
            bucket.qualified_lead_count += 1

    return [
        IcpPerformanceRow(
            industry=industry,
            company_count=bucket.company_count,
            lead_count=bucket.lead_count,
            qualified_lead_count=bucket.qualified_lead_count,
            won_company_count=bucket.won_company_count,
            won_revenue=bucket.won_revenue,
        )
        for industry, bucket in sorted(totals.items())
    ]
