# Migration: Selenium → Apify as the review source

**Status:** implementation brief for Codex. This supersedes the earlier
draft of this same file (which targeted the wrong seam — see "Corrected
finding" below). Read this whole document before writing code; several
sections depend on each other (the rotation design, the result-shape
contract, and the decommission list all touch the same files).

## Goal

Replace `SeleniumGoogleMapsReviewClient` as the review source that OneBox's
crawl-job flow (use case 1 below) fetches from. The Selenium worker is being
**decommissioned outright**, not kept as a fallback mode — its IP-reputation
and browser-fingerprint problems are structural (see
`INCIDENT_P0_GOOGLE_MAPS_ONLY_5_REVIEWS.md`) and not worth carrying forward.

## Non-goals (explicitly out of scope — do not build these)

- **No place-rating history table.** Place-level aggregates (`place_rating`,
  `place_reviews_count`) stay exactly as ephemeral as they are today —
  computed per-crawl and surfaced only in that run's `CrawlBatch` metadata.
  If a later feature wants historical trend data, it will be derived from
  `reviews` rows at read time, not stored as its own table.
- **No child tables for one-to-many review fields** (photos, categories).
  Store them as JSON array columns / inside `raw_payload`. Nothing today
  queries individual review photos.
- **No round-robin load spreading across the two Apify accounts.** The
  rotation described below is *failover only* — use account #1 until it's
  exhausted, then fail over to account #2. Do not build a load balancer.
- **No live progress streaming during an Apify run.** Selenium's
  `on_progress` fired per scrolled card because a human was watching a
  browser scroll. Apify runs as a bounded background job — call `on_progress`
  once at start and once when the dataset is fully fetched. Do not poll the
  dataset mid-run just to animate a progress bar.
- **Use case 2 (OneBox pulling reviews out) needs no changes.** Audited:
  `GET /integration/v1/reviews` (`apps/api/app_api/routers/integration_reviews.py`)
  reads only from `reviews`/`review_analysis` via `IntegrationReviewService`
  and has no dependency on which client filled those tables.

## The two OneBox-facing flows (for orientation, not touched by #2)

```
1. OneBox --(POST crawl-jobs)--> crawler service --(actor call)--> Apify
                                       |                              |
                                       +------ stores in reviews <----+

2. OneBox --(GET /integration/v1/reviews)--> crawler service --> reads reviews table --> OneBox stores as tickets
```

Flow 2 is confirmed fine as-is. Everything below is about flow 1.

## Corrected finding: where the client actually plugs in

An earlier pass at this migration assumed `FetchService._build_client()`
(picked by `settings.review_source_mode`) was the swap point. **It is not,
for the path OneBox actually drives.** The real chain is:

```
apps/api/app_api/routers/integration_crawl_jobs.py  (OneBox enqueues a CrawlJob)
  -> app/services/crawl_queue.py                     (CrawlQueue.enqueue)
  -> app/services/crawl_worker.py: CrawlWorker.execute_next()
  -> fetch_service_factory (HARDCODED to SeleniumFetchService, crawl_worker.py:51)
  -> app/services/selenium_fetch_service.py: SeleniumFetchService._run_fetch()
  -> app/integrations/selenium_google_maps_client.py: SeleniumGoogleMapsReviewClient.fetch_reviews()
```

`FetchService`'s `review_source_mode` switch only serves the older
synchronous `/fetch-jobs` endpoint and dry-runs — not this queue path.

`SeleniumFetchService._run_fetch()` also calls its client with a contract
built for **live browser scrolling**, which has no Apify equivalent and
should not be carried forward:

```python
client.fetch_reviews(
    crawl_target, limit=..., on_progress=..., keep_check=...,
    sort_by=..., scan_limit=..., time_limit_seconds=...,
)
```

- `keep_check(raw_review) -> "keep"|"skip"|"stop"` is a per-card callback
  that decides whether to keep scrolling, used because Google Maps has no
  server-side date filter and Selenium had to early-stop mid-scroll once it
  scrolled past the requested date range.
- `scan_limit` / `time_limit_seconds` bound a live scrolling session.

**None of this exists for Apify.** The chosen actor
(`zen-studio/google-maps-reviews-scraper`) takes the review cap and a
date cutoff as *actor input* and returns an already-bounded, finished
dataset — there is nothing to scroll or stop mid-way. Reuse the shared
result-shape and dedupe/status logic in `_run_fetch`; drop `keep_check`,
`scan_limit`, and `time_limit_seconds` from the new client contract
entirely.

## Plan: modify in place, don't duplicate 150 lines

`CrawlTarget` (`app/services/crawl_target.py`) and `CrawlFetchResult` /
`CrawlResultMetadata` (`app/services/crawl_result.py`) are already
source-agnostic dataclasses/TypedDicts — no changes needed there beyond
optionally adding a couple of new optional metadata keys (see below).

Rather than hand-writing a parallel `ApifyFetchService` from scratch,
**rename and simplify `SeleniumFetchService` in place**:

1. Rename `app/services/selenium_fetch_service.py` →
   `app/services/apify_fetch_service.py`, class `SeleniumFetchService` →
   `ApifyFetchService`.
2. In `_run_fetch`, delete the `keep_check`/`_nilai_rentang` closure and the
   `scan_limit`/`time_limit_seconds` params entirely. Keep everything else:
   the `CrawlFetchResult` shape, the per-review `insert_review` loop with
   inserted/duplicate/failed counting, the `is_within_date_range` post-filter
   (still needed — the actor's `newerThan` is a lower bound only, there's no
   upper-bound date param, so `date_to` filtering still happens client-side
   exactly as it does today), the `ReviewSourceError` → `failed`/
   `failure_code`/`retriable` handling, and the `fetch_log_service.finish_log`
   call.
3. Replace the `self.client.fetch_reviews(...)` call with:
   ```python
   raw_reviews = self.client.fetch_reviews(
       crawl_target, limit=requested_target, sort_by=sort_by,
       date_from=date_from, date_to=date_to,
   )
   ```
4. `validate_target()` currently reads `self.settings.selenium_max_target_reviews`
   — rename that setting to something source-neutral (e.g.
   `crawl_max_target_reviews`) since Selenium is going away; keep the same
   default value and behavior.
5. Update every call site:
   - `app/services/crawl_worker.py:51` — `fetch_service_factory` default
     lambda now builds `ApifyFetchService`.
   - `apps/api/app_api/routers/fetch_jobs.py:82-95` — the
     `source in {"selenium", "selenium_google_maps"}` branch becomes
     `source in {"apify", "apify_google_maps"}` (or just always use
     `ApifyFetchService` if `FetchService`'s other modes — mock,
     google_places — are still wanted for that endpoint; keep those, only
     replace the Selenium branch).
   - `apps/api/app_api/routers/pipeline.py:84-98` — same swap.
   - `app/terminal/fetch_menu.py` — same swap.
   - Grep for stragglers before calling this done:
     `rg -n "SeleniumFetchService|SeleniumGoogleMapsReviewClient|selenium_google_maps" --type py`

## New components

### `app/integrations/apify_client.py` — low-level API wrapper

Thin wrapper around the Apify REST API. No review-domain knowledge here —
just HTTP, auth, polling, and pagination.

- `start_run(actor_id: str, input: dict, *, token: str) -> str` — `POST
  https://api.apify.com/v2/actors/{actor_id}/runs` with `Authorization:
  Bearer {token}`, JSON body = actor input. Returns the run's
  `defaultDatasetId` (needed to fetch items) and run id.
- `get_run_status(run_id: str, *, token: str) -> str` — poll until
  `SUCCEEDED`/`FAILED`/`ABORTED`/`TIMED-OUT`.
- `iter_dataset_items(dataset_id: str, *, token: str) -> Iterator[dict]` —
  `GET https://api.apify.com/v2/datasets/{dataset_id}/items?format=json&limit=&offset=`,
  paginate by `offset`/`limit` until an empty page. This is the piece that
  makes the "we don't know the review count ahead of time" problem
  irrelevant — keep paging until the API returns nothing more, no upfront
  count needed.
- 429 handling: exponential backoff (start ~500ms, double each retry, cap
  attempts) on the *same* token — this is a per-second rate limit, not an
  account-exhaustion signal, so it must not trigger token rotation.
- 402 / credit-exhaustion handling: raise a distinguishable
  `ApifyAccountExhaustedError` so the caller (the token pool) can rotate.

**Verification step before finalizing this file (do first):** the exact
402 error shape and any Apify-specific "insufficient credits" error `type`
string were not confirmed against a live response while writing this doc —
only against general web documentation. Make one real run against a
throwaway/free-tier-exhausted scenario (or read
`GET /v2/users/me/usage/monthly` beforehand to know how close an account is
to its cap) and confirm the exact status code/body before wiring the
rotation trigger to it. Getting this wrong either double-runs on a dead
account or rotates away from a perfectly good one on an unrelated error.

### `app/integrations/apify_token_pool.py` — account rotation only (no checkpoint knowledge)

Single responsibility: know which token is active and fail over to the next
one. It has no idea what a "review" or a "sort order" is — that's the
checkpoint module's job (below). Keeping these separate is deliberate: the
pool would otherwise become the one class every future Apify feature has to
touch.

- Config-driven ordered list of tokens (see Config section). Today exactly
  one token is configured; the pool must work unmodified when a second is
  added later.
- In-memory only, one instance shared by every `ApifyReviewClient` call
  within the long-lived `crawl-worker` process — no DB-backed rotation
  state. `scripts/run_crawl_worker.sh` runs a single worker process, so
  process-lifetime memory is enough; don't build cross-process coordination
  that nothing asks for.
- Sharing matters for correctness, not just convenience: if job 1 in a
  batch of 3 place IDs discovers account A is exhausted, jobs 2 and 3 must
  see that immediately and go straight to account B — never re-attempt a
  token already known dead. This is why the pool instance must be
  constructed once per worker process (e.g. held on `ApifyFetchService` or
  passed in at construction) and not rebuilt per job.
- `ApifyTokenPool`:
  - `current() -> str` — returns the active token.
  - `rotate() -> str | None` — marks the current token exhausted, advances
    to the next configured token, returns it (or `None` if every configured
    token is exhausted).
- `ApifyClient` accepts the pool, not a raw token: on
  `ApifyAccountExhaustedError` from the current token, call `rotate()` and
  retry the *same* request once per remaining token before giving up and
  raising `ApifyAllAccountsExhaustedError` (a new, distinct exception —
  the caller needs to tell "this one request needs a retry" apart from
  "there is no account left to try at all," and they require different
  responses, see the checkpoint design below).

## The account-rotation edge case: resuming mid-crawl without losing your place

This is the part that needs care, and it's the reason the rotation design
isn't just "retry with the next token."

**The scenario:** a batch enqueues 3 place IDs. Account A has enough budget
for place 1 and place 2, then runs out partway through fetching place 3's
reviews (or between jobs — same problem either way, see below). We rotate
to account B for the rest. Two things must hold:

1. **Nothing already fetched is lost or re-spent on.** Whatever reviews
   account A already returned for place 3 before dying get inserted like
   normal — they're real data, not discarded because the run didn't finish.
2. **Account B must continue from exactly the same position, under the
   exact same sort order.** If account A was fetching `reviewsSort=newest`
   and had gotten down to (say) a review from `2026-06-01`, account B must
   also fetch `reviewsSort=newest` starting from `2026-06-01` onward — not
   restart from the top (wasted budget, duplicate rows) and not silently
   fall back to some other sort (Apify has no cross-account session
   concept; a differently-sorted request from account B has no relationship
   to "how far account A got" — position 150 in `newest` order is a
   completely different review than position 150 in `mostRelevant` order).
   **If the sort order can't be confirmed to match, the safe move is to
   throw the mismatch away and restart the target from scratch under the
   newly requested sort — never attempt to splice two different orderings
   together.**

So the resume cursor cannot be "the Nth review" (position is
sort-dependent) — it must be `(sort_by, review_time, review_id)`: the sort
order that produced it, plus the timestamp to resume from under that same
order, plus the exact review id to protect against timestamp ties.

**This also has to survive past a single job attempt.** If account A *and*
account B are both exhausted before place 3's target is reached, the crawl
does not get to finish today — but it must not silently look "done" either.
The checkpoint has to be durable enough that the *next* time this location
is crawled (the next scheduled `regular_delta` run, a manual retry, or
simply next month once Apify credits reset), the crawler picks up from
`2026-06-01` under `newest` instead of re-fetching everything from today
back to `2026-06-01` again. OneBox has no idea this checkpoint exists or
needs to — it just eventually sees a location catch up to fully synced over
however many crawl cycles it takes. This is why the checkpoint must be
**persisted on the target itself** (`locations`/`competitors` table), not
just held in a job's transient `result_json`.

### DB change: `apify_resume_checkpoint` column

Add one nullable `JsonType` column to both `Location` and `Competitor`
(`app/db/models.py`), same pattern as `raw_payload`/`rating_snapshot`
elsewhere in this codebase — no new table:

```python
apify_resume_checkpoint: Mapped[dict | None] = mapped_column(JsonType)
```

Shape (all four keys always present together, or the column is `NULL`):

```json
{
  "sort_by": "newest",
  "review_time": "2026-06-01T09:14:41Z",
  "review_id": "Ci9DQUlRQUNvZENodHljRjlvT2...",
  "recorded_at": "2026-09-15T02:00:00Z"
}
```

Write an Alembic migration following the existing naming convention (see
`alembic/versions/20260826_0007_add_location_ai_config.py` for the pattern)
adding this column to both tables.

### `app/services/apify_checkpoint_store.py` — the second module, owns persistence + validation

Single responsibility: read/write/validate the checkpoint. Knows about the
DB (via `session_factory`, same pattern as `ReviewRepository`) and about
`CrawlTarget`'s `kind`/`id`, but nothing about HTTP or tokens.

- `load(crawl_target) -> ApifyCheckpoint | None`
- `save(crawl_target, checkpoint: ApifyCheckpoint) -> None`
- `clear(crawl_target) -> None` — call this once a fetch for that target
  completes *without* hitting account exhaustion (i.e. it reached the
  requested count, or the actor genuinely had nothing more to return) —
  the target is caught up, the checkpoint no longer means anything.
- `resolve_effective_lower_bound(crawl_target, requested_sort_by, requested_date_from) -> tuple[str, datetime | None]`
  — the one function `ApifyReviewClient` actually calls. Logic:
  - No stored checkpoint → return `(requested_sort_by, requested_date_from)`
    unchanged.
  - Stored checkpoint exists and `checkpoint.sort_by == requested_sort_by`
    → return `(requested_sort_by, max(requested_date_from, checkpoint.review_time))`
    (whichever lower bound is more restrictive wins — never fetch *less*
    than what OneBox asked for, but never re-fetch what's already
    checkpointed either).
  - Stored checkpoint exists but `checkpoint.sort_by != requested_sort_by`
    → **log a warning naming both sort values, discard the checkpoint
    (`clear()`), and return `(requested_sort_by, requested_date_from)`
    unchanged.** This is the explicit "don't silently desync" behavior —
    it costs one wasted re-fetch of the target from scratch, which is
    strictly better than corrupting the result by pretending two different
    orderings are comparable.

### `ApifyReviewClient.fetch_reviews()` — putting it together

1. Ask `apify_checkpoint_store.resolve_effective_lower_bound(...)` for the
   real `sort_by`/`newerThan` to use.
2. Call the actor via `apify_client` using the current token from
   `apify_token_pool`.
3. On `ApifyAccountExhaustedError` mid-run: keep whatever items were already
   paged from `iter_dataset_items` before the failure, call
   `apify_token_pool.rotate()`, and if a token remains, re-issue the *same*
   actor call with `newerThan` advanced to the last item just fetched (same
   sort, same place) — continuing, not restarting.
4. If `rotate()` returns `None` (every token exhausted) and the target
   count has not been reached: this is **not** a hard failure. Save a
   checkpoint via `apify_checkpoint_store.save(...)` using the last
   successfully fetched item's `(sort_by, review_time, review_id)`, return
   whatever reviews were collected so far, and set a flag on the client
   (e.g. `self.last_metadata["stopped_reason"] = "apify_accounts_exhausted"`)
   for `ApifyFetchService` to read.
5. If the target count *was* reached, or the actor returned fewer items
   than requested with no exhaustion involved (genuinely no more reviews
   exist), call `apify_checkpoint_store.clear(...)` — the target is caught
   up.

### `ApifyFetchService._run_fetch()` — reusing existing status semantics, not inventing new ones

When `last_metadata.get("stopped_reason") == "apify_accounts_exhausted"`,
set `result["status"] = "partial_success"` — **this status already exists**
and `CrawlWorker._refresh_batch_status` already treats it as terminal (no
automatic retry loop burning attempts on something a retry can't fix
anyway). Set `result["metadata"]["stop_reason"]` via the existing
`stop_reason()` helper in `crawl_result.py` so it surfaces through
`CrawlBatch` the same way every other stop reason already does — this is
the "flag/mark where we stand" requirement, and it's satisfied by reusing
plumbing that's already wired end to end, not by adding a new job/batch
status.

### `app/integrations/apify_review_parser.py` — JSON → normalize_review contract

Pure mapping functions, mirroring the role of
`app/integrations/google_maps_review_parser.py`. Output must match exactly
what `FetchService.normalize_review()` (`app/services/fetch_service.py:109`)
already expects from any client — this contract does not change:

```python
{
    "source": "apify_google_maps",
    "external_place_id": ...,
    "external_review_id": ...,
    "reviewer_name": ...,
    "reviewer_profile_url": ...,
    "reviewer_photo_url": ...,
    "reviewer_local_guide_level": ...,
    "reviewer_total_reviews": ...,
    "rating": ...,
    "review_text": ...,
    "review_time": ...,
    "review_relative_time": ...,
    "review_language": ...,
    "language": ...,
    "like_count": ...,
    "owner_response_text": ...,
    "owner_response_time": ...,
    "scraped_at": ...,
    "raw_payload": {...the full dataset item...},
}
```

### `app/integrations/apify_review_client.py` — the `ReviewSourceClient`

```python
def fetch_reviews(self, crawl_target, limit, sort_by="newest",
                   date_from=None, date_to=None) -> list[dict]:
```

1. Build actor input:
   - `placeIds: [crawl_target.external_place_id]`
   - `maxReviewsPerPlace: limit`
   - `reviewsSort:` map `sort_by` 1:1 — `newest→newest`,
     `most_relevant→mostRelevant`, `highest_rating→highestRanking`,
     `lowest_rating→lowestRanking` (these are the exact four values
     `CrawlTargetRequest.sort_by` already accepts in
     `apps/api/app_api/integration_crawl_schemas.py:53-55`, so this is a
     straight rename, not a new enum).
   - `newerThan:` derived from `date_from` if given (actor accepts an ISO
     date string or a rolling window like `"7 days"`; pass the ISO date).
     There is no actor-side upper bound — `date_to` is still enforced by
     `ApifyFetchService`'s existing post-fetch `is_within_date_range` filter.
   - `reviewsOrigin: "google"` (first-party only — matches what Selenium was
     scraping; the actor's `"all"` option would pull syndicated/third-party
     reviews we've never ingested before and don't want silently mixed in).
2. Call `apify_client.start_run(...)`, poll to completion, page through
   `iter_dataset_items(...)`.
3. Map each item through `apify_review_parser`, return the list.
4. Populate `self.last_metadata` (read by `_run_fetch`, mirroring what
   `SeleniumGoogleMapsReviewClient.last_metadata` provided) with at least:
   `place_rating`, `place_review_count`, `rating_snapshot_at` (so the
   existing `RatingSnapshot`/`rating_snapshot()` plumbing in
   `crawl_result.py`/`crawl_batch_view.py` keeps working unmodified), plus
   new keys worth adding to `CrawlResultMetadata` (all optional,
   `total=False` already): `apify_run_id`, `apify_dataset_id`,
   `apify_account_index_used`.
5. `self.source_name = "apify_google_maps"` (read by `_run_fetch` for the
   `result["source"]` field and for `generate_review_hash` vs
   `generate_selenium_review_hash` selection in
   `FetchService.normalize_review` — since the source name is no longer
   `"selenium_google_maps"`, it will correctly take the `generate_review_hash`
   path, which hashes on `external_review_id` — fine, since Apify's
   `review_id`-equivalent field is stable across runs).

**Confirmed, not inferred:** the field names below were checked directly
against a real `.json` export of this actor's dataset (400 real review
records, not the actor's marketing-page example — that example used
completely different field names, `reviewId`/`publishedAtMicros`/`author`,
and was discarded as unreliable). The JSON keys are snake_case and match
the CSV export 1:1, with nested objects/arrays preserved instead of
flattened: `location: {lat, lng}`, `rating_stats: {five_star, four_star,
three_star, two_star, one_star}`, `address: [...]`, `categories: [...]`,
`review_photos_urls: [...]`. No further verification call is needed before
writing `apify_review_parser.py`.

**Naming clash to be careful of:** the raw item's own `location` key (lat/lng
coordinates) is unrelated to this codebase's `Location` model or the
`location` field OneBox's own review JSON exposes (the hospital branch
name). Keep the raw item's `location` nested exactly as-is inside
`raw_payload["location"]` — never hoist it to a top-level key anywhere it
could be confused with branch identity. See
`TECH_DEBT_ONEBOX_APIFY_FIELD_NAMING.md` for the fuller naming-divergence
writeup (informational for later OneBox work, not something to act on in
this repo).

## Column mapping (JSON, confirmed against a real export)

| Apify JSON field | `apify_review_parser` output key | `reviews` table column | Notes |
|---|---|---|---|
| — (constant) | `source` | `source` | Literal `"apify_google_maps"` |
| `place_id` | `external_place_id` | `external_place_id` | Same Google Place ID format `Location.external_place_id` already stores |
| `review_id` | `external_review_id` | `external_review_id` | Stable ID — `generate_review_hash` dedupes on it |
| `reviewer_name` | `reviewer_name` | `reviewer_name` | Falls back to `"Anonymous"` in `normalize_review` if empty |
| `reviewer_url` | `reviewer_profile_url` | `reviewer_profile_url` | |
| `reviewer_photo_url` (fallback `reviewer_photo`) | `reviewer_photo_url` | `reviewer_photo_url` | |
| `is_local_guide` (bool) | `reviewer_local_guide_level` | `reviewer_local_guide_level` | `true` → `"Local Guide"`, else `None` — same values Selenium's parser already wrote |
| `reviewer_reviews_count` | `reviewer_total_reviews` | `reviewer_total_reviews` | Already an int — no regex parsing needed |
| `rating` | `rating` | `rating` | Already a `1-5` int |
| `content` | `review_text` | `review_text` | Empty string if the review has no text |
| `reviewed_at_date` (ISO 8601) | `review_time` | `review_time` | Absolute timestamp — passes straight through `parse_datetime` |
| `reviewed_at` (`"4 months ago"`) | `review_relative_time` | `review_relative_time` | Display parity only; `review_time` above wins in `_resolve_review_time` |
| `content_language` | `review_language` / `language` | `review_language` / `language` | Apify gives this directly, no `"unknown"` placeholder needed; both DB columns get the same value (they've never had distinct meaning in this codebase — see `google_maps_review_parser.py:94-95`) |
| `likes_count` | `like_count` | `like_count` | Already an int |
| `owner_response` | `owner_response_text` | `owner_response_text` | |
| `owner_response_at_date` (ISO 8601) | `owner_response_time` | `owner_response_time` | Use the absolute field, not the relative `owner_response_at` |
| `scraped_at` | `scraped_at` | `scraped_at` | Already an ISO timestamp |
| *(entire dataset item)* | `raw_payload` | `raw_payload` | Full item for traceability, same pattern as the Selenium client |

Place-level fields (`place_rating`, `place_reviews_count`,
`rating_stats/*`) feed `last_metadata`/`RatingSnapshot`, not a `reviews`
column — see Non-goals.

Unmapped and intentionally left inside `raw_payload` only (no DB column,
nothing downstream reads them — YAGNI): `address`, `categories`, `category`,
`cid`, `city`, `content_translated`, `country`, `fid`, `full_address`,
`knowledge_graph_id`, `neighborhood`, `phone`, `place_name`,
`place_photo_url`, `postal_code`, `review_photos_urls`, `review_position`,
`review_url`, `reviewer_id`, `reviewer_photos_count`, `state`, `street`,
`translated_language`, `visited_in`, `website`.

## Hashing

`generate_review_hash` (`app/utils/hashing.py`), not
`generate_selenium_review_hash` — selected automatically because
`source != "selenium_google_maps"`. No change needed there.

## Config changes (`app/config.py`)

- `apify_api_tokens: list[str]` — parsed from a comma-separated
  `APIFY_API_TOKENS` env var (mirror the pattern used for any other
  comma-separated list setting already in this file, if one exists; if not,
  a simple `.split(",")` + strip-empty in a field validator is enough).
  Today's `.env` sets exactly one token; the list type is what lets a second
  be added later with zero code changes.
- `apify_actor_id: str` — default `"zen-studio/google-maps-reviews-scraper"`.
- `apify_run_timeout_seconds`, `apify_poll_interval_seconds` — reasonable
  defaults (e.g. 300s timeout, 5s poll interval); expose as settings since
  they'll need tuning once real run durations are observed.
- Rename `selenium_max_target_reviews` → `crawl_max_target_reviews` (used by
  `validate_target`, source-neutral now).
- Remove the now-dead `selenium_*` settings block once
  `selenium_google_maps_client.py` is deleted (see decommission list) —
  don't leave unused config lying around.
- `review_source_mode`: decide whether `"selenium"` is deleted from
  `REVIEW_SOURCE_MODES` now or left as a recognized-but-unused value during
  a short transition. Given the worker is being taken down outright (per
  the user's instruction), prefer deleting it — no dead mode strings.

## Error handling / retry classification (must match `crawl_worker.py`'s existing contract)

`CrawlWorker._is_permanent_source_failure()` checks
`metadata.get("failure_code")` and `metadata.get("retriable") is False`.
Preserve this exactly — but note that **all-accounts-exhausted is deliberately
NOT routed through this path** (see above): it becomes `partial_success`
with a checkpoint saved, not a `failed` job, because there's a real, useful,
non-empty result to keep and a well-defined way to continue later. Reserve
`ReviewSourceError(retriable=False, ...)` for failures a checkpoint can't
help with:

- Place ID invalid / actor can't resolve it at all → permanent, not
  retriable — no checkpoint applies since nothing was ever fetched.
- Actor run failed/aborted for a place-not-found-style reason → treat like
  Selenium's existing "target not found" permanent failures if an
  equivalent code exists; otherwise treat as retriable (transient Apify-side
  failure).
- 429 / rate-limit-exceeded → retriable (already handled by the client's own
  backoff before it ever surfaces as an exception) — never triggers token
  rotation, see `apify_client.py` above.

## Modularization (DRY / single-responsibility — hand these boundaries to Codex as-is)

Six small modules, each owning exactly one concern, so a future change
(e.g. a third Apify account, a different actor, a different rotation
policy) touches one file instead of a tangle:

| Module | Owns | Does NOT know about |
|---|---|---|
| `apify_client.py` | HTTP calls, polling, pagination, 429 backoff | tokens beyond "use this one," reviews, checkpoints |
| `apify_token_pool.py` | which token is active, rotation on exhaustion | HTTP, reviews, checkpoints |
| `apify_checkpoint_store.py` | persisting/validating the resume cursor | HTTP, tokens, review field mapping |
| `apify_review_parser.py` | raw JSON item → `normalize_review` input dict | HTTP, tokens, checkpoints, the DB |
| `apify_review_client.py` | orchestrates the above four into `ReviewSourceClient.fetch_reviews()` | DB session lifecycle, `CrawlJob`/`CrawlBatch` |
| `apify_fetch_service.py` | DB session lifecycle, `FetchLogService`, `ReviewService`, `CrawlFetchResult` shape | Apify HTTP/token/checkpoint internals — it only calls `client.fetch_reviews(...)` |

The `sort_by` mapping (`newest`/`most_relevant`/`highest_rating`/
`lowest_rating` ↔ Apify's `newest`/`mostRelevant`/`highestRanking`/
`lowestRanking`) is needed in exactly two places — building actor input in
`apify_review_client.py`, and comparing a requested sort against a stored
checkpoint's sort in `apify_checkpoint_store.py`. Define it once (a single
module-level dict, e.g. in `apify_review_client.py`, imported by the
checkpoint store) rather than restating the four-way mapping twice.

## Testing plan for Codex to run before calling this done

1. Unit tests for `ApifyTokenPool.rotate()` — single token (no-op path,
   still works with the current 1-account setup), two tokens (rotates once,
   then reports exhausted), zero remaining tokens (returns `None`).
2. Unit tests for `apify_review_parser` against a fixture built from the
   real JSON sample (not invented data) — confirm every mapped column above
   round-trips correctly.
3. Unit test confirming `ApifyFetchService`'s `CrawlFetchResult` shape
   matches what `crawl_worker.py` reads (`status`, `metadata`,
   `error_message`, `total_fetched`, `total_inserted`, `total_duplicate`,
   `total_failed`, `total_skipped_out_of_range`) — reuse/adapt the existing
   `tests/test_selenium_scraping.py` assertions on this shape.
4. **Checkpoint/rotation tests — this is the part most likely to have a
   subtle bug, test it explicitly:**
   - Both accounts exhausted partway through one place's fetch → result is
     `partial_success`, a checkpoint row is saved with the correct
     `(sort_by, review_time, review_id)` from the last item actually
     fetched, and previously-fetched items for that place were inserted
     (not discarded).
   - A second run against the same target with a stored checkpoint and the
     *same* `sort_by` → `resolve_effective_lower_bound` returns the
     checkpoint's `review_time`, not the originally requested `date_from`
     (when the checkpoint is more restrictive).
   - A second run against the same target with a stored checkpoint but a
     *different* `sort_by` → the checkpoint is discarded (logged), the
     fetch restarts from the originally requested `date_from`, and
     `clear()` is called.
   - A run that reaches its target/exhausts naturally (no account
     exhaustion involved) → checkpoint is cleared, not left stale from a
     previous partial run.
5. One real smoke test against a known place (Hermina Bogor) with a small
   `maxReviewsPerPlace` (e.g. 5) end to end: enqueue → worker picks it up →
   confirm rows land in `reviews` with the mapped columns populated
   correctly.
6. `rg -n "SeleniumFetchService|SeleniumGoogleMapsReviewClient|selenium_google_maps" --type py` returns nothing outside of the incident/history markdown files.

## Decommission checklist (do this last, once the Apify path is verified working end to end)

- `app/integrations/selenium_google_maps_client.py` — delete.
- `app/services/selenium_fetch_service.py` — already renamed away in step
  above, nothing left to delete here.
- `tests/test_selenium_scraping.py` — delete or repoint to
  `apify_review_client`/`apify_review_parser`/`ApifyFetchService`.
- `undetected-chromedriver` — remove from `requirements.txt`, regenerate the
  lock the same way it was added.
- `Dockerfile` — remove the `chromium`/`chromium-driver`/`xvfb`/`xauth`
  install block and its pinning comments.
- `docker-compose.yml` — remove the `crawlerservice_selenium-profile` named
  volume and any `SELENIUM_PROFILE_VOLUME` env wiring.
- `scripts/setup_selenium_profile.py` — delete.
- Selenium settings in `app/config.py` — delete (see Config changes above).
- Mark `INCIDENT_P0_GOOGLE_MAPS_ONLY_5_REVIEWS.md` as resolved/historical
  with a pointer to this document, rather than deleting it — it's the record
  of *why* this migration happened.
