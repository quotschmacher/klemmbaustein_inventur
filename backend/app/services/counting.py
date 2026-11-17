from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import (
    CountBalance,
    CountEvent,
    CountOperation,
    CountingSession,
    InventoryRequirement,
    Project,
    SessionInventoryAllocation,
    SessionStatus,
)


class CountError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def adjust_count(
    db: Session, *, session_id: UUID, requirement_id: UUID, delta: int, mutation_id: UUID
) -> dict[str, int | str]:
    session, requirement = _validated_entities(db, session_id, requirement_id)
    existing = db.scalar(
        select(CountEvent).where(
            CountEvent.project_id == session.project_id,
            CountEvent.client_mutation_id == mutation_id,
        )
    )
    if existing is not None:
        if existing.session_id != session_id or existing.requirement_id != requirement_id:
            raise CountError("DUPLICATE_MUTATION_PAYLOAD_MISMATCH", "Mutation wurde mit anderer Nutzlast wiederholt.")
        return _result(db, session, requirement, existing.quantity_after or 0, _revision(db, session_id, requirement_id))

    balance = _locked_balance(db, session_id, requirement_id)
    quantity_before = balance.quantity
    quantity_after = quantity_before + delta
    if quantity_after < 0:
        raise CountError("INVALID_NEGATIVE_QUANTITY", "Die Menge darf nicht unter null fallen.")
    balance.quantity = quantity_after
    balance.revision += 1
    db.add(
        CountEvent(
            project_id=session.project_id,
            session_id=session_id,
            requirement_id=requirement_id,
            client_mutation_id=mutation_id,
            operation=CountOperation.ADJUST,
            delta=delta,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
        )
    )
    db.flush()
    return _result(db, session, requirement, quantity_after, balance.revision)


def set_count(
    db: Session,
    *,
    session_id: UUID,
    requirement_id: UUID,
    quantity: int,
    expected_revision: int,
    mutation_id: UUID,
) -> dict[str, int | str]:
    session, requirement = _validated_entities(db, session_id, requirement_id)
    existing = db.scalar(
        select(CountEvent).where(
            CountEvent.project_id == session.project_id,
            CountEvent.client_mutation_id == mutation_id,
        )
    )
    if existing is not None:
        if existing.session_id != session_id or existing.requirement_id != requirement_id:
            raise CountError("DUPLICATE_MUTATION_PAYLOAD_MISMATCH", "Mutation wurde mit anderer Nutzlast wiederholt.")
        return _result(db, session, requirement, existing.quantity_after or 0, _revision(db, session_id, requirement_id))

    balance = _locked_balance(db, session_id, requirement_id)
    if balance.revision != expected_revision:
        raise CountError("REVISION_CONFLICT", "Der Zählstand wurde inzwischen geändert.")
    quantity_before = balance.quantity
    balance.quantity = quantity
    balance.revision += 1
    db.add(
        CountEvent(
            project_id=session.project_id,
            session_id=session_id,
            requirement_id=requirement_id,
            client_mutation_id=mutation_id,
            operation=CountOperation.SET,
            quantity_before=quantity_before,
            quantity_after=quantity,
        )
    )
    db.flush()
    return _result(db, session, requirement, quantity, balance.revision)


def _validated_entities(
    db: Session, session_id: UUID, requirement_id: UUID
) -> tuple[CountingSession, InventoryRequirement]:
    session = db.get(CountingSession, session_id)
    requirement = db.get(InventoryRequirement, requirement_id)
    if session is None or requirement is None:
        raise CountError("UNKNOWN_INVENTORY_ITEM", "Zählbereich oder Inventarposition wurde nicht gefunden.")
    project = db.get(Project, session.project_id)
    if project is None or project.inventory_snapshot_id != requirement.snapshot_id:
        raise CountError("UNKNOWN_INVENTORY_ITEM", "Die Inventarposition gehört nicht zu diesem Projekt.")
    if session.status is not SessionStatus.IN_PROGRESS:
        raise CountError("SESSION_ARCHIVED", "In diesem Bereich kann nicht mehr gezählt werden.")
    if session.inventory_allocation_enabled and db.scalar(
        select(SessionInventoryAllocation.id).where(
            SessionInventoryAllocation.session_id == session_id,
            SessionInventoryAllocation.requirement_id == requirement_id,
        )
    ) is None:
        raise CountError(
            "INVENTORY_ITEM_NOT_ALLOCATED",
            "Die Inventarposition ist diesem Bereich nicht zugeordnet.",
        )
    return session, requirement


def _locked_balance(db: Session, session_id: UUID, requirement_id: UUID) -> CountBalance:
    db.execute(
        insert(CountBalance)
        .values(session_id=session_id, requirement_id=requirement_id, quantity=0, revision=0)
        .on_conflict_do_nothing(index_elements=["session_id", "requirement_id"])
    )
    balance = db.scalar(
        select(CountBalance)
        .where(CountBalance.session_id == session_id, CountBalance.requirement_id == requirement_id)
        .with_for_update()
    )
    assert balance is not None
    return balance


def _revision(db: Session, session_id: UUID, requirement_id: UUID) -> int:
    balance = db.scalar(
        select(CountBalance).where(
            CountBalance.session_id == session_id, CountBalance.requirement_id == requirement_id
        )
    )
    return balance.revision if balance is not None else 0


def _result(
    db: Session,
    session: CountingSession,
    requirement: InventoryRequirement,
    session_quantity: int,
    revision: int,
) -> dict[str, int | str]:
    global_quantity = db.scalar(
        select(func.coalesce(func.sum(CountBalance.quantity), 0))
        .join(CountingSession, CountBalance.session_id == CountingSession.id)
        .where(
            CountBalance.requirement_id == requirement.id,
            CountingSession.project_id == session.project_id,
            CountingSession.status != SessionStatus.ARCHIVED,
        )
    )
    global_quantity = int(global_quantity or 0)
    delta_global = global_quantity - requirement.expected_qty
    missing_quantity = max(0, -delta_global)
    surplus_quantity = max(0, delta_global)
    return {
        "session_quantity": session_quantity,
        "global_quantity": global_quantity,
        "expected_quantity": requirement.expected_qty,
        "delta_global": delta_global,
        "missing_quantity": missing_quantity,
        "surplus_quantity": surplus_quantity,
        "session_revision": revision,
        "status": "surplus" if surplus_quantity else "provisional_gap" if missing_quantity else "counted",
    }
