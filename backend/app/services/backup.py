from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Color,
    CountBalance,
    CountEvent,
    CountingSession,
    InventoryClass,
    InventoryProvenance,
    InventoryRequirement,
    InventorySnapshot,
    LegoSet,
    MinifigRequirement,
    PartCatalog,
    Project,
    ProjectEvent,
    ProjectStatus,
    ReplacementItem,
    ReplacementOrder,
    SessionStatus,
    SnapshotValidationStatus,
    UnlistedFind,
)

BACKUP_SCHEMA_VERSION = 1


class BackupValidationError(ValueError):
    pass


def project_backup(db: Session, project_id: UUID) -> dict[str, object]:
    project = db.get(Project, project_id)
    if project is None or project.inventory_snapshot_id is None:
        raise BackupValidationError("Inventar nicht gefunden.")
    lego_set = db.get(LegoSet, project.set_id)
    snapshot = db.get(InventorySnapshot, project.inventory_snapshot_id)
    if lego_set is None or snapshot is None:
        raise BackupValidationError("Projektbackup ist unvollständig.")

    requirements = db.execute(
        select(InventoryRequirement, PartCatalog, Color)
        .join(PartCatalog, InventoryRequirement.part_id == PartCatalog.id)
        .join(Color, InventoryRequirement.color_id == Color.id)
        .where(InventoryRequirement.snapshot_id == snapshot.id)
        .order_by(PartCatalog.part_num, Color.provider_color_id, InventoryRequirement.inventory_class)
    ).all()
    requirement_ids = [requirement.id for requirement, _, _ in requirements]
    provenance = db.scalars(
        select(InventoryProvenance)
        .where(InventoryProvenance.requirement_id.in_(requirement_ids))
        .order_by(InventoryProvenance.requirement_id, InventoryProvenance.id)
    ).all() if requirement_ids else []
    sessions = db.scalars(
        select(CountingSession).where(CountingSession.project_id == project.id).order_by(CountingSession.position)
    ).all()
    session_ids = [item.id for item in sessions]
    balances = db.scalars(
        select(CountBalance).where(CountBalance.session_id.in_(session_ids)).order_by(CountBalance.id)
    ).all() if session_ids else []
    events = db.scalars(
        select(CountEvent).where(CountEvent.project_id == project.id).order_by(CountEvent.created_at, CountEvent.id)
    ).all()
    orders = db.scalars(
        select(ReplacementOrder).where(ReplacementOrder.project_id == project.id).order_by(ReplacementOrder.created_at, ReplacementOrder.id)
    ).all()
    order_ids = [item.id for item in orders]
    replacement_items = db.scalars(
        select(ReplacementItem).where(ReplacementItem.order_id.in_(order_ids)).order_by(ReplacementItem.id)
    ).all() if order_ids else []
    extra_finds = db.scalars(
        select(UnlistedFind).where(UnlistedFind.session_id.in_(session_ids)).order_by(UnlistedFind.id)
    ).all() if session_ids else []
    project_events = db.scalars(
        select(ProjectEvent).where(ProjectEvent.project_id == project.id).order_by(ProjectEvent.created_at, ProjectEvent.id)
    ).all()

    return {
        "schema_version": BACKUP_SCHEMA_VERSION,
        "project": {
            "id": str(project.id),
            "label": project.label,
            "status": project.status.value,
            "archived_at": _timestamp(project.archived_at),
            "set": _set_data(lego_set),
        },
        "inventory_snapshot": {
            "id": str(snapshot.id),
            "provider": snapshot.provider,
            "source_revision": snapshot.source_revision,
            "imported_at": _timestamp(snapshot.imported_at),
            "validation_status": snapshot.validation_status.value,
            "checksum": snapshot.checksum,
            "requirements": [
                {
                    "id": str(requirement.id),
                    "inventory_class": requirement.inventory_class.value,
                    "expected_qty": requirement.expected_qty,
                    "part": _part_data(part),
                    "color": _color_data(color),
                }
                for requirement, part, color in requirements
            ],
            "provenance": [_provenance_data(item) for item in provenance],
            "minifig_requirements": [_minifig_data(item) for item in db.scalars(
                select(MinifigRequirement)
                .where(MinifigRequirement.snapshot_id == snapshot.id)
                .order_by(MinifigRequirement.fig_ref)
            ).all()],
        },
        "sessions": [_session_data(item) for item in sessions],
        "count_balances": [_balance_data(item) for item in balances],
        "count_events": [_count_event_data(item) for item in events],
        "replacement_orders": [_replacement_order_data(item) for item in orders],
        "replacement_items": [_replacement_item_data(item) for item in replacement_items],
        "extra_finds": [_extra_find_data(item) for item in extra_finds],
        "project_events": [_project_event_data(item) for item in project_events],
    }


def restore_project_backup(db: Session, backup: object) -> tuple[Project, UUID]:
    data = _validated_backup(backup)
    source_project_id = _uuid(data["project"]["id"], "project.id")
    snapshot_data = data["inventory_snapshot"]
    set_data = data["project"]["set"]
    lego_set = db.scalar(
        select(LegoSet).where(
            LegoSet.provider == set_data["provider"],
            LegoSet.provider_set_id == set_data["provider_set_id"],
        )
    )
    if lego_set is None:
        lego_set = LegoSet(
            provider=set_data["provider"],
            provider_set_id=set_data["provider_set_id"],
            name=set_data["name"],
            year=set_data.get("year"),
            image_url=set_data.get("image_url"),
        )
        db.add(lego_set)
        db.flush()

    snapshot, requirement_map = _restore_or_reuse_snapshot(db, lego_set, snapshot_data)
    project_data = data["project"]
    project = Project(
        set_id=lego_set.id,
        inventory_snapshot_id=snapshot.id,
        label=f"{project_data['label']} (Wiederhergestellt)",
        status=ProjectStatus(project_data["status"]),
    )
    db.add(project)
    db.flush()

    session_map: dict[str, UUID] = {}
    for item in data["sessions"]:
        source_id = _uuid(item["id"], "sessions.id")
        restored = CountingSession(
            project_id=project.id,
            label=item["label"],
            position=_integer(item["position"], "sessions.position", minimum=0),
            mandatory=_boolean(item["mandatory"], "sessions.mandatory"),
            status=SessionStatus(item["status"]),
        )
        db.add(restored)
        db.flush()
        session_map[str(source_id)] = restored.id

    for item in data["count_balances"]:
        db.add(
            CountBalance(
                session_id=_reference(session_map, item["session_id"], "count_balances.session_id"),
                requirement_id=_reference(requirement_map, item["requirement_id"], "count_balances.requirement_id"),
                quantity=_integer(item["quantity"], "count_balances.quantity", minimum=0),
                revision=_integer(item["revision"], "count_balances.revision", minimum=0),
            )
        )

    order_map: dict[str, UUID] = {}
    for item in data["replacement_orders"]:
        source_id = _uuid(item["id"], "replacement_orders.id")
        restored = ReplacementOrder(project_id=project.id, status=item["status"], notes=item.get("notes"))
        db.add(restored)
        db.flush()
        order_map[str(source_id)] = restored.id

    replacement_item_map: dict[str, UUID] = {}
    for item in data["replacement_items"]:
        source_id = _uuid(item["id"], "replacement_items.id")
        target_session_id = item.get("target_session_id")
        restored = ReplacementItem(
            order_id=_reference(order_map, item["order_id"], "replacement_items.order_id"),
            requirement_id=_reference(requirement_map, item["requirement_id"], "replacement_items.requirement_id"),
            qty_ordered=_integer(item["qty_ordered"], "replacement_items.qty_ordered", minimum=0),
            qty_received=_integer(item["qty_received"], "replacement_items.qty_received", minimum=0),
            qty_booked=_integer(item["qty_booked"], "replacement_items.qty_booked", minimum=0),
            target_session_id=(
                _reference(session_map, target_session_id, "replacement_items.target_session_id")
                if target_session_id is not None
                else None
            ),
        )
        db.add(restored)
        db.flush()
        replacement_item_map[str(source_id)] = restored.id

    for item in data["count_events"]:
        order_item_id = item.get("order_item_id")
        db.add(
            CountEvent(
                project_id=project.id,
                session_id=_reference(session_map, item["session_id"], "count_events.session_id"),
                requirement_id=_reference(requirement_map, item["requirement_id"], "count_events.requirement_id"),
                client_mutation_id=_uuid(item["client_mutation_id"], "count_events.client_mutation_id"),
                operation=item["operation"],
                delta=item.get("delta"),
                quantity_before=item.get("quantity_before"),
                quantity_after=item.get("quantity_after"),
                order_item_id=(
                    _reference(replacement_item_map, order_item_id, "count_events.order_item_id")
                    if order_item_id is not None
                    else None
                ),
            )
        )

    for item in data["extra_finds"]:
        db.add(
            UnlistedFind(
                session_id=_reference(session_map, item["session_id"], "extra_finds.session_id"),
                part_num=item.get("part_num"),
                color_ref=item.get("color_ref"),
                label=item["label"],
                qty=_integer(item["qty"], "extra_finds.qty", minimum=0),
                resolution_status=item["resolution_status"],
            )
        )
    for item in data["project_events"]:
        db.add(ProjectEvent(project_id=project.id, event_type=item["event_type"], details=item["details"]))
    return project, source_project_id


def _restore_or_reuse_snapshot(
    db: Session, lego_set: LegoSet, snapshot_data: dict[str, object]
) -> tuple[InventorySnapshot, dict[str, UUID]]:
    snapshot = db.scalar(
        select(InventorySnapshot).where(
            InventorySnapshot.set_id == lego_set.id,
            InventorySnapshot.provider == snapshot_data["provider"],
            InventorySnapshot.source_revision == snapshot_data["source_revision"],
        )
    )
    if snapshot is not None:
        if snapshot.checksum != snapshot_data["checksum"]:
            raise BackupValidationError("Snapshot-Prüfsumme stimmt nicht mit dem vorhandenen Inventar überein.")
    else:
        snapshot = InventorySnapshot(
            set_id=lego_set.id,
            provider=snapshot_data["provider"],
            source_revision=snapshot_data["source_revision"],
            validation_status=SnapshotValidationStatus(snapshot_data["validation_status"]),
            checksum=snapshot_data["checksum"],
        )
        db.add(snapshot)
        db.flush()

    existing_requirements = db.execute(
        select(InventoryRequirement, PartCatalog, Color)
        .join(PartCatalog, InventoryRequirement.part_id == PartCatalog.id)
        .join(Color, InventoryRequirement.color_id == Color.id)
        .where(InventoryRequirement.snapshot_id == snapshot.id)
    ).all()
    existing_by_identity = {
        (part.provider, part.part_num, color.provider, color.provider_color_id, requirement.inventory_class.value): requirement.id
        for requirement, part, color in existing_requirements
    }
    requirement_map: dict[str, UUID] = {}
    created_requirement_map: dict[str, UUID] = {}
    for item in snapshot_data["requirements"]:
        source_id = str(_uuid(item["id"], "inventory_snapshot.requirements.id"))
        part_data = item["part"]
        color_data = item["color"]
        identity = (
            part_data["provider"],
            part_data["part_num"],
            color_data["provider"],
            _integer(color_data["provider_color_id"], "inventory_snapshot.requirements.color.provider_color_id", minimum=0),
            item["inventory_class"],
        )
        existing = existing_by_identity.get(identity)
        if existing is not None:
            requirement_map[source_id] = existing
            continue
        part = _part(db, part_data)
        color = _color(db, color_data)
        requirement = InventoryRequirement(
            snapshot_id=snapshot.id,
            part_id=part.id,
            color_id=color.id,
            inventory_class=InventoryClass(item["inventory_class"]),
            expected_qty=_integer(item["expected_qty"], "inventory_snapshot.requirements.expected_qty", minimum=0),
        )
        db.add(requirement)
        db.flush()
        requirement_map[source_id] = requirement.id
        created_requirement_map[source_id] = requirement.id
    for item in snapshot_data["provenance"]:
        source_requirement_id = str(_uuid(item["requirement_id"], "inventory_snapshot.provenance.requirement_id"))
        if source_requirement_id not in created_requirement_map:
            continue
        db.add(
            InventoryProvenance(
                requirement_id=created_requirement_map[source_requirement_id],
                source_type=item["source_type"],
                source_ref=item["source_ref"],
                quantity=_integer(item["quantity"], "inventory_snapshot.provenance.quantity", minimum=0),
            )
        )
    for item in snapshot_data["minifig_requirements"]:
        existing = db.scalar(
            select(MinifigRequirement).where(
                MinifigRequirement.snapshot_id == snapshot.id,
                MinifigRequirement.fig_ref == item["fig_ref"],
            )
        )
        if existing is None:
            db.add(
                MinifigRequirement(
                    snapshot_id=snapshot.id,
                    fig_ref=item["fig_ref"],
                    name=item["name"],
                    expected_qty=_integer(item["expected_qty"], "minifig_requirements.expected_qty", minimum=0),
                    image_url=item.get("image_url"),
                )
            )
    return snapshot, requirement_map


def _validated_backup(backup: object) -> dict[str, object]:
    if not isinstance(backup, dict):
        raise BackupValidationError("Backup muss ein JSON-Objekt sein.")
    if backup.get("schema_version") != BACKUP_SCHEMA_VERSION:
        raise BackupValidationError("Nicht unterstützte Backup-Schemaversion.")
    required = {
        "project",
        "inventory_snapshot",
        "sessions",
        "count_balances",
        "count_events",
        "replacement_orders",
        "replacement_items",
        "extra_finds",
        "project_events",
    }
    if not required <= backup.keys():
        raise BackupValidationError("Backup enthält nicht alle Pflichtbereiche.")
    if not isinstance(backup["project"], dict) or not isinstance(backup["inventory_snapshot"], dict):
        raise BackupValidationError("Backup-Metadaten sind ungültig.")
    for key in required - {"project", "inventory_snapshot"}:
        if not isinstance(backup[key], list):
            raise BackupValidationError(f"Backup-Bereich {key} ist ungültig.")
    project = backup["project"]
    snapshot = backup["inventory_snapshot"]
    if not {"id", "label", "status", "set"} <= project.keys() or not isinstance(project["set"], dict):
        raise BackupValidationError("Projekt-Metadaten sind ungültig.")
    if not {"provider", "source_revision", "validation_status", "checksum", "requirements", "provenance", "minifig_requirements"} <= snapshot.keys():
        raise BackupValidationError("Snapshot-Metadaten sind ungültig.")
    if not all(isinstance(snapshot[key], list) for key in ("requirements", "provenance", "minifig_requirements")):
        raise BackupValidationError("Snapshot-Listen sind ungültig.")
    try:
        _uuid(project["id"], "project.id")
        ProjectStatus(project["status"])
        SnapshotValidationStatus(snapshot["validation_status"])
        for key in ("provider", "source_revision", "checksum"):
            _text(snapshot[key], f"inventory_snapshot.{key}")
        for key in ("provider", "provider_set_id", "name"):
            _text(project["set"].get(key), f"project.set.{key}")
        for item in snapshot["requirements"]:
            _uuid(item["id"], "inventory_snapshot.requirements.id")
            InventoryClass(item["inventory_class"])
            _integer(item["expected_qty"], "inventory_snapshot.requirements.expected_qty", minimum=0)
            _text(item["part"]["provider"], "inventory_snapshot.requirements.part.provider")
            _text(item["part"]["part_num"], "inventory_snapshot.requirements.part.part_num")
            _text(item["color"]["provider"], "inventory_snapshot.requirements.color.provider")
            _integer(item["color"]["provider_color_id"], "inventory_snapshot.requirements.color.provider_color_id", minimum=0)
        for item in backup["sessions"]:
            _uuid(item["id"], "sessions.id")
            SessionStatus(item["status"])
            _text(item["label"], "sessions.label")
            _integer(item["position"], "sessions.position", minimum=0)
            _boolean(item["mandatory"], "sessions.mandatory")
    except (KeyError, TypeError, ValueError) as error:
        raise BackupValidationError("Backup enthält ungültige Werte oder Referenzen.") from error
    return backup


def _part(db: Session, data: dict[str, object]) -> PartCatalog:
    part = db.scalar(select(PartCatalog).where(PartCatalog.provider == data["provider"], PartCatalog.part_num == data["part_num"]))
    if part is None:
        part = PartCatalog(
            provider=data["provider"],
            part_num=data["part_num"],
            name=data["name"],
            category=data.get("category"),
            image_url=data.get("image_url"),
            bricklink_part_id=data.get("bricklink_part_id"),
        )
        db.add(part)
        db.flush()
    return part


def _color(db: Session, data: dict[str, object]) -> Color:
    provider_color_id = _integer(data["provider_color_id"], "color.provider_color_id", minimum=0)
    color = db.scalar(select(Color).where(Color.provider == data["provider"], Color.provider_color_id == provider_color_id))
    if color is None:
        color = Color(
            provider=data["provider"],
            provider_color_id=provider_color_id,
            name=data["name"],
            rgb=data.get("rgb"),
            bricklink_id=data.get("bricklink_id"),
        )
        db.add(color)
        db.flush()
    return color


def _set_data(item: LegoSet) -> dict[str, object]:
    return {"provider": item.provider, "provider_set_id": item.provider_set_id, "name": item.name, "year": item.year, "image_url": item.image_url}


def _part_data(item: PartCatalog) -> dict[str, object]:
    return {"provider": item.provider, "part_num": item.part_num, "name": item.name, "category": item.category, "image_url": item.image_url, "bricklink_part_id": item.bricklink_part_id}


def _color_data(item: Color) -> dict[str, object]:
    return {"provider": item.provider, "provider_color_id": item.provider_color_id, "name": item.name, "rgb": item.rgb, "bricklink_id": item.bricklink_id}


def _provenance_data(item: InventoryProvenance) -> dict[str, object]:
    return {"id": str(item.id), "requirement_id": str(item.requirement_id), "source_type": item.source_type, "source_ref": item.source_ref, "quantity": item.quantity}


def _minifig_data(item: MinifigRequirement) -> dict[str, object]:
    return {"id": str(item.id), "fig_ref": item.fig_ref, "name": item.name, "expected_qty": item.expected_qty, "image_url": item.image_url}


def _session_data(item: CountingSession) -> dict[str, object]:
    return {"id": str(item.id), "label": item.label, "position": item.position, "mandatory": item.mandatory, "status": item.status.value}


def _balance_data(item: CountBalance) -> dict[str, object]:
    return {"id": str(item.id), "session_id": str(item.session_id), "requirement_id": str(item.requirement_id), "quantity": item.quantity, "revision": item.revision}


def _count_event_data(item: CountEvent) -> dict[str, object]:
    return {"id": str(item.id), "session_id": str(item.session_id), "requirement_id": str(item.requirement_id), "client_mutation_id": str(item.client_mutation_id), "operation": item.operation.value, "delta": item.delta, "quantity_before": item.quantity_before, "quantity_after": item.quantity_after, "order_item_id": str(item.order_item_id) if item.order_item_id else None}


def _replacement_order_data(item: ReplacementOrder) -> dict[str, object]:
    return {"id": str(item.id), "status": item.status, "notes": item.notes}


def _replacement_item_data(item: ReplacementItem) -> dict[str, object]:
    return {"id": str(item.id), "order_id": str(item.order_id), "requirement_id": str(item.requirement_id), "qty_ordered": item.qty_ordered, "qty_received": item.qty_received, "qty_booked": item.qty_booked, "target_session_id": str(item.target_session_id) if item.target_session_id else None}


def _extra_find_data(item: UnlistedFind) -> dict[str, object]:
    return {"id": str(item.id), "session_id": str(item.session_id), "part_num": item.part_num, "color_ref": item.color_ref, "label": item.label, "qty": item.qty, "resolution_status": item.resolution_status}


def _project_event_data(item: ProjectEvent) -> dict[str, object]:
    return {"id": str(item.id), "event_type": item.event_type, "details": item.details}


def _timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _uuid(value: object, field: str) -> UUID:
    if not isinstance(value, str):
        raise BackupValidationError(f"{field} muss eine UUID sein.")
    try:
        return UUID(value)
    except ValueError as error:
        raise BackupValidationError(f"{field} muss eine UUID sein.") from error


def _integer(value: object, field: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise BackupValidationError(f"{field} ist ungültig.")
    return value


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise BackupValidationError(f"{field} ist ungültig.")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BackupValidationError(f"{field} ist ungültig.")
    return value


def _reference(mapping: dict[str, UUID], value: object, field: str) -> UUID:
    source_id = str(_uuid(value, field))
    try:
        return mapping[source_id]
    except KeyError as error:
        raise BackupValidationError(f"{field} verweist auf kein Backup-Objekt.") from error
