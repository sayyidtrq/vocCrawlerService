#!/usr/bin/env bash
set -Eeuo pipefail

trap 'echo "Deployment failed while running: $BASH_COMMAND" >&2' ERR

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

git fetch origin
git checkout apify-migration
git pull --ff-only origin apify-migration

# apify_api_tokens defaults to an empty list (app/config.py) so a missing
# token does NOT crash the container at startup - it just makes every crawl
# fail with every account exhausted immediately. Catch that here instead of
# in a confusing 3am crawl-job failure.
if ! grep -qE '^APIFY_API_TOKENS=.+' ../.env 2>/dev/null; then
  echo "WARNING: APIFY_API_TOKENS is missing or empty in .env - crawls will" >&2
  echo "fail immediately with every Apify account reported as exhausted." >&2
fi

docker compose build api crawl-worker
docker compose up -d --force-recreate api crawl-worker
docker compose ps

curl --fail-with-body -i http://127.0.0.1:8000/api/health
