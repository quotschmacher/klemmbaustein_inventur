# Import- und Exportquellen

## Rebrickable

Dokumentation: https://rebrickable.com/api/v3/docs/ . **Keine API-Keys in Browser-URLs oder Git.** Import serverseitig.

- Set-Details: `/api/v3/lego/sets/{set_num}/`.
- Normale Teile: `/api/v3/lego/sets/{set_num}/parts/` mit `inc_minifig_parts=0`; vollständige `next` Pagination, `is_spare` berücksichtigen.
- Figuren: `/api/v3/lego/sets/{set_num}/minifigs/` und für jede Figur `/api/v3/lego/minifigs/{set_num}/parts/`; Figurenzahl multiplizieren.
- Die `inc_minifig_parts=1` Variante ist **eine Alternative** zur separaten Expansion, nicht zusätzlich dazu.
- `part.part_num`, `part.name`, `part.part_img_url`, `color.id`, `color.name`, `color.rgb`, `quantity`, `is_spare` als relevante Felder; Validierung gemäß API-Antwort.
- Rate Limits, Terms und mögliche Änderungen beachten. **CSV-Import** vorsehen, falls kein API-Key oder API temporär überlastet. Herkunft/Datum/Snapshotversion speichern.
- IDs für Rebrickable und BrickLink sind nicht identisch; echte Crosswalk-Mappings nötig.

## CSV-Import (eigene interne Vorlage)

Pflichtfelder: `part_num,color_id,color_name,quantity,inventory_class` (`required`/`spare`), optionale Felder `part_name,image_url,source_type,source_ref,bricklink_part_id,bricklink_color_id`. UTF-8, quoted CSV, validierte Ganzzahlen >=0, Duplicate-Handling mit Diagnose (nicht blind „last wins“). Für echte Minifig-Expansion bei CSV Quellenhinweis; bei gelieferten bereits expandierten Mengen **nicht nochmal** aus Figurenliste expandieren.

## BrickLink Wanted List

Erst nach verifiziertem Mapping. XML `INVENTORY > ITEM` mit `ITEMTYPE=P`, `ITEMID` (BrickLink-ID), `COLOR` (BrickLink-Farb-ID), `MINQTY` (bestätigte Fehlmenge), optional `CONDITION=N`, `REMARKS`. Fehlende Mappings als eigene CSV/Liste, **nie** falsche Teilnummern ausgeben. Dokumentation: https://www.bricklink.com/help.asp?helpID=2567

## Import-Sicherheit

Fremddaten nie als ausführbares HTML rendern; Bild-URLs nur von erlaubten Quellen oder sicherer Proxy; Requests begrenzen; ZIP-/CSV-Grenzen; Server nicht als freier URL-Fetcher (SSRF). Fehler bei unvollständigem Import müssen Import als `unverified` belassen.
