# 02_INFRA.md

# Review System — Infrastructure & Project Setup Specification

## 1. Objective

This document defines the infrastructure, project structure, database setup, environment configuration, dependencies, and local development setup for **Review System**.

The application is a local terminal-based Python program that runs with:

```bash
python main.py
```

The app uses:

* Python
* PostgreSQL
* SQLAlchemy
* Alembic
* `.env` configuration
* Gemini API client
* Review source API client
* Interactive terminal interface

This is not a web application.

---

## 2. Infrastructure Scope

The MVP infrastructure must support:

1. Running the application locally.
2. Connecting to local PostgreSQL.
3. Managing database schema through migration.
4. Reading configuration from `.env`.
5. Separating terminal UI, services, database, integrations, prompts, and utilities.
6. Supporting mock review fetching if real API is not ready.
7. Supporting mock Gemini analysis if Gemini API is not ready.
8. Exporting data to local files.

---

## 3. Recommended Tech Stack

### 3.1 Language

Use:

```text
Python 3.11+
```

Reason:

* Suitable for local automation.
* Easy to build terminal app.
* Easy API integration.
* Strong PostgreSQL support.
* Easy AI integration.

---

### 3.2 Database

Use:

```text
PostgreSQL
```

Local database name:

```text
hermina_reviews
```

Recommended local connection:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hermina_reviews
```

---

### 3.3 ORM

Use:

```text
SQLAlchemy
```

Reason:

* Clean model definition.
* Easier query management.
* Better long-term maintainability.

---

### 3.4 Migration

Use:

```text
Alembic
```

Reason:

* Database schema can evolve safely.
* Better for future production migration.

---

### 3.5 Terminal Interface

Use simple Python terminal interaction.

Recommended options:

* Standard `input()` and `print()` for first MVP.
* Optional: `rich` for better table display.
* Optional: `tabulate` for table formatting.

Do not build argument-based CLI such as:

```bash
python main.py fetch --location-id 1
```

The user must only run:

```bash
python main.py
```

Then navigate using the interactive terminal menu.

---

### 3.6 Environment Management

Use:

```text
python-dotenv
```

All sensitive configuration must be loaded from `.env`.

Do not hardcode:

* Database URL
* Gemini API key
* Google Maps API key
* Third-party provider key

---

## 4. Project Folder Structure

Generate the project using this structure:

```text
hermina-review-intelligence/
│
├── main.py
│
├── app/
│   ├── __init__.py
│   ├── config.py
│
│   ├── terminal/
│   │   ├── __init__.py
│   │   ├── main_menu.py
│   │   ├── location_menu.py
│   │   ├── fetch_menu.py
│   │   ├── review_menu.py
│   │   ├── analysis_menu.py
│   │   ├── summary_menu.py
│   │   ├── export_menu.py
│   │   ├── fetch_log_menu.py
│   │   └── settings_menu.py
│
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py
│   │   ├── base.py
│   │   └── models.py
│
│   ├── services/
│   │   ├── __init__.py
│   │   ├── location_service.py
│   │   ├── fetch_service.py
│   │   ├── review_service.py
│   │   ├── analysis_service.py
│   │   ├── summary_service.py
│   │   ├── export_service.py
│   │   ├── fetch_log_service.py
│   │   └── settings_service.py
│
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── review_source_client.py
│   │   ├── google_places_client.py
│   │   ├── mock_review_client.py
│   │   ├── gemini_client.py
│   │   └── mock_gemini_client.py
│
│   ├── prompts/
│   │   └── review_analysis_prompt.md
│
│   └── utils/
│       ├── __init__.py
│       ├── hashing.py
│       ├── logger.py
│       ├── date_parser.py
│       ├── formatter.py
│       └── pagination.py
│
├── alembic/
│   ├── versions/
│   └── env.py
│
├── docs/
│   ├── 01_LOGIC.md
│   ├── 02_INFRA.md
│   └── 03_FETCHING.md
│
├── exports/
│
├── .env
├── .env.example
├── requirements.txt
├── alembic.ini
├── README.md
└── .gitignore
```

---

## 5. Main File Responsibility

### 5.1 `main.py`

`main.py` must be the application entry point.

Responsibility:

* Load environment.
* Initialize app.
* Start interactive terminal menu.
* Handle top-level unexpected errors.

Example behavior:

```python
from app.terminal.main_menu import run_main_menu

if __name__ == "__main__":
    run_main_menu()
```

Do not put business logic directly in `main.py`.

---

## 6. Config Specification

### 6.1 `app/config.py`

This file must read environment variables from `.env`.

Required config:

```python
APP_ENV
DATABASE_URL
REVIEW_SOURCE_MODE
GOOGLE_MAPS_API_KEY
GEMINI_API_KEY
GEMINI_MODEL
FETCH_LIMIT_PER_LOCATION
ANALYSIS_BATCH_SIZE
EXPORT_DIR
LOG_LEVEL
```

---

## 7. Environment Variables

### 7.1 `.env.example`

Create `.env.example` with:

```env
APP_ENV=local

DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hermina_reviews

REVIEW_SOURCE_MODE=mock
GOOGLE_MAPS_API_KEY=

GEMINI_MODE=mock
GEMINI_API_KEY=
GEMINI_MODEL=gemini-1.5-flash

FETCH_LIMIT_PER_LOCATION=50
ANALYSIS_BATCH_SIZE=20

EXPORT_DIR=exports
LOG_LEVEL=INFO
```

---

### 7.2 Environment Mode Rules

`REVIEW_SOURCE_MODE` allowed values:

```text
mock
google_places
third_party
```

Rules:

* `mock`: use `MockReviewClient`.
* `google_places`: use `GooglePlacesClient`.
* `third_party`: use future provider client.

`GEMINI_MODE` allowed values:

```text
mock
real
```

Rules:

* `mock`: use `MockGeminiClient`.
* `real`: use `GeminiClient`.

---

## 8. Requirements

Create `requirements.txt` with minimum dependencies:

```txt
SQLAlchemy
alembic
psycopg2-binary
python-dotenv
requests
rich
tabulate
google-generativeai
pandas
```

Optional:

```txt
pytest
black
ruff
```

---

## 9. Database Tables

Use SQLAlchemy models and Alembic migration.

Required tables:

1. `locations`
2. `reviews`
3. `review_analysis`
4. `fetch_logs`

---

## 10. Database Model: locations

### 10.1 Purpose

Stores Hermina hospital location master data.

### 10.2 Fields

```sql
id SERIAL PRIMARY KEY
hospital_name VARCHAR(150) NOT NULL
branch_name VARCHAR(150) NOT NULL
city VARCHAR(100)
address TEXT
latitude NUMERIC(10, 7)
longitude NUMERIC(10, 7)
source VARCHAR(50) NOT NULL
external_place_id VARCHAR(255) NOT NULL
is_active BOOLEAN DEFAULT TRUE
created_at TIMESTAMP DEFAULT NOW()
updated_at TIMESTAMP DEFAULT NOW()
```

### 10.3 Constraints

* `branch_name` is required.
* `source` is required.
* `external_place_id` is required.
* Combination of `source` and `external_place_id` should be unique.

---

## 11. Database Model: reviews

### 11.1 Purpose

Stores raw review data from external source.

### 11.2 Fields

```sql
id SERIAL PRIMARY KEY
location_id INTEGER REFERENCES locations(id)
source VARCHAR(50) NOT NULL
external_place_id VARCHAR(255)
external_review_id VARCHAR(255)
reviewer_name VARCHAR(255)
rating INTEGER
review_text TEXT
review_time TIMESTAMP
language VARCHAR(20)
raw_payload JSONB
review_hash VARCHAR(255) UNIQUE
created_at TIMESTAMP DEFAULT NOW()
updated_at TIMESTAMP DEFAULT NOW()
```

### 11.3 Constraints

* `location_id` is required.
* `source` is required.
* `review_hash` must be unique.
* `rating` should be between 1 and 5 if available.

---

## 12. Database Model: review_analysis

### 12.1 Purpose

Stores AI analysis result for reviews.

### 12.2 Fields

```sql
id SERIAL PRIMARY KEY
review_id INTEGER REFERENCES reviews(id)
sentiment VARCHAR(50)
sentiment_score NUMERIC(5, 4)
issue_category VARCHAR(100)
urgency VARCHAR(50)
summary TEXT
recommended_action TEXT
keywords JSONB
is_potential_viral BOOLEAN DEFAULT FALSE
is_patient_safety_issue BOOLEAN DEFAULT FALSE
model_name VARCHAR(100)
prompt_version VARCHAR(50)
raw_response JSONB
created_at TIMESTAMP DEFAULT NOW()
```

### 12.3 Rules

* Do not overwrite old analysis.
* Re-run analysis should create a new row.
* Latest analysis can be determined by newest `created_at`.

---

## 13. Database Model: fetch_logs

### 13.1 Purpose

Stores every fetch attempt.

### 13.2 Fields

```sql
id SERIAL PRIMARY KEY
location_id INTEGER REFERENCES locations(id)
source VARCHAR(50)
status VARCHAR(50)
total_fetched INTEGER DEFAULT 0
total_inserted INTEGER DEFAULT 0
total_duplicate INTEGER DEFAULT 0
total_failed INTEGER DEFAULT 0
error_message TEXT
started_at TIMESTAMP
finished_at TIMESTAMP
created_at TIMESTAMP DEFAULT NOW()
```

### 13.3 Status Values

Allowed values:

```text
success
failed
partial_success
dry_run
```

---

## 14. Recommended Indexes

Create indexes:

```sql
CREATE INDEX idx_locations_source_place ON locations(source, external_place_id);
CREATE INDEX idx_locations_active ON locations(is_active);

CREATE INDEX idx_reviews_location_id ON reviews(location_id);
CREATE INDEX idx_reviews_review_time ON reviews(review_time);
CREATE INDEX idx_reviews_rating ON reviews(rating);
CREATE INDEX idx_reviews_review_hash ON reviews(review_hash);
CREATE INDEX idx_reviews_source_place ON reviews(source, external_place_id);

CREATE INDEX idx_review_analysis_review_id ON review_analysis(review_id);
CREATE INDEX idx_review_analysis_sentiment ON review_analysis(sentiment);
CREATE INDEX idx_review_analysis_issue_category ON review_analysis(issue_category);
CREATE INDEX idx_review_analysis_urgency ON review_analysis(urgency);

CREATE INDEX idx_fetch_logs_location_id ON fetch_logs(location_id);
CREATE INDEX idx_fetch_logs_status ON fetch_logs(status);
CREATE INDEX idx_fetch_logs_started_at ON fetch_logs(started_at);
```

---

## 15. Database Session

### 15.1 `app/db/session.py`

Must provide:

* SQLAlchemy engine.
* SessionLocal.
* `get_db_session()` helper.
* Proper close session handling.

Example behavior:

```python
session = SessionLocal()
try:
    # use session
finally:
    session.close()
```

---

## 16. Migration Setup

Use Alembic.

Required commands in README:

```bash
alembic init alembic
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Codex should generate model definitions so Alembic can detect schema.

---

## 17. Logging

Create utility:

```text
app/utils/logger.py
```

Logging should support:

* INFO
* WARNING
* ERROR

Log events:

* App startup.
* Database connection check.
* Fetch started.
* Fetch finished.
* Fetch failed.
* Analysis started.
* Analysis failed.
* Export completed.

Do not log full API keys.

---

## 18. Export Directory

All exported files must be stored in:

```text
exports/
```

If folder does not exist, create it automatically.

---

## 19. Mock Mode Requirement

The app must be able to run without real external API keys.

This means:

* If `REVIEW_SOURCE_MODE=mock`, fetching must return mock review data.
* If `GEMINI_MODE=mock`, analysis must return mock structured analysis.
* This allows development without Google/Gemini API.

---

## 20. Mock Review Client

`MockReviewClient` should return sample reviews.

Minimum sample data:

* Positive review.
* Negative review about waiting time.
* Negative review about administration.
* Mixed review.
* Neutral review.

---

## 21. Mock Gemini Client

`MockGeminiClient` should return structured JSON similar to real Gemini output.

Example:

```json
{
  "sentiment": "negative",
  "sentiment_score": 0.85,
  "issue_category": "waiting_time",
  "urgency": "medium",
  "summary": "Pasien mengeluhkan waktu tunggu yang lama.",
  "recommended_action": "Evaluasi alur antrean dan kapasitas petugas.",
  "keywords": ["antrean", "lama"],
  "is_potential_viral": false,
  "is_patient_safety_issue": false
}
```

---

## 22. Local Setup Instructions

README must include:

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate virtual environment
# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create PostgreSQL database
createdb hermina_reviews

# 5. Copy env file
cp .env.example .env

# 6. Run migration
alembic upgrade head

# 7. Run application
python main.py
```

---

## 23. Terminal Display

Use readable terminal display.

Preferred:

* `rich` table if available.
* fallback to simple print table.

Do not make the app depend on advanced UI.

The app should still work in normal terminal.

---

## 24. Error Handling Requirements

The infrastructure must handle:

* Missing `.env`
* Missing database URL
* Database connection failed
* Migration not run
* Missing API key
* Invalid API mode
* Export folder missing
* Invalid table data

The app must not crash silently.

Show clear error message.

---

## 25. Security Rules

* Never print full API key.
* Never commit `.env`.
* Use `.env.example` for sample config.
* Add `.env` to `.gitignore`.
* Add `exports/` to `.gitignore` if exported files may contain sensitive review data.
* Store raw review payload in database, but do not expose it by default in terminal.

---

## 26. `.gitignore`

Create `.gitignore`:

```gitignore
.env
venv/
__pycache__/
*.pyc
exports/
.pytest_cache/
.DS_Store
```

---

## 27. Acceptance Criteria

Codex should generate infrastructure that satisfies:

1. `python main.py` starts the terminal app.
2. App reads config from `.env`.
3. App connects to PostgreSQL.
4. SQLAlchemy models exist for required tables.
5. Alembic migration can create all tables.
6. App can run in mock mode without external API keys.
7. App has separated folders for terminal, services, integrations, db, utils, and prompts.
8. API keys are not hardcoded.
9. Export folder is handled correctly.
10. Logging exists.
11. Database errors are handled gracefully.
12. Business logic is not placed directly in terminal menu files.
13. Mock clients exist for review source and Gemini.
14. Project can be extended later into web dashboard or scheduler.

---

## 28. Important Notes for Codex

* Do not create a web app.
* Do not create FastAPI yet.
* Do not create frontend.
* Do not use command-line argument commands.
* Build interactive terminal menu only.
* Keep code modular.
* Prioritize maintainability.
* Mock mode must work first.
* Real API integrations can be implemented behind client classes.
