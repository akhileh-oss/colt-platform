"""companies people signals evidence leads campaigns messages conversations opportunities audit logs

Revision ID: a2d24a5f5578
Revises: 17ce44b8dd56
Create Date: 2026-08-30 15:45:57.967661

Every table here carries `organization_id`, so every table gets the same Row-Level Security
treatment as `users` (CLAUDE.md §9.7, §27, ADR-0005): ENABLE + FORCE ROW LEVEL SECURITY, and a
`tenant_isolation` policy keyed to `app.current_organization_id`. None of these tables need the
`app.bypass_rls` clause `users` has — that exists for exactly one pre-organization-context
identity lookup, which does not apply here. `sequence_step_id` on `messages` has no foreign key:
`sequence_steps` is a Milestone 14 table, out of scope for this domain foundation milestone.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a2d24a5f5578"
down_revision: str | Sequence[str] | None = "17ce44b8dd56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_TABLES = (
    "audit_logs",
    "campaigns",
    "companies",
    "evidence",
    "people",
    "leads",
    "signals",
    "conversations",
    "opportunities",
    "messages",
)


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table}
        USING (
            organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
        )
        """
    )


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("actor_type", sa.String(length=50), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("trace_id", sa.String(length=100), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_audit_logs_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_actor_id"), "audit_logs", ["actor_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)
    op.create_index(op.f("ix_audit_logs_entity_id"), "audit_logs", ["entity_id"], unique=False)
    op.create_index(
        op.f("ix_audit_logs_organization_id"), "audit_logs", ["organization_id"], unique=False
    )

    op.create_table(
        "campaigns",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="DRAFT", nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column(
            "icp_definition",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "rules", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "channels",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "schedule",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "limits", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "approval_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_campaigns_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaigns")),
    )
    op.create_index(
        op.f("ix_campaigns_organization_id"), "campaigns", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_campaigns_status"), "campaigns", ["status"], unique=False)

    op.create_table(
        "companies",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("normalized_domain", sa.String(length=255), nullable=True),
        sa.Column("industry", sa.String(length=200), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("revenue_range", sa.String(length=50), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("website_url", sa.String(length=2048), nullable=True),
        sa.Column("linkedin_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "source_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_companies_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
    )
    op.create_index(
        op.f("ix_companies_normalized_domain"), "companies", ["normalized_domain"], unique=False
    )
    op.create_index(
        op.f("ix_companies_organization_id"), "companies", ["organization_id"], unique=False
    )

    op.create_table(
        "evidence",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_date", sa.Date(), nullable=True),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "verification_status",
            sa.String(length=50),
            server_default="UNVERIFIED",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_evidence_valid_confidence"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_evidence_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence")),
    )
    op.create_index(op.f("ix_evidence_entity_id"), "evidence", ["entity_id"], unique=False)
    op.create_index(op.f("ix_evidence_entity_type"), "evidence", ["entity_type"], unique=False)
    op.create_index(
        op.f("ix_evidence_organization_id"), "evidence", ["organization_id"], unique=False
    )

    op.create_table(
        "people",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("first_name", sa.String(length=150), nullable=True),
        sa.Column("last_name", sa.String(length=150), nullable=True),
        sa.Column("full_name", sa.String(length=300), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("seniority", sa.String(length=50), nullable=True),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("email_status", sa.String(length=50), nullable=True),
        sa.Column("linkedin_url", sa.String(length=2048), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column(
            "source_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_people_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_people_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_people")),
    )
    op.create_index(op.f("ix_people_company_id"), "people", ["company_id"], unique=False)
    op.create_index(op.f("ix_people_email"), "people", ["email"], unique=False)
    op.create_index(op.f("ix_people_organization_id"), "people", ["organization_id"], unique=False)

    op.create_table(
        "leads",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="NEW", nullable=False),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("current_stage", sa.String(length=100), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('NEW', 'DISCOVERED', 'ENRICHING', 'RESEARCHED', 'QUALIFIED', "
            "'PERSONALIZED', 'PENDING_APPROVAL', 'READY', 'CONTACTED', 'ENGAGED', "
            "'NOT_QUALIFIED', 'NOT_INTERESTED', 'UNSUBSCRIBED', 'SUPPRESSED', 'NURTURE', "
            "'CONVERTED')",
            name=op.f("ck_leads_valid_status"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_leads_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_leads_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["people.id"],
            name=op.f("fk_leads_person_id_people"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leads")),
        sa.UniqueConstraint("organization_id", "person_id", name="uq_leads_organization_person"),
    )
    op.create_index(op.f("ix_leads_company_id"), "leads", ["company_id"], unique=False)
    op.create_index(op.f("ix_leads_organization_id"), "leads", ["organization_id"], unique=False)
    op.create_index(op.f("ix_leads_person_id"), "leads", ["person_id"], unique=False)
    op.create_index(op.f("ix_leads_status"), "leads", ["status"], unique=False)

    op.create_table(
        "signals",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=True),
        sa.Column("signal_type", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("event_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_signals_valid_confidence"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_signals_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_signals_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["people.id"],
            name=op.f("fk_signals_person_id_people"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_signals")),
    )
    op.create_index(op.f("ix_signals_company_id"), "signals", ["company_id"], unique=False)
    op.create_index(
        op.f("ix_signals_organization_id"), "signals", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_signals_person_id"), "signals", ["person_id"], unique=False)
    op.create_index(op.f("ix_signals_signal_type"), "signals", ["signal_type"], unique=False)

    op.create_table(
        "conversations",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("state", sa.String(length=20), server_default="OPEN", nullable=False),
        sa.Column("last_activity_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('OPEN', 'POSITIVE', 'QUESTION', 'OBJECTION', 'NOT_NOW', "
            "'NOT_INTERESTED', 'UNSUBSCRIBED', 'HUMAN_HANDOFF')",
            name=op.f("ck_conversations_valid_state"),
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_conversations_lead_id_leads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_conversations_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )
    op.create_index(op.f("ix_conversations_lead_id"), "conversations", ["lead_id"], unique=False)
    op.create_index(
        op.f("ix_conversations_organization_id"),
        "conversations",
        ["organization_id"],
        unique=False,
    )
    op.create_index(op.f("ix_conversations_state"), "conversations", ["state"], unique=False)

    op.create_table(
        "opportunities",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("primary_person_id", sa.UUID(), nullable=True),
        sa.Column("lead_id", sa.UUID(), nullable=True),
        sa.Column(
            "pipeline_stage", sa.String(length=20), server_default="QUALIFIED", nullable=False
        ),
        sa.Column("estimated_value", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("probability", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("owner_id", sa.UUID(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "pipeline_stage IN ('QUALIFIED', 'DISCOVERY', 'EVALUATION', 'PROPOSAL', "
            "'NEGOTIATION', 'WON', 'LOST')",
            name=op.f("ck_opportunities_valid_pipeline_stage"),
        ),
        sa.CheckConstraint(
            "probability IS NULL OR (probability >= 0 AND probability <= 1)",
            name=op.f("ck_opportunities_valid_probability"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_opportunities_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_opportunities_lead_id_leads"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_opportunities_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_opportunities_owner_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["primary_person_id"],
            ["people.id"],
            name=op.f("fk_opportunities_primary_person_id_people"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_opportunities")),
    )
    op.create_index(
        op.f("ix_opportunities_company_id"), "opportunities", ["company_id"], unique=False
    )
    op.create_index(op.f("ix_opportunities_lead_id"), "opportunities", ["lead_id"], unique=False)
    op.create_index(
        op.f("ix_opportunities_organization_id"),
        "opportunities",
        ["organization_id"],
        unique=False,
    )
    op.create_index(op.f("ix_opportunities_owner_id"), "opportunities", ["owner_id"], unique=False)
    op.create_index(
        op.f("ix_opportunities_pipeline_stage"),
        "opportunities",
        ["pipeline_stage"],
        unique=False,
    )
    op.create_index(
        op.f("ix_opportunities_primary_person_id"),
        "opportunities",
        ["primary_person_id"],
        unique=False,
    )

    op.create_table(
        "messages",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("sequence_step_id", sa.UUID(), nullable=True),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="DRAFT", nullable=False),
        sa.Column(
            "approval_status", sa.String(length=20), server_default="PENDING", nullable=False
        ),
        sa.Column(
            "evidence_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("scheduled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_messages_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_messages_conversation_id_conversations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_messages_lead_id_leads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_messages_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index(op.f("ix_messages_campaign_id"), "messages", ["campaign_id"], unique=False)
    op.create_index(
        op.f("ix_messages_conversation_id"), "messages", ["conversation_id"], unique=False
    )
    op.create_index(op.f("ix_messages_lead_id"), "messages", ["lead_id"], unique=False)
    op.create_index(
        op.f("ix_messages_organization_id"), "messages", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_messages_status"), "messages", ["status"], unique=False)
    op.create_index(
        "uq_messages_organization_idempotency_key",
        "messages",
        ["organization_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "uq_messages_organization_provider_message_id",
        "messages",
        ["organization_id", "provider_message_id"],
        unique=True,
        postgresql_where=sa.text("provider_message_id IS NOT NULL"),
    )

    for table in _TENANT_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    for table in reversed(_TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_index(
        "uq_messages_organization_provider_message_id",
        table_name="messages",
        postgresql_where=sa.text("provider_message_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_messages_organization_idempotency_key",
        table_name="messages",
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.drop_index(op.f("ix_messages_status"), table_name="messages")
    op.drop_index(op.f("ix_messages_organization_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_lead_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_campaign_id"), table_name="messages")
    op.drop_table("messages")

    op.drop_index(op.f("ix_opportunities_primary_person_id"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_pipeline_stage"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_owner_id"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_organization_id"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_lead_id"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_company_id"), table_name="opportunities")
    op.drop_table("opportunities")

    op.drop_index(op.f("ix_conversations_state"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_organization_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_lead_id"), table_name="conversations")
    op.drop_table("conversations")

    op.drop_index(op.f("ix_signals_signal_type"), table_name="signals")
    op.drop_index(op.f("ix_signals_person_id"), table_name="signals")
    op.drop_index(op.f("ix_signals_organization_id"), table_name="signals")
    op.drop_index(op.f("ix_signals_company_id"), table_name="signals")
    op.drop_table("signals")

    op.drop_index(op.f("ix_leads_status"), table_name="leads")
    op.drop_index(op.f("ix_leads_person_id"), table_name="leads")
    op.drop_index(op.f("ix_leads_organization_id"), table_name="leads")
    op.drop_index(op.f("ix_leads_company_id"), table_name="leads")
    op.drop_table("leads")

    op.drop_index(op.f("ix_people_organization_id"), table_name="people")
    op.drop_index(op.f("ix_people_email"), table_name="people")
    op.drop_index(op.f("ix_people_company_id"), table_name="people")
    op.drop_table("people")

    op.drop_index(op.f("ix_evidence_organization_id"), table_name="evidence")
    op.drop_index(op.f("ix_evidence_entity_type"), table_name="evidence")
    op.drop_index(op.f("ix_evidence_entity_id"), table_name="evidence")
    op.drop_table("evidence")

    op.drop_index(op.f("ix_companies_organization_id"), table_name="companies")
    op.drop_index(op.f("ix_companies_normalized_domain"), table_name="companies")
    op.drop_table("companies")

    op.drop_index(op.f("ix_campaigns_status"), table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_organization_id"), table_name="campaigns")
    op.drop_table("campaigns")

    op.drop_index(op.f("ix_audit_logs_organization_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_entity_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_actor_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_table("audit_logs")
