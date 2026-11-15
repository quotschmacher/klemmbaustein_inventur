import asyncio
import os
from uuid import UUID

from fastapi import FastAPI, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from psycopg import connect
from psycopg.errors import OperationalError

from app.db.models import Project
from app.db.session import create_session_factory
from app.services.inventory_import import CsvImportError, create_project, import_csv_inventory

app = FastAPI(title="LEGO Inventur API", version="0.1.0")


class ProjectCreateRequest(BaseModel):
    set_num: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=500)


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
        project = create_project(session, payload.set_num, payload.label)
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
