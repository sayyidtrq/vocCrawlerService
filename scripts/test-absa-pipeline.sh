#!/usr/bin/env bash
set -Eeuo pipefail

VOC_API="${VOC_API:-http://127.0.0.1:8000}"
ABSA_API="${ABSA_API:-http://127.0.0.1:9090/api}"
CRAWLER_CONTAINER="${CRAWLER_CONTAINER:-hermina-review-api}"
EXPECTED_COMPANY_ID=3

command -v curl >/dev/null || {
  echo "ERROR: curl is required."
  exit 1
}
command -v jq >/dev/null || {
  echo "ERROR: jq is required. Install with: sudo apt-get install jq"
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

curl_json() {
  curl --fail-with-body -sS "$@"
}

echo
echo "=== 1. ABSA health from server host ==="
curl_json "${ABSA_API}/health" | jq

echo
echo "=== 2. ABSA connectivity from crawler container ==="
docker exec "${CRAWLER_CONTAINER}" \
  curl --fail-with-body -sS \
  "http://host.docker.internal:9090/api/health" |
  jq

echo
echo "=== 3. Validate OneBox service token ==="
WHOAMI="$(
  curl_json "${AUTH[@]}" \
    "${VOC_API}/api/integration/v1/whoami"
)"
echo "${WHOAMI}" | jq

ACTUAL_COMPANY_ID="$(jq -r '.company_id' <<<"${WHOAMI}")"

if [[ "${ACTUAL_COMPANY_ID}" != "${EXPECTED_COMPANY_ID}" ]]; then
  echo "ERROR: token belongs to company ${ACTUAL_COMPANY_ID}, expected 3."
  exit 1
fi

jq -e '
  ((.scopes | index("analysis:write")) != null) and
  ((.scopes | index("reviews:read")) != null)
' <<<"${WHOAMI}" >/dev/null || {
  echo "ERROR: token requires analysis:write and reviews:read scopes."
  exit 1
}

echo
echo "=== 4. Find a non-empty review owned by company 3 ==="
REVIEWS="$(
  curl_json "${AUTH[@]}" \
    "${VOC_API}/api/integration/v1/reviews?limit=100"
)"

REVIEW="$(
  jq -c '
    [.data[] | select((.review_text // "") != "")][0] // empty
  ' <<<"${REVIEWS}"
)"

if [[ -z "${REVIEW}" ]]; then
  echo "ERROR: no review with non-empty text was found."
  exit 1
fi

REVIEW_ID="$(jq -r '.id' <<<"${REVIEW}")"
LOCATION_ID="$(jq -r '.location_id' <<<"${REVIEW}")"
REVIEW_TEXT="$(jq -r '.review_text' <<<"${REVIEW}")"

echo "${REVIEW}" |
  jq '{
    id,
    location_id,
    location,
    rating,
    review_text,
    current_status: .analysis_status,
    current_sentiment: .sentiment
  }'

echo
echo "=== 5. Show exact direct ABSA input ==="
ABSA_INPUT="$(
  jq -nc \
    --arg review "${REVIEW_TEXT}" \
    '{
      review: $review,
      engine_version: "v14",
      profile: "maps_high_recall",
      confidence_threshold: 0.1
    }'
)"
echo "${ABSA_INPUT}" | jq

echo
echo "=== 6. Show direct ABSA response ==="
ABSA_RESPONSE="$(
  curl_json -X POST "${ABSA_API}/inference/single" \
    -H "Content-Type: application/json" \
    -d "${ABSA_INPUT}"
)"
echo "${ABSA_RESPONSE}" | jq

jq -e '
  (.results | type == "array") and
  (.engine_version == "v14")
' <<<"${ABSA_RESPONSE}" >/dev/null || {
  echo "ERROR: ABSA response does not match the expected V14 contract."
  exit 1
}

echo
echo "=== 7. Trigger full OneBox -> Crawler -> ABSA pipeline ==="
echo "POST /api/integration/v1/analysis/reviews/${REVIEW_ID}/rerun?provider=absa"

REQUEST_ID="manual-absa-$(date +%s)"
SINCE="$(date -u -d '5 minutes ago' '+%Y-%m-%dT%H:%M:%SZ')"

ANALYSIS_RESPONSE="$(
  curl_json -X POST "${AUTH[@]}" \
    -H "X-Request-ID: ${REQUEST_ID}" \
    "${VOC_API}/api/integration/v1/analysis/reviews/${REVIEW_ID}/rerun?provider=absa"
)"
echo "${ANALYSIS_RESPONSE}" | jq

jq -e '
  .data.success == 1 and
  .data.failed == 0
' <<<"${ANALYSIS_RESPONSE}" >/dev/null || {
  echo "ERROR: crawler reported a failed analysis."
  exit 1
}

echo
echo "=== 8. Pull result as OneBox and display sentiment ==="
PULL_RESPONSE="$(
  curl_json -G "${AUTH[@]}" \
    -H "X-Request-ID: ${REQUEST_ID}-pull" \
    --data-urlencode "updated_since=${SINCE}" \
    --data-urlencode "location_id=${LOCATION_ID}" \
    --data-urlencode "limit=200" \
    "${VOC_API}/api/integration/v1/reviews"
)"

RESULT="$(
  jq -c \
    --arg id "${REVIEW_ID}" \
    '.data[] | select(.id == ($id | tonumber))' \
    <<<"${PULL_RESPONSE}" |
    head -1
)"

if [[ -z "${RESULT}" ]]; then
  echo "ERROR: analyzed review was not returned to OneBox."
  echo "${PULL_RESPONSE}" | jq
  exit 1
fi

echo "${RESULT}" |
  jq '{
    id,
    location,
    review_text,
    analyzed,
    analysis_status,
    output_schema_version,
    sentiment,
    sentiment_score,
    issue_category,
    urgency,
    summary,
    recommended_action,
    keywords,
    is_potential_viral,
    is_patient_safety_issue,
    sync_updated_at
  }'

jq -e '
  .analyzed == true and
  .analysis_status == "completed" and
  .sentiment != null
' <<<"${RESULT}" >/dev/null || {
  echo "ERROR: OneBox response does not contain a completed sentiment."
  exit 1
}

echo
echo "PASS: OneBox -> Crawler -> ABSA -> database -> OneBox completed."