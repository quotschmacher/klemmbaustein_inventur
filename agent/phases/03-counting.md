# Phase 3 – Zählen, Übersicht und Farbfilter

1. CRUD Zählbereiche und Status `in_progress` / `completed`.
2. +1, −1, Direkteingabe und serverseitiges idempotentes Eventlog inkl. atomarer Updates.
3. Aggregierte Soll-/Ist-/Fehl-/Überschusswerte je `part_num+color_id`.
4. UI: schnelle Suche, Farbe sortieren, **nur eine Farbe anzeigen**, Farbauswahl ohne Reset bei Bereichswechsel.
5. Überschuss sofort markieren, noch nicht gezählte Mengen erst final als fehlend ausweisen.
6. Integrationstests für Retry, Parallelität und Race Conditions.

**Done:** Alle Akzeptanzfälle A01–A14 aus `04-acceptance-tests.md` grün.
