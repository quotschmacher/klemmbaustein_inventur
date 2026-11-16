from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


CSV = """part_num,color_id,color_name,quantity,inventory_class,part_name,source_type,source_ref\n3001,72,Light Bluish Gray,10,required,Brick 2 x 4,set_regular,test\n3001,5,Red,4,required,Brick 2 x 4,set_regular,test\n3069b,72,Light Bluish Gray,3,required,Tile 1 x 2,set_regular,test\n3001,72,Light Bluish Gray,2,spare,Brick 2 x 4,spare,test\n"""


def test_csv_import_is_idempotent_and_keeps_spares_separate() -> None:
    client = TestClient(app)
    project_response = client.post(
        "/api/v1/projects",
        json={"set_num": f"synthetic-{uuid4()}", "label": "Synthetischer Import"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["data"]["id"]

    upload = {"file": ("synthetic_inventory.csv", CSV, "text/csv")}
    first_import = client.post(f"/api/v1/projects/{project_id}/import/csv", files=upload)
    second_import = client.post(f"/api/v1/projects/{project_id}/import/csv", files=upload)

    assert first_import.status_code == 201
    assert first_import.json()["data"] == {"requirements": 4, "imported": True}
    assert second_import.status_code == 200
    assert second_import.json()["data"] == {"requirements": 4, "imported": False}

    inventory = client.get(f"/api/v1/projects/{project_id}/inventory")
    assert inventory.status_code == 200
    assert inventory.json()["data"]["total"] == 4
    assert {item["inventory_class"] for item in inventory.json()["data"]["items"]} == {
        "required",
        "spare",
    }


def test_rebrickable_import_requires_a_server_side_key(monkeypatch) -> None:
    monkeypatch.delenv("REBRICKABLE_API_KEY", raising=False)
    client = TestClient(app)
    project_response = client.post(
        "/api/v1/projects",
        json={"set_num": f"synthetic-{uuid4()}", "label": "Ohne API-Schlüssel"},
    )

    response = client.post(
        f"/api/v1/projects/{project_response.json()['data']['id']}/import/rebrickable"
    )

    assert response.status_code == 503
