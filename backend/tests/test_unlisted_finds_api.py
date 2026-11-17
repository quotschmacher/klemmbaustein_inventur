from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


CSV = """part_num,color_id,color_name,quantity,inventory_class,part_name,source_type,source_ref
3001,72,Light Bluish Gray,10,required,Brick 2 x 4,set_regular,test
"""


def test_unlisted_find_is_listed_without_changing_inventory_counts() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects",
        json={"set_num": f"unlisted-{uuid4()}", "label": "Fremdteile"},
    ).json()["data"]
    session = client.get(f"/api/v1/projects/{project['id']}/sessions").json()["data"][0]
    assert client.post(
        f"/api/v1/projects/{project['id']}/import/csv",
        files={"file": ("inventory.csv", CSV, "text/csv")},
    ).status_code == 201
    before = client.get(f"/api/v1/projects/{project['id']}/inventory").json()["data"]["items"]

    created = client.post(
        f"/api/v1/sessions/{session['id']}/unlisted",
        json={"part_num": "3068b", "color_ref": "Red", "label": "Unbekannter 2 x 2 Stein", "qty": 3},
    )
    listed = client.get(f"/api/v1/projects/{project['id']}/unlisted")
    after = client.get(f"/api/v1/projects/{project['id']}/inventory").json()["data"]["items"]

    assert created.status_code == 201
    assert created.json()["data"] == {
        "id": created.json()["data"]["id"],
        "session_id": session["id"],
        "part_num": "3068b",
        "color_ref": "Red",
        "label": "Unbekannter 2 x 2 Stein",
        "qty": 3,
        "resolution_status": "open",
    }
    assert listed.status_code == 200
    assert listed.json()["data"] == [created.json()["data"]]
    assert after == before


def test_unlisted_find_rejects_negative_quantity() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects",
        json={"set_num": f"unlisted-{uuid4()}", "label": "Negative Fremdteile"},
    ).json()["data"]
    session = client.get(f"/api/v1/projects/{project['id']}/sessions").json()["data"][0]

    response = client.post(
        f"/api/v1/sessions/{session['id']}/unlisted",
        json={"label": "Darf nicht negativ sein", "qty": -1},
    )

    assert response.status_code == 422
    assert client.get(f"/api/v1/projects/{project['id']}/unlisted").json()["data"] == []


def test_unlisted_finds_are_scoped_to_the_requested_project() -> None:
    client = TestClient(app)
    first_project = client.post(
        "/api/v1/projects",
        json={"set_num": f"unlisted-{uuid4()}", "label": "Erstes Projekt"},
    ).json()["data"]
    second_project = client.post(
        "/api/v1/projects",
        json={"set_num": f"unlisted-{uuid4()}", "label": "Zweites Projekt"},
    ).json()["data"]
    first_session = client.get(f"/api/v1/projects/{first_project['id']}/sessions").json()["data"][0]
    second_session = client.get(f"/api/v1/projects/{second_project['id']}/sessions").json()["data"][0]

    first_created = client.post(
        f"/api/v1/sessions/{first_session['id']}/unlisted",
        json={"label": "Nur erstes Projekt", "qty": 1},
    )
    second_created = client.post(
        f"/api/v1/sessions/{second_session['id']}/unlisted",
        json={"label": "Nur zweites Projekt", "qty": 2},
    )

    assert first_created.status_code == 201
    assert second_created.status_code == 201
    assert client.get(f"/api/v1/projects/{first_project['id']}/unlisted").json()["data"] == [
        first_created.json()["data"]
    ]
    assert client.get(f"/api/v1/projects/{second_project['id']}/unlisted").json()["data"] == [
        second_created.json()["data"]
    ]


def test_unlisted_find_rejects_an_unknown_session() -> None:
    response = TestClient(app).post(
        f"/api/v1/sessions/{uuid4()}/unlisted",
        json={"label": "Kein Bereich", "qty": 1},
    )

    assert response.status_code == 404
