"""project inventory scope

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-17

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add project_id to inventories and add FK
    op.add_column("inventories", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_inventories_project",
        "inventories",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 2. Drop unique constraint on inventories.name
    op.drop_constraint("inventories_name_key", "inventories", type_="unique")

    # 3. Add unique index on (COALESCE(project_id, 0), name)
    op.execute(
        "CREATE UNIQUE INDEX uq_inventories_scope_name ON inventories (COALESCE(project_id, 0), name)"
    )

    # 4. Add default_inventory_id to projects and add FK
    op.add_column("projects", sa.Column("default_inventory_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_projects_default_inventory",
        "projects",
        "inventories",
        ["default_inventory_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 5. Make job_templates.inventory_id nullable
    op.alter_column("job_templates", "inventory_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Reverse 5: make job_templates.inventory_id not null
    op.alter_column("job_templates", "inventory_id", existing_type=sa.Integer(), nullable=False)

    # Reverse 4: drop projects.default_inventory_id FK and column
    op.drop_constraint("fk_projects_default_inventory", "projects", type_="foreignkey")
    op.drop_column("projects", "default_inventory_id")

    # Reverse 3: drop unique index
    op.execute("DROP INDEX IF EXISTS uq_inventories_scope_name")

    # Reverse 2: restore unique constraint on name
    op.create_unique_constraint("inventories_name_key", "inventories", ["name"])

    # Reverse 1: drop inventories.project_id FK and column
    op.drop_constraint("fk_inventories_project", "inventories", type_="foreignkey")
    op.drop_column("inventories", "project_id")
