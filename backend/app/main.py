import asyncio
import os
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile, status
import httpx
from pydantic import BaseModel, Field
from psycopg import connect
from psycopg.errors import OperationalError
from sqlalchemy import select

from app.db.models import Color, CountingSession, InventoryRequirement, PartCatalog, Project, SessionStatus
from app.db.session import create_session_factory
from app.services.counting import CountError, adjust_count, set_count
from app.services.inventory_import import CsvImportError, create_project, import_csv_inventory
from app.services.rebrickable import RebrickableClient, RebrickableImportError
from app.services.rebrickable_project_import import RebrickableProjectImporter
from app.services.reconciliation import ReconciliationError, difference_items, project_reconciliation

app = FastAPI(title="LEGO Inventur API", version="0.1.0")


class ProjectCreateRequest(BaseModel):
    set_num: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=500)
    session_labels: list[str] | None = Field(default=None, max_length=20)


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


@app.get("/api/v1/projects/{project_id}/inventory")
def inventory_route(project_id: UUID) -> dict[str, dict[str, object]]:
    factory = create_session_factory()
    with factory() as session:
        project = session.get(Project, project_id)
        if project is None or project.inventory_snapshot_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventar nicht gefunden.")
        rows = session.execute(
            select(InventoryRequirement, PartCatalog, Color)
            .join(PartCatalog, InventoryRequirement.part_id == PartCatalog.id)
            .join(Color, InventoryRequirement.color_id == Color.id)
            .where(InventoryRequirement.snapshot_id == project.inventory_snapshot_id)
            .order_by(PartCatalog.part_num, Color.provider_color_id)
        ).all()
    items = [
        {
            "id": str(requirement.id),
            "part_num": part.part_num,
            "part_name": part.name,
            "color_id": color.provider_color_id,
            "color_name": color.name,
            "expected_qty": requirement.expected_qty,
            "inventory_class": requirement.inventory_class.value,
        }
        for requirement, part, color in rows
    ]
    return {"data": {"total": len(items), "items": items}}


@app.get("/api/v1/projects/{project_id}/sessions")
def list_sessions_route(project_id: UUID) -> dict[str, list[dict[str, object]]]:
    factory = create_session_factory()
    with factory() as db:
        sessions = db.scalars(
            select(CountingSession)
            .where(CountingSession.project_id == project_id)
            .order_by(CountingSession.position)
        ).all()
    return {"data": [_session_data(item) for item in sessions]}


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


def _session_data(session: CountingSession) -> dict[str, object]:
    return {
        "id": str(session.id),
        "label": session.label,
        "position": session.position,
        "mandatory": session.mandatory,
        "status": session.status.value,
    }


def _count_error(error: CountError) -> None:
    error_status = {
        "INVALID_NEGATIVE_QUANTITY": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "REVISION_CONFLICT": status.HTTP_409_CONFLICT,
        "SESSION_ARCHIVED": status.HTTP_409_CONFLICT,
    }.get(error.code, status.HTTP_422_UNPROCESSABLE_ENTITY)
    raise HTTPException(status_code=error_status, detail={"code": error.code, "message": str(error)})
