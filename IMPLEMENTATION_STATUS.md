# Implementierungsstatus

**Stand:** Task 01 ist implementiert und bis auf den auf diesem Host belegten Zielport 8080 validiert. FastAPI-Healthroute, React-Startseite, Produktions-Compose, Reverse Proxy und persistentes PostgreSQL-Volume sind vorhanden.

| Phase | Status | Testergebnisse | Offene Punkte |
|---|---|---|---|
| 1 – Setup/Schema | WIP | Backend-/Frontend-Tests, Lint, Build und Compose-Smoketest erfolgreich | Exakte Host-Port-Abnahme auf 8080 nach Freigabe des bereits belegten Ports; DB-Schema/Migrationen sind Task 02 |
| 2 – Inventarimport | offen | nicht durchgeführt | API/CSV, Figuren, Spares |
| 3 – Zählen/UI | offen | nicht durchgeführt | 5 Sessions, +/- und Farbfokus, Überschuss |
| 4 – Nachbestellung | offen | nicht durchgeführt | CSV/JSON/XML, Zuordnung |
| 5 – Härtung/Abnahme | offen | nicht durchgeführt | Backup/Restore, End-to-End |

Hermes Agent: Nach jeder Phase mit echten ausgeführten Befehlen und Ergebnissen aktualisieren.

## Task-Verlauf (10 Checkpoints)

| Task | Status | Nachgewiesene Tests | Commit |
|---|---|---|---|
| 01 – Devcontainer und Docker-Start | WIP | Backend: 1 pytest; Frontend: 1 Vitest; Ruff, ESLint, TypeScript/Vite-Build; Compose-Stack/Health auf temporärem Host-Port 18080 | Commit nach Status-/Checkpoint-Update; exakte 8080-Abnahme durch fremde Portbelegung offen |
| 02 – PostgreSQL-Datenmodell und Migrationen | TODO | noch keine | – |
| 03 – Sets, Inventarimport und Quellen | TODO | noch keine | – |
| 04 – Bereiche und Zähl-API | TODO | noch keine | – |
| 05 – Gesamtsummen, Fehlmengen und Überschüsse | TODO | noch keine | – |
| 06 – Zähloberfläche und Farbfilter | TODO | noch keine | – |
| 07 – Gesamtübersicht und Abschlussworkflow | TODO | noch keine | – |
| 08 – Fehlteile, Bestellungen und Beutelzuordnung | TODO | noch keine | – |
| 09 – CSV/JSON-Export, Restore und BrickLink | TODO | noch keine | – |
| 10 – Security, Qualität und produktive Abnahme | TODO | noch keine | – |

Nach jedem Arbeitsauftrag nur nach ausgeführter Prüfung auf DONE setzen. Bei unterbrochener Implementierung WIP verwenden.

## Task 01 – 15. November 2026

- Ergebnis: Devcontainer mit Python 3.12, Node 22 und PostgreSQL-Client; FastAPI `/health` prüft PostgreSQL; React/Vite-Startseite; nginx-Reverse-Proxy `/api/`; `pgdata` ist ein benanntes Volume. Produktions-Images laufen als nicht-root-Benutzer.
- Neue/angepasste Dateien: `.devcontainer/Dockerfile`, `.devcontainer/devcontainer.json`, `compose.yaml`, `backend/`, `frontend/`, `README.md`; dazu dieser Status und der Checkpoint.
- Ausgeführt und erfolgreich: `docker compose -f compose.dev.yaml up -d --build`; Backend: `ruff check .` und `pytest -p no:cacheprovider -q` (1 passed); Frontend: `npm test`, `npm run lint`, `npm run build` (je erfolgreich); `docker compose config --quiet`; Produktions-Compose mit temporärem Port-Override, danach Root-Seite und `/api/health` erfolgreich.
- Persistenz: Nach `docker compose ... restart db` waren DB, API und Web wieder healthy; Docker-Mount ist `lego-inventur_pgdata:/var/lib/postgresql/data`.
- Blocker: `http://localhost:8080/` liefert auf diesem Host eine bereits laufende fremde Anwendung. Der Stack wurde unverändert unter `127.0.0.1:18080` geprüft; der Compose-Vertrag veröffentlicht weiterhin ausschließlich `127.0.0.1:8080:8080`. Keine fremden Prozesse wurden beendet.
- Architekturentscheidungen: keine neue ADR; ADR-001, ADR-002 und ADR-006 wurden umgesetzt.
- Nächste Task: 02 – PostgreSQL-Datenmodell und Migrationen.
