# LEGO Inventur – Hermes-Agent-Projektpaket

**Status:** Spezifikation und Docker-/Devcontainer-Grundgerüst; **noch keine fertige Anwendung**.

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
