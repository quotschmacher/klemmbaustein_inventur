from __future__ import annotations

import json
import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Color,
    CountBalance,
    CountingSession,
    InventoryClass,
    InventoryRequirement,
    LegoSet,
    PartCatalog,
    Project,
    SessionInventoryAllocation,
)
from app.services.inventory_import import CsvImportError, CsvRow, import_inventory_rows
from app.services.rebrickable_project_import import canonical_set_num


_MAX_SNAPSHOT_BYTES = 2_000_000
_EXPECTED_INVENTORIES = {
    "196286": "Anleitung 1",
    "196302": "Anleitung 2",
    "196309": "Anleitung 3",
    "196315": "Anleitung 4",
}
_DECLARED_TOTAL_RE = re.compile(
    r"There\s+are\s*<b>\s*(\d+)\s*</b>\s*parts\s+in\s+this\s+inventory,\s+with\s*<b>\s*(\d+)\s*</b>\s*total\s+quantity",
    re.IGNORECASE | re.DOTALL,
)
_INVENTORY_REF_RE = re.compile(r"/inventory/(\d+)/parts/")
_PART_REF_RE = re.compile(r"^/parts/([^/]+)/")


@dataclass(frozen=True)
class SnapshotPosition:
    part_num: str
    color_id: int
    inventory_class: InventoryClass
    quantity: int


@dataclass(frozen=True)
class ParsedSnapshot:
    inventory_id: str
    positions: tuple[SnapshotPosition, ...]


@dataclass(frozen=True)
class SubsetImportResult:
    sessions: int
    positions: int
    quantity: int


class _SnapshotHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._part_num: str | None = None
        self.positions: list[SnapshotPosition] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a":
            part_ref = _PART_REF_RE.match(attributes.get("href") or "")
            if part_ref:
                self._part_num = part_ref.group(1)
            return
        if tag != "div":
            return
        classes = set((attributes.get("class") or "").split())
        if "js-part-data" not in classes or self._part_num is None:
            return
        raw_color_id = attributes.get("data-color_id")
        raw_quantity = attributes.get("data-quantity")
        if raw_color_id is None or raw_quantity is None:
            raise CsvImportError("Der Rebrickable-Snapshot enthält eine ungültige Teileposition.")
        try:
            color_id = int(raw_color_id)
            quantity = int(raw_quantity)
            inventory_class = InventoryClass.SPARE if attributes.get("data-is_spare") == "1" else InventoryClass.REQUIRED
        except (KeyError, TypeError, ValueError) as error:
            raise CsvImportError("Der Rebrickable-Snapshot enthält eine ungültige Teileposition.") from error
        if color_id < 0 or quantity < 0:
            raise CsvImportError("Der Rebrickable-Snapshot enthält eine ungültige Teileposition.")
        self.positions.append(
            SnapshotPosition(
                part_num=self._part_num,
                color_id=color_id,
                inventory_class=inventory_class,
                quantity=quantity,
            )
        )


def parse_rebrickable_subset_snapshot(content: bytes) -> ParsedSnapshot:
    if len(content) > _MAX_SNAPSHOT_BYTES:
        raise CsvImportError("Der Rebrickable-Snapshot ist zu groß.")
    try:
        payload = json.loads(content.decode("utf-8-sig"))
        status = payload["status"]
        html = payload["html"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise CsvImportError("Die Datei ist kein gültiger Rebrickable-JSON-Snapshot.") from error
    if status != "success" or not isinstance(html, str):
        raise CsvImportError("Der Rebrickable-Snapshot wurde nicht erfolgreich geladen.")

    inventory_ids = set(_INVENTORY_REF_RE.findall(html))
    if len(inventory_ids) != 1:
        raise CsvImportError("Der Rebrickable-Snapshot enthält keine eindeutige Inventar-ID.")
    declared_total = _DECLARED_TOTAL_RE.search(html)
    if declared_total is None:
        raise CsvImportError("Der Rebrickable-Snapshot enthält keine vollständige Mengensumme.")

    parser = _SnapshotHtmlParser()
    try:
        parser.feed(html)
        parser.close()
    except CsvImportError:
        raise
    except Exception as error:
        raise CsvImportError("Der Rebrickable-Snapshot enthält ungültiges HTML.") from error
    if not parser.positions:
        raise CsvImportError("Der Rebrickable-Snapshot enthält keine Teilepositionen.")

    declared_positions, declared_quantity = (int(value) for value in declared_total.groups())
    if len(parser.positions) != declared_positions or sum(item.quantity for item in parser.positions) != declared_quantity:
        raise CsvImportError("Der Rebrickable-Snapshot ist unvollständig oder widersprüchlich.")
    return ParsedSnapshot(inventory_id=inventory_ids.pop(), positions=tuple(parser.positions))


def import_rebrickable_subset_snapshots(
    session: Session, project: Project, snapshots: Iterable[bytes]
) -> SubsetImportResult:
    lego_set = session.get(LegoSet, project.set_id)
    if lego_set is None or canonical_set_num(lego_set.provider_set_id) != "75978-1":
        raise CsvImportError("Anleitungssnapshots werden derzeit nur für das Set 75978-1 unterstützt.")
    if project.inventory_snapshot_id is None:
        raise CsvImportError("Importiere zuerst die globale Stückliste des Sets.")

    parsed = [parse_rebrickable_subset_snapshot(content) for content in snapshots]
    inventory_ids = [snapshot.inventory_id for snapshot in parsed]
    if set(inventory_ids) != set(_EXPECTED_INVENTORIES) or len(inventory_ids) != len(set(inventory_ids)):
        raise CsvImportError("Bitte lade genau je einen vollständigen Snapshot für Anleitung 1 bis Anleitung 4 hoch.")

    sessions = {
        item.label: item
        for item in session.scalars(
            select(CountingSession).where(CountingSession.project_id == project.id)
        ).all()
    }
    expected_labels = set(_EXPECTED_INVENTORIES.values())
    if not expected_labels <= set(sessions):
        raise CsvImportError("Die vier Anleitungsbereiche fehlen im Projekt.")
    if any(item.inventory_allocation_enabled for item in sessions.values()):
        raise CsvImportError("Für dieses Projekt sind bereits Bereichszuordnungen gespeichert.")

    requirements = session.execute(
        select(InventoryRequirement, PartCatalog, Color)
        .join(PartCatalog, InventoryRequirement.part_id == PartCatalog.id)
        .join(Color, InventoryRequirement.color_id == Color.id)
        .where(InventoryRequirement.snapshot_id == project.inventory_snapshot_id)
    ).all()
    requirement_by_key = {
        (part.part_num, color.provider_color_id, requirement.inventory_class): requirement
        for requirement, part, color in requirements
    }
    expected_by_requirement = {requirement.id: requirement.expected_qty for requirement, _, _ in requirements}

    allocated_by_requirement: Counter[object] = Counter()
    snapshot_positions = 0
    snapshot_quantity = 0
    allocations: list[tuple[CountingSession, InventoryRequirement, int]] = []
    for snapshot in parsed:
        target = sessions[_EXPECTED_INVENTORIES[snapshot.inventory_id]]
        quantities: Counter[tuple[str, int, InventoryClass]] = Counter()
        for position in snapshot.positions:
            quantities[(position.part_num, position.color_id, position.inventory_class)] += position.quantity
            snapshot_quantity += position.quantity
        snapshot_positions += len(quantities)
        for key, quantity in quantities.items():
            requirement = requirement_by_key.get(key)
            if requirement is None:
                raise CsvImportError(
                    f"{_EXPECTED_INVENTORIES[snapshot.inventory_id]} enthält {key[0]} in Farbe {key[1]}, "
                    "das nicht in der globalen Stückliste liegt."
                )
            allocated_by_requirement[requirement.id] += quantity
            allocations.append((target, requirement, quantity))

    for requirement_id, allocated_quantity in allocated_by_requirement.items():
        if allocated_quantity > expected_by_requirement[requirement_id]:
            raise CsvImportError("Die Anleitungssnapshots überschreiten eine Sollmenge der globalen Stückliste.")

    for target, requirement, quantity in allocations:
        session.add(
            SessionInventoryAllocation(
                session_id=target.id,
                requirement_id=requirement.id,
                expected_qty=quantity,
            )
        )
    for label in expected_labels:
        sessions[label].inventory_allocation_enabled = True

    figures = sessions.get("Figuren")
    if figures is not None:
        for requirement_id, expected_quantity in expected_by_requirement.items():
            remaining_quantity = expected_quantity - allocated_by_requirement[requirement_id]
            if remaining_quantity > 0:
                session.add(
                    SessionInventoryAllocation(
                        session_id=figures.id,
                        requirement_id=requirement_id,
                        expected_qty=remaining_quantity,
                    )
                )
        figures.inventory_allocation_enabled = True

    return SubsetImportResult(
        sessions=len(expected_labels), positions=snapshot_positions, quantity=snapshot_quantity
    )


def import_rebrickable_json_inventory(
    session: Session, project: Project, snapshots: Iterable[bytes]
) -> tuple[bool, int]:
    contents = list(snapshots)
    if not contents:
        raise CsvImportError("Bitte lade mindestens einen Rebrickable-JSON-Snapshot hoch.")
    existing_rows: list[CsvRow] = []
    prior_checksum = ""
    if project.inventory_snapshot_id is not None:
        has_counts = session.scalar(
            select(CountBalance.id)
            .join(CountingSession, CountBalance.session_id == CountingSession.id)
            .where(CountingSession.project_id == project.id)
            .limit(1)
        )
        if has_counts is not None:
            raise CsvImportError("Nach Beginn der Zählung kann keine weitere JSON-Teilliste ergänzt werden.")
        existing_rows = [
            CsvRow(
                part_num=part.part_num,
                color_id=color.provider_color_id,
                color_name=color.name,
                quantity=requirement.expected_qty,
                inventory_class=requirement.inventory_class,
                part_name=part.name,
                image_url=part.image_url,
                source_type="previous_json_snapshot",
                source_ref=str(project.inventory_snapshot_id),
            )
            for requirement, part, color in session.execute(
                select(InventoryRequirement, PartCatalog, Color)
                .join(PartCatalog, InventoryRequirement.part_id == PartCatalog.id)
                .join(Color, InventoryRequirement.color_id == Color.id)
                .where(InventoryRequirement.snapshot_id == project.inventory_snapshot_id)
            ).all()
        ]
        prior_checksum = str(project.inventory_snapshot_id)
    quantities: Counter[tuple[str, int, InventoryClass]] = Counter()
    provenance: dict[tuple[str, int, InventoryClass], list[tuple[str, str, int]]] = {}
    for snapshot in (parse_rebrickable_subset_snapshot(content) for content in contents):
        for position in snapshot.positions:
            key = (position.part_num, position.color_id, position.inventory_class)
            quantities[key] += position.quantity
            provenance.setdefault(key, []).append(("rebrickable_snapshot", snapshot.inventory_id, position.quantity))
    new_rows = [
        CsvRow(
            part_num=part_num,
            color_id=color_id,
            color_name=f"Farbe {color_id}",
            quantity=quantity,
            inventory_class=inventory_class,
            part_name=part_num,
            image_url=None,
            source_type="rebrickable_snapshot",
            source_ref="json",
            provenance=tuple(provenance[(part_num, color_id, inventory_class)]),
        )
        for (part_num, color_id, inventory_class), quantity in quantities.items()
    ]
    merged: dict[tuple[str, int, InventoryClass], CsvRow] = {}
    for row in [*existing_rows, *new_rows]:
        key = (row.part_num, row.color_id, row.inventory_class)
        previous = merged.get(key)
        merged[key] = row if previous is None else CsvRow(
            part_num=row.part_num,
            color_id=row.color_id,
            color_name=row.color_name,
            quantity=previous.quantity + row.quantity,
            inventory_class=row.inventory_class,
            part_name=row.part_name,
            image_url=row.image_url or previous.image_url,
            source_type=row.source_type,
            source_ref=row.source_ref,
            provenance=(*previous.provenance, *row.provenance),
        )
    rows = list(merged.values())
    checksum = hashlib.sha256(prior_checksum.encode() + b"".join(contents)).hexdigest()
    return import_inventory_rows(
        session,
        project,
        provider="rebrickable_snapshot",
        source_revision=checksum,
        checksum=checksum,
        rows=rows,
    )
