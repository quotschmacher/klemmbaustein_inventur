from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

CSV = """part_num,color_id,color_name,quantity,inventory_class,part_name,source_type,source_ref
3001,72,Light Bluish Gray,2,required,Brick 2 x 4,set_regular,test
"""


def test_confirmed_missing_part_can_be_ordered_received_and_booked_once() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects", json={"set_num": f"replacement-{uuid4()}", "label": "Ersatztest"}
    ).json()["data"]
    sessions = client.get(f"/api/v1/projects/{project['id']}/sessions").json()["data"]
    client.post(
        f"/api/v1/projects/{project['id']}/import/csv",
        files={"file": ("inventory.csv", CSV, "text/csv")},
    )
    for session in sessions:
        client.patch(f"/api/v1/sessions/{session['id']}", json={"status": "completed"})
    missing_item = client.get(f"/api/v1/projects/{project['id']}/differences?type=missing").json()["data"]["items"][0]

    created = client.post(
        f"/api/v1/projects/{project['id']}/replacements",
        json={"requirement_id": missing_item["id"], "qty_ordered": 2, "target_session_id": sessions[0]["id"]},
    )
    assert created.status_code == 201
    replacement = created.json()["data"]

    received = client.patch(
        f"/api/v1/projects/{project['id']}/replacements/{replacement['id']}",
        json={"qty_received": 2, "status": "received"},
    )
    assert received.status_code == 200

    client.patch(f"/api/v1/sessions/{sessions[0]['id']}", json={"status": "in_progress"})
    mutation_id = str(uuid4())
    booked = client.post(
        f"/api/v1/replacements/{replacement['id']}/book-into-session",
        json={"session_id": sessions[0]["id"], "quantity": 2, "client_mutation_id": mutation_id},
    )
    duplicate = client.post(
        f"/api/v1/replacements/{replacement['id']}/book-into-session",
        json={"session_id": sessions[0]["id"], "quantity": 2, "client_mutation_id": mutation_id},
    )

    assert booked.status_code == 200
    assert duplicate.status_code == 200
    assert booked.json()["data"]["global_quantity"] == 2
    replacements = client.get(f"/api/v1/projects/{project['id']}/replacements").json()["data"]
    assert replacements[0]["qty_booked"] == 2


def test_confirmed_missing_parts_are_created_as_one_combined_order() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects", json={"set_num": f"combined-{uuid4()}", "label": "Sammelbestellung"}
    ).json()["data"]
    sessions = client.get(f"/api/v1/projects/{project['id']}/sessions").json()["data"]
    client.post(
        f"/api/v1/projects/{project['id']}/import/csv",
        files={"file": ("inventory.csv", CSV.replace("\n", "\n3002,5,Red,1,required,Brick 2 x 3,set_regular,test\n", 1), "text/csv")},
    )
    for session in sessions:
        client.patch(f"/api/v1/sessions/{session['id']}", json={"status": "completed"})

    created = client.post(
        f"/api/v1/projects/{project['id']}/replacements/from-confirmed-missing",
        json={"target_session_id": sessions[0]["id"]},
    )

    assert created.status_code == 201
    assert created.json()["data"]["item_count"] == 2
    replacements = client.get(f"/api/v1/projects/{project['id']}/replacements").json()["data"]
    assert len(replacements) == 2
    assert len({item["order_id"] for item in replacements}) == 1
