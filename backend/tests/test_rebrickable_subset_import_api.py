import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services.rebrickable_subset_import import parse_rebrickable_subset_snapshot


CSV = """part_num,color_id,color_name,quantity,inventory_class,part_name,source_type,source_ref
3001,5,Red,5,required,Brick 2 x 4,set_regular,test
3002,1,Blue,5,required,Plate 2 x 3,set_regular,test
"""


def _snapshot(inventory_id: int, part_num: str, color_id: int, color_name: str, quantity: int) -> str:
    return json.dumps(
        {
            "status": "success",
            "msg": "",
            "html": f'''<a href="/inventory/{inventory_id}/parts/?format=rbpartscsv">Export</a>
            <p>There are <b>1</b> parts in this inventory, with <b>{quantity}</b> total quantity.</p>
            <div class="js-part"><a href="/parts/{part_num}/example/"><div class="js-part-data"
            data-part_name="Testteil" data-color_id="{color_id}" data-color_name="{color_name}"
            data-color_hsv="#000000 112233" data-quantity="{quantity}" data-is_spare="0">
            <img data-src="https://cdn.rebrickable.com/media/thumbs/parts/test.png"></div></a></div>''',
        }
    )


def test_snapshot_parser_keeps_display_metadata() -> None:
    parsed = parse_rebrickable_subset_snapshot(_snapshot(123456, "3001", 5, "Red", 7).encode())

    assert parsed.positions[0].part_name == "Testteil"
    assert parsed.positions[0].color_name == "Red"
    assert parsed.positions[0].color_rgb == "112233"
    assert parsed.positions[0].image_url == "https://cdn.rebrickable.com/media/thumbs/parts/test.png"


def test_rebrickable_subset_snapshots_allocate_the_four_instruction_sessions() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects",
        json={"set_num": "75978", "label": f"Subset-Test {uuid4()}"},
    ).json()["data"]
    project_id = project["id"]
    imported = client.post(
        f"/api/v1/projects/{project_id}/import/csv",
        files={"file": ("inventory.csv", CSV, "text/csv")},
    )
    assert imported.status_code in {200, 201}

    response = client.post(
        f"/api/v1/projects/{project_id}/import/rebrickable-subsets",
        files=[
            ("files", ("anleitung-1.json", _snapshot(196286, "3001", 5, "Red", 2), "application/json")),
            ("files", ("anleitung-2.json", _snapshot(196302, "3001", 5, "Red", 3), "application/json")),
            ("files", ("anleitung-3.json", _snapshot(196309, "3002", 1, "Blue", 4), "application/json")),
            ("files", ("anleitung-4.json", _snapshot(196315, "3002", 1, "Blue", 1), "application/json")),
        ],
    )

    assert response.status_code == 201
    assert response.json()["data"] == {"sessions": 4, "positions": 4, "quantity": 10}

    sessions = client.get(f"/api/v1/projects/{project_id}/sessions").json()["data"]
    assert [session["label"] for session in sessions] == [
        "Anleitung 1", "Anleitung 2", "Anleitung 3", "Anleitung 4", "Figuren"
    ]
    first_inventory = client.get(
        f"/api/v1/projects/{project_id}/inventory?session_id={sessions[0]['id']}"
    ).json()["data"]["items"]
    assert [(item["part_num"], item["expected_qty"]) for item in first_inventory] == [("3001", 2)]
    figures_inventory = client.get(
        f"/api/v1/projects/{project_id}/inventory?session_id={sessions[4]['id']}"
    ).json()["data"]["items"]
    assert figures_inventory == []


def test_empty_project_can_use_a_json_snapshot_as_its_inventory() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects",
        json={"set_num": f"json-{uuid4()}", "label": "JSON-Projekt"},
    ).json()["data"]

    response = client.post(
        f"/api/v1/projects/{project['id']}/import/rebrickable-json",
        files={"files": ("inventar.json", _snapshot(123456, "3001", 5, "Red", 7), "application/json")},
    )

    assert response.status_code == 201
    assert response.json()["data"] == {"requirements": 1, "imported": True}
    inventory = client.get(f"/api/v1/projects/{project['id']}/inventory").json()["data"]["items"]
    assert [(item["part_num"], item["expected_qty"]) for item in inventory] == [("3001", 7)]


def test_empty_project_can_append_a_second_json_snapshot_before_counting() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects",
        json={"set_num": f"json-{uuid4()}", "label": "Mehrteilige JSON-Inventur"},
    ).json()["data"]
    for inventory_id, part_num, color_id, color_name, quantity in [
        (123456, "3001", 5, "Red", 7),
        (123457, "3002", 1, "Blue", 3),
    ]:
        response = client.post(
            f"/api/v1/projects/{project['id']}/import/rebrickable-json",
            files={"files": ("inventar.json", _snapshot(inventory_id, part_num, color_id, color_name, quantity), "application/json")},
        )
        assert response.status_code == 201

    inventory = client.get(f"/api/v1/projects/{project['id']}/inventory").json()["data"]["items"]
    assert [(item["part_num"], item["expected_qty"]) for item in inventory] == [("3002", 3), ("3001", 7)]
    sessions = client.get(f"/api/v1/projects/{project['id']}/sessions").json()["data"]
    assert [item["label"] for item in sessions] == ["Snapshot 123456", "Snapshot 123457"]
    first = client.get(f"/api/v1/projects/{project['id']}/inventory?session_id={sessions[0]['id']}").json()["data"]["items"]
    second = client.get(f"/api/v1/projects/{project['id']}/inventory?session_id={sessions[1]['id']}").json()["data"]["items"]
    assert [(item["part_num"], item["expected_qty"]) for item in first] == [("3001", 7)]
    assert [(item["part_num"], item["expected_qty"]) for item in second] == [("3002", 3)]
