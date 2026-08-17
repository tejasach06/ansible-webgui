"""credential become same as ssh

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-17

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "credentials",
        sa.Column(
            "become_same_as_ssh",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("credentials", "become_same_as_ssh")
