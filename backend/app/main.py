import asyncio
import os

from fastapi import FastAPI, HTTPException, status
from psycopg import connect
from psycopg.errors import OperationalError

app = FastAPI(title="LEGO Inventur API", version="0.1.0")


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
