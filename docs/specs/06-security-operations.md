# Betrieb, Sicherheit und Datenpflege

## Netzwerk

Produktiv nur `127.0.0.1:8080:80` von `web` veröffentlichen. `api` und `db` nur in Compose-internem Netzwerk. Bei späterem Zugriff im LAN oder Internet zuerst Authentifizierung/HTTPS und Zugriffsschutz hinzufügen; nicht ungeprüft bind `0.0.0.0`.

## Secrets

DB-Passwort und Rebrickable-Key nur `.env` oder Docker Secrets; `.env` gitignored. Keine Secrets in Browserbundles, Source, Testfixtures, Screenshots oder Logs. DB-Benutzer mit minimalen Berechtigungen; keine `postgres`-Superuserverbindung in App.

## Persistenz/Backup

Benanntes Docker-Volume `pgdata`; `docker compose down` ohne `-v` erhält Daten. Regelmäßige `pg_dump`-Backups (Script durch Agent erstellen), Restore in eine **separate** DB testen. JSON-Projektbackup mit `schema_version`, `inventory_snapshot`, `sessions`, `counts`, `events`, `replacements`, `extra_finds`, Source-Metadaten und Prüfsummen. Import nicht automatisch Original überschreiben.

## Externe Daten

Rebrickable Rate-Limits/Terms respektieren, Backoff; Server-Timeout und begrenzter Retry. API liefert Bildlinks; Lizenz-/ToS-Compliance prüfen, keine unzulässigen Bilder massenhaft spiegeln. Bei offline fehlenden Bildern Fallback anzeigen. Echte Bestell-XML nur mit gesichertem BrickLink-ID-Mapping.

## Docker und Updates

Versionsnummern festlegen/pinnen und regelmäßig aktualisieren. Non-root in API/Web, Healthchecks, Restart-Policy, migrations only once per release and before API accepts traffic. Testskript zur Wiederaufnahme nach Neustart und Upgrade. Auditlog für Änderungen, Archivierungen und Nachbestellungen.
