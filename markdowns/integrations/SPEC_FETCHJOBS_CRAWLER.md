# Fetch Jobs enhancement — Part 2 of 2: Crawler Service

**Repo:** `hermina-crawler` · **Branch assumed:** `apify-migration`
**Paired with:** [`SPEC_FETCHJOBS_ONEBOX.md`](SPEC_FETCHJOBS_ONEBOX.md) — Part 1, the OneBox half
**Contract version defined here:** `crawl-jobs v2`
**Status:** proposal, revised 2026-09-17 after review. CS-0 is shipped; CS-1 onward is not started.

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
2. **The pairing table (§8), the shared decisions (§0) and the review-feedback
   table must be identical in both documents.** It
   is the only place the cross-repo ordering is recorded.
3. **Accept before emit.** The crawler must accept a new contract field in
   production *before* OneBox starts sending it. Reversing this produces a
   422 from a Pydantic model with `extra="forbid"` — see §5.3.
4. Bump the contract version string in both documents when §5 changes
   shape.

---

## Review feedback 2026-09-17 — where each point is handled

Identical in both documents.

| Feedback | Answer | Part 1 (OneBox) | Part 2 (Crawler) |
|---|---|---|---|
| How to handle a "floating" review in the crawler | Four kinds — drifting estimated dates, edited, late-published, deleted — each with its own rule | §4.7, OB-8 | B17–B19, §4.6, CS-7 |
| Existing cursor (one per cabang, e.g. Pertamina Margonda backfill → 16 Sep → newest) was slow with many duplicates | Keep the design (D9); six causes found; the crawler now owns coverage state | §4.5, OB-1, OB-4 | B20, §4.5, CS-7, CS-8 |
| Make alerts / toasts / messages unambiguous | Surface rules, wording rules, 25-row message catalogue; existing stop reasons never displayed (bug) | B21, §4.6, OB-9 | CS-8 |
| Review quota default must not be 300 | Default 5,000, maximum 100,000, one constant per repo; 13 + 6 places listed | B1, OB-2, Q6 | B1, §4.7, Q12 |
| Read Pak Indra's raw notes on fetch logic and screen | Notulen 2026-08-21 §M: a date-range fetch takes **all** reviews in range; scheduler may keep a count. Notulen 2026-09-08: Google rating is stored, never computed | D8, §4.5 | D8, §4.5 point 5 |

Sources: `markdowns/02-meetings-and-decisions/meeting-notes/2026-08-21-voc-progress-review.md`
and `2026-09-08_REVIEW_CEO_ULASAN_DAN_WORKSPACE.md` (on `origin/main`);
ADR-0005 (`02-meetings-and-decisions/adr/`), whose unbuilt cursor fields
§4.5 of Part 2 now specifies.

---

## 0. Shared decisions

Identical in both documents. Full rationale for the crawler-side ones is in
§4 below; OneBox-side rationale is in Part 1 §4.

| # | Decision | Owner |
|---|---|---|
| D1 | Ship the reviewer-identity data bug first, alone. ✅ crawler side done; OneBox half is OB-0 | Both |
| D2 | Replace "target review count" with explicit **coverage intent** (`full_backfill` / `date_window` / `delta`) plus an optional cost **budget**. | Both |
| D3 | Use Apify's `place_reviews_count` as the **completeness oracle**. | Crawler |
| D4 | The 300-review cap is entirely ours — the actor accepts up to **100,000**. Remove it everywhere (13 places in OneBox, 6 in the crawler). | Both |
| D5 | Full backfill **cannot be resumed mid-run**, so the crawler worker must stop blocking on the Apify poll loop. | Crawler |
| D6 | Quasi-realtime = tight-interval delta polling gated by a cheap change probe. True realtime does not exist for Google Maps. | Both |
| D7 | Date windows cost in proportion to how **old** the window is, not how wide. Unfixable; must be priced and surfaced. | Both |
| D8 | **Pak Indra's rule** (notulen 2026-08-21 §M): a manual fetch over a date range takes **all** reviews in that range — the count never decides when it stops. The scheduler may keep a count. | Both |
| D9 | **Keep one cursor per cabang** — the existing `last_review_at` design — and extend it: the crawler records what it has actually *crawled*, instead of OneBox inferring it from what it has *imported*. | Both |
| D10 | **Google review dates are mostly estimates** ("a year ago" = exactly 365 days before the crawl). Floating reviews are handled explicitly, and older dates are shown as approximate. | Both |
| D11 | **The 300 default goes.** Default per-cabang ceiling becomes **5,000**, held in one constant per repo; hard maximum 100,000. | Both |

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
| `crawl_max_target_reviews = 300` | `app/config.py:118` |
| `FetchJobRequest.target_review_count` `le=300` | `apps/api/app_api/routers/fetch_jobs.py:23` |
| `PipelineRequest.target_review_count` `le=300` | `apps/api/app_api/routers/pipeline.py:26` |

Related default: `Location.target_review_count` and
`Competitor.target_review_count` default to **100**
(`app/db/models.py:277-279`, `:506-508`). D11 replaces all of these with one
default of 5,000 and one maximum of 100,000.

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

### B17. Most review dates are estimates, not real dates **[blocks timespan]**

`reviewed_at_date` looks like a precise timestamp. For most reviews it is
**computed from Google's relative text** ("a year ago") by subtracting a
round number from the crawl date. Measured on the Astra TB Simatupang run
(1,023 unique reviews, crawled 2026-09-15):

| Google text | Stored age in days → how many reviews |
|---|---|
| `a day ago` | 1 → 1 |
| `2 weeks ago` | 14 → 2 |
| `a month ago` | **30 → 6**, 43 → 1 |
| `2 months ago` | **60 → 23**, 76 → 1, 92 → 1 |
| `a year ago` | **365 → 84**, 400/449/470/501/520/547/640 → 1 each |
| `6 years ago` | **2190 → 66**, eight other values → 1–2 each |

94% of normal reviews and **100%** of edited ones sit at exactly N×30 or
N×365 days before the crawl. A small minority carry a real date. So:

- **Precision depends on age.** Under a week old: roughly day precision.
  Months old: a month. Years old: **a whole year** — a review stored as
  "2025-09-15" may have been written any time from late 2024 to
  September 2025.
- **A date window over old periods cannot be answered exactly.** "Jan–Mar
  2025" matches almost none of the 84 reviews that were all stamped
  2025-09-15, even though some were written in that window.
- **The same review gets a different date on each crawl.** Crawl it a week
  later and "a year ago" becomes 365 days before *that* crawl. This is the
  core of the floating-review problem (§4.6).
- Monthly trend charts built from `review_time` pile old reviews onto a few
  dates.

This contradicts an earlier line in Part 1 (B9) that said Apify returns real
dates; that line was wrong and has been corrected there. The one-day
watermark margin's original reasoning — dates are estimated from relative
text — **is still true.**

### B18. `review_hash` includes fields that change

`generate_review_hash()` (`app/utils/hashing.py:14-24`) hashes `source`,
`external_place_id`, `external_review_id`, **`reviewer_name`, `rating`,
`review_text` and `review_time`**. The same Google review therefore gets a
new hash whenever:

- its estimated date moves (B17) — i.e. on almost every crawl of an older
  review;
- the reviewer edits it (B19);
- its name is filled in — which `include_personal` (CS-0) now does for every
  review collected before 2026-09-16.

**Inside the crawler this is contained:** `_dedupe_statement()`
(`review_repository.py`) matches on hash **or** on
`(source, external_review_id, place)`, so a changed hash is still caught as a
duplicate whenever `external_review_id` is present — and the existing row
keeps its original hash. Verified: the CS-0 name repair does not create
duplicates.

**Outside, it is not.** OneBox uses the hash as `Message.RemoteId`. Its
own comment (`VocProvider.php:873-888`) records 43 of 268 reviews imported
twice with different hashes — the duplicates reported in review. OneBox
added an `external_review_id` guard for it. Rows without an
`external_review_id` (possible in Selenium-era data) have no stable key at
all.

**Do not change the hash formula.** Every stored `RemoteId` in OneBox is an
old-formula hash; changing it re-imports every review as new. The fix is to
stop *relying* on the hash for identity (CS-7), not to redefine it.

### B19. Edited reviews are silently dropped

44 of the 1,023 unique Simatupang reviews (88 of 2,046 records — that run
returned every review twice) show `reviewed_at: "Edited N months ago"`.
An edited review returns under the same `review_id`, so dedup matches it and
**discards the new text and rating**. A patient who changes 5★ to 1★ and
rewrites the review stays 5★ in both the crawler and OneBox.

Its `reviewed_at_date` is then the estimated **edit** date, not the original.

### B20. The delta cursor is read from what OneBox *imported*

Today's per-cabang cursor is `last_review_at`: the newest review OneBox holds
for that cabang (Part 1 §4.5). The crawler holds no coverage state of its own
— ADR-0005 proposed `last_seen_review_time`, `oldest_scanned_review_time`
and `first_run_completed_at`, and none were built (verified: no such field
on any branch).

So whenever the import lags behind the crawl — and import stops at 500
reviews per call (Part 1 B11) — the next delta starts from an old date and
re-crawls reviews already crawled. That is one of the two root causes of the
"slow and full of duplicates" behaviour reported for the existing cursor.
§4.5 has the full list.

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

**Checked against real data:** the Astra TB Simatupang run reports
`place_reviews_count: 1022` and returned **1,023 unique** `review_id`s (2,046
records, each twice). 1,023 ≥ 1,022 × 0.98 → `complete`, which is the right
answer. The same run also shows why the oracle must count **unique** ids:
counting raw records would claim 200% coverage.

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

### 4.5 The per-cabang cursor — keep it, move what it measures

**What exists today** (built in DNGO19-3529, `VocCrawlQueue.php`,
`fetchjobs.volt`): one cursor per cabang, equal to the newest review OneBox
holds for it. Example from review: an initial backfill of **Pertamina
Margonda** collected ~1,100 reviews, the newest dated **16 September**.
Every later fetch of that cabang — manual or scheduled — defaults to
**16 September minus one day → newest**. The design is right and stays
(D9).

**Why it was slow and full of duplicates.** Six causes, roughly in order of
impact:

| # | Cause | Where | Effect |
|---|---|---|---|
| 1 | Cursor comes from OneBox's *imported* rows, not the crawler's *crawled* rows | B20; Part 1 B11 | Import lag → cursor lags → reviews already crawled are crawled again |
| 2 | Scheduled batches use **one** date for every cabang — the oldest cursor | Part 1 B8 | One lagging cabang makes all of them re-crawl from its date |
| 3 | Selenium scrolled from newest down to the cursor on every run | removed by the Apify migration | Slow |
| 4 | Changing `review_hash` | B18 | OneBox imported the same review twice (43/268) |
| 5 | Margin of one day, and `anyDate` accepts a date only | `VocCrawlQueue.php:284`; `apify_review_client.py:119` | Every run re-crawls at least one full day. **Expected and cheap** — this kind of duplicate is not a bug |
| 6 | One DB commit per review | `insert_review_optimistically()` | Slow on Supabase (≈270 commits for job 542) |

**What changes:**

1. **The crawler keeps coverage state per target** — the ADR-0005 fields,
   finally built. New table `crawl_coverage` (one row per location /
   competitor, or columns on those tables — implementer's choice):

   | Field | Meaning | Moved by |
   |---|---|---|
   | `newest_crawled_at` | newest `review_time` the crawler has **stored** for this target | any successful crawl |
   | `newest_crawled_precision` | `day` / `week` / `month` / `year` of that value (§4.6) | same |
   | `oldest_crawled_at` | oldest `review_time` stored | backfill, date window |
   | `backfill_completed_at` | set when a `full_backfill` ends `completeness: complete` | CS-2 |
   | `last_successful_crawl_at` | wall clock of the last crawl that finished | any successful crawl |
   | `last_expected_review_count` | `place_reviews_count` at that crawl | any crawl |

2. **`delta` takes its lower bound from `newest_crawled_at − margin`**, not
   from the date OneBox sends. OneBox may still send a `date_from` (older
   deployments do); the crawler uses **the later of the two**, so an
   out-of-date OneBox cursor can no longer cause a re-crawl. Cause 1 is
   gone.
3. **Only successful crawls move the cursor.** A run that ends
   `ApifyRunIncompleteError` or `budget_exhausted` does not move
   `newest_crawled_at` past what it actually stored — otherwise a failed run
   would skip reviews forever.
4. **`date_window` never moves `newest_crawled_at` forward.** It may move
   `oldest_crawled_at` back. (Answers ADR-0005 open question 4: a custom
   range does not disturb the regular delta cursor.)
5. **Pak Indra's rule (D8)** applies to `date_window`: it collects every
   review in the window; `budget` is only a cost guard. If the budget or a
   timeout stops it early, the job ends `completeness: partial` and the
   crawler records the window as incomplete (`crawl_window_log`: target,
   from, to, completeness, finished_at), so the UI can say *"rentang ini
   belum lengkap"* and offer to run it again. Because the actor has no upper
   date bound or offset (D5), **running it again means a full re-run with
   dedup, not a cheap resume** — CS-3 exists so the window is finished in one
   run in the first place.
6. **Commit in chunks** (cause 6) — CS-8.

Expose the coverage row to OneBox on the estimate endpoint (CS-5) and on
each job result, so the Fetch Jobs screen shows the crawler's cursor rather
than inferring its own.

### 4.6 Floating reviews

A **floating review** is one whose date or position is not stable between
crawls, so it can drift across the cursor. The evidence is B17–B19. There
are four kinds, each handled differently.

| Kind | What happens | Risk | Handling |
|---|---|---|---|
| **F1 — drifting estimated date** | `review_time` is recomputed from "a year ago" on every crawl | Hash changes (B18); date windows and trends are wrong; a coarse later estimate could overwrite a precise earlier one | **Identity is `external_review_id`**, never the hash. Store `review_time_precision`. **Never replace a stored `review_time` with a coarser one** — the first sighting while the review was fresh is the most precise we will ever get. The delta scheduler naturally captures that |
| **F2 — edited review** | same `review_id`, new text/rating, "Edited N ago", jumps to the top of *newest* | Change silently dropped (B19) | Detect a changed `review_text` or `rating` on a dedup match → update them in place, set `edited_at` (estimated) and `is_edited`, keep the original `review_time`, set `analysis_status = pending` so AI re-runs, bump `sync_updated_at`. Keep the previous text in `raw_payload.previous_versions[]` |
| **F3 — late-published review** | Google publishes it days after it was written, with its original date — **below** the cursor | A delta that starts at the cursor never sees it: **lost silently** | **Weekly safety sweep** per cabang: one delta with `anyDate = newest_crawled_at − 30 days`. Duplicates are expected and cheap. Also trigger a sweep when `place_reviews_count − stored` grows between crawls by more than the new reviews just stored |
| **F4 — deleted review** | disappears from Google; `place_reviews_count` drops | We keep showing it | Out of scope. Record the count drop in coverage state; do not delete anything automatically |

**Deriving `review_time_precision`** — in `ApifyReviewParser`, from
`reviewed_at` and the crawl date:

```
text unit (strip "Edited ")          precision
"N minute(s)/hour(s) ago"            day
"a day ago" / "N days ago"           day
"a week ago" / "N weeks ago"         week
"a month ago" / "N months ago"       month
"a year ago" / "N years ago"         year
age != N × unit exactly              day   (the actor had a real date)
unparseable                          unknown
```

**Date windows with estimated dates.** A review stored at date *d* with
precision *p* was written somewhere in `(d − 1p, d]`. The `date_window`
filter in `_store_reviews()` keeps a review when that interval **overlaps**
the window, and marks it `date_approximate = true`. It over-includes rather
than silently dropping real matches — the user can see which dates are
approximate (Part 1 §4.7). Exact-precision reviews are filtered exactly as
today.

**What not to do:**

- Do not "correct" old dates from `scraped_at − text`: that is what already
  happened, and it is the problem.
- Do not change `generate_review_hash()` (B18).
- Do not overwrite `review_time` on a re-sighting except with a strictly
  finer precision.

### 4.7 Defaults (D11)

One default and one maximum per repo, used everywhere:

```python
# app/config.py
crawl_default_review_limit: int = 5_000      # was 300 / 100 in six places
crawl_max_target_reviews:   int = 100_000    # the actor's own maximum
```

Why 5,000: it covers the real places seen so far (Pertamina Margonda ~1,100;
Astra TB Simatupang 1,022 per Google), matches OneBox's smallest `VOC_REVIEW`
package (`rev_5000`), and is still a ceiling rather than a target — a delta
run stops at the cursor long before reaching it. **Confirm the number with
product** (Part 1 Q6) before shipping; changing it later is a one-line
config edit.

`Location.target_review_count` / `Competitor.target_review_count` defaults
move from 100 to this setting. Existing rows keep their stored value; a
data migration raising rows still at 100 or 300 is optional and should be
decided per tenant.

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

### 5.5 Review API additions (`GET /integration/v1/reviews`) — additive only

Per review, new optional keys. OneBox must treat each as possibly absent.

```python
"review_time_precision": "day" | "week" | "month" | "year" | "unknown",
"date_approximate": bool,          # precision coarser than day
"is_edited": bool,
"edited_at": datetime | None,      # estimated, same precision rules
```

The keyset cursor is unchanged. An edit (F2) bumps `sync_updated_at`, so
edited reviews are re-served automatically.

Per job result, a `coverage` object mirrors the §4.5 table.

### 5.6 Config (`app/config.py`)

```python
crawl_max_target_reviews: int = 300            # -> 100_000
crawl_default_review_limit: int = 5_000       # new, D11 / §4.7
crawl_safety_sweep_days: int = 30             # new, F3
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

### CS-7 — Floating reviews and crawl-coverage cursor

**Depends on:** CS-1. **Pairs with:** OneBox OB-8. Can start before CS-3.

**Files:**
- `app/integrations/apify_review_parser.py` — derive
  `review_time_precision`, `is_edited` (§4.6 table)
- `app/db/models.py` + migration — `Review` / `CompetitorReview`:
  `review_time_precision`, `is_edited`, `edited_at`; new `crawl_coverage`
  (§4.5) and `crawl_window_log`
- `app/services/review_repository.py` — extend the CS-0 `enrich` hook:
  on a dedup match, apply F1 (finer precision only) and F2 (text/rating
  change); leave `review_hash` untouched
- `app/services/review_service.py` — bump `sync_updated_at` and reset
  `analysis_status` on F2
- `app/integrations/apify_review_client.py` — lower bound for `delta` =
  `max(OneBox date_from, newest_crawled_at − margin)`
- `app/services/apify_fetch_service.py` — precision-aware window filter;
  update coverage only on success; write `crawl_window_log`
- scheduler hook or worker — weekly safety sweep (F3)
- `apps/api/app_api/...` — §5.5 fields

**Verify** (new tests, all against real-shaped fixtures from the Simatupang
export):
- a review stored as `day` precision is **not** overwritten by a later
  `year`-precision sighting of the same `review_id`;
- the same `review_id` with new text and rating updates in place, keeps
  `review_time`, keeps `review_hash`, sets `is_edited`, bumps
  `sync_updated_at`, and inserts no row;
- a `year`-precision review dated 2025-09-15 **is** kept by a
  2025-01-01..2025-03-31 window, flagged `date_approximate`;
- a delta whose OneBox `date_from` is older than `newest_crawled_at` uses
  `newest_crawled_at − margin`;
- an incomplete run does not move `newest_crawled_at`.

**Do not touch:** `generate_review_hash()`.

---

### CS-8 — Stable `stop_reason` vocabulary, and commit throughput

**Depends on:** nothing. **Pairs with:** OneBox OB-9.

1. **One published list of `stop_reason` codes.** Today three vocabularies
   exist: Selenium's raw keys (`time_limit`, `max_scroll_attempts`,
   `no_new_review_cards`), the mapped public ones in `crawl_result.stop_reason()`
   (`timeout`, `no_more_reviews`, `older_than_window`), and Apify's
   (`apify_accounts_exhausted`). OneBox still matches the **raw Selenium
   keys** (`fetchjobs.volt:1163-1167`) — so no stop reason is ever shown.
   Publish the final list in §5.4 and emit only those:

   | Code | Meaning |
   |---|---|
   | `coverage_complete` | got everything the mode asked for |
   | `no_new_reviews` | delta found nothing past the cursor |
   | `budget_exhausted` | our ceiling was hit first |
   | `source_quota_exhausted` | every Apify account ran out (was `apify_accounts_exhausted`) |
   | `source_not_confirmed` | Apify never confirmed the run; will retry (was `APIFY_RUN_*` failure codes) |
   | `deadline_exceeded` | CS-3 wall-clock deadline hit |
   | `target_disabled` | cabang inactive or removed |

   Keep emitting the old keys alongside for one release, then drop them
   (removal order: OneBox first).
2. **Commit in chunks** instead of per review (§4.5 cause 6). Keep the
   per-row `IntegrityError` fallback for the chunk that fails, so dedup
   semantics are unchanged. Measure on the job-542 shape (270 reviews)
   before and after.

**Verify:** every code in the table is produced by at least one test; a
270-review store issues far fewer commits and yields identical counts.

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

**Q11 — safety-sweep window.** F3 uses 30 days, a guess. Google does not
publish its moderation delay. Measure how many reviews the first few sweeps
find that the regular delta missed, then tune.

**Q12 — is 5,000 the right default ceiling?** D11 / §4.7. Product decision,
shared with Part 1 Q6.

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
| **J** | **OB-8** edited reviews + approximate dates + cursor display | **CS-7** floating reviews + crawl-coverage cursor | **CS-7 first** — new response fields; OneBox must tolerate their absence |
| **K** | **OB-9** user-facing messages | **CS-8** stable `stop_reason` vocabulary | **CS-8 first** — OneBox maps the codes CS-8 publishes |

**Two ordering rules that will bite if ignored:**

- **Adding a field: crawler first.** `extra="forbid"` turns an unknown field
  into a 422.
- **Removing a field: OneBox first.** Stop sending before the crawler stops
  accepting.

**Capability delivery:** capability 1 (fetch all) lands with **E** + **G**.
Capability 2 (timespan) is usable after **B**+**C** and improves with **A**.
Capability 3 (quasi-realtime) lands with **H**. **J** and **K** make all three trustworthy to a user and should land with the first capability that ships.

---

## 9. Out of scope

- Changing the `GET /integration/v1/reviews` cursor contract. (§5.5 adds
  optional fields only.)
- Competitor crawls. Same mechanisms apply, but they are not among the three
  requested capabilities and `_execute_competitor` (`crawl_worker.py:233`)
  would double the test matrix.
- Google Business Profile API (§4.4) — named, not specced.
- `TECH_DEBT_ONEBOX_APIFY_FIELD_NAMING.md` renaming work.
- Automatic mode selection. The user picks cabang and mode, per the original
  requirement.
