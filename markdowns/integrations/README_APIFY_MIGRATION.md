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
  apify_checkpoint_store.py persists/validates the "resume from here" cursor
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
       -> ApifyCheckpointStore.resolve_effective_lower_bound()   (where did we leave off?)
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

## The two-account rotation, and why it's not just "retry with token 2"

If you only remember one thing from this migration, make it this: **a
resume position is `(sort_by, review_time, review_id)`, never a bare
position/offset.** Position 150 under `newest` sort and position 150 under
`most_relevant` sort are two unrelated reviews — you cannot hand a
half-finished fetch from one account to the other unless both are using the
exact same sort order, and you have to track *which* order got you *how
far*.

What actually happens when account A runs out of credit mid-fetch:

1. `ApifyReviewClient` keeps whatever reviews were already parsed before the
   failure — nothing already fetched is thrown away.
2. `ApifyTokenPool.rotate()` moves to account B (shared across every job in
   the worker process — if job 1 in a batch discovers account A is dead,
   jobs 2 and 3 go straight to B, they never re-attempt a token already
   known exhausted).
3. The *same* actor call is re-issued on account B, with `anyDate` advanced
   to the last successfully parsed review's date — continuing, not
   restarting.
4. If B *also* runs out before the target count is reached, the job doesn't
   fail. It's marked `partial_success` (an existing, already-terminal status
   — nothing new invented) and a checkpoint —
   `{sort_by, review_time, review_id, recorded_at}` — is written to
   `apify_resume_checkpoint` on the `Location`/`Competitor` row itself.
5. The next time that target is crawled (next scheduled `regular_delta` run,
   a manual retry, whenever), `ApifyCheckpointStore.resolve_effective_lower_bound()`
   reads that checkpoint and picks up from exactly where it left off —
   automatically, with zero OneBox involvement (OneBox has no idea this
   checkpoint exists and doesn't need to).
6. **The one safety rule**: if a stored checkpoint's `sort_by` doesn't match
   what the new request wants, the checkpoint is discarded (logged) and the
   target restarts from scratch under the new sort. Splicing two different
   orderings together is treated as strictly worse than one wasted re-fetch.

A related but distinct case: an actor run that never confirms `SUCCEEDED`
at all (Apify reports it failed/aborted, or our own poll loop just gives up
waiting after `apify_run_timeout_seconds`). **This is deliberately NOT
treated the same as account exhaustion.** Account exhaustion is us choosing
to stop (we ran out of budget) and Apify never disputed that the data we
have is good, so calling it `partial_success` — "done, here's what we
got" — is accurate. A run that never confirmed `SUCCEEDED` is different:
Apify itself hasn't vouched for the data being complete, so we have no
basis to tell OneBox this target is finished, even if we already have
reviews in hand. Reporting a false "done" here risks a target getting
silently stuck at partial coverage indefinitely, since a `regular_delta`
crawl for an already-"finished" target may not get re-triggered for a
while.

So instead: whatever reviews the dataset already had (real data — Apify
pushes items incrementally as the actor scrapes) get stored, a checkpoint
gets saved either way, but the job is raised as `ApifyRunIncompleteError` →
a retriable **failure**, not a terminal success. `CrawlWorker`'s own retry
mechanism picks it up again, and because the checkpoint was already saved,
that retry resumes from where the incomplete run left off instead of
re-scraping the whole place from zero — that's the actual fix for "wasting
API calls" (a from-scratch retry would mean paying for a second full run on
reviews already scraped once), achieved without ever telling OneBox
something is finished that Apify didn't actually confirm. Only a run that
produced *zero* reviews and never confirmed success is treated as an
ordinary hard failure (no checkpoint to save, nothing to keep).

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
