"""Deterministic ICP-performance summary (CLAUDE.md §68, Milestone 22)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from colt_application.icp_performance import summarize_icp_performance
from colt_domain import Company, Lead, LeadStatus, Opportunity, PipelineStage

NOW = datetime.now(UTC)


def _company(*, industry: str | None) -> Company:
    return Company(
        id=uuid4(),
        organization_id=uuid4(),
        name="Acme",
        industry=industry,
        created_at=NOW,
        updated_at=NOW,
    )


def _lead(*, company_id: UUID, status: LeadStatus) -> Lead:
    return Lead(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=company_id,
        person_id=uuid4(),
        status=status,
        created_at=NOW,
        updated_at=NOW,
    )


def _opportunity(
    *, company_id: UUID, pipeline_stage: PipelineStage, estimated_value: float | None
) -> Opportunity:
    return Opportunity(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=company_id,
        pipeline_stage=pipeline_stage,
        estimated_value=estimated_value,
        currency="USD",
        created_at=NOW,
        updated_at=NOW,
    )


def test_companies_group_by_industry() -> None:
    companies = [_company(industry="fintech"), _company(industry="fintech")]

    rows = {row.industry: row for row in summarize_icp_performance(companies, [], [])}

    assert rows["fintech"].company_count == 2


def test_companies_without_an_industry_fall_back_to_unknown() -> None:
    companies = [_company(industry=None)]

    rows = {row.industry: row for row in summarize_icp_performance(companies, [], [])}

    assert rows["unknown"].company_count == 1


def test_leads_are_attributed_to_their_companys_industry() -> None:
    company = _company(industry="fintech")
    leads = [
        _lead(company_id=company.id, status=LeadStatus.NEW),
        _lead(company_id=company.id, status=LeadStatus.QUALIFIED),
    ]

    rows = {row.industry: row for row in summarize_icp_performance([company], leads, [])}

    assert rows["fintech"].lead_count == 2
    assert rows["fintech"].qualified_lead_count == 1


def test_leads_for_an_unknown_company_still_count_under_unknown() -> None:
    leads = [_lead(company_id=uuid4(), status=LeadStatus.NEW)]

    rows = {row.industry: row for row in summarize_icp_performance([], leads, [])}

    assert rows["unknown"].lead_count == 1


def test_won_opportunities_attribute_revenue_to_their_companys_industry() -> None:
    company = _company(industry="fintech")
    opportunities = [
        _opportunity(
            company_id=company.id, pipeline_stage=PipelineStage.WON, estimated_value=5000.0
        ),
        _opportunity(
            company_id=company.id,
            pipeline_stage=PipelineStage.NEGOTIATION,
            estimated_value=9999.0,
        ),
    ]

    rows = {row.industry: row for row in summarize_icp_performance([company], [], opportunities)}

    assert rows["fintech"].won_company_count == 1
    assert rows["fintech"].won_revenue == 5000.0


def test_rows_are_sorted_by_industry_name() -> None:
    companies = [_company(industry="zeta"), _company(industry="alpha")]

    rows = summarize_icp_performance(companies, [], [])

    assert [row.industry for row in rows] == ["alpha", "zeta"]
