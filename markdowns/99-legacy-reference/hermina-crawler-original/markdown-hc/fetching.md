# 03_FETCHING.md

# Review System — Fetching & Sync Specification

## 1. Objective

This document defines how the application should fetch, normalize, deduplicate, store, and log public review data for selected Hermina hospital locations.

The application must support fetching from different review sources through a common interface.

For the MVP, fetching can run in mock mode first.

---

## 2. Fetching Principle

The system must follow these principles:

1. Fetching must be separated from terminal UI.
2. Fetching must be handled by service and integration classes.
3. Raw fetched data must be normalized before storing.
4. Duplicate reviews must not be inserted.
5. Every fetch attempt must be logged.
6. Fetching must support dry run mode.
7. Fetching must continue to next location if one location fails.
8. The app must support mock fetching if real API is unavailable.
9. Production use should prioritize official API or legal provider.
10. Direct scraping should not be the default production approach.

---

## 3. Fetching Architecture

```text
Terminal Fetch Menu
    |
    v
FetchService
    |
    v
Review Source Client
    |
    v
Normalize Reviews
    |
    v
Generate Review Hash
    |
    v
Check Duplicate
    |
    v
Insert New Reviews
    |
    v
Create Fetch Log
    |
    v
Return Fetch Result to Terminal
```

---

## 4. Review Source Modes

The app must support this config:

```env
REVIEW_SOURCE_MODE=mock
```

Allowed values:

```text
mock
google_places
third_party
```

---

### 4.1 Mock Mode

If:

```env
REVIEW_SOURCE_MODE=mock
```

Use:

```text
MockReviewClient
```

Purpose:

* Development.
* Testing.
* Demo without API key.
* Building database and analysis flow first.

Mock mode should return realistic Hermina-style review data.

---

### 4.2 Google Places Mode

If:

```env
REVIEW_SOURCE_MODE=google_places
```

Use:

```text
GooglePlacesClient
```

Purpose:

* Fetch official review data using configured Google Maps/Places API key.
* Use `external_place_id` from `locations` table.

Important:

* Do not hardcode API key.
* API key must come from `.env`.
* Respect API limits and policy.
* Returned reviews may be limited depending on API capabilities.

---

### 4.3 Third Party Mode

If:

```env
REVIEW_SOURCE_MODE=third_party
```

Use future provider client.

Purpose:

* Support review provider API if needed.
* Useful if client needs more historical review data.

For MVP, this mode can raise:

```text
Third-party provider is not implemented yet.
```

---

## 5. Review Source Client Interface

Create a common client interface.

All review source clients should implement:

```python
fetch_reviews(location, limit: int = 50) -> list[dict]
```

Input:

* `location`: location object from database.
* `limit`: max review count.

Output:

* list of raw review dictionaries.

Example:

```python
[
    {
        "source": "mock",
        "external_place_id": "mock-hermina-depok",
        "external_review_id": "mock-review-001",
        "reviewer_name": "Andi",
        "rating": 5,
        "review_text": "Pelayanan dokter sangat baik dan ramah.",
        "review_time": "2026-06-19T10:00:00+07:00",
        "language": "id",
        "raw_payload": {}
    }
]
```

---

## 6. FetchService Responsibilities

`FetchService` must handle:

1. Get location data.
2. Select correct review source client.
3. Start fetch log.
4. Fetch raw reviews.
5. Normalize raw reviews.
6. Generate review hash.
7. Check duplicate review.
8. Insert new review.
9. Count fetched, inserted, duplicate, failed.
10. Update fetch log.
11. Return result object to terminal UI.

The terminal menu should only call `FetchService`.

---

## 7. Fetch One Location Flow

Flow:

```text
Start
  |
  |-- User selects Fetch Reviews for One Location
  |
  |-- Show active locations
  |
  |-- User selects location ID
  |
  |-- FetchService.fetch_location(location_id)
  |
  |-- Create fetch log with status started
  |
  |-- Call selected Review Source Client
  |
  |-- Normalize result
  |
  |-- For each review:
        |
        |-- Generate review_hash
        |-- Check if review_hash exists
        |-- If duplicate: skip
        |-- If new: insert
        |-- If error: count failed
  |
  |-- Update fetch log
  |
  |-- Return result
End
```

---

## 8. Fetch All Active Locations Flow

Flow:

```text
Start
  |
  |-- User selects Fetch Reviews for All Active Locations
  |
  |-- FetchService.fetch_all_active_locations()
  |
  |-- Get active locations
  |
  |-- For each location:
        |
        |-- Run fetch_location(location_id)
        |-- If success: continue
        |-- If failed: log error and continue
  |
  |-- Return final sync summary
End
```

Rules:

* One failed location must not stop all sync.
* Each location must have its own fetch log.
* Final summary must include success and failed count.

---

## 9. Dry Run Fetch Flow

Dry run is used to test fetching without database insert.

Flow:

```text
Start
  |
  |-- User selects Dry Run Fetch for One Location
  |
  |-- Show active locations
  |
  |-- User selects location ID
  |
  |-- FetchService.dry_run_location(location_id)
  |
  |-- Call selected Review Source Client
  |
  |-- Normalize result
  |
  |-- Show sample review data
  |
  |-- Do not insert reviews
  |
  |-- Do not create review_analysis
  |
  |-- May create fetch log with status dry_run
End
```

Rules:

* No review insert.
* No analysis insert.
* Show total fetched.
* Show first 3–5 sample reviews.
* Useful before real sync.

---

## 10. Normalized Review Format

All fetched reviews must be converted into this normalized format before insert:

```json
{
  "location_id": 1,
  "source": "google_places",
  "external_place_id": "xxxxx",
  "external_review_id": "optional",
  "reviewer_name": "Reviewer Name",
  "rating": 5,
  "review_text": "Review text here.",
  "review_time": "2026-06-19T10:00:00+07:00",
  "language": "id",
  "raw_payload": {}
}
```

---

## 11. Required Normalization Rules

### 11.1 Source

If source is missing, use configured source mode.

Example:

```text
mock
google_places
third_party
```

---

### 11.2 External Place ID

Use:

```text
location.external_place_id
```

If API response contains source-specific place ID, keep both if needed inside `raw_payload`.

---

### 11.3 Reviewer Name

If reviewer name is missing:

```text
Anonymous
```

---

### 11.4 Rating

Rating must be integer from 1 to 5.

If rating is missing or invalid:

* Allow null.
* Do not crash.
* Log warning.

---

### 11.5 Review Text

If review text is empty:

* Store empty string if source provides rating-only review.
* Do not analyze empty text later unless analysis service explicitly supports it.

---

### 11.6 Review Time

Review time should be stored as timestamp.

If source gives relative time such as:

```text
2 weeks ago
```

Then:

* Store raw value in `raw_payload`.
* If cannot parse accurately, allow null for `review_time`.

---

### 11.7 Language

If language is missing:

```text
unknown
```

---

### 11.8 Raw Payload

Always store full original response per review into `raw_payload`.

Purpose:

* Audit.
* Debugging.
* Reprocessing.
* Source traceability.

---

## 12. Deduplication Logic

Every review must have a `review_hash`.

Hash input:

```text
source
external_place_id
external_review_id
reviewer_name
rating
review_text
review_time
```

Pseudo-code:

```python
from hashlib import sha256

def generate_review_hash(review: dict) -> str:
    hash_input = "|".join([
        str(review.get("source") or ""),
        str(review.get("external_place_id") or ""),
        str(review.get("external_review_id") or ""),
        str(review.get("reviewer_name") or ""),
        str(review.get("rating") or ""),
        str(review.get("review_text") or ""),
        str(review.get("review_time") or "")
    ])

    return sha256(hash_input.encode("utf-8")).hexdigest()
```

Rules:

* If `review_hash` already exists, skip insert.
* Count skipped review as duplicate.
* Do not overwrite existing review by default.
* Store new review only if hash is new.
* Unique constraint should exist on `reviews.review_hash`.

---

## 13. Insert Review Logic

For each normalized review:

```text
1. Generate review_hash.
2. Check if review_hash exists.
3. If exists, increment duplicate count.
4. If not exists, insert review.
5. If insert fails, increment failed count.
6. Continue to next review.
```

Review insert should not fail the entire fetch unless database connection is broken.

---

## 14. Fetch Result Object

`FetchService` should return a structured result.

Example:

```python
{
    "location_id": 1,
    "location_name": "Hermina Depok",
    "source": "google_places",
    "status": "success",
    "total_fetched": 20,
    "total_inserted": 5,
    "total_duplicate": 15,
    "total_failed": 0,
    "error_message": None
}
```

Terminal UI will display this object.

---

## 15. Fetch Log Rules

Every real fetch must create a fetch log.

For fetch start:

```text
status = started
started_at = current timestamp
```

For fetch success:

```text
status = success
finished_at = current timestamp
```

For partial success:

```text
status = partial_success
finished_at = current timestamp
```

For failed fetch:

```text
status = failed
error_message = error detail
finished_at = current timestamp
```

For dry run:

```text
status = dry_run
finished_at = current timestamp
```

---

## 16. Fetch Log Data

Store:

```json
{
  "location_id": 1,
  "source": "google_places",
  "status": "success",
  "total_fetched": 20,
  "total_inserted": 5,
  "total_duplicate": 15,
  "total_failed": 0,
  "error_message": null,
  "started_at": "2026-06-19T10:00:00+07:00",
  "finished_at": "2026-06-19T10:00:10+07:00"
}
```

---

## 17. Error Handling

### 17.1 Invalid Location

If selected location does not exist:

```text
Location not found.
```

Return to fetch menu.

---

### 17.2 No Active Location

If fetch all active locations but none exist:

```text
No active Hermina locations found.
Please add or activate location first.
```

---

### 17.3 Missing API Key

If source mode requires API key but key is missing:

```text
Review source API key is missing.
Please check your .env configuration.
```

Fetch should stop for that location.

---

### 17.4 API Timeout

If request timeout occurs:

* Retry using retry strategy.
* If still fails, mark fetch as failed.
* Save error message into fetch log.

---

### 17.5 API Rate Limit

If rate limit occurs:

* Retry if safe.
* If still rate-limited, mark fetch as failed.
* Show user-friendly message.

---

### 17.6 Parsing Error

If one review cannot be parsed:

* Count as failed.
* Continue parsing next review.
* Log error.

---

### 17.7 Database Insert Error

If one review fails insert:

* Rollback that insert.
* Count as failed.
* Continue with next review if possible.

If database connection is broken:

* Stop current fetch.
* Mark fetch as failed.

---

## 18. Retry Strategy

Default retry:

```text
max_retry = 3
```

Delay:

```text
retry 1 = 5 seconds
retry 2 = 15 seconds
retry 3 = 30 seconds
```

Retry applies to:

* Network timeout
* Temporary API failure
* HTTP 5xx response

Do not retry:

* Invalid API key
* Invalid place ID
* Permission denied
* Bad request caused by invalid payload

---

## 19. Fetch Limit

Use config:

```env
FETCH_LIMIT_PER_LOCATION=50
```

Rules:

* Default limit is 50.
* Terminal can later ask user for custom limit.
* MVP can use default config only.
* Client should not fetch more than API allows.

---

## 20. Mock Review Data

MockReviewClient should generate at least 10 sample reviews.

Sample themes:

1. Doctor service positive.
2. Nurse service positive.
3. Waiting time negative.
4. Administration negative.
5. Parking negative.
6. Pharmacy waiting negative.
7. Cleanliness positive.
8. Facility mixed.
9. Booking system negative.
10. General praise.

Example mock review:

```python
{
    "source": "mock",
    "external_place_id": location.external_place_id,
    "external_review_id": "mock-001",
    "reviewer_name": "Andi Saputra",
    "rating": 5,
    "review_text": "Dokternya ramah dan penjelasannya mudah dimengerti.",
    "review_time": "2026-06-19T09:00:00+07:00",
    "language": "id",
    "raw_payload": {
        "mock": True
    }
}
```

---

## 21. Google Places Client Behavior

`GooglePlacesClient` should:

1. Read API key from config.
2. Use location `external_place_id`.
3. Fetch place details and reviews if available.
4. Normalize reviews into standard format.
5. Return list of raw review dictionaries.

If real API is not implemented yet, create class placeholder with clear error:

```text
GooglePlacesClient is not fully implemented yet.
Please use REVIEW_SOURCE_MODE=mock.
```

Do not put scraping logic directly inside this client unless explicitly requested later.

---

## 22. Direct Scraping Rule

For this MVP:

* Do not implement aggressive scraping.
* Do not implement proxy rotation.
* Do not implement browser automation against Google Maps.
* Do not bypass rate limits.
* Do not bypass authentication or anti-bot systems.

If custom scraping is required later, it must be treated as a separate module and reviewed separately.

---

## 23. Fetch Frequency Recommendation

MVP:

```text
Manual fetch from terminal
```

Internal pilot:

```text
1x per day
```

Future production:

```text
2–4x per day depending on API policy and client requirement
```

No scheduler is required in this MVP.

---

## 24. Terminal Output for Fetch

### 24.1 Success Output

```text
Fetching reviews for Hermina Depok...

Source          : mock
Location        : Hermina Depok
Total fetched   : 10
Inserted        : 10
Duplicate       : 0
Failed          : 0
Status          : Success

Press Enter to continue...
```

---

### 24.2 Duplicate Output

```text
Fetching reviews for Hermina Depok...

Source          : mock
Location        : Hermina Depok
Total fetched   : 10
Inserted        : 0
Duplicate       : 10
Failed          : 0
Status          : Success

No new reviews found.
```

---

### 24.3 Failed Output

```text
Fetch failed.

Location : Hermina Depok
Source   : google_places
Error    : Review source API key is missing.

Press Enter to continue...
```

---

## 25. Data Quality Checks

After fetching, system should ensure:

* Review source exists.
* Location ID exists.
* Review hash generated.
* Rating is valid or null.
* Review text is not None.
* Raw payload is stored.
* Duplicate is skipped.
* Fetch log is saved.

---

## 26. Separation of Concerns

Do not put fetch logic in terminal menu file.

Correct:

```text
fetch_menu.py
    calls FetchService
FetchService
    calls ReviewSourceClient
    calls ReviewService
    calls FetchLogService
```

Incorrect:

```text
fetch_menu.py
    directly calls API
    directly inserts database
    directly generates hash
```

---

## 27. Future Improvement

Fetching module should be easy to extend later with:

* Scheduler.
* More review sources.
* Historical review import.
* Manual CSV import.
* Web dashboard sync button.
* Alert for new negative reviews.
* Alert for critical issues.

---

## 28. Acceptance Criteria

Codex should generate fetching logic that satisfies:

1. User can fetch reviews for one location from terminal menu.
2. User can fetch reviews for all active locations from terminal menu.
3. User can dry run fetch without inserting reviews.
4. Fetching works in mock mode.
5. Fetching does not require real API keys in mock mode.
6. Fetching uses service layer, not terminal menu logic.
7. Reviews are normalized before insert.
8. Reviews generate unique hash.
9. Duplicate reviews are skipped.
10. Fetch logs are created.
11. Failed fetch is logged.
12. One failed location does not stop sync all.
13. API errors are handled gracefully.
14. Raw payload is stored.
15. Fetch result is displayed clearly in terminal.
16. Fetching logic can later support Google Places or third-party providers.

---

## 29. Important Notes for Codex

* Build mock fetching first.
* Keep real Google Places integration behind client class.
* Do not implement direct Google Maps scraping in MVP.
* Do not use command-line arguments.
* Do not build scheduler yet.
* Do not build web dashboard yet.
* Prioritize stable local terminal app.
* Keep code readable and modular.
