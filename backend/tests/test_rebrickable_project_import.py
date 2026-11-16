from uuid import uuid4

from sqlalchemy import select

from app.db.models import InventoryProvenance, InventoryRequirement, MinifigRequirement, Project
from app.db.session import create_session_factory
from app.services.inventory_import import create_project
from app.services.rebrickable_project_import import RebrickableProjectImporter


class FakeRebrickableClient:
    def fetch_object(self, path: str) -> dict[str, object]:
        assert "/api/v3/lego/sets/" in path
        return {"name": "Testset", "year": 2020}

    def fetch_all_pages(self, path: str) -> list[dict[str, object]]:
        if path.endswith("/parts/?inc_minifig_parts=0"):
            return [{"part": {"part_num": "3001", "name": "Brick"}, "color": {"id": 5, "name": "Red"}, "quantity": 2, "is_spare": False}]
        if path.endswith("/minifigs/"):
            return [{"set_num": "fig-1", "set_name": "Figur", "quantity": 3}]
        if path.endswith("/minifigs/fig-1/parts/"):
            return [{"part": {"part_num": "3001", "name": "Brick"}, "color": {"id": 5, "name": "Red"}, "quantity": 1, "is_spare": False}]
        raise AssertionError(path)


def test_rebrickable_import_aggregates_minifig_parts_with_provenance() -> None:
    factory = create_session_factory()
    with factory.begin() as session:
        project = create_project(session, f"test-set-{uuid4()}", "Rebrickable-Test")
        project_set_id = project.id

    with factory.begin() as session:
        project = session.get(Project, project_set_id)
        assert project is not None
        RebrickableProjectImporter(FakeRebrickableClient()).import_project(session, project)

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
        assert len(provenance) == 2
        assert session.scalars(
            select(MinifigRequirement).where(MinifigRequirement.snapshot_id == project.inventory_snapshot_id)
        ).all()
