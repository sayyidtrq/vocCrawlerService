# OneBox - what changes for the stateless crawler (v2)

Status: Proposed (2026-10-27). Read with [ADR-0006](../decisions/ADR-0006-stateless-rest-crawler.md) and [STATELESS_V2_API.md](STATELESS_V2_API.md).
Audience: the OneBox developer. This **replaces** `markdowns/multitenant-readiness/05-ONEBOX-HANDOFF.md` (the tenant provisioning, push worklist and outbox plan, tasks MT-30 to MT-35). Do not build those.

OneBox references below are from branch `origin/feature/voc` of the `onecloud` repo.

## 1. The idea in one paragraph

The crawler no longer knows tenants, worklists, schedules or quotas, and it is no longer the place OneBox reads reviews back from. OneBox says what to crawl and when (one call per place), reads the reviews straight from the crawl, stores them, sends them for analysis in the request, and keeps the quotas. The crawler keeps a backup only so you can check for stale or missing data.

## 2. What you stop building (old plan, MT-30 to MT-35)

| Old task | Why it is no longer needed |
|---|---|
| Package-activation hook that registers a tenant and stores a token | no tenants in the crawler; one shared token |
| Setup Parameter page with per-site token, status and Refresh | nothing to show per site |
| Snapshot builder with a `snapshot_version` counter | no worklist push |
| Outbox, retries, debounce, scheduled push and drift check | no push of worklists, no tenant lifecycle |
| Sending a weight, or deactivating a tenant | OneBox decides which sites crawl, and the order |

## 3. What you remove after the switch

- `GET /api/VocWorklist` (`controllers/api/v1/VocWorklistController.php`) and the service account it needs (`/api/Authenticate`). The crawler no longer pulls anything. Keep `services/VocWorklist.php` only if you still use it to build targets or taxonomies.
- The old write calls in `VoiceOfCustomerSystemClient`: `createLocation`, `updateLocation`, `deleteLocation`, `createCompetitor`, `updateCompetitor`, `deleteCompetitor`, `resolveLocation`, `listLocations`, and the user-login mode (`api_mode=user`). The crawler has no locations to maintain.
- Per-Connection `Options.service_token`. There is one token for all sites: `CRAWLER_API_TOKEN` on the crawler, the same value in one OneBox setting (for example base URL and token as system settings, not per Connection).

## 4. Call-by-call mapping

| OneBox today (`VoiceOfCustomerSystemClient`) | v2 | Notes |
|---|---|---|
| `enqueueCrawl($targets, $key, $options)` -> `POST /api/integration/v1/crawl-jobs` | `POST /api/integration/v2/crawls` | targets become `{place_id}` (the Google place id, not `onebox_location_id`); `crawl_mode` becomes `mode` (`backfill`, `delta`, `range`); `date_range` becomes `date_from`/`date_to`; `review_quota_remaining` is gone (you enforce quotas yourself); add `site_id` as a label |
| `crawlBatch($batchId)`, `crawlBatches()` | `GET /api/integration/v2/crawls/{crawl_id}` | one `crawl_id` per place; there is no batch and no list. Keep your own run log |
| `fetchPage` / `getIntegrationReviews` -> `GET /api/integration/v1/reviews` (the import read) | the pages of `GET /v2/crawls/{crawl_id}?cursor=&limit=` | reviews come from the crawl, not from a stored copy |
| `analyzePending`, `analyzeReview` | `POST /api/integration/v2/analysis` | you send the reviews and the taxonomy; the result comes back in the response |
| `replySuggestion($reviewId, $body)` | `POST /api/integration/v2/reply-suggestion` | add `text` and the full `taxonomy` body; response shape is unchanged |
| `whoami`, `health` | `GET /api/health` | `whoami` has no v2 equivalent |
| (new) | `GET /v2/audit/summary`, `POST /v2/audit/reconcile` | stale and missing data checks |

## 5. The crawl and import flow

**Start.** For each place to crawl, one `POST /v2/crawls`:
- First time for a place: `mode: "backfill"`, `max_reviews` = the target review count you already keep per location.
- Afterwards: `mode: "delta"` with `date_from` = the place's watermark minus a safety margin (`VocTargetRegistry` already advances a per-location watermark; use it, and subtract about two days so a late review is not missed; `review_hash` removes the overlap).
- Custom range: `mode: "range"` with both dates.
- Send an `Idempotency-Key` that is the same on a retry of the same request (for example site, schedule run and place). A repeated key returns the stored run and starts no second, paid Apify run.
- Store the returned `crawl_id` per place in your import state (where `saveVocImportState` keeps the batch id today).

**Read.** `VocProvider::receive` can keep its ingest loop. Change only where a page comes from: `GET /v2/crawls/{crawl_id}?cursor=<_sync_cursor>&limit=100`, until `done: true`.
- You may read while the run is still `running`; pages hold what the dataset has so far, and `next_cursor` is where to continue.
- Keep the existing rules: skip rows without `review_hash`, dedupe on `review_hash`, hold the cursor when a row fails, dead-letter poison rows.
- Rows differ from v1 in three ways: there is no `id` (use `review_hash` in logs and in `catatWatermark`), no `sync_updated_at` (advance the watermark from `review_time`), and no analysis fields inside the review.
- `review_hash` is identical to v1's for the same review as long as the place id string is the same one v1 used (`Location.external_place_id`); a test in the crawler repo (`tests/test_v2_hash_parity.py`) proves it for seven shapes. So switching over does not create duplicates.

**Collect on time.** Apify keeps a run's dataset only for some days. Poll every run to `done` soon after it finishes, and alert on any run not collected within, say, 24 hours. `GET /v2/audit/summary` shows the last crawl per place.

**Errors to handle.** `429 APIFY_CONCURRENCY_LIMIT` (wait `Retry-After`, 60 s, then retry); `503 APIFY_ACCOUNTS_EXHAUSTED` and `503 APIFY_NOT_CONFIGURED` (alert operations, do not retry quickly); `502 APIFY_RUN_FAILED`; `404 CRAWL_NOT_FOUND`; `400 INVALID_CRAWL_ID`; `401` and `503 V2_NOT_CONFIGURED` (token missing or wrong).

## 6. Analysis

After ingesting new reviews, send the ones without an analysis in batches of at most 50 to `POST /v2/analysis` with `taxonomy` set to the taxonomy body OneBox already builds from `VocCatalog` (the same body the old worklist carried) and `provider` if you want to choose one.
- `results[].analysis` carries `sentiment`, `issue_category`, `urgency`, `summary`, `recommended_action`, `tags` and the rest, the same names `VocAnalysisSchema` validates today. Pass `results[].analysis` plus the `review_hash` and `rating` through your existing normalizer.
- `status` is `analyzed`, `rating_fallback` (empty text, no model call) or `failed`. Keep failed reviews as "not analysed" and retry them later; one failure never fails the batch.
- `usage` gives prompt, completion and total tokens: add them to the tenant's Jev budget (Q-43) in OneBox.

## 7. Reply suggestion

Same call shape as today with two additions: `text` (the review text) and `taxonomy` (the full body, not just a key). Send the presets as now (`id`, `when_to_use`). The decision (`mode`, `preset_id`, `confidence`, ...) is unchanged, so `VocReplySuggestion::decide` keeps working.

## 8. What OneBox now owns

| Concern | Rule |
|---|---|
| Review storage and dedupe | OneBox is the only record; dedupe on `review_hash` |
| Delta cursors | the per-location watermark, sent as `date_from` |
| Scheduling and fairness | decide which place starts when; do not start more runs than Apify allows (watch for 429); no weights in the crawler |
| Quotas (Q-41) | backfill cap `max(100000, 2500 x locations)` fetched reviews, lifetime per tenant; operating cap `2000 x locations` per month; alert at 50% of operating and 80% of backfill; pause new crawls at 100%. Count from the reviews your own import received |
| Jev budget (Q-43, proposed) | `max($10, $0.25 x locations)` a month, from `usage` in the analysis responses |
| Retries | idempotent `POST` with a stable key, backoff on 429 |

## 9. Gaps: v1 features v2 does not have

Decide for each whether OneBox drops it, keeps it locally, or asks for a v2 endpoint.

| v1 feature | v2 |
|---|---|
| `crawl-jobs/estimate`, `crawl-jobs/probe` (how many reviews, is the place ahead of us) | none. Ask if the UI needs it |
| `crawl-jobs` list | none; use your own run log |
| `analysis/models` (available models list) | none; add `GET /v2/analysis/models` if the UI needs it |
| `analysis/rollback`, `analysis/quality-summary` | the crawler stores no analysis to roll back; do it on OneBox's own stored analyses |
| `competitor-reviews` | crawl a competitor's place id like any other place and keep it in OneBox's own tables |
| Reading reviews you already imported again | not possible from v2; `audit/reconcile` only tells you which hashes differ |

## 10. Suggested order

1. Put `CRAWLER_API_TOKEN` on the crawler and one OneBox setting; confirm `GET /v2/audit/summary` returns 200.
2. A feature flag per site: `crawler_api = v1 | v2`.
3. On one dev site and one place: v2 backfill with a small `max_reviews`, compare the review count and hashes with what v1 already imported (no duplicates expected), then a delta, then `audit/reconcile` with the hashes OneBox holds.
4. Switch analysis, then reply suggestion, for that site.
5. Roll out site by site, then remove the v1 calls and the worklist endpoint.

Before step 3 someone should run one real crawl against the deployed crawler (the local real crawl of one place already worked: 5 reviews in about 30 seconds).
