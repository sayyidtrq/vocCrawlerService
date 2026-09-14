# Tech debt: Apify ↔ crawler ↔ OneBox field naming

**Status:** informational only. Nothing here requires action in this repo
right now, and nothing here is actionable in OneBox until there's access to
that codebase. This is a memo to revisit later, not a task for this
migration.

## Why this exists

Apify's raw review JSON uses its own naming convention (`content`,
`owner_response`, `likes_count`, `is_local_guide`, ...), which does not
match this codebase's internal `reviews` table columns (`review_text`,
`owner_response_text`, `like_count`, `reviewer_local_guide_level`, ...).
`app/integrations/apify_review_parser.py` (see
`MIGRATION_APIFY_REVIEW_SOURCE.md`) bridges this gap entirely inside the
crawler service — **OneBox is unaffected and needs no changes**: it has
always received the crawler's own internal column names via
`GET /integration/v1/reviews`, regardless of which scraper (Selenium or
Apify) filled the table. This document exists only to record the naming
decisions made while bridging, in case they're worth revisiting once
there's access to make the equivalent change on the OneBox side too.

## Renamings absorbed silently inside the crawler (no OneBox-visible effect)

| Apify raw field | Crawler's internal name | Note |
|---|---|---|
| `content` | `review_text` | |
| `owner_response` | `owner_response_text` | |
| `reviewed_at_date` | `review_time` | |
| `likes_count` | `like_count` | |
| `reviewer_reviews_count` | `reviewer_total_reviews` | |
| `reviewer_url` | `reviewer_profile_url` | |
| `place_id` | `external_place_id` | |
| `review_id` | `external_review_id` | |

None of these need OneBox to change anything — they were already the
crawler's internal names before Apify existed; Selenium just populated them
differently.

## Real technical debt worth OneBox revisiting later (deferred, not actionable now)

1. **`reviewer_local_guide_level` is a lossy boolean→string collapse
   inherited from the Selenium era.** Selenium could only detect "Local
   Guide" as a text label scraped off the page, so the column has always
   stored either the string `"Local Guide"` or `NULL`. Apify gives a real
   boolean (`is_local_guide: true/false`) for every review. The crawler
   keeps collapsing it to the old string shape to avoid touching the
   contract. If OneBox ever wants a genuine boolean local-guide flag, the
   crawler could add a new additive field (the integration contract is
   additive-only, per `integration_reviews.py`'s own docstring) — but
   that's a product/schema decision for whoever owns OneBox's review model,
   not something to smuggle into this migration.

2. **`review_language` and `language` on the `reviews` table have been
   duplicate/vestigial since Selenium always wrote `"unknown"` to both
   (it never actually detected language).** Apify gives one real signal
   (`content_language`, sometimes `null`) that the crawler writes to both
   columns, so the duplication persists rather than getting resolved by
   this migration. Worth collapsing to one column someday, but that's a
   deliberate schema decision, not something to fold into a scraper swap.

3. **Apify's `rating_stats` (count of 5-star/4-star/3-star/2-star/1-star
   reviews for the place) has no home anywhere downstream today.** It's
   real, free, per-place aggregate data Google already computed; OneBox's
   review/ticket views could eventually show a rating-distribution widget
   from it. Right now it's discarded into `raw_payload` and read by
   nothing. Flagging as an available-but-unused opportunity, not a defect.

4. **Naming collision risk if `raw_payload` is ever flattened for export.**
   Apify's raw item has its own `location` key meaning `{lat, lng}`
   coordinates. This codebase's `Location` model — and OneBox's existing
   review JSON contract — both use `"location"` to mean the hospital
   *branch name* (e.g. `"location": "Hermina Bogor"`). These never collide
   today because Apify's raw `location` object only ever lives nested
   inside `raw_payload` and is never surfaced as a top-level field. If
   anyone later "helpfully" flattens `raw_payload` into a top-level export
   or debug view, this collision will produce a silently wrong value for
   whichever `location` key gets clobbered. Worth a comment at the point of
   any future flattening, not a change now.
