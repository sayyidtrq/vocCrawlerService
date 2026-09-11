#!/usr/bin/env bash
set -Eeuo pipefail

trap 'echo "Deployment failed while running: $BASH_COMMAND" >&2' ERR

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

git fetch origin
git checkout dev-testing-proxy
git pull --ff-only origin dev-testing-proxy

docker compose build api crawl-worker
docker compose up -d --force-recreate api crawl-worker
docker compose ps

curl --fail-with-body -i http://127.0.0.1:8000/api/health
