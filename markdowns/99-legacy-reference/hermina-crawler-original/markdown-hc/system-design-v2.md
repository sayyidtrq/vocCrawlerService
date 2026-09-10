# System Design V2 - Voice of Customer Review Intelligence

Tanggal draft: 2026-07-02

Dokumen ini menerjemahkan kebutuhan stakeholder dan fitur tambahan menjadi rancangan sistem V2. V2 diposisikan sebagai pengembangan dari Review System menuju produk Voice of Customer yang dapat dipakai oleh company, government, dan organisasi multi-lokasi.

## 1. Visi Produk

V2 bertujuan menjadi platform Voice of Customer untuk mengumpulkan, menormalisasi, menganalisis, dan menindaklanjuti feedback publik maupun internal dari berbagai channel.

Sumber data yang ditargetkan:

- Google Review / Google Maps
- Google Places
- website publik perusahaan
- website layanan pemerintah
- Play Store
- App Store
- CSAT
- survey
- inbound omnichannel
- social media publik yang legal untuk diakses
- file import CSV/XLSX

Output utama:

- dashboard reputasi dan layanan,
- review inbox,
- AI classification,
- competitor analysis,
- heatmap lokasi,
- action insight untuk supervisor,
- laporan manajemen.

## 2. Objective Stakeholder

### 2.1 Objective Bisnis

- Membantu organisasi memahami kualitas layanan dan produk dari suara pelanggan.
- Menjawab pertanyaan supervisor: "apa yang harus diperbaiki?"
- Mengubah review menjadi insight perbaikan operasional.
- Menggabungkan channel publik dan internal dalam satu dashboard VoC.
- Menyediakan measurement per product, wilayah, unit kerja, klasifikasi masalah, dan layanan.

### 2.2 Objective Agent/Operations

- Agent tidak hanya menangani komunikasi langsung via chat/ticket, tetapi juga review publik.
- Review dari Google, app store, website, dan channel lain dapat menjadi case/inbox.
- Review negatif atau critical dapat dibuat menjadi action item.
- Agent/supervisor dapat melihat status tindak lanjut.

### 2.3 Objective Product V2

- Profile management untuk multi-company/multi-government.
- Auth/login/register.
- Feature entitlement per profile.
- Analyze competitor.
- Heatmap/map lokasi review dan summary rating.
- Connector website crawler berbasis Firecrawl.
- Connector Selenium sebagai fallback untuk web dinamis.
- Fondasi taxonomy VoC.

## 3. Prinsip Desain Sistem

1. Core existing tetap dipakai.
2. Scraper/crawler dipisah sebagai connector dan worker, bukan logic UI.
3. Onebox/VoC app hanya memanggil API/job, tidak menjalankan Selenium langsung dari request UI.
4. Semua source data masuk ke canonical review schema.
5. AI analysis harus versioned dan auditable.
6. Feature entitlement harus berbasis profile/subscription.
7. Long-running job harus masuk queue.
8. Auth dan multi-tenant harus disiapkan sebelum produk dipakai banyak organisasi.
9. Scraping harus legal, terkontrol, dan tidak melakukan bypass auth/CAPTCHA/token.

## 4. High-Level Architecture V2

```text
Web App / Onebox UI
  |
  | REST API
  v
API Server
  |
  | create jobs, read data, enforce auth/profile flags
  v
Core Domain Services
  |
  | enqueue long-running work
  v
Job Queue
  |
  v
Worker Layer
  |-- Google Places Connector
  |-- Google Business Profile Connector (future official)
  |-- Selenium Google Maps Connector
  |-- Firecrawl Website Connector
  |-- Play Store Connector
  |-- App Store Connector
  |-- Social/Public Web Connector
  |-- AI Analysis Worker
  |-- Export Worker
  |
  v
PostgreSQL
  |
  v
Dashboard / Reports / Map / Action Tracker
```

## 5. Existing Core Yang Dipakai Ulang

V2 tetap memakai modul existing:

- `LocationService`
- `FetchService`
- `SeleniumFetchService`
- `ReviewService`
- `AnalysisService`
- `SummaryService`
- `ExportService`
- `FetchLogService`
- `SettingsService`
- PostgreSQL schema existing
- FastAPI routes existing
- Next.js page structure existing

V2 menambahkan entity baru, API baru, dan page baru.

## 6. Modul V2

### 6.1 Authentication

Fitur:

- register,
- login,
- logout,
- forgot password,
- reset password,
- session management,
- protected route,
- role-based access.

Role awal:

- `super_admin`
- `org_admin`
- `manager`
- `agent`
- `analyst`
- `viewer`

Scope role:

- `super_admin`: manage semua profile dan feature entitlement.
- `org_admin`: manage profile sendiri, user, source, dan settings.
- `manager`: dashboard, insights, action tracker.
- `agent`: review inbox dan action handling.
- `analyst`: analysis, reports, taxonomy.
- `viewer`: read-only dashboard/report.

### 6.2 Profile Management

Profile adalah representasi organisasi/client.

Target pengguna:

- company,
- government,
- rumah sakit,
- unit layanan publik,
- brand/product owner.

Fitur:

- create profile,
- edit profile,
- activate/deactivate profile,
- set industry type,
- set organization type,
- set plan/benefit,
- set feature flags,
- set review quota,
- set competitor analysis permission.

Parameter benefit awal:

- `ai_enable_flag`
- `total_enable_review`
- `analyze_competitor_flag`

Tambahan yang disarankan:

- `website_crawler_enable_flag`
- `selenium_enable_flag`
- `map_heatmap_enable_flag`
- `export_enable_flag`
- `max_locations`
- `max_sources`
- `analysis_monthly_quota`
- `retention_days`

### 6.3 Source Management

Source management memisahkan konfigurasi channel dari location.

Source type:

- `google_places`
- `google_maps_selenium`
- `google_business_profile`
- `website_firecrawl`
- `website_selenium`
- `play_store`
- `app_store`
- `csat`
- `survey`
- `csv_import`
- `social_public_web`

Field source:

- profile id,
- source type,
- source name,
- base URL,
- external id,
- credential reference,
- active flag,
- schedule config,
- crawl limit,
- metadata JSON.

### 6.4 Location Management V2

Existing `locations` diperluas dengan profile ownership dan grouping.

Tambahan field:

- profile id,
- region id,
- area id,
- service unit id,
- product id,
- latitude,
- longitude,
- operational status,
- competitor flag.

Tujuan:

- mendukung heatmap,
- mendukung drilldown wilayah,
- mendukung comparison antar cabang,
- mendukung competitor location.

### 6.5 Review Inbox

Review Inbox adalah evolusi dari Reviews Page.

Fitur:

- semua review dalam satu inbox,
- filter by profile,
- filter by source,
- filter by product,
- filter by wilayah,
- filter by unit kerja,
- filter by klasifikasi masalah,
- filter by rating,
- filter by sentiment,
- filter by urgency,
- filter by status handling,
- assign to agent,
- internal note,
- mark as handled,
- create action item.

Status handling:

- `new`
- `triaged`
- `assigned`
- `in_progress`
- `resolved`
- `ignored`
- `archived`

### 6.6 AI Analysis V2

Existing AI analysis diperluas dari review-level classification menjadi VoC taxonomy.

Output tambahan:

- product classification,
- wilayah classification,
- unit kerja classification,
- klasifikasi masalah,
- klasifikasi layanan,
- root cause hypothesis,
- service recovery suggestion,
- escalation target,
- confidence score,
- competitor mention flag,
- pii/phi risk flag.

AI harus mengikuti `ai_enable_flag`. Jika profile tidak mengaktifkan AI, sistem hanya menyimpan review mentah dan summary non-AI.

### 6.7 Taxonomy Management

Taxonomy diperlukan agar AI output dan dashboard konsisten.

Entity taxonomy:

- product,
- wilayah/region,
- unit kerja,
- service type,
- issue category,
- severity,
- channel,
- keyword rule.

Fitur:

- CRUD taxonomy,
- mapping keyword ke taxonomy,
- mapping source/location ke wilayah,
- mapping issue ke unit kerja owner,
- enable/disable taxonomy value,
- review AI suggestion before apply.

### 6.8 Analyze Competitor

Fitur ini aktif jika `analyze_competitor_flag = true`.

Use case:

- membandingkan rating perusahaan dengan kompetitor,
- melihat jumlah review kompetitor,
- melihat top issue kompetitor,
- melihat sentiment comparison,
- melihat keyword yang sering muncul pada kompetitor,
- melihat location-level benchmark.

Data competitor:

- competitor profile,
- competitor locations,
- competitor source URLs,
- competitor reviews,
- competitor analysis result.

Important rule:

- competitor data hanya dari sumber publik yang boleh diakses,
- tidak melakukan bypass login/auth/CAPTCHA,
- tidak mengambil data personal berlebihan,
- data competitor diberi label jelas.

Dashboard competitor:

- brand rating comparison,
- review volume comparison,
- sentiment comparison,
- issue category comparison,
- location proximity comparison,
- top negative themes,
- top strengths/weaknesses.

### 6.9 Heatmap / Map

Heatmap menampilkan lokasi dengan jumlah review dan summary rating.

Fitur:

- map marker per location,
- marker size berdasarkan total review,
- marker color berdasarkan average rating atau risk score,
- popup summary:
  - location name,
  - total review,
  - average rating,
  - negative count,
  - critical count,
  - top issue,
  - latest fetch,
- filter by date range,
- filter by source,
- filter by profile,
- filter by competitor/internal,
- heat layer untuk density complaint.

Data requirement:

- latitude,
- longitude,
- total reviews,
- average rating,
- sentiment count,
- critical count,
- issue count,
- latest fetch.

Map library option:

- Leaflet untuk cepat dan open-source,
- Mapbox jika butuh style enterprise dan budget tersedia,
- Google Maps jika ingin konsisten dengan Google ecosystem tetapi perlu perhatikan billing.

Rekomendasi MVP: Leaflet + OpenStreetMap tiles untuk internal demo.

### 6.10 Website Crawler Dengan Firecrawl

Firecrawl digunakan untuk website publik yang tidak membutuhkan login.

Use case:

- crawl halaman product/service,
- crawl page complaint/testimonial jika publik,
- crawl berita/pengumuman,
- crawl review atau feedback publik yang ada di website,
- convert page ke markdown untuk AI extraction.

Alur:

```text
Source URL
  -> Firecrawl scrape/crawl
  -> normalized document
  -> extraction prompt
  -> canonical review/feedback item
  -> deduplication
  -> AI analysis
  -> dashboard
```

Field tambahan untuk website item:

- page URL,
- page title,
- author if exists,
- published date,
- extracted text,
- source snippet,
- crawl depth,
- crawl batch id.

### 6.11 Selenium Fallback

Selenium tetap dipakai untuk:

- Google Maps POC,
- website dynamic yang Firecrawl tidak bisa baca,
- source yang butuh klik/scroll tetapi tetap publik.

Rules:

- tidak bypass login,
- tidak bypass CAPTCHA,
- target count dibatasi,
- delay dan retry dikontrol,
- semua run masuk fetch log,
- source harus bisa dimatikan per profile.

### 6.12 Reports V2

Reports harus menjawab kebutuhan stakeholder.

Jenis report:

- executive summary,
- branch/location report,
- issue category report,
- competitor report,
- action tracker report,
- raw data export,
- AI insight export.

Format:

- CSV,
- JSON,
- PDF future,
- PPT future.

## 7. Data Model V2 Draft

### 7.1 profiles

```text
id
name
slug
organization_type
industry_type
status
ai_enable_flag
total_enable_review
analyze_competitor_flag
website_crawler_enable_flag
selenium_enable_flag
map_heatmap_enable_flag
export_enable_flag
max_locations
max_sources
analysis_monthly_quota
retention_days
created_at
updated_at
```

### 7.2 users

```text
id
profile_id
name
email
password_hash
role
status
last_login_at
created_at
updated_at
```

### 7.3 sources

```text
id
profile_id
source_type
name
base_url
external_id
credential_ref
is_active
schedule_config
crawl_limit
metadata_json
created_at
updated_at
```

### 7.4 regions

```text
id
profile_id
name
code
parent_region_id
created_at
updated_at
```

### 7.5 products

```text
id
profile_id
name
code
description
is_active
created_at
updated_at
```

### 7.6 work_units

```text
id
profile_id
name
code
owner_user_id
is_active
created_at
updated_at
```

### 7.7 issue_taxonomies

```text
id
profile_id
name
code
description
default_urgency
owner_work_unit_id
is_active
created_at
updated_at
```

### 7.8 Extend locations

Tambahan ke existing `locations`:

```text
profile_id
source_id
region_id
product_id
work_unit_id
is_competitor
competitor_name
```

### 7.9 Extend reviews

Tambahan ke existing `reviews`:

```text
profile_id
source_id
product_id
region_id
work_unit_id
issue_taxonomy_id
handling_status
assigned_user_id
is_competitor
competitor_name
source_url
published_at
external_thread_id
```

### 7.10 Extend review_analysis

Tambahan ke existing `review_analysis`:

```text
product_code
region_code
work_unit_code
service_classification
issue_classification
root_cause_hypothesis
escalation_target
confidence_score
pii_phi_risk_flag
analysis_version
```

### 7.11 action_items

```text
id
profile_id
review_id
title
description
owner_work_unit_id
assigned_user_id
status
priority
due_date
resolution_note
created_at
updated_at
closed_at
```

### 7.12 competitor_profiles

```text
id
profile_id
name
industry_type
notes
is_active
created_at
updated_at
```

### 7.13 crawl_jobs

```text
id
profile_id
source_id
location_id
job_type
status
requested_by
requested_target_count
fetched_count
inserted_count
duplicate_count
failed_count
error_message
metadata_json
started_at
finished_at
created_at
```

## 8. API V2 Draft

### 8.1 Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`

### 8.2 Profiles

- `GET /api/profiles`
- `POST /api/profiles`
- `GET /api/profiles/{profile_id}`
- `PATCH /api/profiles/{profile_id}`
- `POST /api/profiles/{profile_id}/toggle-active`
- `GET /api/profiles/{profile_id}/usage`

### 8.3 Sources

- `GET /api/sources`
- `POST /api/sources`
- `GET /api/sources/{source_id}`
- `PATCH /api/sources/{source_id}`
- `DELETE /api/sources/{source_id}`
- `POST /api/sources/{source_id}/test`

### 8.4 Reviews

- `GET /api/reviews`
- `GET /api/reviews/{review_id}`
- `PATCH /api/reviews/{review_id}/handling`
- `POST /api/reviews/{review_id}/assign`
- `POST /api/reviews/{review_id}/notes`
- `POST /api/reviews/{review_id}/create-action`

### 8.5 Crawl Jobs

- `POST /api/crawl-jobs`
- `POST /api/crawl-jobs/all-active`
- `GET /api/crawl-jobs`
- `GET /api/crawl-jobs/{job_id}`
- `POST /api/crawl-jobs/{job_id}/retry`
- `POST /api/crawl-jobs/{job_id}/cancel`

### 8.6 Analysis

- `POST /api/analysis/pending`
- `POST /api/analysis/reviews/{review_id}/rerun`
- `POST /api/analysis/locations/{location_id}/rerun`
- `POST /api/analysis/competitors/run`
- `GET /api/analysis/coverage`

### 8.7 Competitor

- `GET /api/competitors`
- `POST /api/competitors`
- `PATCH /api/competitors/{competitor_id}`
- `DELETE /api/competitors/{competitor_id}`
- `GET /api/competitors/benchmark`
- `GET /api/competitors/{competitor_id}/reviews`

### 8.8 Map

- `GET /api/map/locations`
- `GET /api/map/heatmap`
- `GET /api/map/locations/{location_id}/summary`

### 8.9 Taxonomy

- `GET /api/taxonomies/products`
- `POST /api/taxonomies/products`
- `GET /api/taxonomies/work-units`
- `POST /api/taxonomies/work-units`
- `GET /api/taxonomies/issues`
- `POST /api/taxonomies/issues`
- `POST /api/taxonomies/auto-map`

## 9. Page V2

### 9.1 Public/Auth Pages

- Login
- Register
- Forgot Password
- Reset Password

### 9.2 Main Application Pages

- Dashboard
- Review Inbox
- Locations
- Sources
- Fetch/Crawl Jobs
- Analysis
- Insights
- Competitor Analysis
- Map/Heatmap
- Action Tracker
- Reports
- Profile Management
- Taxonomy Management
- User Management
- Settings

## 10. Business Rules Entitlement

### 10.1 AI Enable Flag

Jika `ai_enable_flag = false`:

- analysis button disabled,
- analysis worker tidak memproses profile tersebut,
- dashboard hanya menampilkan raw summary,
- upsell/notice dapat muncul untuk org admin.

### 10.2 Total Enable Review

`total_enable_review` adalah batas jumlah review aktif/tersimpan atau batas review yang dapat dianalisis, tergantung keputusan product.

Rekomendasi:

- gunakan sebagai monthly analysis/fetch quota untuk menghindari data deletion,
- tetap simpan review mentah jika legal/retention memperbolehkan,
- tampilkan usage meter di Profile Management.

### 10.3 Analyze Competitor Flag

Jika `analyze_competitor_flag = false`:

- page competitor hidden atau read-only,
- competitor source creation disabled,
- competitor analysis API menolak request.

## 11. Processing Flow V2

### 11.1 Review Fetch Flow

```text
User selects source/location
  -> API validates auth/profile entitlement
  -> API creates crawl_job
  -> Worker fetches data from connector
  -> Worker normalizes items
  -> Worker deduplicates by source hash
  -> Worker stores reviews
  -> Worker updates crawl_job/fetch_log
  -> If AI enabled, enqueue analysis
```

### 11.2 AI Analysis Flow

```text
Review inserted
  -> check profile.ai_enable_flag
  -> build prompt with taxonomy context
  -> call AI provider/local LLM
  -> validate schema
  -> store review_analysis
  -> auto update review taxonomy fields if confidence high
  -> generate recommended action
  -> create alert/action suggestion if critical
```

### 11.3 Competitor Analysis Flow

```text
Org admin adds competitor
  -> add competitor locations/sources
  -> run crawl job
  -> store competitor reviews with is_competitor=true
  -> analyze with same taxonomy
  -> compare own vs competitor
  -> render benchmark dashboard
```

### 11.4 Heatmap Flow

```text
Location has lat/lng
  -> reviews aggregated by location
  -> calculate average rating, review count, negative count, critical count
  -> API returns marker data
  -> frontend renders map marker and heat layer
```

## 12. Additional Stakeholder Requests To Propose

Recommended additional requests for stakeholder discussion:

1. Define primary users and permission model.
2. Define organization types: company, government, hospital, brand.
3. Define exact quota meaning for `total_enable_review`.
4. Define whether AI analysis should be per review only or also per summary period.
5. Define source priority: Google Maps, website, Play Store, App Store, CSAT, survey.
6. Define legal/compliance policy for scraping and public data.
7. Define whether competitor data may be stored long-term.
8. Define dashboard period default: 7 days, 30 days, quarter, custom.
9. Define action tracker SLA and owner unit.
10. Define export/report format needed by management.
11. Define whether Onebox should create ticket/conversation from review.
12. Define whether agent should be able to reply to review from system.
13. Define taxonomy master data owner.
14. Define map granularity: branch-level only or region/city clustering.
15. Define PII/PHI redaction requirement for healthcare/government use.

## 13. MVP V2 Scope Recommendation

### Phase 1 - Foundation

- Auth/login/register.
- Profile Management.
- Feature entitlement fields.
- Attach profile id to locations/reviews/fetch logs.
- Protect existing pages by auth.

### Phase 2 - Source Expansion

- Source Management page.
- Firecrawl website connector.
- Selenium website fallback abstraction.
- Crawl job entity.
- Queue/worker split for long-running jobs.

### Phase 3 - VoC Intelligence

- Extended taxonomy.
- AI classification V2.
- Review Inbox with handling status.
- Action Tracker.

### Phase 4 - Competitor And Map

- Competitor entity and sources.
- Analyze Competitor page.
- Map/Heatmap page.
- Benchmark dashboard.

### Phase 5 - Reporting And Governance

- Reports page implementation.
- Profile usage report.
- Audit log.
- Export history.
- PII/PHI redaction.

## 14. Technical Risks

### 14.1 Synchronous Job Risk

Existing fetch/analysis runs through API request. Selenium and AI can be slow. V2 needs queue/worker.

Mitigation:

- create `crawl_jobs`,
- return job id immediately,
- worker updates status,
- frontend polls job status.

### 14.2 Scraping Reliability Risk

Selenium selectors can break and Firecrawl can fail on heavily protected sites.

Mitigation:

- connector abstraction,
- per-source health status,
- fetch logs with raw error,
- retry policy,
- fallback connector.

### 14.3 Auth And Multi-Tenant Risk

Existing tables have no `profile_id`, so data separation is not yet enforced.

Mitigation:

- add profile id early,
- backfill default profile,
- enforce profile scope at service/API layer,
- add tests for tenant isolation.

### 14.4 AI Output Drift

Taxonomy output can be inconsistent.

Mitigation:

- schema validation,
- prompt versioning,
- confidence score,
- taxonomy mapping table,
- manual review for low-confidence items.

## 15. Success Metrics V2

Product metrics:

- active profiles,
- active sources,
- review volume per profile,
- AI analysis coverage,
- competitor analysis usage,
- map usage,
- export usage,
- action item completion rate.

Operational metrics:

- crawl success rate,
- duplicate rate,
- average fetch duration,
- analysis failure rate,
- cost per analyzed review,
- number of critical alerts.

Business outcome metrics:

- reduction in repeated complaint category,
- improved average rating,
- improved response time,
- action closure SLA,
- branch/unit improvement trend.

## 16. Recommended V2 Direction

V2 harus diperlakukan sebagai produk VoC multi-profile, bukan hanya crawler tambahan.

Urutan terbaik:

1. Tambahkan auth dan profile management.
2. Tambahkan entitlement/benefit flags.
3. Ubah crawler menjadi job-based worker.
4. Tambahkan source management.
5. Tambahkan Firecrawl connector.
6. Tambahkan taxonomy VoC.
7. Tambahkan competitor analysis.
8. Tambahkan map/heatmap.
9. Tambahkan action tracker dan reports.

