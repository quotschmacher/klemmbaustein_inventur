from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app

CSV = """part_num,color_id,color_name,quantity,inventory_class,part_name,source_type,source_ref
3001,72,Light Bluish Gray,10,required,Brick 2 x 4,set_regular,test
"""


def test_default_sessions_and_count_mutations_are_idempotent() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects",
        json={"set_num": f"count-{uuid4()}", "label": "Zähltest"},
    ).json()["data"]
    sessions = client.get(f"/api/v1/projects/{project['id']}/sessions")
    assert [item["label"] for item in sessions.json()["data"]] == [
        "Anleitung 1", "Anleitung 2", "Anleitung 3", "Anleitung 4", "Minifiguren"
    ]

    client.post(
        f"/api/v1/projects/{project['id']}/import/csv",
        files={"file": ("inventory.csv", CSV, "text/csv")},
    )
    item = client.get(f"/api/v1/projects/{project['id']}/inventory").json()["data"]["items"][0]
    session_id = sessions.json()["data"][0]["id"]
    mutation_id = str(uuid4())

    first = client.post(
        f"/api/v1/sessions/{session_id}/counts/adjust",
        json={"inventory_item_id": item["id"], "delta": 1, "client_mutation_id": mutation_id},
    )
    duplicate = client.post(
        f"/api/v1/sessions/{session_id}/counts/adjust",
        json={"inventory_item_id": item["id"], "delta": 1, "client_mutation_id": mutation_id},
    )

    assert first.status_code == 200
    assert first.json()["data"]["session_quantity"] == 1
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["session_quantity"] == 1


def test_count_cannot_become_negative_and_absolute_update_checks_revision() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects",
        json={"set_num": f"count-{uuid4()}", "label": "Korrekturtest"},
    ).json()["data"]
    sessions = client.get(f"/api/v1/projects/{project['id']}/sessions").json()["data"]
    client.post(f"/api/v1/projects/{project['id']}/import/csv", files={"file": ("inventory.csv", CSV, "text/csv")})
    item = client.get(f"/api/v1/projects/{project['id']}/inventory").json()["data"]["items"][0]
    session_id = sessions[0]["id"]

    negative = client.post(
        f"/api/v1/sessions/{session_id}/counts/adjust",
        json={"inventory_item_id": item["id"], "delta": -1, "client_mutation_id": str(uuid4())},
    )
    set_count = client.put(
        f"/api/v1/sessions/{session_id}/counts/{item['id']}",
        json={"quantity": 5, "expected_revision": 0, "client_mutation_id": str(uuid4())},
    )
    stale = client.put(
        f"/api/v1/sessions/{session_id}/counts/{item['id']}",
        json={"quantity": 3, "expected_revision": 0, "client_mutation_id": str(uuid4())},
    )

    assert negative.status_code == 422
    assert set_count.status_code == 200
    assert set_count.json()["data"]["session_quantity"] == 5
    assert stale.status_code == 409


def test_parallel_increment_requests_do_not_lose_updates() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects",
        json={"set_num": f"count-{uuid4()}", "label": "Paralleltest"},
    ).json()["data"]
    sessions = client.get(f"/api/v1/projects/{project['id']}/sessions").json()["data"]
    client.post(f"/api/v1/projects/{project['id']}/import/csv", files={"file": ("inventory.csv", CSV, "text/csv")})
    item = client.get(f"/api/v1/projects/{project['id']}/inventory").json()["data"]["items"][0]

    def increment() -> int:
        response = TestClient(app).post(
            f"/api/v1/sessions/{sessions[0]['id']}/counts/adjust",
            json={"inventory_item_id": item["id"], "delta": 1, "client_mutation_id": str(uuid4())},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(lambda _: increment(), range(2))) == [200, 200]

    result = client.post(
        f"/api/v1/sessions/{sessions[0]['id']}/counts/adjust",
        json={"inventory_item_id": item["id"], "delta": 0, "client_mutation_id": str(uuid4())},
    )
    assert result.json()["data"]["session_quantity"] == 2


def test_completed_session_rejects_further_counts() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects",
        json={"set_num": f"count-{uuid4()}", "label": "Abschlusstest"},
    ).json()["data"]
    session_id = client.get(f"/api/v1/projects/{project['id']}/sessions").json()["data"][0]["id"]
    client.post(f"/api/v1/projects/{project['id']}/import/csv", files={"file": ("inventory.csv", CSV, "text/csv")})
    item = client.get(f"/api/v1/projects/{project['id']}/inventory").json()["data"]["items"][0]
    assert client.patch(f"/api/v1/sessions/{session_id}", json={"status": "completed"}).status_code == 200

    response = client.post(
        f"/api/v1/sessions/{session_id}/counts/adjust",
        json={"inventory_item_id": item["id"], "delta": 1, "client_mutation_id": str(uuid4())},
    )
    assert response.status_code == 409
