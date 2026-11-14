# Funktionale Anforderungen

## P0 – Muss

**FR-001 Setimport:** LEGO-ID wie `75978-1` importieren (serverseitige Rebrickable API oder CSV); Quellenstand, Importzeit und Prüfergebnis speichern. Alle Paginationsseiten. Echte Teilebilder bzw. Bildlinks und Farben wenn verfügbar. Ohne zuverlässigen Import keine „vollständig“-Aussage.

**FR-002 Bereiche:** Beim neuen Projekt für 75978 die Bereiche `Anleitung 1`, `Anleitung 2`, `Anleitung 3`, `Anleitung 4`, `Minifiguren` anlegen. Umbenennen, sortieren, weitere anlegen; Archiv statt destruktives Löschen bereits befüllter Bereiche. Jeder Bereich `in_progress`/`completed`, abschließbar und wieder öffnend mit Auditlog. Pflichterfassungen konfigurierbar, standardmäßig alle fünf.

**FR-003 Zählen:** Pro Position plus/minus in Einerschritten, Direkteingabe, optional +5/+10, Undo letzter Aktion. Keine unter-0 Mengen; **keine obere Schranke** bei Sollmenge. Sofortige Datenbankpersistenz mit idempotenter Mutation und Rückmeldung. Stabil bei Browserrefresh.

**FR-004 Globale Summen:** Gesamt-Ist = Summe aller aktiven Bereiche pro Teil+Farbe+Inventarklasse; fehlend = max(0, Soll−Ist), überschüssig = max(0, Ist−Soll). Überschuss global sofort sichtbar, Fehlmenge vor Abschluss nur als „offen/vorläufig“.

**FR-005 Ansicht und Filter:** Textsuche nach Teilnummer/Name, sortieren nach Farbe, Kategorie, Name, Nummer oder Abweichung; Dropdown „Alle Farben“ / „Nur [gewählte Farbe]“. **Bei Single-Color-Modus keine andersfarbigen Zeilen rendern.** Farbsymbol plus Name (barrierearm). Filter bleibt beim Wechsel der Zählbereiche bestehen. Zählergebnisse verlieren durch Filter nie ihren Zustand.

**FR-006 Status:** Projektübersicht mit 5 Bereichen und Anzahl erfasster Positionen (nicht vermeintlicher Anteil „fertiger“ Steine), offenen Pflichtbereichen, globalem Überschuss, vorläufigem Rest, nach Abschluss echten Defiziten. Expliziter „Bereich abgeschlossen“ Dialog.

**FR-007 Extras:** Fremdteil-/Nicht-in-Set-Funde per freier Eingabe erfassen (Teilnummer/Farbe/Menge), getrennt als „nicht im Inventar“, ohne Sollmenge und nie als negative Menge.

**FR-008 Figuren:** Figurenbestandteile als atomare Teile zählen, einmal in Soll aufnehmen; Figuren-Checkliste als separate strukturierte Prüfung mit Figuranzahl und Zubehör ohne zusätzliche additive Stückzahlen. Ersatzteile als `spare` getrennt auswerten, nicht für Pflicht-Vollständigkeit voraussetzen.

**FR-009 Fehlteile/Überschüsse:** Fehlteile- und Überschusslisten mit Farben und Bildern, den fünf Ist-Beiträgen, Status, Export. Überschuss auch bei 1 über Soll. Möglichkeit falsch zugeordnete Teile manuell umzutragen, nachvollziehbar.

**FR-010 Nachbestellung:** Fehlteilpositionen manuell Haus/Beutel zuordnen, Bestellstatus und tatsächlichen Eingang nachhalten. Keine automatische unbelegte Gebäude-Zuordnung. Ersatz erst bei realem Eingang/Zählen in die Ist-Menge einbeziehen; keine doppelte Buchung.

**FR-011 Sicherung:** PostgreSQL-Volume, exportierbares JSON-Projektbackup (Schemas/versioniert), CSV-Export Inventar/Zählungen/Fehlteile, DB-Backup-Anleitung. Import/Restore validieren, nie stillschweigend überschreiben.

**FR-012 Docker:** Devcontainer komplett; fertige Anwendung mit `docker compose up -d --build`; nur `127.0.0.1:8080` veröffentlicht; persistentes DB-Volume; Restart/Upgrade ohne Datenverlust.

## P1 – Soll

- BrickLink Wanted-List XML mit validiertem Teil-/Farb-Mapping; nicht exportierbare Positionen separat auflisten.
- Tastatur-Shortcuts (`+`, `-`) im fokussierten Zählbereich ohne Kollision mit Texteingaben.
- Drag? Nein; bevorzugt einfache mobile Grundansicht und Druckbericht je Beutel.
- Optional ausgewählte Farbe beim Bereichswechsel, QR/Labeldruck erst später.

## P2 – Später

- Mehrbenutzerfähigkeit mit Authentifizierung/Versionskonflikten, Offline-PWA, automatisierte Bauabschnittszuordnung, Kamerascans.
