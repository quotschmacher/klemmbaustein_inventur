#!/usr/bin/env bash
set -euo pipefail

# Runs every currently configured quality gate inside the development container.
root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root_dir"

docker compose -f compose.dev.yaml up -d --build
docker compose -f compose.dev.yaml exec -T workspace sh -lc "python -m pip install -e '/workspace/backend[dev]'"
docker compose -f compose.dev.yaml exec -T workspace sh -lc 'npm ci --prefix /workspace/frontend'
docker compose -f compose.dev.yaml exec -T workspace sh -lc 'cd /workspace/backend && ruff check . && pytest -p no:cacheprovider -q'
docker compose -f compose.dev.yaml exec -T workspace sh -lc 'npm test --prefix /workspace/frontend && npm run lint --prefix /workspace/frontend && npm run build --prefix /workspace/frontend'
