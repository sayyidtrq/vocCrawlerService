# Fetch Jobs — coverage modes, timespan fetch, and quasi-realtime

**Status:** proposal, not yet approved. No code written.
**Audience:** OneBox devs (`onecloud`) and Crawler devs (`hermina-crawler`).
**Branch this assumes:** `apify-migration` (Selenium is gone; Apify is the
only review source).

This spec covers three capabilities requested for the Fetch Jobs screen
(`/feature/voc/Mediamonitoring/#/voc/fetchjobs`):

1. Fetch **all** reviews for a cabang.
2. Fetch reviews for a **specific timespan** for a cabang.
3. **Quasi-realtime** review pickup for a cabang.

In all three the user picks the cabang and the mode by hand. Nothing here
proposes automatic mode selection.

---

## 0. Decision summary

Read this section if you read nothing else.

| # | Decision | Why |
|---|---|---|
| D1 | **Ship the §1 data bug first, on its own.** ✅ *done — `include_personal`* | Every review we collected had a NULL reviewer name. Unrelated to this enhancement, so it did not wait for it. A second suspected bug (§1.2) was investigated and **withdrawn** — it was not real. |
| D2 | Replace "target review count" with an explicit **coverage intent** (`full_backfill` / `date_window` / `delta`). | The 300 number means three different things in three modes today, and none of them mean "all". |
| D3 | Use Apify's `place_reviews_count` as the **completeness oracle**. | It is on every dataset item and we already read it and then throw it away. It is the only way to answer "did we get everything?", which today we cannot answer at all. |
| D4 | The 300 cap is **entirely ours**. Delete it in four places; replace with a per-company cost budget. | The actor's `limit` accepts up to **100,000**. 300 was a Selenium survivability limit. |
| D5 | Full backfill **cannot be resumed mid-run** and therefore requires the worker to stop blocking on the Apify poll loop. | Confirmed against the actor's input schema: there is no offset and no upper date bound. See §7 Q1 — this is settled, not an open question. |
| D6 | Quasi-realtime = tight-interval delta polling gated by a **cheap change probe**. True realtime from Google Maps does not exist. | Google Maps has no review webhook. The only true-push option is the Google Business Profile API (§4.4), which is a different integration. |
| D7 | Date windows are **expensive in proportion to how old they are**, not how wide they are. | The actor has a lower date bound (`anyDate`) and no upper bound. `date_to` is enforced client-side after we have already paid to scrape. |

**Sequencing:** §1 ships independently and immediately. WP1–WP3 deliver
"fetch all" and "fetch timespan". WP4–WP6 deliver quasi-realtime. WP7 is the
cost guard and should land before WP1 is enabled in production, not after.

---

## 1. Live data bug, found while writing this spec — FIXED

Two were suspected. **One was real and is now fixed (§1.1); the other was
investigated and withdrawn (§1.2).** Both were found by diffing the actor's
real input schema against
[`app/integrations/apify_review_client.py`](../../app/integrations/apify_review_client.py);
only one survived being checked against real data.

This is **not** part of the enhancement and did not wait for it.

### 1.1 Every review we store has a NULL reviewer name — FIXED

The actor's input schema:

```
include_personal | boolean | default = false
    "If enabled, the actor will include personal information about the
     reviewer, such as name, user ID, and profile URL."
```

Our actor input
([`apify_review_client.py:106`](../../app/integrations/apify_review_client.py#L106))
never sets `include_personal`, so it defaults to `false`.

Confirmed across **2,920 real records from three separate actor runs**
(Five Coffee Forest 400, Astra Balikpapan 474, Astra TB Simatupang 2,046).
Not one record in any of them carries reviewer identity:

```
reviewer_name = 0/2920    reviewer_id = 0/2920    reviewer_url = 0/2920
```

Meanwhile `ApifyReviewParser.parse_review()` maps `reviewer_name`,
`reviewer_url`, `reviewer_photo_url` and `reviewer_reviews_count`
([`apify_review_parser.py:11-19`](../../app/integrations/apify_review_parser.py#L11)).
All four land as NULL.

**Impact:** a VoC ticket raised from a complaint has no customer name on it.
Staff cannot address the reviewer, and cannot tell a repeat complainant from
a first-timer.

**Fix (shipped):** `"include_personal": True` added to the actor input dict
in `ApifyReviewClient.fetch_reviews()`, covered by an assertion in
`tests/test_apify_fetch_service.py`.

**Standing privacy note.** This switches on collection of personal data
about identifiable people — reviewer name, id and profile URL. The project
owner authorised it directly, and it restores what the DB columns were
designed for and what the Selenium crawler already collected, so this is a
restoration rather than an expansion of scope. Recorded here so the decision
is traceable rather than buried in a diff. If PDP/compliance review later
objects, the revert is one key in the actor input.

**Backfill consideration, not yet decided:** every review collected before
this fix still has NULL reviewer fields. They do not repair themselves — a
re-crawl of those places is the only way to populate them, and dedup means a
plain re-crawl will match on `review_hash`/`external_review_id` and skip
them rather than update them. Decide whether reviewer identity on historical
reviews is worth an enrichment pass. Not part of WP0.

### 1.2 ~~Indonesian reviews stored as English translations~~ — WITHDRAWN, not a bug

**An earlier revision of this spec claimed we were storing English machine
translations instead of the patients' own words. That claim was wrong.** It
was inferred from the actor's schema text (`lang` defaults to `"en"`) plus
four fixture records that happened to be written in English. It was then
checked against real data and did not survive.

Kept here rather than deleted, because the wrong version was circulated and
because the verification method is the reusable part.

**What the real data shows.** Across 2,920 records from three actor runs:

| Field | Meaning |
|---|---|
| `content` | the **original** review text, always |
| `content_translated` | rendering into `lang`, empty when no translation was needed |
| `translated_language` | the target lang when a translation happened, else `None` |

```
content            : "cs tidak cepat tanggap, bagian claim asuransi tidak responsif"
content_translated : "CS is not responsive, insurance claims section is not responsive"
```

836 of 2,046 records in the Astra Simatupang run carry a translation, and in
every one of them the Indonesian original stays in `content`.
`ApifyReviewParser.parse_review()` reads `content`, so **it is already
correct** and needs no change.

The four fixture records that triggered the false alarm are from *Five
Coffee Forest* and have `content_translated: ""` with
`translated_language: None` — meaning no translation occurred, i.e. those
reviews were genuinely written in English.

**Do not set `lang: "id"`.** It would only change the language of
`content_translated`, which `parse_review()` does not store. It buys
nothing and costs actor work.

**One small real gap remains, unrelated to `lang`:** `content_language` is
`None` in all 2,920 records — the actor never populates it — so
`review_language` and `language` always store NULL. Fixing that means
deriving the language ourselves (or inferring "not `lang`" from
`translated_language` being set). Low priority, not a data-loss bug, and
explicitly **not** part of WP0.

**Method note for the team:** this is the third time on this integration
that Apify's own documentation has proven unreliable — after
`source: "Googles"` and the `newerThan`/`anyDate` naming. The rule that
keeps holding: **settle output-field semantics against a real dataset
export, never against the schema description.** A `json.load` over a saved
run costs a minute and would have caught this before it was written down.

---

## 2. How a fetch job works today

Traced end to end, so the bottleneck list in §3 can point at specific lines.

```
Fetch Jobs screen  (onecloud/app/views/Voc/fetchjobs.volt)
  mode select: delta | backfill | custom          :835-848
  target input, hard max 300                      :115, :1495
        |
        v  POST
VocController::crawlStartAction()                 :10528
  validates target against CRAWL_TARGET_MAX = 300  :67, :10549
  rejects source !== 'selenium'                    :10557   <-- stale
  crawlDateRange()  -> {from, to}                  :9057
  crawlSortBy()     -> forces 'newest' if ranged   :9044
  checks VOC_SCRAPE / VOC_REVIEW / VOC_AI quota    :10612
        |
        v
Service\VocCrawlQueue::enqueue()                  :42
  crawlMode()  -> custom_range | regular_delta     :171   <-- never backfill
  scanLimit()  -> max(500, target*10), cap 5000    :194   <-- dead downstream
  one mode + one date range for the WHOLE batch
  watermarkFrom() -> MIN(newest) across cabang     :321
        |
        v  POST /api/integration/v1/crawl-jobs
CrawlBatchCreateRequest / CrawlTargetRequest       (crawler)
  target_review_count  ge=1 le=300                 :37
  max_reviews_to_collect ge=1 le=300               :38
  scan_limit           ge=1 le=5000                :42
  crawl_mode  initial_backfill|regular_delta|custom_range  :43
        |
        v
CrawlQueue.enqueue() -> CrawlJob rows
        |
        v
CrawlWorker.execute_next()                        :152
  claim_next() reads crawl_mode + scan_limit       :140-147
  ... and never passes either one onward           :182-191   <-- dead
        |
        v
ApifyFetchService.fetch_location()                 :72
  validate_target(): min(crawl_max_target_reviews, 300)  :305
  also clamped by EntitlementService.review_quota()
        |
        v
ApifyReviewClient.fetch_reviews()                  :63
  del date_to   # "Apify has no actor-side upper bound"   :71
  actor_input: place_ids, limit, order, source, anyDate   :106
  ApifyClient.get_run_status()  blocks, 300s ceiling      :49
        |
        v
_store_reviews(): is_within_date_range() drops date_to violations  :278
```

The return path (`GET /integration/v1/reviews` → `VocProvider` → OneBox
`Message` rows) is untouched by this spec except for §3 B11.

---

## 3. Bottleneck inventory

Each item names the evidence. Items marked **[blocks fetch-all]** must be
resolved for capability 1; **[blocks timespan]** for capability 2;
**[blocks realtime]** for capability 3.

### B1. The 300 cap is duplicated in six places **[blocks fetch-all]**

| Where | Line |
|---|---|
| `VocController::CRAWL_TARGET_MAX` | `VocController.php:67` |
| `VocCrawlQueue::TARGET_MAX` | `VocCrawlQueue.php:26` |
| Fetch Jobs input `max="300"` | `fetchjobs.volt:115` |
| Fetch Jobs JS validation | `fetchjobs.volt:1495` |
| `CrawlTargetRequest` `le=300` ×2 | `integration_crawl_schemas.py:37,38` |
| `ApifyFetchService.validate_target` `min(setting, 300)` | `apify_fetch_service.py:305` |

Plus `EntitlementService.review_quota()` clamps further from
`Company.total_enable_review`.

The actor's own `limit` accepts **up to 100,000**, default 200. The 300 was
a Selenium survivability limit — a real browser scrolling Maps could not
reliably go deeper. It carries no meaning against an HTTP API billed per
review.

Note `apify_fetch_service.py:305` hardcodes `300` *next to* the
`crawl_max_target_reviews` setting, so raising the setting alone does
nothing. Anyone trying the obvious config fix will conclude the system
ignores its own configuration.

### B2. "Fetch all" cannot be expressed at any layer **[blocks fetch-all]**

`initial_backfill` exists in the contract at every level and has **never
been sent**. `VocCrawlQueue::crawlMode()` (`:171`) returns only
`custom_range` or `regular_delta` — the docblock at `:160-166` says so
explicitly and explains why (it needed a per-cabang Google review count,
which did not exist at the time).

That number now arrives on every Apify item as `place_reviews_count`. The
stated blocker is gone.

The UI's "backfill" mode (`fetchjobs.volt:840-843`) just sets `target = 300`
with no dates. For a place with 9,422 reviews that is 3% coverage,
presented to the user as "sedalam mungkin".

### B3. `crawl_mode` and `scan_limit` are wired but inert

`claim_next()` reads both into `ClaimedCrawlJob`
(`crawl_worker.py:141,146`). The `fetch_location()` call at `:182-191`
passes neither. `ApifyFetchService.fetch_location()` has no parameter for
either. They survive only as audit metadata via `_finish()`'s
`metadata.setdefault(...)` at `:357-362`.

`scan_limit` counted *review cards scanned in a browser*. It has no Apify
analogue and should be removed rather than left looking load-bearing.
`VocCrawlQueue::scanLimit()`'s careful `max(500, target*10)` arithmetic
(`:194`) computes a number nothing reads.

### B4. We compute the completeness oracle and discard it **[blocks fetch-all]**

`_capture_place_metadata()`
([`apify_review_client.py:218-228`](../../app/integrations/apify_review_client.py#L218))
stores `place_reviews_count` into `last_metadata["place_review_count"]` on
the first item. Verified present in the real sample:

```json
{"place_id": "ChIJ9fLOGgDraS4RRild036hTbY",
 "place_rating": 4.4, "place_reviews_count": 400}
```

Nothing reads it to decide whether a fetch is complete. Completeness is
instead inferred from `stored < requested_target`
(`apify_fetch_service.py:201-208`) — which is why asking for 300 against a
270-review place classifies a *complete* fetch as `partial_success`. That
mismatch is the same ambiguity that made job 542 hard to diagnose.

### B5. The poll timeout is shorter than a real backfill **[blocks fetch-all]**

`apify_run_timeout_seconds = 300` (`config.py:121`). `get_run_status()`
returns `"POLL_TIMEOUT"` at the deadline (`apify_client.py:61-69`), which
now raises `ApifyRunIncompleteError` → retriable failure.

A 5,000-review scrape does not finish in five minutes. With
`crawl_worker_max_attempts = 3` (`config.py:152`), a large backfill burns
three full actor runs and then fails permanently — **having paid for all
three**. Raising the 300-review cap without fixing this converts a capacity
limit into a billing leak.

### B6. The worker blocks on the poll loop; the lease is shorter than the work

`ApifyClient.get_run_status()` `time.sleep`s in-process
(`apify_client.py:70`). One worker process serves one job at a time
(`scripts/run_crawl_worker.py:31-38`).

`crawl_worker_lease_seconds = 900` (`config.py:151`). `claim_next()` treats
a `running` job whose lease expired as claimable (`crawl_worker.py:102-106`).
So **any run legitimately exceeding 15 minutes becomes re-claimable while it
is still running**, and a second worker starts a *second Apify run* for the
same cabang. Double billing, duplicate rows.

Today this is masked because the 300s poll ceiling (B5) fires first. Fix B5
without fixing this and the bug becomes reachable.

### B7. Date windows cost in proportion to age, not width **[blocks timespan]**

Confirmed against the actor input schema — the only date control is:

```
anyDate | string | "Scrape reviews newer than"
```

There is **no upper bound**. `fetch_reviews()` does `del date_to` at
`apify_review_client.py:71` and `_store_reviews()` drops out-of-range rows
client-side via `is_within_date_range()` (`:278`), counting them into
`total_skipped_out_of_range`.

So "reviews from Jan–Mar 2024" on a busy cabang scrapes **everything from
Jan 2024 to today** and discards ~90% of it after paying. A one-month window
two years back costs the same as a two-year backfill.

This is inherent to the actor and cannot be fixed in our code. It can only
be *priced* (warn the user) and *mitigated* (§4.3).

### B8. One mode and one date range per batch, shared across all cabang

`VocCrawlQueue::enqueue()` builds every target with the same `$dateFrom`
(`:88-94`). `watermarkFrom()` deliberately takes `MIN(newest)` across all
cabang (`:349-357`, rationale at `:308-312`) — correct for safety, but it
means **one lagging cabang forces all 50 to re-scrape from its date**.

Under Selenium that cost time. Under per-review billing it costs money,
linearly, every scheduled run.

The crawler contract **already supports per-target `date_from`/`date_to`**
(`CrawlTargetRequest.date_from`, `:48-49`) and `CrawlQueue.enqueue()`
already accepts a `target_date_ranges` dict keyed by location id. OneBox
simply never varies it. This is the cheapest high-value fix in this
document: it is a change to one loop in `VocCrawlQueue::enqueue()`, with the
receiving contract already in place.

### B9. The watermark margin's stated reason is now false

`WATERMARK_MARGIN_DAYS = 1` (`VocCrawlQueue.php:284`). The docblock explains
it compensates for `review_time` being *estimated from relative text*
("2 minggu lalu") — a Selenium artifact.

Apify returns `reviewed_at_date` as a real ISO timestamp
(`2026-04-23T00:00:00Z` in the sample). The imprecision it guards against no
longer exists.

**Do not delete the margin.** It is still needed, for a different reason:
`anyDate` only accepts `YYYY-MM-DD` and we truncate to a date at
`apify_review_client.py:119`, so sub-day precision is lost anyway. Keep the
margin; **rewrite the comment**. Leaving a correct constant with a false
justification is how the next person deletes it.

### B10. The 60-minute schedule floor is calibrated to Selenium **[blocks realtime]**

`VocCron::MIN_INTERVAL_MINUTES = 60` (`VocCron.php:32`). The docblock
justifies it: *"satu run bisa memakan sepuluh menit worker — pada 11 Agustus
2026 sebuah run bertarget 5 berjalan 619 detik."*

619 seconds for five reviews was a browser scrolling Google Maps. An Apify
delta run against a cabang with zero new reviews is one HTTP round trip plus
actor startup — seconds, not minutes.

The floor is the single blocker for quasi-realtime, and the measurement it
rests on describes a system that no longer exists. It must be
**re-measured against Apify**, not simply lowered on this argument.

### B11. The import cycle caps at 500 reviews **[blocks fetch-all]**

`VocProvider.php:98-99`:

```php
$pageSize = min(200, max(1, (int)($this->extras['page_size'] ?? 50)));
$maxPages = max(1, (int)($this->extras['max_pages'] ?? 10));
```

50 × 10 = **500 reviews per import call**, then `do…while ($hasMore && $page
<= $maxPages)` (`:252`) stops.

The crawler side caps a page at `MAX_LIMIT = 200`
(`integration_schemas.py:45`).

A 3,000-review backfill therefore needs six presses of the import button —
the UI does expose a `resume` flag (`crawlImportAction`, `resume` POST
param) but the user must keep clicking. Fetch-all is not usable until import
either auto-resumes or its caps are raised.

### B12. OneBox still rejects any source but `selenium`

`VocController.php:10557-10561` rejects `source` unless it is `''` or
`'selenium'`. Harmless today because the UI sends nothing, but it is a
tripwire: the first person who sends `source=apify` gets
*"Sumber apify belum didukung. Saat ini crawl hanya lewat Selenium."*

### B13. Resume advances the lower bound in the wrong direction **[blocks fetch-all]**

On account exhaustion (`apify_review_client.py:173-177`):

```python
if last_review is not None:
    lower_bound = parse_datetime(last_review.get("review_time")) or lower_bound
```

With `order: "newest"` the dataset arrives newest-first, so `last_review` is
the **oldest** row seen. Setting `anyDate` to it means *"give me reviews
newer than the oldest I already have"* — which is the set we just fetched.

The re-run therefore re-covers ground already paid for. `seen_review_ids`
(`:141-144`) filters the duplicates out, so `reviews` does not grow, and the
`while len(reviews) < limit` loop (`:103`) makes no progress until the
accounts exhaust or the limit is somehow met.

The same expression is used for the checkpoint written by `_save_checkpoint()`,
so a *resumed* job inherits the same wrong bound.

This is latent today (the common path is `SUCCEEDED` → `break` at `:149`)
but it is directly on the fetch-all path, and there is **no actor parameter
that would let it be fixed as written** — see D5 / §4.2.

### B14. Progress is reported exactly twice

`on_progress` fires at `(0, target, 0)` before the fetch and
`(len, target, len)` after (`apify_fetch_service.py:181-182`). The bar sits
at 0% for the whole run, then jumps to 100%.

For a ten-minute backfill that is indistinguishable from a hang — the exact
ambiguity that made job 542 unreadable. `iter_dataset_items()` is already a
generator (`apify_client.py:72`); per-page progress is nearly free.

---

## 4. Design

### 4.1 Coverage intent replaces target count

`target_review_count` currently means three different things depending on
mode, and none of them means "all". Replace it with an explicit intent plus
an optional cost ceiling.

```
coverage = full_backfill | date_window | delta
budget   = optional int, max reviews we are willing to PAY for (not a goal)
```

| Coverage | Bound sent to actor | Terminates when | User supplies |
|---|---|---|---|
| `full_backfill` | `limit = place_reviews_count` (or `budget`) | collected ≥ expected × tolerance | cabang only |
| `date_window` | `anyDate = date_from`, `limit = budget` | run SUCCEEDED, rows filtered to window | cabang + from/to |
| `delta` | `anyDate = watermark − margin` | run SUCCEEDED | cabang only |

`budget` is a **ceiling, not a target**. Hitting it is an abnormal outcome
that must be reported distinctly (`stop_reason: "budget_exhausted"`), never
folded into "success". This is the distinction that `partial_success`
currently blurs.

Backward compatibility, so OneBox and Crawler can deploy independently:

```
crawl_mode=regular_delta     -> coverage=delta
crawl_mode=custom_range      -> coverage=date_window
crawl_mode=initial_backfill  -> coverage=full_backfill
absent + no dates            -> coverage=delta
absent + dates               -> coverage=date_window
target_review_count          -> budget
scan_limit                   -> ignored, logged once per process
```

### 4.2 `place_reviews_count` as the completeness oracle

This is the load-bearing idea. Today "are we done?" is guessed from
`stored < requested_target`. Replace with:

```python
expected  = last_metadata["place_review_count"]   # already captured
collected = len(unique review_ids drained)
complete  = expected is not None and collected >= expected * COMPLETENESS_TOLERANCE
```

`COMPLETENESS_TOLERANCE` (suggest `0.98`, configurable) exists because
Google's displayed count and the scrapeable set genuinely disagree:
ratings-without-text are counted but not always returned, and deletions lag
the counter. Demanding exact equality would make every backfill report
incomplete forever.

What this fixes immediately:

- **"asked 300, place has 270, job never settles."** 270 ≥ 270 × 0.98 →
  complete → `succeeded`. Cleanly, with no special case.
- **A real partial is now distinguishable from a complete small place.**
  Today both look like `stored < requested`.
- **`full_backfill` becomes definable at all.** Without an expected count
  there is no terminating condition for "everything".

If `expected` is missing (zero-item dataset, or the actor changes the field)
fall back to today's behaviour and record `completeness: "unknown"` in
metadata. Never silently treat unknown as complete.

**Consequence of D5 — backfill must complete in one run.** The actor offers
no offset and no upper date bound (§7 Q1, settled). Combined with B13, there
is no way to resume a partially-drained backfill by narrowing `anyDate`. So
`full_backfill` must run as a **single actor run** with
`limit = expected`, and the run may take far longer than any lease we would
want to hold. That is what forces WP3.

Note this does **not** invalidate the existing checkpoint mechanism — it
remains correct and useful for `delta` and `date_window`, where the bound
genuinely moves forward in time. It simply cannot serve `full_backfill`.

### 4.3 Timespan fetch, and being honest about its cost

Per B7 the actor cannot be told an upper bound, so a window
`[from, to]` costs the same as `[from, now]`.

Do not hide this. Do three things instead:

1. **Estimate before spending.** With `expected` from a rating snapshot or
   the Places probe (§4.4), and the cabang's known review cadence, show the
   user *"perkiraan ~1.800 ulasan akan disisir untuk mendapat ~40 dalam
   rentang ini"* before the button does anything.
2. **Count and report the waste.** `total_skipped_out_of_range` already
   exists. Surface it in the Fetch Jobs history so the cost is visible after
   the fact, not only in the metadata blob.
3. **Prefer narrowing from the recent side.** A window ending today costs
   nothing extra. A window ending two years ago costs everything since. Say
   so in the UI hint next to the date picker.

There is one genuine optimisation available. `filter_stars` is in the actor
schema:

```
filter_stars | array | "Select one or more star ratings to filter reviews.
    When enabled, the sort order is automatically set to 'Newest'…"
```

For a VoC system, *"all 1–2 star reviews in this window"* is often the
actual question, and filtering server-side cuts the scraped volume by
roughly the share of low ratings (typically 10–20%). Worth exposing as an
optional filter on `date_window`. It is not required for the three
capabilities requested — treat it as a cheap follow-on, and note that it
forces `order=newest`, which our `date_window` path already uses.

### 4.4 Quasi-realtime

**True realtime does not exist for Google Maps reviews.** There is no
webhook. Apify's run webhooks fire when *our own run* finishes; they say
nothing about a new review appearing. Any spec that promises push here is
wrong.

The only genuine push path is the **Google Business Profile API**, which has
real review notifications over Pub/Sub. It requires verified ownership of
each location — which Hermina plausibly has for its own cabang, though not
for competitors. It is a separate integration with its own OAuth and quota
model. **Out of scope here, but it is the honest answer to "can we have real
realtime", and it should be evaluated on its own before anyone invests
further in tightening the polling loop.**

What is deliverable now is **gated tight-interval polling**:

```
every N minutes (N ~ 10-15):
    probe  = GooglePlacesClient -> userRatingCount        (cheap)
    if probe == last_seen_count:  skip entirely, cost 0
    else:                         enqueue a delta crawl   (Apify, billed)
```

The probe reuses what is already in the repo:
`app/integrations/google_places_client.py` already requests
`userRatingCount` in its field mask (`:40`) and the
`GOOGLE_MAPS_API_KEY` setting already exists. No new dependency, no new
credential.

Why the gate matters: without it, polling every 10 minutes means ~144 Apify
runs per cabang per day, nearly all of which return nothing. With it, we pay
Apify only when the count actually moved. Places API Details calls are
cheap and the count field sits in the lowest-cost SKU tier — but confirm
current pricing and the account's quota before committing to an interval.

Known limitation to state plainly: `userRatingCount` **does not move when a
review is edited, or when one is added and another deleted in the same
window.** The gate is an optimisation, not a correctness mechanism. Keep a
slower unconditional delta (the existing hourly schedule) underneath it as a
floor, so an edited review is picked up within the hour even though the
probe never fired.

---

## 5. Contract changes

### 5.1 `CrawlTargetRequest` (`apps/api/app_api/integration_crawl_schemas.py`)

```python
coverage: Literal["full_backfill", "date_window", "delta"] | None = None
budget: int | None = Field(default=None, ge=1, le=100_000)

# deprecated, still accepted, mapped in a validator:
target_review_count:    int | None  = Field(default=None, ge=1, le=100_000)
max_reviews_to_collect: int | None  = Field(default=None, ge=1, le=100_000)
crawl_mode: Literal[...] | None = None
scan_limit: int | None = None          # accepted, ignored
```

Validator rules:

- `coverage == "date_window"` requires at least one of `date_from`/`date_to`.
- `coverage == "full_backfill"` forbids `date_from`/`date_to` (a bounded
  backfill is a `date_window`; allowing both is how two modes silently
  become one).
- `coverage` absent → derive from `crawl_mode`, then from presence of dates,
  per §4.1.
- `le=300` → `le=100_000` on all count fields.

### 5.2 `CrawlFetchResult` metadata additions

```python
"coverage": "full_backfill" | "date_window" | "delta",
"expected_review_count": int | None,      # place_reviews_count
"collected_unique": int,
"completeness": "complete" | "partial" | "unknown",
"completeness_ratio": float | None,
"budget": int | None,
"stop_reason": ... | "budget_exhausted" | "coverage_complete",
```

### 5.3 OneBox side

- `VocCrawlQueue::enqueue()` — accept per-target date ranges instead of one
  shared range (B8); emit `coverage` instead of deriving `crawl_mode`.
- `VocCrawlQueue::crawlMode()` — replaced by the caller's explicit choice.
- `VocCrawlQueue::scanLimit()` — delete (B3).
- `VocController::CRAWL_TARGET_MAX` — becomes a budget ceiling, not 300.
- `VocController::crawlStartAction()` — drop the `selenium` source check
  (B12).

### 5.4 Config (`app/config.py`)

```python
apify_run_timeout_seconds: int = 300      # -> per-coverage, see WP3
apify_backfill_deadline_seconds: int = 7200   # new: wall-clock, not poll
crawl_worker_lease_seconds: int = 900     # must exceed the longest run
crawl_completeness_tolerance: float = 0.98    # new
crawl_max_target_reviews: int = 300       # -> 100_000
```

---

## 6. Work packages

Each is independently reviewable and shippable. Dependencies are stated.
Formatted for delegation: exact files, exact change, how to verify, what not
to touch.

---

### WP0 — Fix the live data bug ✅ DONE

**Shipped:** `"include_personal": True` in the actor input dict,
`app/integrations/apify_review_client.py`, plus an assertion in
`tests/test_apify_fetch_service.py`. Suite green (141 passed, 2 skipped).

`"lang": "id"` was **not** shipped — see §1.2, that diagnosis was withdrawn
after checking real data. `ApifyReviewParser` already reads the original
text correctly and was left untouched.

**Still open, deliberately deferred:** reviewer fields on reviews collected
*before* this fix stay NULL (§1.1, "backfill consideration"), and
`review_language`/`language` still store NULL because the actor never
populates `content_language` (§1.2, "one small real gap").

**Remaining verification:** one real crawl against a live cabang confirming
`reviewer_name` now arrives populated. The fix is asserted at the
actor-input layer, which is where the bug was, but it has not yet been seen
end to end against production Apify.

---

### WP1 — Remove the 300 cap, introduce `coverage` and `budget`

**Depends on:** nothing. **Blocks:** WP2, WP3.

**Files:**
- `apps/api/app_api/integration_crawl_schemas.py` — §5.1
- `app/services/apify_fetch_service.py:300-314` — `validate_target()`: drop
  the hardcoded `300`, honour `crawl_max_target_reviews`, keep the
  entitlement clamp but report it as `budget`, not as the target
- `app/config.py` — §5.4
- `onecloud`: `VocController.php:67`, `VocCrawlQueue.php:26`,
  `fetchjobs.volt:115,1495`

**Verify:** `tests/test_integration_crawl_jobs.py` — a request with
`budget=5000` is accepted; `budget=100001` is rejected; a legacy request
carrying `target_review_count=300` and no `coverage` still behaves exactly
as today.

**Do not touch:** the fetch loop, the checkpoint store, `ReviewRepository`.

---

### WP2 — Completeness oracle

**Depends on:** WP1. **Blocks:** WP3.

**Files:**
- `app/integrations/apify_review_client.py` — surface
  `expected_review_count` and `collected_unique` in `last_metadata`
- `app/services/apify_fetch_service.py:200-212` — replace the
  `stored < requested_target` partial-classification with the §4.2 rule
- `app/config.py` — `crawl_completeness_tolerance`

**Verify:** new tests in `tests/test_apify_fetch_service.py`:
- 270 collected, `place_reviews_count = 270`, requested 300 → `success`,
  `completeness: "complete"` *(this is the job-542 shape and is the
  acceptance test for this WP)*
- 100 collected, `place_reviews_count = 5000` → `partial_success`,
  `completeness: "partial"`
- `place_reviews_count` absent → `completeness: "unknown"`, old behaviour

**Do not touch:** `ApifyRunIncompleteError` semantics. A run Apify never
confirmed is still not a completed fetch, regardless of what the count says.
The two mechanisms are orthogonal and must stay that way.

---

### WP3 — Stop blocking the worker on the Apify poll loop

**Depends on:** WP1, WP2. This is the largest package.

**Problem:** B5 + B6 + D5. A backfill cannot be resumed, so it must run to
completion in one actor run, which can exceed both the 300 s poll ceiling
and the 900 s lease.

**Design:** split the job into two phases with a queue hop between them.

```
Phase A  claim -> ApifyClient.start_run()
         persist run_id + dataset_id on the CrawlJob
         status = "awaiting_source", available_at = now + poll_interval
         RELEASE the lease and return

Phase B  claim -> read run status
         RUNNING   -> reschedule (available_at = now + poll_interval)
                      unless now > started_at + backfill_deadline
         SUCCEEDED -> drain dataset, store, apply WP2, finish
         else      -> existing ApifyRunIncompleteError path
```

**Files:**
- `app/db/models.py` + a migration — `CrawlJob.source_run_id`,
  `source_dataset_id`, `source_started_at`
- `app/services/crawl_worker.py` — new `awaiting_source` status in
  `claim_next()` and `_refresh_batch_status()`'s terminal set
- `app/integrations/apify_review_client.py` — split `fetch_reviews()` into
  `start_fetch()` / `resume_fetch()`
- `app/services/apify_fetch_service.py` — thread the two phases through

**Also fixes:** B6 (the lease no longer has to outlive the run) and B14
(Phase B can report real progress each time it polls).

**Verify:** a fake client whose run reports `RUNNING` three times then
`SUCCEEDED` must produce exactly one `start_run` call and one stored result;
assert the job returned to the queue between polls and that no second actor
run was started.

**Do not touch:** the `partial_success` / `ApifyRunIncompleteError`
distinction settled on the `apify-migration` branch.

**Cheaper interim** — if WP3 cannot be scheduled soon, raising
`apify_run_timeout_seconds` to ~3600 and `crawl_worker_lease_seconds` above
it unblocks *single-cabang manual* fetch-all today. The ceiling it leaves:
the batch is fully serial, so "fetch all, all 50 cabang" is one worker ×
50 runs back to back, and a crashed worker holds a job for the whole lease.
Ship the interim knowingly, not as the answer.

---

### WP4 — Per-cabang date ranges in OneBox *(cheapest high-value item)*

**Depends on:** nothing. Independently shippable.

**File:** `onecloud/app/services/VocCrawlQueue.php:60-102`

**Change:** compute the watermark **per cabang** and set each target's own
`date_from`, instead of one `MIN()` across the batch (B8). The receiving
contract already supports it — `CrawlTargetRequest.date_from` and
`CrawlQueue.enqueue(target_date_ranges=...)` both exist and are already
wired.

Keep the "a cabang with zero reviews cancels narrowing" rule
(`VocCrawlQueue.php:367-371`) — but apply it to *that cabang only*, not to
the whole batch.

**Verify:** a two-cabang batch where A is current and B is a month behind
must send two different `date_from` values.

**Impact:** directly proportional saving on every scheduled run. On a
50-cabang site with one lagging cabang this is the difference between
re-scraping 50 cabang from last month and re-scraping one.

---

### WP5 — Change-detection probe

**Depends on:** nothing. **Blocks:** WP6.

**Files:**
- `app/integrations/google_places_client.py` — add a `review_count(place_id)`
  method; the field mask at `:40` already requests `userRatingCount`
- new `app/services/review_count_probe.py` — cache last-seen count per
  location, return `changed: bool`
- `app/db/models.py` — `Location.last_probed_review_count`,
  `last_probed_at`

**Verify:** probe returns `changed=False` on an unchanged count without
issuing any Apify call. Assert the Apify client is never constructed on the
unchanged path — that assertion *is* the cost saving.

**Do not touch:** `GooglePlacesClient.fetch_reviews()`. It stays unused as a
review source; only the count is being borrowed.

---

### WP6 — Quasi-realtime schedules

**Depends on:** WP5, and honestly on WP3 (tight intervals with a blocking
worker will queue up behind each other).

**Files:**
- `onecloud/app/library/VocCron.php:32` — lower `MIN_INTERVAL_MINUTES`
- `onecloud/app/views/Voc/schedules.volt` — expose the tighter presets
- scheduler path — call the probe before enqueueing

**Before lowering the floor:** re-measure actual Apify delta-run wall time
for a cabang with zero new reviews, across ~20 runs. Set the floor from that
measurement plus headroom. The existing 60 comes from a 619-second Selenium
run (B10) and must not simply be replaced with another guess.

**Verify:** a schedule at the new interval against an unchanged cabang
completes with zero Apify runs and a `skipped_no_change` run record.

---

### WP7 — Cost guard and preflight estimate *(land before WP1 reaches prod)*

**Depends on:** WP2 for `expected_review_count`.

Removing a 300-review cap without a spend guard is how a single click
becomes a large invoice.

**Files:**
- new `app/services/crawl_budget_service.py` — per-company monthly review
  budget, checked at enqueue and enforced during drain
- new endpoint `GET /integration/v1/crawl-jobs/estimate?location_id=` —
  returns `expected_review_count` from the last rating snapshot or the WP5
  probe
- `fetchjobs.volt` — show *"perkiraan ~9.422 ulasan"* and require explicit
  confirmation above a threshold

**Verify:** a `full_backfill` whose estimate exceeds the remaining budget is
rejected at enqueue with a distinct error code, **before** any actor run
starts.

Note OneBox already has `VOC_SCRAPE`/`VOC_REVIEW`/`VOC_AI` benefit quotas
(`VocController.php:10612`) counted **per call, not per review**
(`:10633` counts targets). Under per-review billing that unit is now wrong.
Decide whether to extend the existing benefit system or keep the crawler-side
budget separate — do not build a second quota system by accident.

---

### WP8 — Cleanup

**Depends on:** WP1–WP3 landed.

- Delete `scan_limit` end to end: `VocCrawlQueue::scanLimit()`,
  `CrawlTargetRequest.scan_limit`, `ClaimedCrawlJob.scan_limit`,
  `_finish()`'s `metadata.setdefault("scan_limit", …)`.
- Remove the `selenium` source check (`VocController.php:10557`).
- Rewrite the `WATERMARK_MARGIN_DAYS` docblock per B9 — **keep the constant,
  replace the justification.**
- Fix or delete the wrong-direction resume bound at
  `apify_review_client.py:173-177` (B13). After WP3, `full_backfill` no
  longer uses it; confirm what `delta` and `date_window` actually need
  rather than preserving it by default.

---

## 7. Open questions

**Q1 — resume/offset support in the actor. SETTLED, answer is no.**
Pulled from the live input schema
(`GET /v2/acts/web_wanderer~google-reviews-scraper/builds/default`): the
full property list is `include_personal, place_urls, place_ids, anyDate,
lang, filter_stars, limit, order, source, searchKeyword, search,
search_limit, search_location, search_coordination, sort_dataset, sort_keys,
sort_order`. There is **no offset, no cursor, and no upper date bound**.
`limit` maxes at 100,000. This is what forces D5/WP3.

**Q2 — privacy sign-off on `include_personal`. RESOLVED.** Authorised
directly by the project owner; shipped. Standing note recorded in §1.1 so
the decision stays traceable.

**Q3 — which field carries the original-language text. RESOLVED, and it
invalidated the bug it was asked about.** `content` holds the original in
all 2,920 records checked; `content_translated` holds the `lang` rendering.
The parser was already correct. See §1.2 — the proposed `lang: "id"` fix was
withdrawn rather than shipped.

**Q4 — Places API cost and quota at a 10-minute interval.** WP5/WP6. Needs
the actual GCP billing tier for this project, not list pricing.

**Q5 — is Google Business Profile API viable for Hermina's own cabang?**
Determines whether WP6's polling is a stopgap or the permanent answer. Worth
answering before investing further in the polling path (§4.4).

**Q6 — benefit quota unit.** WP7. Per-call quotas predate per-review
billing. Product decision.

**Q7 — what does `lowest_rating` actually do.** Still unverified from the
`apify-migration` branch, though the schema now confirms it is a valid
`order` enum value. Low priority.

---

## 8. Explicitly out of scope

- Changing `GET /integration/v1/reviews` or its cursor contract. The pull
  path stays as is, except for B11's page caps.
- Competitor crawls. The same mechanisms apply, but competitors are not part
  of the three requested capabilities and add an eligibility path
  (`_execute_competitor`, `crawl_worker.py:233`) that would double the test
  matrix.
- The OneBox-side field renaming catalogued in
  `TECH_DEBT_ONEBOX_APIFY_FIELD_NAMING.md`.
- Google Business Profile API integration (§4.4) — named, not specced.
- Automatic mode selection. The user picks the cabang and the mode, per the
  original requirement.

---

## 9. Suggested sequencing

```
done     WP0   include_personal data bug       (shipped, suite green)

now      WP4   per-cabang date ranges          (independent, pure saving)

then     WP1   remove cap, coverage + budget
         WP2   completeness oracle             (fixes the job-542 shape)
         WP7   cost guard                      (BEFORE WP1 reaches prod)

then     WP3   async run phases                (unblocks real fetch-all)

then     WP5   change probe
         WP6   quasi-realtime schedules

last     WP8   cleanup
```

Capability 1 (fetch all) lands with WP3. Capability 2 (timespan) is usable
after WP1+WP2 and improves with WP4. Capability 3 (quasi-realtime) lands
with WP6.
