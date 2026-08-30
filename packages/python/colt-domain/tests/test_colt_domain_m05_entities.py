"""Milestone 05 domain entity invariants (CLAUDE.md §10.3-§10.14, §48).

One file for all ten new entities rather than ten files: each gets a focused slice covering its
validators and any frozen-copy methods, following the pattern established in
`test_colt_domain_organization.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from colt_domain import (
    AuditLog,
    Campaign,
    Company,
    Conversation,
    ConversationState,
    Evidence,
    Lead,
    LeadStatus,
    Message,
    Opportunity,
    Person,
    PipelineStage,
    Signal,
)

NOW = datetime.now(UTC)
ORG_ID = uuid4()


def _make_company(*, name: str = "Acme Corp", employee_count: int | None = None) -> Company:
    return Company(
        id=uuid4(),
        organization_id=ORG_ID,
        name=name,
        employee_count=employee_count,
        created_at=NOW,
        updated_at=NOW,
    )


def test_company_blank_name_is_rejected() -> None:
    with pytest.raises(ValidationError, match="blank"):
        _make_company(name="  ")


def test_company_negative_employee_count_is_rejected() -> None:
    with pytest.raises(ValidationError, match="negative"):
        _make_company(employee_count=-1)


def _make_person(*, full_name: str = "Alice Doe") -> Person:
    return Person(
        id=uuid4(),
        organization_id=ORG_ID,
        company_id=uuid4(),
        full_name=full_name,
        created_at=NOW,
        updated_at=NOW,
    )


def test_person_blank_full_name_is_rejected() -> None:
    with pytest.raises(ValidationError, match="blank"):
        _make_person(full_name="   ")


def _make_signal(*, signal_type: str = "funding", confidence: float | None = None) -> Signal:
    return Signal(
        id=uuid4(),
        organization_id=ORG_ID,
        company_id=uuid4(),
        signal_type=signal_type,
        observed_at=NOW,
        confidence=confidence,
        created_at=NOW,
    )


def test_signal_blank_type_is_rejected() -> None:
    with pytest.raises(ValidationError, match="blank"):
        _make_signal(signal_type=" ")


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_signal_confidence_out_of_range_is_rejected(confidence: float) -> None:
    with pytest.raises(ValidationError, match="confidence"):
        _make_signal(confidence=confidence)


def _make_evidence(
    *, claim: str = "Acme raised a Series B", source_url: str = "https://example.test/a"
) -> Evidence:
    return Evidence(
        id=uuid4(),
        organization_id=ORG_ID,
        entity_type="company",
        entity_id=uuid4(),
        claim=claim,
        source_url=source_url,
        observed_at=NOW,
        created_at=NOW,
    )


def test_evidence_blank_claim_is_rejected() -> None:
    with pytest.raises(ValidationError, match="claim"):
        _make_evidence(claim="  ")


def test_evidence_blank_source_url_is_rejected() -> None:
    with pytest.raises(ValidationError, match="source_url"):
        _make_evidence(source_url=" ")


def test_evidence_defaults_to_unverified() -> None:
    assert _make_evidence().verification_status == "UNVERIFIED"


def _make_lead(*, status: LeadStatus = LeadStatus.NEW) -> Lead:
    return Lead(
        id=uuid4(),
        organization_id=ORG_ID,
        company_id=uuid4(),
        person_id=uuid4(),
        status=status,
        created_at=NOW,
        updated_at=NOW,
    )


def test_lead_defaults_to_new() -> None:
    assert _make_lead().status is LeadStatus.NEW


def test_lead_with_status_returns_a_new_instance() -> None:
    lead = _make_lead()
    later = datetime.now(UTC)
    qualified = lead.with_status(LeadStatus.QUALIFIED, at=later)

    assert lead.status is LeadStatus.NEW, "original must be unchanged"
    assert qualified.status is LeadStatus.QUALIFIED
    assert qualified.updated_at == later


def test_lead_is_frozen() -> None:
    lead = _make_lead()
    with pytest.raises(ValidationError):
        lead.status = LeadStatus.CONVERTED


def _make_campaign(*, name: str = "Q1 Outbound") -> Campaign:
    return Campaign(id=uuid4(), organization_id=ORG_ID, name=name, created_at=NOW, updated_at=NOW)


def test_campaign_blank_name_is_rejected() -> None:
    with pytest.raises(ValidationError, match="blank"):
        _make_campaign(name="")


def test_campaign_defaults_to_draft() -> None:
    assert _make_campaign().status == "DRAFT"


def _make_conversation(*, state: ConversationState = ConversationState.OPEN) -> Conversation:
    return Conversation(
        id=uuid4(),
        organization_id=ORG_ID,
        lead_id=uuid4(),
        channel="email",
        state=state,
        created_at=NOW,
        updated_at=NOW,
    )


def test_conversation_defaults_to_open() -> None:
    assert _make_conversation().state is ConversationState.OPEN


def test_conversation_with_state_returns_a_new_instance() -> None:
    conversation = _make_conversation()
    later = datetime.now(UTC)
    handed_off = conversation.with_state(ConversationState.HUMAN_HANDOFF, at=later)

    assert conversation.state is ConversationState.OPEN, "original must be unchanged"
    assert handed_off.state is ConversationState.HUMAN_HANDOFF
    assert handed_off.updated_at == later


def _make_message(*, channel: str = "email", body: str = "Hi Alice") -> Message:
    return Message(
        id=uuid4(),
        organization_id=ORG_ID,
        campaign_id=uuid4(),
        lead_id=uuid4(),
        channel=channel,
        body=body,
        created_at=NOW,
        updated_at=NOW,
    )


def test_message_blank_channel_is_rejected() -> None:
    with pytest.raises(ValidationError, match="channel"):
        _make_message(channel=" ")


def test_message_blank_body_is_rejected() -> None:
    with pytest.raises(ValidationError, match="body"):
        _make_message(body="")


def test_message_defaults() -> None:
    message = _make_message()
    assert message.status == "DRAFT"
    assert message.approval_status == "PENDING"
    assert message.evidence_ids == []


def _make_opportunity(*, stage: PipelineStage = PipelineStage.QUALIFIED) -> Opportunity:
    return Opportunity(
        id=uuid4(),
        organization_id=ORG_ID,
        company_id=uuid4(),
        pipeline_stage=stage,
        created_at=NOW,
        updated_at=NOW,
    )


def test_opportunity_defaults_to_qualified() -> None:
    assert _make_opportunity().pipeline_stage is PipelineStage.QUALIFIED


def test_opportunity_with_stage_returns_a_new_instance() -> None:
    opportunity = _make_opportunity()
    later = datetime.now(UTC)
    won = opportunity.with_stage(PipelineStage.WON, at=later)

    assert opportunity.pipeline_stage is PipelineStage.QUALIFIED, "original must be unchanged"
    assert won.pipeline_stage is PipelineStage.WON
    assert won.updated_at == later


def _make_audit_log(*, actor_type: str = "user", action: str = "lead.created") -> AuditLog:
    return AuditLog(
        id=uuid4(),
        organization_id=ORG_ID,
        actor_type=actor_type,
        action=action,
        created_at=NOW,
    )


def test_audit_log_blank_actor_type_is_rejected() -> None:
    with pytest.raises(ValidationError, match="actor_type"):
        _make_audit_log(actor_type=" ")


def test_audit_log_blank_action_is_rejected() -> None:
    with pytest.raises(ValidationError, match="action"):
        _make_audit_log(action="")


def test_audit_log_has_no_updated_at_field() -> None:
    assert "updated_at" not in AuditLog.model_fields
