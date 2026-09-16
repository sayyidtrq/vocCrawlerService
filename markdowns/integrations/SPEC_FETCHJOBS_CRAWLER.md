# Fetch Jobs enhancement — Part 2 of 2: Crawler Service

**Repo:** `hermina-crawler` · **Branch assumed:** `apify-migration`
**Paired with:** [`SPEC_FETCHJOBS_ONEBOX.md`](SPEC_FETCHJOBS_ONEBOX.md) — Part 1, the OneBox half
**Contract version defined here:** `crawl-jobs v2`
**Status:** proposal. CS-0 is shipped; CS-1 onward is not started.

---

## Sync rules — read before editing either document

These two documents describe one change split across two repos. They drift
the moment someone edits one and not the other.

1. **This document owns the contract** (§5). The crawler serves
   `POST /api/integration/v1/crawl-jobs`, so the field list, types and
   validation rules are defined here and nowhere else. The OneBox document
   carries a *caller's view* of the same contract, explicitly marked as
   derived. **If you change §5, update the OneBox document's §5 in the same
   commit.**
2. **The pairing table (§8) must be byte-identical in both documents.** It
   is the only place the cross-repo ordering is recorded.
3. **Accept before emit.** The crawler must accept a new contract field in
   production *before* OneBox starts sending it. Reversing this produces a
   422 from a Pydantic model with `extra="forbid"` — see §5.3.
4. Bump the contract version string in both documents when §5 changes
   shape.

---

## 0. Shared decisions

Identical in both documents. Full rationale for the crawler-side ones is in
§4 below; OneBox-side rationale is in Part 1 §4.

| # | Decision | Owner |
|---|---|---|
| D1 | Ship the §1 data bug first, alone. ✅ done | Crawler |
| D2 | Replace "target review count" with explicit **coverage intent** (`full_backfill` / `date_window` / `delta`) plus an optional cost **budget**. | Both |
| D3 | Use Apify's `place_reviews_count` as the **completeness oracle**. | Crawler |
| D4 | The 300-review cap is entirely ours — the actor accepts up to **100,000**. Remove it in all six places. | Both |
| D5 | Full backfill **cannot be resumed mid-run**, so the worker must stop blocking on the Apify poll loop. | Crawler |
| D6 | Quasi-realtime = tight-interval delta polling gated by a cheap change probe. True realtime does not exist for Google Maps. | Both |
| D7 | Date windows cost in proportion to how **old** the window is, not how wide. Unfixable; must be priced and surfaced. | Both |

---

## 1. Live data bug — FIXED (CS-0)

Two were suspected. One was real and is fixed; the other was investigated
and withdrawn. Both were found by diffing the actor's real input schema
against
[`app/integrations/apify_review_client.py`](../../app/integrations/apify_review_client.py);
only one survived contact with real data.

### 1.1 Every review had a NULL reviewer name — FIXED

The actor's input schema:

```
include_personal | boolean | default = false
    "If enabled, the actor will include personal information about the
     reviewer, such as name, user ID, and profile URL."
```

We never sent it, so it defaulted to `false`.

Confirmed across **2,920 real records from three separate actor runs**
(Five Coffee Forest 400, Astra Balikpapan 474, Astra TB Simatupang 2,046).
Not one record in any of them carries reviewer identity:

```
reviewer_name = 0/2920    reviewer_id = 0/2920    reviewer_url = 0/2920
```

`ApifyReviewParser.parse_review()` maps four reviewer fields
([`apify_review_parser.py:11-19`](../../app/integrations/apify_review_parser.py#L11))
and every one of them was landing NULL. A VoC ticket raised from a complaint
had no customer attached to it.

**Fix (shipped, commit `c96a883`):** `"include_personal": True` in the actor
input dict in `ApifyReviewClient.fetch_reviews()`, with an assertion in
`tests/test_apify_fetch_service.py`.

**Standing privacy note.** This switches on collection of personal data
about identifiable people. The project owner authorised it directly, and it
restores what the DB columns were designed for and what the Selenium crawler
already collected — a restoration, not an expansion of scope. Recorded here
so the decision is traceable rather than buried in a diff. The revert is one
key in the actor input.

**History repair — FIXED, via re-crawl.** Reviews collected before this fix
had NULL reviewer fields and, on their own, would never recover: dedup
matched them on `review_hash` / `external_review_id` and *skipped* the
incoming row, discarding the name it now carried.

`insert_review_optimistically()` (`app/services/review_repository.py`)
now takes an `enrich` hook, called with the existing row whenever a
duplicate is found. Both `ReviewService` and `CompetitorReviewService` pass
one that calls `backfill_missing_fields()`, which fills the five
`BACKFILLABLE_FIELDS` (`reviewer_name`, `reviewer_profile_url`,
`reviewer_photo_url`, `reviewer_local_guide_level`,
`reviewer_total_reviews`) **only where they are currently empty**.

Properties that matter:

- **Never overwrites.** A later crawl that happens to come back without a
  name cannot erase one we already have. Safe to run repeatedly.
- **Still counted as a duplicate.** No row is inserted; `total_duplicate`
  is unchanged, so crawl stats and OneBox's view are unaffected.
- **No separate script.** Repairing a cabang's history = re-crawling it.
  Each cabang heals the next time it is crawled at a depth that reaches its
  old reviews — a `delta` crawl only reaches recent ones, so older history
  needs a deeper (`date_window` / `full_backfill`) crawl.
- Covered by
  `test_recrawl_backfills_missing_reviewer_name_without_overwriting`,
  mutation-checked: removing the hook fails that test on the name assertion.

**Getting the repair to OneBox.** OneBox keeps its own copy and only
re-pulls a review when `GET /integration/v1/reviews` re-serves it. That
cursor is keyset over **`sync_updated_at`** (not `updated_at`), and the
column deliberately has no `onupdate=` — "every writer sets it explicitly"
(`models.py:391-396`). So `ReviewService`'s hook bumps `sync_updated_at`
whenever it actually fills something, using the same
`clock_timestamp()`/`now()` expression as `AnalysisService` to keep keyset
ordering intact. Without that bump the crawler DB would be repaired and
OneBox would never know. The test asserts the watermark advances on repair
and does **not** advance on a no-op; both assertions were mutation-checked.

`CompetitorReview` has no `sync_updated_at` and does not flow to OneBox
tickets, so its hook only fills the columns.

**What OneBox then displays — partly fixed, partly not.** The Ulasan screen
resolves the name as `ContactName ?: Meta.reviewer_name ?: 'Anonim'`
(`VocController.php:3365`, `:4828`, `:7896`). OneBox's re-import path
(`VocProvider::perbaruiReviewTersimpan`) merges the new `reviewer_name` into
`Meta`, so:

| Review state in OneBox | After re-crawl + import |
|---|---|
| Not yet made into a ticket (no Contact) | ✅ real name shown, from `Meta` |
| Already a ticket (Contact exists) | ❌ still "Anonymous" |

The second row fails because import stamps the message sender with the
literal name `'Anonymous'` when `reviewer_name` is empty
(`VocProvider.php:907-908`); the Contact born from it when the review is
made into a ticket inherits that name, and a non-empty `ContactName`
shadows `Meta`. **That is a OneBox fix — Part 1 OB-0.**

### 1.2 ~~Reviews stored as English translations~~ — WITHDRAWN, not a bug

**An earlier revision claimed we were storing English machine translations
instead of the patients' own words. That claim was wrong.** It was inferred
from the actor's schema text (`lang` defaults to `"en"`) plus four fixture
records that happened to be written in English. Kept here rather than
deleted, because the wrong version circulated and because the verification
method is the reusable part.

Across the same 2,920 records:

| Field | Meaning |
|---|---|
| `content` | the **original** review text, always |
| `content_translated` | rendering into `lang`, empty when none was needed |
| `translated_language` | target lang when a translation happened, else `None` |

```
content            : "cs tidak cepat tanggap, bagian claim asuransi tidak responsif"
content_translated : "CS is not responsive, insurance claims section is not responsive"
```

836 of 2,046 records in the Simatupang run carry a translation, and in every
one the Indonesian original stays in `content`. `parse_review()` reads
`content`, so **it is already correct**. The four fixture records that
triggered the false alarm are from *Five Coffee Forest* with
`content_translated: ""` and `translated_language: None` — no translation
occurred, i.e. they were genuinely written in English.

**Do not set `lang: "id"`.** It would only change the language of
`content_translated`, which we do not store.

**One small real gap remains, unrelated to `lang`:** `content_language` is
`None` in all 2,920 records — the actor never populates it — so
`review_language` and `language` always store NULL. Fixing that means
deriving the language ourselves, or inferring "not `lang`" from
`translated_language` being set. Low priority, not data loss, not in any WP
below.

**Method note.** This is the third time Apify's documentation has proven
unreliable on this integration, after `source: "Googles"` and the
`newerThan`/`anyDate` naming. The rule that keeps holding: **settle
output-field semantics against a real dataset export, never against the
schema description.** A `json.load` over a saved run costs a minute.

---

## 2. Crawler-side flow

Picks up where Part 1 §2 hands off. The `>>>` line is the repo boundary.

```
>>> POST /api/integration/v1/crawl-jobs   (from OneBox)
        |
        v
CrawlBatchCreateRequest / CrawlTargetRequest
  apps/api/app_api/integration_crawl_schemas.py
  target_review_count     ge=1 le=300              :37
  max_reviews_to_collect  ge=1 le=300              :38
  scan_limit              ge=1 le=5000             :42
  crawl_mode  initial_backfill|regular_delta|custom_range   :43
  model_config extra="forbid"                      :23
        |
        v
routers/integration_crawl_jobs.py::enqueue_crawl_jobs()      :83
  _target_crawl_options() -> per-target dict                 :53
        |
        v
CrawlQueue.enqueue()  ->  CrawlBatch + CrawlJob rows
  _normalize_crawl_mode() / _normalize_scan_limit()          :388
        |
        v
CrawlWorker.execute_next()                                   :152
  claim_next() reads crawl_mode + scan_limit                 :140-147
  ... and passes neither onward                              :182-191   <-- dead
        |
        v
ApifyFetchService.fetch_location()                           :72
  validate_target(): min(crawl_max_target_reviews, 300)      :305
  also clamped by EntitlementService.review_quota()
        |
        v
ApifyReviewClient.fetch_reviews()                            :63
  del date_to   # "Apify has no actor-side upper bound"      :71
  actor_input: place_ids, limit, order, source, anyDate,
               include_personal                              :106
  ApifyClient.get_run_status()  BLOCKS, 300s ceiling         :49
        |
        v
_store_reviews(): is_within_date_range() drops date_to violations   :278
  ReviewService.insert_review() per review  (dedup + write)
```

The return path (`GET /integration/v1/reviews`) is untouched by this spec.
Its page cap interacts with fetch-all — see Part 1 OB-4.

---

## 3. Crawler-side bottlenecks

OneBox-side bottlenecks are in Part 1 §3. Two items (B1, B12) span both
repos and appear in both documents, marked ⇄.

### ⇄ B1. The 300 cap, crawler half

| Where | Line |
|---|---|
| `CrawlTargetRequest.target_review_count` `le=300` | `integration_crawl_schemas.py:37` |
| `CrawlTargetRequest.max_reviews_to_collect` `le=300` | `integration_crawl_schemas.py:38` |
| `CrawlBatchCreateRequest.max_reviews_to_collect` `le=300` | `integration_crawl_schemas.py:93` |
| `ApifyFetchService.validate_target()` `min(setting, 300)` | `apify_fetch_service.py:305` |

Plus `EntitlementService.review_quota()` clamps from
`Company.total_enable_review`.

The actor's `limit` accepts **up to 100,000** (default 200). The 300 was a
Selenium survivability limit — a real browser scrolling Maps could not go
deeper reliably. It means nothing against an HTTP API billed per review.

`apify_fetch_service.py:305` hardcodes `300` *next to* the
`crawl_max_target_reviews` setting meant to control it, so raising the
setting alone does nothing. Anyone trying the obvious config fix concludes
the system ignores its own configuration.

The OneBox half is Part 1 §3 B1.

### B3. `crawl_mode` and `scan_limit` are wired but inert

`claim_next()` reads both into `ClaimedCrawlJob`
(`crawl_worker.py:141,146`). The `fetch_location()` call at `:182-191`
passes neither, and `ApifyFetchService.fetch_location()` has no parameter
for either. They survive only as audit metadata via `_finish()`'s
`metadata.setdefault(...)` at `:357-362`.

`scan_limit` counted *review cards scanned in a browser*. It has no Apify
analogue. Leaving it looking load-bearing is worse than deleting it.

### B4. We compute the completeness oracle and discard it **[blocks fetch-all]**

`_capture_place_metadata()`
([`apify_review_client.py:218-228`](../../app/integrations/apify_review_client.py#L218))
stores `place_reviews_count` into `last_metadata["place_review_count"]` from
the first item. Verified present in real data:

```json
{"place_id": "ChIJ9fLOGgDraS4RRild036hTbY",
 "place_rating": 4.4, "place_reviews_count": 400}
```

Nothing reads it to decide completeness. Completeness is instead guessed
from `stored < requested_target`
([`apify_fetch_service.py:200-208`](../../app/services/apify_fetch_service.py#L200))
— which is why asking for 300 against a 270-review place classifies a
*complete* fetch as `partial_success`. That mismatch is the same ambiguity
that made job 542 unreadable.

### B5. The poll timeout is shorter than a real backfill **[blocks fetch-all]**

`apify_run_timeout_seconds = 300` (`config.py:121`). `get_run_status()`
returns `"POLL_TIMEOUT"` at the deadline (`apify_client.py:61-69`), which
raises `ApifyRunIncompleteError` → retriable failure.

A 5,000-review scrape does not finish in five minutes. With
`crawl_worker_max_attempts = 3` (`config.py:152`) a large backfill burns
three full actor runs and then fails permanently — **having paid for all
three**. Raising the cap (B1) without fixing this converts a capacity limit
into a billing leak.

### B6. The worker blocks; the lease is shorter than the work

`ApifyClient.get_run_status()` `time.sleep`s in-process
(`apify_client.py:70`), and one worker process serves one job at a time
(`scripts/run_crawl_worker.py:31-38`).

`crawl_worker_lease_seconds = 900` (`config.py:151`), and `claim_next()`
treats a `running` job with an expired lease as claimable
(`crawl_worker.py:102-106`). So **any run legitimately exceeding 15 minutes
becomes re-claimable while still running**, and a second worker starts a
*second Apify run* for the same cabang. Double billing, duplicate rows.

Masked today because the 300 s poll ceiling (B5) fires first. Fix B5 without
fixing this and the bug becomes reachable.

### B7. Date windows cost by age, not width **[blocks timespan]**

Confirmed against the live actor schema — the only date control is:

```
anyDate | string | "Scrape reviews newer than"
```

There is **no upper bound**. `fetch_reviews()` does `del date_to`
(`apify_review_client.py:71`) and `_store_reviews()` drops out-of-range rows
client-side via `is_within_date_range()` (`:278`), counting them into
`total_skipped_out_of_range`.

"Reviews from Jan–Mar 2024" therefore scrapes **everything from Jan 2024 to
today** and discards ~90% after paying. Inherent to the actor; cannot be
fixed here. It can only be priced (Part 1 OB-6) and mitigated (§4.3).

### B13. Resume advances the lower bound in the wrong direction **[blocks fetch-all]**

On account exhaustion (`apify_review_client.py:173-177`):

```python
if last_review is not None:
    lower_bound = parse_datetime(last_review.get("review_time")) or lower_bound
```

With `order: "newest"` the dataset arrives newest-first, so `last_review` is
the **oldest** row seen. Setting `anyDate` to it means *"reviews newer than
the oldest I already have"* — the set just fetched.

The re-run re-covers ground already paid for. `seen_review_ids` (`:141-144`)
filters the duplicates, so `reviews` does not grow, and the
`while len(reviews) < limit` loop (`:103`) makes no progress until accounts
exhaust or the limit is somehow met. The same expression feeds
`_save_checkpoint()`, so a resumed job inherits the same wrong bound.

Latent today (the common path is `SUCCEEDED` → `break` at `:149`) but
directly on the fetch-all path, and **no actor parameter exists that would
let it be fixed as written** — see D5 and §4.2.

### B14. Progress is reported exactly twice

`on_progress` fires at `(0, target, 0)` before the fetch and
`(len, target, len)` after (`apify_fetch_service.py:181-182`). The bar sits
at 0% for the whole run then jumps to 100%. For a ten-minute backfill that
is indistinguishable from a hang — the exact ambiguity that made job 542
unreadable. `iter_dataset_items()` is already a generator
(`apify_client.py:72`); per-page progress is nearly free.

### ⇄ B12. OneBox rejects any source but `selenium`

Lives in OneBox (`VocController.php:10557-10561`) but the tripwire points at
this repo: the first person who sends `source=apify` gets *"Sumber apify
belum didukung."* Fixed in Part 1 OB-7.

---

## 4. Design, crawler side

### 4.1 Coverage intent replaces target count

`target_review_count` means three different things depending on mode and
none of them means "all". Replace with explicit intent plus an optional cost
ceiling:

| Coverage | Bound sent to actor | Terminates when | OneBox supplies |
|---|---|---|---|
| `full_backfill` | `limit = place_reviews_count` (or `budget`) | collected ≥ expected × tolerance | cabang only |
| `date_window` | `anyDate = date_from`, `limit = budget` | run SUCCEEDED, rows filtered to window | cabang + from/to |
| `delta` | `anyDate = watermark − margin` | run SUCCEEDED | cabang only |

`budget` is a **ceiling, not a target**. Hitting it is an abnormal outcome
reported as `stop_reason: "budget_exhausted"`, never folded into success.
That distinction is exactly what `partial_success` currently blurs.

### 4.2 `place_reviews_count` as the completeness oracle

The load-bearing idea. Replace the `stored < requested_target` guess with:

```python
expected  = last_metadata["place_review_count"]   # already captured today
collected = len(unique review_ids drained)
complete  = expected is not None and collected >= expected * COMPLETENESS_TOLERANCE
```

`COMPLETENESS_TOLERANCE` (suggest `0.98`, configurable) exists because
Google's displayed count and the scrapeable set genuinely disagree:
ratings-without-text are counted but not always returned, and deletions lag
the counter. Exact equality would make every backfill report incomplete
forever.

What it fixes immediately:

- **"asked 300, place has 270, job never settles."** 270 ≥ 270 × 0.98 →
  complete → `succeeded`. No special case.
- **A real partial becomes distinguishable from a complete small place.**
  Today both look like `stored < requested`.
- **`full_backfill` becomes definable at all.** Without an expected count
  there is no terminating condition for "everything".

If `expected` is missing (empty dataset, or the actor drops the field), fall
back to today's behaviour and record `completeness: "unknown"`. **Never
treat unknown as complete.**

**Consequence — backfill must complete in one run (D5).** The actor offers
no offset and no upper date bound (§7 Q1, settled). Combined with B13 there
is no way to resume a partially-drained backfill by narrowing `anyDate`. So
`full_backfill` runs as a **single actor run** with `limit = expected`, and
that run may far outlast any lease we would want to hold. That is what
forces CS-3.

This does **not** invalidate the existing checkpoint mechanism. It stays
correct and useful for `delta` and `date_window`, where the bound genuinely
moves forward in time. It simply cannot serve `full_backfill`.

### 4.3 Timespan, and the one real optimisation

Per B7 the cost of a window is set by its *start*, not its width. Three
responses, two of which live in OneBox (Part 1 OB-6): estimate before
spending, report `total_skipped_out_of_range` as visible waste, and steer
users toward windows ending recently.

The crawler-side one: `filter_stars` is in the actor schema.

```
filter_stars | array | "Select one or more star ratings to filter reviews.
    When enabled, the sort order is automatically set to 'Newest'…"
```

For a VoC system *"all 1–2 star reviews in this window"* is often the actual
question, and filtering server-side cuts scraped volume by roughly the share
of low ratings (typically 10–20%). Worth exposing as an optional filter on
`date_window`. Not required for the three capabilities; a cheap follow-on.
Note it forces `order=newest`, which `date_window` already uses.

### 4.4 Quasi-realtime, crawler side

**True realtime does not exist for Google Maps reviews.** No webhook.
Apify's run webhooks fire when *our own run* finishes; they say nothing
about a new review appearing. Any spec promising push here is wrong.

The only genuine push path is the **Google Business Profile API** (real
review notifications over Pub/Sub, requires verified ownership per
location). Separate integration, own OAuth and quota model. **Out of scope,
but it is the honest answer to "can we have real realtime", and it deserves
evaluation before anyone invests further in tightening the poll.**

Deliverable now is a **change probe** the OneBox scheduler can call before
spending anything:

```
probe = GooglePlacesClient -> userRatingCount     (cheap)
if probe == last_seen_count:  skip, cost 0
else:                         run a delta crawl   (Apify, billed)
```

Reuses what is already here: `app/integrations/google_places_client.py`
already requests `userRatingCount` in its field mask (`:40`) and
`GOOGLE_MAPS_API_KEY` already exists. No new dependency, no new credential.

Without the gate, 10-minute polling is ~144 Apify runs per cabang per day,
nearly all returning nothing.

**Limitation to state plainly:** `userRatingCount` does **not** move when a
review is edited, or when one is added and another deleted in the same
window. The gate is an optimisation, not a correctness mechanism. OneBox
must keep a slower unconditional delta underneath it (Part 1 OB-5).

---

## 5. Contract `crawl-jobs v2` — DEFINED HERE

The OneBox document carries a caller's view of this section. **Changing
anything here means changing Part 1 §5 in the same commit.**

### 5.1 `CrawlTargetRequest` (`apps/api/app_api/integration_crawl_schemas.py`)

```python
coverage: Literal["full_backfill", "date_window", "delta"] | None = None
budget: int | None = Field(default=None, ge=1, le=100_000)

# deprecated, still accepted, mapped in a validator:
target_review_count:    int | None = Field(default=None, ge=1, le=100_000)
max_reviews_to_collect: int | None = Field(default=None, ge=1, le=100_000)
crawl_mode: Literal["initial_backfill","regular_delta","custom_range"] | None = None
scan_limit: int | None = None          # accepted, ignored, logged once
```

Validator rules:

- `coverage == "date_window"` requires at least one of `date_from`/`date_to`.
- `coverage == "full_backfill"` **forbids** `date_from`/`date_to`. A bounded
  backfill is a `date_window`; allowing both is how two modes silently
  become one.
- `coverage` absent → derive from `crawl_mode`, then from presence of dates.
- `le=300` → `le=100_000` on every count field.

### 5.2 Legacy mapping (lets the two repos deploy independently)

```
crawl_mode=regular_delta     -> coverage=delta
crawl_mode=custom_range      -> coverage=date_window
crawl_mode=initial_backfill  -> coverage=full_backfill
absent + no dates            -> coverage=delta
absent + dates               -> coverage=date_window
target_review_count          -> budget
scan_limit                   -> ignored
```

### 5.3 Why "accept before emit" is not optional

`CrawlTargetRequest` and `CrawlBatchCreateRequest` both set
`model_config = ConfigDict(extra="forbid")`
(`integration_crawl_schemas.py:23`, `:87`). An unknown field is a **422, not
a warning**. If OneBox ships `coverage` before the crawler accepts it, every
crawl in production fails immediately.

OneBox already has a guard for this shape of failure —
`VoiceOfCustomerSystemClient::enqueueCrawl()` retries without the new
contract fields when the crawler rejects them (`:834-849`). Do not rely on
it. It was written for `crawl_mode`/`scan_limit` and silently degrades the
request rather than surfacing the mismatch.

### 5.4 Result metadata additions

```python
"coverage": "full_backfill" | "date_window" | "delta",
"expected_review_count": int | None,      # place_reviews_count
"collected_unique": int,
"completeness": "complete" | "partial" | "unknown",
"completeness_ratio": float | None,
"budget": int | None,
"stop_reason": ... | "budget_exhausted" | "coverage_complete",
```

### 5.5 Config (`app/config.py`)

```python
crawl_max_target_reviews: int = 300            # -> 100_000
apify_run_timeout_seconds: int = 300           # -> per-coverage, see CS-3
apify_backfill_deadline_seconds: int = 7200    # new: wall clock, not poll
crawl_worker_lease_seconds: int = 900          # must exceed the longest run
crawl_completeness_tolerance: float = 0.98     # new
```

---

## 6. Work packages

Formatted for delegation: exact files, exact change, how to verify, what not
to touch.

---

### CS-0 — Reviewer identity: collect it, and repair history ✅ DONE

Two parts, see §1.1:

1. `include_personal: True` in the actor input — new reviews arrive named
   (`c96a883`).
2. Re-crawl repairs old reviews — `backfill_missing_fields()` via the
   `enrich` hook on `insert_review_optimistically()`, with a
   `sync_updated_at` bump so OneBox re-pulls the row.

`"lang": "id"` was **not** shipped — §1.2 withdrew that diagnosis.

**Pairs with OneBox OB-0**, without which already-ticketed reviews keep
showing "Anonymous" even after this repair.

**To actually repair a cabang's history:** crawl it at a depth that reaches
its old reviews (a `delta` crawl only touches recent ones), then run the
OneBox import.

**Remaining verification:** one real crawl against a live cabang confirming
`reviewer_name` now arrives populated. The fix is asserted at the
actor-input layer, which is where the bug was, but has not been seen end to
end against production Apify.

---

### CS-1 — Contract v2: `coverage` + `budget`, remove the 300 cap

**Depends on:** nothing. **Blocks:** CS-2, CS-3, and OneBox OB-2.
**Must reach production before OB-2** — §5.3.

**Files:**
- `apps/api/app_api/integration_crawl_schemas.py` — §5.1, §5.2
- `app/services/crawl_queue.py:388` — `_normalize_crawl_mode()` maps to
  `coverage`; `_normalize_scan_limit()` becomes a no-op pending CS-6
- `app/services/apify_fetch_service.py:300-314` — `validate_target()`: drop
  the hardcoded `300`, honour `crawl_max_target_reviews`, keep the
  entitlement clamp but report it as `budget`, not as the target
- `app/config.py` — §5.5

**Verify:** in `tests/test_integration_crawl_jobs.py` —
`budget=5000` accepted; `budget=100001` rejected; `coverage="full_backfill"`
with dates rejected; **a legacy request carrying only
`target_review_count=300` and `crawl_mode=regular_delta` behaves exactly as
today.** That last one is the deploy-safety test — it is what lets the two
repos ship independently.

**Do not touch:** the fetch loop, the checkpoint store, `ReviewRepository`.

---

### CS-2 — Completeness oracle

**Depends on:** CS-1. **Blocks:** CS-3, CS-5.

**Files:**
- `app/integrations/apify_review_client.py` — surface
  `expected_review_count` and `collected_unique` in `last_metadata`
- `app/services/apify_fetch_service.py:200-212` — replace the
  `stored < requested_target` partial classification with §4.2
- `app/config.py` — `crawl_completeness_tolerance`

**Verify:** new tests in `tests/test_apify_fetch_service.py`:
- 270 collected, `place_reviews_count=270`, requested 300 → `success`,
  `completeness: "complete"` — **this is the job-542 shape and is the
  acceptance test for this WP**
- 100 collected, `place_reviews_count=5000` → `partial_success`,
  `completeness: "partial"`
- `place_reviews_count` absent → `completeness: "unknown"`, old behaviour

**Do not touch:** `ApifyRunIncompleteError` semantics. A run Apify never
confirmed is still not a completed fetch regardless of what the count says.
The two mechanisms are orthogonal and must stay that way.

---

### CS-3 — Stop blocking the worker on the Apify poll loop

**Depends on:** CS-1, CS-2. Largest package. **Unblocks fetch-all.**

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
                      unless now > source_started_at + backfill_deadline
         SUCCEEDED -> drain dataset, store, apply CS-2, finish
         else      -> existing ApifyRunIncompleteError path
```

**Files:**
- `app/db/models.py` + alembic migration — `CrawlJob.source_run_id`,
  `source_dataset_id`, `source_started_at`
- `app/services/crawl_worker.py` — new `awaiting_source` status in
  `claim_next()`'s `due` clause and in `_refresh_batch_status()`'s
  non-terminal set
- `app/integrations/apify_review_client.py` — split `fetch_reviews()` into
  `start_fetch()` / `resume_fetch()`
- `app/services/apify_fetch_service.py` — thread both phases through

**Also fixes:** B6 (the lease no longer has to outlive the run) and B14
(Phase B reports real progress on every poll).

**Verify:** a fake client reporting `RUNNING` three times then `SUCCEEDED`
must produce **exactly one** `start_run` call and one stored result; assert
the job returned to the queue between polls and that no second actor run
started.

**Do not touch:** the `partial_success` / `ApifyRunIncompleteError`
distinction settled on this branch.

**Cheaper interim** — if CS-3 cannot be scheduled soon, raising
`apify_run_timeout_seconds` to ~3600 and `crawl_worker_lease_seconds` above
it unblocks *single-cabang manual* fetch-all today. The ceiling: the batch
is fully serial, so "fetch all, 50 cabang" is one worker running 50 runs
back to back, and a crashed worker holds a job for the whole lease. Ship it
knowingly, not as the answer.

---

### CS-4 — Review-count change probe

**Depends on:** nothing. **Blocks:** OneBox OB-5.

**Files:**
- `app/integrations/google_places_client.py` — add `review_count(place_id)`;
  the field mask at `:40` already requests `userRatingCount`
- new `app/services/review_count_probe.py` — cache last-seen count per
  location, return `changed: bool`
- `app/db/models.py` + migration — `Location.last_probed_review_count`,
  `Location.last_probed_at`
- expose it to OneBox — either on the estimate endpoint (CS-5) or as a
  `probe_first` flag on enqueue. **Decide with the OneBox side; this is a
  contract change and §5 must be updated.**

**Verify:** probe returns `changed=False` on an unchanged count **without
constructing the Apify client**. That assertion *is* the cost saving.

**Do not touch:** `GooglePlacesClient.fetch_reviews()`. It stays unused as a
review source; only the count is being borrowed.

---

### CS-5 — Preflight estimate endpoint + budget enforcement

**Depends on:** CS-2. **Pairs with:** OneBox OB-6.
**Must land before CS-1 is enabled in production.**

Removing a 300-review cap without a spend guard is how one click becomes a
large invoice.

**Files:**
- new `app/services/crawl_budget_service.py` — per-company monthly review
  budget, checked at enqueue **and** enforced during drain
- new `GET /integration/v1/crawl-jobs/estimate?location_id=` — returns
  `expected_review_count` from the last rating snapshot or the CS-4 probe
- §5 — document the new endpoint in the contract

**Verify:** a `full_backfill` whose estimate exceeds remaining budget is
rejected at enqueue with a distinct error code, **before any actor run
starts**.

**Coordinate with OneBox:** OneBox already has `VOC_SCRAPE`/`VOC_REVIEW`/
`VOC_AI` benefit quotas counted **per call, not per review**. Under
per-review billing that unit is wrong. Decide jointly whether to extend the
existing benefit system or keep this budget separate — **do not build a
second quota system by accident.** Part 1 OB-6 carries the OneBox half.

---

### CS-6 — Cleanup

**Depends on:** CS-1..CS-3 landed.

- Delete `scan_limit` end to end: `CrawlTargetRequest.scan_limit`,
  `CrawlBatchCreateRequest.scan_limit`, `ClaimedCrawlJob.scan_limit`,
  `_normalize_scan_limit()`, `_finish()`'s
  `metadata.setdefault("scan_limit", …)`. Coordinate with OneBox OB-7,
  which deletes the sending half.
- Fix or delete the wrong-direction resume bound at
  `apify_review_client.py:173-177` (B13). After CS-3 `full_backfill` no
  longer uses it; confirm what `delta` and `date_window` actually need
  rather than preserving it by default.
- Remove `crawl_mode` once OneBox emits only `coverage`. **Not before** —
  §5.3 in reverse.

---

## 7. Open questions, crawler side

**Q1 — resume/offset support in the actor. SETTLED, answer is no.**
Pulled live from
`GET /v2/acts/web_wanderer~google-reviews-scraper/builds/default`. Full
property list: `include_personal, place_urls, place_ids, anyDate, lang,
filter_stars, limit, order, source, searchKeyword, search, search_limit,
search_location, search_coordination, sort_dataset, sort_keys, sort_order`.
**No offset, no cursor, no upper date bound.** `limit` maxes at 100,000.
This is what forces D5/CS-3.

**Q2 — privacy sign-off on `include_personal`. RESOLVED.** Authorised
directly by the project owner; shipped. Standing note in §1.1.

**Q3 — which field carries original-language text. RESOLVED, and it
invalidated the bug it was asked about.** `content` holds the original in
all 2,920 records checked. Parser already correct. See §1.2.

**Q4 — Places API cost and quota at a 10-minute interval.** CS-4. Needs the
actual GCP billing tier for this project, not list pricing.

**Q5 — is Google Business Profile API viable for Hermina's own cabang?**
Determines whether the polling path is a stopgap or permanent. Worth
answering before investing further in it. §4.4.

**Q7 — what does `order: "lowest_rating"` actually do.** Still unverified,
though the schema now confirms it is a valid enum value. Low priority.

*(Q6 is an OneBox question — benefit quota unit. See Part 1 §7.)*

---

## 8. Pairing table — KEEP IDENTICAL IN BOTH DOCUMENTS

| Pair | OneBox (Part 1) | Crawler (Part 2) | Cross-repo rule |
|---|---|---|---|
| **Z** | **OB-0** rename anonymous Contacts | **CS-0** reviewer identity + history repair ✅ | CS-0 shipped; OB-0 needed for ticketed reviews |
| **A** | **OB-1** per-cabang date ranges | — | none — pure OneBox saving, ship anytime |
| **B** | **OB-2** emit `coverage`+`budget` | **CS-1** accept `coverage`+`budget` | **CS-1 to prod first** (Part 2 §5.3, `extra="forbid"` → 422) |
| **C** | — | **CS-2** completeness oracle | after CS-1 |
| **D** | **OB-6** preflight UI + quota unit | **CS-5** estimate endpoint + budget | **both before B reaches prod** |
| **E** | — | **CS-3** async run phases | after C; unblocks real fetch-all |
| **F** | **OB-3** Fetch Jobs mode UI | — | after B on both sides |
| **G** | **OB-4** import cycle caps | — | before fetch-all is usable end to end |
| **H** | **OB-5** realtime schedules | **CS-4** count probe | **CS-4 first**; contract change, update Part 2 §5 |
| **I** | **OB-7** cleanup | **CS-6** cleanup | **OB-7 first** — stop sending before we stop accepting |

**Two ordering rules that will bite if ignored:**

- **Adding a field: crawler first.** `extra="forbid"` turns an unknown field
  into a 422.
- **Removing a field: OneBox first.** Stop sending before the crawler stops
  accepting.

**Capability delivery:** capability 1 (fetch all) lands with **E** + **G**.
Capability 2 (timespan) is usable after **B**+**C** and improves with **A**.
Capability 3 (quasi-realtime) lands with **H**.

---

## 9. Out of scope

- Changing `GET /integration/v1/reviews` or its cursor contract.
- Competitor crawls. Same mechanisms apply, but they are not among the three
  requested capabilities and `_execute_competitor` (`crawl_worker.py:233`)
  would double the test matrix.
- Google Business Profile API (§4.4) — named, not specced.
- `TECH_DEBT_ONEBOX_APIFY_FIELD_NAMING.md` renaming work.
- Automatic mode selection. The user picks cabang and mode, per the original
  requirement.
