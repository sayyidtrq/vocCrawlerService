# Website Design - Voice of Customer V2

Tanggal draft: 2026-07-02

Dokumen ini merancang pengembangan UI/UX berdasarkan frontend existing di `hermina-crawler-fe`. Tujuannya menjaga gaya desain yang sudah terbentuk, sambil menambahkan kebutuhan V2: profile management, auth, competitor analysis, dan map/heatmap.

## 1. Observasi Existing Design

Frontend existing adalah dashboard operasional berbasis Next.js.

Karakter utama:

- sidebar kiri gelap,
- workspace terang,
- panel/card semi-transparan,
- table-heavy operational UI,
- badge untuk status/sentiment/urgency,
- lucide-react icons,
- warna aksen sage, blue, green, amber, red, purple,
- page header konsisten,
- section header konsisten,
- DataTable reusable,
- responsive layout.

Navigation existing:

- Dashboard
- Locations
- Fetch Jobs
- Reviews
- Analysis
- Insights
- Reports
- Settings

Komponen reusable existing:

- `AppShell`
- `PageHeader`
- `SectionHeader`
- `Badge`
- `EmptyState`
- `BackendWarning`
- `ActionMessagePanel`
- `DataTable`
- `PlaceholderPage`

## 2. Design Direction V2

V2 tetap memakai gaya operational SaaS, bukan landing page. Product ini dipakai untuk kerja harian agent, analyst, supervisor, dan admin, sehingga UI harus:

- cepat discan,
- padat tapi tidak sesak,
- kuat di tabel dan filter,
- jelas untuk status operational,
- minim dekorasi,
- fokus pada data, triage, dan action.

Prinsip visual:

- Pertahankan sidebar gelap.
- Pertahankan badge status.
- Gunakan panel seperlunya untuk kelompok fungsi.
- Hindari hero marketing.
- Untuk page baru, ikuti pola `PageHeader -> action/status panels -> main table/grid`.
- Untuk page data besar, gunakan `DataTable`.
- Untuk page map, map menjadi fokus utama, bukan kartu kecil.

## 3. Information Architecture V2

### 3.1 Public/Auth Area

Route:

- `/login`
- `/register`
- `/forgot-password`
- `/reset-password`

Layout:

- tanpa sidebar,
- centered auth panel,
- brand mark Hermina/VoC,
- form sederhana,
- status/error inline.

### 3.2 Protected App Area

Sidebar V2:

```text
Overview
  Dashboard
  Map Heatmap
  Insights

Operations
  Review Inbox
  Fetch/Crawl Jobs
  Action Tracker

Management
  Profiles
  Sources
  Locations
  Competitors
  Taxonomy

Analysis
  AI Analysis
  Competitor Analysis
  Reports

Admin
  Users
  Settings
```

Untuk MVP V2, sidebar bisa tetap flat agar cepat:

- Dashboard
- Review Inbox
- Locations
- Sources
- Fetch Jobs
- Analysis
- Competitor
- Map
- Insights
- Reports
- Profiles
- Settings

## 4. Page Design V2

### 4.1 Login Page

Tujuan:

- user masuk ke aplikasi.

Komponen:

- brand block,
- email input,
- password input,
- login button,
- link forgot password,
- link register jika self-service aktif,
- error panel.

State:

- idle,
- submitting,
- invalid credential,
- backend unavailable.

### 4.2 Register Page

Tujuan:

- create user dan profile awal jika self-service diaktifkan.

Komponen:

- organization name,
- organization type,
- name,
- email,
- password,
- confirm password,
- submit.

Catatan:

- Untuk enterprise/government, register bisa dibuat invite-only.

### 4.3 Dashboard Page V2

Existing dashboard dipertahankan, lalu ditambah:

- profile selector,
- date range selector,
- source filter,
- review quota meter,
- AI enabled status,
- competitor enabled status,
- map shortcut.

KPI:

- Total Reviews
- Average Rating
- AI Coverage
- Critical Signals
- Negative Sentiment
- Open Actions
- Active Sources
- Review Quota Used

Layout:

```text
PageHeader + filters
KPI grid
Risk/coverage panel
Top issues panel
Recent critical reviews
Branch/location ranking
```

### 4.4 Profile Management Page

Tujuan:

- mengelola company/government profile dan benefit/entitlement.

Komponen:

- profile table,
- create/edit profile form,
- benefit flags,
- quota usage,
- status active/inactive,
- industry/organization type.

Field:

- profile name,
- slug,
- organization type,
- industry type,
- status,
- `ai_enable_flag`,
- `total_enable_review`,
- `analyze_competitor_flag`,
- optional flags:
  - website crawler,
  - selenium,
  - map heatmap,
  - export.

UX:

- Use toggle for boolean flags.
- Use numeric input for quota.
- Use badge for active/inactive.
- Use usage meter for quota.

### 4.5 Sources Page

Tujuan:

- setup channel crawler/fetch per profile.

Komponen:

- source table,
- add/edit source drawer/form,
- source type segmented/select,
- base URL/external ID fields,
- crawl limit,
- schedule config,
- credential status,
- test source button.

Source type badges:

- Google Places
- Google Maps Selenium
- Website Firecrawl
- Website Selenium
- Play Store
- App Store
- CSV Import
- Survey
- CSAT

### 4.6 Locations Page V2

Existing page dipertahankan dan diperluas.

Tambahan:

- profile filter,
- region/wilayah,
- product,
- work unit,
- source,
- competitor flag,
- map coordinate validation,
- bulk import locations.

Table columns:

- location,
- profile,
- region,
- source,
- status,
- reviews,
- average rating,
- risk,
- target,
- actions.

### 4.7 Fetch/Crawl Jobs Page V2

Existing Fetch Jobs page menjadi Crawl Jobs.

Tambahan:

- source selector,
- job type selector,
- profile scope,
- connector health,
- queue status,
- retry job,
- cancel job,
- worker status,
- duration.

Job type:

- fetch reviews,
- crawl website,
- analyze pending,
- export report,
- competitor crawl.

Main interaction:

- Run single source/location.
- Run all active.
- Dry run.
- Retry failed.
- View metadata.

### 4.8 Review Inbox Page

Ini adalah evolusi dari Reviews Page.

Tujuan:

- agent/supervisor melakukan triage review.

Layout:

```text
Filter bar
Left: review table/list
Right: selected review detail panel
```

Filter:

- profile,
- source,
- location,
- product,
- wilayah,
- unit kerja,
- klasifikasi masalah,
- rating,
- sentiment,
- urgency,
- handling status,
- assigned agent,
- competitor/internal,
- keyword,
- date range.

Review detail panel:

- review text,
- reviewer,
- source,
- rating,
- date,
- AI summary,
- recommended action,
- taxonomy classification,
- safety/viral flags,
- internal notes,
- assigned owner,
- handling status,
- create action item.

### 4.9 Analysis Page V2

Existing page dipertahankan dan diperluas.

Tambahan:

- profile filter,
- AI entitlement status,
- analysis quota,
- model/provider status,
- failed analysis table,
- confidence distribution,
- taxonomy coverage.

Action:

- analyze pending,
- rerun by profile,
- rerun by location,
- rerun by source,
- rerun failed,
- export analysis result.

### 4.10 Competitor Analysis Page

Tujuan:

- membandingkan performa review organisasi dengan competitor.

Komponen:

- competitor selector,
- date range,
- source selector,
- benchmark KPI,
- comparison table,
- sentiment comparison,
- issue comparison,
- top strengths,
- top weaknesses,
- competitor review feed.

KPI:

- own average rating,
- competitor average rating,
- review volume gap,
- negative sentiment gap,
- critical issue gap,
- top issue overlap.

Layout:

```text
PageHeader + filters
Comparison KPI strip
Own vs competitor chart/grid
Top issue comparison
Competitor reviews table
Recommended strategy panel
```

### 4.11 Map / Heatmap Page

Tujuan:

- menampilkan titik lokasi dengan jumlah review dan summary rating.

Layout:

```text
Full-width filter bar
Large map canvas
Right/Bottom summary panel
```

Map elements:

- marker per location,
- cluster marker untuk area padat,
- marker color:
  - green: rating bagus/risk rendah,
  - amber: watch,
  - red: critical/high negative,
- marker size berdasarkan total review,
- heat layer berdasarkan negative/critical density.

Popup marker:

- location name,
- profile,
- total review,
- average rating,
- negative count,
- critical count,
- top issue,
- latest fetch,
- link to Review Inbox filtered by location.

Filter:

- profile,
- date range,
- source,
- sentiment,
- rating,
- competitor/internal,
- issue category.

Recommended library:

- MVP: Leaflet + OpenStreetMap.
- Later: Mapbox/Google Maps jika butuh enterprise style atau geospatial features lebih kuat.

### 4.12 Action Tracker Page

Tujuan:

- mengubah insight menjadi pekerjaan yang bisa ditindaklanjuti.

Komponen:

- action table,
- status board,
- priority filter,
- owner filter,
- due date,
- linked review,
- resolution note.

Status:

- open,
- assigned,
- in progress,
- waiting,
- resolved,
- closed.

### 4.13 Reports Page V2

Existing route placeholder diimplementasikan.

Komponen:

- report type selector,
- profile selector,
- location/source/date filter,
- export format,
- generate button,
- export history table.

Report type:

- executive summary,
- raw reviews,
- analysis summary,
- location report,
- competitor report,
- action tracker report.

### 4.14 Taxonomy Page

Tujuan:

- admin/analyst mengelola klasifikasi bisnis.

Tabs:

- Product
- Wilayah
- Unit Kerja
- Klasifikasi Masalah
- Klasifikasi Layanan
- Keyword Rules

UI:

- table + inline action,
- create/edit form,
- active/inactive toggle,
- owner mapping.

### 4.15 Settings Page V2

Existing placeholder diimplementasikan.

Section:

- runtime status,
- database check,
- AI provider status,
- Firecrawl status,
- Selenium config,
- Google API status,
- worker status,
- security settings,
- retention settings.

## 5. Component Additions

Komponen baru yang disarankan:

- `ProfileSelector`
- `DateRangeFilter`
- `SourceBadge`
- `QuotaMeter`
- `FeatureFlagToggle`
- `ReviewDetailPanel`
- `TaxonomySelect`
- `StatusTimeline`
- `ActionDrawer`
- `MapCanvas`
- `MetricCard`
- `ComparisonMetric`
- `ConnectorHealthBadge`
- `JobStatusBadge`
- `UsageMeter`

## 6. UI State Requirements

Setiap page perlu state:

- loading,
- empty,
- error backend,
- forbidden/feature disabled,
- quota exceeded,
- action running,
- success response,
- failed response.

Khusus entitlement:

- Jika AI disabled, tampilkan disabled panel dan hide run analysis action.
- Jika competitor disabled, tampilkan read-only blocked state.
- Jika quota habis, disable fetch/analyze sesuai policy.

## 7. Visual Rules

Gunakan pola existing:

- `PageHeader` untuk semua route utama.
- `SectionHeader` untuk panel.
- `Badge` untuk status.
- `DataTable` untuk list besar.
- `lucide-react` untuk icon action.
- Button icon untuk edit/delete/refresh/run.

Tambahan visual:

- map page boleh full canvas dan lebih luas dari panel biasa,
- competitor page bisa memakai comparison cards,
- profile page perlu usage meter,
- source page perlu connector health indicators.

## 8. Responsive Behavior

Desktop:

- sidebar fixed,
- table min width dengan horizontal scroll,
- detail panel side-by-side,
- map full width.

Tablet:

- sidebar collapses/top grid seperti existing breakpoint,
- filters stack,
- detail panel turun ke bawah.

Mobile:

- single column,
- tables horizontal scroll,
- map tetap tinggi minimal 520px,
- action buttons wrap.

## 9. MVP V2 Frontend Prioritas

Urutan implementasi frontend:

1. Auth pages.
2. Profile Management.
3. Protected route/app session.
4. Extend sidebar navigation.
5. Sources Page.
6. Review Inbox enhancement.
7. Map/Heatmap Page.
8. Competitor Analysis Page.
9. Reports Page implementation.
10. Taxonomy Page.
11. Action Tracker Page.

## 10. Design Acceptance Criteria

Sebuah page dianggap siap jika:

- connected ke backend real atau kontrak API jelas,
- memiliki loading/error/empty state,
- responsive untuk desktop dan mobile,
- tidak ada text overflow di button/table utama,
- action penting memakai icon,
- filter bisa discan,
- status memakai badge konsisten,
- tidak membuat gaya visual baru yang bertabrakan dengan existing app.

