import asyncio
import csv
import os
from datetime import datetime, timezone
from io import StringIO
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
import httpx
from pydantic import BaseModel, Field
from psycopg import connect
from psycopg.errors import OperationalError
from sqlalchemy import func, select

from app.db.models import (
    Color,
    CountBalance,
    CountingSession,
    InventoryRequirement,
    LegoSet,
    PartCatalog,
    Project,
    SessionInventoryAllocation,
    SessionStatus,
)
from app.db.session import create_session_factory
from app.services.counting import CountError, adjust_count, set_count
from app.services.inventory_import import CsvImportError, create_project, import_csv_inventory
from app.services.exports import (
    BrickLinkExportError,
    ExportError,
    bricklink_wanted_list_xml,
    inventory_export_items,
)
from app.services.backup import BackupValidationError, project_backup, restore_project_backup
from app.services.rebrickable import RebrickableClient, RebrickableImportError
from app.services.rebrickable_project_import import RebrickableProjectImporter
from app.services.rebrickable_subset_import import (
    import_rebrickable_json_inventory,
    import_rebrickable_subset_snapshots,
)
from app.services.reconciliation import ReconciliationError, difference_items, project_reconciliation
from app.services.replacements import (
    ReplacementError,
    book_replacement,
    create_combined_replacement_order,
    create_replacement,
    replacement_item_data,
    replacement_items,
    update_replacement,
)
from app.services.unlisted_finds import (
    UnlistedFindError,
    project_unlisted_finds,
    record_unlisted_find,
    unlisted_find_data,
)

app = FastAPI(title="LEGO Inventur API", version="0.1.0")


class ProjectCreateRequest(BaseModel):
    set_num: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=500)
    session_labels: list[str] | None = Field(default=None, max_length=20)


class ProjectArchiveRequest(BaseModel):
    archived: bool


class SessionCreateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=255)
    position: int = Field(ge=0)
    mandatory: bool = True


class SessionPatchRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=255)
    position: int | None = Field(default=None, ge=0)
    mandatory: bool | None = None
    status: SessionStatus | None = None


class CountAdjustRequest(BaseModel):
    inventory_item_id: UUID
    delta: int = Field(ge=-1000, le=1000)
    client_mutation_id: UUID


class CountSetRequest(BaseModel):
    quantity: int = Field(ge=0)
    expected_revision: int = Field(ge=0)
    client_mutation_id: UUID


class UnlistedFindCreateRequest(BaseModel):
    part_num: str | None = Field(default=None, min_length=1, max_length=255)
    color_ref: str | None = Field(default=None, min_length=1, max_length=255)
    label: str = Field(min_length=1, max_length=500)
    qty: int = Field(ge=0)


class ReplacementCreateRequest(BaseModel):
    requirement_id: UUID
    qty_ordered: int = Field(ge=1, le=10000)
    target_session_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CombinedReplacementCreateRequest(BaseModel):
    target_session_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ReplacementPatchRequest(BaseModel):
    qty_ordered: int | None = Field(default=None, ge=0, le=10000)
    qty_received: int | None = Field(default=None, ge=0, le=10000)
    target_session_id: UUID | None = None
    status: Literal["planned", "ordered", "received", "packed"] | None = None


class ReplacementBookingRequest(BaseModel):
    session_id: UUID
    quantity: int = Field(ge=1, le=10000)
    client_mutation_id: UUID


def _database_dsn() -> str:
    database_url = os.environ["DATABASE_URL"]
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _check_database() -> None:
    with connect(_database_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()


@app.get("/health")
async def health() -> dict[str, dict[str, str]]:
    try:
        await asyncio.to_thread(_check_database)
    except (KeyError, OperationalError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Datenbank ist nicht erreichbar.",
        ) from error

    return {"data": {"status": "ok"}}


@app.post("/api/v1/projects", status_code=status.HTTP_201_CREATED)
def create_project_route(payload: ProjectCreateRequest) -> dict[str, dict[str, str]]:
    factory = create_session_factory()
    with factory.begin() as session:
        project = create_project(session, payload.set_num, payload.label, payload.session_labels)
        return {"data": {"id": str(project.id)}}


@app.get("/api/v1/projects")
def list_projects_route(include_archived: bool = False) -> dict[str, list[dict[str, object]]]:
    factory = create_session_factory()
    with factory() as db:
        statement = select(Project, LegoSet).join(LegoSet, Project.set_id == LegoSet.id)
        if not include_archived:
            statement = statement.where(Project.archived_at.is_(None))
        rows = db.execute(statement.order_by(Project.updated_at.desc())).all()
    return {"data": [
        {"id": str(project.id), "label": project.label, "set_num": lego_set.provider_set_id, "status": project.status.value, "archived": project.archived_at is not None}
        for project, lego_set in rows
    ]}


@app.patch("/api/v1/projects/{project_id}")
def archive_project_route(project_id: UUID, payload: ProjectArchiveRequest) -> dict[str, dict[str, object]]:
    factory = create_session_factory()
    with factory.begin() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
        project.archived_at = datetime.now(timezone.utc) if payload.archived else None
        return {"data": {"id": str(project.id), "archived": project.archived_at is not None}}


@app.post("/api/v1/projects/{project_id}/import/csv")
async def import_csv_route(
    project_id: UUID, response: Response, file: UploadFile = File(...)
) -> dict[str, dict[str, int | bool]]:
    content = await file.read()
    factory = create_session_factory()
    try:
        with factory.begin() as session:
            project = session.get(Project, project_id)
            if project is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
            imported, requirements = import_csv_inventory(session, project, content)
    except CsvImportError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    response.status_code = status.HTTP_201_CREATED if imported else status.HTTP_200_OK
    return {"data": {"requirements": requirements, "imported": imported}}


@app.post("/api/v1/projects/{project_id}/import/rebrickable")
def import_rebrickable_route(project_id: UUID, response: Response) -> dict[str, dict[str, int | bool]]:
    api_key = os.environ.get("REBRICKABLE_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="REBRICKABLE_API_KEY ist nicht konfiguriert.",
        )
    factory = create_session_factory()
    try:
        with httpx.Client(base_url="https://rebrickable.com", follow_redirects=False) as http_client:
            importer = RebrickableProjectImporter(RebrickableClient(api_key, http_client))
            with factory.begin() as session:
                project = session.get(Project, project_id)
                if project is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
                imported, requirements = importer.import_project(session, project)
    except (CsvImportError, RebrickableImportError) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    response.status_code = status.HTTP_201_CREATED if imported else status.HTTP_200_OK
    return {"data": {"requirements": requirements, "imported": imported}}


@app.post("/api/v1/projects/{project_id}/import/rebrickable-subsets")
async def import_rebrickable_subsets_route(
    project_id: UUID, response: Response, files: list[UploadFile] = File(...)
) -> dict[str, dict[str, int]]:
    contents = [await file.read() for file in files]
    factory = create_session_factory()
    try:
        with factory.begin() as session:
            project = session.get(Project, project_id)
            if project is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
            result = import_rebrickable_subset_snapshots(session, project, contents)
    except CsvImportError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    response.status_code = status.HTTP_201_CREATED
    return {"data": {"sessions": result.sessions, "positions": result.positions, "quantity": result.quantity}}


@app.post("/api/v1/projects/{project_id}/import/rebrickable-json")
async def import_rebrickable_json_route(
    project_id: UUID, response: Response, files: list[UploadFile] = File(...)
) -> dict[str, dict[str, int | bool]]:
    factory = create_session_factory()
    try:
        with factory.begin() as session:
            project = session.get(Project, project_id)
            if project is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
            imported, requirements = import_rebrickable_json_inventory(
                session, project, [await file.read() for file in files]
            )
    except CsvImportError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    response.status_code = status.HTTP_201_CREATED if imported else status.HTTP_200_OK
    return {"data": {"requirements": requirements, "imported": imported}}


@app.get("/api/v1/projects/{project_id}/inventory")
def inventory_route(
    project_id: UUID,
    session_id: UUID | None = None,
    color_id: int | None = Query(default=None, ge=0),
    search: str | None = Query(default=None, max_length=255),
) -> dict[str, dict[str, object]]:
    factory = create_session_factory()
    with factory() as session:
        project = session.get(Project, project_id)
        if project is None or project.inventory_snapshot_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventar nicht gefunden.")
        global_counts = (
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
        selected_session: CountingSession | None = None
        allocation_quantities: dict[UUID, int] = {}
        if session_id is not None:
            selected_session = session.get(CountingSession, session_id)
            if selected_session is None or selected_session.project_id != project_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bereich nicht gefunden.")
            if selected_session.inventory_allocation_enabled:
                allocation_quantities = dict(
                    session.execute(
                        select(SessionInventoryAllocation.requirement_id, SessionInventoryAllocation.expected_qty).where(
                            SessionInventoryAllocation.session_id == session_id
                        )
                    ).all()
                )
        statement = (
            select(InventoryRequirement, PartCatalog, Color)
            .join(PartCatalog, InventoryRequirement.part_id == PartCatalog.id)
            .join(Color, InventoryRequirement.color_id == Color.id)
            .outerjoin(global_counts, global_counts.c.requirement_id == InventoryRequirement.id)
            .where(InventoryRequirement.snapshot_id == project.inventory_snapshot_id)
        )
        if selected_session is not None and selected_session.inventory_allocation_enabled:
            statement = statement.where(InventoryRequirement.id.in_(allocation_quantities))
        if color_id is not None:
            statement = statement.where(Color.provider_color_id == color_id)
        if search:
            term = f"%{search.strip()}%"
            statement = statement.where(
                PartCatalog.part_num.ilike(term) | PartCatalog.name.ilike(term)
            )
        rows = session.execute(statement.order_by(Color.provider_color_id, PartCatalog.part_num)).all()
        session_balances = {}
        if session_id is not None:
            session_balances = {
                requirement_id: (quantity, revision)
                for requirement_id, quantity, revision in session.execute(
                    select(CountBalance.requirement_id, CountBalance.quantity, CountBalance.revision).where(
                        CountBalance.session_id == session_id
                    )
                ).all()
            }
        global_quantities = dict(
            session.execute(select(global_counts.c.requirement_id, global_counts.c.global_quantity)).all()
        )
    items = [
        {
            "id": str(requirement.id),
            "part_num": part.part_num,
            "part_name": part.name,
            "image_url": requirement.image_url or part.image_url,
            "color_id": color.provider_color_id,
            "color_name": color.name,
            "color_rgb": color.rgb,
            "expected_qty": allocation_quantities.get(requirement.id, requirement.expected_qty),
            "inventory_class": requirement.inventory_class.value,
            "session_quantity": int(session_balances.get(requirement.id, (0, 0))[0]),
            "session_revision": int(session_balances.get(requirement.id, (0, 0))[1]),
            "global_quantity": int(global_quantities.get(requirement.id, 0)),
        }
        for requirement, part, color in rows
    ]
    return {"data": {"total": len(items), "items": items}}


@app.get("/api/v1/projects/{project_id}/sessions")
def list_sessions_route(project_id: UUID) -> dict[str, list[dict[str, object]]]:
    factory = create_session_factory()
    with factory() as db:
        counted_positions = (
            select(
                CountBalance.session_id.label("session_id"),
                func.count(CountBalance.requirement_id).label("counted_positions"),
            )
            .where(CountBalance.quantity > 0)
            .group_by(CountBalance.session_id)
            .subquery()
        )
        rows = db.execute(
            select(CountingSession, func.coalesce(counted_positions.c.counted_positions, 0))
            .outerjoin(counted_positions, counted_positions.c.session_id == CountingSession.id)
            .where(CountingSession.project_id == project_id)
            .order_by(CountingSession.position)
        ).all()
    return {"data": [_session_data(item, int(counted)) for item, counted in rows]}


@app.get("/api/v1/projects/{project_id}/unlisted")
def list_unlisted_finds_route(project_id: UUID) -> dict[str, list[dict[str, object]]]:
    factory = create_session_factory()
    try:
        with factory() as db:
            finds = project_unlisted_finds(db, project_id)
    except UnlistedFindError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return {"data": [unlisted_find_data(find) for find in finds]}


@app.get("/api/v1/projects/{project_id}/summary")
def summary_route(project_id: UUID) -> dict[str, dict[str, object]]:
    factory = create_session_factory()
    try:
        with factory() as db:
            summary, _ = project_reconciliation(db, project_id)
    except ReconciliationError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return {"data": summary}


@app.get("/api/v1/projects/{project_id}/differences")
def differences_route(
    project_id: UUID,
    type: Literal["missing", "surplus", "all"] = Query(default="all"),
) -> dict[str, dict[str, object]]:
    factory = create_session_factory()
    try:
        with factory() as db:
            final, items = difference_items(db, project_id, type)
    except ReconciliationError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return {"data": {"final": final, "items": items}}


@app.get("/api/v1/projects/{project_id}/exports/inventory.csv")
def inventory_csv_export_route(project_id: UUID) -> Response:
    factory = create_session_factory()
    try:
        with factory() as db:
            items = inventory_export_items(db, project_id)
    except ExportError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _csv_response(
        items,
        [
            "part_num",
            "part_name",
            "color_id",
            "color_name",
            "inventory_class",
            "expected_quantity",
            "global_quantity",
            "missing_quantity",
            "surplus_quantity",
        ],
        "inventory.csv",
    )


@app.get("/api/v1/projects/{project_id}/exports/differences.csv")
def differences_csv_export_route(project_id: UUID) -> Response:
    factory = create_session_factory()
    try:
        with factory() as db:
            final, items = difference_items(db, project_id, "all")
    except ReconciliationError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    rows = [
        {
            "difference_type": difference_type,
            "part_num": item["part_num"],
            "part_name": item["part_name"],
            "color_id": item["color_id"],
            "color_name": item["color_name"],
            "expected_quantity": item["expected_quantity"],
            "global_quantity": item["global_quantity"],
            "difference_quantity": item[f"{difference_type}_quantity"],
        }
        for item in items
        for difference_type in ("surplus", "missing")
        if item[f"{difference_type}_quantity"] > 0 and (difference_type != "missing" or final)
    ]
    return _csv_response(
        rows,
        [
            "difference_type",
            "part_num",
            "part_name",
            "color_id",
            "color_name",
            "expected_quantity",
            "global_quantity",
            "difference_quantity",
        ],
        "differences.csv",
    )


@app.get("/api/v1/projects/{project_id}/exports/backup.json")
def backup_json_export_route(project_id: UUID) -> JSONResponse:
    factory = create_session_factory()
    try:
        with factory() as db:
            backup = project_backup(db, project_id)
    except BackupValidationError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return JSONResponse(
        content=jsonable_encoder(backup),
        headers={"Content-Disposition": 'attachment; filename="backup.json"'},
    )


@app.get("/api/v1/projects/{project_id}/exports/wanted-list.xml")
def bricklink_export_route(project_id: UUID) -> Response:
    factory = create_session_factory()
    try:
        with factory() as db:
            xml = bricklink_wanted_list_xml(db, project_id)
    except BrickLinkExportError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": error.code, "message": str(error), "details": error.details},
        ) from error
    except ExportError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="wanted-list.xml"'},
    )


@app.post("/api/v1/projects/import-backup", status_code=status.HTTP_201_CREATED)
def restore_backup_route(backup: dict[str, object]) -> dict[str, dict[str, str]]:
    factory = create_session_factory()
    try:
        with factory.begin() as db:
            project, source_project_id = restore_project_backup(db, backup)
            db.flush()
            result = {"id": str(project.id), "restored_from_project_id": str(source_project_id)}
    except BackupValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_BACKUP_VERSION", "message": str(error)},
        ) from error
    return {"data": result}


@app.get("/api/v1/projects/{project_id}/replacements")
def list_replacements_route(project_id: UUID) -> dict[str, list[dict[str, object]]]:
    factory = create_session_factory()
    with factory() as db:
        return {"data": replacement_items(db, project_id)}


@app.post("/api/v1/projects/{project_id}/replacements", status_code=status.HTTP_201_CREATED)
def create_replacement_route(
    project_id: UUID, payload: ReplacementCreateRequest
) -> dict[str, dict[str, object]]:
    factory = create_session_factory()
    try:
        with factory.begin() as db:
            item = create_replacement(db, project_id=project_id, **payload.model_dump())
            data = replacement_item_data(db, project_id, item.id)
    except ReplacementError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    return {"data": data}


@app.post("/api/v1/projects/{project_id}/replacements/from-confirmed-missing", status_code=status.HTTP_201_CREATED)
def create_combined_replacement_route(
    project_id: UUID, payload: CombinedReplacementCreateRequest
) -> dict[str, dict[str, object]]:
    factory = create_session_factory()
    try:
        with factory.begin() as db:
            order, items = create_combined_replacement_order(
                db, project_id=project_id, **payload.model_dump()
            )
    except ReplacementError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    return {"data": {"order_id": str(order.id), "item_count": len(items)}}


@app.patch("/api/v1/projects/{project_id}/replacements/{replacement_id}")
def patch_replacement_route(
    project_id: UUID, replacement_id: UUID, payload: ReplacementPatchRequest
) -> dict[str, dict[str, object]]:
    factory = create_session_factory()
    try:
        with factory.begin() as db:
            item = update_replacement(
                db, project_id=project_id, item_id=replacement_id, **payload.model_dump(exclude_none=True)
            )
            data = replacement_item_data(db, project_id, item.id)
    except ReplacementError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    return {"data": data}


@app.post("/api/v1/replacements/{replacement_id}/book-into-session")
def book_replacement_route(
    replacement_id: UUID, payload: ReplacementBookingRequest
) -> dict[str, dict[str, int | str]]:
    factory = create_session_factory()
    try:
        with factory.begin() as db:
            result = book_replacement(
                db,
                item_id=replacement_id,
                session_id=payload.session_id,
                quantity=payload.quantity,
                mutation_id=payload.client_mutation_id,
            )
    except ReplacementError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except CountError as error:
        _count_error(error)
    return {"data": result}


@app.post("/api/v1/projects/{project_id}/sessions", status_code=status.HTTP_201_CREATED)
def create_session_route(project_id: UUID, payload: SessionCreateRequest) -> dict[str, dict[str, object]]:
    factory = create_session_factory()
    with factory.begin() as db:
        if db.get(Project, project_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
        counting_session = CountingSession(project_id=project_id, **payload.model_dump())
        db.add(counting_session)
        db.flush()
        return {"data": _session_data(counting_session)}


@app.patch("/api/v1/sessions/{session_id}")
def patch_session_route(session_id: UUID, payload: SessionPatchRequest) -> dict[str, dict[str, object]]:
    factory = create_session_factory()
    with factory.begin() as db:
        counting_session = db.get(CountingSession, session_id)
        if counting_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bereich nicht gefunden.")
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(counting_session, field, value)
        db.flush()
        return {"data": _session_data(counting_session)}


@app.post("/api/v1/sessions/{session_id}/counts/adjust")
def adjust_count_route(session_id: UUID, payload: CountAdjustRequest) -> dict[str, dict[str, int | str]]:
    factory = create_session_factory()
    try:
        with factory.begin() as db:
            result = adjust_count(
                db,
                session_id=session_id,
                requirement_id=payload.inventory_item_id,
                delta=payload.delta,
                mutation_id=payload.client_mutation_id,
            )
    except CountError as error:
        _count_error(error)
    return {"data": result}


@app.put("/api/v1/sessions/{session_id}/counts/{inventory_item_id}")
def set_count_route(
    session_id: UUID, inventory_item_id: UUID, payload: CountSetRequest
) -> dict[str, dict[str, int | str]]:
    factory = create_session_factory()
    try:
        with factory.begin() as db:
            result = set_count(
                db,
                session_id=session_id,
                requirement_id=inventory_item_id,
                quantity=payload.quantity,
                expected_revision=payload.expected_revision,
                mutation_id=payload.client_mutation_id,
            )
    except CountError as error:
        _count_error(error)
    return {"data": result}


@app.post("/api/v1/sessions/{session_id}/unlisted", status_code=status.HTTP_201_CREATED)
def create_unlisted_find_route(
    session_id: UUID, payload: UnlistedFindCreateRequest
) -> dict[str, dict[str, object]]:
    factory = create_session_factory()
    try:
        with factory.begin() as db:
            find = record_unlisted_find(db, session_id=session_id, **payload.model_dump())
            data = unlisted_find_data(find)
    except UnlistedFindError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return {"data": data}


def _session_data(session: CountingSession, counted_positions: int = 0) -> dict[str, object]:
    return {
        "id": str(session.id),
        "label": session.label,
        "position": session.position,
        "mandatory": session.mandatory,
        "status": session.status.value,
        "counted_positions": counted_positions,
    }


def _count_error(error: CountError) -> None:
    error_status = {
        "INVALID_NEGATIVE_QUANTITY": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "REVISION_CONFLICT": status.HTTP_409_CONFLICT,
        "SESSION_ARCHIVED": status.HTTP_409_CONFLICT,
    }.get(error.code, status.HTTP_422_UNPROCESSABLE_ENTITY)
    raise HTTPException(status_code=error_status, detail={"code": error.code, "message": str(error)})


def _csv_response(rows: list[dict[str, object]], fieldnames: list[str], filename: str) -> Response:
    content = StringIO(newline="")
    writer = csv.DictWriter(content, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content=content.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
