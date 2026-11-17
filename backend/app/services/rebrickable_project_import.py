from __future__ import annotations

import hashlib
import json
import re

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Color,
    InventoryRequirement,
    InventorySnapshot,
    LegoSet,
    PartCatalog,
    MinifigRequirement,
    Project,
    ProjectStatus,
    SessionInventoryAllocation,
    SnapshotValidationStatus,
    CountingSession,
)
from app.services.inventory_import import CsvImportError, import_inventory_rows
from app.services.rebrickable import RebrickableClient
from app.services.rebrickable_import import rebrickable_rows


def canonical_set_num(entered_set_num: str) -> str:
    value = entered_set_num.strip()
    return f"{value}-1" if re.fullmatch(r"\d+", value) else value


class RebrickableProjectImporter:
    def __init__(self, client: RebrickableClient) -> None:
        self._client = client

    def import_project(self, session: Session, project: Project) -> tuple[bool, int]:
        lego_set = session.get(LegoSet, project.set_id)
        if lego_set is None:
            raise CsvImportError("Das Projekt besitzt kein Set.")
        set_num = canonical_set_num(lego_set.provider_set_id)
        instruction_set = set_num == "75978-1"
        cached_snapshot = session.scalar(
            select(InventorySnapshot)
            .where(
                InventorySnapshot.set_id == project.set_id,
                InventorySnapshot.provider == "rebrickable",
                InventorySnapshot.validation_status == SnapshotValidationStatus.VALID,
            )
            .order_by(InventorySnapshot.imported_at.desc())
        )
        if cached_snapshot is not None and (
            not instruction_set or self._has_instruction_allocations(session, project)
        ):
            project.inventory_snapshot_id = cached_snapshot.id
            project.status = ProjectStatus.IN_PROGRESS
            requirement_count = session.scalar(
                select(func.count()).select_from(InventoryRequirement).where(
                    InventoryRequirement.snapshot_id == cached_snapshot.id
                )
            )
            return False, int(requirement_count or 0)
        instruction_rows = self._fetch_instruction_rows(set_num) if instruction_set else []
        if cached_snapshot is not None:
            project.inventory_snapshot_id = cached_snapshot.id
            project.status = ProjectStatus.IN_PROGRESS
            self._create_instruction_allocations(session, project, instruction_rows)
            requirement_count = session.scalar(
                select(func.count()).select_from(InventoryRequirement).where(
                    InventoryRequirement.snapshot_id == cached_snapshot.id
                )
            )
            return False, int(requirement_count or 0)

        detail = self._client.fetch_object(f"/api/v3/lego/sets/{set_num}/")
        expanded_parts = self._client.fetch_all_pages(f"/api/v3/lego/sets/{set_num}/parts/?inc_minifig_parts=1")
        minifigs = self._client.fetch_all_pages(f"/api/v3/lego/sets/{set_num}/minifigs/")
        rows = rebrickable_rows(expanded_parts)
        minifig_requirements: list[tuple[str, str, int, str | None]] = []
        for minifig in minifigs:
            try:
                fig_ref = str(minifig["set_num"])
                quantity = int(minifig["quantity"])
                fig_name = str(minifig.get("set_name") or fig_ref)
            except (KeyError, TypeError, ValueError) as error:
                raise CsvImportError("Rebrickable lieferte eine ungültige Minifigur.") from error
            minifig_requirements.append(
                (fig_ref, fig_name, quantity, str(minifig["set_img_url"]) if minifig.get("set_img_url") else None)
            )

        checksum = hashlib.sha256(
            json.dumps({"detail": detail, "parts": expanded_parts, "minifigs": minifigs}, sort_keys=True).encode()
        ).hexdigest()
        lego_set.name = str(detail.get("name") or lego_set.name)
        lego_set.year = int(detail["year"]) if detail.get("year") is not None else lego_set.year
        lego_set.image_url = str(detail["set_img_url"]) if detail.get("set_img_url") else lego_set.image_url
        imported, requirement_count = import_inventory_rows(
            session,
            project,
            provider="rebrickable",
            source_revision=checksum,
            checksum=checksum,
            rows=rows,
        )
        if imported and project.inventory_snapshot_id is not None:
            for fig_ref, fig_name, quantity, image_url in minifig_requirements:
                session.add(
                    MinifigRequirement(
                        snapshot_id=project.inventory_snapshot_id,
                        fig_ref=fig_ref,
                        name=fig_name,
                        expected_qty=quantity,
                        image_url=image_url,
                    )
                )
            if instruction_set:
                self._create_instruction_allocations(session, project, instruction_rows)
        return imported, requirement_count

    def _fetch_instruction_rows(self, set_num: str) -> list[list]:
        return [
            rebrickable_rows(
                self._client.fetch_all_pages(f"/api/v3/lego/sets/{set_num}-s{position}/parts/?inc_minifig_parts=1")
            )
            for position in range(1, 5)
        ]

    def _has_instruction_allocations(self, session: Session, project: Project) -> bool:
        return bool(
            session.scalar(
                select(SessionInventoryAllocation.id)
                .join(CountingSession, SessionInventoryAllocation.session_id == CountingSession.id)
                .where(CountingSession.project_id == project.id)
            )
        )

    def _create_instruction_allocations(self, session: Session, project: Project, instruction_rows: list[list]) -> None:
        if project.inventory_snapshot_id is None:
            raise CsvImportError("Das Projekt besitzt kein Inventar.")
        sessions = session.scalars(
            select(CountingSession)
            .where(CountingSession.project_id == project.id)
            .order_by(CountingSession.position)
        ).all()
        labels = [f"Anleitung {position}" for position in range(1, 5)]
        if [item.label for item in sessions] != labels:
            raise CsvImportError("Die Anleitungsbereiche stimmen nicht mit den vier Teilmodellen überein.")
        requirements = session.execute(
            select(InventoryRequirement, PartCatalog, Color)
            .join(PartCatalog, InventoryRequirement.part_id == PartCatalog.id)
            .join(Color, InventoryRequirement.color_id == Color.id)
            .where(InventoryRequirement.snapshot_id == project.inventory_snapshot_id)
        ).all()
        by_identity = {
            (part.part_num, color.provider_color_id, requirement.inventory_class): requirement
            for requirement, part, color in requirements
        }
        for counting_session, rows in zip(sessions, instruction_rows, strict=True):
            counting_session.inventory_allocation_enabled = True
            for row in rows:
                requirement = by_identity.get((row.part_num, row.color_id, row.inventory_class))
                if requirement is None:
                    raise CsvImportError("Ein Anleitungs-Teilmodell enthält keine Position des Hauptinventars.")
                session.add(
                    SessionInventoryAllocation(
                        session_id=counting_session.id,
                        requirement_id=requirement.id,
                        expected_qty=row.quantity,
                    )
                )


def default_importer(api_key: str) -> RebrickableProjectImporter:
    http_client = httpx.Client(base_url="https://rebrickable.com", follow_redirects=False)
    return RebrickableProjectImporter(RebrickableClient(api_key, http_client))
