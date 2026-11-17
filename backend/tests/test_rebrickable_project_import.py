from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import (
    CountingSession,
    InventoryProvenance,
    InventoryRequirement,
    MinifigRequirement,
    Project,
    SessionInventoryAllocation,
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
        if path.endswith("/parts/?inc_minifig_parts=1"):
            return [{"part": {"part_num": "3001", "name": "Brick"}, "color": {"id": 5, "name": "Red"}, "quantity": 5, "is_spare": False}]
        if path.endswith("/minifigs/"):
            return [{"set_num": "fig-1", "set_name": "Figur", "quantity": 3}]
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
            "/75978-1/parts/?inc_minifig_parts=1": [
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
        assert importer.import_project(session, project) == (True, 1)
        assert client.calls == 3
        assert importer.import_project(session, project) == (False, 1)
        assert client.calls == 3

    with factory() as session:
        project = session.get(Project, project_set_id)
        assert project is not None
        requirement = session.scalar(
            select(InventoryRequirement).where(InventoryRequirement.snapshot_id == project.inventory_snapshot_id)
        )
        assert requirement is not None
        assert requirement.expected_qty == 5
        provenance = session.scalars(
            select(InventoryProvenance).where(InventoryProvenance.requirement_id == requirement.id)
        ).all()
        assert len(provenance) == 1
        assert session.scalars(
            select(MinifigRequirement).where(MinifigRequirement.snapshot_id == project.inventory_snapshot_id)
        ).all()


def test_75978_import_uses_parent_master_and_submodels_as_session_allocations() -> None:
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
        requirements = session.scalars(
            select(InventoryRequirement).where(InventoryRequirement.snapshot_id == project.inventory_snapshot_id)
        ).all()
        assert sorted(requirement.expected_qty for requirement in requirements) == [5, 10]
        sessions = session.scalars(
            select(CountingSession).where(CountingSession.project_id == project_id).order_by(CountingSession.position)
        ).all()
        assert [item.label for item in sessions] == ["Anleitung 1", "Anleitung 2", "Anleitung 3", "Anleitung 4"]
        assert all(item.inventory_allocation_enabled for item in sessions)
        allocations = session.scalars(
            select(SessionInventoryAllocation).where(SessionInventoryAllocation.session_id.in_([item.id for item in sessions]))
        ).all()
        assert sorted(item.expected_qty for item in allocations) == [1, 2, 3, 4]

    client = TestClient(app)
    sessions = client.get(f"/api/v1/projects/{project_id}/sessions").json()["data"]
    first_inventory = client.get(
        f"/api/v1/projects/{project_id}/inventory?session_id={sessions[0]['id']}"
    ).json()["data"]["items"]
    third_inventory = client.get(
        f"/api/v1/projects/{project_id}/inventory?session_id={sessions[2]['id']}"
    ).json()["data"]["items"]
    assert [(item["part_num"], item["expected_qty"] ) for item in first_inventory] == [("3001", 2)]
    assert [(item["part_num"], item["expected_qty"] ) for item in third_inventory] == [("3002", 4)]

    first_count = client.post(
        f"/api/v1/sessions/{sessions[0]['id']}/counts/adjust",
        json={"inventory_item_id": first_inventory[0]["id"], "delta": 2, "client_mutation_id": str(uuid4())},
    )
    second_inventory = client.get(
        f"/api/v1/projects/{project_id}/inventory?session_id={sessions[1]['id']}"
    ).json()["data"]["items"]
    second_count = client.post(
        f"/api/v1/sessions/{sessions[1]['id']}/counts/adjust",
        json={"inventory_item_id": second_inventory[0]["id"], "delta": 3, "client_mutation_id": str(uuid4())},
    )
    assert first_count.status_code == 200
    assert second_count.status_code == 200
    assert second_count.json()["data"]["global_quantity"] == 5
    assert second_count.json()["data"]["expected_quantity"] == 10
    summary = client.get(f"/api/v1/projects/{project_id}/summary").json()["data"]
    assert summary["counts_total"] == 5
    assert summary["provisional_gap_units"] == 10

    rejected = client.post(
        f"/api/v1/sessions/{sessions[0]['id']}/counts/adjust",
        json={"inventory_item_id": third_inventory[0]["id"], "delta": 1, "client_mutation_id": str(uuid4())},
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "INVENTORY_ITEM_NOT_ALLOCATED"

    backup = client.get(f"/api/v1/projects/{project_id}/exports/backup.json").json()
    assert backup["sessions"][0]["inventory_allocation_enabled"] is True
    assert len(backup["session_inventory_allocations"]) == 4
    restored = client.post("/api/v1/projects/import-backup", json=backup)
    assert restored.status_code == 201
    restored_id = restored.json()["data"]["id"]
    restored_sessions = client.get(f"/api/v1/projects/{restored_id}/sessions").json()["data"]
    assert [item["label"] for item in restored_sessions] == ["Anleitung 1", "Anleitung 2", "Anleitung 3", "Anleitung 4"]
    restored_first_inventory = client.get(
        f"/api/v1/projects/{restored_id}/inventory?session_id={restored_sessions[0]['id']}"
    ).json()["data"]["items"]
    assert [(item["part_num"], item["expected_qty"]) for item in restored_first_inventory] == [("3001", 2)]


def test_75978_import_rolls_back_when_one_instruction_submodel_is_incomplete() -> None:
    factory = create_session_factory()
    with factory.begin() as session:
        project = create_project(session, "75978-1", "Hogwarts fehlgeschlagen")
        project_id = project.id

    with pytest.raises(CsvImportError, match="Submodell ist unvollständig"):
        with factory.begin() as session:
            project = session.get(Project, project_id)
            assert project is not None
            RebrickableProjectImporter(InstructionRebrickableClient(fail_on="75978-1-s3")).import_project(session, project)

    with factory() as session:
        project = session.get(Project, project_id)
        assert project is not None
        assert project.inventory_snapshot_id is None
        assert not session.scalars(
            select(SessionInventoryAllocation)
            .join(CountingSession, SessionInventoryAllocation.session_id == CountingSession.id)
            .where(CountingSession.project_id == project_id)
        ).all()
