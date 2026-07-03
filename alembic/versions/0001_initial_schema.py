"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-07-03

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), index=True, nullable=True),
        sa.Column("industry", sa.String(), index=True, nullable=True),
        sa.Column("state", sa.String(), index=True, nullable=True),
        sa.Column("target_titles", sa.JSON(), nullable=True),
        sa.Column("zipcodes", sa.JSON(), nullable=True),
        sa.Column("total_contacts", sa.Integer(), server_default="0", nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=True),
        sa.Column("cost_spent", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("proxy_list", sa.JSON(), nullable=True),
        sa.Column("contacts_per_company", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )

    op.create_table(
        "email_cache",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "email", sa.String(), unique=True, index=True, nullable=True
        ),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("source", sa.String(), server_default="millionverifier", nullable=True),
        sa.Column(
            "last_verified_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("celery_task_id", sa.String(), index=True, nullable=True),
        sa.Column(
            "campaign_id",
            sa.Integer(),
            sa.ForeignKey("campaigns.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(), server_default="pending", nullable=True),
        sa.Column("log_messages", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("skip_email_verify", sa.Integer(), server_default="0", nullable=True),
        sa.Column("mv_credits_used", sa.Integer(), server_default="0", nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "raw_company_records",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("company_name", sa.String(), index=True, nullable=True),
        sa.Column("website", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("state", sa.String(), index=True, nullable=True),
        sa.Column("zip_code", sa.String(), index=True, nullable=True),
        sa.Column("industry", sa.String(), index=True, nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("gmaps_url", sa.String(), nullable=True),
        sa.Column("source", sa.String(), server_default="google_maps", nullable=True),
        sa.Column(
            "status",
            sa.String(),
            server_default="pending_enrichment",
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )

    op.create_table(
        "enriched_leads",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "raw_record_id",
            sa.Integer(),
            sa.ForeignKey("raw_company_records.id"),
            nullable=True,
        ),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("title", sa.String(), index=True, nullable=True),
        sa.Column("linkedin_url", sa.String(), nullable=True),
        sa.Column("guessed_email", sa.String(), nullable=True),
        sa.Column(
            "email_verification_status",
            sa.String(),
            server_default="pending",
            nullable=True,
        ),
        sa.Column("email_confidence_score", sa.Float(), nullable=True),
        sa.Column("linkedin_profile_pic_url", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_table("enriched_leads")
    op.drop_table("raw_company_records")
    op.drop_table("jobs")
    op.drop_table("email_cache")
    op.drop_table("campaigns")
