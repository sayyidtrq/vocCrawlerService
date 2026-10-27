# Brief: switch OneBox to the stateless crawler API (v2)

For: a Claude Code session working in the OneBox repo. Written 2026-10-27. Self-contained: you have no earlier context.

## 0. Your task in one paragraph

The VoC crawler service was redesigned as a **stateless REST API (v2)**. OneBox must be able to use it. Add a **v2 path** to the OneBox VoC code, behind a **per-connection feature flag that defaults to the current v1 behaviour**, and prove it with offline PHP checks against a fake v2 crawler. Do not remove the v1 path, do not push, do not touch the crawler repository.

## 1. Where things are

| What | Path |
|---|---|
| OneBox repo | `/Volumes/CodeCS/Ciptadra/onecloud` (the app is in `onecloud/` inside it; PHP, Phalcon) |
| Base your work on | `origin/feature/voc` (the VoC code lives there, **not** in `develop`). The main checkout is on another branch with untracked files: use a worktree. |
| Branch to create | `feature/voc-crawler-v2` |
| Crawler repo (read only) | `/Volumes/CodeCS/Ciptadra/hermina-crawler`, branch `feature/stateless-rest-crawler` (not pushed; read the files on disk) |
| Design | `hermina-crawler/markdowns/decisions/ADR-0006-stateless-rest-crawler.md` |
| API how-to with curl examples | `hermina-crawler/markdowns/05-runbooks/STATELESS_V2_API.md` |
| What changes for OneBox (read first) | `hermina-crawler/markdowns/05-runbooks/ONEBOX_V2_MIGRATION.md` |
| Exact request/response models | `hermina-crawler/apps/api/app_api/v2_crawl_schemas.py`, `v2_ai_schemas.py`, `v2_audit_schemas.py` |

Start with:

```bash
cd /Volumes/CodeCS/Ciptadra/onecloud
git fetch origin
git worktree add ../onecloud-voc-v2 -b feature/voc-crawler-v2 origin/feature/voc
cd ../onecloud-voc-v2/onecloud
```

Ignore `markdowns/multitenant-readiness/05-ONEBOX-HANDOFF.md` in the crawler repo: it is superseded. Do not build tenant provisioning, a pushed worklist, an outbox, a Setup Parameter page or a `snapshot_version` counter.

## 2. The v2 contract (what the crawler now offers)

Base path `/api/integration/v2`. Header `Authorization: Bearer <CRAWLER_API_TOKEN>` on every call: **one shared token for all sites**. Success bodies are `{"data": ..., "meta": {"api_version": "v2", "request_id": ...}}`; errors are `{"error": {"code", "message", "request_id"}}`. `site_id` (int >= 0) is only a label the crawler stores in its audit trail; send OneBox's site id.

**Start crawls** `POST /crawls` (optional `Idempotency-Key`, 8 to 128 chars)

```json
{"site_id": 169, "targets": [{"place_id": "ChIJ..."}], "mode": "delta",
 "date_from": "2026-10-20T00:00:00Z", "date_to": null, "max_reviews": 200, "sort_by": "newest"}
```

- `mode`: `backfill`, `delta` (default) or `range` (needs both dates). Dates are timezone-aware ISO. `max_reviews` 1 to 100000 (default 100). `targets` 1 to 50 distinct place ids. `sort_by`: `newest`, `most_relevant`, `highest_rating`, `lowest_rating`.
- `202`: `data = {"idempotent_replay": bool, "runs": [{"place_id", "crawl_id", "run_id", "status": "started"|"failed", "error": {"code","message"}|null}]}`. Keep the opaque `crawl_id`. The same `Idempotency-Key` returns the stored runs and starts no new paid Apify run.

**Read a crawl** `GET /crawls/{crawl_id}?cursor=&limit=` (limit 1 to 500, default 100; cursor is the previous `next_cursor`, none at first)

- `200`: `data = {"crawl_id","run_id","place_id","status","fetched_so_far","reviews":[...],"next_cursor","done"}`. `status` is `running`, `succeeded`, `failed`, `aborted`, `timed_out` or `unknown`. While running you get what the dataset holds so far with `done:false`; keep calling with `next_cursor`. `done:true` means final state and the end was served.
- Review fields: `source`, `external_review_id`, `external_place_id`, `reviewer_name`, `reviewer_profile_url`, `review_url`, `review_photo_urls`, `rating`, `review_text`, `review_time` (UTC, `Z`), `review_time_precision`, `date_approximate`, `is_edited`, `edited_at`, `owner_response_text`, `owner_response_time`, `review_hash`. There is **no** `id`, no `sync_updated_at`, no analysis inside a review.
- `review_hash` is identical to the one v1 gave the same review, provided the place id string is the same one v1 used (`Location.external_place_id`, in OneBox `Connection.Options.location.external_place_id` / `VocTarget.ExternalPlaceId`). A test on the crawler side proves it.

**Analysis** `POST /analysis`

```json
{"site_id": 169, "provider": "jev", "taxonomy": {"key": "...", "aspects": [...], "risk_flags": [...]},
 "reviews": [{"id": "r1", "review_hash": "...", "rating": 2, "text": "...", "reviewer_name": null}]}
```

- 1 to 50 reviews, unique `id` (echoed back). `taxonomy` is the same body OneBox already builds for the crawler (see `Library\VocTaxonomy::worklistKey(...)`), or `null` for legacy behaviour. `provider` optional (`jev`, `openai`, `absa`).
- `200`: `data = {"provider","model","summary":{"analyzed","rating_fallback","failed"},"usage":{"prompt_tokens","completion_tokens","total_tokens"},"results":[{"id","review_hash","status":"analyzed"|"rating_fallback"|"failed","corrected","analysis":{...}|null,"error":{...}|null}]}`. `analysis` carries `sentiment`, `issue_category`, `urgency`, `summary`, `recommended_action`, `tags`, ... with the same names `Library\VocAnalysisSchema` validates today. One failed review never fails the call.

**Reply suggestion** `POST /reply-suggestion`

```json
{"site_id": 169, "review_hash": "...", "text": "...", "taxonomy": {...full body...},
 "presets": [{"id": "mohon_maaf_waktu_tunggu", "when_to_use": "..."}], "thresholds": {"preset": 0.75}}
```

`200`: `data = {"mode": "preset"|"escalate"|"none", "preset_id", "confidence", "risk_flags", "language", "tokens_used", "model", "reason"}`: the same decision shape as v1.

**Audit** (optional for this task): `GET /audit/summary?site_id=&place_id=`, `POST /audit/reconcile` `{"site_id","place_id","review_hashes":[...],"since","limit"}`.

**Errors to handle:** `401 INVALID_SERVICE_TOKEN`; `503 V2_NOT_CONFIGURED` (token unset on the crawler); `503 APIFY_NOT_CONFIGURED` and `503 APIFY_ACCOUNTS_EXHAUSTED` (alert operations, do not retry fast); `429 APIFY_CONCURRENCY_LIMIT` with `Retry-After: 60` (wait, then retry); `502 APIFY_RUN_FAILED`; `404 CRAWL_NOT_FOUND`; `400 INVALID_CRAWL_ID`; analysis: `400 INVALID_TAXONOMY`, `503 PROVIDER_NOT_CONFIGURED`; reply: `502 SUGGESTION_FAILED`; audit: `503 AUDIT_UNAVAILABLE`.

## 3. What exists in OneBox today (from `origin/feature/voc`)

Line numbers are from that branch; re-check them.

| Concern | Where |
|---|---|
| HTTP client for the crawler | `onecloud/app/library/VoiceOfCustomerSystemClient.php`: `enqueueCrawl` (~766), `crawlBatch` (~972), `estimateCrawl` (~951), `probeCrawl` (~963), `fetchPage` (~194), `analyzePending` (~488), `analyzeReview` (~557), `replySuggestion` (~538); modes `api_mode=user|service`; mock mode; `serviceJson()` helper; `withRetry` |
| Enqueue (single path) | `onecloud/app/services/VocCrawlQueue.php` `enqueue(...)` (line ~60) builds targets from `VocConnectionRule::connectionsForSite()`, coverage `delta`/`date_window`/`full_backfill`, per-target date ranges, `clampBudget` (uses `estimateCrawl`), `review_quota_remaining`; also `enqueueSchedule` (~403), `probeChangedLocations` (~442), `clientForSite` (~480), watermark helpers (`watermarkFrom`, `narrowDateRanges`) |
| Callers of enqueue | `VocController.php` ~12845, ~14445, ~15656; `VocTask.php` ~190 |
| Batch status and import | `VocController::crawlImportAction` (~20525), `crawlAnalyzeAction` (~20736); `crawlBatch` call sites in `VocController.php` ~8186, ~15921, ~20565 and `VocTask.php` ~612; import state saved with `saveVocImportState` |
| Review ingest | `onecloud/app/services/Provider/VocProvider.php` `receive()` (~107 to ~370): pages via `fetchPage`, cursor in `Options._sync_cursor`, skips rows without `review_hash`, holds the cursor on failed rows, dead-letters poison rows, advances per-location watermarks with `\Service\VocTargetRegistry::advanceWatermarks` |
| Analysis | crawler-side: `VocController.php` ~1763, ~1983 (`analyzeReview`), ~20799/~20859 (`analyzePending`); OneBox-side engines also exist (`VocAnalysisEngine*`, `VocController.php` ~2019). Normalizer: `Library\VocAnalysisSchema` |
| Reply suggestion | `VocController.php` ~17698 (`analysisClient($siteId)->setTimeout(20)->replySuggestion(...)`), `Library\VocReplySuggestion::decide` (~17567) |
| Taxonomy bodies | `Library\VocTaxonomy::worklistKey()` (~93), `Library\VocCatalog` |
| Connection config | `Connection` rows: `Url`, `UserId`, `Password`, `Options` JSON (`api_mode`, `service_token`, `mock`, `location.external_place_id`, ...) |
| Existing checks | plain PHP scripts `onecloud/tests/voc/*_check.php` (no PHPUnit; see `onecloud/tests/voc/README.md`), a php -S fake `tests/voc/support/fake_crawler.php`, Docker e2e in `tests/voc/e2e/` (PHP 8.4, MySQL 5.7) |

## 4. What to build

Scope is **v2 as an opt-in path**. Keep every v1 behaviour byte-for-byte when the flag is off.

1. **Flag.** `Connection.Options.crawler_api` = `"v1"` (default) or `"v2"`, read through one helper (put it next to `VocConnectionRule`). v2 uses `Connection.Url` as the base URL and `Options.service_token` as the shared bearer token (same value on every connection of the crawler; do not build a new settings UI). Mock mode keeps working (extend the mock reader only if cheap).
2. **Client.** Add v2 methods (in `VoiceOfCustomerSystemClient` or a small new class in `library/` that reuses its HTTP helper and retry): `startCrawls`, `getCrawlPage`, `analyzeReviews`, `replySuggestionV2`, and optionally `auditSummary` / `auditReconcile`. Send `Idempotency-Key`. On `429` wait `Retry-After` (cap the total wait) and retry; map every error code of section 2 to the existing error style (see `VocCrawlQueue::classifyError`).
3. **Enqueue.** In `VocCrawlQueue::enqueue` (and `enqueueSchedule` through it), when the connections of the site have `crawler_api=v2`: build targets as `{place_id}` from the connection's `Options.location.external_place_id`; map coverage `full_backfill` -> `backfill`, `delta` -> `delta`, `date_window` -> `range`; `date_from`/`date_to` from the existing per-target ranges and watermark logic (reuse `narrowDateRanges`/`watermarkFrom`; inspect what safety margin they already apply and keep it; if none, subtract two days for `delta` since dedupe on `review_hash` absorbs the overlap); `max_reviews` from the existing budget. `clampBudget` uses `estimateCrawl`, which has no v2 equivalent: in v2 mode skip the clamp and use the target count OneBox already holds. Quota: v2 has no `review_quota_remaining`; clamp `max_reviews` to the remaining quota and stop ingesting once it is used up, so the existing quota behaviour is preserved. Use a stable idempotency key per (site, run, place). Return something the callers can store: keep `batch_id` semantics for v1; for v2 return a OneBox-side batch id that maps to the list of `{location_id, place_id, crawl_id}` (store it where the batch id is stored today; choose the smallest storage, and add a migration under `onecloud/app/migrations/` only if no existing JSON column fits; say what you chose and why).
4. **Import.** `crawlImportAction`, the `crawlBatch` call sites and `VocTask` (~612) must understand a v2 batch: poll each `crawl_id`; a place is ready when `status` is final and the pages are served. `VocProvider::receive` keeps its loop, but in v2 mode pages come from `getCrawlPage(crawl_id, cursor, limit)` instead of `fetchPage`, until `done`. Adapt for the row differences: log with `review_hash` instead of `id`; advance watermarks from `review_time` (no `sync_updated_at`); no analysis fields on the row. Keep: skip rows without `review_hash`, dedupe, hold the cursor on failures, dead letter. A run that stays uncollected for a long time must be reported (a log line and whatever alert mechanism the code already has), because Apify expires datasets after some days.
5. **Analysis (crawler-side path only).** Where OneBox calls `analyzePending` / `analyzeReview` with a crawler review id, in v2 mode send the new reviews (ingested, not yet analysed) to `POST /analysis` in batches of at most 50 with the taxonomy body from `VocTaxonomy`, and store each `results[].analysis` through `VocAnalysisSchema` into the same place v1 results go (same Meta fields). Keep failed reviews as "not analysed" for a later retry; add `usage.total_tokens` to whatever usage counter exists (look at `voc_benefit_usage_check.php`). The OneBox-side engines (`VocAnalysisEngine*`) are out of scope: do not change them.
6. **Reply suggestion.** In v2 mode call `POST /reply-suggestion` with `text` (the review text OneBox already has for that message), the full `taxonomy` body and the presets; `VocReplySuggestion::decide` and everything after it stay unchanged.
7. **v1-only features.** `estimateCrawl`, `probeCrawl` (used by `probeChangedLocations`), `crawlBatches`, `availableAnalysisModels`, `rollbackAnalyses`, `analysisQualitySummary`, `competitorReviews` have no v2 equivalent. In v2 mode do not call them: return a clear "not available in v2" result or a sensible local fallback, without breaking the UI. List what you did for each in your report.

## 5. Rules

- Follow the code style of the surrounding file (`array()` syntax, no new language features beyond what the file already uses, Indonesian comments where the file uses them, English identifiers).
- v1 stays the default and must keep working unchanged. Do not delete v1 code.
- Commits: small, one concern each, on `feature/voc-crawler-v2`. **Do not push.**
- No real crawler or Apify calls in tests. No secrets in the repo. Do not read or print real tokens.
- Do not modify the crawler repo. If you think the crawler API needs a change or hit a contract mismatch, stop and write it down in your report.
- Do not implement quota caps (Q-41), the Jev budget rule (Q-43) or any new UI: out of scope.
- If something is ambiguous and blocks you, ask the user one short question; otherwise decide, note the decision in your report and continue.

## 6. How to test

1. Build a **fake v2 crawler** next to the existing one (`tests/voc/support/fake_crawler_v2.php`, `php -S`) that implements `POST /crawls`, `GET /crawls/{id}`, `POST /analysis`, `POST /reply-suggestion` with the shapes of section 2: bearer check, idempotency replay, a run that is `running` then `succeeded` with several pages, a `429` with `Retry-After`, a failed review in an analysis batch, request logging to a file.
2. Add plain PHP checks in `tests/voc/` (follow the README: no PHPUnit, no `vendor/`), for example `voc_crawler_v2_client_check.php`, `voc_crawl_queue_v2_check.php`, `voc_provider_v2_check.php`, `voc_analysis_v2_check.php`. Cover: request bodies for each coverage mode, place id and date mapping, idempotency key stability, 429 backoff and retry, error mapping, paging with the cursor and `done`, dedupe and cursor hold on a bad row, watermark advance from `review_time`, analysis batching at 50 and failed-review retry, reply suggestion body, the flag defaulting to v1 and v1 requests being unchanged.
3. Run the existing VoC checks listed in `tests/voc/README.md` (and `tests/voc/e2e/run.sh` if Docker is available) before and after, and report any check that fails on the base branch so it is not blamed on you.
4. `php -l` every changed PHP file.

## 7. Definition of done

- With `crawler_api` unset or `v1`, behaviour and requests are unchanged (checks prove it).
- With `crawler_api=v2` on a connection, against the fake v2 crawler: a scheduled or manual crawl starts runs, the import reads all pages, reviews are deduplicated by `review_hash`, the cursor and watermarks advance, analysis results land in the same fields as before, a reply suggestion works.
- All new checks pass; the existing VoC checks give the same results as on the base branch.
- Committed on `feature/voc-crawler-v2`, not pushed.

## 8. Report back

When done, reply with: the branch and commit list; files changed; how each of sections 4.1 to 4.7 was done; the storage choice for crawl ids (and the migration if any); what you did for each v1-only feature; the exact commands to run the new checks and their output summary; anything not done, any assumption you made, and any problem in the crawler contract.
