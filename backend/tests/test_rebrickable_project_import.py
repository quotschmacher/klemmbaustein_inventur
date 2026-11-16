from uuid import uuid4

from sqlalchemy import select

from app.db.models import InventoryProvenance, InventoryRequirement, MinifigRequirement, Project
from app.db.session import create_session_factory
from app.services.inventory_import import create_project
from app.services.rebrickable_project_import import RebrickableProjectImporter


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
