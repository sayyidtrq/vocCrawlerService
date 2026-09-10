# Review System

Local, interactive terminal application for managing Hermina locations,
fetching public review data, preventing duplicate records, analyzing reviews,
viewing summaries, and exporting results.

The MVP intentionally has no web dashboard, scheduler, background worker, or
command-argument CLI. Start it with:

```bash
python main.py
```

Panduan lengkap penggunaan setiap menu tersedia di
[`PANDUAN_PENGGUNAAN.md`](PANDUAN_PENGGUNAAN.md).

## Integration modes

Mock/testing:

```env
REVIEW_SOURCE_MODE=mock
GEMINI_MODE=mock
```

Mock mode is deterministic: fetching the same location twice inserts ten
reviews on the first fetch and identifies them as duplicates on later fetches.

Real integrations:

```env
REVIEW_SOURCE_MODE=google_places
GOOGLE_MAPS_API_KEY=your_restricted_key
GOOGLE_PLACES_LANGUAGE_CODE=id
GOOGLE_PLACES_REGION_CODE=ID

GEMINI_MODE=real
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.5-flash
```

Real Google Places mode uses Place Details (New). Each location must contain a
real Google Place ID such as `ChIJ...`. The official endpoint returns at most
five reviews per place, sorted by relevance; it does not provide complete
historical review pagination.

## Selenium review scraping

For controlled local POC use:

```env
REVIEW_SOURCE_MODE=selenium
SELENIUM_HEADLESS=false
SELENIUM_DEFAULT_TARGET_REVIEWS=100
SELENIUM_MAX_TARGET_REVIEWS=300
SELENIUM_SCROLL_DELAY_SECONDS=2
SELENIUM_MAX_SCROLL_ATTEMPTS=100
SELENIUM_WAIT_TIMEOUT_SECONDS=20
SELENIUM_USER_DATA_DIR=.selenium-profile
```

Google may show a limited Maps view in a fresh browser profile. The application
does not automate login or bypass this restriction. Set up the dedicated
profile once:

```bash
python -m scripts.setup_selenium_profile
```

Sign in manually in the opened Chrome window, complete any Google Maps setup
shown, return to the place page, and open its Reviews panel. The session is
stored under `.selenium-profile/`, which is ignored by Git.

Each location can store a Google Maps URL, a direct reviews URL, and a target
review count. In the terminal use:

```text
Fetch / Sync Reviews → Selenium Fetch from Review URL
```

The scraper scrolls slowly, does not use proxies or CAPTCHA bypass, and closes
its own browser safely after every run.

## Local setup

Python 3.11 or newer and PostgreSQL are required.

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate it
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create the PostgreSQL database
createdb hermina_reviews

# 5. Create local configuration
# Windows PowerShell
Copy-Item .env.example .env

# macOS/Linux
cp .env.example .env

# 6. Edit DATABASE_URL and other values in .env

# 7. Create/update the schema
alembic upgrade head

# 8. Start the interactive terminal
python main.py
```

If the database is unavailable or the migration has not run, startup shows a
clear warning and still opens the menu. Database-backed actions will continue
to report the underlying error until PostgreSQL is ready.

If a database password contains spaces or URL-special characters, URL-encode
it in `DATABASE_URL`.

## Database migrations

Models live in `app/db/models.py`; Alembic reads the active `DATABASE_URL` from
`.env`.

```bash
alembic upgrade head
alembic revision --autogenerate -m "describe change"
```

## Tests

Tests use an isolated in-memory SQLite database and never modify the configured
PostgreSQL database.

```bash
pytest
```

## Security

- `.env` and `exports/` are ignored by Git.
- API keys are never printed in full.
- Raw provider payloads are stored for audit but hidden from normal review
  tables.
- Exported files may contain sensitive review content and should be handled
  accordingly.
