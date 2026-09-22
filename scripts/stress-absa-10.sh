#!/usr/bin/env bash
set -Eeuo pipefail

VOC_API="${VOC_API:-http://127.0.0.1:8000}"
CONCURRENCY=10
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"; unset VOC_SERVICE_TOKEN' EXIT

command -v jq >/dev/null || {
  echo "ERROR: jq is required."
  exit 1
}

if [[ -z "${VOC_SERVICE_TOKEN:-}" ]]; then
  read -rsp "VOC service token: " VOC_SERVICE_TOKEN
  echo
fi

AUTH=(
  -H "Authorization: Bearer ${VOC_SERVICE_TOKEN}"
  -H "Accept: application/json"
)

echo "=== Validate token ==="
WHOAMI="$(
  curl --fail-with-body -sS "${AUTH[@]}" \
    "${VOC_API}/api/integration/v1/whoami"
)"
echo "$WHOAMI" | jq

jq -e '
  ((.scopes | index("analysis:write")) != null) and
  ((.scopes | index("reviews:read")) != null)
' <<<"$WHOAMI" >/dev/null || {
  echo "ERROR: token requires analysis:write and reviews:read."
  exit 1
}

echo
echo "=== Select 10 reviews ==="
REVIEWS="$(
  curl --fail-with-body -sS "${AUTH[@]}" \
    "${VOC_API}/api/integration/v1/reviews?limit=200"
)"

mapfile -t REVIEW_IDS < <(
  jq -r '
    [.data[] | select((.review_text // "") != "")][0:10][].id
  ' <<<"$REVIEWS"
)

if (( ${#REVIEW_IDS[@]} < CONCURRENCY )); then
  echo "ERROR: found only ${#REVIEW_IDS[@]} non-empty reviews; need 10."
  exit 1
fi

printf '%s\n' "${REVIEW_IDS[@]}" | tee "$TMP_DIR/review-ids.txt"
SINCE="$(date -u -d '5 minutes ago' '+%Y-%m-%dT%H:%M:%SZ')"

echo
echo "=== Start 10 concurrent ABSA inferences ==="
echo "review_id,http_status,total_ms,inference_ms,overhead_ms,result" \
  > "$TMP_DIR/metrics.csv"

for REVIEW_ID in "${REVIEW_IDS[@]}"; do
  (
    START_MS="$(date +%s%3N)"

    HTTP_STATUS="$(
      curl -sS \
        --max-time 600 \
        -o "$TMP_DIR/response-${REVIEW_ID}.json" \
        -w '%{http_code}' \
        -X POST \
        "${AUTH[@]}" \
        -H "X-Request-ID: stress-absa-${REVIEW_ID}-$(date +%s)" \
        "${VOC_API}/api/integration/v1/analysis/reviews/${REVIEW_ID}/rerun?provider=absa" \
        || printf '000'
    )"

    END_MS="$(date +%s%3N)"
    TOTAL_MS="$((END_MS - START_MS))"
    INFERENCE_MS="$(
      jq -r '.data.llm_call_ms_total // 0' \
        "$TMP_DIR/response-${REVIEW_ID}.json"
    )"
    OVERHEAD_MS="$(
      awk -v total="$TOTAL_MS" -v inference="$INFERENCE_MS" \
        'BEGIN {printf "%.1f", total - inference}'
    )"

    if jq -e \
      '.data.success == 1 and .data.failed == 0' \
      "$TMP_DIR/response-${REVIEW_ID}.json" >/dev/null 2>&1; then
      RESULT="success"
    else
      RESULT="failed"
    fi

    echo "${REVIEW_ID},${HTTP_STATUS},${TOTAL_MS},${INFERENCE_MS},${OVERHEAD_MS},${RESULT}" \
      >> "$TMP_DIR/metrics.csv"
  ) &
done

wait

echo
echo "=== Request metrics ==="
sort -t, -k1,1n "$TMP_DIR/metrics.csv" |
  column -s, -t

SUCCESS="$(
  awk -F, '$6 == "success" {count++} END {print count+0}' \
    "$TMP_DIR/metrics.csv"
)"
FAILED="$((CONCURRENCY - SUCCESS))"
AVG_TOTAL_MS="$(
  awk -F, '
    NR > 1 {sum += $3; count++}
    END {printf "%.1f", count ? sum/count : 0}
  ' "$TMP_DIR/metrics.csv"
)"
AVG_INFERENCE_MS="$(
  awk -F, '
    NR > 1 {sum += $4; count++}
    END {printf "%.1f", count ? sum/count : 0}
  ' "$TMP_DIR/metrics.csv"
)"
MAX_INFERENCE_MS="$(
  awk -F, 'NR > 1 && $4 > max {max=$4} END {printf "%.1f", max}' \
    "$TMP_DIR/metrics.csv"
)"

echo
echo "success=${SUCCESS}"
echo "failed=${FAILED}"
echo "average_total_ms=${AVG_TOTAL_MS}"
echo "average_inference_ms=${AVG_INFERENCE_MS}"
echo "maximum_inference_ms=${MAX_INFERENCE_MS}"

echo
echo "=== Pull sentiments returned to OneBox ==="
PULL_RESPONSE="$(
  curl --fail-with-body -sS -G \
    "${AUTH[@]}" \
    --data-urlencode "updated_since=${SINCE}" \
    --data-urlencode "limit=200" \
    "${VOC_API}/api/integration/v1/reviews"
)"

echo "$PULL_RESPONSE" |
  jq --rawfile ids "$TMP_DIR/review-ids.txt" '
    ($ids | split("\n") | map(select(length > 0) | tonumber)) as $wanted
    |
    [
      .data[]
      | select(.id as $id | $wanted | index($id))
      | {
          id,
          analysis_status,
          sentiment,
          sentiment_score,
          issue_category,
          urgency
        }
    ]
  '

RETURNED="$(
  echo "$PULL_RESPONSE" |
    jq --rawfile ids "$TMP_DIR/review-ids.txt" '
      ($ids | split("\n") | map(select(length > 0) | tonumber)) as $wanted
      |
      [
        .data[]
        | select(
            (.id as $id | $wanted | index($id)) and
            .analysis_status == "completed" and
            .sentiment != null
          )
      ]
      | length
    '
)"

echo
echo "sentiments_returned=${RETURNED}/10"

if [[ "$SUCCESS" == "10" && "$RETURNED" == "10" ]]; then
  echo "PASS: all 10 concurrent inferences completed."
else
  echo "FAIL: inspect responses under ${TMP_DIR} before the script exits."
  exit 1
fi
