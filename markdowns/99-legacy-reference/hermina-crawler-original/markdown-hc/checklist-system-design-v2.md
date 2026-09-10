# Checklist System Design V2

Tanggal audit: 2026-07-02

Dokumen ini memetakan kondisi implementasi terbaru terhadap `system-design-v2.md`. Status dibuat berdasarkan codebase saat ini, bukan hanya rencana dokumen.

## Legend

- [x] Done: sudah ada di codebase dan bisa dipakai sebagai baseline.
- [~] Partial: sudah ada sebagian, tetapi belum lengkap/aman sebagai V2 production behavior.
- [ ] Todo: belum terlihat implementasinya.
- [hold] Hold: sengaja ditunda sesuai keputusan scope.

## 1. Snapshot Terbaru

Yang sudah/sedang terimplement:

- [x] Auth barrier frontend via `AuthProvider` dan redirect ke `/login`.
- [x] Login page.
- [x] Register company/admin.
- [x] JWT access token backend.
- [x] Endpoint `/api/auth/register`, `/api/auth/login`, `/api/auth/me`.
- [x] Baseline company/profile entity melalui table `companies`.
- [x] Baseline benefit parameter: `ai_enable_flag`, `total_enable_review`, `analyze_competitor_flag`.
- [x] Multi-tenancy baseline: `company_id` sudah masuk ke `locations`, `reviews`, dan `fetch_logs`.
- [x] Company-scoped service untuk location, review, summary, fetch log, fetch, selenium fetch, analysis, export.
- [x] Competitor registry baseline: model, service, router, dan frontend page.
- [x] Google place resolver by coordinate: `/api/places/resolve`.
- [~] Map picker component sudah ada, tetapi belum terpasang di Location Management page.
- [~] Auth-aware UI sudah menampilkan entitlement di sidebar.
- [~] Competitor menu disembunyikan jika `analyze_competitor_flag=false`, tetapi backend enforcement belum lengkap.

Catatan dependency:

- [x] `bcrypt` dipin ke versi kompatibel `>=4.0.1,<4.1` untuk menghindari mismatch `passlib==1.7.4` dengan `bcrypt==5.x`.
- [x] Register password sudah divalidasi maksimal 72 bytes agar error bcrypt tidak bocor mentah ke UI.

## 2. Core Existing Tetap Dipakai

- [x] Core Python service layer tetap digunakan.
- [x] FastAPI tetap menjadi API layer.
- [x] Next.js tetap menjadi frontend.
- [x] PostgreSQL + Alembic tetap menjadi persistence/migration layer.
- [x] Selenium fetch masih jalan langsung dari backend sesuai keputusan V2.
- [~] Core lama sudah diberi `company_id`, tetapi perlu audit test untuk memastikan semua query benar-benar tenant-safe.

Next:

- [ ] Tambahkan regression test tenant isolation untuk locations, reviews, fetch logs, dashboard, export, analysis.
- [ ] Rapikan migration history karena ada dua migration multi-tenancy yang tampak beririsan: `495376ef...` dan `6a66329...`.

## 3. Auth, Login, Register

### Backend

- [x] `Company` model.
- [x] `User` model.
- [x] Password hash via passlib bcrypt.
- [x] Register company + admin user.
- [x] Login OAuth2 form username/password.
- [x] JWT creation.
- [x] `get_current_user` dependency.
- [x] `get_current_company_id` helper.
- [~] Password validation ada untuk bcrypt max bytes.
- [ ] Password minimum strength belum ada.
- [ ] Refresh token/session expiry UX belum ada.
- [ ] Forgot/reset password belum ada.
- [ ] Role model belum ada.
- [ ] Super admin/org admin/manager/agent/analyst/viewer belum ada.

### Frontend

- [x] `AuthProvider` wrap root layout.
- [x] Login/register page.
- [x] Token disimpan di localStorage.
- [x] Logout button di sidebar.
- [x] AppShell loading state saat cek session.
- [x] `/api/auth/me` sudah dipanggil dengan bearer token di auth context.
- [~] Protected render sudah ada di `AppShell`.
- [ ] Global API helper `fetchJson/postJson/patchJson/deleteJson` belum otomatis menyisipkan `Authorization: Bearer <token>`. Ini critical karena mayoritas page memakai helper tersebut.
- [ ] Register success belum memvalidasi response login gagal sebelum parsing `access_token`.
- [ ] Form validation frontend untuk password length/min strength belum lengkap.

Prioritas auth berikutnya:

1. [ ] Tambahkan bearer token otomatis di `hermina-crawler-fe/app/lib/api.ts`.
2. [ ] Tambahkan guard: page `/login` redirect ke dashboard jika user sudah login.
3. [ ] Tambahkan role field minimal di `users` atau hold role dengan explicit note.
4. [ ] Tambahkan password policy dan error message yang ramah.

## 4. Profile / Company Management

- [x] Company table menjadi baseline profile.
- [x] Company punya `name`.
- [x] Company punya `ai_enable_flag`.
- [x] Company punya `total_enable_review`.
- [x] Company punya `analyze_competitor_flag`.
- [x] Register dapat menentukan benefit baseline.
- [~] Sidebar menampilkan benefit entitlement.
- [ ] Belum ada Profile Management page terpisah untuk edit company/benefit setelah register.
- [ ] Belum ada endpoint update company/profile benefit.
- [ ] Belum ada usage meter riil untuk `total_enable_review`.
- [ ] Belum ada enforcement quota fetch berdasarkan `total_enable_review`.
- [ ] Belum ada `map_heatmap_enable_flag`, `export_enable_flag`, `max_locations`, `max_sources`, `analysis_monthly_quota`, `retention_days`.
- [hold] `website_crawler_enable_flag` tetap hold.
- [x] `selenium_enable_flag` tidak dipakai sesuai keputusan: Selenium default boleh untuk profile yang punya akses crawler.

Prioritas profile berikutnya:

1. [ ] Buat endpoint `GET/PATCH /api/company/me` atau `/api/profiles/me`.
2. [ ] Buat Profile Settings page untuk update company name + benefit baseline.
3. [ ] Enforce `total_enable_review` di fetch job.
4. [ ] Enforce `ai_enable_flag` di analysis endpoint.
5. [ ] Enforce `analyze_competitor_flag` di competitor endpoint backend.

## 5. Multi-Tenancy / Company Scope

- [x] `company_id` ada di `locations`.
- [x] `company_id` ada di `reviews`.
- [x] `company_id` ada di `fetch_logs`.
- [x] `company_id` ada di `competitors`.
- [x] LocationService menerima `company_id`.
- [x] ReviewService menerima `company_id`.
- [x] FetchService menerima `company_id`.
- [x] SeleniumFetchService menerima `company_id`.
- [x] FetchLogService menerima `company_id`.
- [x] SummaryService menerima `company_id`.
- [x] AnalysisService menerima `company_id`.
- [x] ExportService menerima `company_id`.
- [x] CompetitorService menerima `company_id`.
- [x] Location, reviews, dashboard, fetch jobs, analysis, export, fetch logs, competitors sudah memakai `current_user.company_id`.
- [~] `settings` endpoint protected, tetapi isinya masih runtime global, bukan company settings.
- [~] `places/resolve` protected, tetapi tidak punya company-specific quota/audit.
- [ ] Belum ada automated tenant-isolation tests.
- [ ] Belum ada audit log user action.

Prioritas multi-tenancy berikutnya:

1. [ ] Test user A tidak bisa access location/review/fetch log/user data milik company B.
2. [ ] Pastikan unique constraints mempertimbangkan company untuk location. Saat ini unique `source + external_place_id` di `locations` masih global dan berpotensi menghalangi dua company mendaftarkan tempat yang sama.
3. [ ] Backfill/default company strategy untuk data lama perlu didokumentasikan dan dites.

## 6. Location Management V2

- [x] CRUD locations existing.
- [x] Location scoped by company.
- [x] Location table frontend existing.
- [x] Location form masih support hospital, branch, city, address, lat/lng, source, external place id, Google Maps URL, target review count, active flag.
- [x] Last loaded reviews dipakai untuk simple score/risk di table.
- [~] Google place resolver endpoint by coordinate sudah ada.
- [~] `MapPicker` component sudah ada.
- [ ] `MapPicker` belum dipasang ke Locations form.
- [ ] Belum ada search/discovery by keyword seperti "Hermina Indonesia".
- [ ] Belum ada candidate list lokasi dari external API.
- [ ] Belum ada auto-fill full flow dari selected candidate.
- [ ] Belum ada duplicate warning UI sebelum save.
- [ ] Belum ada bulk import CSV/XLSX.
- [ ] Belum ada data quality badge.
- [ ] Belum ada archive location, masih delete permanen.
- [ ] Belum ada quick action fetch now/view reviews/open maps di location table.

Prioritas location berikutnya:

1. [ ] Pasang `MapPicker` ke Locations page dan auto-fill lat/lng/place id/address/maps URL.
2. [ ] Tambahkan place search endpoint by keyword, bukan hanya reverse geocode lat/lng.
3. [ ] Tambahkan duplicate check endpoint/UI berdasarkan company + source + external_place_id.
4. [ ] Ubah unique constraint location agar company-aware: `company_id + source + external_place_id`.
5. [ ] Tambahkan quick action `Fetch Now` dari row location.

## 7. Fetch / Crawl Jobs

- [x] Fetch one location.
- [x] Fetch all active.
- [x] Dry run one location.
- [x] Dry run all active.
- [x] Selenium direct backend masih dipakai, sesuai V2 decision.
- [x] Fetch logs scoped by company.
- [x] Location must have company_id before fetch.
- [~] Fetch target masih dibatasi max 300 oleh service/config.
- [~] `total_enable_review` tampil sebagai benefit, tetapi belum enforce fetch target/quota.
- [ ] Belum ada persistent `crawl_jobs` table/entity yang terpisah dari `fetch_logs`.
- [ ] Belum ada queue/worker. Ini tidak wajib V2 awal, tapi tetap future hardening.
- [ ] Belum ada cancel/retry job endpoint di model job baru.
- [ ] Belum ada date range crawl parameter.
- [ ] Belum ada post-filter by review date.

Prioritas fetch berikutnya:

1. [ ] Enforce `target_review_count <= company.total_enable_review` atau definisikan ulang quota usage.
2. [ ] Tambahkan `date_preset/date_from/date_to` ke payload fetch job.
3. [ ] Simpan date range ke fetch log metadata.
4. [ ] Tambahkan parser relative date untuk Selenium Google review jika ingin filter "hari ini/1 hari terakhir".
5. [ ] Buat `crawl_jobs` entity setelah fetch flow stabil.

## 8. Review Inbox / Reviews

- [x] Reviews page existing.
- [x] Review list company-scoped.
- [x] Filter by location, rating, sentiment, keyword.
- [x] Latest-first sorting.
- [x] Review table menampilkan rating, sentiment, urgency, issue, flags, recommended action.
- [ ] Belum ada date filter: today, last 1 day, last 7 days, last 30 days, this month, custom.
- [ ] Belum ada handling status: new/triaged/assigned/in_progress/resolved/ignored/archived.
- [ ] Belum ada assignment agent.
- [ ] Belum ada internal notes.
- [ ] Belum ada review detail side panel.
- [ ] Belum ada create action item dari review.
- [ ] Belum ada product/wilayah/unit kerja/klasifikasi filters.

Prioritas reviews berikutnya:

1. [ ] Tambahkan date filters di backend `/api/reviews` dan frontend Reviews page.
2. [ ] Tambahkan fields `handling_status`, `assigned_user_id`, dan notes/action model.
3. [ ] Ubah Reviews page menjadi Review Inbox dengan detail panel.
4. [ ] Tambahkan filter by urgency dan issue category di API/UI.

## 9. AI Analysis V2

- [x] AnalysisService existing.
- [x] Local LLM client aktif.
- [x] Prompt version disimpan.
- [x] Output review-level sentiment/category/urgency/summary/recommended action/keywords/safety/viral.
- [x] Analysis route sudah company-scoped.
- [~] Frontend Analysis page bisa run pending/rerun.
- [ ] `ai_enable_flag` belum enforce di backend analysis routes.
- [ ] Belum ada analysis quota usage.
- [ ] Belum ada AI V2 taxonomy: product, wilayah, unit kerja, klasifikasi masalah/layanan.
- [ ] Belum ada confidence score.
- [ ] Belum ada PII/PHI risk flag.
- [ ] Belum ada prompt V2 dengan taxonomy context.
- [ ] Belum ada model/provider settings per company.

Prioritas AI berikutnya:

1. [ ] Backend guard: jika `company.ai_enable_flag=false`, analysis endpoint return 403/feature disabled.
2. [ ] Update prompt/schema V2 untuk product/wilayah/unit kerja/klasifikasi.
3. [ ] Tambahkan migration untuk analysis taxonomy fields.
4. [ ] Tambahkan UI display/filter untuk taxonomy output.
5. [ ] Tambahkan confidence score dan fallback manual review.

## 10. Competitor Analysis

- [x] Competitor model.
- [x] CompetitorReview model.
- [x] CompetitorService CRUD.
- [x] Competitor API CRUD.
- [x] Competitor page frontend.
- [x] Competitor menu hidden jika flag disabled di frontend.
- [~] Competitor registry sudah company-scoped.
- [ ] Backend competitor API belum enforce `analyze_competitor_flag`.
- [ ] Belum ada fetch/scrape competitor reviews.
- [ ] Belum ada competitor review list page.
- [ ] Belum ada competitor analysis pipeline.
- [ ] Belum ada benchmark own vs competitor.
- [ ] Belum ada competitor insight dashboard.
- [ ] Belum ada route/action untuk `run competitor crawl`.

Prioritas competitor berikutnya:

1. [ ] Backend guard competitor endpoints berdasarkan `analyze_competitor_flag`.
2. [ ] Implement fetch competitor reviews memakai SeleniumGoogleMapsReviewClient atau reusable connector.
3. [ ] Store competitor reviews ke `competitor_reviews`.
4. [ ] Buat competitor benchmark endpoint.
5. [ ] Upgrade Competitors page dari registry menjadi Analyze Competitor dashboard.

## 11. Map / Heatmap

- [~] MapPicker component ada untuk picking coordinate.
- [~] Leaflet/react-leaflet kemungkinan sudah disiapkan di frontend component, tetapi belum diverifikasi sebagai page heatmap.
- [ ] Belum ada Map/Heatmap page.
- [ ] Belum ada map aggregation API.
- [ ] Belum ada marker color/size berdasarkan review count/rating/risk.
- [ ] Belum ada popup summary per location.
- [ ] Belum ada filter map by date/source/sentiment/rating/competitor.
- [ ] Belum ada heat layer negative/critical density.

Prioritas map berikutnya:

1. [ ] Selesaikan Location MapPicker integration dulu.
2. [ ] Buat endpoint `GET /api/map/locations` untuk marker summary.
3. [ ] Buat page `/map` atau `/heatmap`.
4. [ ] Tambahkan marker color by risk dan marker size by review count.

## 12. Source Management

- [x] Source masih berada di field location/competitor.
- [ ] Belum ada `sources` table.
- [ ] Belum ada Source Management page.
- [ ] Belum ada source health per source.
- [ ] Belum ada credential reference per source.
- [ ] Belum ada source test endpoint kecuali `places/resolve` untuk Google coordinate.
- [hold] Firecrawl/website crawler source tetap hold.
- [hold] Social/public web connector tetap hold.
- [hold] App Store/Play Store connector belum masuk scope implementasi sekarang.

Prioritas source berikutnya:

1. [ ] Jangan buat Source Management dulu kalau Location/Fetch/Auth belum stabil.
2. [ ] Setelah date range + quota jalan, baru ekstrak source config dari location menjadi table `sources`.

## 13. Taxonomy Management

- [x] Issue category existing fixed enum di AI schema/service.
- [ ] Belum ada taxonomy tables.
- [ ] Belum ada Product taxonomy.
- [ ] Belum ada Wilayah/Region taxonomy.
- [ ] Belum ada Unit Kerja taxonomy.
- [ ] Belum ada Klasifikasi Masalah/Layanan taxonomy.
- [ ] Belum ada Taxonomy Management page.
- [ ] Belum ada keyword rules.
- [ ] Belum ada mapping issue -> owner unit.

Prioritas taxonomy berikutnya:

1. [ ] Define taxonomy master minimal di markdown/seed.
2. [ ] Tambahkan fields output AI V2 dulu.
3. [ ] Baru buat CRUD Taxonomy Management setelah struktur stabil.

## 14. Action Tracker

- [ ] Belum ada action_items table.
- [ ] Belum ada action tracker API.
- [ ] Belum ada action tracker page.
- [ ] Belum ada link review -> action item.
- [ ] Belum ada owner/due date/status/resolution note.

Prioritas action tracker:

1. [ ] Tunggu Review Inbox handling status selesai.
2. [ ] Tambahkan action item dari review detail.
3. [ ] Buat Action Tracker page.

## 15. Reports / Export / Settings

### Reports

- [x] Backend export CSV/JSON existing.
- [x] Export sudah company-scoped.
- [~] Reports page masih placeholder.
- [ ] Belum ada export history.
- [ ] Belum ada report type selector.
- [ ] Belum ada date range/profile/location/source filters untuk report.
- [ ] Belum ada PDF/PPT report.

### Settings

- [x] Backend settings endpoint protected.
- [~] Settings page masih placeholder.
- [~] Settings masih runtime-global, bukan company-scoped settings.
- [ ] Belum ada connector health dashboard.
- [ ] Belum ada AI provider status UI.
- [ ] Belum ada profile benefit edit UI.

Prioritas reports/settings:

1. [ ] Implement Settings page untuk read-only runtime + current company benefit.
2. [ ] Implement Reports page untuk trigger export existing.
3. [ ] Tambahkan export history setelah export page basic berjalan.

## 16. Firecrawl / Website Crawler

- [hold] Firecrawl dependency ada, tetapi feature ditahan sesuai keputusan scope.
- [hold] Tidak dijadikan benefit flag aktif.
- [hold] Tidak dijadikan prioritas sebelum V2 core stabil.

Kapan dibuka lagi:

- setelah auth + company scope + quota + date range + location discovery stabil,
- setelah integration design Onebox selesai,
- setelah source management table jelas.

## 17. Onebox Integration Preparation

- [x] V2 saat ini masih standalone VoC web app.
- [x] Selenium masih direct backend/manual synchronous.
- [~] API/job response sudah mulai punya bentuk yang bisa diintegrasikan nanti.
- [ ] Belum ada dedicated integration markdown.
- [ ] Belum ada API contract untuk Onebox.
- [ ] Belum ada webhook/event callback.
- [ ] Belum ada conversation/ticket mapping ke Onebox.
- [ ] Belum ada agent reply workflow.

Prioritas Onebox:

- [hold] Ditahan sampai V2 core selesai.
- [ ] Setelah V2 stabil, buat `onebox-integration-design.md`.

## 18. Urutan Kerja Yang Disarankan Dari Sekarang

### P0 - Stabilkan Auth + Protected API

- [ ] Global API helper attach bearer token.
- [ ] Handle 401 global: logout/redirect login.
- [ ] Backend entitlement guard untuk AI dan competitor.
- [ ] Password policy frontend/backend.
- [ ] Tenant isolation tests minimal.

Alasan: hampir semua page sekarang butuh token. Kalau API helper belum bawa token, fitur lain terlihat rusak walaupun backend benar.

### P1 - Stabilkan Company Scope + Location UX

- [ ] Fix unique constraint location menjadi company-aware.
- [ ] Integrate MapPicker ke Locations form.
- [ ] Add place search/discovery by keyword.
- [ ] Add duplicate warning.
- [ ] Add quick action Fetch Now.

Alasan: location adalah pintu masuk semua crawl/review.

### P2 - Fetch Quota + Date Range

- [ ] Enforce `total_enable_review`.
- [ ] Tambahkan date range payload fetch.
- [ ] Simpan date range di metadata fetch log.
- [ ] Tambahkan review date filter di API/UI.
- [ ] Relative date parser untuk Selenium.

Alasan: stakeholder sudah minta crawl lebih terstruktur dan tidak terlalu banyak.

### P3 - Review Inbox

- [ ] Tambahkan handling status.
- [ ] Tambahkan urgency/issue/date filters.
- [ ] Tambahkan review detail panel.
- [ ] Tambahkan notes.
- [ ] Siapkan create action item.

Alasan: ini mengubah sistem dari crawler dashboard menjadi VoC operation tool.

### P4 - AI V2 Taxonomy

- [ ] Prompt/schema V2.
- [ ] Product/wilayah/unit kerja/klasifikasi fields.
- [ ] Confidence score.
- [ ] UI filter/display taxonomy.

Alasan: ini langsung menjawab dimensi stakeholder.

### P5 - Competitor Analysis

- [ ] Enforce competitor flag backend.
- [ ] Fetch competitor reviews.
- [ ] Benchmark endpoint.
- [ ] Competitor dashboard.

Alasan: registry sudah ada, tinggal diangkat menjadi analysis.

### P6 - Map / Heatmap

- [ ] Marker summary API.
- [ ] Heatmap page.
- [ ] Location risk marker.
- [ ] Link marker ke filtered reviews.

Alasan: map butuh data location dan review yang sudah stabil.

### P7 - Reports, Settings, Source Management

- [ ] Reports page untuk export existing.
- [ ] Settings page untuk runtime + company benefit.
- [ ] Source Management setelah flow location/fetch matang.

## 19. Definition Of Done Berikutnya

V2 baseline berikutnya dianggap siap demo jika:

- [ ] user bisa register, login, logout tanpa 401 loop,
- [ ] semua page protected bisa fetch data dengan bearer token,
- [ ] company A tidak bisa membaca/mengubah data company B,
- [ ] company benefit tampil dan backend enforce minimal untuk AI/competitor/quota,
- [ ] lokasi bisa dibuat dengan helper map/place resolver,
- [ ] fetch bisa dibatasi quota dan date range,
- [ ] reviews bisa difilter by date/rating/sentiment/location,
- [ ] dashboard menampilkan data scoped per company,
- [ ] competitor disabled benar-benar disabled di UI dan backend.
