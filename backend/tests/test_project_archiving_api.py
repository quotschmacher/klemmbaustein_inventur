from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_archived_projects_are_hidden_by_default_and_can_be_listed() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects", json={"set_num": f"archive-{uuid4()}", "label": "Testprojekt"}
    ).json()["data"]

    archived = client.patch(f"/api/v1/projects/{project['id']}", json={"archived": True})
    default_projects = client.get("/api/v1/projects").json()["data"]
    all_projects = client.get("/api/v1/projects?include_archived=true").json()["data"]

    assert archived.status_code == 200
    assert project["id"] not in {item["id"] for item in default_projects}
    assert next(item for item in all_projects if item["id"] == project["id"])["archived"] is True
