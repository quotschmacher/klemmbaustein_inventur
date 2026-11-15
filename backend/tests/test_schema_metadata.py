from app.db.models import Base


def test_metadata_contains_the_inventory_schema_tables() -> None:
    expected_tables = {
        "sets",
        "projects",
        "inventory_snapshots",
        "colors",
        "part_catalog",
        "inventory_requirements",
        "inventory_provenance",
        "minifig_requirements",
        "sessions",
        "count_balances",
        "count_events",
        "unlisted_finds",
        "replacement_orders",
        "replacement_items",
        "project_events",
    }

    assert expected_tables <= set(Base.metadata.tables)


def test_persisted_enum_values_follow_the_api_contract() -> None:
    inventory_class = Base.metadata.tables["inventory_requirements"].c.inventory_class.type
    session_status = Base.metadata.tables["sessions"].c.status.type

    assert inventory_class.enums == ["required", "spare"]
    assert session_status.enums == ["in_progress", "completed", "archived"]
