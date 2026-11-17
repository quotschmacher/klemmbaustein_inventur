# Hilfsskripte

Alle Skripte werden aus dem Repository-Root heraus aufgerufen und nutzen Docker Compose; auf dem Host sind weder Python, Node noch PostgreSQL erforderlich.

- `./scripts/check.sh`: startet den Devcontainer und führt Ruff, Backend-Tests, Frontend-Tests, ESLint und den Produktionsbuild aus.
- `./scripts/backup.sh`: erstellt einen PostgreSQL-Custom-Dump unter `./backups/` mit UTC-Zeitstempel und restriktiven Dateirechten. Das Verzeichnis ist gitignored.
- `./scripts/restore.sh --confirm BACKUP.dump ziel_restore_db`: restauriert nur in eine **neue**, sicher benannte Datenbank, deren Name `restore` oder `test` enthält. Die laufende Produktivdatenbank und vorhandene Zieldatenbanken werden grundsätzlich nicht überschrieben.
- `./scripts/smoke.sh`: startet den Produktions-Compose-Stack, prüft `/` und `/api/health`, startet API und Web neu und vergleicht die Projektliste vor/nach dem Neustart.
- `./scripts/e2e.sh`: erzeugt einen frischen, isolierten Compose-Projektnamen samt neuem Volume, prüft den Browser-Workflow mit Playwright gegen Port 18080 und beendet danach nur Container/Netzwerk (nie das Volume).

Beispiel:

```bash
./scripts/backup.sh
./scripts/restore.sh --confirm backups/lego-inventur-20261117T120000Z.dump lego_inventory_restore_test
./scripts/smoke.sh
```
