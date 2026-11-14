# Architecture Decision Records (initial)

## ADR-001 PostgreSQL

**Status:** beschlossen. PostgreSQL 16 bietet Constraints, robuste Transaktionen, einfache Docker-Nutzung. MySQL **nicht** zusätzlich anbieten; keine Dialektkomplexität ohne Nutzen.

## ADR-002 FastAPI + React/TypeScript

**Status:** beschlossen. Klare Trennung von Data/Business-Logic und flüssiger Zähloberfläche. Python 3.12 / Node 22 in Containern, nicht Host.

## ADR-003 Bereiche zählen Ist, nicht Soll

**Status:** beschlossen. Ein offizielles Set-Inventar, mehrere physische Bereiche. Fehlteile sind nur global belegbar, Nachbestellungs-Zielbeutel ist manuelle organisatorische Angabe.

## ADR-004 Figuren atomar expandieren

**Status:** beschlossen. Figuren-Kontrollliste darf nicht zusätzlich auf die Einzelteile aufgeschlagen werden. Pflichtinventar wird aus normalem Set-Bestand + genau einer Figuren-Expansion gebildet; Spare-Auswertung getrennt.

## ADR-005 Eventlog + Idempotenz

**Status:** beschlossen. DB speichert Deltaevents und aktuellen Stand; wiederholte Netzanforderungen dürfen keinen doppelten Count erzeugen.

## ADR-006 Docker-only Entwicklung und Betrieb

**Status:** beschlossen. Devcontainer `workspace+db`; Produktions-Compose `web+api+db`. Bind 127.0.0.1, persistentes pgdata.

## ADR-007 Kein automatisches Haus-Missing

**Status:** beschlossen. Es gibt keine zuverlässige Haus-Soll-Liste. Fehlteile nicht per Haus behaupten; Nutzer kann Beutel für Ersatz manuell festlegen.
