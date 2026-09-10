#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.staging-1123.yml"
ENV_FILE="$ROOT_DIR/.env.staging-1123"
PROJECT="voc-staging-1123"
EXPECTED_BRANCH="${EXPECTED_BRANCH:-staging}"
INITIAL=false

if [[ "${1:-}" == "--initial" ]]; then
  INITIAL=true
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--initial]" >&2
  exit 2
fi

cd "$ROOT_DIR"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE; run scripts/bootstrap-staging-1123.sh first." >&2
  exit 1
fi
if [[ "$(stat -c '%a' "$ENV_FILE")" != "600" ]]; then
  echo "$ENV_FILE must have mode 600." >&2
  exit 1
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [[ "$CURRENT_BRANCH" != "$EXPECTED_BRANCH" ]]; then
  echo "Expected branch '$EXPECTED_BRANCH', found '$CURRENT_BRANCH'." >&2
  exit 1
fi
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "Tracked files are dirty; refusing to deploy." >&2
  exit 1
fi

git fetch origin "$EXPECTED_BRANCH"
git merge-base --is-ancestor HEAD "origin/$EXPECTED_BRANCH" || {
  echo "Local branch contains commits absent from origin/$EXPECTED_BRANCH." >&2
  exit 1
}
git pull --ff-only origin "$EXPECTED_BRANCH"

docker compose --env-file "$ENV_FILE" -p "$PROJECT" -f "$COMPOSE_FILE" config --quiet
docker compose --env-file "$ENV_FILE" -p "$PROJECT" -f "$COMPOSE_FILE" build
docker compose --env-file "$ENV_FILE" -p "$PROJECT" -f "$COMPOSE_FILE" up -d --force-recreate

if [[ "$INITIAL" == true ]]; then
  docker compose --env-file "$ENV_FILE" -p "$PROJECT" -f "$COMPOSE_FILE" exec -T api \
    python -m scripts.manage_company create --name "OneBox Staging 1.123"
fi

for _ in {1..30}; do
  if curl --fail --silent --show-error http://127.0.0.1:8001/api/health >/dev/null; then
    break
  fi
  sleep 2
done
curl --fail-with-body http://127.0.0.1:8001/api/health
docker compose --env-file "$ENV_FILE" -p "$PROJECT" -f "$COMPOSE_FILE" ps

if [[ "$INITIAL" == true ]]; then
  echo
  echo "Verify the company id above is 1, then issue the OneBox token:"
  echo "docker compose --env-file .env.staging-1123 -p $PROJECT -f docker-compose.staging-1123.yml exec api python -m scripts.manage_api_client issue --company-id 1 --name onebox-staging-1.123 --scope crawl:enqueue --scope crawl:read --expires-days 90"
fi
