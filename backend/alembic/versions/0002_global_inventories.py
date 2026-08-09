"""global inventories

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-09

"""
from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _fk_name(table: str, column: str, referred_table: str) -> str:
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys(table):
        if fk["constrained_columns"] == [column] and fk["referred_table"] == referred_table:
            return fk["name"]
    raise RuntimeError(f"foreign key not found: {table}.{column} -> {referred_table}")


def _unique_name(table: str, columns: list[str]) -> str:
    inspector = sa.inspect(op.get_bind())
    for uq in inspector.get_unique_constraints(table):
        if uq["column_names"] == columns:
            return uq["name"]
    raise RuntimeError(f"unique constraint not found: {table}({', '.join(columns)})")


def upgrade() -> None:
    op.execute("DELETE FROM schedules")
    op.execute("DELETE FROM job_templates")

    job_runs_inventory_fk = _fk_name("job_runs", "inventory_id", "inventories")
    op.drop_constraint(job_runs_inventory_fk, "job_runs", type_="foreignkey")
    op.alter_column("job_runs", "inventory_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key(
        None,
        "job_runs",
        "inventories",
        ["inventory_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute("UPDATE job_runs SET inventory_id = NULL")
    op.execute("DELETE FROM inventories")

    inventories_project_fk = _fk_name("inventories", "project_id", "projects")
    inventories_project_rel_path_uq = _unique_name("inventories", ["project_id", "rel_path"])
    op.drop_constraint(inventories_project_rel_path_uq, "inventories", type_="unique")
    op.drop_constraint(inventories_project_fk, "inventories", type_="foreignkey")
    op.drop_column("inventories", "project_id")
    op.create_unique_constraint(None, "inventories", ["name"])
    op.create_unique_constraint(None, "inventories", ["rel_path"])


def downgrade() -> None:
    raise NotImplementedError("destructive cutover")
