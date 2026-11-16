# Implementierungsstatus

**Stand:** Task 01 ist vollständig validiert. FastAPI-Healthroute, React-Startseite, Produktions-Compose, Reverse Proxy und persistentes PostgreSQL-Volume sind vorhanden und über `http://localhost:8080/` erreichbar.

| Phase | Status | Testergebnisse | Offene Punkte |
|---|---|---|---|
| 1 – Setup/Schema | abgeschlossen | Task 01 und 02 abgenommen: Compose, Healthchecks, SQLAlchemy/Alembic-Schema und produktive Migration | keine |
| 2 – Inventarimport | abgeschlossen | CSV-/Rebrickable-Import, Quellen-/Provenance-Daten und lokale Cache-Wiederverwendung abgenommen | keine |
| 3 – Zählen/UI | offen | nicht durchgeführt | 5 Sessions, +/- und Farbfokus, Überschuss |
| 4 – Nachbestellung | offen | nicht durchgeführt | CSV/JSON/XML, Zuordnung |
| 5 – Härtung/Abnahme | offen | nicht durchgeführt | Backup/Restore, End-to-End |

Hermes Agent: Nach jeder Phase mit echten ausgeführten Befehlen und Ergebnissen aktualisieren.

## Task-Verlauf (10 Checkpoints)

| Task | Status | Nachgewiesene Tests | Commit |
|---|---|---|---|
| 01 – Devcontainer und Docker-Start | DONE | Backend: 1 pytest; Frontend: 1 Vitest; Ruff, ESLint, TypeScript/Vite-Build; `docker compose up -d --build`, alle Dienste healthy, Root und `/api/health` auf Port 8080 | `952ff2f task-01: Devcontainer und Docker-Start` |
| 02 – PostgreSQL-Datenmodell und Migrationen | DONE | 4 pytest, Ruff, `alembic upgrade head`; frische PostgreSQL-Testdatenbank und Produktions-Migrationsservice auf Revision `d5a0b1802099` geprüft | `e3c245a task-02: PostgreSQL-Datenmodell und Migrationen` |
| 03 – Sets, Inventarimport und Quellen | DONE | 14 Backend-Tests; Frontend-Test/Lint/Build; Alembic head; echte lokale Rebrickable-UI-Abnahme mit Cache und Proxy-Timeoutschutz | `933374b fix: Rebrickable-Import ohne Proxy-Timeout` |
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
- Frühere Portbelegung: Der ursprünglich fremd belegte Host-Port 8080 war später frei. Anschließend lief `docker compose up -d --build` erfolgreich; `db`, `api` und `web` waren healthy, die Bindung war `127.0.0.1:8080->8080/tcp`, die Startseite und `/api/health` antworteten erfolgreich.
- Architekturentscheidungen: keine neue ADR; ADR-001, ADR-002 und ADR-006 wurden umgesetzt.
- Nächste Task: 02 – PostgreSQL-Datenmodell und Migrationen.

## Task 02 – 15. November 2026

- Ergebnis: Vollständiges SQLAlchemy-2-Datenmodell für Set, Snapshot, Teile/Farben, Anforderungen/Provenance, Bereiche, Bilanzen/Events, Fremdfunde, Bestellungen und Projekt-Events. Nichtnegative Mengen, eindeutige fachliche Schlüssel, revisionierte Bilanzen und Idempotenzschlüssel sind durch Datenbank-Constraints abgesichert.
- Migration: Alembic-Initialmigration `d5a0b1802099` erstellt alle 15 Tabellen. Der Compose-Service `migrate` führt sie nach gesundem PostgreSQL und vor der API aus.
- Tests: `ruff check .`; `pytest -p no:cacheprovider -q` mit 4 erfolgreichen Tests; `alembic upgrade head` und `alembic current`; frische Testdatenbank `lego_inventory_schema_test` migriert und mit Migrationstest verifiziert. Produktions-Compose setzte die Revision im persistenten Volume, API-Health danach erfolgreich.
- Behobener Build-Fehler: Der erste Produktions-Migrationscontainer enthielt `alembic.ini` und `migrations/` nicht. `backend/Dockerfile` kopiert beide nun ins Image; der erneute Compose-Start lief erfolgreich.
- Architekturentscheidungen: keine neue ADR; ADR-001, ADR-005 und ADR-006 konkret umgesetzt.
- Nächste Task: 03 – Sets, Inventarimport und Quellen.

## Task 03 – 16. November 2026

- Ergebnis: Projekte können ein synthetisches UTF-8-CSV-Inventar importieren und danach die Teileliste anzeigen. Anforderungen bleiben nach Teilenummer, Farbe und Inventarklasse getrennt; Spares werden nicht Pflichtteilen zugerechnet. Wiederholte CSV-Dateien sind idempotent.
- Rebrickable: Der serverseitige Import akzeptiert Kartonnummern wie `75978` und normalisiert sie zu `75978-1`. Er verwendet die expandierte Set-Stückliste sowie eine Figurencheckliste, speichert Quelle/Checksumme/Provenance und zeigt das Ergebnis in der UI. API-Schlüssel bleibt ausschließlich serverseitig.
- Abrufschutz: Wiederholte Imports desselben Sets verwenden einen validierten lokalen Rebrickable-Snapshot ohne neue Anbieter-Requests. Der Reverse Proxy wartet bis zu 180 Sekunden; HTML-Proxyfehler werden im UI verständlich behandelt.
- Tests und Abnahme: `ruff check .`, 14 Backend-Tests, `alembic upgrade head`/`current` auf `8e64fb2d1a11`, Frontend-Test/ESLint/Vite-Build, produktive Container und `/api/health` erfolgreich. Der Nutzer bestätigte den erfolgreichen lokalen Rebrickable-Import nach Cache-/Timeoutkorrektur.
- Offene Risiken: Kein automatischer Provider-Refresh; ein späterer expliziter Aktualisierungsworkflow muss Cache-Invalidierung und Rate-Limit berücksichtigen.
- Nächste Task: 04 – Bereiche und Zähl-API.
