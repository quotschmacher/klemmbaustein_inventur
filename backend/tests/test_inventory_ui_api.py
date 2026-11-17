from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

CSV = """part_num,color_id,color_name,color_rgb,quantity,inventory_class,part_name,source_type,source_ref
3001,72,Light Bluish Gray,9BA19D,10,required,Brick 2 x 4,set_regular,test
3001,5,Red,C91A09,4,required,Brick 2 x 4,set_regular,test
"""


def test_inventory_filters_to_exact_color_and_includes_selected_session_count() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects", json={"set_num": f"ui-{uuid4()}", "label": "UI-Filter"}
    ).json()["data"]
    session = client.get(f"/api/v1/projects/{project['id']}/sessions").json()["data"][0]
    client.post(
        f"/api/v1/projects/{project['id']}/import/csv",
        files={"file": ("inventory.csv", CSV, "text/csv")},
    )
    all_items = client.get(f"/api/v1/projects/{project['id']}/inventory").json()["data"]["items"]
    gray_item = next(item for item in all_items if item["color_id"] == 72)
    client.post(
        f"/api/v1/sessions/{session['id']}/counts/adjust",
        json={"inventory_item_id": gray_item["id"], "delta": 3, "client_mutation_id": str(uuid4())},
    )

    filtered = client.get(
        f"/api/v1/projects/{project['id']}/inventory?session_id={session['id']}&color_id=72"
    ).json()["data"]

    assert filtered["total"] == 1
    assert filtered["items"][0]["color_id"] == 72
    assert filtered["items"][0]["color_rgb"] == "9BA19D"
    assert filtered["items"][0]["session_quantity"] == 3
    assert filtered["items"][0]["global_quantity"] == 3


def test_inventory_exposes_imported_part_image_url() -> None:
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects", json={"set_num": f"image-{uuid4()}", "label": "Bild"}
    ).json()["data"]
    csv_with_image = CSV.replace(
        "source_ref\n", "source_ref,image_url\n"
    ).replace(
        "set_regular,test\n", "set_regular,test,https://cdn.rebrickable.com/media/parts/elements/example.jpg\n"
    )
    client.post(
        f"/api/v1/projects/{project['id']}/import/csv",
        files={"file": ("inventory.csv", csv_with_image, "text/csv")},
    )

    inventory = client.get(f"/api/v1/projects/{project['id']}/inventory").json()["data"]["items"]

    assert inventory[0]["image_url"] == "https://cdn.rebrickable.com/media/parts/elements/example.jpg"
