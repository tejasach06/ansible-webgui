"""operator pack

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("job_templates", sa.Column("survey_spec", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("job_templates", sa.Column("diff_mode", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("job_runs", sa.Column("survey_secrets_enc", sa.LargeBinary(), nullable=True))
    op.add_column("job_runs", sa.Column("relaunch_of_id", sa.Integer(), sa.ForeignKey("job_runs.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_job_events_run_event", "job_events", ["job_run_id", "event"])
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), unique=True, nullable=False),
        sa.Column("kind", sa.Enum("webhook", "slack", name="notificationkind"), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("on_success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("on_failure", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("on_approval_needed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("notifications")
    sa.Enum(name="notificationkind").drop(op.get_bind())
    op.drop_index("ix_job_events_run_event", table_name="job_events")
    op.drop_column("job_runs", "relaunch_of_id")
    op.drop_column("job_runs", "survey_secrets_enc")
    op.drop_column("job_templates", "diff_mode")
    op.drop_column("job_templates", "survey_spec")
