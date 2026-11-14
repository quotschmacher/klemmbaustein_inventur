# Hermes Agent im Devcontainer ausführen

Der **Host** benötigt Docker Desktop/Engine und eine kompatible IDE (z. B. VS Code mit Dev Containers). Die Coding-Tools, Python, Node und Postgres laufen im Container. Das Hermes-CLI selbst kann ebenfalls **im Devcontainer** laufen.

## Vorgehensweise

1. VS Code -> Ordner öffnen -> „Dev Containers: Reopen in Container“.
2. In einem Terminal **innerhalb des Containers** verifizieren: `python --version`, `node --version`, `psql --version`.
3. Falls `hermes` noch nicht vorhanden ist: offiziellen Hermes-Installer **im Devcontainer-Terminal** ausführen. Anleitung: https://hermes-agent.nousresearch.com/docs/getting-started/installation/ . Der vom Anbieter dokumentierte Installationsweg ist:

   ```bash
   curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
   ```

   Installation aus dem Internet nur nach Prüfung/Vertrauen in die offizielle Quelle. Hermes kann zusätzliche Laufzeittools in das Container-Home installieren. Prüfe die aktuell gültigen Voraussetzungen.
4. `hermes` im Projektverzeichnis `/workspace` starten; Modell-Login bzw. API-Konfiguration **interaktiv im Container**, keine Keys in Git/Chats. Hermes lädt projektlokal `AGENTS.md`; lies manuell den Startauftrag `agent/START_HERE.md` und gib ihn an Hermes.
5. Wenn Devcontainer neu erstellt wird, ist ein nicht persistierter Hermes-CLI-Installationsstand möglicherweise erneut einzurichten. Der **Projektcode und die Postgres-Daten** bleiben auf dem Host-Mount bzw. im benannten DB-Volume. Für die weitere Entwicklung kann Hermes später reproduzierbar in einem separaten Tooling-Image gepinnt werden – keine Zugangsdaten in Images einbrennen.

Hermes auf dem Host ist **nicht** erforderlich, wenn es im Devcontainer installiert wurde. Das vorliegende Paket enthält die Anweisungen und Infrastruktur, **nicht** die Hermes-Binärdatei oder einen fertig installierten Agenten.
