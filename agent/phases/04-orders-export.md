# Phase 4 – Nachbestellung, Beutel und Export

1. Fehlteile nur bei abgeschlossenen Pflichtzählungen als bestellreife Defizite darstellen; vorläufige Differenz klar kennzeichnen.
2. Fehlteil-Positionen/Beschaffungsstatus `planned, ordered, received, packed` mit optionaler manueller Zielbeutel-Zuordnung.
3. CSV- und JSON-Sicherung, CSV-Export der Fehlmengen mit Mappings.
4. BrickLink Wanted-List XML nur für verlässlich gemappte Teil- und Farb-IDs; ungemappte Positionen separat warnen.
5. Zuordnung zu einem Haus **nicht** als belegte Soll-Position ausgeben, sondern als Nutzerentscheidung.

**Done:** End-to-End: fünfte Erfassung fertig, fehlende Teile exportieren, Nachbestellungen zuordnen, beim tatsächlichen Einpacken zählen, globalen Sollabgleich aktualisieren.
