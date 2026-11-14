# Startauftrag an Hermes Agent

Du befindest dich im Repository `lego-inventur-hermes`. **Implementiere** die in `AGENTS.md` und `docs/` spezifizierte LEGO-Inventur-App; es handelt sich nicht um eine Aufforderung, weitere Spezifikationen zu schreiben.

## Ziel

Ein echtes, dauerhaftes Web-Tool zum Zählen von LEGO 75978 (und später anderen Sets), mit einer einzigen Soll-Inventarliste und **fünf separat gespeicherten Ist-Zählbereichen** (Anleitungen 1–4 und Minifiguren). Erkenne **globale Fehlmengen und Überschüsse** pro Teilenummer/Farbe; biete Sortierung nach Farbe und den Filter **nur eine Farbe anzeigen**; sichere alles in PostgreSQL; liefere eine deutschsprachige UI mit großen +/− Buttons.

## Verbindliche Technik

- Entwickeln: Devcontainer auf Basis `compose.dev.yaml`; keine Host-Python-/Node-/Postgres-Installation.
- Produktion: `compose.yaml` startet Web, API, DB; einzig Web-Port an `127.0.0.1:8080` veröffentlicht; DB-Volume persistent.
- Backend: Python/FastAPI/SQLAlchemy/Alembic/PostgreSQL.
- Frontend: React/TypeScript/Vite; später durch Nginx ausgeliefert.
- Datenquelle: Rebrickable serverseitig mit API-Key oder CSV, Minifiguren ausdrücklich ohne Doppelzählung.
- Allgemeine Geschäfts- und Testregeln aus `docs/specs/03-business-rules.md` und `docs/specs/04-acceptance-tests.md`.

## Ausführung

1. Lies `README.md`, alle `docs/specs/`, `docs/architecture/`, `backend/AGENTS.md`, `frontend/AGENTS.md`.
2. Prüfe den Devcontainer/Compose und verbessere nötigenfalls die Konfiguration.
3. Arbeite `agent/phases/01-setup.md` bis `05-hardening.md` ab. **Nicht nach Planungsphase abbrechen.**
4. Erstelle `IMPLEMENTATION_STATUS.md` und aktualisiere ihn nach jedem Meilenstein mit ausgeführten Befehlen, Testergebnissen und offenen Punkten.
5. Falls Rebrickable-Zugangsdaten fehlen, baue CSV-Import und alle Features gegen explizite Demo-Fixtures. Echte LEGO-75978-Vollständigkeit erst nach erfolgreichem Import als geprüft kennzeichnen.
6. Am Ende liefere die wirklich ausführbaren Docker-Befehle, dokumentiere Funktionstests und bekannte Einschränkungen.

## Fertig-Kriterium

Nicht „fertig“ melden, bevor die End-to-End-Akzeptanzfälle grün sind und die Produktions-Compose-Konfiguration vom leeren Volume bis zur funktionierenden App getestet wurde.
