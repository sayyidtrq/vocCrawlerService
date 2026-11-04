# Runbook - Stateless v2 API

Status: Current (2026-10-27, branch `feature/stateless-rest-crawler`, design in [ADR-0006](../decisions/ADR-0006-stateless-rest-crawler.md))
Audience: whoever calls the crawler from OneBox, or checks it by hand.

The v2 API is stateless: every call carries what it needs, and the crawler keeps a database only as a backup and audit trail. v1 is unchanged and still serves the current OneBox.

## 1. Set it up

| Step | What |
|---|---|
| 1 | Set one shared token in the crawler environment: `CRAWLER_API_TOKEN=<long random string>`. Without it every v2 call answers `503 V2_NOT_CONFIGURED`. |
| 2 | Make sure `APIFY_API_TOKENS` is set (crawls) and, for analysis, `TYPESAFE_API_KEY` (Jev) or `OPENAI_API_KEY`. |
| 3 | Run the migrations (the API container does it on start): `docker compose exec -T api python -m alembic upgrade head`. Head today: `20261027_0016`. It adds `audit_crawl_runs`, `audit_reviews`, `audit_analyses`. |
| 4 | Check: `curl -s -H "Authorization: Bearer $TOKEN" "$CRAWLER/api/integration/v2/audit/summary"` returns `200` with zeros on a fresh database. |

Every example below uses `CRAWLER=https://your-crawler-host` and `TOKEN=<the CRAWLER_API_TOKEN value>`. Every success response is `{"data": ..., "meta": {"api_version": "v2", "request_id": ...}}`. Errors are `{"error": {"code", "message", "request_id"}}`. Send `X-Request-ID` to correlate.

## 2. Crawl

Start (one Apify run per place, not waited on). `site_id` is only a label stored in the audit trail.

```bash
curl -s -X POST "$CRAWLER/api/integration/v2/crawls" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -H "Idempotency-Key: onebox-site169-2026-10-27-a" \
  -d '{"site_id": 169, "targets": [{"place_id": "ChIJ..."}], "mode": "delta",
       "date_from": "2026-10-20T00:00:00Z", "max_reviews": 200, "sort_by": "newest"}'
```

| Field | Rule |
|---|---|
| `mode` | `delta` (default), `backfill`, or `range` (needs `date_from` and `date_to`) |
| `date_from`, `date_to` | timezone-aware ISO times; `date_to` only with `range` |
| `max_reviews` | 1 to 100000, default 100 |
| `targets` | 1 to 50 distinct `place_id` |
| `Idempotency-Key` | optional, 8 to 128 characters. Repeating it returns the stored runs (`idempotent_replay: true`) and starts no new paid Apify run. If the audit database is down it just starts the runs. |

Response `202`: `data.runs[]` with `place_id`, `crawl_id`, `run_id`, `status` (`started` or `failed`) and `error`. Keep the `crawl_id`.

Poll and read reviews (cursor is the next offset, start with none):

```bash
curl -s -H "Authorization: Bearer $TOKEN" "$CRAWLER/api/integration/v2/crawls/$CRAWL_ID?limit=100"
curl -s -H "Authorization: Bearer $TOKEN" "$CRAWLER/api/integration/v2/crawls/$CRAWL_ID?limit=100&cursor=$NEXT_CURSOR"
```

`data.status` is `running`, `succeeded`, `failed`, `aborted`, `timed_out` or `unknown`. While running you get the reviews already in the dataset with `done: false`; keep calling with `next_cursor` until `done: true` (`next_cursor: null`). Each review carries a `review_hash`; dedupe on it in OneBox. A failed or aborted run still returns what it produced. Collect a run soon after it finishes, because Apify expires datasets after some days.

| Status | Meaning |
|---|---|
| `429 APIFY_CONCURRENCY_LIMIT` | Apify is at its concurrent-run limit; wait `Retry-After` (60 s) and retry |
| `503 APIFY_NOT_CONFIGURED` | no Apify token is configured on the crawler (`APIFY_API_TOKENS` is empty); checked before any Apify call, on both POST and GET |
| `503 APIFY_ACCOUNTS_EXHAUSTED` | tokens are configured but every account is out of credit |
| `502 APIFY_RUN_FAILED` | any other Apify failure |
| `400 INVALID_CRAWL_ID` | the `crawl_id` was altered or is malformed |
| `404 CRAWL_NOT_FOUND` | Apify does not know that run for that account |

## 3. Analysis and reply suggestion

Both take everything in the body; nothing is read from the database.

```bash
curl -s -X POST "$CRAWLER/api/integration/v2/analysis" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"site_id": 169, "provider": "jev", "taxonomy": { ...the OneBox taxonomy snapshot body, with "key"... },
       "reviews": [{"id": "r1", "review_hash": "<from the crawl>", "rating": 2,
                    "text": "Antre lama sekali", "reviewer_name": null}]}'
```

- 1 to 50 reviews per call, unique `id` each (echoed back). `taxonomy: null` means the legacy behaviour; an unusable taxonomy is `400 INVALID_TAXONOMY`.
- Empty text gives a rating-only result without a model call (`rating_fallback`). A review whose model call fails after the retries is `failed` with `ANALYSIS_FAILED`; the rest still succeed.
- `data.results[]` keeps the request order; `data.usage` sums the tokens. No provider has a key: `503 PROVIDER_NOT_CONFIGURED`.

```bash
curl -s -X POST "$CRAWLER/api/integration/v2/reply-suggestion" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"site_id": 169, "review_hash": "<hash>", "text": "Antre lama sekali",
       "taxonomy": { ...snapshot body... },
       "presets": [{"id": "mohon_maaf_waktu_tunggu", "when_to_use": "Keluhan antrean atau lama menunggu tanpa isu keselamatan"}],
       "thresholds": {"preset": 0.75}}'
```

`data.mode` is `preset` (with `preset_id` and `confidence`), `escalate` (a critical risk flag fired) or `none` (with a `reason`: `taxonomy_unavailable`, `no_text`, `no_presets`, or no confident preset). OneBox keeps the reply text and looks it up by `preset_id`. A provider failure is `502 SUGGESTION_FAILED`.

## 4. `POST /api/integration/v2/brief`

OneBox sends its draft and aggregate facts; the crawler rewrites them in natural Indonesian by default with one OpenAI call. OneBox owns number verification. The crawler never stores or logs the draft, facts, or rewritten text; the audit row contains only operational metadata, status, and token counts (`result: {}`).

```bash
curl -s -X POST "$CRAWLER/api/integration/v2/brief" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"language": "id", "audience": "coo", "draft": "Ringkasan uji: 17 laporan.",
       "facts": [{"key": "reports", "value": 17}], "max_words": 250}'
```

| Field | Rule |
|---|---|
| `language` | two lowercase letters, default `id` |
| `audience` | `coo` (default) or `manager` |
| `draft` | required, 1 to 6000 characters |
| `facts` | up to 200 objects, default `[]`; each has a `key` of 1 to 60 characters and a string, integer, or float `value` |
| `max_words` | integer, 50 to 600, default 250 |

Response `200`:

```json
{"data": {"text": "Ringkasan uji mencatat 17 laporan.", "model": null, "usage": {"prompt_tokens": 100, "completion_tokens": 12, "total_tokens": 112}}, "meta": {"api_version": "v2", "request_id": "brief-example"}}
```

`model` is the configured model identifier (or `null` when unavailable). Set `OPENAI_API_KEY` and `OPENAI_MODEL`; optional `BRIEF_MODEL` overrides the model for this endpoint only, and can also supply the model when `OPENAI_MODEL` is unset. A blank `BRIEF_MODEL` falls back to `OPENAI_MODEL`.

Errors use the shared v2 envelope: `401 INVALID_SERVICE_TOKEN` for missing/bad auth, `400 INVALID_PARAMETER` for validation, `429 BRIEF_FAILED` for provider rate limits (`Retry-After: 60`), `502 BRIEF_FAILED` for provider failure or empty text, and `503 PROVIDER_NOT_CONFIGURED` for missing OpenAI configuration. As with every v2 route, an unset `CRAWLER_API_TOKEN` gives `503 V2_NOT_CONFIGURED`.

## 5. Audit: is the backup stale?

```bash
# one place
curl -s -H "Authorization: Bearer $TOKEN" "$CRAWLER/api/integration/v2/audit/summary?site_id=169&place_id=ChIJ..."
# the whole site, stalest places first
curl -s -H "Authorization: Bearer $TOKEN" "$CRAWLER/api/integration/v2/audit/summary?site_id=169&limit=50"
```

Place summary: stored review count, newest and oldest review time, last seen, last crawl (run, status, age in seconds), analysis counts by status, and `unanalyzed_count` (reviews with no successful analysis: only `analyzed` or `rating_fallback` counts). An unknown place returns zeros with `200`.

```bash
curl -s -X POST "$CRAWLER/api/integration/v2/audit/reconcile" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"site_id": 169, "place_id": "ChIJ...", "review_hashes": ["<hash>", "<hash>"], "since": "2026-09-01T00:00:00Z", "limit": 1000}'
```

Send the hashes OneBox holds for the place. You get `missing_in_caller` (the backup has it, OneBox lacks it), `missing_in_backup` (OneBox has it, the backup never saw it), `matched`, exact counts, and truncation flags. A place with more than 200,000 backup rows answers `400 RECONCILE_TOO_LARGE`; pass `since`. Both audit calls only read. If the database is down they answer `503 AUDIT_UNAVAILABLE`.

## 6. Tests for v2

```bash
.venv/bin/python -m pytest tests/test_v2_crawls.py tests/test_v2_ai.py tests/test_v2_audit.py -q     # 332 tests, offline
.venv/bin/python -m alembic heads                                                                    # one head: 20261027_0016
```

They use in-memory SQLite and fakes for Apify and the AI providers, so nothing real is called. Real Apify, Jev and OpenAI have not been exercised yet: before OneBox switches, run one real crawl of one place with a small `max_reviews`, poll it to `done`, and check `audit/summary` shows it.

## 7. Smoke test the AI Insight API on a deployed Crawler

OneBox's AI Insight (weekly brief, label confidence) depends on `/analysis` and `/brief`. `scripts/smoke_v2.sh` covers crawl, audit, reconcile and idempotency; this script covers the AI side, using only the Python 3 standard library:

```bash
CRAWLER=https://your-dev-host TOKEN=<CRAWLER_API_TOKEN> python3 scripts/smoke_ai_insight_v2.py
# flags: --provider jev|openai|absa  --max-tokens 20000  --taxonomy-file taxonomy.json  --skip-analysis  --skip-brief
```

It leaves `TOKEN` out of its output (if unset it prompts, hidden). Exit 0 means every check passed. What each part proves:

1. **auth**: a request without a token gets 401; a request with the token reaches validation (400 on an empty review list, so no model is called). A 503 means `CRAWLER_API_TOKEN` is unset on the server.
2. **`/analysis`**: four synthetic reviews (one rating-only). Every `category_confidence` is a number in [0, 1], the rating-only review has none, and at least one analysed review carries it for `absa`, or for `jev` when `--taxonomy-file` is given (Jev returns it only on its taxonomy path, so without a taxonomy the check is skipped and says so). If none does, the server runs a build older than `b6a5501`.
3. **`/brief`**: a draft and facts shaped like OneBox's weekly brief. The reply must be non-empty, report model and token usage, keep every headline number and add no number of its own (the same guard OneBox applies, `VocBriefGuard`, ported to Python). A second call appends an instruction written in words ("sembilan ratus sembilan puluh sembilan") to the draft and fails if the digits `999` come back. An empty draft and 201 facts must both be rejected.
4. **tokens**: the total is printed, and `--max-tokens` turns an overrun into a failure.

Cost: one `/analysis` call of 4 reviews (the rating-only one costs nothing) and two LLM `/brief` calls. The script's own tests (`tests/test_smoke_ai_insight_script.py`) run it offline against the stubbed app, including broken-server cases (invented number, dropped headline number, missing or out-of-range confidence, wrong token, empty brief) that must fail.
