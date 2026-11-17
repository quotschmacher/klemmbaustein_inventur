# LEGO Inventur – Hermes-Agent-Projektpaket

**Status:** Implementierte, lokal über Docker Compose betriebene Anwendung; Abnahme- und Betriebsnachweise in `IMPLEMENTATION_STATUS.md`.

Ziel: LEGO-Sets auf Vollständigkeit prüfen. Eine zentrale, verifizierte Inventarliste wird in beliebig viele **physische Zählbereiche** (z. B. Haus 1–4, Figuren) aufgeteilt. Die gezählten Mengen werden über alle Bereiche pro **Teilenummer + Farbe** summiert. Die Anwendung erkennt **Fehlmengen, Überschüsse und Fremdteile**. Jedes Haus kann unabhängig gezählt und eingepackt werden, ohne dass eine separate Soll-Liste pro Gebäude existiert.

**Startfall:** LEGO 75978-1 (Winkelgasse). **Sprache:** Deutsch. **Browser:** Desktop zuerst. **Datenhaltung:** PostgreSQL; nie nur im Browser. **Betrieb:** Docker Compose. **Entwicklung:** Docker Dev Containers (Python, Node und Tools nur im Container). **Agent:** Hermes Agent mit den Regeln in `AGENTS.md`.

## Einstieg mit Hermes

1. Diesen Ordner als Projektverzeichnis/Repository öffnen.
2. `AGENTS.md` und `agent/START_HERE.md` lesen. **Kein** `.hermes.md` anlegen: Hermes soll die hierarchischen `AGENTS.md`-Dateien laden.
3. In VS Code: **Dev Containers: Reopen in Container** (Docker und eine Devcontainer-fähige IDE sind die einzigen Host-Voraussetzungen). Alternativ den Agent auf dem Host starten und **sämtliche Build-/Test-Kommandos im Container** ausführen.
4. Hermes bei Bedarf **im Devcontainer** installieren und starten: siehe `docs/specs/09-hermes-in-devcontainer.md`.
5. `.env.example` nach `.env` kopieren und zufälliges Datenbankpasswort festlegen. Rebrickable-API-Schlüssel optional ergänzen. `.env` niemals committen.
6. In Hermes den Inhalt von `agent/START_HERE.md` als Startauftrag verwenden. Meilensteine unter `agent/phases/` nacheinander umsetzen.
7. Der Devcontainer startet **nur Workspace und PostgreSQL**; die späteren API-/UI-Services sind durch Hermes nach Spezifikation zu entwickeln. Die fertige Anwendung muss mit `docker compose up -d --build` unter `http://localhost:8080` laufen.

## Verifizierter Entwicklungs- und Startablauf (Task 01)

Die folgenden Befehle werden ausschließlich im Devcontainer beziehungsweise über Docker Compose ausgeführt. Sie benötigen keine lokale Python-, Node- oder PostgreSQL-Installation:

```bash
# Devcontainer/Workspace mit PostgreSQL starten
docker compose -f compose.dev.yaml up -d --build

# Im Workspace Abhängigkeiten installieren und die Qualitätsprüfungen ausführen
docker compose -f compose.dev.yaml exec workspace python -m pip install -e '/workspace/backend[dev]'
docker compose -f compose.dev.yaml exec workspace npm ci --prefix /workspace/frontend
docker compose -f compose.dev.yaml exec workspace sh -lc 'cd /workspace/backend && ruff check . && pytest -p no:cacheprovider -q'
docker compose -f compose.dev.yaml exec workspace sh -lc 'npm test --prefix /workspace/frontend && npm run lint --prefix /workspace/frontend && npm run build --prefix /workspace/frontend'

# Produktiv-Compose lokal starten (nur Web ist veröffentlicht)
docker compose config
docker compose up -d --build
docker compose ps
curl -fsS http://localhost:8080/
curl -fsS http://localhost:8080/api/health
```

`docker compose down` stoppt die Container, erhält jedoch das benannte Volume `lego-inventur_pgdata`. Nie `docker compose down -v` verwenden, wenn Daten erhalten bleiben sollen.

## Datenexport und Projekt-Restore

Die API stellt pro Projekt diese Downloads bereit:

- `GET /api/v1/projects/{id}/exports/inventory.csv`: Soll-, Gesamt-Ist-, Fehl- und Überschussmengen, einschließlich `spare`.
- `GET /api/v1/projects/{id}/exports/differences.csv`: Überschüsse sofort; Fehlmengen erst nach Abschluss aller Pflichtbereiche.
- `GET /api/v1/projects/{id}/exports/backup.json`: versioniertes Projektbackup (`schema_version: 1`) mit Snapshot, Quellen/Prüfsumme, Bereichen, Zählständen/-events, Bestellungen, Fremdfunden und Projekt-Events.
- `POST /api/v1/projects/import-backup`: nimmt das JSON-Objekt eines Backups entgegen, validiert Version und Referenzen und erstellt ausschließlich ein neues Projekt. Ein vorhandenes Projekt wird nie überschrieben.

Die Wiederherstellung verwendet einen bereits vorhandenen, prüfsummengleichen Snapshot wieder oder legt ihn aus dem Backup an. Neue Projekt-, Bereichs-, Event- und Bestell-UUIDs verhindern Kollisionen mit dem Original und erhalten alle referenziellen Beziehungen.

`GET /api/v1/projects/{id}/exports/wanted-list.xml` erzeugt eine BrickLink-Wanted-List nur für bestätigte Fehlmengen und nur bei Teil- **und** Farb-Mapping. Fehlt mindestens ein Mapping, antwortet die API mit `422 BRICKLINK_MAPPING_MISSING` und einer Warnliste; sie liefert in diesem Fall ausdrücklich kein unzuverlässiges XML.

## Lokale Aktualisierung nach Git-Commits

Dieses Repository enthält einen versionierten Post-Commit-Hook. Einmal pro Clone aktivieren:

```bash
git config core.hooksPath .githooks
```

Danach führt jeder lokale Commit automatisch `docker compose up -d --build` aus und stellt die aktualisierten Container unter `http://localhost:8080` bereit.

## Struktur

```
AGENTS.md                  Verbindliche Agent-/Projektregeln
agent/START_HERE.md         Startauftrag für Hermes
agent/phases/               Konkrete Implementierungsaufträge in Reihenfolge
agent/roles/                Fachrollen für (Sub-)Agents
backend/AGENTS.md           Python-/Datenbankkonventionen
frontend/AGENTS.md          UI-/Accessibility-Konventionen
docs/specs/                 Fachliche Anforderungen, Rechenregeln, API, UI, Tests
docs/architecture/          Architektur, Datenmodell, ADRs
.devcontainer/              Reproduzierbare Entwicklungsumgebung
compose.dev.yaml            Datenbank + Development-Workspace
compose.yaml                Produktions-Zielkonfiguration (erst nach Implementierung lauffähig)
.env.example                Konfigurationsvorlage ohne echte Secrets
```

## Beschlossene Entscheidungen

- PostgreSQL 16 statt MySQL (eine DB wählen, nicht beide implementieren).
- FastAPI / Python 3.12, SQLAlchemy 2, Alembic, pytest; React / TypeScript / Vite, Vitest/Testing Library, Playwright.
- Zugriff lokal über einen Reverse Proxy; DB nie öffentlich. Produktions-Images multi-stage und non-root.
- Rebrickable-API serverseitig oder legal bezogene Importdateien. Keine imaginären Inventare pro Haus.
- Minifiguren in einzelne Bauteile **genau einmal** expandieren; Figuren-Checkliste optional separat, ohne Doppelzählung.
- Ersatzteile separat vom Pflichtinventar; Abgleich auf der richtigen Basis.

## Quellen

- Hermes Context Files: https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files
- Rebrickable API: https://rebrickable.com/api/v3/docs/
- Rebrickable API Terms/Downloads: https://rebrickable.com/api/
- BrickLink Wanted-List-Upload: https://www.bricklink.com/help.asp?helpID=2567

## Lizenz/Compliance

Keine LEGO-/Rebrickable-Bilder oder Daten ohne Beachtung der jeweiligen Bedingungen massenhaft einbinden. Anwendungsname und Design eigenständig; kein LEGO-/BrickTally-Branding kopieren.

## Entwicklung in kurzen Hermes-Sitzungen

1. Für einen neuen Projektstart `agent/START_HERE.md` an Hermes geben.
2. Immer **nur eine Task** aus `agent/TASK_INDEX.md` implementieren und testen lassen.
3. Nach Tokenlimit eine neue Hermes-Sitzung beginnen und `agent/RESUME.md` übergeben.
4. Übergabe steht in `agent/checkpoints/CURRENT.md`; Details in `IMPLEMENTATION_STATUS.md`.
5. Git-Commits sichern Codefortschritt; PostgreSQL-Nutzdaten separat sichern. Keine Volumes löschen.

Die Aufgaben sind in 10 kleine Module aufgeteilt und verweisen auf die ursprünglichen 5 Phasen und vollständigen Specs.
