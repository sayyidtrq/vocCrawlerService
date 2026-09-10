# Review System - Product Plan

## 1. Product Objective

Review System adalah platform review intelligence untuk rumah sakit. Tujuannya membantu tim pusat, cabang, patient experience, marketing, dan manajemen operasional untuk:

1. mengambil data review secara on-demand / real-time sesuai request dan filter,
2. menyimpan dan membersihkan data review dari berbagai cabang,
3. menganalisis sentimen, kategori masalah, urgency, dan risiko,
4. menyajikan dashboard dan visualisasi yang mudah dibaca,
5. menghasilkan insight dan rekomendasi aksi untuk vendor / client rumah sakit,
6. menjadi fondasi untuk predictive analysis dan AI recommendation di fase berikutnya.

Untuk MVP, market utama adalah rumah sakit dengan multi-cabang, mengikuti logic yang sudah ada di `logic.md`.

---

## 2. Current Core System

Core system yang sudah ada tetap menjadi sumber kebenaran awal. Web product tidak mengganti logic utama, tetapi membungkusnya menjadi produk yang lebih scalable.

Core existing modules:

- Location management
- Fetch / sync reviews
- Mock source
- Google Places source
- Selenium scraping source
- PostgreSQL storage
- Review deduplication
- Fetch logs
- Gemini analysis
- Review browsing / filtering
- Summary
- Export CSV / JSON
- Feature
- Terminal interactive menu via `python main.py`


Target perubahan:

- Terminal app tetap bisa dipakai sebagai internal tool.
- Business logic Python dipertahankan sebagai core engine.
- Web app menjadi interface utama untuk user product.
- Fetching, analysis, visualization, dan reporting dipindahkan ke web experience.

---

## 3. MVP Product Scope

### MVP goal

Membuat web-based review intelligence platform untuk rumah sakit yang bisa:

1. manage daftar rumah sakit / cabang,
2. menjalankan review scraping/fetch secara manual dari web,
3. melihat hasil fetch dan log-nya,
4. melihat review dalam table yang bisa difilter,
5. menjalankan AI analysis untuk review,
6. melihat dashboard insight dasar,
7. export data atau report sederhana.

### MVP non-goals

Untuk menjaga scope tetap realistis, MVP belum mencakup:

- scheduler otomatis,
- billing / subscription,
- full self-serve multi-tenant SaaS,
- web dashboard yang terlalu kompleks,
- scraping agresif, proxy rotation, CAPTCHA bypass, atau auth bypass,
- mobile app,
- automated reply ke Google Review,
- enterprise SSO,
- predictive model custom yang kompleks.

Catatan penting: scraping Selenium adalah mode POC/internal testing. Untuk production serius, sumber data resmi seperti Google Business Profile API, partner data provider, atau izin client perlu dipertimbangkan.

---

## 4. Target Users

### Primary users

1. Patient Experience / Customer Experience Team
   - Melihat keluhan pasien.
   - Mengidentifikasi issue yang sering muncul.
   - Memprioritaskan review urgent.

2. Branch Manager / Hospital Manager
   - Melihat performa cabang.
   - Membandingkan rating, sentimen, dan kategori issue.
   - Mengambil tindakan operasional.

3. Marketing / Reputation Team
   - Memantau reputasi online.
   - Melihat trend review negatif dan positif.
   - Menyiapkan bahan laporan.

4. Management / Executive
   - Melihat ringkasan performa seluruh cabang.
   - Melihat risiko reputasi dan patient safety.
   - Mengambil keputusan berbasis data.

### MVP user role

Untuk MVP awal, cukup pakai satu role:

- Admin / Internal Operator

Role lanjutan seperti `owner`, `manager`, `analyst`, dan `viewer` bisa disiapkan di schema tapi belum wajib aktif di UI.

---

## 5. Product Modules

### 5.1 Locations

Mengelola daftar rumah sakit / cabang.

Fitur:

- Add location
- Edit location
- Activate / deactivate location
- Delete location
- Set source mode per location
- Simpan external place id
- Simpan Google Maps URL
- Simpan Google reviews URL
- Simpan target review count

Field penting:

- hospital name
- branch name
- city
- address
- latitude
- longitude
- source
- external place id
- google maps url
- google reviews url
- target review count
- active status

### 5.2 Fetch / Scrape Jobs

Mengambil review berdasarkan location dan source.

Source modes:

- `mock`
- `google_places`
- `selenium`
- `third_party` / future provider

Fitur MVP:

- Start fetch for one location
- Start fetch for all active locations
- Dry run fetch
- View last fetch result
- View fetch history
- See inserted / duplicate / failed counts
- See source used
- See job status

Untuk web product, konsep terminal `Fetch / Sync Reviews` dipindah menjadi halaman `Fetch Jobs`.

### 5.3 Reviews

Menampilkan data review yang sudah tersimpan.

Fitur:

- Review table
- Filter by location
- Filter by rating
- Filter by date range
- Filter by source
- Filter by sentiment
- Filter by issue category
- Filter by urgency
- Filter by analyzed / not analyzed
- Search by reviewer / text / keyword
- Detail drawer untuk melihat raw payload jika diperlukan

### 5.4 AI Analysis

Menganalisis review menggunakan Gemini atau mock mode.

Output sesuai `logic.md`:

- sentiment
- sentiment score
- issue category
- urgency
- summary
- recommended action
- keywords
- potential viral
- patient safety

Fitur MVP:

- Analyze unprocessed reviews
- Analyze selected location
- Analyze selected reviews
- View analysis result per review
- Batch analysis status

### 5.5 Dashboard & Visualization

Menyajikan ringkasan data dalam bentuk visual.

MVP dashboard:

- Total reviews
- Average rating
- Rating distribution
- Sentiment distribution
- Issue category distribution
- Urgency distribution
- Review trend over time
- Negative review trend
- Top issue categories
- Top keywords
- Branch comparison
- Critical / high urgency reviews

### 5.6 Insights & Recommendation

Menyajikan insight praktis untuk client.

MVP insight:

- Cabang dengan sentimen negatif tertinggi
- Kategori masalah paling sering muncul
- Review urgent yang butuh perhatian
- Rekomendasi tindakan dari AI
- Ringkasan kondisi cabang
- Potensi risiko reputasi
- Potensi patient safety issue

### 5.7 Reports & Export

Menghasilkan output untuk stakeholder.

MVP:

- Export reviews CSV
- Export analysis CSV
- Export JSON
- Download report sederhana per location / date range

Future:

- PDF executive report
- Scheduled email report
- PowerPoint summary
- Client-branded report

---

## 6. Web App Pages

Frontend menggunakan Next.js dengan clean modern UI, sidebar, table, filter, dan chart.

### 6.1 App Shell

Layout:

- Left sidebar navigation
- Top bar
- Main content area
- Page-level filters
- Toast notification
- Loading states
- Empty states

Navigation:

- Dashboard
- Locations
- Fetch Jobs
- Reviews
- Analysis
- Insights
- Reports
- Settings

### 6.2 Dashboard Page

Tujuan:

- Memberikan overview cepat kondisi review rumah sakit.

Komponen:

- KPI cards
- Rating trend chart
- Sentiment chart
- Issue category chart
- Urgency chart
- Recent critical reviews
- Branch comparison table

### 6.3 Locations Page

Tujuan:

- Mengelola cabang rumah sakit.

Komponen:

- Location table
- Add/edit location form
- Active toggle
- Source badge
- Target review count
- External place id
- Google review URL

### 6.4 Fetch Jobs Page

Tujuan:

- Menjalankan dan memantau proses scraping/fetch.

Komponen:

- Start fetch button
- Dry run button
- Location selector
- Source selector
- Target count input
- Fetch log table
- Job detail drawer
- Inserted / duplicate / failed summary

### 6.5 Reviews Page

Tujuan:

- Melihat dan memfilter review mentah maupun review yang sudah dianalisis.

Komponen:

- Review table
- Filter bar
- Rating badge
- Sentiment badge
- Urgency badge
- Category badge
- Review detail drawer
- Raw payload toggle for internal admin

### 6.6 Analysis Page

Tujuan:

- Menjalankan AI analysis dan melihat coverage analisis.

Komponen:

- Analyze unprocessed button
- Analyze by location
- Batch status
- Analysis coverage card
- Failed analysis log

### 6.7 Insights Page

Tujuan:

- Memberikan rekomendasi action-oriented.

Komponen:

- AI summary card
- Top issues
- Recommended actions
- Patient safety alerts
- Reputation risk cards
- Branch priority list

### 6.8 Reports Page

Tujuan:

- Export dan report generation.

Komponen:

- Date range picker
- Location selector
- Report type selector
- Export CSV / JSON
- Future: PDF generation

### 6.9 Settings Page

Tujuan:

- Mengelola konfigurasi local/product.

Komponen:

- Source mode
- Gemini mode
- Fetch limit
- Timeout
- Retry
- Batch size
- Prompt version
- Export directory

---

## 7. Recommended Technical Architecture

### Senior engineering judgement

Karena core system sudah Python dan scraping Selenium juga Python, backend sebaiknya tetap Python.

Rekomendasi utama untuk MVP web product:

> Next.js frontend + FastAPI backend + existing Python core services + PostgreSQL.

Alasan memilih FastAPI untuk MVP:

- Lebih ringan daripada Django untuk API-first product.
- Cocok untuk membungkus service layer yang sudah ada.
- Cocok untuk job-style endpoint seperti fetch, analyze, export.
- Lebih cepat untuk membuat API kontrak antara frontend dan backend.
- Tidak memaksa struktur ORM/admin Django ke app yang sudah punya SQLAlchemy/Alembic.
- Lebih natural jika nanti ada worker terpisah untuk scraping dan AI analysis.

Django tetap opsi bagus kalau product membutuhkan:

- built-in admin panel yang kuat,
- user/permission CRUD kompleks sejak awal,
- monolith backend yang sangat admin-heavy,
- Django ORM sebagai pusat aplikasi.

Namun untuk kondisi project saat ini, FastAPI lebih clean dan lebih sedikit migrasi konsep.

### Proposed architecture

```text
Next.js Web App
   |
   | REST / JSON API
   v
FastAPI Backend
   |
   | calls existing Python services
   v
Hermina Core Engine
   |-- LocationService
   |-- FetchService
   |-- ReviewService
   |-- AnalysisService
   |-- SummaryService
   |-- ExportService
   |-- FetchLogService
   |-- SettingsService
   |
   v
PostgreSQL
```

Future scalable version:

```text
Next.js Web App
   |
FastAPI API Server
   |
Queue / Job Broker
   |
Worker Process
   |-- Selenium Scraper
   |-- Gemini Analyzer
   |-- Export Generator
   |
PostgreSQL / Supabase Postgres
```

---

## 8. Suggested Stack

### Frontend

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui or similar clean component system
- Chart library such as Recharts
- TanStack Table for complex review tables
- React Hook Form + Zod for forms/validation

### Backend

- FastAPI
- SQLAlchemy
- Alembic
- Pydantic
- Existing Python service layer
- Selenium for current scraping mode
- Gemini integration for AI analysis

### Database

Local MVP:

- PostgreSQL local

Cloud-ready:

- Supabase Postgres

### Background jobs

MVP local:

- Manual endpoint can run job synchronously for early prototype
- Safer option: background task with job status

Scalable version:

- Redis + Celery/RQ/Dramatiq
- Dedicated worker for scraping and analysis

### Storage

Local MVP:

- `exports/`

Cloud-ready:

- Supabase Storage or S3-compatible object storage

---

## 9. API Design Draft

### Locations

- `GET /api/locations`
- `GET /api/locations/{id}`
- `POST /api/locations`
- `PATCH /api/locations/{id}`
- `DELETE /api/locations/{id}`
- `PATCH /api/locations/{id}/active`

### Fetch jobs

- `POST /api/fetch-jobs`
- `POST /api/fetch-jobs/dry-run`
- `GET /api/fetch-jobs`
- `GET /api/fetch-jobs/{id}`
- `GET /api/fetch-jobs/latest`

### Reviews

- `GET /api/reviews`
- `GET /api/reviews/{id}`
- `GET /api/reviews/summary`

Supported filters:

- location id
- source
- rating
- date range
- sentiment
- issue category
- urgency
- analyzed status
- keyword
- patient safety
- potential viral

### Analysis

- `POST /api/analysis/run`
- `POST /api/analysis/run-location`
- `POST /api/analysis/run-selected`
- `GET /api/analysis/status`

### Dashboard

- `GET /api/dashboard/overview`
- `GET /api/dashboard/trends`
- `GET /api/dashboard/categories`
- `GET /api/dashboard/branches`
- `GET /api/dashboard/urgent-reviews`

### Exports

- `POST /api/exports/reviews`
- `POST /api/exports/analysis`
- `GET /api/exports`
- `GET /api/exports/{id}/download`

### Settings

- `GET /api/settings`
- `PATCH /api/settings`

---

## 10. Database Evolution

Existing database can be reused.

Current important entities:

- locations
- reviews
- review_analyses / analysis fields
- fetch_logs
- settings

Recommended additions for web product:

### `fetch_jobs`

Represents a user-triggered fetch/scrape request.

Fields:

- id
- location_id
- source
- status
- requested_target_count
- fetched_count
- inserted_count
- duplicate_count
- failed_count
- error_message
- started_at
- finished_at
- created_by
- metadata

### `exports`

Represents generated export/report file.

Fields:

- id
- type
- format
- file_path / storage_path
- filters
- status
- created_at
- created_by

### `organizations`

Future multi-tenant readiness.

Fields:

- id
- name
- slug
- status

### `users`

Future auth readiness.

Fields:

- id
- organization_id
- email
- name
- role
- status

For MVP local, `organizations` and `users` can be prepared but not fully enforced.

---

## 11. Supabase Readiness

Supabase cocok untuk fase cloud karena bisa menyediakan:

- managed Postgres,
- Auth,
- Storage,
- dashboard DB,
- API ecosystem.

Namun scraping Selenium tidak cocok dijalankan di Supabase Edge Function karena membutuhkan browser automation yang berat dan stateful. Scraping sebaiknya tetap di worker/server terpisah.

Recommended cloud shape:

```text
Vercel / other frontend host
   |
FastAPI backend on container/server
   |
Worker container for Selenium + AI
   |
Supabase Postgres
   |
Supabase Storage for exports/reports
```

Supabase principles:

- Keep schema portable with Alembic migrations.
- Use Supabase Postgres as database, not as scraping runtime.
- Enable Row Level Security when frontend directly accesses Supabase.
- Do not expose service role key to frontend.
- Backend/worker may use privileged credentials only on server-side env.
- Keep local `.env` first, then mirror to cloud env variables later.

---

## 12. Environment Strategy

### Local MVP

Use `.env` local:

- `APP_ENV=local`
- `DATABASE_URL`
- `REVIEW_SOURCE_MODE`
- `GOOGLE_MAPS_API_KEY`
- `GEMINI_MODE`
- `GEMINI_API_KEY`
- `FETCH_LIMIT_PER_LOCATION`
- `FETCH_TIMEOUT_SECONDS`
- `FETCH_MAX_RETRY`
- `ANALYSIS_BATCH_SIZE`
- `PROMPT_VERSION`
- `PAGE_SIZE`
- `SHOW_RAW_PAYLOAD`

Additional future web env:

- `API_BASE_URL`
- `NEXT_PUBLIC_API_BASE_URL`
- `WEB_APP_URL`
- `AUTH_ENABLED`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `REDIS_URL`
- `EXPORT_STORAGE_MODE`
- `SELENIUM_PROFILE_DIR`
- `SELENIUM_HEADLESS`

Rule:

- Anything prefixed with `NEXT_PUBLIC_` is visible to browser.
- Secrets must only live in backend/worker env.

---

## 13. Data Source Strategy

### Source mode: mock

Purpose:

- development
- testing
- demo without external dependency

### Source mode: google_places

Purpose:

- official Google API access
- limited review count depending API behavior
- safer than scraping

### Source mode: selenium

Purpose:

- internal POC
- manual/on-demand scraping
- collecting visible Google Maps reviews beyond official API limitations

Constraints:

- no aggressive scraping,
- no proxy rotation,
- no CAPTCHA bypass,
- no auth bypass,
- respect delays and max target limits,
- not production default without legal/product review.

### Future source mode: client-owned official source

Potential options:

- Google Business Profile API if client owns/manages profile,
- third-party review provider,
- uploaded CSV/XLSX from client,
- internal hospital feedback system.

---

## 14. Analytics & AI Scope

### MVP analytics

- average rating
- rating distribution
- review count trend
- sentiment distribution
- issue category distribution
- urgency distribution
- keyword frequency
- branch comparison
- negative review list
- critical review list

### MVP AI recommendation

For each review:

- issue category
- urgency level
- summary
- recommended action
- patient safety flag
- potential viral flag

For dashboard:

- top 3 branch risks
- top 5 recurring issues
- action recommendation by issue category
- executive summary per selected period

### Future predictive analysis

Potential features:

- rating forecast
- negative review spike detection
- reputational risk score
- patient safety risk trend
- branch-level issue prediction
- seasonal complaint pattern
- anomaly detection
- churn / dissatisfaction proxy score

---

## 15. MVP User Flow

### Flow 1: Setup location

1. User opens Locations page.
2. User clicks Add Location.
3. User inputs hospital branch data.
4. User inputs Google Maps / Google Reviews URL.
5. User sets source mode.
6. User sets target review count.
7. User saves location.

### Flow 2: Fetch reviews

1. User opens Fetch Jobs page.
2. User selects location.
3. User selects source mode.
4. User chooses target count.
5. User clicks Start Fetch.
6. System creates fetch job.
7. Backend calls existing FetchService.
8. System stores new reviews and skips duplicates.
9. User sees job result.

### Flow 3: Review data

1. User opens Reviews page.
2. User filters by location/date/rating.
3. User opens review detail.
4. User checks raw review and analysis result.

### Flow 4: Analyze reviews

1. User opens Analysis page.
2. User selects location or unprocessed reviews.
3. User clicks Run Analysis.
4. System runs Gemini/mock analysis.
5. System saves sentiment, category, urgency, and recommendation.

### Flow 5: Read dashboard insight

1. User opens Dashboard.
2. User selects date range and location.
3. User sees rating, sentiment, trend, category, and urgency.
4. User opens Insights for recommended actions.

### Flow 6: Export report

1. User opens Reports page.
2. User selects location and date range.
3. User selects export type.
4. System generates file.
5. User downloads CSV/JSON/report.

---

## 16. MVP Implementation Roadmap

### Phase 0 - Product specification

Goal:

- Finalize product direction and technical plan.

Deliverables:

- `product.md`
- web architecture decision
- page list
- API draft
- migration plan from terminal to web

### Phase 1 - API wrapper over existing core

Goal:

- Expose current Python service layer via HTTP API.

Deliverables:

- FastAPI app
- health check endpoint
- locations API
- reviews API
- fetch logs API
- settings API

### Phase 2 - Next.js web shell

Goal:

- Build clean modern web UI foundation.

Deliverables:

- Next.js app
- sidebar layout
- dashboard route
- locations route
- reviews route
- fetch jobs route
- analysis route
- settings route
- shared components

### Phase 3 - Location, reviews, and fetch UI

Goal:

- Move terminal features into web.

Deliverables:

- manage locations from web
- run fetch from web
- view fetch logs
- view reviews
- filter reviews

### Phase 4 - AI analysis and insight dashboard

Goal:

- Make product valuable beyond raw scraping.

Deliverables:

- run analysis from web
- show sentiment/category/urgency
- dashboard charts
- insight cards
- recommendation list

### Phase 5 - Reports and export

Goal:

- Make data usable by client stakeholders.

Deliverables:

- CSV export
- JSON export
- basic report generation
- export history

### Phase 6 - Cloud readiness

Goal:

- Prepare for deployable product.

Deliverables:

- Supabase Postgres compatibility
- container-ready backend
- worker process design
- env separation
- auth plan
- storage plan

---

## 17. Product Metrics

MVP success metrics:

- number of active locations
- number of reviews fetched
- fetch success rate
- duplicate rate
- analysis coverage percentage
- number of critical reviews detected
- time from fetch to insight
- number of exports generated
- number of actionable recommendations produced

Future business metrics:

- monthly active client teams
- branch manager engagement
- report usage
- action completion rate
- reduction in repeated complaint category
- improvement in average rating
- reduced response time to critical reviews

---

## 18. Risks

### Scraping risk

Selenium scraping can be brittle and has platform policy risk. It should be treated as internal/controlled mode until product/legal decision is clear.

Mitigation:

- keep source abstraction,
- support official API/provider alternatives,
- avoid aggressive scraping,
- keep fetch manual/on-demand for MVP,
- maintain fetch logs and metadata.

### Selector breakage

Google Maps UI can change.

Mitigation:

- centralize selectors,
- log extraction failures,
- keep sample test pages if possible,
- keep manual verification flow.

### AI quality risk

AI output may be inconsistent.

Mitigation:

- use versioned prompts,
- save prompt version,
- allow re-analysis,
- expose confidence/metadata later,
- keep category taxonomy fixed.

### Data privacy risk

Reviews may contain personal health information.

Mitigation:

- restrict access,
- avoid exposing raw payload broadly,
- redact where needed in future,
- separate client data by organization when multi-tenant.

### Cost risk

AI analysis and scraping infra can cost money.

Mitigation:

- batch analysis,
- cache analysis result,
- only analyze new reviews,
- track analysis usage.

---

## 19. Open Product Questions

Questions to decide before production:

1. Is MVP for one hospital group only, or already multi-client?
2. Should web MVP require login from day one?
3. Does "real-time" mean user-triggered on-demand, or scheduled every X hours?
4. Will production source be Selenium, Google Business Profile API, third-party provider, or hybrid?
5. Who owns Google Business Profile access for each hospital?
6. Does client need downloadable executive report?
7. Do users need to assign/follow up recommended actions?
8. Should AI recommendation be per review only, or also per branch/category?

Recommended MVP answers:

1. Start with one organization / one client group.
2. Local MVP can skip auth; cloud MVP should add auth.
3. Start with on-demand fetch.
4. Keep source abstraction; Selenium for internal POC, official/provider path for production.
5. Store source metadata per location.
6. CSV/JSON first, PDF later.
7. Action tracking later.
8. Per review and dashboard-level summary first.

---

## 20. Final MVP Direction

Build the product as a web app, but keep the Python engine.

Recommended shape:

```text
apps/web       -> Next.js frontend
apps/api       -> FastAPI backend
app/           -> existing Hermina core engine
alembic/       -> database migrations
exports/       -> local generated files
```

Short version:

- Frontend: Next.js
- Backend: FastAPI
- Core logic: existing Python services
- Database: PostgreSQL local, Supabase Postgres ready
- Scraping: existing Selenium mode behind controlled API
- AI: Gemini/mock behind AnalysisService
- UI: clean hospital intelligence dashboard with sidebar, filters, charts, tables, and report exports

This path keeps the current working system alive while turning it into a product that can later be shipped.

