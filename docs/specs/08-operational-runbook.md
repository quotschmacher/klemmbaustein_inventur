# Betriebs-Runbook (Zielzustand nach Umsetzung)

## Host-Voraussetzungen

Docker Engine/Desktop + Docker Compose Plugin. Optional VS Code mit Dev Containers Extension für IDE-gestützte Entwicklung. Keine lokale Python-, Node-, Postgres-, Nginx- oder sonstige Anwendungsinstallation.

## Entwicklung

```bash
cp .env.example .env
# Passwort in .env setzen
# Projekt mit Dev Containers: Reopen in Container öffnen
# Im Container, sobald Hermes App-Skelette gebaut hat:
cd /workspace/backend && python -m pip install -e '.[dev]'
cd /workspace/frontend && npm ci
# Entwicklungsserver gemäß fertig dokumentiertem Startkommando
```

Die beiden `pip`-/`npm`-Befehle gehören **in den Devcontainer**, nicht auf den Host. Hermes muss den finalen Workflow mit Lockfiles spezifizieren und prüfen.

## Produktion

```bash
cp .env.example .env
# Sicheres Passwort/API-Key in .env eintragen
docker compose up -d --build
docker compose ps
# http://localhost:8080
```

Dieser Befehl funktioniert **erst nachdem Hermes backend, frontend, Dockerfiles und Migrationen implementiert hat**. `docker compose down` entfernt keine benannten Datenvolumes; `docker compose down -v` entfernt sie und ist für produktive Daten verboten.

## Datenbank sichern

Hermes implementiert `scripts/backup.sh` (`pg_dump`, Datei mit Datum) und einen getesteten Restore. DB-/Projektbackup vor jedem Upgrade. Port der Datenbank nicht an Host publizieren.

## Fehlerbehebung

- Kein UI: `docker compose ps`, Logs `docker compose logs --tail=100 web api`, API health.
- API-Import scheitert: Key/Netz/Rate-Limit prüfen, CSV als Alternative nutzen.
- Zählwerte falsch: `count_events`, `count_balances`, Sessionstatus, Mapping prüfen; niemals DB manuell ohne Migration korrigieren.
- Farbfilter leer: prüfen ob echte Farbe im Snapshot enthalten, Clear-Filter anzeigen.
