#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/deploy_server.sh [branch]

Deploys the crawler service from a git branch on the server:
  1. fetches origin/<branch>
  2. checks out the target branch when needed
  3. checks that the branch is safe
  4. fast-forwards from origin/<branch>
  5. builds api and crawl-worker images
  6. recreates api and crawl-worker
  7. verifies Docker status and /api/health

Examples:
  ./scripts/deploy_server.sh main
  ./scripts/deploy_server.sh codex/c1-crawl-instrumentation

Environment:
  DEPLOY_BRANCH      Default branch if no argument is passed.
  HEALTH_URL         Default: http://127.0.0.1:8000/api/health
  COMPOSE            Default: docker compose
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

TARGET_BRANCH="${1:-${DEPLOY_BRANCH:-$(git branch --show-current 2>/dev/null || true)}}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/health}"
COMPOSE="${COMPOSE:-docker compose}"

if [[ -z "${TARGET_BRANCH}" ]]; then
  echo "[deploy] ERROR: branch is required when HEAD is detached." >&2
  usage >&2
  exit 2
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${REPO_ROOT}" ]]; then
  echo "[deploy] ERROR: not inside a git repository." >&2
  exit 2
fi
cd "${REPO_ROOT}"

if [[ ! -x scripts/check_deploy_branch.sh ]]; then
  chmod +x scripts/check_deploy_branch.sh
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "[deploy] ERROR: working tree is not clean." >&2
  git status --short >&2
  exit 1
fi

echo "[deploy] fetching origin/${TARGET_BRANCH}"
git fetch origin "${TARGET_BRANCH}" --prune

if ! git rev-parse --verify --quiet "origin/${TARGET_BRANCH}" >/dev/null; then
  echo "[deploy] ERROR: remote branch origin/${TARGET_BRANCH} does not exist." >&2
  exit 1
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [[ "${CURRENT_BRANCH}" != "${TARGET_BRANCH}" ]]; then
  echo "[deploy] switching ${CURRENT_BRANCH:-detached} -> ${TARGET_BRANCH}"
  if git show-ref --verify --quiet "refs/heads/${TARGET_BRANCH}"; then
    git checkout "${TARGET_BRANCH}"
  else
    git checkout -b "${TARGET_BRANCH}" "origin/${TARGET_BRANCH}"
  fi
fi

echo "[deploy] checking ${TARGET_BRANCH}"
scripts/check_deploy_branch.sh "${TARGET_BRANCH}"

echo "[deploy] fast-forwarding ${TARGET_BRANCH}"
git pull --ff-only origin "${TARGET_BRANCH}"

echo "[deploy] building api and crawl-worker"
${COMPOSE} build api crawl-worker

echo "[deploy] recreating api and crawl-worker"
${COMPOSE} up -d --force-recreate api crawl-worker

echo "[deploy] compose status"
${COMPOSE} ps

echo "[deploy] health check: ${HEALTH_URL}"
curl --fail --show-error --silent --location "${HEALTH_URL}"
echo

echo "[deploy] OK: deploy finished."
