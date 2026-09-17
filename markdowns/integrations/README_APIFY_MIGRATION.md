# Apify migration — developer README

Branch: `apify-migration` (pushed to origin, not yet merged). This is the
orientation doc for anyone picking up this branch cold. For the full design
rationale and decision log, see the other docs in this folder (linked
throughout); this one is "how it works and how to run it."

## What changed, in one paragraph

The crawler's review source used to be a real Chromium browser (Selenium)
scrolling Google Maps by hand — slow, fragile, and its IP-reputation/
fingerprint problems repeatedly capped crawls at ~5 reviews (see
`INCIDENT_P0_GOOGLE_MAPS_ONLY_5_REVIEWS.md`). Selenium is now deleted
entirely. Reviews come from an Apify actor
(`web_wanderer/google-reviews-scraper`) called over HTTP instead — no
browser, no IP problem, billed per review scraped.

## Where things live now

```
app/integrations/
  apify_client.py          low-level HTTP: start a run, poll it, page the dataset
  apify_token_pool.py       which of your (1-2) Apify accounts is active
  apify_review_parser.py    raw actor JSON -> the review dict every source client returns
  apify_review_client.py    orchestrates the three above into fetch_reviews()

app/services/
  apify_checkpoint_store.py records where a run stopped (not a resume point)
  apify_fetch_service.py    DB wiring: FetchLogService, ReviewService, CrawlFetchResult shape
```

Each file owns exactly one thing — see the table in
`MIGRATION_APIFY_REVIEW_SOURCE.md`'s "Modularization" section if you're
about to add a feature and aren't sure which file it belongs in.

## How a crawl actually flows

```
OneBox POST /integration/v1/crawl-jobs
  -> CrawlQueue.enqueue()                         (app/services/crawl_queue.py)
  -> CrawlWorker.execute_next()                   (app/services/crawl_worker.py)
  -> ApifyFetchService.fetch_location/fetch_competitor()
  -> ApifyReviewClient.fetch_reviews()
       -> ApifyCheckpointStore.resolve_effective_lower_bound()   (sort check only)
       -> ApifyClient.start_run() -> get_run_status() -> iter_dataset_items()
       -> ApifyReviewParser.parse_review() per item
  -> ReviewService.insert_review() per parsed review   (dedup + write to `reviews`)
```

`GET /integration/v1/reviews` (OneBox pulling data back out) is a completely
separate, unrelated path that reads straight from the `reviews` table — it
has zero knowledge of Apify and needed zero changes for this migration.

## Config you need to set

Nothing here is optional except the actor id (has a working default):

```
APIFY_API_TOKENS=token_for_account_1              # required - empty means every crawl fails
APIFY_API_TOKENS=token_for_account_1,token_for_account_2   # once account #2 exists
APIFY_ACTOR_ID=web_wanderer/google-reviews-scraper # default, only set to override
```

`APIFY_API_TOKENS` defaults to an empty list (`app/config.py`), which does
**not** crash the app at startup — it just makes every crawl fail
immediately with "all accounts exhausted." `scripts/deploy-apify.sh` warns
about this at deploy time if it's missing, but it won't block the deploy.

## The two-account rotation, the checkpoint, and what "resume" really means

> **Corrected 2026-09-17.** An earlier version of this section said an
> interrupted fetch "picks up from exactly where it left off" via a
> checkpoint. That was wrong, and the code that implemented it lost data.
> See `SPEC_FETCHJOBS_CRAWLER.md` B13.

What actually happens when account A runs out of credit mid-fetch:

1. `ApifyReviewClient` keeps whatever reviews were already parsed.
2. `ApifyTokenPool.rotate()` moves to account B (shared across every job in
   the worker process, so later jobs never retry an account already known
   to be exhausted).
3. The **same window** is re-run on account B. The lower bound is *not*
   moved: with `order: newest` the last review read is the **oldest** one,
   so advancing `anyDate` to it would ask only for reviews already in hand
   and skip every older review that was never read. Duplicates from the
   repeat are dropped by `seen_review_ids` and by DB dedup.
4. If B also runs out, the job ends `partial_success` with
   `stop_reason: source_quota_exhausted`.

The actor has **no offset and no upper date bound**, so there is no correct
way to resume a partially-read window. The `apify_resume_checkpoint`
column is still written, as a record of where a run stopped, but it no
longer narrows the next run. A retry repeats the window and pays for it
again; that is the honest cost.

Progress between crawls is tracked separately, by the crawler's own
coverage state on each location (`newest_crawled_at`, `oldest_crawled_at`,
`backfill_completed_at`, …). A `delta` crawl starts from
`newest_crawled_at` minus one day, and once a week from minus thirty days
as a safety sweep for late-published reviews.

An actor run that never confirms `SUCCEEDED` (failed, aborted, or past its
deadline) is **not** treated like account exhaustion: whatever the dataset
had is stored, but the job fails as retriable (or, past the deadline, as
permanent with `stop_reason: deadline_exceeded`) instead of telling OneBox
the target is done.

Runs are no longer waited on in-process: the worker starts the run, parks
the job (`awaiting_source`, shown to OneBox as `running`), and re-checks it
every 30 seconds. See `SPEC_FETCHJOBS_CRAWLER.md` CS-3.

## Database change

One nullable JSON column, `apify_resume_checkpoint`, on both `locations`
and `competitors` (migration `20260915_0008_add_apify_resume_checkpoint`).
That's the entire schema footprint of this migration — no new tables.

## Testing

```
python -m pytest tests/ -q --ignore=tests/test_real_integrations.py
```

139 passed, 2 skipped, as of this branch. Key test files:
`tests/test_apify_fetch_service.py` (the rotation/checkpoint behavior —
read this one first if you're touching that logic),
`tests/fixtures/apify_google_maps_reviews_sample.json` (4 real, diverse
records pulled from an actual actor run — use this instead of inventing
fixture data if you add a new mapped field).

## Deploying

`scripts/deploy-apify.sh` — same shape as `deploy-dev.sh`, pointed at this
branch instead of `dev`. It's a stopgap for testing this branch specifically
and should stop being needed once `apify-migration` merges into `dev`.

## What's NOT done yet (don't assume these work until verified)

- **Live-verified against a real Apify account as of this line**: field
  names `place_ids`/`limit`/`order`/`source`/`anyDate` are all real (the
  actor's live 400 responses confirmed which ones it accepts), and
  `source` specifically must be lowercase `"google"` — the actor's own
  docs page had this wrong as `"Googles"` at the time this branch was
  written, caught only once a real crawl hit it in production. Still not
  verified: a full successful run end-to-end (only the input validation
  has been exercised against a real account so far).
- **The exact 402/credit-exhaustion response shape is unverified.**
  `ApifyClient._is_credit_exhaustion()` checks for a 402 status or
  "credit"/"payment required"/"quota" in the error body — implemented from
  general Apify documentation, not a real exhausted-account response. This
  is exactly the trigger the whole rotation design depends on; test it for
  real before trusting a production crawl to fail over correctly.
- **`order`'s `lowest_rating` value is a guess** — not documented on this
  actor at all, kept as a snake_case placeholder consistent with the other
  three values.
- Field-naming inconsistencies between Apify's raw JSON and this repo's
  column names (all bridged internally, OneBox unaffected) are catalogued
  in `TECH_DEBT_ONEBOX_APIFY_FIELD_NAMING.md` for later reference.
- **Unexplained hang observed once in production, root cause unknown.**
  Crawl job 542 (2026-09-15, ~300-review target against a location with
  270 real reviews) fetched all 270 successfully — confirmed via
  `progress_fetched: 270`, which only gets written *after*
  `ApifyReviewClient.fetch_reviews()` already returned — but the job never
  reached a terminal status. The hang was therefore downstream of a
  successful fetch: somewhere in the per-review insert loop
  (`ApifyFetchService._store_reviews`, ~270 individual DB commits against
  Supabase), `FetchLogService.finish_log`, or `CrawlWorker._finish`'s own
  writes. No log capture was taken before the server was redeployed
  (which recreated the `crawl-worker` container), so the evidence is gone
  and this could not be root-caused. If it recurs, capture
  `docker compose logs crawl-worker --tail 200` and, if possible, a
  Supabase `pg_stat_activity` snapshot **before** redeploying or restarting
  anything — redeploying destroys the only evidence a stuck-mid-job hang
  leaves behind.

## Further reading

- `MIGRATION_APIFY_REVIEW_SOURCE.md` — the full design spec this branch was
  built from (architecture decisions, the complete column-mapping table,
  the non-goals that were deliberately left out).
- `APIFY_MIGRATION_EXECUTION_REPORT.md` — what the implementation run
  actually did, file by file, and its own gap list.
- `TECH_DEBT_ONEBOX_APIFY_FIELD_NAMING.md` — naming decisions worth
  revisiting on the OneBox side once there's access to make that change.
- `INCIDENT_P0_GOOGLE_MAPS_ONLY_5_REVIEWS.md` — why Selenium had to go.
