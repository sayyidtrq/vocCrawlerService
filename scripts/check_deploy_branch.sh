#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/check_deploy_branch.sh [branch]

Checks whether the current server checkout is safe to deploy:
  - must be inside a git repository
  - working tree must be clean
  - current branch must match the requested branch
  - local branch must not be ahead of or diverged from origin/<branch>

Examples:
  ./scripts/check_deploy_branch.sh main
  ./scripts/check_deploy_branch.sh codex/c1-crawl-instrumentation
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

TARGET_BRANCH="${1:-${DEPLOY_BRANCH:-$(git branch --show-current 2>/dev/null || true)}}"

if [[ -z "${TARGET_BRANCH}" ]]; then
  echo "[check] ERROR: branch is required when HEAD is detached." >&2
  usage >&2
  exit 2
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${REPO_ROOT}" ]]; then
  echo "[check] ERROR: not inside a git repository." >&2
  exit 2
fi
cd "${REPO_ROOT}"

CURRENT_BRANCH="$(git branch --show-current)"
REMOTE_REF="origin/${TARGET_BRANCH}"

echo "[check] repo    : ${REPO_ROOT}"
echo "[check] current : ${CURRENT_BRANCH}"
echo "[check] target  : ${TARGET_BRANCH}"

if [[ "${CURRENT_BRANCH}" != "${TARGET_BRANCH}" ]]; then
  echo "[check] ERROR: current branch is not target branch." >&2
  echo "[check] Run: git checkout ${TARGET_BRANCH}" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "[check] ERROR: working tree is not clean." >&2
  git status --short >&2
  exit 1
fi

git fetch origin "${TARGET_BRANCH}" --prune

if ! git rev-parse --verify --quiet "${REMOTE_REF}" >/dev/null; then
  echo "[check] ERROR: remote branch ${REMOTE_REF} does not exist." >&2
  exit 1
fi

LOCAL_SHA="$(git rev-parse HEAD)"
REMOTE_SHA="$(git rev-parse "${REMOTE_REF}")"
BASE_SHA="$(git merge-base HEAD "${REMOTE_REF}")"

echo "[check] local   : ${LOCAL_SHA}"
echo "[check] remote  : ${REMOTE_SHA}"

if [[ "${LOCAL_SHA}" == "${REMOTE_SHA}" ]]; then
  echo "[check] OK: branch is clean and already matches ${REMOTE_REF}."
  exit 0
fi

if [[ "${LOCAL_SHA}" == "${BASE_SHA}" ]]; then
  echo "[check] OK: branch is clean and can fast-forward to ${REMOTE_REF}."
  exit 0
fi

if [[ "${REMOTE_SHA}" == "${BASE_SHA}" ]]; then
  echo "[check] ERROR: local branch is ahead of ${REMOTE_REF}." >&2
  echo "[check] Push or move those commits to a review branch before deploy." >&2
  exit 1
fi

echo "[check] ERROR: local and remote branches diverged." >&2
echo "[check] Resolve manually before deploy." >&2
exit 1
