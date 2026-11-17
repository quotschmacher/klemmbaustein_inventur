import csv
from io import StringIO
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import CountEvent
from app.db.session import create_session_factory
from app.main import app


CSV = """part_num,color_id,color_name,quantity,inventory_class,part_name,source_type,source_ref
3001,72,Light Bluish Gray,2,required,Brick 2 x 4,set_regular,test
3002,5,Red,4,required,Brick 2 x 3,set_regular,test
3001,72,Light Bluish Gray,1,spare,Brick 2 x 4,spare,test
"""


def _project_with_inventory(client: TestClient) -> str:
    project = client.post(
        "/api/v1/projects",
        json={
            "set_num": f"export-{uuid4()}",
            "label": "Export-Test",
            "session_labels": ["Bereich"],
        },
    ).json()["data"]
    response = client.post(
        f"/api/v1/projects/{project['id']}/import/csv",
        files={"file": ("inventory.csv", CSV, "text/csv")},
    )
    assert response.status_code == 201
    return project["id"]


def test_inventory_csv_export_includes_expected_and_global_counts() -> None:
    client = TestClient(app)
    project_id = _project_with_inventory(client)
    session = client.get(f"/api/v1/projects/{project_id}/sessions").json()["data"][0]
    inventory = client.get(f"/api/v1/projects/{project_id}/inventory").json()["data"]["items"]
    required = next(item for item in inventory if item["part_num"] == "3001" and item["inventory_class"] == "required")

    counted = client.post(
        f"/api/v1/sessions/{session['id']}/counts/adjust",
        json={"inventory_item_id": required["id"], "delta": 3, "client_mutation_id": str(uuid4())},
    )
    assert counted.status_code == 200

    response = client.get(f"/api/v1/projects/{project_id}/exports/inventory.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].endswith('inventory.csv"')
    rows = list(csv.DictReader(StringIO(response.text)))
    assert rows == [
        {
            "part_num": "3001",
            "part_name": "Brick 2 x 4",
            "color_id": "72",
            "color_name": "Light Bluish Gray",
            "inventory_class": "required",
            "expected_quantity": "2",
            "global_quantity": "3",
            "missing_quantity": "0",
            "surplus_quantity": "1",
        },
        {
            "part_num": "3001",
            "part_name": "Brick 2 x 4",
            "color_id": "72",
            "color_name": "Light Bluish Gray",
            "inventory_class": "spare",
            "expected_quantity": "1",
            "global_quantity": "0",
            "missing_quantity": "1",
            "surplus_quantity": "0",
        },
        {
            "part_num": "3002",
            "part_name": "Brick 2 x 3",
            "color_id": "5",
            "color_name": "Red",
            "inventory_class": "required",
            "expected_quantity": "4",
            "global_quantity": "0",
            "missing_quantity": "4",
            "surplus_quantity": "0",
        },
    ]


def test_differences_csv_export_contains_confirmed_missing_and_surplus() -> None:
    client = TestClient(app)
    project_id = _project_with_inventory(client)
    session = client.get(f"/api/v1/projects/{project_id}/sessions").json()["data"][0]
    inventory = client.get(f"/api/v1/projects/{project_id}/inventory").json()["data"]["items"]
    required = next(item for item in inventory if item["part_num"] == "3001" and item["inventory_class"] == "required")

    assert client.post(
        f"/api/v1/sessions/{session['id']}/counts/adjust",
        json={"inventory_item_id": required["id"], "delta": 3, "client_mutation_id": str(uuid4())},
    ).status_code == 200
    assert client.patch(f"/api/v1/sessions/{session['id']}", json={"status": "completed"}).status_code == 200

    response = client.get(f"/api/v1/projects/{project_id}/exports/differences.csv")

    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith('differences.csv"')
    rows = list(csv.DictReader(StringIO(response.text)))
    assert rows == [
        {
            "difference_type": "surplus",
            "part_num": "3001",
            "part_name": "Brick 2 x 4",
            "color_id": "72",
            "color_name": "Light Bluish Gray",
            "expected_quantity": "2",
            "global_quantity": "3",
            "difference_quantity": "1",
        },
        {
            "difference_type": "missing",
            "part_num": "3002",
            "part_name": "Brick 2 x 3",
            "color_id": "5",
            "color_name": "Red",
            "expected_quantity": "4",
            "global_quantity": "0",
            "difference_quantity": "4",
        },
    ]


def test_json_backup_restores_a_new_project_with_counts_events_and_replacements() -> None:
    client = TestClient(app)
    project_id = _project_with_inventory(client)
    session = client.get(f"/api/v1/projects/{project_id}/sessions").json()["data"][0]
    inventory = client.get(f"/api/v1/projects/{project_id}/inventory").json()["data"]["items"]
    required = next(item for item in inventory if item["part_num"] == "3001" and item["inventory_class"] == "required")
    missing = next(item for item in inventory if item["part_num"] == "3002")
    assert client.post(
        f"/api/v1/sessions/{session['id']}/counts/adjust",
        json={"inventory_item_id": required["id"], "delta": 3, "client_mutation_id": str(uuid4())},
    ).status_code == 200
    assert client.patch(f"/api/v1/sessions/{session['id']}", json={"status": "completed"}).status_code == 200
    replacement = client.post(
        f"/api/v1/projects/{project_id}/replacements",
        json={"requirement_id": missing["id"], "qty_ordered": 2, "target_session_id": session["id"]},
    )
    assert replacement.status_code == 201
    assert client.patch(
        f"/api/v1/projects/{project_id}/replacements/{replacement.json()['data']['id']}",
        json={"qty_received": 2, "status": "received"},
    ).status_code == 200

    backup_response = client.get(f"/api/v1/projects/{project_id}/exports/backup.json")

    assert backup_response.status_code == 200
    assert backup_response.headers["content-disposition"].endswith('backup.json"')
    backup = backup_response.json()
    assert backup["schema_version"] == 1
    assert backup["project"]["id"] == project_id
    assert len(backup["count_events"]) == 1
    assert backup["count_events"][0]["session_id"] == session["id"]
    assert len(backup["replacement_orders"]) == 1
    assert len(backup["replacement_items"]) == 1

    restore_response = client.post("/api/v1/projects/import-backup", json=backup)

    assert restore_response.status_code == 201
    restored_id = restore_response.json()["data"]["id"]
    assert restored_id != project_id
    assert restore_response.json()["data"]["restored_from_project_id"] == project_id
    restored_inventory = client.get(f"/api/v1/projects/{restored_id}/inventory").json()["data"]["items"]
    assert sorted(
        (item["part_num"], item["inventory_class"], item["expected_qty"], item["global_quantity"])
        for item in restored_inventory
    ) == [
        ("3001", "required", 2, 3),
        ("3001", "spare", 1, 0),
        ("3002", "required", 4, 0),
    ]
    restored_replacements = client.get(f"/api/v1/projects/{restored_id}/replacements").json()["data"]
    assert [(item["qty_ordered"], item["qty_received"], item["qty_booked"]) for item in restored_replacements] == [(2, 2, 0)]
    with create_session_factory()() as db:
        restored_events = db.scalars(select(CountEvent).where(CountEvent.project_id == restored_id)).all()
    assert len(restored_events) == 1
    assert restored_events[0].quantity_after == 3


def test_restore_rejects_unknown_backup_schema_without_creating_a_project() -> None:
    client = TestClient(app)
    before = client.get("/api/v1/projects?include_archived=true").json()["data"]

    response = client.post("/api/v1/projects/import-backup", json={"schema_version": 99})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_BACKUP_VERSION"
    after = client.get("/api/v1/projects?include_archived=true").json()["data"]
    assert [item["id"] for item in after] == [item["id"] for item in before]


def test_bricklink_export_refuses_unmapped_confirmed_missing_parts() -> None:
    client = TestClient(app)
    project_id = _project_with_inventory(client)
    session = client.get(f"/api/v1/projects/{project_id}/sessions").json()["data"][0]
    assert client.patch(f"/api/v1/sessions/{session['id']}", json={"status": "completed"}).status_code == 200

    response = client.get(f"/api/v1/projects/{project_id}/exports/wanted-list.xml")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "BRICKLINK_MAPPING_MISSING"
    assert detail["details"]["unmapped"] == [
        {
            "part_num": "3001",
            "color_id": 72,
            "missing_quantity": 2,
            "missing_part_mapping": True,
            "missing_color_mapping": True,
        },
        {
            "part_num": "3002",
            "color_id": 5,
            "missing_quantity": 4,
            "missing_part_mapping": True,
            "missing_color_mapping": True,
        },
    ]
