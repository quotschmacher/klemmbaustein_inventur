from app.services.rebrickable_import import rebrickable_rows


def test_rebrickable_rows_add_minifig_components_once() -> None:
    rows = rebrickable_rows(
        [],
        [
            {
                "part": {"part_num": "x1", "name": "Minifig accessory"},
                "color": {"id": 5, "name": "Red"},
                "quantity": 2,
                "is_spare": False,
            }
        ],
        minifig_quantity=3,
        fig_ref="fig-1",
    )

    assert [(row.part_num, row.quantity, row.source_type, row.source_ref) for row in rows] == [
        ("x1", 6, "minifig_component", "fig-1")
    ]
