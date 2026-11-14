# Zielarchitektur

```
Browser (lokal)
   |
   | http://127.0.0.1:8080
   v
web: nginx + gebaute React/Vite-Dateien
   | reverse proxy /api/
   v
api: FastAPI + business services / Rebrickable importer
   |
   +-- PostgreSQL 16 (internes Volume pgdata)
   +-- Rebrickable HTTPS (nur bei Import, serverseitiger Key)
```

**Warum diese Wahl?** FastAPI bietet klaren OpenAPI-Vertrag, Python ist praktisch zum Importieren und Validieren von LEGO-Daten; React/TypeScript ermöglicht schnelle filterbare Zähllisten. PostgreSQL gewährleistet atomare Transaktionen/Audit. MySQL wäre möglich, wird aber nicht parallel implementiert.

## Deployment

- Development: `.devcontainer/devcontainer.json` über `compose.dev.yaml`; Service `workspace` mit Python & Node, `db` mit persistentem Volume. API/Frontend als Prozesse *innerhalb des Workspaces* auf Ports 8000/5173 während der Entwicklung; keine Host-Runtimes.
- Production: `compose.yaml` mit `web`, `api`, `db`. Public: nur Web-Port 8080, DB nicht published.
- Auf Linux/Mac/Windows Host Docker (und VS Code mit Dev Containers für IDE) erforderlich; nicht „gar nichts“ installieren: **Docker selbst muss vorhanden sein**.

## Anwendungsschichten

- frontend: UI + API client, Filter und Bearbeitung.
- backend/routes: HTTP transport; domain/services: count service, reconciliation, inventory import, order allocation, exports; repositories: DB.
- migrations: Alembic.
- integration tests: echte PostgreSQL-Instanz.

## Datenfluss

1. Benutzer importiert Set. Importer lädt paginiert / validiert, erstellt immutable Revision `inventory_snapshot`.
2. Benutzer öffnet Projekt / erfasst fünf Bereiche; UI fragt Items+Farbe/Sortierung an.
3. Benutzer klickt +: Client erzeugt einmalige Mutation-UUID, API schreibt Event+Balance in einer Transaktion, gibt globale Aggregate zurück.
4. Frontend zeigt sofort aktualisierte Werte inkl. Überschuss.
5. Nach allen abgeschlossenen Pflichtbereichen werden Differenzen als echte Fehlteile ausgewiesen und exportiert.

## Import der Minifiguren

Rebrickable standardmäßig `/lego/sets/{set_num}/parts/?inc_minifig_parts=0` und `/lego/sets/{set_num}/minifigs/`; für jede Figur `/lego/minifigs/{fig_id}/parts/`, multipliziert mit Figuren-Sollanzahl. Für den Pflichtbestand sind beide Quellen **additiv**. Rebrickable-Datenstruktur/Version in Tests verifizieren. Alternativ ein einziger vollständig expandierter Import (`inc_minifig_parts=1`) **statt** getrennter Expansion; nie beides.

## Skalierung

Der Zugriff erfolgt lokal mit nur einem Nutzer (V1). Trotzdem DB Idempotenz/Race-sicher. Indizes auf (project_id, part_id, color_id), (session_id, inventory_item_id), (project_id, client_mutation_id), Sortierung/Farbe. Pagination bei großen Listen.
