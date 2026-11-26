#!/usr/bin/env bash
# Redeploy crawler staging: compose bawaan + .env di checkout ini.
# Untuk stack terpisah (.env.staging-1124) pakai scripts/deploy-staging-1124.sh.
set -Eeuo pipefail

trap 'echo "[deploy] failed while running: $BASH_COMMAND" >&2' ERR

BRANCH="${DEPLOY_BRANCH:-staging}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8001/api/health}"
HEALTH_WAIT_SECONDS="${HEALTH_WAIT_SECONDS:-180}"

cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

# Salah .env di branch ini = kunci/DB dev terbawa ke staging.
if ! grep -Eq '^APP_ENV[[:space:]]*=[[:space:]]*"?staging"?[[:space:]]*$' .env 2>/dev/null; then
  echo "[deploy] .env must exist and set APP_ENV=staging." >&2
  exit 1
fi
if [[ "$(git branch --show-current)" != "$BRANCH" ]]; then
  echo "[deploy] expected branch '$BRANCH', found '$(git branch --show-current)'." >&2
  exit 1
fi
# File untracked (.env, docker-compose.override.yml) tidak dihitung.
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "[deploy] tracked files are dirty; refusing to deploy." >&2
  exit 1
fi

git fetch origin "$BRANCH"
git merge-base --is-ancestor HEAD "origin/$BRANCH" || {
  echo "[deploy] local $BRANCH has commits absent from origin/$BRANCH." >&2
  exit 1
}
git pull --ff-only origin "$BRANCH"
echo "[deploy] deploying $(git log --oneline -1)"

docker compose build api crawl-worker
docker compose up -d --force-recreate api crawl-worker

# api menjalankan migrasi Alembic dulu; tunggu sampai benar-benar sehat.
deadline=$((SECONDS + HEALTH_WAIT_SECONDS))
until curl --fail --silent --show-error "$HEALTH_URL" >/dev/null 2>&1; do
  if ((SECONDS >= deadline)); then
    echo "[deploy] api not healthy after ${HEALTH_WAIT_SECONDS}s; recent log:" >&2
    docker compose logs --tail=40 api >&2
    exit 1
  fi
  sleep 3
done
curl --fail-with-body "$HEALTH_URL"
echo

docker compose ps
running="$(docker compose ps --status running --services)"
if ! grep -qx crawl-worker <<<"$running"; then
  echo "[deploy] crawl-worker is not running; recent log:" >&2
  docker compose logs --tail=40 crawl-worker >&2
  exit 1
fi
echo "[deploy] OK"
