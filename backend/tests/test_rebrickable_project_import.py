from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import (
    CountingSession,
    InventoryProvenance,
    InventoryRequirement,
    MinifigRequirement,
    Project,
)
from app.db.session import create_session_factory
from app.services.inventory_import import create_project
from app.services.rebrickable_project_import import RebrickableProjectImporter
from app.services.inventory_import import CsvImportError
from app.main import app


class FakeRebrickableClient:
    def __init__(self) -> None:
        self.calls = 0

    def fetch_object(self, path: str) -> dict[str, object]:
        self.calls += 1
        assert "/api/v3/lego/sets/" in path
        return {"name": "Testset", "year": 2020}

    def fetch_all_pages(self, path: str) -> list[dict[str, object]]:
        self.calls += 1
        if path.endswith("/parts/?inc_minifig_parts=0"):
            return [{"part": {"part_num": "3001", "name": "Brick"}, "color": {"id": 5, "name": "Red"}, "quantity": 5, "is_spare": False}]
        if path.endswith("/minifigs/"):
            return [{"set_num": "fig-1", "set_name": "Figur", "quantity": 3}]
        if path.endswith("/minifigs/fig-1/parts/"):
            return [{"part": {"part_num": "3002", "name": "Plate"}, "color": {"id": 1, "name": "Blue"}, "quantity": 2, "is_spare": False}]
        raise AssertionError(path)


class InstructionRebrickableClient:
    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on

    def fetch_object(self, path: str) -> dict[str, object]:
        assert path.endswith("/75978-1/")
        return {"name": "75978", "year": 2020}

    def fetch_all_pages(self, path: str) -> list[dict[str, object]]:
        if self.fail_on and self.fail_on in path:
            raise CsvImportError("Submodell ist unvollständig.")
        parts = {
            "/75978-1/parts/?inc_minifig_parts=0": [
                {"part": {"part_num": "3001", "name": "Brick"}, "color": {"id": 5, "name": "Red"}, "quantity": 10, "is_spare": False},
                {"part": {"part_num": "3002", "name": "Plate"}, "color": {"id": 1, "name": "Blue"}, "quantity": 5, "is_spare": False},
            ],
            "/75978-1-s1/parts/?inc_minifig_parts=1": [
                {"part": {"part_num": "3001", "name": "Brick"}, "color": {"id": 5, "name": "Red"}, "quantity": 2, "is_spare": False}
            ],
            "/75978-1-s2/parts/?inc_minifig_parts=1": [
                {"part": {"part_num": "3001", "name": "Brick"}, "color": {"id": 5, "name": "Red"}, "quantity": 3, "is_spare": False}
            ],
            "/75978-1-s3/parts/?inc_minifig_parts=1": [
                {"part": {"part_num": "3002", "name": "Plate"}, "color": {"id": 1, "name": "Blue"}, "quantity": 4, "is_spare": False}
            ],
            "/75978-1-s4/parts/?inc_minifig_parts=1": [
                {"part": {"part_num": "3002", "name": "Plate"}, "color": {"id": 1, "name": "Blue"}, "quantity": 1, "is_spare": False}
            ],
        }
        if path.endswith("/minifigs/"):
            return []
        try:
            return parts[next(key for key in parts if key in path)]
        except StopIteration as error:
            raise AssertionError(path) from error


def test_rebrickable_import_aggregates_minifig_parts_with_provenance() -> None:
    factory = create_session_factory()
    with factory.begin() as session:
        project = create_project(session, f"test-set-{uuid4()}", "Rebrickable-Test")
        project_set_id = project.id

    with factory.begin() as session:
        project = session.get(Project, project_set_id)
        assert project is not None
        client = FakeRebrickableClient()
        importer = RebrickableProjectImporter(client)
        assert importer.import_project(session, project) == (True, 2)
        assert client.calls == 4
        assert importer.import_project(session, project) == (False, 2)
        assert client.calls == 4

    with factory() as session:
        project = session.get(Project, project_set_id)
        assert project is not None
        requirements = session.scalars(
            select(InventoryRequirement).where(InventoryRequirement.snapshot_id == project.inventory_snapshot_id)
        ).all()
        assert sorted(item.expected_qty for item in requirements) == [5, 6]
        requirement = requirements[0]
        provenance = session.scalars(
            select(InventoryProvenance).where(InventoryProvenance.requirement_id == requirement.id)
        ).all()
        assert len(provenance) == 1
        assert session.scalars(
            select(MinifigRequirement).where(MinifigRequirement.snapshot_id == project.inventory_snapshot_id)
        ).all()


def test_75978_import_uses_parent_inventory_without_nonexistent_submodel_parts() -> None:
    factory = create_session_factory()
    with factory.begin() as session:
        project = create_project(session, "75978-1", "Hogwarts")
        project_id = project.id

    with factory.begin() as session:
        project = session.get(Project, project_id)
        assert project is not None
        _, requirement_count = RebrickableProjectImporter(InstructionRebrickableClient()).import_project(session, project)
        assert requirement_count == 2

    with factory() as session:
        project = session.get(Project, project_id)
        assert project is not None
        sessions = session.scalars(
            select(CountingSession).where(CountingSession.project_id == project_id).order_by(CountingSession.position)
        ).all()
        assert [item.label for item in sessions] == ["Anleitung 1", "Anleitung 2", "Anleitung 3", "Anleitung 4", "Figuren"]
        assert not any(item.inventory_allocation_enabled for item in sessions)

    client = TestClient(app)
    sessions = client.get(f"/api/v1/projects/{project_id}/sessions").json()["data"]
    first_inventory = client.get(
        f"/api/v1/projects/{project_id}/inventory?session_id={sessions[0]['id']}"
    ).json()["data"]["items"]
    assert sorted(item["part_num"] for item in first_inventory) == ["3001", "3002"]
