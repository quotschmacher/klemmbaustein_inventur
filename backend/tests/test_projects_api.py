from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_projects_can_be_listed_for_later_continuation() -> None:
    client = TestClient(app)
    created = client.post(
        "/api/v1/projects", json={"set_num": f"resume-{uuid4()}", "label": "Fortsetzen"}
    ).json()["data"]

    response = client.get("/api/v1/projects")

    assert response.status_code == 200
    project = next(item for item in response.json()["data"] if item["id"] == created["id"])
    assert project["label"] == "Fortsetzen"
