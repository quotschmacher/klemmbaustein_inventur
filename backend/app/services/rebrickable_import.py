from collections.abc import Iterable

from app.db.models import InventoryClass
from app.services.inventory_import import CsvImportError, CsvRow


def rebrickable_rows(
    items: Iterable[dict[str, object]],
    minifig_items: Iterable[dict[str, object]] = (),
    *,
    minifig_quantity: int = 1,
    fig_ref: str | None = None,
) -> list[CsvRow]:
    aggregated: dict[tuple[str, int, InventoryClass], dict[str, object]] = {}
    for item, source_type, source_ref, multiplier in [
        *((item, "set_regular", "rebrickable", 1) for item in items),
        *((item, "minifig_component", fig_ref or "minifig", minifig_quantity) for item in minifig_items),
    ]:
        try:
            part = item["part"]
            color = item["color"]
            if not isinstance(part, dict) or not isinstance(color, dict):
                raise TypeError
            part_num = str(part["part_num"])
            color_id = int(color["id"])
            quantity = int(item["quantity"]) * multiplier
            inventory_class = InventoryClass.SPARE if item.get("is_spare") else InventoryClass.REQUIRED
        except (KeyError, TypeError, ValueError) as error:
            raise CsvImportError("Rebrickable lieferte eine ungültige Teileposition.") from error
        if not part_num or color_id < 0 or quantity < 0:
            raise CsvImportError("Rebrickable lieferte eine ungültige Teileposition.")
        key = (part_num, color_id, inventory_class)
        if key not in aggregated:
            aggregated[key] = {
                "color_name": str(color.get("name") or f"Farbe {color_id}"),
                "part_name": str(part.get("name") or part_num),
                "image_url": str(part["part_img_url"]) if part.get("part_img_url") else None,
                "quantity": 0,
                "provenance": [],
            }
        data = aggregated[key]
        data["quantity"] = int(data["quantity"]) + quantity
        provenance = data["provenance"]
        assert isinstance(provenance, list)
        provenance.append(("spare" if inventory_class is InventoryClass.SPARE else source_type, source_ref, quantity))

    if not aggregated:
        raise CsvImportError("Rebrickable lieferte keine Teilepositionen.")
    return [
        CsvRow(
            part_num=part_num,
            color_id=color_id,
            color_name=str(data["color_name"]),
            quantity=int(data["quantity"]),
            inventory_class=inventory_class,
            part_name=str(data["part_name"]),
            image_url=data["image_url"] if isinstance(data["image_url"], str) else None,
            source_type=data["provenance"][0][0],
            source_ref=data["provenance"][0][1],
            provenance=tuple(data["provenance"]),
        )
        for (part_num, color_id, inventory_class), data in aggregated.items()
    ]
