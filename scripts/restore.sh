#!/usr/bin/env bash
set -euo pipefail

# Restores a custom dump only into a new, explicitly named, isolated database.
if [[ $# -ne 3 || "$1" != "--confirm" ]]; then
  echo "Verwendung: $0 --confirm BACKUP.dump ziel_restore_db" >&2
  exit 64
fi

backup=$2
target_db=$3
root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root_dir"

if [[ ! -f "$backup" ]]; then
  echo "Backup-Datei nicht gefunden: $backup" >&2
  exit 66
fi
if [[ ! "$target_db" =~ ^[a-zA-Z0-9_]+$ ]] || [[ ! "$target_db" =~ (restore|test) ]]; then
  echo "Zieldatenbank muss sicher benannt sein und 'restore' oder 'test' enthalten." >&2
  exit 64
fi

current_db=$(docker compose exec -T db sh -ceu 'printf %s "$POSTGRES_DB"')
if [[ "$target_db" == "$current_db" ]]; then
  echo "Restore in die laufende Produktionsdatenbank ist verboten." >&2
  exit 64
fi

if docker compose exec -T db sh -ceu "psql -U \"\$POSTGRES_USER\" -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname = '$target_db'\"" | grep -qx '1'; then
  echo "Zieldatenbank existiert bereits: $target_db. Sie wird nie überschrieben." >&2
  exit 65
fi

docker compose exec -T db sh -ceu "createdb -U \"\$POSTGRES_USER\" '$target_db'"
docker compose cp "$backup" "db:/tmp/restore.dump"
docker compose exec -T db sh -ceu "pg_restore --no-owner --no-privileges -U \"\$POSTGRES_USER\" -d '$target_db' /tmp/restore.dump && rm -f /tmp/restore.dump"
printf 'Backup sicher wiederhergestellt in separater Datenbank: %s\n' "$target_db"
