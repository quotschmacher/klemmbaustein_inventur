from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

CSV = """part_num,color_id,color_name,quantity,inventory_class,part_name,source_type,source_ref
3001,72,Light Bluish Gray,10,required,Brick 2 x 4,set_regular,test
"""


def test_session_list_exposes_counted_positions_for_dashboard() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects", json={"set_num": f"dashboard-{uuid4()}", "label": "Dashboard"}
    ).json()["data"]
    client.post(
        f"/api/v1/projects/{project['id']}/import/csv",
        files={"file": ("inventory.csv", CSV, "text/csv")},
    )
    session = client.get(f"/api/v1/projects/{project['id']}/sessions").json()["data"][0]
    item = client.get(f"/api/v1/projects/{project['id']}/inventory").json()["data"]["items"][0]
    client.post(
        f"/api/v1/sessions/{session['id']}/counts/adjust",
        json={"inventory_item_id": item["id"], "delta": 1, "client_mutation_id": str(uuid4())},
    )

    sessions = client.get(f"/api/v1/projects/{project['id']}/sessions").json()["data"]

    assert sessions[0]["counted_positions"] == 1
