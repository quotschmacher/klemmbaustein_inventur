# UI/UX – Desktop-Zähloberfläche

## Navigation

Seitenleiste: Projekte -> Projekt 75978 -> Übersicht -> Anleitung 1/2/3/4 -> Figuren -> Fehlteile -> Überschüsse -> Bestellungen -> Datenexport/Backup.

## Zählliste

In jeder Zeile: kleines Foto (lazy), Teilenummer, Name, **Farbplättchen plus Farbtext**, erwartete Pflichtmenge im gesamten Set, gezählte Menge **im ausgewählten Bereich**, globale gezählte Menge, +/- Buttons, optional Zahleneingabe, globale Abweichung. Rot/„Überschuss +3“ bei zu viel; „Vorläufig offen 3“ bevor alle Bereiche fertig sind. Fußnote: *Die Sollmenge gilt für das ganze Set, nicht pro Haus.*

### Filter- und Sortierleiste (P0)

- Suchfeld (Teilenummer, Name), Farb-Dropdown mit Eintrag „Alle Farben“ und pro vorhandener Farbe „Nur: [Name]“.
- Wenn `selectedColorId != null`, render/API-Ergebnis enthält **ausschließlich** Teile mit **genau dieser** Farb-ID. Such-/Statusfilter werden zusätzlich konjunktiv angewendet. Alle anderen Farben werden **ausgeblendet**, nicht ausgegraut.
- Sortieroptionen: Farbe A–Z (Default), Farbgruppe -> Teilname -> Teilnummer, Teilname, Teilenummer, Sollmenge und Abweichung.
- Button „Filter zurücksetzen“; ausgewählte Farbe als Chip anzeigen; Farbnamen und Farbfelder für Unterscheidung nutzen. Filter bleibt beim Tabwechsel gespeichert (Query-String oder UI-Setting), Zählergebnisse aus DB.
- Filtern darf nicht versehentlich auf Teile eines anderen Sets oder auf zusätzliche `spare`-Positionen ausgeweitet werden.
- Ziel: nach Farbe sortierte Schraub-/Steinhaufen bequem abzählen. Tastatur-`+` / `-` optional bei fokussierter Zeile.

## Bereichsübersicht

Jedes Haus hat Name, Zählstatus, Anzahl berührter Inventarpositionen, letzte Änderung, Buttons „Fortsetzen“, „Abschließen“, „Wieder öffnen“. Figuren eigener Bereich, **aber dieselbe atomare Soll-Liste**. Vor dem Abschließen Warnung, dass kein Soll pro Haus bekannt ist; „Abgeschlossen“ bedeutet **physisch fertig erfasst/verpackt**, nicht „pro Haus vollständig“.

## Gesamtübersicht

Drei separate Hinweise: „Noch offene Zählbereiche“, „Aktueller globaler Überschuss“, „Vorläufige Differenz / bestätigte Fehlteile“. Farbe/Zustandsanzeige mit Text. Filter nach Farbe auch in Fehl-/Überschussansicht. Einzelner Teil zeigt Beiträge je Haus (z. B. 5+10+2+3+0) plus Soll und Ergebnis.

## Nachbestellung

Zeile: Teilname, Farbcode/-name, fehlende Menge, Bestellmenge, Quelle, Status, freiwilliger Zielbeutel. Ein kleines Warnsymbol erläutert „Zielbeutel ist eine manuelle Zuordnung, nicht die automatisch ermittelte Ursache“. Nach Eingang nur mit expliziter Buchung in Bereich zählen.

## Barrierearmut/Performance

Mindestens WCAG AA orientiert (Kontrast, sichtbarer Fokus, Tastaturbedienung, Textalternativen), Buttons mit `aria-label="+1 [Teil] [Farbe]"`, Eingabevalidierung, Hinweise nach Serverfehler. >1000 Zeilen performant (Pagination/Virtualisierung), Bilder mit Fallback. Keine rein farblichen Markierungen; Schrift gut lesbar am Desktop.
