from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_the_api_is_available() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}}
