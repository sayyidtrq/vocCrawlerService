# Fetch Jobs enhancement — Part 1 of 2: OneBox

**Repo:** `onecloud` (OneBox) · **Screen:** `/feature/voc/Mediamonitoring/#/voc/fetchjobs`
**Paired with:** [`SPEC_FETCHJOBS_CRAWLER.md`](SPEC_FETCHJOBS_CRAWLER.md) — Part 2, the Crawler Service half
**Contract version consumed:** `crawl-jobs v2` (defined in Part 2 §5)
**Status:** proposal, revised 2026-09-17 after review. No OneBox work started. All `onecloud` paths below are
relative to `onecloud/onecloud/app/`.

---

## Sync rules — read before editing either document

These two documents describe one change split across two repos. They drift
the moment someone edits one and not the other.

1. **Part 2 owns the contract.** The crawler serves
   `POST /api/integration/v1/crawl-jobs`, so the field list, types and
   validation are defined in Part 2 §5. **§5 here is a caller's view derived
   from it — never the source.** If the two disagree, Part 2 is right and
   this document is stale.
2. **The pairing table (§8), the shared decisions (§0) and the review-feedback
   table must be identical in both documents.** It
   is the only place the cross-repo ordering is recorded.
3. **Accept before emit.** Do not ship a OneBox change that *sends* a new
   field until the crawler that *accepts* it is in production. The crawler
   rejects unknown fields with a 422 (Part 2 §5.3), so getting this backwards
   fails every crawl immediately.
4. **Remove in the opposite order.** Stop sending a field here before the
   crawler stops accepting it.

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

Identical in both documents.

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

## 1. Reviewer names — what changed on the crawler, and what OneBox still owes

Full write-up is Part 2 §1. The short version for OneBox devs:

- **Until now every review arrived with `reviewer_name = NULL`.** The Apify
  actor omits reviewer identity unless asked (`include_personal`, default
  `false`). Verified across 2,920 real records: zero named. OneBox rendered
  all of them as "Anonymous"/"Anonim".
- **Fixed on the crawler.** New crawls arrive named. Re-crawling an old
  review now fills its missing name in place and advances its
  `sync_updated_at`, so the next OneBox import re-serves it.
- **OneBox already merges re-served reviews.**
  `VocProvider::rowReview()` → `sudahPernahMasuk()` →
  `perbaruiReviewTersimpan()` (`services/Provider/VocProvider.php:889-895`)
  replaces `MessageContent.Meta` with fresh `buildMeta()` output, and
  `buildMeta()` carries `reviewer_name` (`:1178`). **No change needed for
  that path.**

What the user then sees depends on whether the review has become a ticket.
The Ulasan screens resolve the name as:

```php
$r->ContactName ?: ($meta['reviewer_name'] ?? 'Anonim')
```

(`controllers/VocController.php:3365`, `:4828`, `:7896`; `:3774` is the same
shape with `ReviewerName`.)

| Review state | After re-crawl + import |
|---|---|
| Not yet a ticket — no Contact | ✅ real name, from `Meta` |
| Already a ticket — Contact exists | ❌ **still "Anonymous"** |

Why the second row fails: `rowReview()` stamps the sender as the literal
string `'Anonymous'` when `reviewer_name` is empty (`VocProvider.php:907-908`).
The Contact born from that message when it becomes a ticket inherits
`'Anonymous'` — a non-empty string, so it wins the `?:` and shadows the
repaired `Meta` forever. **That is OB-0.**

One mitigating fact makes OB-0 safe: `buildReviewerIdentity()`
(`VocProvider.php:964-979`) gives an anonymous reviewer the identity
`anonymous-review:<review_hash>` — **one Contact per review**, not one
shared "Anonymous" Contact. Renaming it cannot relabel anybody else.

**Reviews still showing no name after all of this** are ones the crawler has
not re-crawled deeply enough to reach. A `delta` crawl only touches recent
reviews; older history needs a `date_window` or backfill crawl of that
cabang, followed by an import.

**Language, separately:** `Meta.language` stays NULL for all Apify reviews.
The actor never reports the original language (Part 2 §1.2). The review
*text* is the patient's original — only the language tag is missing. Low
priority; nothing to do in OneBox until the crawler starts sending it.

---

## 2. OneBox-side flow

Ends where Part 2 §2 picks up. The `>>>` line is the repo boundary.

```
Fetch Jobs screen                       views/Voc/fetchjobs.volt
  mode select: delta | backfill | custom          :835-848
  target input, hard max 300                      :115
  JS validation 1..300                            :1495
  delta: date_from = last_review_at - 1 day, locked   :879-884
  backfill: target=300, no dates                      :840-843, :885-890
        |
        v  POST
VocController::crawlStartAction()                 controllers/VocController.php:10528
  target required, 1..CRAWL_TARGET_MAX (300)      :67, :10549
  rejects source !== 'selenium'                   :10557-10561   <-- stale
  crawlDateRange()   -> {from, to} UTC            :9057
  crawlSortBy()      -> forced 'newest' if ranged :9044
  jadwalSedangBerjalan()  -> 409 if a schedule is running   :10594
  VOC_SCRAPE / VOC_REVIEW / VOC_AI benefit checks :10612
  verifyBenefit('VOC_SCRAPE', count(targets))     :10635   <-- per call, not per review
        |
        v
Service\VocCrawlQueue::enqueue()                  services/VocCrawlQueue.php:42
  TARGET_MAX = 300                                :26
  one $dateFrom/$dateTo for ALL targets           :88-94
  crawlMode()  -> custom_range | regular_delta    :171   <-- never initial_backfill
  scanLimit()  -> max(500, target*10), cap 5000   :194   <-- nothing downstream reads it
        |
        v
VoiceOfCustomerSystemClient::enqueueCrawl()       library/VoiceOfCustomerSystemClient.php:706
  retries WITHOUT crawl_mode/scan_limit on rejection   :834-849
>>> POST /api/integration/v1/crawl-jobs   (to Crawler)

... crawler works (Part 2) ...

VocController::crawlStatusAction() / crawlHistoryAction()   :11880, :11949
  polls GET /crawl-jobs/{batch_id}

VocController::crawlImportAction()                :15452
  VocProvider::receive()                          services/Provider/VocProvider.php
    page_size default 50, max_pages default 10    :98-99   <-- 500 reviews per call
    fetchPage() -> GET /integration/v1/reviews    library/VoiceOfCustomerSystemClient.php:194
    rowReview() per item; re-served -> perbaruiReviewTersimpan()   :889-895
  applyAnalysis(), labelPendingReviews(), recordRatingSnapshot()
```

Scheduled crawls take the same `VocCrawlQueue::enqueue()` path, via
`VocSchedule` / `VocScheduleRun` and `library/VocCron.php`. Relative
lookback is resolved at run time by `VocCrawlQueue::dateRangeForSchedule()`
(`:229`), which also applies the watermark (`watermarkFrom()`, `:321`).

---

## 3. OneBox-side bottlenecks

Crawler-side bottlenecks are in Part 2 §3. B-numbers are shared across both
documents so a bottleneck keeps one name; gaps here are crawler-only items.
Items marked ⇄ span both repos.

### ⇄ B1. The 300 cap, OneBox half **[blocks fetch-all]**

| Where | Line |
|---|---|
| Where | What it limits | Line |
|---|---|---|
| `VocController::CRAWL_TARGET_MAX` | manual crawl, cabang + competitor | `controllers/VocController.php:67` (used `:9343`, `:10549`) |
| `VocCrawlQueue::TARGET_MAX` | every enqueue | `services/VocCrawlQueue.php:26` |
| `max(1, min(300, $target))` | **per-cabang review target when a location is saved** | `controllers/VocController.php:10177-10179` |
| `max(1, min(300, …))` | location payload sent to the crawler | `controllers/VocController.php:12188`, `:13777` |
| "Target jumlah review … 1 sampai 300" | location form validation | `controllers/VocController.php:13378-13384` |
| input `max="300"` | Fetch Jobs | `views/Voc/fetchjobs.volt:115` |
| `target: 300` | Fetch Jobs backfill default | `views/Voc/fetchjobs.volt:842` |
| JS `target > 300` + modal | Fetch Jobs | `views/Voc/fetchjobs.volt:1495-1496` |
| input `max="300"` | Schedules | `views/Voc/schedules.volt:235` |
| JS "harus 1 sampai 300" | Schedules | `views/Voc/schedules.volt:1401` |
| `$target > 300` | schedule save | `library/VocCron.php:335-336` |

Thirteen literals, five meanings, no shared constant. The per-cabang target
at `:10177` is the "benefit quota review" raised in review: every cabang is
created with a ceiling of at most 300, and the crawler's own default is 100.
D11 replaces all of them with **one** default (5,000) and **one** maximum
(100,000) — OB-2.

The `VOC_REVIEW` benefit itself is not 300: the smallest package is 5,000
per month (`benefitPackages()`, `:2210-2216`; migration
`1786000000000000_1_123_0/Benefit.php:45`). The per-crawl caps above are
what actually limited users.

The actor's own `limit` goes to **100,000**. The 300 was a Selenium
survivability limit and has no meaning against an HTTP API billed per
review. The crawler half of the cap is Part 2 §3 B1 — **raising only one
side changes nothing**, because the crawler also rejects anything above 300.

### B2. "Fetch all" cannot be expressed **[blocks fetch-all]**

`VocCrawlQueue::crawlMode()` (`:171-174`) returns only `custom_range` or
`regular_delta`. The contract has carried `initial_backfill` at every layer,
and OneBox has never sent it. The docblock at `:160-166` explains why: it
needed each cabang's Google review count, which did not exist then.

That count now arrives on every crawled review (`place_reviews_count`) and
is captured by the crawler. **The stated blocker is gone.**

Meanwhile the UI's "Backfill Awal" mode (`fetchjobs.volt:840-843`) is
described as *"Ambil riwayat ulasan sedalam mungkin"* and actually sends
`target = 300`, no dates. On a place with 9,422 reviews that is 3%
coverage, presented to the user as "as deep as possible". The hint text at
`:890` — *"Crawler menyisir sedalam yang diizinkan batas waktu"* — describes
Selenium behaviour that no longer exists.

### ⇄ B7. Date windows cost by age — and the UI does not say so **[blocks timespan]**

Mechanism is in Part 2 §3 B7: the actor only accepts a *lower* date bound,
so "Jan–Mar 2024" pays to scrape everything from Jan 2024 to today, and the
crawler discards the rest after paying.

The OneBox part of the problem is that nothing tells the user. The custom
mode hint (`fetchjobs.volt:845`) reads *"Untuk audit atau menambal periode
tertentu"* — framing that invites exactly the expensive request.
`total_skipped_out_of_range` comes back in every batch result and is not
surfaced as a cost.

### B8. One date range for the whole batch **[biggest cheap saving]**

`VocCrawlQueue::enqueue()` gives every target the same `$dateFrom` /
`$dateTo` (`:88-94`). For scheduled delta runs, `watermarkFrom()`
deliberately takes the **oldest** "newest review" across all cabang
(`:349-357`, rationale `:308-312`) — correct, because one shared date must
be safe for every cabang in the batch.

The consequence: **one lagging cabang forces all of them to re-scrape from
its date.** Under Selenium that cost minutes. Under per-review billing it
costs money, on every scheduled run, for every cabang.

The crawler contract **already accepts `date_from`/`date_to` per target**,
and the crawler already routes them per location. OneBox just never varies
them. The fix is local to this repo — OB-1.

The same shape affects `crawlMode()`; its docblock (`:167-169`) notes that a
per-cabang mode needs the batch split per cabang. Under contract v2 each
target carries its own `coverage`, so that split is no longer needed.

### B9. The watermark margin — keep it, keep its reason

`WATERMARK_MARGIN_DAYS = 1` (`VocCrawlQueue.php:284`). Its docblock
(`:272-283`) says `review_time` is estimated from relative text
("2 minggu lalu"), so starting exactly at the watermark would lose reviews.

**An earlier revision of this document said that reason no longer applied
under Apify. That was wrong.** Real data shows Apify's dates are *also*
mostly estimated from relative text (Part 2 B17): "a year ago" is stored as
exactly 365 days before the crawl for 84 of 91 such reviews. The margin and
its explanation are both still correct. Add the measurement to the comment
(OB-7); do not remove either.

For the delta cursor the estimate is precise enough — reviews near the
cursor are days old, and Google reports those to the day. The estimate only
becomes coarse for reviews months or years old (§4.7).

The `ZONA_ONEBOX` handling (`:294`, `:379-392`) is still correct and still
necessary — do not touch it.

### B10. The 60-minute schedule floor is calibrated to Selenium **[blocks realtime]**

`VocCron::MIN_INTERVAL_MINUTES = 60` (`library/VocCron.php:32`), justified
at `:24-31`: *"pada 11 Agustus 2026 sebuah run bertarget 5 berjalan 619
detik."*

619 seconds for five reviews was a browser scrolling Google Maps. An Apify
delta run against a cabang with no new reviews is an HTTP round trip plus
actor startup. The floor is the single OneBox blocker for quasi-realtime,
and the measurement behind it describes a system that no longer exists.

It must be **re-measured**, not simply lowered on this argument — OB-5.

### B11. Import stops at 500 reviews per call **[blocks fetch-all]**

`VocProvider.php:98-99`:

```php
$pageSize = min(200, max(1, (int)($this->extras['page_size'] ?? 50)));
$maxPages = max(1, (int)($this->extras['max_pages'] ?? 10));
```

50 × 10 = **500 reviews per `receive()`**, after which the
`do … while ($hasMore && $page <= $maxPages)` loop (`:252`) stops and parks
the position in `Options._sync_next_cursor`. The crawler serves at most 200
per page (`MAX_LIMIT`).

A 3,000-review backfill therefore needs six import presses. The resume
mechanism exists (`crawlImportAction`'s `resume` flag, and the cursor state
at `:463-465`, `:592-642`), but nothing drives it to completion. Once
fetch-all works on the crawler side, this is the next wall — OB-4.

### ⇄ B12. OneBox rejects any source but `selenium`

`VocController.php:10555-10561`:

```php
// Selenium satu-satunya sumber yang didukung antrean durable saat ini.
if ($source !== '' && $source !== 'selenium') {
    return $this->jsonFail('Sumber "' . $source . '" belum didukung. Saat ini crawl hanya lewat Selenium.');
}
```

Harmless today because the UI sends nothing, so `$source` defaults to
`'selenium'`. But the comment is false, the default is false, and the first
caller to send `source=apify` is refused with a message claiming Selenium is
the only option. OB-7.

### ⇄ B17. Old review dates are estimates, and the screens show them as exact

Mechanism in Part 2 B17. In OneBox it shows up as:

- a review from 2024 displayed as *"15 Sep 2025"* because Google said
  "a year ago" on 15 Sep 2026;
- monthly trend and "bulan lalu" benchmark (notulen 2026-08-21 §A) built
  from those dates — old months look empty, a few dates look crowded;
- a custom date range over an old period appearing to have almost no
  reviews.

None of this is visible to the user today. §4.7 / OB-8.

### ⇄ B19. Edited reviews never reach OneBox

When a reviewer edits text or stars, the crawler currently drops the change
(Part 2 B19). Once CS-7 stores it and re-serves the review,
`perbaruiReviewTersimpan()` refreshes `Meta` — but `MessageContent.Body`,
the sentiment label and any ticket are left as they were. OB-8.

### ⇄ B20. The cursor measures imports, not crawls

`last_review_at` comes from `ulasanTerbaruPerKoneksi()`
(`VocController.php:9984`) and `watermarkFrom()` (`VocCrawlQueue.php:343-357`),
both reading OneBox's own `Message` rows. If import is behind (B11), the
cursor is behind, and the next fetch re-crawls what the crawler already has.
Part 2 §4.5 moves the source of truth to the crawler; OneBox keeps its value
for display and as a fallback.

### B21. Messages that mislead

Found in `fetchjobs.volt`:

| Where | Problem |
|---|---|
| `STOP_ALASAN` (`:1163-1167`) | Matches Selenium's raw keys (`time_limit`, `max_scroll_attempts`, `no_new_review_cards`). The crawler publishes mapped codes (`timeout`, `no_more_reviews`, …) and Apify's own. **No stop reason is ever shown.** |
| `STATE_LABEL.PARTIAL` (`:1012`) | Says *"Sebagian cabang gagal"* for every `partial_success`, including a single cabang that simply hit its ceiling. Nothing failed. |
| `STATE_LABEL.RUNNING` (`:1007`) | *"Mengambil review dari Google"* for the whole run, then a jump — the crawler only reports progress twice (Part 2 B14). Looks frozen. |
| `diagnosaCrawl()` (`:1180-1186`) | Talks about the *"Terbaru"* sort failing to apply in Google Maps — a Selenium failure mode that cannot happen with Apify. |
| backfill hint (`:841`, `:890`) | *"sedalam mungkin"* / *"sedalam yang diizinkan batas waktu"* while sending a 300 cap. |
| validation (`:1496`) | *"Batas pengambilan antara 1 dan 300"* — the number is ours, not Google's, and the user cannot tell. |
| duplicates | Shown next to *"gagal"* in the same counter line (`:1091-1097`: *baru · duplikat · di luar rentang · gagal*), so a normal re-crawl reads like an error. |

A user reading these cannot tell *done*, *done but partial*, *nothing new*,
*still retrying* and *broken* apart. §4.6 / OB-9.

### B15. Benefit quota counts calls, not reviews

`verifyBenefit('VOC_SCRAPE', $jumlahTarget)` (`VocController.php:10633-10635`)
charges **one unit per target cabang**, regardless of how many reviews the
crawl will pull. With a 300 cap the ratio was bounded. With the cap removed,
one "fetch all" unit can mean 10,000 billed reviews.

This is a product decision, not a bug — Q6. It must be decided before OB-2
reaches production.

### B16. `crawl_mode` / `scan_limit` fallback hides contract mismatches

`VoiceOfCustomerSystemClient::enqueueCrawl()` (`:834-849`) catches a
rejection of the new fields and **retries without them**, logging
*"Crawler menolak field kontrak baru (crawl_mode/scan_limit)"*. That was the
right call for the v1 rollout. For v2 it is dangerous: a `coverage` field
the crawler does not yet accept would be silently stripped, and a
`full_backfill` request would quietly run as a default delta. OB-2 must not
extend this fallback to `coverage`/`budget`.

---

## 4. Design, OneBox side

### 4.1 Mode is the user's choice — make it explicit

The three capabilities map onto the three modes the screen already has.
Only what each one *sends* changes:

| UI mode (existing) | Capability | Sends (v2) | Date fields | Count field |
|---|---|---|---|---|
| **Update Terbaru** (`delta`) | 3, and routine | `coverage: "delta"` | auto from watermark, locked (as today) | hidden; optional budget |
| **Backfill Awal** (`backfill`) | 1 — fetch all | `coverage: "full_backfill"` | none, **forbidden** by the contract | replaced by the estimate (OB-6) |
| **Custom** (`custom`) | 2 — timespan | `coverage: "date_window"` | from/to required | optional budget |

The existing autofill guard (`targetDisentuh`, `fetchjobs.volt:853-854`) and
the zero-review redirect to backfill (`:956-966`) both stay; they are still
right.

The "Batas pengambilan" field stops being a goal and becomes a ceiling. Its
current comment (`:110`) already says so — *"sebuah BATAS"* — the rest of
the screen just does not behave that way yet.

### 4.2 Fetch all needs a cost preview, not a number box

Removing the 300 cap turns one click into a potentially large bill. The
backfill mode must show, before the Mulai button does anything:

> **Perkiraan ~9.422 ulasan** untuk Hermina Bekasi. Kuota bulan ini tersisa
> 12.000. [Mulai backfill]

The number comes from the crawler's estimate endpoint (Part 2 CS-5).
Require an explicit confirm above a threshold. Reject before enqueue — not
after — when the estimate exceeds the remaining budget; the existing pattern
of checking quotas *before* touching the queue (`VocController.php:10591-10593`)
is the model to follow.

### 4.3 Timespan: say what it costs

Per D7, a window's cost is set by its *start*, not its width. Three
changes:

1. **Estimate.** For a window, show roughly how many reviews will be scanned
   to find the ones inside it. The crawler returns the place's total count
   and the cabang's recent cadence can be derived from reviews OneBox
   already holds.
2. **Report the waste after the fact.** Show `total_skipped_out_of_range`
   in the history row as "disisir tapi di luar rentang". The history
   renderer already separates matched from scanned (`fetchjobs.volt:757-762`,
   `:1045-1071`); extend that rather than adding a new widget.
3. **Rewrite the hint** next to the date picker: a window ending recently is
   cheap; a window ending long ago costs everything since its start.

### 4.4 Quasi-realtime — what OneBox owns

**True realtime is not available for Google Maps reviews** — no webhook
exists. The only genuine push path is the Google Business Profile API
(Part 2 §4.4), a separate integration.

What OneBox owns is the **schedule**:

- Allow tighter intervals once the Selenium-era floor is replaced by a real
  measurement (B10).
- Before enqueueing, ask the crawler whether the cabang's review count
  moved (Part 2 CS-4). If not, record the run as skipped and spend nothing.
- **Keep an unconditional slower delta underneath** (the current hourly
  schedule is fine). The count probe does not notice an *edited* review, or
  an add and a delete in the same window. The fast gated schedule is an
  optimisation; the slow ungated one is the correctness floor.

The existing overlap guard — a running schedule blocks a manual crawl of
the same cabang (`jadwalSedangBerjalan()`, `VocController.php:10594`; UI
warning at `fetchjobs.volt:930-935`) — becomes more important at tight
intervals, not less. Keep it.

---

### 4.5 The per-cabang cursor — what the user sees

The design stays: **one cursor per cabang** (D9). Review example —
**Pertamina Margonda**: the initial backfill collected ~1,100 reviews, the
newest dated 16 September; every later fetch, manual or scheduled, defaults
to *16 September minus one day → newest*.

Why it was slow and produced many duplicates, and what fixes each (full
table in Part 2 §4.5):

| Cause | Fix | Owner |
|---|---|---|
| Cursor read from OneBox's imported rows, so it lags whenever import lags | Crawler keeps its own coverage state and never starts before it | CS-7 |
| Scheduled batches share the oldest cursor across all cabang | Per-cabang dates | **OB-1** |
| Import stops at 500 per call, so the cursor falls further behind | Auto-resume import | **OB-4** |
| Unstable `review_hash` → the same review imported twice | Crawler identity by `external_review_id` (OneBox's own guard stays) | CS-7 |
| One-day margin re-crawls a day each run | **Keep.** Show these as *"sudah ada"*, not as a problem | **OB-9** |
| Selenium scrolling | Already gone | — |

What changes on screen:

- The Fetch Jobs status panel shows the **crawler's** coverage for the
  selected cabang (from the estimate endpoint / job result), not only
  OneBox's newest imported review:

  > **Pertamina Margonda** · Place ID … · 1.100 ulasan di OneBox
  > Riwayat lengkap sampai **16 Sep 2026** · penarikan terakhir 17 Sep, 06:00

  and, when the backfill is not complete:

  > Riwayat baru terambil sampai **Mar 2024** (perkiraan). Jalankan
  > **Ambil Semua** untuk melengkapi.

- **Update Terbaru** keeps its locked start date (`fetchjobs.volt:879-884`)
  and its note, reworded: *"Mulai dari ulasan terbaru yang sudah
  diambil (16 Sep), mundur 1 hari supaya tidak ada yang terlewat."*
- **Rentang Khusus** does not move the cursor (Part 2 §4.5 point 4). Say so
  under the date picker: *"Rentang khusus tidak mengubah titik mulai Update
  Terbaru."*
- Per Pak Indra's rule (D8), **Rentang Khusus takes every review in the
  range.** The count field is gone from this mode; only the optional cost
  ceiling remains, collapsed under *"Batas biaya (opsional)"*. If a window
  ends incomplete, the history row says so and offers *"Lengkapi rentang
  ini"*.
- The scheduler may keep its per-run count (D8) — it becomes a ceiling with
  the new default.

### 4.6 Messages, toasts and alerts

Principle: **every message says what happened, what it means for the
user's data, and what — if anything — to do next.** No crawler vocabulary on
screen: no *Apify, worker, actor, cursor, scan, kartu, gulir, batch*.

**Which surface for what:**

| Surface | Use for | Never for |
|---|---|---|
| **Toast** (auto-hide ~5 s) | confirmation of an action the user just took | anything the user must act on |
| **Status panel** (`statusPanel`, stays) | the live state of the current run, and pre-flight warnings | confirmations |
| **Modal** (`showInfoModal`) | a decision is needed, or the request was refused | progress, success |
| **History row** | the final outcome, readable days later | — |

One event → one message. Do not show a toast *and* a modal for the same
thing.

**Wording rules:**

1. Use *ulasan* throughout (not a mix of review / rating / ulasan).
2. Numbers always carry their meaning: *"12 ulasan baru"*, never *"12 / 50"*.
3. **Duplicates are not errors.** Say *"sudah ada di OneBox"*, never beside
   *gagal*.
4. **Nothing new is a success.** Green, not grey or yellow.
5. Partial ≠ failed. Say what was kept and what is missing.
6. Automatic retries say they are automatic, and when.
7. Old dates are approximate; say so where they are shown (§4.7).
8. A refusal says **why** and **what to change**, in that order.

**Message catalogue.** `{…}` are values from the job result. Codes are the
Part 2 CS-8 `stop_reason` list; OB-9 maps each exactly once.

| # | Situation (code / state) | Surface · tone | Title | Body | Action |
|---|---|---|---|---|---|
| M1 | Request accepted | toast · info | Penarikan dimulai | {cabang} · {mode}. Hasilnya muncul di Riwayat Fetch; halaman ini boleh ditinggal. | — |
| M2 | Waiting in queue | panel · neutral | Menunggu giliran | Ada {n} penarikan lain di depan. | — |
| M3 | Running, count known | panel · neutral | Mengambil ulasan {cabang} | {x} dari sekitar {expected} ulasan · berjalan {mm:ss} | — |
| M4 | Running, count unknown | panel · neutral | Mengambil ulasan {cabang} | Sedang berjalan {mm:ss}. Jumlah muncul begitu data pertama masuk. | — |
| M5 | Saving to OneBox (OB-4) | panel · neutral | Menyimpan ke OneBox | {i} dari {n} ulasan disimpan. | — |
| M6 | `no_new_reviews` | panel + history · **success** | Tidak ada ulasan baru | {cabang} sudah terbaru sampai {tanggal}. {d} ulasan yang dicek sudah ada di OneBox. | — |
| M7 | delta, new found | panel + history · success | {x} ulasan baru masuk | {d} lainnya sudah ada di OneBox. | Buka Kelola Ulasan |
| M8 | backfill `coverage_complete` | panel + history · success | Riwayat {cabang} lengkap | {collected} ulasan, sesuai jumlah di Google ({expected}). Selisih kecil wajar: ulasan tanpa teks atau yang dihapus. | Buka Kelola Ulasan |
| M9 | window `coverage_complete` | panel + history · success | {x} ulasan dalam {from}–{to} | {d} sudah ada sebelumnya. Tanggal ulasan yang lebih lama dari sebulan adalah perkiraan dari Google. | Buka Kelola Ulasan |
| M10 | window, skipped newer | inline under M9 · neutral | — | Untuk sampai ke rentang ini, {s} ulasan yang lebih baru ikut dicek lalu dilewati. | — |
| M11 | `budget_exhausted` | panel + history · **warning** | Belum lengkap — batas pengambilan tercapai | Tersimpan {collected} dari sekitar {expected} ulasan. Naikkan batas untuk melanjutkan. | Lanjutkan |
| M12 | `source_not_confirmed`, will retry | panel + history · warning | Belum selesai — dicoba lagi otomatis | Pengambilan {cabang} belum tuntas. {k} ulasan yang sudah terambil tetap disimpan. Dicoba lagi sekitar pukul {jam}. | — |
| M13 | `source_quota_exhausted` | panel + history · warning | Kuota layanan pengambilan habis | {k} ulasan tersimpan. Sisanya dilanjutkan otomatis pada penarikan berikutnya. Hubungi admin bila berulang. | — |
| M14 | `deadline_exceeded` | panel + history · warning | Penarikan terlalu lama dan dihentikan | {k} ulasan tersimpan. Coba **Rentang Khusus** yang lebih pendek. | Coba lagi |
| M15 | failed, config (`classifyError` = config) | panel + history · error | Penarikan gagal | {alasan dari classifyError}. | Buka Lokasi / hubungi admin |
| M16 | failed, transient, retries used up | panel + history · error | Penarikan gagal setelah {n} percobaan | {k} ulasan sempat tersimpan. Coba lagi nanti. | Coba lagi |
| M17 | `target_disabled` | history · neutral | Dilewati | {cabang} nonaktif saat giliran tiba. | Buka Lokasi |
| M18 | batch, some cabang failed | panel · warning | {f} dari {n} cabang gagal | Cabang lain selesai. Lihat rinciannya di bawah. | — |
| M19 | batch, some cabang partial | panel · warning | {p} dari {n} cabang belum lengkap | Tidak ada yang gagal. | — |
| M20 | pre-flight: estimate > remaining quota | modal · refusal | Kuota ulasan bulan ini tidak cukup | Perkiraan {est} ulasan, sisa kuota {rem}. Pilih **Update Terbaru** atau **Rentang Khusus**, atau tambah kuota di Pengaturan. | Pengaturan |
| M21 | pre-flight: large backfill | modal · confirm | Ambil sekitar {est} ulasan? | Menurut Google, {cabang} punya {est} ulasan. Ini memakai {est} dari sisa kuota {rem}. | Batal · Ambil semua |
| M22 | invalid ceiling | modal · refusal | Batas pengambilan tidak valid | Isi angka 1 sampai 100.000, atau kosongkan untuk memakai batas bawaan (5.000). | — |
| M23 | window with no start date | modal · refusal | Rentang Khusus butuh tanggal awal | Pilih tanggal awal. Untuk seluruh riwayat, pakai **Ambil Semua**. | — |
| M24 | old window chosen | inline hint · neutral | — | Rentang yang jauh ke belakang mengecek semua ulasan sesudahnya, jadi lebih lama dan lebih banyak memakai kuota. | — |
| M25 | edited review (OB-8), in the list | badge | *Diubah* | tooltip: Diubah pengulas sekitar {edited_at}. Isi dan bintang sudah diperbarui. | — |

Kept as they are (already clear): *Pilih cabang dulu*, *Cabang belum punya
Place ID*, *Jadwal sedang berjalan untuk cabang ini*, *Rentang tanggal
terbalik*, *Sudah diantre*, *Cabang ini belum punya ulasan*.

**Renames:** mode *"Backfill Awal"* → **"Ambil Semua"**; *"Update
Terbaru"* stays; *"Custom"* → **"Rentang Khusus"** (already used in
messages). *"Batas pengambilan"* → **"Batas biaya (opsional)"**.
`STATE_LABEL.PARTIAL` → M19 wording. `STATE_LABEL.COMPLETE` stays
(*"Ulasan siap dikelola"*).

### 4.7 Approximate dates and edited reviews on screen

- Where a review date is shown and `date_approximate` is true, show
  **"± Sep 2025"** (month) or **"± 2025"** (year) instead of a full date,
  with the tooltip *"Perkiraan dari Google ('setahun lalu' saat diambil)"*.
  Sorting still uses the stored date.
- Trend charts and the *bulan lalu* benchmark: count approximate reviews in
  a separate, lighter series — or exclude them — and say which in the chart
  legend. **Do not silently mix them.** Product decides which (Q13).
- The `Rating Google` snapshot is unaffected: it is stored, not computed
  from dates.
- Edited reviews: badge **Diubah** (M25). When the crawler re-serves an
  edited review, update the body and star rating, re-run the native
  sentiment label, and — if a ticket exists — add a ticket note
  *"Ulasan diubah pengulas: ★{lama} → ★{baru}"* instead of editing the
  ticket's original description.

## 5. Contract `crawl-jobs v2` — CALLER'S VIEW (derived from Part 2 §5)

**Not the source of truth.** If this disagrees with Part 2 §5, Part 2 is
right.

### 5.1 What OneBox sends per target

```jsonc
{
  "kind": "location",
  "onebox_location_id": 123,
  "coverage": "delta" | "date_window" | "full_backfill",
  "budget": 5000,                       // optional ceiling, 1..100000
  "date_from": "2026-01-01T00:00:00Z",  // date_window only; per target
  "date_to":   "2026-03-31T16:59:59Z",  // date_window only; per target
  "sort_by": "newest"
}
```

Rules the crawler enforces (and OneBox should pre-check, to give a readable
error instead of a 422):

- `date_window` needs at least one of `date_from` / `date_to`.
- `full_backfill` must carry **no** dates.
- Count fields are capped at 100,000, not 300.
- Unknown fields are rejected — never send a field the deployed crawler does
  not know yet.

### 5.2 Legacy fields during rollout

Until OB-2 ships, OneBox keeps sending what it sends today, and the crawler
maps it:

```
crawl_mode=regular_delta     -> coverage=delta
crawl_mode=custom_range      -> coverage=date_window
target_review_count          -> budget
scan_limit                   -> ignored
```

That mapping is what lets the crawler deploy first without OneBox changing.

### 5.3 What comes back — new result metadata

Per job in `GET /crawl-jobs/{batch_id}`:

```jsonc
"coverage": "full_backfill",
"expected_review_count": 9422,     // Google's own count for the place
"collected_unique": 9301,
"completeness": "complete" | "partial" | "unknown",
"completeness_ratio": 0.987,
"budget": null,
"stop_reason": "coverage_complete" | "budget_exhausted" | ...
```

`completeness` is the field the history screen should show for backfills —
it answers "did we get everything?", which the current `n / target` display
cannot. Treat `"unknown"` as unknown, **never** as complete.

`stop_reason` values are the CS-8 list: `coverage_complete`,
`no_new_reviews`, `budget_exhausted`, `source_quota_exhausted`,
`source_not_confirmed`, `deadline_exceeded`, `target_disabled`. Map each to
one message (§4.6) and show unknown codes as a neutral *"Selesai"* with the
raw code in the detail view — never as silence.

Each job result also carries a `coverage` object (Part 2 §4.5): newest and
oldest crawled date, their precision, and whether a full backfill has
completed.

`expected_review_count` is also the right number for
`recordRatingSnapshot()`'s Google count (`crawlImportAction`), which today
reads it from the batch via `googleRatingDariBatch()`.

### 5.4 Review API additions (`GET /integration/v1/reviews`)

Optional keys — treat each as possibly absent:

```jsonc
"review_time_precision": "day" | "week" | "month" | "year" | "unknown",
"date_approximate": true,
"is_edited": true,
"edited_at": "2026-07-17T00:00:00Z"
```

Store them in `Meta` via `buildMeta()` (`VocProvider.php:~1150-1185`).

---

## 6. Work packages

Formatted for delegation: exact files, exact change, how to verify, what not
to touch. Paths relative to `onecloud/onecloud/app/`.

---

### OB-0 — Replace "Anonymous" Contacts once the real name arrives

**Depends on:** crawler CS-0 (shipped). **Independent of everything else.**

**Problem:** §1. Ticketed reviews keep showing "Anonymous" after the crawler
repairs their name, because the Contact's name shadows `Meta`.

**Change:** in `VocProvider::perbaruiReviewTersimpan()`
(`services/Provider/VocProvider.php:~790-839`), after the `Meta` merge
succeeds, when the incoming `reviewer_name` is non-empty:

1. find the Contact attached to this message's ticket, if any;
2. **only if its name is exactly `'Anonymous'`**, set it to the real name.

Guards, all required:

- **Exact-match only.** Never touch a Contact whose name is anything else —
  staff may have renamed it by hand.
- **Only anonymous-identity Contacts.** Their identity is
  `anonymous-review:<review_hash>` (`buildReviewerIdentity()`, `:964-979`),
  so each belongs to exactly one review and renaming cannot relabel another
  person. If the Contact's identity is not of that form, leave it.
- **Do not re-key the identity.** Merging this Contact into the reviewer's
  other Contacts (same real name / profile URL) is a separate, riskier
  feature — out of scope.

**Cheaper partial alternative, if OB-0 must wait:** change the display
precedence at `VocController.php:3365`, `:3774`, `:4828`, `:7896` so a
`ContactName` equal to `'Anonymous'` falls through to `Meta.reviewer_name`.
Four one-line changes, no data written. It fixes the Ulasan screens only —
the ticket and contact screens still say "Anonymous" — so treat it as a
stopgap, not the fix.

**Verify** (`tests/voc/`, following the existing `*_check.php` style):
a ticketed review with Contact `'Anonymous'` becomes named after a re-served
row carries `reviewer_name`; a Contact already named "Budi" is unchanged by
a row naming "Andi"; a row with empty `reviewer_name` changes nothing.

**To see the result on real data:** re-crawl the cabang at a depth that
reaches the old reviews, then run the import (`crawlImportAction`).

---

### OB-1 — Per-cabang date ranges *(cheapest high-value item)*

**Depends on:** nothing — the crawler already accepts per-target dates.
Ship anytime.

**Files:**
- `services/VocCrawlQueue.php` — `enqueue()` (`:60-102`) builds each target
  with **its own** `date_from`; `watermarkFrom()` (`:321-399`) returns a
  per-connection map instead of one `MIN()`
- `services/VocCrawlQueue.php` — `dateRangeForSchedule()` (`:229-269`)
  returns per-location ranges for delta schedules

**Keep, per cabang:** the "a cabang with zero reviews gets no narrowing"
rule (`:314-317`, `:367-371`). Today one empty cabang cancels narrowing for
the whole batch; after this it cancels it only for itself.

**Keep unchanged:** "watermark only narrows, never widens" (`:299-306`) —
still correct per cabang. The `ZONA_ONEBOX` conversion (`:379-392`) — still
necessary. The explicit-date schedule path (`:234-254`) — explicit dates
stay shared, since the user chose them.

**Verify:** extend `tests/voc/voc_crawl_queue_check.php` — a two-cabang
batch where A is current and B is a month behind sends two different
`date_from` values; a batch with one empty cabang still narrows the other.

**Impact:** direct saving on every scheduled run, proportional to how far
behind the most-lagging cabang is.

---

### OB-2 — Send contract v2: `coverage` + `budget`; remove the 300 cap

**Depends on:** crawler **CS-1 in production**, and **OB-6 + CS-5** before
this reaches production (spend guard). Rule 3 of the sync rules applies.

**Files:**
- `services/VocCrawlQueue.php`
  - `enqueue()` — take `$coverage` (and per-target dates from OB-1); emit
    `coverage` + `budget` per target
  - replace `TARGET_MIN`/`TARGET_MAX` (`:25-26`) with the **single source
    of truth** for D11:
    ```php
    const DEFAULT_REVIEW_LIMIT = 5000;    // was 300 / 50 / 100
    const MAX_REVIEW_LIMIT     = 100000;  // the source's own maximum
    ```
    and point **all 13 literals in B1** at these two constants —
    `VocController.php:67, 10177-10179, 12188, 13378-13384, 13777`,
    `VocCron.php:335`, and pass them to `fetchjobs.volt` / `schedules.volt`
    as template variables instead of hardcoding them in HTML and JS.
    Schedules and Update Terbaru may keep a smaller *pre-filled* value
    (e.g. 500) — pre-fill, not cap
  - `crawlMode()` (`:171`) — delete; the caller states the mode
  - `scanLimit()` (`:191-199`) — stop sending; delete in OB-7
- `controllers/VocController.php`
  - `crawlStartAction()` (`:10528`) — read the UI mode, map to `coverage`;
    stop requiring `target_review_count` for `full_backfill`
    (`:10543-10545`)
  - `CRAWL_TARGET_MAX` (`:67`) — delete; use
    `VocCrawlQueue::MAX_REVIEW_LIMIT` (also in
    `competitorCrawlStartAction()`, `:9343`)
  - location save (`:10177-10179`, `:13378-13384`) — default for a new
    cabang is `DEFAULT_REVIEW_LIMIT`; existing cabang keep their stored value
    unless product decides on a one-off raise
- `library/VoiceOfCustomerSystemClient.php` — `enqueueCrawl()` (`:706`):
  send the new fields; **do not** add `coverage`/`budget` to the
  strip-and-retry fallback at `:834-849` (B16) — a stripped `coverage`
  silently turns a backfill into a delta

**Verify:** `voc_crawl_queue_check.php` — each UI mode produces the right
`coverage`; `full_backfill` sends no dates; a budget above 100,000 is
refused locally with a readable message.

**Do not touch:** the idempotency key (`crawlStartAction`, `:10620-10626`),
the quota-before-queue ordering (`:10591-10593`), the schedule overlap guard.

---

### OB-3 — Fetch Jobs screen: modes that mean what they say

**Depends on:** OB-2 (and therefore CS-1).

**File:** `views/Voc/fetchjobs.volt`

- `MODE` table (`:835-848`) — drop the per-mode `target` defaults; backfill
  has no count to default
- `terapkanMode()` (`:869-907`)
  - `backfill`: hide the count field; show the estimate (OB-6); rewrite the
    note at `:890`
  - `custom`: add the cost hint (§4.3); make at least one date required
    (the existing check at `:1521-1525` already covers the from-date)
  - `delta`: unchanged behaviour
- input `#fj-single-target` (`:115`) and its validation (`:1487-1497`) —
  becomes an optional ceiling, bounds from the contract, not `1..300`
- history rendering (`:757-762`, `:1045-1071`, `:1178-1193`) — for
  backfills show `completeness` and `collected_unique / expected_review_count`
  instead of `n / target`; show `total_skipped_out_of_range` as waste
- "run again" (`:779`) — must replay `coverage`, not a target count

**Verify:** `tests/voc/volt_compile_check.php` still passes; manual check of
all three modes against a dev crawler with CS-1 deployed.

**Do not touch:** the zero-review redirect to backfill (`:956-966`), the
`targetDisentuh` guard (`:853-854`), the status panel warnings
(`:909-949`) — all still correct.

---

### OB-4 — Import must keep up with fetch-all

**Depends on:** nothing technically; matters once CS-3 makes fetch-all real.

**Problem:** B11 — 500 reviews per `receive()`.

**Options, cheapest first:**

1. **Auto-resume in `crawlImportAction()`** (`:15452`): after a batch that
   ends with more pages pending, keep calling with `resume=1` until the
   cursor is exhausted or a time budget per request is spent, and report
   progress. The cursor bookkeeping already exists
   (`VocProvider.php:463-465`, `:592-642`).
2. **Raise the per-connection defaults** — `page_size` to 200 (the
   crawler's max) and `max_pages` higher. One-line change, but a single
   request then runs long enough to hit web-server timeouts. Measure before
   choosing a number.
3. **Move import to a background task** (`tasks/VocTask.php` exists). The
   right answer at scale; the largest change.

Recommended: option 1 now, option 3 if backfills of many thousands of
reviews become routine.

**Verify:** a connection with 1,200 pending reviews imports all of them from
one user action, and the cursor ends at the checkpoint.

**Do not touch:** the dead-letter logic (`GAGAL_MAKS`, `:509`, `:554`) and
the "failed rows hold the cursor" rule (`:171-174`, `:228-238`).

---

### OB-5 — Quasi-realtime schedules

**Depends on:** crawler **CS-4** (count probe) in production; practically
also CS-3, or tight schedules queue up behind long crawls.

**Files:**
- `library/VocCron.php:32` — lower `MIN_INTERVAL_MINUTES`
- `views/Voc/schedules.volt` — expose the tighter presets
- `controllers/VocController.php` — `scheduleSaveAction()` (`:11347`)
  enforces the new floor; `scheduleRunNowAction()` (`:11625`) unchanged
- the scheduler run path (`tasks/VocTask.php`) — call the probe first; if
  the count did not move, write a `VocScheduleRun` row with a
  `skipped_no_change` outcome and do not enqueue

**Before lowering the floor:** measure real Apify delta-run wall time for a
cabang with no new reviews, ~20 runs. Set the floor from that measurement
plus headroom, and **rewrite the docblock at `VocCron.php:24-31`** with the
new measurement. Do not replace one guess with another.

**Keep:** an unconditional (un-gated) delta schedule per cabang at the
current hourly rate as the correctness floor (§4.4).

**Verify:** a gated schedule against an unchanged cabang produces
`skipped_no_change` runs and **no crawl batch**; the ungated floor schedule
still enqueues.

---

### OB-6 — Cost preview and the quota unit

**Depends on:** crawler **CS-5** (estimate endpoint). **Must land before
OB-2 reaches production.**

**Files:**
- `library/VoiceOfCustomerSystemClient.php` — add `estimateCrawl($locationId)`
  for `GET /integration/v1/crawl-jobs/estimate`
- `controllers/VocController.php` — a small JSON action the Fetch Jobs
  screen calls when backfill or custom is selected
- `views/Voc/fetchjobs.volt` — render the preview (§4.2); require confirm
  above a threshold
- `crawlStartAction()` — reject **before** `verifyBenefit` consumes quota
  when the estimate exceeds the remaining budget (same ordering principle
  as `:10591-10593`)

**Quota unit (B15, Q6):** decide with the crawler side whether
`VOC_SCRAPE`/`VOC_REVIEW` start counting reviews rather than calls, or
whether the crawler-side budget (CS-5) is the only per-review guard.
**Do not end up with two independent quota systems that disagree.**

**Verify:** a backfill whose estimate exceeds the remaining budget is
refused with no batch created and no benefit consumed.

---

### OB-7 — Cleanup

**Depends on:** OB-2 and OB-3 shipped. **Ships before** crawler CS-6 — stop
sending before the crawler stops accepting.

- Delete `VocCrawlQueue::scanLimit()` and its constants (`:191-199`), and
  stop sending `scan_limit`.
- Stop sending `crawl_mode`; remove `crawl_mode`/`scan_limit` from the
  fallback at `VoiceOfCustomerSystemClient.php:834-849`.
- Remove the `selenium` source check and its comment
  (`VocController.php:10555-10561`).
- Extend the `WATERMARK_MARGIN_DAYS` docblock (`VocCrawlQueue.php:272-283`)
  with the Apify measurement from Part 2 B17 — **keep the constant and its
  existing reason**; both are still right (B9).
- Replace `STOP_ALASAN` (`fetchjobs.volt:1163-1167`) and the Selenium-only
  branch of `diagnosaCrawl()` (`:1180-1186`) — done in OB-9; delete
  leftovers here.
- Rewrite the `VocCrawlQueue::crawlMode()` docblock references
  (`:152-170`) or remove them with the method.
- Update `fetchjobs.volt` copy that still describes Selenium behaviour
  ("menyisir", "kartu", "batas waktu") where it no longer applies.

---

### OB-8 — Edited reviews, approximate dates, crawler coverage on screen

**Depends on:** crawler **CS-7** in production. Every new field is optional,
so OB-8 must also work when they are absent.

**Files:**
- `services/Provider/VocProvider.php`
  - `buildMeta()` (`~:1150-1185`) — store `review_time_precision`,
    `date_approximate`, `is_edited`, `edited_at`
  - `perbaruiReviewTersimpan()` (`:787`) — when `is_edited` and the text or
    rating differ from what OneBox holds: update `MessageContent.Body` and
    the star rating, clear the native sentiment label so
    `labelPendingReviews()` runs again, and if a ticket exists add the note
    from §4.7 instead of rewriting the ticket
- `controllers/VocController.php` — review list payloads (`:3365`, `:3774`,
  `:4828`, `:7896`) include `date_approximate` and `is_edited`; trend and
  benchmark queries apply the Q13 decision
- `views/Voc/reviews.volt`, `workspace.volt`, `workspacebranch.volt`,
  `dashboardprofile.volt` — "± month/year" date display, **Diubah** badge
- `views/Voc/fetchjobs.volt` — `perbaruiStatusCabang()` (`:911-949`) shows
  crawler coverage (§4.5); the Update Terbaru note rewording

**Verify:** a re-served review with new text and ★ updates body, rating and
label without creating a second message; a ticketed one gets a note and
keeps its description; a review without the new keys renders exactly as
today.

**Do not touch:** `RemoteId` / `review_hash` handling, and the
`sudahPernahMasuk()` guard.

---

### OB-9 — Messages, toasts and alerts

**Depends on:** crawler **CS-8** (stable codes). Wording changes that do not
depend on codes (M20–M24, renames) can ship first.

**Files:**
- `views/Voc/fetchjobs.volt`
  - replace `STOP_ALASAN` with a map from the CS-8 codes to M6–M17
  - `STATE_LABEL` (`:1004-1014`) — PARTIAL → M19; RUNNING → M3/M4
  - the counter line (`:1091-1097`) — separate *sudah ada* from *gagal*
    visually; *gagal* only appears when non-zero
  - `diagnosaCrawl()` — drop the Selenium sort-order branch
  - every `showInfoModal` in the table in §4.6 — reword per catalogue
  - add a small toast helper if the screen has none; use it only for M1
  - mode labels and hints (renames in §4.6)
- `views/Voc/schedules.volt` — `:1401` validation wording (M22)
- `controllers/VocController.php` — `jsonFail()` messages from
  `crawlStartAction()` that reach the user use the same wording as the
  modals (e.g. `:10551`, `:10637-10639`)

**Verify:** a checklist run against a dev crawler that produces each code at
least once — every row M1–M25 appears exactly as written, in the listed
surface, and no state shows more than one message. Add the mapping to
`tests/voc/` as a static check that every CS-8 code has a message.

**Review with product before building:** the catalogue is a proposal; the
wording is the part users will judge the feature by.

---

## 7. Open questions, OneBox side

**Q6 — benefit quota unit, and the 5,000 default.** B15 / OB-6 / D11.
Is 5,000 the right per-cabang default ceiling (it matches the smallest
`VOC_REVIEW` package and covers every place measured so far), and should
existing cabang stored at 300 or 100 be raised? Per-call quotas predate per-review
billing. Product decision; blocks OB-2 in production.

**Q8 — backfill confirm threshold.** OB-6. Above how many estimated reviews
should the screen demand explicit confirmation? Product decision.

**Q9 — who may run fetch-all.** Today any user with Fetch Jobs access can
start a crawl. With no 300 cap, should `full_backfill` require a higher
permission? `tests/voc/voc_permission_map_check.php` is where that would be
pinned down.

**Q13 — approximate dates in trends.** §4.7. Show old reviews as a separate
series, exclude them from monthly trends, or include them with a note?
Affects the "bulan lalu" benchmark from notulen 2026-08-21 §A.

**Q14 — should Rentang Khusus still allow a ceiling at all?** D8 says take
everything in the range. The optional cost ceiling in §4.5 is a safety
valve; product may prefer the quota check (M20) as the only guard.

**Q10 — auto-resume import time budget.** OB-4 option 1. How long may one
web request run on the target infrastructure before it is killed? Needed to
size the resume loop.

**Q5 (shared) — Google Business Profile API.** Whether real push is viable
for Hermina's own cabang decides whether OB-5 is a stopgap or permanent.
See Part 2 §7.

*(Q1–Q4, Q7 are crawler questions — Part 2 §7.)*

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

- Changing the OneBox import contract beyond B11's page caps.
- Competitor fetch jobs (`fetchjobscompetitorAction`,
  `competitorCrawlStartAction`). Same mechanisms apply; not among the three
  requested capabilities.
- Merging per-review anonymous Contacts into real reviewer Contacts (OB-0
  only renames).
- Google Business Profile API — named in Part 2 §4.4, not specced.
- Field renaming catalogued in `TECH_DEBT_ONEBOX_APIFY_FIELD_NAMING.md`.
- Automatic mode selection. The user picks cabang and mode.
