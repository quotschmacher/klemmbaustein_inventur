from __future__ import annotations

import hashlib
import json
import re

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    InventoryRequirement,
    InventorySnapshot,
    KlemmbausteinSet,
    MinifigRequirement,
    Project,
    ProjectStatus,
    SnapshotValidationStatus,
)
from app.services.inventory_import import CsvImportError, CsvRow, import_inventory_rows
from app.services.rebrickable import RebrickableClient
from app.services.rebrickable_import import rebrickable_rows


def canonical_set_num(entered_set_num: str) -> str:
    value = entered_set_num.strip()
    return f"{value}-1" if re.fullmatch(r"\d+", value) else value


class RebrickableProjectImporter:
    def __init__(self, client: RebrickableClient) -> None:
        self._client = client

    def import_project(self, session: Session, project: Project) -> tuple[bool, int]:
        klemmbaustein_set = session.get(KlemmbausteinSet, project.set_id)
        if klemmbaustein_set is None:
            raise CsvImportError("Das Projekt besitzt kein Set.")
        set_num = canonical_set_num(klemmbaustein_set.provider_set_id)
        cached_snapshot = session.scalar(
            select(InventorySnapshot)
            .where(
                InventorySnapshot.set_id == project.set_id,
                InventorySnapshot.provider == "rebrickable",
                InventorySnapshot.source_revision.like("v2:%"),
                InventorySnapshot.validation_status == SnapshotValidationStatus.VALID,
            )
            .order_by(InventorySnapshot.imported_at.desc())
        )
        if cached_snapshot is not None:
            project.inventory_snapshot_id = cached_snapshot.id
            project.status = ProjectStatus.IN_PROGRESS
            requirement_count = session.scalar(
                select(func.count()).select_from(InventoryRequirement).where(
                    InventoryRequirement.snapshot_id == cached_snapshot.id
                )
            )
            return False, int(requirement_count or 0)

        detail = self._client.fetch_object(f"/api/v3/lego/sets/{set_num}/")
        set_parts = self._client.fetch_all_pages(f"/api/v3/lego/sets/{set_num}/parts/?inc_minifig_parts=0")
        minifigs = self._client.fetch_all_pages(f"/api/v3/lego/sets/{set_num}/minifigs/")
        rows = rebrickable_rows(set_parts)
        minifig_requirements: list[tuple[str, str, int, str | None]] = []
        minifig_component_rows = []
        minifig_components: dict[str, list[dict[str, object]]] = {}
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
            components = self._client.fetch_all_pages(f"/api/v3/lego/minifigs/{fig_ref}/parts/")
            minifig_components[fig_ref] = components
            minifig_component_rows.extend(
                rebrickable_rows(
                    (), minifig_items=components, minifig_quantity=quantity, fig_ref=fig_ref
                )
            )
        rows = _merge_rows([*rows, *minifig_component_rows])

        checksum = hashlib.sha256(
            json.dumps(
                {"detail": detail, "parts": set_parts, "minifigs": minifigs, "minifig_components": minifig_components},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        klemmbaustein_set.name = str(detail.get("name") or klemmbaustein_set.name)
        klemmbaustein_set.year = int(detail["year"]) if detail.get("year") is not None else klemmbaustein_set.year
        klemmbaustein_set.image_url = str(detail["set_img_url"]) if detail.get("set_img_url") else klemmbaustein_set.image_url
        imported, requirement_count = import_inventory_rows(
            session,
            project,
            provider="rebrickable",
            source_revision=f"v2:{checksum}",
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
        return imported, requirement_count


def default_importer(api_key: str) -> RebrickableProjectImporter:
    http_client = httpx.Client(base_url="https://rebrickable.com", follow_redirects=False)
    return RebrickableProjectImporter(RebrickableClient(api_key, http_client))


def _merge_rows(rows: list[CsvRow]) -> list[CsvRow]:
    merged: dict[tuple[str, int, object], CsvRow] = {}
    for row in rows:
        key = (row.part_num, row.color_id, row.inventory_class)
        existing = merged.get(key)
        if existing is None:
            merged[key] = row
            continue
        merged[key] = CsvRow(
            part_num=existing.part_num,
            color_id=existing.color_id,
            color_name=existing.color_name,
            quantity=existing.quantity + row.quantity,
            inventory_class=existing.inventory_class,
            part_name=existing.part_name,
            image_url=existing.image_url or row.image_url,
            source_type=existing.source_type,
            source_ref=existing.source_ref,
            color_rgb=existing.color_rgb or row.color_rgb,
            provenance=(*existing.provenance, *row.provenance),
        )
    return list(merged.values())
