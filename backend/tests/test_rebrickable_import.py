from app.services.rebrickable_import import rebrickable_rows


def test_rebrickable_rows_keep_spares_separate() -> None:
    rows = rebrickable_rows(
        [
            {
                "part": {"part_num": "3001", "name": "Brick 2 x 4", "part_img_url": "https://img/3001"},
                "color": {"id": 72, "name": "Light Bluish Gray", "rgb": "A0A5A9"},
                "quantity": 10,
                "is_spare": False,
            },
            {
                "part": {"part_num": "3001", "name": "Brick 2 x 4", "part_img_url": "https://img/3001"},
                "color": {"id": 72, "name": "Light Bluish Gray", "rgb": "A0A5A9"},
                "quantity": 2,
                "is_spare": True,
            },
        ]
    )

    assert [(row.part_num, row.quantity, row.inventory_class.value) for row in rows] == [
        ("3001", 10, "required"),
        ("3001", 2, "spare"),
    ]
