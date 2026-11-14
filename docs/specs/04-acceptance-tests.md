# Akzeptanztests (automatisiert implementieren)

Alle Beispiele **synthetisch**, sie sind keine echten 75978-Stückzahlen. Nutze ein Fixture mit folgenden Pflichtpositionen:
- Teil `3001`, Farbe 72, Soll 10
- Teil `3001`, Farbe 5, Soll 4 (gleicher Stein, andere Farbe)
- Teil `3069b`, Farbe 72, Soll 3
- Spares: `3001`, Farbe 72, Soll 2 (optional, nicht zur Pflichtzählung addieren)
- 5 Pflichtbereiche `A1,A2,A3,A4,FIG`.

| ID | Szenario | Erwartung |
|---|---|---|
| A01 | In A1 4x +1 `3001/72`; A2 6x +1 | Global 10, Defizit 0, Überschuss 0 |
| A02 | In A3 +1 gleicher Stein | Global 11, **Überschuss 1 sofort** |
| A03 | −1 in A3 | Global 10, Überschuss verschwindet |
| A04 | −1 bei Menge 0 | Fehler, Menge bleibt 0 |
| A05 | A1 2+ A2 3, andere Bereiche offen | Vorläufig offen 5; **nicht** bestätigtes Fehlteil |
| A06 | alle Pflichtbereiche abgeschlossen, global 8 bei Soll 10 | Bestätigtes Fehlteil 2 |
| A07 | Bereich wieder öffnen | Fehlmenge erneut nur vorläufig |
| A08 | doppelte HTTP-Anfrage mit gleicher mutation UUID | genau eine Zähländerung |
| A09 | zwei parallele +1 mit unterschiedlichen UUIDs | beide zählen; kein Lost Update |
| A10 | Direktmenge mit veralteter revision | 409; kein Überschreiben |
| A11 | Filter nur Farbe 72 | keine Position mit Farbe 5 in UI/API |
| A12 | Wechsel A1 nach A2 und zurück bei Farbe 72 | Filter bleibt erhalten, Mengen korrekt |
| A13 | `3001/72` und `3001/5` | getrennte Zähler und Sollwerte |
| A14 | Minifig-Bauteil aus Expanded-Inventory | einmal im Soll; Figurencheckliste erhöht Soll nicht |
| A15 | Spare erwartet 2, 0 gefunden | Pflichtstatus bleibt vollständig, Spare separat offen |
| A16 | Überzählige Teile in anderem Set nicht enthalten | als Fremdteil, nicht als Pflichtinventar |
| A17 | Container/Browser neu starten | Werte in Postgres unverändert |
| A18 | Export CSV/JSON; Backup -> neues Projekt importieren | identische Summen, event IDs valide |
| A19 | Rebrickable liefert Page 1 + Page 2 | beide Seiten enthalten, kein Teilverlust |
| A20 | Import liefert API Fehler nach Page 1 | kein als validiert aktiver Snapshot |
| A21 | BrickLink Mapping fehlt für ein Teil | kein falsches XML, Warnliste |
| A22 | Nachbestellung `ordered` oder `received` | keine Erhöhung der Ist-Menge |
| A23 | Nachbestellung explizit eingebucht | exakt eine +n-Buchung, Zielbeutel sichtbar |
| A24 | unbekanntes Teil als Extra | eigener Fremdteilstatus |
| A25 | 20 Sessionwechsel / Farbfiler plus große Liste | keine verlorenen Zählungen |
| A26 | `/` App erreichbar ohne installierte Node/Python DB auf Host | Devcontainer/Compose erfüllen Voraussetzung |

## Testpyramide

- Backend: pure Berechnungs-Unit-Tests, PostgreSQL-Integrationstests für Mutationen/Indizes/Transaktionen, API-Contract-Tests.
- Frontend: Komponenten- und Filtertests mit Testing Library, Keyboard-Fokus.
- E2E: Playwright innerhalb von Docker, realistische Nutzerreise 5 Bereiche, Neustart, Vorläufig-/Endgültig-Status.
- Backup-Restore-/Migrations-Test mit getrenntem DB-Volume; keine produktiven Daten überschreiben.

## Minimale Abnahme-Demo

Mit synthetischem 10er-Soll: 4 in A1, 6 in A2, 1 in A3 → Überschuss +1; −1 → ausgeglichen; 1 aus A2 wegnehmen → vorläufig 1; restliche Pflichtbereiche abschließen → bestätigte Fehlmenge 1; Farbfilter auf Farbe 72 → nur diese; Seite neuladen → alle Daten erhalten.
