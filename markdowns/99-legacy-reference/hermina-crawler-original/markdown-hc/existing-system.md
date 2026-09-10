# Existing System - Review System

Dokumen ini merangkum kondisi sistem berdasarkan codebase saat ini. Fokusnya adalah modul yang sudah ada, alur data, batasan implementasi, dan gap menuju pengembangan Voice of Customer V2.

## 1. Ringkasan Sistem

Review System saat ini adalah sistem review intelligence berbasis Python yang sudah memiliki:

- core service layer untuk lokasi, review, fetch, deduplication, analysis, summary, export, dan fetch log,
- FastAPI sebagai HTTP API untuk frontend,
- Next.js sebagai web interface operasional,
- PostgreSQL sebagai storage utama,
- Alembic sebagai migration manager,
- Selenium Google Maps scraper untuk mengambil review publik,
- Google Places client untuk official Places API dengan batas review yang terbatas,
- Local LLM client berbasis OpenAI-compatible API untuk analisis review,
- terminal app legacy melalui `python main.py`.

``Secara arsitektur, sistem sudah bergerak dari terminal-only MVP menjadi web MVP dengan API. Core logic tetap berada di folder `app/`, sedangkan API wrapper berada di `apps/api/` dan frontend berada di `hermina-crawler-fe/`.
``
## 2. Struktur Codebase

```text
app/
  config.py
  db/
    models.py
    session.py
  integrations/
    google_places_client.py
    selenium_google_maps_client.py
    local_llm_client.py
    gemini_client.py
    openrouter_client.py
    mock_review_client.py
  services/
    location_service.py
    fetch_service.py
    selenium_fetch_service.py
    review_service.py
    analysis_service.py
    summary_service.py
    export_service.py
    fetch_log_service.py
    settings_service.py
  terminal/
  prompts/

apps/api/
  main.py
  app_api/routers/

hermina-crawler-fe/
  app/
    dashboard/
    locations/
    fetch-jobs/
    reviews/
    analysis/
    insights/
    reports/
    settings/
    components/
    lib/

alembic/
tests/
markdowns/
exports/
```

## 3. Runtime Dan Dependency

Backend:

- Python
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL driver `psycopg2-binary`
- Selenium
- BeautifulSoup
- requests
- pandas
- Firecrawl Python SDK sudah tercantum di dependency, tetapi belum terlihat sebagai connector aktif di service layer
- OpenAI SDK untuk Local LLM/OpenRouter-compatible call
- google-genai masih tersedia untuk Gemini client

Frontend:

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS
- lucide-react icons

## 4. Konfigurasi Utama

Konfigurasi dibaca dari `.env` melalui `app/config.py`.

Field penting:

- `DATABASE_URL`
- `REVIEW_SOURCE_MODE`
- `GOOGLE_MAPS_API_KEY`
- `GOOGLE_PLACES_LANGUAGE_CODE`
- `GOOGLE_PLACES_REGION_CODE`
- `LOCAL_LLM_BASE_URL`
- `LOCAL_LLM_API_KEY`
- `LOCAL_LLM_MODEL`
- `FETCH_LIMIT_PER_LOCATION`
- `FETCH_TIMEOUT_SECONDS`
- `FETCH_MAX_RETRY`
- `SELENIUM_HEADLESS`
- `SELENIUM_DEFAULT_TARGET_REVIEWS`
- `SELENIUM_MAX_TARGET_REVIEWS`
- `SELENIUM_SCROLL_DELAY_SECONDS`
- `SELENIUM_MAX_SCROLL_ATTEMPTS`
- `SELENIUM_WAIT_TIMEOUT_SECONDS`
- `SELENIUM_USER_DATA_DIR`
- `ANALYSIS_BATCH_SIZE`
- `PROMPT_VERSION`
- `PAGE_SIZE`
- `SHOW_RAW_PAYLOAD`

Mode source yang dikenali:

- `mock`
- `google_places`
- `google_business_profile`
- `third_party`
- `selenium`

Catatan: `google_business_profile` sudah disebut di konfigurasi, tetapi implementasi connector-nya masih `UnsupportedReviewClient`.

## 5. Database Existing

Schema utama berada di `app/db/models.py`.

### 5.1 locations

Menyimpan cabang/lokasi yang akan diambil review-nya.

Field utama:

- `id`
- `hospital_name`
- `branch_name`
- `city`
- `address`
- `latitude`
- `longitude`
- `source`
- `external_place_id`
- `google_maps_url`
- `google_reviews_url`
- `target_review_count`
- `is_active`
- `created_at`
- `updated_at`

Constraint dan index:

- unique per `source` + `external_place_id`
- index active location
- index source/place

### 5.2 reviews

Menyimpan review yang sudah dinormalisasi.

Field utama:

- `location_id`
- `source`
- `external_place_id`
- `external_review_id`
- `reviewer_name`
- `reviewer_profile_url`
- `reviewer_photo_url`
- `reviewer_local_guide_level`
- `reviewer_total_reviews`
- `rating`
- `review_text`
- `review_time`
- `review_relative_time`
- `review_language`
- `language`
- `like_count`
- `owner_response_text`
- `owner_response_time`
- `scraped_at`
- `raw_payload`
- `review_hash`

Deduplication dilakukan dengan unique `review_hash`.

### 5.3 review_analysis

Menyimpan hasil AI analysis.

Field utama:

- `review_id`
- `sentiment`
- `sentiment_score`
- `issue_category`
- `urgency`
- `summary`
- `recommended_action`
- `keywords`
- `is_potential_viral`
- `is_patient_safety_issue`
- `model_name`
- `prompt_version`
- `raw_response`

### 5.4 fetch_logs

Menyimpan audit proses fetch/scraping.

Field utama:

- `location_id`
- `source`
- `status`
- `total_fetched`
- `total_inserted`
- `total_duplicate`
- `total_failed`
- `error_message`
- `metadata`
- `started_at`
- `finished_at`
- `created_at`

## 6. Backend API Existing

FastAPI dibuat di `apps/api/main.py` dengan base `/api`.

### 6.1 Health

- `GET /api/health`

### 6.2 Settings

- `GET /api/settings`
- `GET /api/settings/database-check`

Mengembalikan runtime config publik dan status masking API key.

### 6.3 Locations

- `GET /api/locations`
- `POST /api/locations`
- `GET /api/locations/{location_id}`
- `PATCH /api/locations/{location_id}`
- `POST /api/locations/{location_id}/toggle-active`
- `DELETE /api/locations/{location_id}`

Fitur sudah mencakup create, read, update, activate/deactivate, dan delete.

### 6.4 Reviews

- `GET /api/reviews`
- `GET /api/reviews/{review_id}`

Filter existing:

- page
- page size
- location id
- rating
- sentiment
- keyword
- latest first
- include raw payload

### 6.5 Dashboard

- `GET /api/dashboard/overview`
- `GET /api/dashboard/locations/{location_id}`
- `GET /api/dashboard/critical-issues`
- `GET /api/dashboard/negative-reviews`

Output mencakup total location, total review, coverage analysis, sentiment count, top issue, critical issues, latest fetch, location summary, negative review list, dan critical review list.

### 6.6 Fetch Jobs

- `POST /api/fetch-jobs`
- `POST /api/fetch-jobs/all-active`

Fetch dapat dijalankan untuk satu lokasi atau semua active location. Untuk Selenium, API memanggil `SeleniumFetchService`.

### 6.7 Fetch Logs

- `GET /api/fetch-logs`
- `GET /api/fetch-logs/latest`

Filter existing:

- location id
- failed only
- limit

### 6.8 Analysis

- `POST /api/analysis/pending`
- `POST /api/analysis/locations/{location_id}/rerun`
- `POST /api/analysis/reviews/{review_id}/rerun`

Analysis dapat dijalankan untuk pending review, rerun satu lokasi, atau rerun satu review.

### 6.9 Exports

- `POST /api/exports/reviews/all.csv`
- `POST /api/exports/reviews/location/{location_id}.csv`
- `POST /api/exports/analysis-summary.csv`
- `POST /api/exports/raw-reviews.json`

Export disimpan ke folder `exports/`.

### 6.10 Pipeline

- `POST /api/pipeline/location`

Endpoint orchestration untuk fetch, analyze, dan export per location.

## 7. Service Layer Existing

### 7.1 LocationService

Tanggung jawab:

- create location,
- list location,
- get location,
- update location,
- toggle active,
- delete location,
- validasi target review count.

### 7.2 FetchService

Tanggung jawab:

- memilih client berdasarkan `REVIEW_SOURCE_MODE`,
- fetch review dengan retry,
- normalisasi data review,
- generate hash,
- insert review,
- mencatat fetch log,
- dry run,
- fetch all active locations.

### 7.3 SeleniumFetchService

Tanggung jawab:

- validasi target review count,
- menjalankan Selenium client,
- menyimpan metadata scraping,
- insert review dengan normalizer dari `FetchService`,
- mencatat partial success jika target tidak terpenuhi.

### 7.4 ReviewService

Tanggung jawab:

- insert review dengan deduplication,
- get review detail,
- list review dengan filter,
- join latest analysis,
- export row retrieval.

### 7.5 AnalysisService

Tanggung jawab:

- mencari review yang belum dianalisis,
- memanggil AI client,
- validasi output AI,
- menyimpan hasil analysis,
- rerun analysis.

Allowed categories saat ini:

- `doctor_service`
- `nurse_service`
- `administration`
- `waiting_time`
- `cleanliness`
- `facility`
- `parking`
- `billing`
- `pharmacy`
- `emergency_room`
- `inpatient`
- `customer_service`
- `booking_system`
- `staff_communication`
- `security`
- `food`
- `general_praise`
- `other`

### 7.6 SummaryService

Tanggung jawab:

- overall summary,
- location summary,
- critical issue list,
- negative review list.

### 7.7 ExportService

Tanggung jawab:

- export all review CSV,
- export location review CSV,
- export analysis summary CSV,
- export raw review JSON.

### 7.8 FetchLogService

Tanggung jawab:

- start log,
- finish log,
- create dry run log,
- list log,
- get latest log.

## 8. Integration Existing

### 8.1 MockReviewClient

Digunakan untuk development/testing. Menghasilkan data deterministic agar fetch ulang dapat menguji deduplication.

### 8.2 GooglePlacesClient

Mengambil data dari Google Places API. Field mask mencakup:

- id
- displayName
- rating
- userRatingCount
- reviews

Batasan: client membatasi maksimal 5 review karena Places API bukan jalur full historical review management.

### 8.3 SeleniumGoogleMapsReviewClient

Scraper berbasis Selenium untuk Google Maps review panel.

Kemampuan:

- resolve URL dari `google_reviews_url`, `google_maps_url`, atau place id,
- validasi URL Google Maps,
- buka review panel,
- accept consent jika muncul,
- sort newest jika memungkinkan,
- scroll review container,
- expand review text,
- extract reviewer, rating, text, relative time, profile URL, photo URL, local guide flag, total reviews, like count, owner response, scraped time,
- simpan scraping metadata.

Batasan:

- tidak melakukan login automation,
- tidak bypass CAPTCHA,
- selector bisa patah jika Google Maps UI berubah,
- mode ini lebih cocok untuk POC/internal controlled usage.

### 8.4 LocalLLMClient

Client AI aktif yang dipakai `AnalysisService` saat ini.

Karakteristik:

- memakai OpenAI SDK,
- base URL configurable melalui `LOCAL_LLM_BASE_URL`,
- model configurable melalui `LOCAL_LLM_MODEL`,
- memaksa output JSON,
- validasi output memakai schema `ReviewAnalysisResult`.

### 8.5 GeminiClient dan OpenRouterClient

File client tersedia, tetapi service saat ini default ke `LocalLLMClient`.

Catatan teknis:

- `GeminiClient` dan `OpenRouterClient` merujuk beberapa setting seperti `gemini_model`, `gemini_api_key`, `openrouter_model`, dan `openrouter_api_key` yang belum terlihat di dataclass `Settings`.
- Jika ingin mengaktifkan lagi Gemini/OpenRouter, perlu sinkronisasi config.

## 9. AI Prompt Existing

Prompt berada di `app/prompts/review_analysis_prompt.md`.

Instruksi utama:

- role sebagai analis pengalaman pasien,
- tidak mengarang kejadian,
- sentiment: positive, neutral, negative, mixed, unknown,
- urgency: low, medium, high, critical, unknown,
- issue category dominan,
- summary dan recommended action dalam Bahasa Indonesia,
- maksimal lima keyword,
- patient safety dan viral flag hanya jika ada sinyal nyata.

## 10. Frontend Existing

Frontend berada di `hermina-crawler-fe/`.

### 10.1 App Shell

Komponen utama:

- left sidebar navigation,
- brand block,
- status backend target,
- main workspace.

Navigation existing:

- Dashboard
- Locations
- Fetch Jobs
- Reviews
- Analysis
- Insights
- Reports
- Settings

### 10.2 Dashboard Page

Status: implemented.

Fitur:

- health check,
- settings summary,
- total reviews,
- AI coverage,
- critical signals,
- pending AI,
- active locations,
- latest fetch,
- quick route to Locations, Fetch Jobs, Reviews.

### 10.3 Locations Page

Status: implemented.

Fitur:

- create location,
- edit location,
- delete location,
- toggle active,
- source filter,
- status filter,
- target review count,
- Google Maps URL,
- location registry table,
- simple branch risk score dari loaded reviews.

### 10.4 Fetch Jobs Page

Status: implemented.

Fitur:

- run fetch satu lokasi,
- dry run satu lokasi,
- fetch all active,
- dry run all active,
- select location,
- target review count,
- fetch log table,
- status filter.

### 10.5 Reviews Page

Status: implemented.

Fitur:

- review table,
- backend pagination,
- keyword search,
- filter location,
- filter sentiment,
- filter rating,
- rating display,
- sentiment badge,
- urgency badge,
- issue label,
- safety/viral flags,
- recommended action display.

### 10.6 Analysis Page

Status: implemented.

Fitur:

- analyze pending,
- rerun location analysis,
- rerun review analysis,
- location scope,
- rating filter,
- analysis coverage,
- pending review sample,
- analyzed review sample.

### 10.7 Insights Page

Status: implemented.

Fitur:

- reputation risk heuristic,
- critical count,
- negative count,
- recommendation count,
- top issue list,
- critical alerts,
- recommended actions,
- negative review watchlist.

### 10.8 Reports Page

Status: route placeholder.

Tujuan yang tertulis:

- mengelola export CSV/JSON,
- paket laporan stakeholder.

### 10.9 Settings Page

Status: route placeholder.

Tujuan yang tertulis:

- runtime config,
- API key status,
- database connection check.

## 11. Design System Existing

Karakter visual:

- dashboard operational style,
- dark left sidebar,
- light workspace,
- glass-like panels,
- muted professional palette,
- sage/blue/green/amber/red/purple accents,
- lucide icons,
- reusable DataTable,
- badge system untuk sentiment/urgency/status,
- responsive grid.

Component existing:

- `AppShell`
- `PageHeader`
- `SectionHeader`
- `Badge`
- `EmptyState`
- `BackendWarning`
- `ActionMessagePanel`
- `DataTable`
- `PlaceholderPage`

## 12. Test Existing

Test folder mencakup:

- MVP core behavior,
- Selenium scraping service behavior,
- real integration tests.

Test menggunakan isolated SQLite in-memory untuk core tests, sehingga tidak memodifikasi PostgreSQL configured.

## 13. Hal Yang Sudah Siap

- Core object location/review/analysis/fetch log sudah ada.
- Fetch dan deduplication sudah bekerja di service layer.
- API sudah expose sebagian besar fitur MVP.
- Web admin/ops sudah bisa operate lokasi, fetch job, review browsing, analysis, dan insights.
- Selenium scraper sudah punya metadata dan target count.
- Export CSV/JSON sudah ada di backend.
- Prompt AI sudah versionable melalui `PROMPT_VERSION`.

## 14. Gap Existing

Gap menuju produk Onebox/VoC V2:

- belum ada profile/company/government account management,
- belum ada multi-tenant organization model,
- belum ada auth/login/register,
- belum ada role dan permission,
- belum ada feature entitlement seperti `ai_enable_flag`, `total_enable_review`, `analyze_competitor_flag`,
- belum ada competitor entity dan competitor review pipeline,
- belum ada heatmap/map visualization,
- belum ada website crawler connector berbasis Firecrawl meskipun dependency sudah tersedia,
- belum ada social media connector,
- belum ada Google Business Profile connector yang benar-benar aktif,
- belum ada queue/background worker untuk long-running Selenium/AI job,
- fetch job masih dieksekusi synchronously lewat API,
- belum ada scheduler,
- belum ada action tracker untuk supervisor/unit kerja,
- belum ada taxonomy management untuk product/wilayah/unit kerja/klasifikasi masalah/layanan,
- Reports dan Settings masih placeholder di frontend,
- belum ada audit trail user action,
- belum ada response/reply workflow ke channel review.

## 15. Kesimpulan Existing System

Sistem saat ini sudah cukup matang sebagai internal review intelligence MVP. Basis datanya sudah menyimpan review, analysis, dan log. Backend API dan frontend operasional juga sudah tersedia.

Pengembangan V2 sebaiknya tidak mengganti fondasi ini. Yang perlu dilakukan adalah menambahkan layer SaaS/Product di atas core existing:

- profile/company management,
- auth dan role,
- entitlement/feature flag,
- source connector tambahan,
- competitor analysis,
- map/heatmap,
- taxonomy VoC,
- job queue,
- action tracker,
- reporting yang lebih stakeholder-ready.

