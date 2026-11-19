from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Color,
    CountBalance,
    CountingSession,
    InventoryClass,
    InventoryRequirement,
    InventorySnapshot,
    PartCatalog,
    Project,
    SessionStatus,
    SnapshotValidationStatus,
)


class ReconciliationError(ValueError):
    pass


def project_reconciliation(db: Session, project_id) -> tuple[dict[str, object], list[dict[str, object]]]:
    project = db.get(Project, project_id)
    if project is None or project.inventory_snapshot_id is None:
        raise ReconciliationError("Inventar nicht gefunden.")

    counts = (
        select(
            CountBalance.requirement_id.label("requirement_id"),
            func.coalesce(func.sum(CountBalance.quantity), 0).label("counted"),
        )
        .join(CountingSession, CountBalance.session_id == CountingSession.id)
        .where(
            CountingSession.project_id == project.id,
            CountingSession.status != SessionStatus.ARCHIVED,
        )
        .group_by(CountBalance.requirement_id)
        .subquery()
    )
    rows = db.execute(
        select(InventoryRequirement, PartCatalog, Color, func.coalesce(counts.c.counted, 0))
        .join(PartCatalog, InventoryRequirement.part_id == PartCatalog.id)
        .join(Color, InventoryRequirement.color_id == Color.id)
        .outerjoin(counts, counts.c.requirement_id == InventoryRequirement.id)
        .where(
            InventoryRequirement.snapshot_id == project.inventory_snapshot_id,
            InventoryRequirement.inventory_class == InventoryClass.REQUIRED,
        )
        .order_by(PartCatalog.part_num, Color.provider_color_id)
    ).all()
    items = [
        _item(requirement, part, color, int(counted))
        for requirement, part, color, counted in rows
    ]

    sessions = db.scalars(
        select(CountingSession).where(CountingSession.project_id == project_id)
    ).all()
    required_sessions = [session for session in sessions if session.mandatory]
    all_required_complete = all(
        session.status == SessionStatus.COMPLETED for session in required_sessions
    )
    provisional_gap_units = sum(item["missing_quantity"] for item in items) if not all_required_complete else 0
    confirmed_missing_units = sum(item["missing_quantity"] for item in items) if all_required_complete else 0
    snapshot = db.get(InventorySnapshot, project.inventory_snapshot_id)
    snapshot_valid = snapshot is not None and snapshot.validation_status == SnapshotValidationStatus.VALID

    summary = {
        "required_sessions_total": len(required_sessions),
        "required_sessions_completed": sum(
            session.status == SessionStatus.COMPLETED for session in required_sessions
        ),
        "all_required_complete": all_required_complete,
        "inventory_verified": snapshot_valid,
        "counts_total": sum(item["global_quantity"] for item in items),
        "surplus_types": sum(item["surplus_quantity"] > 0 for item in items),
        "provisional_gap_units": provisional_gap_units,
        "confirmed_missing_units": confirmed_missing_units,
    }
    return summary, items


def difference_items(db: Session, project_id, difference_type: str) -> tuple[bool, list[dict[str, object]]]:
    summary, items = project_reconciliation(db, project_id)
    all_complete = bool(summary["all_required_complete"])
    quantities_by_requirement: dict[str, list[dict[str, object]]] = defaultdict(list)
    for requirement_id, session_label, quantity in db.execute(
        select(CountBalance.requirement_id, CountingSession.label, CountBalance.quantity)
        .join(CountingSession, CountBalance.session_id == CountingSession.id)
        .where(CountingSession.project_id == project_id, CountBalance.quantity > 0)
        .order_by(CountingSession.position)
    ).all():
        quantities_by_requirement[str(requirement_id)].append({"label": session_label, "quantity": int(quantity)})
    for item in items:
        item["session_breakdown"] = quantities_by_requirement[str(item["id"])]
    if difference_type == "missing":
        return all_complete, [item for item in items if item["missing_quantity"] > 0] if all_complete else []
    if difference_type == "surplus":
        return all_complete, [item for item in items if item["surplus_quantity"] > 0]
    if difference_type == "all":
        return all_complete, items
    raise ReconciliationError("Unbekannter Differenztyp.")


def _item(requirement, part, color, counted: int) -> dict[str, object]:
    expected = requirement.expected_qty
    return {
        "id": str(requirement.id),
        "part_num": part.part_num,
        "part_name": part.name,
        "color_id": color.provider_color_id,
        "color_name": color.name,
        "expected_quantity": expected,
        "global_quantity": counted,
        "missing_quantity": max(0, expected - counted),
        "surplus_quantity": max(0, counted - expected),
    }
