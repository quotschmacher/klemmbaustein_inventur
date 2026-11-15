from pathlib import Path
import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_upgrade_head_creates_schema_and_critical_constraints() -> None:
    backend_root = Path(__file__).parents[1]
    config = Config(str(backend_root / "alembic.ini"))

    command.upgrade(config, "head")

    engine = create_engine(os.environ["DATABASE_URL"])
    inspector = inspect(engine)
    assert "count_events" in inspector.get_table_names()
    assert "replacement_items" in inspector.get_table_names()

    event_constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("count_events")}
    replacement_checks = {constraint["name"] for constraint in inspector.get_check_constraints("replacement_items")}

    assert "uq_count_event_project_mutation" in event_constraints
    assert "ck_replacement_item_booked_received" in replacement_checks
