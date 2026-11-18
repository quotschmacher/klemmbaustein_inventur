from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

CSV = """part_num,color_id,color_name,quantity,inventory_class,part_name,source_type,source_ref
3001,72,Light Bluish Gray,10,required,Brick 2 x 4,set_regular,test
3001,72,Light Bluish Gray,2,spare,Brick 2 x 4,spare,test
"""


def _adjust(client: TestClient, session_id: str, item_id: str, delta: int) -> None:
    response = client.post(
        f"/api/v1/sessions/{session_id}/counts/adjust",
        json={"inventory_item_id": item_id, "delta": delta, "client_mutation_id": str(uuid4())},
    )
    assert response.status_code == 200


def test_summary_marks_gaps_as_provisional_until_required_sessions_complete() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects",
        json={"set_num": "75978", "label": "Summen-Test", "session_labels": ["Bereich A", "Bereich B"]},
    ).json()["data"]
    sessions = client.get(f"/api/v1/projects/{project['id']}/sessions").json()["data"]
    client.post(f"/api/v1/projects/{project['id']}/import/csv", files={"file": ("inventory.csv", CSV, "text/csv")})
    required_item = client.get(f"/api/v1/projects/{project['id']}/inventory").json()["data"]["items"][0]

    _adjust(client, sessions[0]["id"], required_item["id"], 4)
    _adjust(client, sessions[1]["id"], required_item["id"], 4)
    provisional = client.get(f"/api/v1/projects/{project['id']}/summary").json()["data"]

    assert provisional["all_required_complete"] is False
    assert provisional["provisional_gap_units"] == 2
    assert provisional["confirmed_missing_units"] == 0

    for session in sessions:
        assert client.patch(f"/api/v1/sessions/{session['id']}", json={"status": "completed"}).status_code == 200
    confirmed = client.get(f"/api/v1/projects/{project['id']}/summary").json()["data"]
    missing = client.get(f"/api/v1/projects/{project['id']}/differences?type=missing").json()["data"]

    assert confirmed["all_required_complete"] is True
    assert confirmed["provisional_gap_units"] == 0
    assert confirmed["confirmed_missing_units"] == 2
    assert missing["items"][0]["missing_quantity"] == 2

    assert client.patch(f"/api/v1/sessions/{sessions[0]['id']}", json={"status": "in_progress"}).status_code == 200
    reopened = client.get(f"/api/v1/projects/{project['id']}/summary").json()["data"]
    assert reopened["all_required_complete"] is False
    assert reopened["provisional_gap_units"] == 2
    assert reopened["confirmed_missing_units"] == 0


def test_surplus_is_immediately_visible_and_spares_do_not_affect_required_summary() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects", json={"set_num": "75978", "label": "Überschuss-Test"}
    ).json()["data"]
    sessions = client.get(f"/api/v1/projects/{project['id']}/sessions").json()["data"]
    client.post(f"/api/v1/projects/{project['id']}/import/csv", files={"file": ("inventory.csv", CSV, "text/csv")})
    required_item = client.get(f"/api/v1/projects/{project['id']}/inventory").json()["data"]["items"][0]

    surplus_adjustment = client.post(
        f"/api/v1/sessions/{sessions[0]['id']}/counts/adjust",
        json={"inventory_item_id": required_item["id"], "delta": 11, "client_mutation_id": str(uuid4())},
    )
    summary = client.get(f"/api/v1/projects/{project['id']}/summary").json()["data"]
    surplus = client.get(f"/api/v1/projects/{project['id']}/differences?type=surplus").json()["data"]

    assert summary["surplus_types"] == 1
    assert summary["provisional_gap_units"] == 0
    assert surplus["items"][0]["surplus_quantity"] == 1
    assert surplus_adjustment.json()["data"]["surplus_quantity"] == 1
