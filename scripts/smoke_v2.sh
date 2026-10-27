#!/usr/bin/env bash
# Smoke test for the deployed stateless v2 API (ADR-0006). Needs curl and jq.
#
#   CRAWLER=https://your-host scripts/smoke_v2.sh <google_place_id>
#
# Optional env: TOKEN (else prompted, hidden), SITE_ID (default 0, a label only),
#   MAX_REVIEWS (default 5, max 100), PROVIDER (default jev), POLL_SECONDS (default 300),
#   TAXONOMY_FILE (a OneBox taxonomy body as JSON; adds taxonomy to the analysis and runs reply-suggestion).
# Costs one small Apify run and one analysis call. Exit 0 = every check passed.
set -uo pipefail

PLACE_ID="${1:-${PLACE_ID:-}}"
: "${CRAWLER:?set CRAWLER=https://your-host}"
[ -n "$PLACE_ID" ] || { echo "usage: CRAWLER=https://host $0 <google_place_id>" >&2; exit 2; }
command -v jq >/dev/null || { echo "jq is required" >&2; exit 2; }
if [ -z "${TOKEN:-}" ]; then read -r -s -p "CRAWLER_API_TOKEN: " TOKEN; echo; fi
SITE_ID="${SITE_ID:-0}"; MAX_REVIEWS="${MAX_REVIEWS:-5}"; PROVIDER="${PROVIDER:-jev}"
[ "$MAX_REVIEWS" -ge 1 ] && [ "$MAX_REVIEWS" -le 100 ] || { echo "MAX_REVIEWS must be 1..100 (the script reads one page)" >&2; exit 2; }
KEY="smoke-$(date +%s)"
BASE="${CRAWLER%/}/api/integration/v2"
PASS=0; FAIL=0; CODE=000; BODY=""

why() { jq -r 'select(.error) | "        -> \(.error.code): \(.error.message)"' <<<"$BODY" 2>/dev/null || true; }
ok() { PASS=$((PASS + 1)); printf '  ok    %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  FAIL  %s\n' "$1"; why; }
check() { if [ "$2" = "$3" ]; then ok "$1 ($3)"; else bad "$1: expected $3, got $2"; fi; }
finish() { printf '\npassed %s, failed %s\n' "$PASS" "$FAIL"; exit $((FAIL > 0)); }
val() { jq -r "$1" <<<"${2:-$BODY}" 2>/dev/null; }

# api METHOD PATH [JSON_BODY] [IDEMPOTENCY_KEY] -> sets CODE and BODY
api() {
  local method=$1 path=$2 data=${3:-} idem=${4:-} out
  local args=(-s -m 120 -X "$method" -H "Authorization: Bearer $TOKEN" -H "X-Request-ID: $KEY" "$BASE$path")
  [ -n "$data" ] && args+=(-H "Content-Type: application/json" -d "$data")
  [ -n "$idem" ] && args+=(-H "Idempotency-Key: $idem")
  if out=$(curl "${args[@]}" -w $'\n%{http_code}'); then CODE=${out##*$'\n'}; BODY=${out%$'\n'*}; else CODE=000; BODY=""; fi
}

echo "1. auth ($BASE)"
code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$BASE/audit/summary")
check "no token is rejected" "$code" 401
api GET "/audit/summary?site_id=$SITE_ID"
check "token is accepted" "$CODE" 200
[ "$CODE" = 200 ] || { echo "stop: fix auth first (503 = CRAWLER_API_TOKEN unset on the server)"; finish; }

echo "2. start crawl (backfill, $MAX_REVIEWS reviews, place $PLACE_ID)"
START=$(jq -n --argjson s "$SITE_ID" --arg p "$PLACE_ID" --argjson m "$MAX_REVIEWS" \
  '{site_id: $s, targets: [{place_id: $p}], mode: "backfill", max_reviews: $m}')
api POST /crawls "$START" "$KEY"
check "start accepted" "$CODE" 202
CRAWL_ID=$(val '.data.runs[0].crawl_id // empty')
check "run status" "$(val '.data.runs[0].status // "?"')" started
if [ -z "$CRAWL_ID" ]; then val '.data.runs[0].error // empty'; finish; fi

echo "3. poll until done"
deadline=$(( $(date +%s) + ${POLL_SECONDS:-300} ))
while :; do
  api GET "/crawls/$CRAWL_ID?limit=100"
  [ "$CODE" = 200 ] || break
  [ "$(val '.data.done')" = true ] && break
  [ "$(date +%s)" -ge "$deadline" ] && break
  printf '  ...   %s, %s reviews so far\n' "$(val '.data.status')" "$(val '(.data.reviews | length)')"
  sleep 5
done
PAGE=$BODY
check "page read" "$CODE" 200
check "done" "$(val '.data.done' "$PAGE")" true
check "crawl status" "$(val '.data.status' "$PAGE")" succeeded
N=$(val '(.data.reviews | length)' "$PAGE"); ND=$(val '([.data.reviews[].review_hash] | unique | length)' "$PAGE")
RUN_ID=$(val '.data.run_id' "$PAGE")
[ "${N:-0}" -gt 0 ] && ok "reviews returned ($N)" || { bad "no reviews returned"; finish; }
check "every review has a hash" "$(val '[.data.reviews[] | select((.review_hash // "") == "")] | length' "$PAGE")" 0

PQ=$(jq -rn --arg p "$PLACE_ID" '$p | @uri')
echo "4. audit before analysis"
api GET "/audit/summary?site_id=$SITE_ID&place_id=$PQ"
check "summary" "$CODE" 200
[ "$(val '.data.reviews.stored_count')" -ge "$ND" ] && ok "backup holds the reviews ($(val '.data.reviews.stored_count'))" || bad "backup holds fewer than $ND reviews"
check "last run is this one" "$(val '.data.crawls.last_run.run_id')" "$RUN_ID"
check "last run status" "$(val '.data.crawls.last_run.status')" succeeded
echo "        unanalyzed before: $(val '.data.reviews.unanalyzed_count') (0 on a re-run of the same place)"

echo "5. analysis ($PROVIDER, ${TAXONOMY_FILE:-no taxonomy})"
AREQ=$(jq --argjson s "$SITE_ID" --arg p "$PROVIDER" --slurpfile t "${TAXONOMY_FILE:-/dev/null}" \
  '{site_id: $s, provider: $p, taxonomy: ($t[0] // null), reviews: [.data.reviews | to_entries[] |
    {id: ("r" + (.key | tostring)), review_hash: .value.review_hash, rating: .value.rating,
     text: .value.review_text, reviewer_name: .value.reviewer_name}]}' <<<"$PAGE")
api POST /analysis "$AREQ"
check "analysis" "$CODE" 200
check "one result per review" "$(val '(.data.results | length)')" "$N"
check "failed analyses" "$(val '.data.summary.failed')" 0
echo "        $(val '"model \(.data.model), tokens \(.data.usage.total_tokens), analyzed \(.data.summary.analyzed), rating_fallback \(.data.summary.rating_fallback)"')"

echo "6. audit after analysis"
api GET "/audit/summary?site_id=$SITE_ID&place_id=$PQ"
check "summary" "$CODE" 200
check "unanalyzed" "$(val '.data.reviews.unanalyzed_count')" 0

echo "7. reply suggestion"
if [ -n "${TAXONOMY_FILE:-}" ]; then
  RREQ=$(jq --argjson s "$SITE_ID" --slurpfile t "$TAXONOMY_FILE" \
    '{site_id: $s, review_hash: .data.reviews[0].review_hash, text: .data.reviews[0].review_text, taxonomy: $t[0],
      presets: [{id: "mohon_maaf_waktu_tunggu", when_to_use: "Keluhan antrean atau lama menunggu tanpa isu keselamatan"}]}' <<<"$PAGE")
  api POST /reply-suggestion "$RREQ"
  check "reply suggestion" "$CODE" 200
  echo "        mode $(val '.data.mode'), preset $(val '.data.preset_id // "-"'), reason $(val '.data.reason // "-"')"
else
  echo "  skip  set TAXONOMY_FILE=<taxonomy.json> to test it (it needs a real taxonomy body)"
fi

echo "8. reconcile"
RCON=$(jq --argjson s "$SITE_ID" --arg p "$PLACE_ID" '{site_id: $s, place_id: $p, review_hashes: [.data.reviews[].review_hash]}' <<<"$PAGE")
api POST /audit/reconcile "$RCON"
check "reconcile with the crawled hashes" "$CODE" 200
check "missing in backup" "$(val '.data.missing_in_backup_count')" 0
check "matched" "$(val '.data.matched')" "$ND"
RNONE=$(jq -n --argjson s "$SITE_ID" --arg p "$PLACE_ID" '{site_id: $s, place_id: $p, review_hashes: []}')
api POST /audit/reconcile "$RNONE"
check "reconcile with no hashes" "$CODE" 200
check "everything missing in caller" "$(val '.data.missing_in_caller_count')" "$(val '.data.backup_count')"

echo "9. idempotency"
api POST /crawls "$START" "$KEY"
check "replay flag" "$(val '.data.idempotent_replay')" true
[ "$(val '.data.runs[0].crawl_id')" = "$CRAWL_ID" ] && ok "same crawl_id, no new run" || bad "replay returned a different crawl_id"

finish
