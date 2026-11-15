from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from io import StringIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Color,
    InventoryClass,
    InventoryProvenance,
    InventoryRequirement,
    InventorySnapshot,
    LegoSet,
    PartCatalog,
    Project,
    ProjectStatus,
    SnapshotValidationStatus,
)

_REQUIRED_COLUMNS = {"part_num", "color_id", "color_name", "quantity", "inventory_class"}


class CsvImportError(ValueError):
    pass


@dataclass(frozen=True)
class CsvRow:
    part_num: str
    color_id: int
    color_name: str
    quantity: int
    inventory_class: InventoryClass
    part_name: str
    image_url: str | None
    source_type: str
    source_ref: str


def parse_csv_inventory(content: bytes) -> list[CsvRow]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CsvImportError("Die CSV muss UTF-8-kodiert sein.") from error

    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None or not _REQUIRED_COLUMNS <= set(reader.fieldnames):
        raise CsvImportError("Die CSV enthält nicht alle Pflichtspalten.")

    rows: list[CsvRow] = []
    identities: set[tuple[str, int, str]] = set()
    for line_number, row in enumerate(reader, start=2):
        try:
            part_num = (row["part_num"] or "").strip()
            color_id = int(row["color_id"] or "")
            quantity = int(row["quantity"] or "")
            inventory_class = InventoryClass((row["inventory_class"] or "").strip())
        except (TypeError, ValueError) as error:
            raise CsvImportError(f"Ungültige Daten in Zeile {line_number}.") from error
        if not part_num or color_id < 0 or quantity < 0:
            raise CsvImportError(f"Ungültige Daten in Zeile {line_number}.")

        identity = (part_num, color_id, inventory_class.value)
        if identity in identities:
            raise CsvImportError(f"Doppelte Inventarposition in Zeile {line_number}.")
        identities.add(identity)
        rows.append(
            CsvRow(
                part_num=part_num,
                color_id=color_id,
                color_name=(row["color_name"] or "").strip() or f"Farbe {color_id}",
                quantity=quantity,
                inventory_class=inventory_class,
                part_name=(row.get("part_name") or part_num).strip(),
                image_url=(row.get("image_url") or "").strip() or None,
                source_type=(row.get("source_type") or "csv").strip(),
                source_ref=(row.get("source_ref") or "csv").strip(),
            )
        )
    if not rows:
        raise CsvImportError("Die CSV enthält keine Inventarpositionen.")
    return rows


def import_csv_inventory(session: Session, project: Project, content: bytes) -> tuple[bool, int]:
    rows = parse_csv_inventory(content)
    checksum = hashlib.sha256(content).hexdigest()
    existing = session.scalar(
        select(InventorySnapshot).where(
            InventorySnapshot.set_id == project.set_id,
            InventorySnapshot.provider == "csv",
            InventorySnapshot.source_revision == checksum,
        )
    )
    if existing is not None:
        project.inventory_snapshot_id = existing.id
        project.status = ProjectStatus.IN_PROGRESS
        requirements = session.scalar(
            select(func.count()).select_from(InventoryRequirement).where(
                InventoryRequirement.snapshot_id == existing.id
            )
        )
        return False, int(requirements or 0)

    snapshot = InventorySnapshot(
        set_id=project.set_id,
        provider="csv",
        source_revision=checksum,
        validation_status=SnapshotValidationStatus.VALID,
        checksum=checksum,
    )
    session.add(snapshot)
    session.flush()

    for row in rows:
        color = session.scalar(
            select(Color).where(Color.provider == "csv", Color.provider_color_id == row.color_id)
        )
        if color is None:
            color = Color(provider="csv", provider_color_id=row.color_id, name=row.color_name)
            session.add(color)
            session.flush()
        part = session.scalar(
            select(PartCatalog).where(PartCatalog.provider == "csv", PartCatalog.part_num == row.part_num)
        )
        if part is None:
            part = PartCatalog(
                provider="csv",
                part_num=row.part_num,
                name=row.part_name,
                image_url=row.image_url,
            )
            session.add(part)
            session.flush()
        requirement = InventoryRequirement(
            snapshot_id=snapshot.id,
            part_id=part.id,
            color_id=color.id,
            inventory_class=row.inventory_class,
            expected_qty=row.quantity,
        )
        session.add(requirement)
        session.flush()
        session.add(
            InventoryProvenance(
                requirement_id=requirement.id,
                source_type=row.source_type,
                source_ref=row.source_ref,
                quantity=row.quantity,
            )
        )

    project.inventory_snapshot_id = snapshot.id
    project.status = ProjectStatus.IN_PROGRESS
    return True, len(rows)


def create_project(session: Session, set_num: str, label: str) -> Project:
    lego_set = session.scalar(
        select(LegoSet).where(LegoSet.provider == "csv", LegoSet.provider_set_id == set_num)
    )
    if lego_set is None:
        lego_set = LegoSet(provider="csv", provider_set_id=set_num, name=set_num)
        session.add(lego_set)
        session.flush()
    project = Project(set_id=lego_set.id, label=label, status=ProjectStatus.PENDING_IMPORT)
    session.add(project)
    session.flush()
    return project
