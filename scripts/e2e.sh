#!/usr/bin/env bash
set -euo pipefail

# Runs Playwright against a new, isolated Compose project and leaves its volume intact.
root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root_dir"
project_name="klemmbaustein-inventur-e2e-$(date -u +%Y%m%d%H%M%S)"
compose=(docker compose -p "$project_name" -f compose.yaml -f compose.e2e.yaml)

"${compose[@]}" up -d --build
for _ in $(seq 1 45); do
  if curl -fsS http://localhost:18080/api/health > /dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS http://localhost:18080/api/health > /dev/null
docker compose -f compose.dev.yaml exec -T workspace sh -lc 'cd /workspace/frontend && PLAYWRIGHT_BASE_URL=http://host.docker.internal:18080 npx playwright test'
"${compose[@]}" down
printf 'E2E erfolgreich: isolierter Compose-Stack %s wurde geprüft; sein Datenvolume bleibt erhalten.\n' "$project_name"
