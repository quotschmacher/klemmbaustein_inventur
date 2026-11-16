from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Color,
    CountEvent,
    CountingSession,
    InventoryRequirement,
    PartCatalog,

    ReplacementItem,
    ReplacementOrder,
)
from app.services.counting import adjust_count
from app.services.reconciliation import difference_items


class ReplacementError(ValueError):
    pass


def create_replacement(
    db: Session,
    *,
    project_id: UUID,
    requirement_id: UUID,
    qty_ordered: int,
    target_session_id: UUID | None,
    notes: str | None,
) -> ReplacementItem:
    _confirmed_missing_requirement(db, project_id, requirement_id)
    _validate_target_session(db, project_id, target_session_id)
    order = ReplacementOrder(project_id=project_id, status="planned", notes=notes)
    db.add(order)
    db.flush()
    item = ReplacementItem(
        order_id=order.id,
        requirement_id=requirement_id,
        qty_ordered=qty_ordered,
        target_session_id=target_session_id,
    )
    db.add(item)
    db.flush()
    return item


def create_combined_replacement_order(
    db: Session, *, project_id: UUID, target_session_id: UUID | None, notes: str | None
) -> tuple[ReplacementOrder, list[ReplacementItem]]:
    final, missing = difference_items(db, project_id, "missing")
    if not final or not missing:
        raise ReplacementError("Es gibt keine bestätigten Fehlteile für eine Sammelbestellung.")
    _validate_target_session(db, project_id, target_session_id)
    order = ReplacementOrder(project_id=project_id, status="planned", notes=notes)
    db.add(order)
    db.flush()
    items = [
        ReplacementItem(
            order_id=order.id,
            requirement_id=UUID(item["id"]),
            qty_ordered=int(item["missing_quantity"]),
            target_session_id=target_session_id,
        )
        for item in missing
    ]
    db.add_all(items)
    db.flush()
    return order, items


def update_replacement(
    db: Session,
    *,
    project_id: UUID,
    item_id: UUID,
    qty_ordered: int | None = None,
    qty_received: int | None = None,
    target_session_id: UUID | None = None,
    status: str | None = None,
) -> ReplacementItem:
    item, order = _item_and_order(db, project_id, item_id)
    if target_session_id is not None:
        _validate_target_session(db, project_id, target_session_id)
        item.target_session_id = target_session_id
    if qty_ordered is not None:
        item.qty_ordered = qty_ordered
    if qty_received is not None:
        if qty_received < item.qty_booked:
            raise ReplacementError("Erhaltene Menge darf bereits eingebuchte Teile nicht unterschreiten.")
        item.qty_received = qty_received
    if status is not None:
        order.status = status
    db.flush()
    return item


def book_replacement(
    db: Session,
    *,
    item_id: UUID,
    session_id: UUID,
    quantity: int,
    mutation_id: UUID,
) -> dict[str, int | str]:
    item = db.get(ReplacementItem, item_id)
    if item is None:
        raise ReplacementError("Bestellposition nicht gefunden.")
    order = db.get(ReplacementOrder, item.order_id)
    assert order is not None
    session = db.get(CountingSession, session_id)
    if session is None or session.project_id != order.project_id:
        raise ReplacementError("Zielbereich gehört nicht zur Bestellung.")
    existing = db.scalar(
        select(CountEvent).where(
            CountEvent.project_id == order.project_id,
            CountEvent.client_mutation_id == mutation_id,
        )
    )
    if existing is not None:
        if existing.order_item_id != item.id:
            raise ReplacementError("Mutation wurde bereits für eine andere Buchung verwendet.")
        return adjust_count(
            db,
            session_id=session_id,
            requirement_id=item.requirement_id,
            delta=0,
            mutation_id=mutation_id,
        )
    if quantity > item.qty_received - item.qty_booked:
        raise ReplacementError("Es können nur tatsächlich erhaltene Ersatzteile eingebucht werden.")
    result = adjust_count(
        db,
        session_id=session_id,
        requirement_id=item.requirement_id,
        delta=quantity,
        mutation_id=mutation_id,
    )
    event = db.scalar(
        select(CountEvent).where(
            CountEvent.project_id == order.project_id,
            CountEvent.client_mutation_id == mutation_id,
        )
    )
    assert event is not None
    event.order_item_id = item.id
    item.qty_booked += quantity
    db.flush()
    return result


def replacement_items(db: Session, project_id: UUID) -> list[dict[str, object]]:
    rows = db.execute(
        select(ReplacementItem, ReplacementOrder, InventoryRequirement, PartCatalog, Color)
        .join(ReplacementOrder, ReplacementItem.order_id == ReplacementOrder.id)
        .join(InventoryRequirement, ReplacementItem.requirement_id == InventoryRequirement.id)
        .join(PartCatalog, InventoryRequirement.part_id == PartCatalog.id)
        .join(Color, InventoryRequirement.color_id == Color.id)
        .where(ReplacementOrder.project_id == project_id)
        .order_by(ReplacementOrder.created_at.desc(), PartCatalog.part_num)
    ).all()
    return [_item_data(item, order, requirement, part, color) for item, order, requirement, part, color in rows]


def replacement_item_data(db: Session, project_id: UUID, item_id: UUID) -> dict[str, object]:
    item, order = _item_and_order(db, project_id, item_id)
    requirement, part, color = db.execute(
        select(InventoryRequirement, PartCatalog, Color)
        .join(PartCatalog, InventoryRequirement.part_id == PartCatalog.id)
        .join(Color, InventoryRequirement.color_id == Color.id)
        .where(InventoryRequirement.id == item.requirement_id)
    ).one()
    return _item_data(item, order, requirement, part, color)


def _confirmed_missing_requirement(db: Session, project_id: UUID, requirement_id: UUID) -> None:
    final, missing = difference_items(db, project_id, "missing")
    if not final or not any(item["id"] == str(requirement_id) for item in missing):
        raise ReplacementError("Nur bestätigte Fehlteile dürfen bestellt werden.")


def _validate_target_session(db: Session, project_id: UUID, session_id: UUID | None) -> None:
    if session_id is not None:
        session = db.get(CountingSession, session_id)
        if session is None or session.project_id != project_id:
            raise ReplacementError("Der Zielbereich gehört nicht zum Projekt.")


def _item_and_order(db: Session, project_id: UUID, item_id: UUID) -> tuple[ReplacementItem, ReplacementOrder]:
    item = db.get(ReplacementItem, item_id)
    if item is None:
        raise ReplacementError("Bestellposition nicht gefunden.")
    order = db.get(ReplacementOrder, item.order_id)
    assert order is not None
    if order.project_id != project_id:
        raise ReplacementError("Bestellposition gehört nicht zum Projekt.")
    return item, order


def _item_data(item, order, requirement, part, color) -> dict[str, object]:
    return {
        "id": str(item.id),
        "order_id": str(order.id),
        "requirement_id": str(requirement.id),
        "part_num": part.part_num,
        "part_name": part.name,
        "color_name": color.name,
        "qty_ordered": item.qty_ordered,
        "qty_received": item.qty_received,
        "qty_booked": item.qty_booked,
        "target_session_id": str(item.target_session_id) if item.target_session_id else None,
        "status": order.status,
        "notes": order.notes,
    }
