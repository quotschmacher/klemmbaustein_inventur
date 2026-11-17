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
    CountingSession,
    SessionStatus,
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
    color_rgb: str | None = None
    provenance: tuple[tuple[str, str, int], ...] = ()


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
                color_rgb=(row.get("color_rgb") or "").strip().lstrip("#") or None,
            )
        )
    if not rows:
        raise CsvImportError("Die CSV enthält keine Inventarpositionen.")
    return rows


def import_csv_inventory(session: Session, project: Project, content: bytes) -> tuple[bool, int]:
    rows = parse_csv_inventory(content)
    checksum = hashlib.sha256(content).hexdigest()
    return import_inventory_rows(
        session,
        project,
        provider="csv",
        source_revision=checksum,
        checksum=checksum,
        rows=rows,
    )


def import_inventory_rows(
    session: Session,
    project: Project,
    *,
    provider: str,
    source_revision: str,
    checksum: str,
    rows: list[CsvRow],
) -> tuple[bool, int]:
    existing = session.scalar(
        select(InventorySnapshot).where(
            InventorySnapshot.set_id == project.set_id,
            InventorySnapshot.provider == provider,
            InventorySnapshot.source_revision == source_revision,
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
        provider=provider,
        source_revision=source_revision,
        validation_status=SnapshotValidationStatus.VALID,
        checksum=checksum,
    )
    session.add(snapshot)
    session.flush()

    for row in rows:
        color = session.scalar(
            select(Color).where(Color.provider == provider, Color.provider_color_id == row.color_id)
        )
        if color is None:
            color = Color(provider=provider, provider_color_id=row.color_id, name=row.color_name, rgb=row.color_rgb)
            session.add(color)
            session.flush()
        elif color.rgb is None and row.color_rgb:
            color.rgb = row.color_rgb
        part = session.scalar(
            select(PartCatalog).where(PartCatalog.provider == provider, PartCatalog.part_num == row.part_num)
        )
        if part is None:
            part = PartCatalog(
                provider=provider,
                part_num=row.part_num,
                name=row.part_name,
                image_url=row.image_url,
            )
            session.add(part)
            session.flush()
        elif part.image_url is None and row.image_url:
            part.image_url = row.image_url
        requirement = InventoryRequirement(
            snapshot_id=snapshot.id,
            part_id=part.id,
            color_id=color.id,
            inventory_class=row.inventory_class,
            expected_qty=row.quantity,
        )
        session.add(requirement)
        session.flush()
        provenance = row.provenance or ((row.source_type, row.source_ref, row.quantity),)
        for source_type, source_ref, quantity in provenance:
            session.add(
                InventoryProvenance(
                    requirement_id=requirement.id,
                    source_type=source_type,
                    source_ref=source_ref,
                    quantity=quantity,
                )
            )

    project.inventory_snapshot_id = snapshot.id
    project.status = ProjectStatus.IN_PROGRESS
    return True, len(rows)


def create_project(
    session: Session, set_num: str, label: str, session_labels: list[str] | None = None
) -> Project:
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
    labels = _session_labels_for_new_project(set_num, session_labels)
    for position, session_label in enumerate(labels):
        session.add(
            CountingSession(
                project_id=project.id,
                label=session_label,
                position=position,
                mandatory=True,
                status=SessionStatus.IN_PROGRESS,
            )
        )
    return project


def _session_labels_for_new_project(set_num: str, session_labels: list[str] | None) -> list[str]:
    if session_labels:
        labels = [label.strip() for label in session_labels if label.strip()]
        if not labels or len(labels) != len(set(labels)):
            raise CsvImportError("Bereichsnamen müssen eindeutig und nicht leer sein.")
        return labels
    if set_num.strip().removesuffix("-1") == "75978":
        return ["Anleitung 1", "Anleitung 2", "Anleitung 3", "Anleitung 4", "Minifiguren"]
    return ["Unsortiert"]
