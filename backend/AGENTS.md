# Backend-spezifische Agent-Regeln

Stack: Python 3.12, FastAPI, SQLAlchemy 2 async oder sync (eins konsistent), Alembic, Pydantic v2, PostgreSQL 16, pytest. Typannotationen und strukturierte Fehlerantworten. Geschäftslogik in Services, nicht in Routen.

- Mutation atomar in Datenbanktransaktion. Eindeutige `client_mutation_id` gegen Request-Retries und Doppelklick-Replays; `unique(project_id, client_mutation_id)`.
- `count_events` unveränderliches Auditlog; `count_balances` Materialisierung. Delta minus nur bei resultierender Menge >= 0.
- Zeilensperre/atomare Update-Semantik; konkurrierende Änderungen und Retry mit Tests belegen.
- `required_quantity` aus Snapshot ist immutable nach Inventurstart; Reimport nur über kontrollierte Revision/Migration.
- Benutze Decimal/Int für Stückzahlen, NIE Float. API-Inputs begrenzen, validieren; stabile Error-Codes und Pagination.
- Server lädt Rebrickable-Daten mit Timeouts, begrenzter Retry-Strategie, `next`-Pagination, Rate-Limits und prüft die Vollständigkeit. Fehlerhafte/teilweise Imports nicht aktivieren.
- Importiert Minifig-Bestandteile genau einmal. Spares getrennt halten. Mapping BrickLink IDs nur wenn geprüft; sonst Exportblocker anzeigen.
- DB-Verbindung ausschließlich aus Umgebungsvariable; kein Passwort in Quelltext oder Logs.
- Tests mit echter PostgreSQL-Instanz im Docker-Verbund, nicht nur SQLite.
