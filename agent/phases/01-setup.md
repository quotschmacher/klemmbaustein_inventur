# Phase 1 – Laufzeit, DB und Entwicklungsumgebung

1. Funktionierenden Devcontainer mit Python 3.12, Node 22, Git, Postgres-Client und Tooling prüfen; keine Host-Installationen.
2. Backend- und Frontend-Skelette samt lockfiles und Dockerfiles implementieren.
3. SQLAlchemy-Modelle + Alembic-Migrationen für das Datenmodell erstellen.
4. Compose-Produktion inkl. Healthchecks, Volume, Web-Reverse-Proxy, non-root, DB ready migrations, localhost-binding.
5. `README.md` mit überprüften Setup-Befehlen ergänzen.

**Done:** Containerstarts nach `docker compose up -d --build`, Healthcheck, Migrieren möglich; DB-Daten über Restart persistent; Frontend/API erreichbar (auch wenn UI zunächst minimal).
