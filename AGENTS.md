# Hermes Agent – Projektanweisungen (Root)

Du bist der Implementierungsagent für **Klemmbaustein Inventur**. Nutze `agent/START_HERE.md`, `docs/specs/*`, `docs/architecture/*`, `agent/phases/*` als verbindliche Anforderungen. **Sprache des Produkts und aller Nutzertexte: Deutsch.** Code/Bezeichner in Englisch. Fragen nur bei echten Blockern; sonst Entscheidungen im ADR dokumentieren.

## Arbeitsweise

1. Entwickle ausschließlich **innerhalb des Devcontainers**. Keine lokal installierten Python-/Node-/Postgres-Abhängigkeiten verlangen. Host benötigt nur Docker und für GUI-Devcontainer VS Code/kompatible IDE.
2. Arbeite **pro Sitzung genau eine Task** aus `agent/TASK_INDEX.md` ab; Phasen in `agent/phases/` bleiben als thematische Referenz; dokumentiere Fortschritt in `IMPLEMENTATION_STATUS.md` (Anforderung, Ergebnis, Tests, Blocker, nächste Schritte). Kein „fertig“ ohne Tests.
3. Schreibe zuerst Tests für fachliche Regeln: **Summe über alle Bereiche, Fehlmenge, Überschuss, 0-Grenze, Doppelzählung von Minifigs, Idempotenz, parallele Updates, abgeschlossene Bereiche**.
4. Nach jeder Task Lint, Typprüfung, Unit- und Integrationstests sowie bei UI-Phasen E2E ausführen. Fehler beheben; keine grünen Tests fingieren.
5. Datenbank-Änderungen nur durch **versionierte Alembic-Migrationen**, keine destructive resets ohne ausdrückliche Freigabe, keine Secrets im Git.
6. Wenn externe API nicht erreichbar ist, mit **synthetischen, klar als Testdaten gekennzeichneten Fixtures** weiterarbeiten. Behaupte nie, damit sei die echte Stückliste von 75978 validiert.
7. Keine unautorisierten Netzaufrufe/Datenübermittlungen aus dem Browser. API-Keys bleiben serverseitig.
8. Jede API mutiert die DB serverseitig; Menge nicht als autoritativen Wert im Frontend halten. Bilder lazy laden, Fallback zeigen.
9. Korrigiere Risiken im Datenmodell statt sie zu kaschieren (z. B. kein stillschweigendes Minifig-Doppelerfassen).

## Akzeptanzkriterien (verbindlich)

- `docker compose up -d --build` startet Web + API + PostgreSQL aus leerem persistentem Volume nach Migration, `http://localhost:8080` funktioniert.
- Zählstände bleiben nach Browserneustart und Containerneustart erhalten.
- 5 Startbereiche für 75978: Anleitung 1–4, Figuren. Weitere Bereiche beliebig anlegbar.
- Jede Position kann mit +1, −1 und Direkteingabe geändert werden; +1 auch oberhalb der Sollmenge; −1 nie unter 0.
- Sofortige Sichtbarkeit des **globalen** Überschusses pro Teilenummer+Farbe; fehlende Mengen erst nach Abschluss aller Pflicht-Zählbereiche als „Fehlteile“ deklarieren.
- Farbfilter: **nur eine gewählte Farbe anzeigen**, übrige ausblenden; sortieren und zurücksetzen; Einstellung über Bereichswechsel erhalten.
- Gleiche Teile aus mehreren Zählbereichen werden genau einmal aufsummiert, nicht überschrieben.
- PostgreSQL nur intern; alle Dateiexporte/Backups nachvollziehbar; Rebrickable-Schlüssel geheim.

## Priorität bei Konflikten

1. Sicherheit und korrekte Inventurregeln in `docs/specs/03-business-rules.md`.
2. `docs/specs/01-functional-requirements.md` und `docs/specs/04-acceptance-tests.md`.
3. Architektur-/API-/UI-Spezifikationen.
4. Freie technische Entscheidungen, wenn nicht spezifiziert.

## Nicht tun

- Keine fiktive Stückliste nach Bauanleitung annehmen.
- Kein „Teile fehlen“-Label, solange notwendige Erfassungen nicht abgeschlossen sind.
- Kein Blockieren der + Taste bei Sollmenge; Überschuss MUSS möglich sein.
- Keine eigenmächtige Zuordnung fehlender Teile zu einem Gebäude ohne Hinweis, dass es sich um eine manuelle Vermutung handelt.
- Kein blindes Importieren von Fragmentelementen, das zu Doppelzählung bei Figuren führt.

## Tokenlimit und Wiederaufnahme (verbindlich)

- Starte mit `agent/RESUME.md` sowie `agent/checkpoints/CURRENT.md`; Task-Index `agent/TASK_INDEX.md`.
- Maximal **eine Task pro Sitzung** bearbeiten; keinen Total-Neustart planen.
- Nach jeder Task/WIP `IMPLEMENTATION_STATUS.md` und `agent/checkpoints/CURRENT.md` aktualisieren; Tests und letzte Commits wahrheitsgemäß festhalten.
- Datenbank-Volumes nie für den Wiederanlauf löschen. Git sichert den Code, nicht das PostgreSQL-Volume.
