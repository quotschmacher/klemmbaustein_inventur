# Hilfsskripte – durch Hermes zu implementieren

- `check.sh`: in Containern Lint, Typen, Backend-Tests, Frontend-Tests, E2E.
- `backup.sh`: `pg_dump` aus PostgreSQL-Container mit Timestamp in `./backups/` (lokal; gitignored).
- `restore.sh`: Restore ausschließlich in benannte Ziel-Datenbank nach expliziter Bestätigung.
- `smoke.sh`: Docker-Betriebsprüfung inklusive erneuter Auslesung nach Neustart.

Diese Scripts sind noch nicht implementiert; Phase 5 erzeugt sie und testet sie. Keine Placebo-Scripts hinzufügen.
