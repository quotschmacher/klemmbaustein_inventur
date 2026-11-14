# Phase 5 – Härtung und Betrieb

1. API-Validierung, Importgrenzen, Secrets, sichere Defaults, CORS, Rate-Limit, Logging ohne Geheimnisse.
2. DB-Backup/Restore dokumentiert und als automatisierbares Skript testbar (kein Verlust beim Rebuild).
3. Fehlerfälle bei API-Ausfall, fehlerhaften Bildern, unterbrochenen Requests; Retry mit Idempotenz.
4. UI Performance mit >1000 Inventarpositionen, Accessibility, responsive Grundbedienung.
5. Produktivtest: leeres Volume -> Import -> Zählen -> Neustart -> Zählstände identisch -> Export.
6. `IMPLEMENTATION_STATUS.md`, README und Betriebshandbuch aktualisieren.

**Done:** Alle in `docs/specs/04-acceptance-tests.md` definierten Muss-Kriterien nachweislich geprüft. Restpunkte explizit dokumentiert.
