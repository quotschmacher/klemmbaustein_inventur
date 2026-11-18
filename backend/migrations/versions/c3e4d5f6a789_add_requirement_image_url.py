"""add per-requirement image URL

Revision ID: c3e4d5f6a789
Revises: f2c1d4e7a891
Create Date: 2026-11-19
"""

from alembic import op
import sqlalchemy as sa

revision = "c3e4d5f6a789"
down_revision = "f2c1d4e7a891"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inventory_requirements", sa.Column("image_url", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column("inventory_requirements", "image_url")
