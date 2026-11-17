"""add session inventory allocations

Revision ID: f2c1d4e7a891
Revises: 43e98bf42a01
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2c1d4e7a891"
down_revision: Union[str, None] = "43e98bf42a01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("inventory_allocation_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_table(
        "session_inventory_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
        sa.Column("expected_qty", sa.BIGINT(), nullable=False),
        sa.CheckConstraint("expected_qty >= 0", name="ck_session_allocation_expected_qty_nonnegative"),
        sa.ForeignKeyConstraint(["requirement_id"], ["inventory_requirements.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "requirement_id", name="uq_session_allocation_requirement"),
    )


def downgrade() -> None:
    op.drop_table("session_inventory_allocations")
    op.drop_column("sessions", "inventory_allocation_enabled")