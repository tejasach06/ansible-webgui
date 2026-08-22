"""timestamptz timestamps

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-17

"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

COLUMNS = [
    ("users", "created_at"),
    ("project_memberships", "created_at"),
    ("pipelines", "created_at"),
    ("pipeline_runs", "created_at"),
    ("pipeline_runs", "started_at"),
    ("pipeline_runs", "finished_at"),
    ("job_runs", "created_at"),
    ("job_runs", "started_at"),
    ("job_runs", "finished_at"),
    ("job_events", "created_at"),
    ("job_plays", "started_at"),
    ("job_plays", "finished_at"),
    ("job_tasks", "started_at"),
    ("job_tasks", "finished_at"),
    ("schedules", "next_run_at"),
    ("commits", "created_at"),
    ("audit_log", "created_at"),
]


def upgrade() -> None:
    for table, column in COLUMNS:
        op.execute(
            f'ALTER TABLE {table} ALTER COLUMN {column} '
            f'TYPE TIMESTAMP WITH TIME ZONE USING {column} AT TIME ZONE \'UTC\''
        )


def downgrade() -> None:
    for table, column in COLUMNS:
        op.execute(
            f'ALTER TABLE {table} ALTER COLUMN {column} '
            f'TYPE TIMESTAMP WITHOUT TIME ZONE USING {column} AT TIME ZONE \'UTC\''
        )
