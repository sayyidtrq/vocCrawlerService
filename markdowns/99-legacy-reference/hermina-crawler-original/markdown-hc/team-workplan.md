# Rancangan Pembagian Kerja - VoC V2

Tanggal draft: 2026-07-02

Dokumen ini membagi pekerjaan V2 berdasarkan komposisi tim:

- 1 Solution Engineer + Developer: kamu
- 2 Frontend Developer
- 1 Backend + AI Developer

Tujuan pembagian ini adalah membuat pekerjaan paralel, jelas owner-nya, dan tetap aman secara arsitektur.

## 1. Role Dan Tanggung Jawab

### 1.1 Solution Engineer + Developer

Peran utama:

- menerjemahkan requirement stakeholder menjadi system design,
- menjaga scope MVP/V2,
- membuat API contract,
- menentukan data model,
- review desain dan implementasi,
- ikut develop bagian integrasi yang critical,
- menjadi bridge antara bisnis, frontend, backend, dan AI.

Tanggung jawab teknis:

- finalisasi `system-design-v2.md`,
- finalisasi API contract,
- finalisasi database migration plan,
- define taxonomy awal,
- review PR frontend/backend,
- implement spike/PoC untuk connector yang risk tinggi,
- validasi flow end-to-end.

### 1.2 Frontend Developer 1

Fokus:

- app shell,
- auth UI,
- profile management,
- source management,
- settings/admin surface.

Deliverable:

- login/register/forgot password page,
- protected route behavior,
- Profile Management page,
- Sources page,
- Settings V2 page,
- reusable components untuk feature flag, quota meter, source badge.

### 1.3 Frontend Developer 2

Fokus:

- operational review workflow,
- analytics/dashboard,
- map,
- competitor UI.

Deliverable:

- Review Inbox enhancement,
- Map/Heatmap page,
- Competitor Analysis page,
- Action Tracker page,
- Reports page,
- dashboard KPI enhancement.

### 1.4 Backend + AI Developer

Fokus:

- auth backend,
- profile/multi-tenant schema,
- source/crawler abstraction,
- Firecrawl connector,
- AI V2 classification,
- queue/job processing.

Deliverable:

- users/profile schema,
- auth API,
- profile/source API,
- entitlement middleware/service,
- crawl job API,
- Firecrawl connector,
- AI taxonomy output schema,
- analysis V2 service,
- map aggregation API,
- competitor API.

## 2. Workstream

### Workstream A - Product & Architecture

Owner: Solution Engineer

Output:

- existing-system.md
- system-design-v2.md
- website-design.md
- team-workplan.md
- API contract draft
- schema migration plan
- milestone plan

### Workstream B - Auth & Profile Foundation

Owner: Backend + AI Developer

Support:

- Frontend Developer 1
- Solution Engineer

Output:

- `profiles` table,
- `users` table,
- login/register API,
- session/JWT handling,
- profile entitlement service,
- profile-scoped data access,
- frontend auth pages,
- protected app shell.

### Workstream C - Source & Crawl Jobs

Owner: Backend + AI Developer

Support:

- Frontend Developer 1
- Solution Engineer

Output:

- `sources` table,
- `crawl_jobs` table,
- source CRUD API,
- crawl job API,
- Firecrawl connector,
- Selenium connector abstraction,
- job status/log metadata,
- Sources page,
- Crawl Jobs page enhancement.

### Workstream D - Review Inbox & Taxonomy

Owner:

- Backend + AI Developer for API/schema,
- Frontend Developer 2 for UI.

Support:

- Solution Engineer for taxonomy and stakeholder logic.

Output:

- taxonomy tables,
- review status/assignment fields,
- review inbox filters,
- review detail panel,
- taxonomy assignment,
- action item creation.

### Workstream E - AI V2

Owner: Backend + AI Developer

Support:

- Solution Engineer
- Frontend Developer 2

Output:

- prompt V2,
- schema V2,
- product/wilayah/unit kerja/klasifikasi output,
- confidence score,
- quota check with `ai_enable_flag`,
- AI coverage API,
- analysis UI enhancement.

### Workstream F - Competitor Analysis

Owner:

- Backend + AI Developer for competitor model/API,
- Frontend Developer 2 for UI.

Support:

- Solution Engineer for product logic and constraints.

Output:

- competitor profiles,
- competitor locations/sources,
- competitor crawl job,
- competitor reviews label,
- benchmark API,
- competitor analysis page.

### Workstream G - Map / Heatmap

Owner:

- Frontend Developer 2 for map UI,
- Backend + AI Developer for aggregation API.

Support:

- Solution Engineer.

Output:

- map aggregation endpoint,
- location marker payload,
- heatmap payload,
- map filters,
- marker popup,
- link to filtered Review Inbox.

### Workstream H - Reports & Settings

Owner:

- Frontend Developer 1 for Settings,
- Frontend Developer 2 for Reports,
- Backend + AI Developer for export history/API.

Output:

- reports page implementation,
- export history,
- profile usage report,
- settings runtime page,
- connector health status.

## 3. Milestone Plan

### Milestone 0 - Alignment

Durasi: 1-2 hari

Owner: Solution Engineer

Deliverable:

- review dokumen existing system,
- sepakati scope MVP V2,
- sepakati schema/API draft,
- sepakati UI navigation V2,
- tentukan definisi quota `total_enable_review`.

Exit criteria:

- tim setuju fitur Phase 1,
- data model dasar disetujui,
- backlog dibuat.

### Milestone 1 - Auth + Profile

Durasi: 1 minggu

Backend + AI:

- migration `profiles`,
- migration `users`,
- auth API,
- profile entitlement service,
- default profile backfill.

Frontend 1:

- login page,
- register page,
- protected route,
- profile management page.

Solution Engineer:

- API review,
- schema review,
- e2e smoke test.

Exit criteria:

- user bisa login,
- app protected,
- profile bisa dibuat,
- feature flags bisa disimpan,
- existing location/review bisa terhubung ke default profile.

### Milestone 2 - Sources + Crawl Job Foundation

Durasi: 1-2 minggu

Backend + AI:

- sources API,
- crawl jobs API,
- Firecrawl connector MVP,
- job status model,
- worker design minimal.

Frontend 1:

- Sources page,
- source create/edit,
- source test action,
- connector health indicator.

Frontend 2:

- Fetch Jobs menjadi Crawl Jobs,
- job detail status/log UI.

Solution Engineer:

- define source contract,
- test Firecrawl/Selenium flow,
- validate no auth bypass.

Exit criteria:

- source bisa dibuat,
- Firecrawl source bisa dry-run,
- crawl job tercatat,
- hasil crawl bisa masuk canonical review/feedback item.

### Milestone 3 - Review Inbox + Taxonomy

Durasi: 1-2 minggu

Backend + AI:

- taxonomy schema/API,
- review handling fields,
- assignment/status API.

Frontend 2:

- Review Inbox layout,
- review detail panel,
- status handling,
- assignment UI,
- taxonomy filters.

Frontend 1:

- Taxonomy Management page.

Solution Engineer:

- define taxonomy awal,
- validate stakeholder dimension:
  - Product,
  - Wilayah,
  - Unit Kerja,
  - Klasifikasi Masalah/Layanan.

Exit criteria:

- review bisa difilter berdasarkan taxonomy,
- status handling bisa diubah,
- review bisa dibuat action item.

### Milestone 4 - AI V2

Durasi: 1 minggu

Backend + AI:

- prompt V2,
- analysis schema V2,
- taxonomy-aware classification,
- confidence score,
- entitlement check,
- analysis quota usage.

Frontend 2:

- Analysis page enhancement,
- confidence and taxonomy result display.

Solution Engineer:

- review output AI,
- compare sample results,
- refine prompt.

Exit criteria:

- AI menghasilkan product/wilayah/unit kerja/klasifikasi,
- AI disabled profile tidak bisa menjalankan analysis,
- output tersimpan dan bisa difilter.

### Milestone 5 - Competitor + Map

Durasi: 1-2 minggu

Backend + AI:

- competitor schema/API,
- competitor crawl/analysis flow,
- benchmark endpoint,
- map aggregation endpoint.

Frontend 2:

- Competitor Analysis page,
- Map/Heatmap page.

Frontend 1:

- profile flag gating for competitor/map.

Solution Engineer:

- validate competitor use case,
- review map summary,
- define benchmark formula.

Exit criteria:

- competitor bisa dibuat,
- competitor review bisa dianalisis,
- own vs competitor comparison tampil,
- map marker tampil berdasarkan lokasi dan rating/review count.

### Milestone 6 - Reports + Hardening

Durasi: 1 minggu

Backend + AI:

- export history,
- report API,
- audit log minimal,
- failed job retry improvements.

Frontend 1:

- Settings V2.

Frontend 2:

- Reports page.

Solution Engineer:

- end-to-end QA,
- stakeholder demo script,
- backlog next phase.

Exit criteria:

- report bisa digenerate,
- settings status jelas,
- demo flow end-to-end siap.

## 4. Suggested Backlog Breakdown

### Backend Tickets

- Add `profiles` migration.
- Add `users` migration.
- Add auth service.
- Add JWT/session middleware.
- Add profile entitlement service.
- Add `sources` migration.
- Add source CRUD API.
- Add `crawl_jobs` migration.
- Add crawl job API.
- Add Firecrawl connector.
- Refactor Selenium fetch into connector interface.
- Add queue/worker runner.
- Add taxonomy migrations.
- Extend reviews with handling/taxonomy fields.
- Add review assignment API.
- Add action item migration/API.
- Add AI V2 schema.
- Add competitor migrations/API.
- Add map aggregation API.
- Add export history.

### Frontend Tickets

- Create auth layout.
- Build Login page.
- Build Register page.
- Add session store/client.
- Protect app routes.
- Add Profile Management page.
- Add feature flag form.
- Add QuotaMeter component.
- Add Sources page.
- Enhance Fetch Jobs to Crawl Jobs.
- Enhance Review Inbox.
- Add ReviewDetailPanel.
- Add Taxonomy Management page.
- Enhance Analysis page.
- Add Competitor Analysis page.
- Add Map/Heatmap page.
- Add Action Tracker page.
- Implement Reports page.
- Implement Settings page.

### Solution Engineer Tickets

- Finalize V2 requirement.
- Finalize API contract.
- Finalize schema ERD.
- Define taxonomy master.
- Define competitor benchmark formula.
- Define map risk color logic.
- Define entitlement business rules.
- Prepare demo script.
- Review backend PR.
- Review frontend PR.
- Run e2e validation.

## 5. Dependency Map

```text
Auth/Profile
  -> entitlement
  -> sources
  -> crawl jobs
  -> review inbox profile scope
  -> AI quota
  -> competitor flag
  -> map profile filter

Sources
  -> crawl jobs
  -> Firecrawl connector
  -> review ingestion

Taxonomy
  -> AI V2
  -> review inbox filter
  -> insights
  -> action tracker

Competitor
  -> profile flag
  -> sources
  -> crawl jobs
  -> AI analysis
  -> benchmark dashboard

Map
  -> location lat/lng
  -> review aggregation
  -> profile/location filters
```

## 6. Collaboration Rules

- Backend API contract ditulis dulu sebelum frontend consume.
- Frontend boleh memakai typed mock sementara jika API belum selesai, tetapi harus mengikuti contract.
- Migration harus kecil dan reversible.
- Existing feature tidak boleh rusak saat menambah profile.
- Semua endpoint baru harus profile-scoped.
- Long-running job tidak boleh blocking request di V2 final.
- AI prompt/schema harus versioned.
- Scraping tidak boleh bypass auth/CAPTCHA/token.

## 7. Testing Plan

### Backend

- unit test profile entitlement,
- unit test auth,
- unit test source connector normalization,
- unit test review deduplication dengan profile/source,
- unit test AI V2 validation,
- API test for protected route,
- API test for tenant isolation.

### Frontend

- component smoke test for key pages,
- manual responsive QA,
- auth flow QA,
- disabled state for feature flags,
- map render QA,
- table filter QA.

### End-to-End Manual Demo

Flow demo:

1. Login.
2. Create profile.
3. Enable AI and competitor flag.
4. Add source.
5. Add location.
6. Run crawl job.
7. See review inbox.
8. Run AI analysis.
9. See insight.
10. Add competitor.
11. Run competitor analysis.
12. Open heatmap.
13. Generate report.

## 8. Recommended Sprint Split

### Sprint 1

- Auth.
- Profile.
- Protected app.
- Profile flags.

### Sprint 2

- Sources.
- Crawl jobs.
- Firecrawl connector.
- Fetch job UI enhancement.

### Sprint 3

- Review Inbox.
- Taxonomy.
- AI V2.

### Sprint 4

- Competitor.
- Map/Heatmap.
- Action Tracker.

### Sprint 5

- Reports.
- Settings.
- QA hardening.
- Stakeholder demo.

## 9. Definition Of Done

Sebuah fitur dianggap selesai jika:

- schema/API selesai,
- frontend connected ke API real,
- loading/error/empty state tersedia,
- permission/entitlement dicek,
- data profile-scoped,
- test minimal tersedia,
- tidak mematahkan existing pages,
- sudah di-review oleh Solution Engineer,
- sudah masuk demo script jika user-facing.

