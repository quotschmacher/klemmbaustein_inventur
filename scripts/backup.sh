#!/usr/bin/env bash
set -euo pipefail

# Creates a portable PostgreSQL custom-format dump without exposing DB credentials.
root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root_dir"

backup_dir="$root_dir/backups"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
filename="lego-inventur-$(date -u +%Y%m%dT%H%M%SZ).dump"
target="$backup_dir/$filename"

docker compose exec -T db sh -ceu 'pg_dump --format=custom --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "$target"
chmod 600 "$target"
printf 'Backup erstellt: %s\n' "$target"
