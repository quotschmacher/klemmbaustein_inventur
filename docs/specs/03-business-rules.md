# Zentrale Rechen- und Geschäftsregeln

## Fachliche Schlüssel

- Ein physisches Teil ist fachlich mindestens `(part_num, color_id)`; **Farbe ist Bestandteil der Identität**.
- `source_kind` dokumentiert Herkunft der Sollposition (`set_regular`, `minifig_component`, `spare`). Für Pflicht-Vollständigkeit werden `set_regular` und `minifig_component` zu **einer** `required` Sollmenge je Teil/Farbe **addiert**; `spare` bleibt eine gesonderte Sollkategorie.
- Für dieselbe Teilenummer/Farbe: `required_total = set_regular_qty + Σ(minifig_qty × component_qty)`. **Nicht** nochmal zusätzlich `inc_minifig_parts=1` importieren, wenn separat expandiert wurde.
- `is_spare=true` nie automatisch als normal erforderlich behandeln. Gesonderter Tab „Ersatzteile“ mit eigenem `spare_expected`; optional gefunden und geprüft.
- Original-LEGO-Pieces-Zahl kann von expandierten Inventarpositionen abweichen (Figuren, Spares, Druckteile). Keine Gleichheit mit aufgedruckter Gesamtzahl erzwingen.

## Zählung

Für jede `inventory_item_id` und `session_id` eine persistierte Zahl `count >= 0`. Nicht vorhandener Eintrag wird als 0 behandelt. Jedes `POST adjust` erzeugt eine unveränderliche Transaktion mit UUID-Idempotenzschlüssel.

```
global_count(item) = Σ count(session, item) über aktive Zählbereiche
missing(item) = max(0, expected(item) - global_count(item))
surplus(item) = max(0, global_count(item) - expected(item))
delta(item) = global_count(item) - expected(item)
```

**Wichtig:** `global_count` darf über `expected` steigen; `surplus` wird **sofort** angezeigt und darf nicht beim Sollbetrag abgeschnitten werden.

`missing` ist ein numerischer Wert, wird aber erst als **„fehlend/bestellbar“** bezeichnet, wenn alle als Pflicht markierten Zählbereiche abgeschlossen sind. Vorher **„noch offen, vorläufige Differenz“**. Ein als abgeschlossen markierter Bereich darf wieder geöffnet werden; dadurch wird das ganze Projekt erneut vorläufig. Bei unvollständiger Inventardatenbasis KEINE endgültige Vollständigkeit melden.

## Korrektur und Parallelität

- `delta=-1` bei 0 → HTTP 422/409, keine negative Bilanz.
- `delta=+1` bei Soll → akzeptiert, erzeugt Überschuss.
- Direkteingabe „set=20“ erfordert `expected_revision` des bisherigen Zählstands; bei Konkurrenz `409 Conflict` und re-fetch; keine verlorenen Änderungen.
- `client_mutation_id` wiederholt → identisches gespeichertes Ergebnis zurückgeben, **nicht** nochmals addieren. Idempotenz nie nur im Browser lösen.
- Unbekannte oder nicht im offiziellen Inventar aufgeführte Teile über separate `extra_finds`; sie haben keine Sollposition und werden nicht stillschweigend in Soll eingefügt.
- `archived` Bereiche zählen NICHT in Summen, Archivierung mit gezählten Teilen braucht explizite Bestätigung und Auditlog. Standardmäßig nicht löschen.

## Nachbestellungen/Zuordnung

Fehlmenge ist auf **Setebene**, nicht Haus-Ebene, bewiesen. Ein `target_session` für eine Nachbestellung ist **manuelle organisatorische Zuordnung**, kein Beweis des ursprünglichen Verwendungsorts.

`ordered`/`received` erhöhen Ist **nicht** automatisch. Erst der explizite `count replacement into session`-Buchungsschritt nach tatsächlicher physischer Zuordnung addiert +n, verknüpft mit order_item-Id, idempotent. Auditlog verhindert doppelte Buchung.

## Vollständigkeitsstatus

`READY`: Inventarsnapshot validiert; alle Pflichtbereiche abgeschlossen; keine Differenzen im Pflichtinventar und keine ungelösten Fremdteile. Spares werden separat gemeldet. `DEFICIT`: mindestens ein fehlender Pflichtstein; `SURPLUS_REVIEW`: Überschuss oder Fremdteil vorhanden; `IN_PROGRESS`: unvollständige Erfassungen; `UNVERIFIED`: fehlerhafte/offene Quellenbasis. Kombinationen im UI anzeigen, keine gegenseitige Verdeckung.
