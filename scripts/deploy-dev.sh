#!/usr/bin/env bash
set -Eeuo pipefail

trap 'echo "Deployment failed while running: $BASH_COMMAND" >&2' ERR

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

git fetch origin
git checkout dev
git pull --ff-only origin dev

ENV_FILE=../.env
if ! grep -qE '^APIFY_API_TOKENS=.+' "$ENV_FILE" 2>/dev/null; then
  echo "WARNING: APIFY_API_TOKENS is missing or empty in .env." >&2
fi

if grep -qiE '^ANALYSIS_PROVIDER=jev$' "$ENV_FILE" 2>/dev/null \
  && ! grep -qE '^JEV_API_KEY=.+' "$ENV_FILE" 2>/dev/null; then
  echo "ERROR: JEV_API_KEY is required when ANALYSIS_PROVIDER=jev." >&2
  exit 1
fi

docker compose build --no-cache api crawl-worker
docker compose up -d --force-recreate redis api crawl-worker
docker compose ps

curl --fail-with-body -i http://127.0.0.1:8000/api/health
