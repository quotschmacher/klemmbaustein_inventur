"""normalize enum storage values

Revision ID: 8e64fb2d1a11
Revises: d5a0b1802099
Create Date: 2026-11-15

"""
from typing import Sequence, Union

from alembic import op

revision: str = "8e64fb2d1a11"
down_revision: Union[str, None] = "d5a0b1802099"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _replace_constraint(table: str, name: str, expression: str) -> None:
    op.drop_constraint(name, table, type_="check")
    op.create_check_constraint(name, table, expression)


def upgrade() -> None:
    _replace_constraint(
        "inventory_snapshots", "snapshotvalidationstatus", "validation_status IN ('pending', 'valid', 'invalid')"
    )
    _replace_constraint(
        "inventory_requirements", "inventoryclass", "inventory_class IN ('required', 'spare')"
    )
    _replace_constraint(
        "projects", "projectstatus", "status IN ('pending_import', 'in_progress', 'ready', 'deficit', 'surplus_review', 'unverified')"
    )
    _replace_constraint("sessions", "sessionstatus", "status IN ('in_progress', 'completed', 'archived')")
    _replace_constraint(
        "count_events", "countoperation", "operation IN ('adjust', 'set', 'replacement_booking')"
    )


def downgrade() -> None:
    _replace_constraint(
        "inventory_snapshots", "snapshotvalidationstatus", "validation_status IN ('PENDING', 'VALID', 'INVALID')"
    )
    _replace_constraint(
        "inventory_requirements", "inventoryclass", "inventory_class IN ('REQUIRED', 'SPARE')"
    )
    _replace_constraint(
        "projects", "projectstatus", "status IN ('PENDING_IMPORT', 'IN_PROGRESS', 'READY', 'DEFICIT', 'SURPLUS_REVIEW', 'UNVERIFIED')"
    )
    _replace_constraint("sessions", "sessionstatus", "status IN ('IN_PROGRESS', 'COMPLETED', 'ARCHIVED')")
    _replace_constraint(
        "count_events", "countoperation", "operation IN ('ADJUST', 'SET', 'REPLACEMENT_BOOKING')"
    )
