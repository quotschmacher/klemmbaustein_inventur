# HTTP-API v1 (Vertrag)

Base: `/api/v1`, JSON, OpenAPI von FastAPI unter `/api/docs` nur lokal oder dev. Alle IDs UUID (Strings), Stückzahlen Ganzzahlen >= 0, UTC Zeitstempel. Standardfehler `{ "error": { "code": "...", "message": "...", "details": {} } }`. Erfolg `{ "data": ..., "meta": ... }`. Pagination per `limit`/`cursor`, Standardlimit 100.

| Methode | Route | Aufgabe |
|---|---|---|
| GET | `/health` | Health inklusive DB |
| POST | `/projects` | Projekt mit Set-ID anlegen |
| GET | `/projects` | Projektliste |
| GET | `/projects/{id}` | Metadaten, Snapshotstatus |
| POST | `/projects/{id}/import/rebrickable` | Import serverseitig, Schlüssel nur ENV |
| POST | `/projects/{id}/import/csv` | CSV hochladen und validieren |
| GET | `/projects/{id}/inventory` | Teile mit Bild, Farbe, Soll, Ist pro Bereich und global, Filter |
| GET | `/projects/{id}/colors` | verfügbare Farben für Filter |
| POST | `/projects/{id}/sessions` | Zählbereich anlegen |
| GET | `/projects/{id}/sessions` | Bereiche / Status |
| PATCH | `/sessions/{id}` | Name, Reihenfolge, Pflicht, Abschlussstatus |
| POST | `/sessions/{id}/counts/adjust` | delta, UUID mutation_id, part-color item |
| PUT | `/sessions/{id}/counts/{inventory_item_id}` | absolute Menge mit revision |
| GET | `/projects/{id}/summary` | globale Werte, Fehl-/Überschussstatus |
| GET | `/projects/{id}/differences` | `type=missing|surplus|unlisted|all`, final-Flag |
| POST | `/sessions/{id}/unlisted` | Fremdteilfund |
| GET/POST/PATCH | `/projects/{id}/replacements` | Bestellung / Eingang / Zielbeutel |
| POST | `/replacements/{id}/book-into-session` | erhaltenen Ersatz physisch zubuchen |
| GET | `/projects/{id}/exports/inventory.csv` | Inventar/Counts |
| GET | `/projects/{id}/exports/differences.csv` | Fehl-/Überschussliste |
| GET | `/projects/{id}/exports/wanted-list.xml` | BrickLink bei verifiziertem Mapping |
| GET | `/projects/{id}/exports/backup.json` | Projektbackup |
| POST | `/projects/import-backup` | Validierter Restore (neues Projekt oder explizites Replace) |

## Beispiele

`POST /api/v1/sessions/{session_id}/counts/adjust`

```json
{"inventory_item_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","delta":1,"client_mutation_id":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"}
```

Antwort (200):

```json
{"data":{"session_quantity":21,"global_quantity":39,"expected_quantity":38,"delta_global":1,"missing_quantity":0,"surplus_quantity":1,"session_revision":7,"status":"surplus"}}
```

Wiederholung **derselben** `client_mutation_id` gibt das ursprüngliche Resultat zurück. Eine **neue** UUID addiert erneut. Antwort bei ungültiger negativer Menge `422 INVALID_NEGATIVE_QUANTITY`, bei veraltetem Revisionstag `409 REVISION_CONFLICT`.

`GET /projects/{id}/inventory?session_id=...&color_id=72&sort=color_asc&search=tile&status=all&limit=100&cursor=...` – Backend filtert korrekt und liefert `total_visible`. `color_id` NULL = alle, ansonsten **exakt nur eine Farbe**. Status `uncounted`, `counted`, `surplus`, `provisional_gap`; keine vorläufige Gap als bestellbare Missing-Liste ausgeben.

`GET /projects/{id}/summary` Antwort enthält `required_sessions_total`, `required_sessions_completed`, `inventory_verified`, `counts_total`, `surplus_types`, `provisional_gap_units`, `confirmed_missing_units`, `all_required_complete`, `required_status`, `spares_status` und pro Bereich eigene Kennzahlen.

Bei `POST /projects` kann eine nicht verfügbare Inventardatenquelle zunächst `pending_import` ergeben. `POST /.../import/rebrickable` meldet Fehler/Status, nie leeres Inventar als erfolgreich.

### API-Fehlercodes

`INVENTORY_NOT_READY`, `INVALID_NEGATIVE_QUANTITY`, `REVISION_CONFLICT`, `DUPLICATE_MUTATION_PAYLOAD_MISMATCH`, `SESSION_ARCHIVED`, `UNKNOWN_INVENTORY_ITEM`, `REBRICKABLE_RATE_LIMIT`, `IMPORT_INCOMPLETE`, `BRICKLINK_MAPPING_MISSING`, `INVALID_BACKUP_VERSION`.
