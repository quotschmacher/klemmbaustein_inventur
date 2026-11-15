from collections.abc import Iterable

from app.db.models import InventoryClass
from app.services.inventory_import import CsvImportError, CsvRow


def rebrickable_rows(items: Iterable[dict[str, object]]) -> list[CsvRow]:
    rows: list[CsvRow] = []
    identities: set[tuple[str, int, InventoryClass]] = set()
    for item in items:
        try:
            part = item["part"]
            color = item["color"]
            if not isinstance(part, dict) or not isinstance(color, dict):
                raise TypeError
            part_num = str(part["part_num"])
            color_id = int(color["id"])
            quantity = int(item["quantity"])
            inventory_class = InventoryClass.SPARE if item.get("is_spare") else InventoryClass.REQUIRED
        except (KeyError, TypeError, ValueError) as error:
            raise CsvImportError("Rebrickable lieferte eine ungültige Teileposition.") from error
        if not part_num or color_id < 0 or quantity < 0:
            raise CsvImportError("Rebrickable lieferte eine ungültige Teileposition.")
        identity = (part_num, color_id, inventory_class)
        if identity in identities:
            raise CsvImportError("Rebrickable lieferte eine doppelte Teileposition.")
        identities.add(identity)
        rows.append(
            CsvRow(
                part_num=part_num,
                color_id=color_id,
                color_name=str(color.get("name") or f"Farbe {color_id}"),
                quantity=quantity,
                inventory_class=inventory_class,
                part_name=str(part.get("name") or part_num),
                image_url=str(part["part_img_url"]) if part.get("part_img_url") else None,
                source_type="set_regular" if inventory_class is InventoryClass.REQUIRED else "spare",
                source_ref="rebrickable",
            )
        )
    if not rows:
        raise CsvImportError("Rebrickable lieferte keine Teilepositionen.")
    return rows
