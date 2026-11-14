# Frontend-spezifische Agent-Regeln

Stack: React, TypeScript strict, Vite; Data-Fetching mit Query Cache; Testen mit Vitest + Testing Library, End-to-End mit Playwright.

- Deutschsprachig, Desktop-first, bedienbar per Maus und Tastatur; keine Farbkommunikation ohne Text.
- Teile-Zählzeile: Foto, Teil-ID, Name, Farbfeld+Farbname, Soll gesamt, Ist im Bereich, Ist gesamt, +/- Buttons, Direktmenge, globale Abweichung.
- Plus/Minus groß und flüssig; Buttons sichtbar fokussierbar; nach Click Fokus behalten, Screenreader-Beschriftung mit Teil-ID/Farbe.
- Farbfilter `Alle Farben` oder `Nur <Farbe>`; Filterung muss ALLE anderen Farben tatsächlich ausblenden. Sortierung nach Farbe/Name/Teilenummer; sichtbar ausgewählter Filter und Reset.
- Filter-/Sortierstatus darf über Wechsel des Zählbereichs nicht verloren gehen (URL-Query oder Einstellungen).
- Optimistisches UI nur mit sauberer Fehlerbehandlung/Rollback; Server-Antwort ist autoritativ. Keine verlustanfällige ausschließliche Speicherung in LocalStorage.
- Große Listen virtualisieren oder paginieren; Bilder lazy laden; `img` mit Alt-Text und sicherer Fallbackgrafik.
- „Noch nicht gezählt“ nicht „fehlt“ nennen, solange die Pflichtbereiche offen sind; Überschuss dagegen sofort sichtbar.
