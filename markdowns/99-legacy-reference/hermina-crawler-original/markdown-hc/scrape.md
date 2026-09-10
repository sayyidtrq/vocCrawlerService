# 04_SELENIUM_SCRAPING.md

# Review System — Selenium Review Scraping Specification

## 1. Objective

This document defines a Selenium-based review scraping module for **Review System**.

The goal is to collect public Google Maps review data from selected Hermina hospital review pages and store the results into a local PostgreSQL database.

This module is intended for:

* Local proof of concept.
* Internal research.
* Data exploration.
* Review analysis testing.

This module should not be treated as the default production method.

For production or official client use, prefer:

* Google Business Profile API if the client owns/manages the Google Business Profile locations.
* Google Places API if limited review data is acceptable.
* Licensed third-party review provider if historical review volume is required.

---

## 2. Important Policy Note

Google Places API may return only a limited number of reviews. Selenium scraping can technically collect more visible reviews from the Google Maps UI, but this approach may violate Google platform terms depending on usage.

Therefore:

* Do not bypass authentication.
* Do not bypass anti-bot systems.
* Do not use proxy rotation.
* Do not scrape aggressively.
* Do not run high-frequency scraping.
* Do not use this as production default.
* Use only for controlled internal testing unless legal/product approval is given.

---

## 3. Application Mode

Add a new review source mode:

```env
REVIEW_SOURCE_MODE=selenium
```

Allowed values:

```text
mock
google_places
google_business_profile
third_party
selenium
```

If:

```env
REVIEW_SOURCE_MODE=selenium
```

Then the system must use:

```text
SeleniumGoogleMapsReviewClient
```

---

## 4. User Flow in Terminal

The user still runs the app using:

```bash
python main.py
```

The terminal app should show the existing interactive menu.

In the location management menu, user should be able to store:

* Branch name
* City
* Google Maps review URL
* Target review count

In the fetch menu, user should be able to choose:

```text
Fetch / Sync Reviews

1. Fetch Reviews for One Location
2. Fetch Reviews for All Active Locations
3. Dry Run Fetch for One Location
4. Selenium Fetch from Review URL
5. View Last Fetch Result
0. Back to Main Menu
```

When selecting Selenium Fetch:

```text
Select Location:
1. RS Hermina Bekasi
2. RS Hermina Depok
3. RS Hermina Bogor

Target reviews to fetch:
1. 100 reviews
2. 150 reviews
3. 200 reviews
4. Custom number

Select target:
```

---

## 5. Required Input Data

For each location, the system should support these fields:

```text
hospital_name
branch_name
city
address
latitude
longitude
source
external_place_id
google_maps_url
google_reviews_url
target_review_count
is_active
```

For Selenium scraping, the most important field is:

```text
google_reviews_url
```

Example:

```text
https://www.google.com/maps/place/.../reviews
```

If only `google_maps_url` exists, the scraper may open the business page and click/open the review section.

---

## 6. Recommended Database Columns

Update `locations` table with:

```sql
ALTER TABLE locations ADD COLUMN google_maps_url TEXT;
ALTER TABLE locations ADD COLUMN google_reviews_url TEXT;
ALTER TABLE locations ADD COLUMN target_review_count INTEGER DEFAULT 100;
```

---

## 7. Review Data Columns

The `reviews` table should store these fields:

```sql
id
location_id
source
external_place_id
external_review_id
reviewer_name
reviewer_profile_url
reviewer_photo_url
reviewer_local_guide_level
reviewer_total_reviews
rating
review_text
review_time
review_relative_time
review_language
like_count
owner_response_text
owner_response_time
scraped_at
raw_payload
review_hash
created_at
updated_at
```

---

## 8. Recommended SQL Schema Extension

```sql
ALTER TABLE reviews ADD COLUMN reviewer_profile_url TEXT;
ALTER TABLE reviews ADD COLUMN reviewer_photo_url TEXT;
ALTER TABLE reviews ADD COLUMN reviewer_local_guide_level VARCHAR(100);
ALTER TABLE reviews ADD COLUMN reviewer_total_reviews INTEGER;
ALTER TABLE reviews ADD COLUMN review_relative_time VARCHAR(100);
ALTER TABLE reviews ADD COLUMN review_language VARCHAR(20);
ALTER TABLE reviews ADD COLUMN like_count INTEGER DEFAULT 0;
ALTER TABLE reviews ADD COLUMN owner_response_text TEXT;
ALTER TABLE reviews ADD COLUMN owner_response_time TIMESTAMP;
ALTER TABLE reviews ADD COLUMN scraped_at TIMESTAMP;
```

---

## 9. Core Review Fields to Scrape

Minimum fields:

```text
reviewer_name
rating
review_text
review_relative_time
review_time if available
source
google_reviews_url
scraped_at
raw_payload
review_hash
```

Recommended fields:

```text
reviewer_profile_url
reviewer_photo_url
reviewer_local_guide_level
reviewer_total_reviews
like_count
owner_response_text
owner_response_time
review_language
```

Optional fields:

```text
review_id
review_sort_order
review_permalink
review_images
```

---

## 10. Normalized Review Format

Every scraped review must be normalized into:

```json
{
  "location_id": 1,
  "source": "selenium_google_maps",
  "external_place_id": null,
  "external_review_id": null,
  "reviewer_name": "Nama Reviewer",
  "reviewer_profile_url": "https://www.google.com/maps/contrib/...",
  "reviewer_photo_url": "https://...",
  "reviewer_local_guide_level": "Local Guide",
  "reviewer_total_reviews": 37,
  "rating": 5,
  "review_text": "Pelayanan baik dan dokter ramah.",
  "review_relative_time": "2 minggu lalu",
  "review_time": null,
  "review_language": "id",
  "like_count": 0,
  "owner_response_text": "Terima kasih atas ulasannya.",
  "owner_response_time": null,
  "scraped_at": "2026-06-19T15:00:00+07:00",
  "raw_payload": {},
  "review_hash": "generated_hash"
}
```

---

## 11. Selenium Scraping Flow

```text
Start
  |
  |-- User selects Selenium Fetch from Review URL
  |
  |-- Show active locations
  |
  |-- User selects location
  |
  |-- User selects target count: 100 / 150 / 200 / custom
  |
  |-- Open Google Maps review URL
  |
  |-- Wait for review panel to load
  |
  |-- Sort reviews if possible
  |
  |-- Scroll review panel until target count is reached
  |
  |-- Extract review cards
  |
  |-- Normalize review data
  |
  |-- Generate review hash
  |
  |-- Check duplicate
  |
  |-- Insert only new reviews
  |
  |-- Save fetch log
  |
  |-- Return result to terminal
End
```

---

## 12. Scroll Strategy

Google Maps review panel loads reviews dynamically. The scraper should:

1. Open the review URL.
2. Wait until review container appears.
3. Locate scrollable review container.
4. Scroll slowly.
5. Wait between scrolls.
6. Count loaded review cards.
7. Stop when target count is reached or no new cards are loaded.

Default behavior:

```text
target_review_count = 100
scroll_delay_seconds = 2
max_no_new_scroll_attempts = 5
max_scroll_attempts = 100
```

---

## 13. Target Review Count

Supported options:

```text
100
150
200
custom
```

Rules:

* Default is 100.
* Custom must be integer.
* Custom should not exceed configured max.
* Recommended max for local POC is 300.

Add config:

```env
SELENIUM_DEFAULT_TARGET_REVIEWS=100
SELENIUM_MAX_TARGET_REVIEWS=300
SELENIUM_SCROLL_DELAY_SECONDS=2
SELENIUM_MAX_SCROLL_ATTEMPTS=100
SELENIUM_HEADLESS=false
```

---

## 14. Browser Mode

Support two modes:

```env
SELENIUM_HEADLESS=false
```

Allowed values:

```text
true
false
```

Recommendation:

* Use `false` during development.
* Use `true` only after selector is stable.

In non-headless mode, user can see the browser opening and scrolling.

---

## 15. Selector Strategy

Google Maps DOM can change. Avoid relying on only one fixed selector.

Create selector constants in:

```text
app/integrations/google_maps_selectors.py
```

Selectors should be grouped by purpose:

```python
REVIEW_CARD_SELECTORS = [
    "...",
    "..."
]

REVIEWER_NAME_SELECTORS = [
    "...",
    "..."
]

RATING_SELECTORS = [
    "...",
    "..."
]

REVIEW_TEXT_SELECTORS = [
    "...",
    "..."
]

REVIEW_TIME_SELECTORS = [
    "...",
    "..."
]

SCROLL_CONTAINER_SELECTORS = [
    "...",
    "..."
]
```

The scraper should try selectors in order and fail gracefully if a selector does not work.

---

## 16. Data Extraction Rules

### 16.1 Reviewer Name

Extract visible reviewer name.

If missing:

```text
Anonymous
```

---

### 16.2 Rating

Extract star rating.

Common format may appear as:

```text
5 bintang
5 stars
Rating 5.0
```

Normalize to integer:

```text
1
2
3
4
5
```

If rating cannot be parsed, set null.

---

### 16.3 Review Text

Extract full review text.

If review is collapsed with button like:

```text
Lainnya
More
```

The scraper should click it before extracting text.

If text is empty, store empty string.

---

### 16.4 Review Relative Time

Extract visible relative time, for example:

```text
1 hari lalu
2 minggu lalu
3 bulan lalu
setahun lalu
```

Store this in:

```text
review_relative_time
```

Do not force exact timestamp if not available.

---

### 16.5 Review Time

If exact review timestamp is not available, set:

```text
review_time = null
```

Do not guess exact date from relative time unless a reliable parser is implemented.

---

### 16.6 Reviewer Profile URL

If reviewer profile link is available, store it.

Otherwise null.

---

### 16.7 Like Count

If visible, parse like count as integer.

Otherwise:

```text
0
```

---

### 16.8 Owner Response

If business owner response is visible, store:

```text
owner_response_text
owner_response_time
```

If not visible, set null.

---

## 17. Deduplication Logic

For Selenium scraping, review IDs may not always be available.

Generate hash using:

```text
source
location_id
reviewer_name
rating
review_text
review_relative_time
reviewer_profile_url
```

Pseudo-code:

```python
def generate_selenium_review_hash(review):
    hash_input = "|".join([
        str(review.get("source") or ""),
        str(review.get("location_id") or ""),
        str(review.get("reviewer_name") or ""),
        str(review.get("rating") or ""),
        str(review.get("review_text") or ""),
        str(review.get("review_relative_time") or ""),
        str(review.get("reviewer_profile_url") or "")
    ])

    return sha256(hash_input.encode("utf-8")).hexdigest()
```

Rules:

* If hash exists, skip insert.
* Count as duplicate.
* Do not overwrite existing raw review.
* If owner response changes, do not create duplicate review unless review content changes.
* Later improvement can store owner response history separately.

---

## 18. Fetch Log for Selenium

Fetch log should include:

```text
source = selenium_google_maps
status
total_fetched
total_inserted
total_duplicate
total_failed
error_message
started_at
finished_at
```

Additional optional fields if table supports JSON metadata:

```json
{
  "target_review_count": 100,
  "loaded_review_cards": 120,
  "scraped_review_cards": 100,
  "scroll_attempts": 35,
  "headless": false,
  "url": "https://www.google.com/maps/..."
}
```

If `fetch_logs` table does not have metadata column, add:

```sql
ALTER TABLE fetch_logs ADD COLUMN metadata JSONB;
```

---

## 19. Error Handling

### 19.1 Invalid Review URL

Show:

```text
Invalid Google review URL.
Please update location google_reviews_url.
```

---

### 19.2 Browser Failed to Start

Show:

```text
Selenium browser failed to start.
Please check Chrome and ChromeDriver installation.
```

---

### 19.3 Review Container Not Found

Show:

```text
Review container was not found.
Google Maps layout may have changed or the URL is invalid.
```

---

### 19.4 No Reviews Loaded

Show:

```text
No reviews were loaded.
Please check the review URL or try non-headless mode.
```

---

### 19.5 Selector Failed

If one field selector fails:

* Do not stop entire scraping.
* Store null or empty value.
* Continue extracting other fields.

If review card selector fails entirely:

* Stop scraping.
* Mark fetch log as failed.

---

### 19.6 Insert Error

If one review insert fails:

* Rollback that insert.
* Count as failed.
* Continue next review.

---

## 20. Rate and Behavior Limits

To avoid aggressive scraping:

```text
scroll_delay_seconds >= 2
target_review_count <= 300 for MVP
max_scroll_attempts <= 100
```

Do not implement:

* Proxy rotation.
* CAPTCHA bypass.
* Account automation.
* Login automation.
* Anti-bot bypass.
* Parallel scraping.

---

## 21. Terminal Output

### 21.1 Start Output

```text
Starting Selenium review fetch...

Location      : RS Hermina Bekasi
Target review : 100
Headless      : false
Source        : selenium_google_maps
```

---

### 21.2 Success Output

```text
Selenium fetch completed.

Location          : RS Hermina Bekasi
Target requested  : 100
Review cards read : 100
Inserted          : 82
Duplicate         : 18
Failed            : 0
Scroll attempts   : 32
Status            : Success

Press Enter to continue...
```

---

### 21.3 Partial Output

```text
Selenium fetch completed with partial result.

Location          : RS Hermina Bekasi
Target requested  : 200
Review cards read : 135
Inserted          : 40
Duplicate         : 95
Failed            : 0
Reason            : No new review cards loaded after several scroll attempts.

Press Enter to continue...
```

---

### 21.4 Failed Output

```text
Selenium fetch failed.

Location : RS Hermina Bekasi
Error    : Review container was not found.

Press Enter to continue...
```

---

## 22. Recommended Project Structure Addition

Add these files:

```text
app/integrations/selenium_google_maps_client.py
app/integrations/google_maps_selectors.py
app/services/selenium_fetch_service.py
```

Optional:

```text
app/utils/selenium_wait.py
app/utils/rating_parser.py
app/utils/text_cleaner.py
```

---

## 23. Required Dependencies

Add to `requirements.txt`:

```txt
selenium
webdriver-manager
beautifulsoup4
```

Optional:

```txt
lxml
```

---

## 24. Environment Variables

Add to `.env.example`:

```env
SELENIUM_HEADLESS=false
SELENIUM_DEFAULT_TARGET_REVIEWS=100
SELENIUM_MAX_TARGET_REVIEWS=300
SELENIUM_SCROLL_DELAY_SECONDS=2
SELENIUM_MAX_SCROLL_ATTEMPTS=100
SELENIUM_WAIT_TIMEOUT_SECONDS=20
```

---

## 25. Better Mechanism Recommendation

The recommended mechanism for MVP is:

```text
1. Add location and review URL manually.
2. Run Selenium fetch from terminal.
3. Scrape selected number of reviews.
4. Normalize data.
5. Store into local PostgreSQL.
6. Run Gemini analysis separately.
7. View summary and export.
```

Do not combine scraping and Gemini analysis in one step.

Correct sequence:

```text
Fetch first
Analyze later
Summarize after analysis
```

Reason:

* Easier debugging.
* Prevents data loss if Gemini fails.
* Allows re-analysis with new prompt.
* Keeps raw data independent from AI output.

---

## 26. Suggested Development Order

Codex should implement Selenium scraping in this order:

### Phase 1 — DB Extension

* Add google_maps_url to locations.
* Add google_reviews_url to locations.
* Add target_review_count to locations.
* Add selenium-specific review fields.
* Add fetch log metadata if possible.

### Phase 2 — Config

* Add Selenium environment variables.
* Add REVIEW_SOURCE_MODE=selenium.

### Phase 3 — Selenium Client Skeleton

* Open browser.
* Open URL.
* Wait for page.
* Close browser safely.

### Phase 4 — Review Panel Detection

* Find review container.
* Scroll slowly.
* Count review cards.

### Phase 5 — Data Extraction

* Extract reviewer name.
* Extract rating.
* Extract review text.
* Extract relative time.
* Extract profile URL if available.

### Phase 6 — Storage

* Normalize review.
* Generate hash.
* Insert new reviews.
* Skip duplicates.

### Phase 7 — Terminal Menu Integration

* Add Selenium fetch menu.
* Allow user to select 100, 150, 200, or custom.
* Show result summary.

---

## 27. Acceptance Criteria

Codex should generate Selenium scraping logic that satisfies:

1. App can run with `python main.py`.
2. User can select Selenium fetch from terminal menu.
3. User can select a Hermina location.
4. User can choose target review count: 100, 150, 200, or custom.
5. Selenium opens Google Maps review URL.
6. Selenium scrolls review panel.
7. Selenium extracts review cards.
8. Extracted data is normalized.
9. Review hash is generated.
10. Duplicate reviews are skipped.
11. New reviews are inserted into PostgreSQL.
12. Fetch log is created.
13. Browser closes safely after run.
14. Partial scraping result is still saved.
15. App does not crash if one review card fails.
16. App does not combine scraping with Gemini analysis.
17. Gemini analysis can be run separately after scraping.
18. Scraper does not implement proxy rotation or CAPTCHA bypass.

---

## 28. Important Notes for Codex

* Implement Selenium scraping as a separate client.
* Do not remove existing mock mode.
* Do not remove Google Places mode.
* Do not perform analysis during scraping.
* Do not hardcode Google Maps URLs.
* Store review URL per location.
* Keep source value as `selenium_google_maps`.
* Use slow scroll and explicit wait.
* Always close browser in `finally`.
* Store raw payload for each review.
* Make selectors easy to update.

