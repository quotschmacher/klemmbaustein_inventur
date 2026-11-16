import pytest

from app.services.rebrickable_project_import import canonical_set_num


@pytest.mark.parametrize(
    ("entered", "expected"),
    [
        ("75978", "75978-1"),
        ("75978-1", "75978-1"),
        (" 75978 ", "75978-1"),
    ],
)
def test_canonical_set_num_accepts_box_number_and_rebrickable_number(entered: str, expected: str) -> None:
    assert canonical_set_num(entered) == expected
