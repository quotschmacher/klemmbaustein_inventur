from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, tostring

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Color,
    CountBalance,
    CountingSession,
    InventoryRequirement,
    PartCatalog,
    Project,
    SessionStatus,
)


from app.services.reconciliation import ReconciliationError, difference_items


class ExportError(ValueError):
    pass


class BrickLinkExportError(ExportError):
    def __init__(self, code: str, message: str, details: dict[str, object]) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def inventory_export_items(db: Session, project_id) -> list[dict[str, object]]:
    project = db.get(Project, project_id)
    if project is None or project.inventory_snapshot_id is None:
        raise ExportError("Inventar nicht gefunden.")

    counts = (
        select(
            CountBalance.requirement_id.label("requirement_id"),
            func.coalesce(func.sum(CountBalance.quantity), 0).label("global_quantity"),
        )
        .join(CountingSession, CountBalance.session_id == CountingSession.id)
        .where(
            CountingSession.project_id == project_id,
            CountingSession.status != SessionStatus.ARCHIVED,
        )
        .group_by(CountBalance.requirement_id)
        .subquery()
    )
    rows = db.execute(
        select(InventoryRequirement, PartCatalog, Color, func.coalesce(counts.c.global_quantity, 0))
        .join(PartCatalog, InventoryRequirement.part_id == PartCatalog.id)
        .join(Color, InventoryRequirement.color_id == Color.id)
        .outerjoin(counts, counts.c.requirement_id == InventoryRequirement.id)
        .where(InventoryRequirement.snapshot_id == project.inventory_snapshot_id)
        .order_by(PartCatalog.part_num, Color.provider_color_id, InventoryRequirement.inventory_class)
    ).all()
    return [
        {
            "part_num": part.part_num,
            "part_name": part.name,
            "color_id": color.provider_color_id,
            "color_name": color.name,
            "inventory_class": requirement.inventory_class.value,
            "expected_quantity": requirement.expected_qty,
            "global_quantity": int(global_quantity),
            "missing_quantity": max(0, requirement.expected_qty - int(global_quantity)),
            "surplus_quantity": max(0, int(global_quantity) - requirement.expected_qty),
        }
        for requirement, part, color, global_quantity in rows
    ]


def bricklink_wanted_list_xml(db: Session, project_id) -> bytes:
    try:
        final, items = difference_items(db, project_id, "missing")
    except ReconciliationError as error:
        raise ExportError(str(error)) from error
    if not final:
        raise BrickLinkExportError(
            "INVENTORY_NOT_READY",
            "BrickLink-Export ist erst nach Abschluss aller Pflichtbereiche möglich.",
            {"unmapped": []},
        )
    project = db.get(Project, project_id)
    if project is None or project.inventory_snapshot_id is None:
        raise ExportError("Inventar nicht gefunden.")
    mapping_rows = db.execute(
        select(PartCatalog, Color)
        .select_from(InventoryRequirement)
        .join(PartCatalog, InventoryRequirement.part_id == PartCatalog.id)
        .join(Color, InventoryRequirement.color_id == Color.id)
        .where(InventoryRequirement.snapshot_id == project.inventory_snapshot_id)
    ).all()
    mappings = {
        (part.part_num, color.provider_color_id): (part.bricklink_part_id, color.bricklink_id)
        for part, color in mapping_rows
    }
    unmapped: list[dict[str, object]] = []
    mapped_items: list[tuple[dict[str, object], str, int]] = []
    for item in items:
        part_id, color_id = mappings[(item["part_num"], item["color_id"])]
        if not part_id or color_id is None:
            unmapped.append(
                {
                    "part_num": item["part_num"],
                    "color_id": item["color_id"],
                    "missing_quantity": item["missing_quantity"],
                    "missing_part_mapping": not bool(part_id),
                    "missing_color_mapping": color_id is None,
                }
            )
        else:
            mapped_items.append((item, part_id, color_id))
    if unmapped:
        raise BrickLinkExportError(
            "BRICKLINK_MAPPING_MISSING",
            "BrickLink-Export verweigert: Für mindestens eine Fehlposition fehlt ein geprüftes Mapping.",
            {"unmapped": unmapped},
        )
    root = Element("INVENTORY")
    for item, part_id, color_id in mapped_items:
        entry = SubElement(root, "ITEM")
        for name, value in (
            ("ITEMTYPE", "P"),
            ("ITEMID", part_id),
            ("COLOR", str(color_id)),
            ("MINQTY", str(item["missing_quantity"])),
            ("CONDITION", "N"),
        ):
            SubElement(entry, name).text = value
    return tostring(root, encoding="utf-8", xml_declaration=True)
