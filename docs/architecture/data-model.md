# PostgreSQL-Datenmodell (verbindliche konzeptuelle Spezifikation)

Das Schema dient als Implementierungsvertrag; Hermes erstellt die **realen** SQLAlchemy-Modelle und Alembic-Migrationen. Primärschlüssel UUID; `created_at`, `updated_at` wo sinnvoll, integer check ≥ 0.

| Tabelle | Wichtige Felder / Constraints |
|---|---|
| `sets` | `id`, `provider`, `provider_set_id` UNIQUE, `name`, `year`, `image_url` |
| `projects` | `id`, `set_id`, `label`, `inventory_snapshot_id`, `status`, `created_at` |
| `inventory_snapshots` | `id`, `set_id`, `provider`, `source_revision`, `imported_at`, `validation_status`, `checksum` |
| `colors` | `provider`, `provider_color_id`, `name`, `rgb`, `bricklink_id` NULL, UNIQUE(provider,id) |
| `part_catalog` | `provider`, `part_num`, `name`, `category`, `image_url`, `bricklink_part_id` NULL, UNIQUE(provider,part_num) |
| `inventory_requirements` | `id`, `snapshot_id`, `part_id`, `color_id`, `inventory_class` (`required`/`spare`), `expected_qty`, UNIQUE(snapshot,part,color,class) |
| `inventory_provenance` | `requirement_id`, `source_type` (`set_regular`/`minifig_component`/`spare`), `source_ref`, `quantity` – beweist Summenaggregation |
| `minifig_requirements` | `snapshot_id`, `fig_ref`, `name`, `expected_qty`, `image_url` – Figuren-Checkliste ohne additive Mengenerhöhung |
| `sessions` | `id`, `project_id`, `label`, `position`, `mandatory`, `status` (`in_progress`/`completed`/`archived`) |
| `count_balances` | `session_id`, `requirement_id`, `quantity`, `revision`, UNIQUE(session,requirement) |
| `count_events` | `id`, `project_id`, `session_id`, `requirement_id`, `client_mutation_id`, `operation`, `delta`/`before`/`after`, `created_at`, `order_item_id` NULL, UNIQUE(project,client_mutation_id) |
| `unlisted_finds` | `id`, `session_id`, `part_num` NULL, `color_ref` NULL, `label`, `qty`, `resolution_status` |
| `replacement_orders` | `id`, `project_id`, `status`, `notes` |
| `replacement_items` | `id`, `order_id`, `requirement_id`, `qty_ordered`, `qty_received`, `target_session_id` NULL, `qty_booked` – check booked<=received |
| `project_events` | Abschluss, Wiederöffnen, Archivierung, Import, Zuordnungsänderung, Restore mit Zeit/Details |

## Wichtige Entwurfsentscheidungen

1. **Inventar-Snapshot immutable.** Erfassung referenziert genau eine importierte Revision. Kein stilles Austauschverfahren, das Counts auf falsche IDs setzt.
2. **Requirement `required` umfasst physische Teile aus Bau und Figuren**: provenance hält die Teilmengen auseinander, req. expected ist Summe. Spares eigener `inventory_class`.
3. **Keine Anforderungen pro Haus**. Sessions enthalten nur gezählte physische Mengen. Fehlteilzuordnung nur über `replacement_items.target_session_id` und ausdrücklich manuell.
4. Kein Zähler über Integer-Limits (DB BIGINT oder geprüft int). Zählstand >= 0; keine upper bound.
5. Eventlog und Materialisierung atomar. Im Fehlerfall komplettes Rollback. `client_mutation_id` ist innerhalb Projekt eindeutig und Payload-Mismatch gibt Fehler.
6. Export/Restore erhält UUIDs und schema_version oder führt eine dokumentierte Neu-ID-Zuordnung aus; nie referentielle Integrität brechen.

## Materialisierte Bilanz – SQL-Idee

```sql
SELECT r.id AS requirement_id, r.expected_qty,
       COALESCE(SUM(b.quantity) FILTER (WHERE s.status <> 'archived'), 0) AS counted
FROM inventory_requirements r
LEFT JOIN count_balances b ON b.requirement_id = r.id
LEFT JOIN sessions s ON s.id = b.session_id
WHERE r.snapshot_id = :snapshot_id AND r.inventory_class = 'required'
GROUP BY r.id;
```

**Achtung:** Im produktiven Query `sessions` per Projekt filtern und Archiv-Semantik eindeutig implementieren. Teste SUM bei NULL, 0 und 1000+ Positionen. Für das Schreiben atomaren Row Lock/Upsert und Retry-Schutz verwenden.
