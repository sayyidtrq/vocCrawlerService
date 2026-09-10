# Review System - Implementation Plan

Dokumen ini adalah lanjutan teknis dari `product.md`. Fokusnya bukan lagi ide product, tapi langkah implementasi supaya terminal MVP yang sudah jalan bisa berevolusi menjadi web product yang scalable.

Status awal:

- Core terminal app sudah berjalan via `python main.py`.
- Business logic sudah modular di folder `app/services`.
- Database sudah PostgreSQL dengan SQLAlchemy + Alembic.
- Review source sudah punya abstraction layer.
- Selenium mode sudah ada sebagai internal scraping source.
- Gemini/mock analysis sudah ada.
- Supabase akan disiapkan sebagai cloud-ready target, tapi local `.env` tetap menjadi default untuk sekarang.

Catatan MCP Supabase:

- User sudah connect MCP Supabase.
- Pada sesi ini tool callable Supabase belum muncul di daftar tools yang bisa dipanggil.
- Karena project Supabase masih kosong, plan ini dibuat Supabase-ready tanpa melakukan mutation ke project Supabase.
- Saat tool Supabase MCP sudah visible, langkah pertama adalah inspect project/schema, lalu apply migration secara terkontrol.

---

## 1. North Star Architecture

Recommended architecture:

```text
apps/web
  Next.js frontend
  Sidebar dashboard
  Tables, filters, charts, report pages

apps/api
  FastAPI backend
  Thin HTTP wrapper over existing Python services
  API schemas, auth boundary, job endpoints

app
  Existing Hermina core engine
  Services, integrations, DB models, terminal menu

alembic
  Existing database migrations

exports
  Local export output
```

Key principle:

> Jangan rewrite core logic. Bungkus service yang sudah ada menjadi API, lalu bangun UI di atas API itu.

---

## 2. Backend Decision

### Recommendation: FastAPI

Backend MVP sebaiknya memakai FastAPI.

Alasan:

- Existing code sudah Python.
- Existing ORM sudah SQLAlchemy, bukan Django ORM.
- Existing migration sudah Alembic, bukan Django migration.
- FastAPI cocok untuk API-first architecture.
- Scraping, analysis, export, dan fetch jobs cocok dibungkus sebagai service endpoints.
- Lebih ringan daripada migrasi ke Django.
- Lebih gampang dipisah menjadi API server + worker process.

### Why not Django first?

Django bagus kalau kita butuh:

- built-in admin,
- monolith CRUD yang besar,
- Django ORM sebagai pusat data model,
- permission/admin workflow kompleks dari hari pertama.

Tapi untuk kondisi repo sekarang, Django akan memaksa banyak adaptasi:

- SQLAlchemy -> Django ORM atau double ORM,
- Alembic -> Django migration,
- service layer perlu banyak glue,
- terminal app bisa ikut kena refactor besar.

Jadi senior judgement untuk MVP:

> Pakai FastAPI dulu. Django bisa dipertimbangkan nanti kalau product berubah menjadi admin-heavy monolith.

---

## 3. Repo Migration Strategy

### Phase A - Keep terminal app stable

Jangan sentuh entrypoint terminal:

```text
main.py
app/terminal/*
```

Terminal tetap harus jalan:

```bash
python main.py
```

### Phase B - Add API without moving core

Tambah folder:

```text
apps/api
  main.py
  requirements.txt
  app_api/
    __init__.py
    dependencies.py
    errors.py
    schemas/
    routers/
```

API akan import core dari root `app`.

Example:

```python
from app.services.location_service import LocationService
```

Ini menjaga `app/` sebagai core engine bersama untuk terminal dan web.

### Phase C - Add frontend

Tambah folder:

```text
apps/web
  app/
  components/
  lib/
  hooks/
  package.json
  next.config.ts
```

Frontend hanya bicara ke FastAPI, bukan langsung ke database untuk MVP local.

### Phase D - Worker later

Untuk MVP awal, API boleh menjalankan fetch/analyze secara synchronous dulu jika target kecil dan internal.

Tapi design endpoint harus siap dipindahkan ke worker:

```text
POST /api/fetch-jobs
  -> create job
  -> return job id
  -> worker runs scraping
  -> frontend polls job status
```

---

## 4. Backend API Structure

### Folder layout

```text
apps/api/
  main.py
  requirements.txt
  app_api/
    dependencies.py
    errors.py
    schemas/
      locations.py
      reviews.py
      fetch_jobs.py
      analysis.py
      dashboard.py
      exports.py
      settings.py
    routers/
      health.py
      locations.py
      reviews.py
      fetch_jobs.py
      analysis.py
      dashboard.py
      exports.py
      settings.py
```

### API dependencies

`dependencies.py` should provide:

- settings dependency,
- optional auth dependency later,
- pagination parser,
- service factory helpers.

For MVP, services can instantiate themselves because they already use `get_session_factory()`.

### Error handling

Convert service errors:

- `ValueError` -> HTTP 400 / 404 depending context
- unexpected exception -> HTTP 500
- validation error -> HTTP 422

Add consistent response shape:

```json
{
  "error": {
    "code": "location_not_found",
    "message": "Location not found."
  }
}
```

---

## 5. API Contract Draft

### Health

```http
GET /api/health
```

Response:

```json
{
  "status": "ok",
  "app": "Review System",
  "env": "local"
}
```

### Locations

```http
GET /api/locations
GET /api/locations?active_only=true
POST /api/locations
GET /api/locations/{location_id}
PATCH /api/locations/{location_id}
POST /api/locations/{location_id}/toggle-active
DELETE /api/locations/{location_id}
```

Create body:

```json
{
  "hospital_name": "Hermina",
  "branch_name": "Hermina Bekasi",
  "city": "Bekasi",
  "address": "Jl. Kemakmuran...",
  "latitude": -6.2416574,
  "longitude": 106.994774,
  "source": "selenium",
  "external_place_id": "ChIJ...",
  "google_maps_url": "https://maps.google.com/...",
  "google_reviews_url": "https://www.google.com/maps/place/...",
  "target_review_count": 100,
  "is_active": true
}
```

### Fetch jobs

MVP endpoint:

```http
POST /api/fetch-jobs
```

Body:

```json
{
  "location_id": 4,
  "source": "selenium",
  "target_review_count": 100,
  "dry_run": false
}
```

Response:

```json
{
  "location_id": 4,
  "location_name": "Hermina Bekasi",
  "source": "selenium_google_maps",
  "status": "success",
  "target_review_count": 100,
  "total_fetched": 100,
  "total_inserted": 33,
  "total_duplicate": 67,
  "total_failed": 0,
  "error_message": null,
  "metadata": {}
}
```

Other endpoints:

```http
GET /api/fetch-logs
GET /api/fetch-logs/latest
GET /api/fetch-logs?location_id=4
GET /api/fetch-logs?failed_only=true
```

### Reviews

```http
GET /api/reviews
GET /api/reviews/{review_id}
```

Supported query params:

```text
page
page_size
location_id
rating
sentiment
keyword
latest_first
```

Recommended next filters to add:

```text
source
issue_category
urgency
date_from
date_to
analyzed
is_patient_safety_issue
is_potential_viral
```

### Analysis

```http
POST /api/analysis/pending
POST /api/analysis/location/{location_id}
POST /api/analysis/reviews/{review_id}/rerun
```

For MVP, these can call:

- `AnalysisService.analyze_pending`
- `AnalysisService.rerun_location`
- `AnalysisService.rerun_review`

### Dashboard

```http
GET /api/dashboard/overview
GET /api/dashboard/locations/{location_id}
GET /api/dashboard/critical-issues
GET /api/dashboard/negative-reviews
```

Initial implementation can wrap:

- `SummaryService.overall_summary`
- `SummaryService.location_summary`
- `SummaryService.critical_issues`
- `SummaryService.negative_reviews`

### Exports

```http
POST /api/exports/reviews/all.csv
POST /api/exports/reviews/location/{location_id}.csv
POST /api/exports/analysis-summary.csv
POST /api/exports/raw-reviews.json
```

MVP can return:

```json
{
  "status": "success",
  "path": "exports/reviews_all_20260624_231000.csv"
}
```

Future cloud should return signed URL or Supabase Storage path.

### Settings

```http
GET /api/settings
```

Do not return raw secrets.

Good response:

```json
{
  "app_env": "local",
  "review_source_mode": "selenium",
  "gemini_mode": "real",
  "fetch_limit_per_location": 50,
  "selenium_default_target_reviews": 100,
  "selenium_max_target_reviews": 300,
  "analysis_batch_size": 20,
  "prompt_version": "v1",
  "google_maps_api_key_configured": true,
  "gemini_api_key_configured": true
}
```

---

## 6. Frontend Implementation Plan

### Stack

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui style component system
- Recharts for charts
- TanStack Table for review/fetch tables
- React Hook Form + Zod for forms

### Frontend folder layout

```text
apps/web/
  app/
    layout.tsx
    page.tsx
    dashboard/page.tsx
    locations/page.tsx
    fetch-jobs/page.tsx
    reviews/page.tsx
    analysis/page.tsx
    insights/page.tsx
    reports/page.tsx
    settings/page.tsx
  components/
    app-sidebar.tsx
    topbar.tsx
    data-table.tsx
    metric-card.tsx
    charts/
    forms/
  lib/
    api-client.ts
    types.ts
    formatters.ts
```

### Page priority

Build in this order:

1. App shell + sidebar
2. Dashboard overview
3. Locations CRUD
4. Fetch jobs + logs
5. Reviews table + filters
6. Analysis actions
7. Insights page
8. Exports/reports page
9. Settings page

### UI direction

Visual style:

- clean enterprise SaaS,
- hospital/healthcare professional feel,
- white/neutral background,
- blue/emerald accents,
- compact data cards,
- clear severity badges,
- responsive but desktop-first.

Badge conventions:

- positive: green
- neutral/mixed: slate/amber
- negative: red
- low: slate
- medium: amber
- high: orange
- critical: red
- patient safety: red outline
- potential viral: purple outline

---

## 7. Database Plan

### Keep existing tables first

Existing tables already useful:

- `locations`
- `reviews`
- `review_analysis`
- `fetch_logs`

MVP web can launch with these tables.

### Add later: `fetch_jobs`

Current `fetch_logs` works as historical log.

For scalable web jobs, add `fetch_jobs` later:

```sql
create table fetch_jobs (
  id bigserial primary key,
  location_id bigint not null references locations(id) on delete cascade,
  source text not null,
  status text not null default 'queued',
  requested_target_count integer,
  total_fetched integer not null default 0,
  total_inserted integer not null default 0,
  total_duplicate integer not null default 0,
  total_failed integer not null default 0,
  error_message text,
  metadata jsonb not null default '{}'::jsonb,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now()
);
```

Initial statuses:

- `queued`
- `running`
- `success`
- `partial_success`
- `failed`
- `dry_run`

### Add later: organization/user tables

For future SaaS/multi-client:

- `organizations`
- `profiles`
- `organization_members`

Do not force multi-tenancy into MVP if it slows delivery.

---

## 8. Supabase Cloud Readiness

### Recommended Supabase usage

Use Supabase for:

- Postgres database,
- Auth later,
- Storage later,
- dashboard/admin inspection.

Do not use Supabase for:

- Selenium runtime,
- browser automation,
- heavy scraping jobs.

### Production shape with Supabase

```text
Next.js frontend
  hosted on Vercel/other

FastAPI backend
  hosted on container/server

Worker
  hosted on container/server with Chrome/Selenium dependencies

Supabase
  Postgres
  Auth
  Storage
```

### RLS principle

If frontend directly accesses Supabase tables:

- enable RLS on all exposed tables,
- create policies by organization/user ownership,
- never rely only on `TO authenticated`,
- never use user-editable metadata for authorization.

For MVP local:

- frontend calls backend only,
- backend connects to Postgres,
- RLS can be introduced when cloud auth begins.

### Secrets

Never expose these in frontend:

- `DATABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GEMINI_API_KEY`
- `GOOGLE_MAPS_API_KEY`

Allowed frontend env:

- `NEXT_PUBLIC_API_BASE_URL`
- future `NEXT_PUBLIC_SUPABASE_URL`
- future Supabase publishable/anon key if using Supabase auth client

---

## 9. Worker Strategy

### MVP local synchronous mode

At first:

```text
POST /api/fetch-jobs
  -> run FetchService/SeleniumFetchService
  -> return result
```

This is acceptable for internal local MVP.

Downside:

- request can take long,
- browser automation can block API worker,
- user may need to wait.

### Better MVP+ mode

Add simple background job:

```text
POST /api/fetch-jobs
  -> create job row
  -> start background task
  -> return job id

GET /api/fetch-jobs/{id}
  -> poll job status
```

### Scalable mode

Use queue:

- Redis + RQ, Celery, or Dramatiq.

Recommended simple pick:

- RQ if we want minimal setup.
- Celery if we expect complex scheduled/periodic jobs later.

For this product, Celery is probably better long-term, but RQ is faster for MVP.

---

## 10. Implementation Order

### Step 1 - Add FastAPI API package

Install backend deps:

```text
fastapi
uvicorn[standard]
pydantic
python-multipart
```

Keep existing dependencies.

Add:

```text
apps/api/main.py
apps/api/app_api/routers/health.py
```

Acceptance:

```bash
python -m uvicorn apps.api.main:app --reload
```

`GET /api/health` returns ok.

### Step 2 - Locations API

Wrap `LocationService`.

Acceptance:

- list locations works,
- create Hermina location works,
- update location works,
- toggle active works.

### Step 3 - Reviews + dashboard read APIs

Wrap:

- `ReviewService`
- `SummaryService`

Acceptance:

- web can load dashboard numbers,
- web can list reviews with pagination,
- review detail works.

### Step 4 - Fetch endpoints

Wrap:

- `FetchService`
- `SeleniumFetchService`
- `FetchLogService`

Acceptance:

- run mock fetch from API,
- run selenium fetch from API in local controlled environment,
- fetch logs visible.

### Step 5 - Analysis endpoints

Wrap:

- `AnalysisService`

Acceptance:

- analyze pending reviews,
- rerun one review,
- rerun location.

### Step 6 - Export endpoints

Wrap:

- `ExportService`

Acceptance:

- CSV export creates file,
- JSON export creates file,
- response masks absolute local path if needed.

### Step 7 - Next.js shell

Build:

- sidebar,
- layout,
- API client,
- dashboard route,
- empty/loading/error states.

### Step 8 - Feature pages

Build in order:

1. Locations
2. Reviews
3. Fetch Jobs
4. Analysis
5. Dashboard charts
6. Insights
7. Reports
8. Settings

---

## 11. Local Development Commands

Potential commands after implementation:

Terminal MVP:

```bash
python main.py
```

API:

```bash
python -m uvicorn apps.api.main:app --reload --port 8000
```

Web:

```bash
cd apps/web
npm run dev
```

Database migration:

```bash
alembic upgrade head
```

Tests:

```bash
pytest
```

---

## 12. Environment Files

### Root `.env`

Keep current Python/backend env here:

```text
APP_ENV=local
APP_NAME=Review System
DATABASE_URL=postgresql://...
REVIEW_SOURCE_MODE=selenium
GEMINI_MODE=real
GOOGLE_MAPS_API_KEY=...
GEMINI_API_KEY=...
```

### `apps/web/.env.local`

Frontend env:

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Future:

```text
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
```

### Cloud backend env

Future:

```text
DATABASE_URL=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
GEMINI_API_KEY=
GOOGLE_MAPS_API_KEY=
SELENIUM_USER_DATA_DIR=
```

---

## 13. Verification Plan

After each phase:

### Backend checks

- import check,
- API health check,
- targeted endpoint tests,
- `pytest` for existing terminal/core behavior,
- ensure `python main.py` still starts.

### Frontend checks

- app compiles,
- dashboard loads from API,
- table pagination works,
- form validation works,
- error states visible.

### Database checks

- `alembic upgrade head`
- no duplicate review insert regression
- fetch logs still written
- analysis rows still linked to reviews

### Supabase checks later

When MCP/CLI is available:

- inspect project,
- apply schema to empty Supabase project,
- run advisors,
- verify tables,
- verify RLS plan before exposing anything to frontend.

---

## 14. Immediate Next Build Task

Recommended next task:

> Implement Phase 1: FastAPI API wrapper with health, locations, reviews, dashboard summary, and fetch logs read-only endpoints.

Why read-only first:

- fastest way to prove web/API bridge,
- low risk to existing terminal app,
- easy to test,
- creates frontend foundation before dangerous long-running Selenium actions.

After read-only API works:

> Add controlled fetch/analyze action endpoints.

This avoids turning Selenium into a web-triggered footgun too early.

