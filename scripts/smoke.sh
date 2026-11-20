#!/usr/bin/env bash
set -euo pipefail

# Production Compose smoke test: public routes and persisted project list survive restart.
root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root_dir"

tmp_dir=${TMPDIR:-/tmp}
before="$tmp_dir/klemmbaustein-inventur-projects-before.json"
after="$tmp_dir/klemmbaustein-inventur-projects-after.json"

docker compose up -d --build
curl -fsS http://localhost:8080/ > /dev/null
curl -fsS http://localhost:8080/api/health > /dev/null
curl -fsS 'http://localhost:8080/api/v1/projects?include_archived=true' > "$before"
docker compose restart api web
for _ in $(seq 1 30); do
  if curl -fsS http://localhost:8080/api/health > /dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS http://localhost:8080/api/health > /dev/null
docker compose ps
curl -fsS 'http://localhost:8080/api/v1/projects?include_archived=true' > "$after"
cmp --silent "$before" "$after"
printf 'Smoke-Test erfolgreich: öffentliche Routen erreichbar, Projektliste nach Neustart unverändert.\n'
