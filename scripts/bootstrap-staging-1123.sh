#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.staging-1123"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-postgresql}"
DB_NAME="voc_staging_1123"
DB_USER="voc_staging_1123"

dotenv_quote() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '"%s"' "$value"
}

if [[ -e "$ENV_FILE" ]]; then
  echo "$ENV_FILE already exists; refusing to replace secrets." >&2
  exit 1
fi
if ! docker inspect "$POSTGRES_CONTAINER" >/dev/null 2>&1; then
  echo "PostgreSQL container '$POSTGRES_CONTAINER' was not found." >&2
  exit 1
fi

read -r -p "OneBox staging service email: " ONEBOX_SVC_EMAIL
read -r -s -p "OneBox staging service password: " ONEBOX_SVC_PASSWORD
printf '\n'
if [[ -z "$ONEBOX_SVC_EMAIL" || -z "$ONEBOX_SVC_PASSWORD" ]]; then
  echo "OneBox service credentials are required." >&2
  exit 1
fi

DB_PASSWORD="$(openssl rand -hex 24)"
CURSOR_SECRET="$(openssl rand -hex 32)"
JWT_SECRET="$(openssl rand -hex 32)"
TOKEN_PEPPER="$(openssl rand -hex 32)"

if docker exec "$POSTGRES_CONTAINER" psql -U postgres -tAc \
  "SELECT 1 FROM pg_roles WHERE rolname = '$DB_USER'" | grep -q 1; then
  echo "Database role '$DB_USER' already exists; aborting to avoid changing its password." >&2
  exit 1
fi
if docker exec "$POSTGRES_CONTAINER" psql -U postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1; then
  echo "Database '$DB_NAME' already exists; aborting to avoid reusing unknown state." >&2
  exit 1
fi

docker exec "$POSTGRES_CONTAINER" psql -U postgres -v ON_ERROR_STOP=1 \
  -c "CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASSWORD'"
docker exec "$POSTGRES_CONTAINER" createdb -U postgres -O "$DB_USER" "$DB_NAME"

umask 077
printf '%s\n' \
  'APP_ENV=staging' \
  'APP_NAME=VoC Crawler Staging 1.123' \
  'LOG_LEVEL=INFO' \
  "DATABASE_URL=postgresql+psycopg2://$DB_USER:$DB_PASSWORD@postgresql:5432/$DB_NAME" \
  "INTEGRATION_CURSOR_SECRET=$CURSOR_SECRET" \
  "JWT_SECRET_KEY=$JWT_SECRET" \
  "SERVICE_TOKEN_PEPPER=$TOKEN_PEPPER" \
  'REVIEW_SOURCE_MODE=selenium' \
  'SELENIUM_HEADLESS=false' \
  'SELENIUM_DEFAULT_TARGET_REVIEWS=10' \
  'SELENIUM_MAX_TARGET_REVIEWS=300' \
  'ONEBOX_BASE_URL=https://staging.onebox.co.id/1_123_0' \
  "ONEBOX_SVC_EMAIL=$(dotenv_quote "$ONEBOX_SVC_EMAIL")" \
  "ONEBOX_SVC_PASSWORD=$(dotenv_quote "$ONEBOX_SVC_PASSWORD")" \
  'ONEBOX_SITE_ID=169' \
  'ONEBOX_COMPANY_ID=1' \
  'ONEBOX_WORKLIST_PATH=/api/VocWorklist' \
  'STAGING_API_PORT=8001' >"$ENV_FILE"
chmod 600 "$ENV_FILE"

unset ONEBOX_SVC_PASSWORD DB_PASSWORD CURSOR_SECRET JWT_SECRET TOKEN_PEPPER
echo "Created an isolated database and $ENV_FILE (mode 600)."
echo "Next: run scripts/deploy-staging-1123.sh --initial."
