"""add project archive timestamp

Revision ID: 43e98bf42a01
Revises: 8e64fb2d1a11
Create Date: 2026-11-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "43e98bf42a01"
down_revision: Union[str, None] = "8e64fb2d1a11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "archived_at")
