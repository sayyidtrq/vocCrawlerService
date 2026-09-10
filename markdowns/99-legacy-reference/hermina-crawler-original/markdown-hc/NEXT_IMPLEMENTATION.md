# Next Implementation — Roadmap Setelah Dockerization

Update: 7 Juli 2026. Urutan berdasarkan prioritas nyata (bukan sekadar checklist lama — beberapa item di `checklist-system-design-v2.md` sudah tidak akurat, lihat catatan di bawah).

## P0 — SECURITY: Supabase RLS + Data API (DITUNDA, WAJIB SEBELUM PRODUCTION)

**Ditemukan & ditunda 7 Jul 2026.** DB Supabase (`ppirwqfvqnpubhokxyuz`, region ap-northeast-1) sekarang jadi DB utama backend (menggantikan bundled Postgres). Audit langsung ke DB menemukan:

- **RLS mati (`relrowsecurity=false`) di SEMUA 9 tabel public**, termasuk `users` (berisi `password_hash`).
- Role `anon` dan `authenticated` punya **grant penuh** (SELECT/INSERT/UPDATE/DELETE/TRUNCATE) di semua tabel.
- **Data API / PostgREST project ini AKTIF & reachable** (`https://ppirwqfvqnpubhokxyuz.supabase.co/rest/v1/` balas 401 "No API key found" = server hidup).

Dampak: siapa pun yang pegang **anon key** project (anon key didesain publik, biasa ketempel di frontend) bisa baca/hapus seluruh data lintas company lewat Data API — bypass total JWT + `company_id` isolation di FastAPI, karena Data API ngomong langsung ke Postgres.

Kenapa aman untuk difix nanti tanpa mecahin apa-apa: backend konek sebagai role `postgres` (bypass RLS, grant tetap), frontend pakai FastAPI (bukan supabase-js/anon key). Jadi enable RLS + revoke anon TIDAK merusak backend/frontend.

Dikonfirmasi ulang via Supabase MCP `get_advisors` (security) 7 Jul 2026: 9x lint `rls_disabled_in_public` level **ERROR** — persis di kesembilan tabel yang sama (`locations`, `companies`, `users`, `reviews`, `review_analysis`, `fetch_logs`, `competitors`, `competitor_reviews`, `alembic_version`). Referensi: https://supabase.com/docs/guides/database/database-linter?lint=0013_rls_disabled_in_public

Fix (belum dijalankan — koordinasi tim dulu):
```sql
-- minimal: enable RLS di semua tabel (tanpa policy = deny-all buat anon/authenticated)
alter table public.companies         enable row level security;
alter table public.users             enable row level security;
alter table public.locations         enable row level security;
alter table public.reviews           enable row level security;
alter table public.review_analysis   enable row level security;
alter table public.fetch_logs        enable row level security;
alter table public.competitors       enable row level security;
alter table public.competitor_reviews enable row level security;
alter table public.alembic_version   enable row level security;
-- opsional (belt-and-suspenders): revoke grant Data API
-- revoke all on all tables in schema public from anon, authenticated;
```
Alternatif paling bersih: matikan "Exposed schemas = public" di Data API settings dashboard kalau Data API memang tidak dipakai sama sekali.

Terkait: **`JWT_SECRET_KEY` belum di-set di `.env`** → backend pakai fallback insecure yang ada di source publik. Untuk API yang konek ke DB prod dan bakal diekspos ke Infra/OneBox, ini WAJIB di-set ke value random sebelum deploy (kalau tidak, siapa pun bisa forge JWT).

## P0 — CI/CD (diimplementasikan 7 Jul 2026, butuh 1 setup manual)

Workflow `.github/workflows/deploy.yml` sudah dibuat: push ke `main` (path backend) → build image → push ke `ghcr.io/sayyidtrq/herminacrawler` → deploy otomatis ke server private via self-hosted runner. Detail lengkap + cara kerja + langkah setup di `markdowns/CI_CD_SETUP.md`.

**Sisa kerjaan (wajib dikerjakan manual di server private, gua gak punya akses ke sana):**
1. Install & register GitHub Actions self-hosted runner di server itu.
2. Buat `/opt/hermina-crawler`, `git clone` repo, isi `.env` di situ.
3. Pastikan user runner bisa jalanin `docker` tanpa sudo.
4. Test: push kecil ke `main` atau trigger manual via tab Actions, pantau job `deploy`.

## P0 — Deployment & Integrasi OneBox (arahan lead, sedang berjalan)

1. **Push `main` ke origin** — beberapa commit lokal (repo cleanup, Docker, merge, migration/test fix, Supabase switch, CI/CD) belum di-push.
2. **Setup self-hosted runner** — lihat item CI/CD di atas. Setelah ini jalan, poin di bawah soal "deploy manual ke server dev" jadi otomatis.
3. **Set secret production di server**: `JWT_SECRET_KEY` (wajib, jangan pakai fallback kode), `DATABASE_URL` (Supabase, sudah aktif), `LOCAL_LLM_BASE_URL`, `CORS_ALLOWED_ORIGINS` (+ origin OneBox).
4. **Kirim paket integrasi ke tim OneBox**: base URL, `/api/health`, `/api/docs`, auth flow (register/login → Bearer), daftar endpoint pull. `markdowns/api-design.md` (kerjaan tim, sudah masuk main) adalah kontraknya — review dulu apakah sudah sinkron dengan response `database` field baru di health.
5. **Klarifikasi auth model untuk OneBox**: sekarang auth-nya user-based JWT (login email/password, expired 7 hari). Untuk service-to-service pull, kemungkinan butuh API key statis atau service account + refresh mechanism. Putuskan bareng tim OneBox sebelum mereka mulai integrasi.

## P1 — Bug Nyata yang Sudah Terkonfirmasi di Kode

1. **Unique constraint `locations` belum company-aware.** `uq_locations_source_place` masih global `(source, external_place_id)` — company B tidak bisa mendaftarkan tempat yang sudah didaftarkan company A. Tabel `competitors` sudah benar (`uq_competitors_source_place_company`); samakan. Butuh satu migration baru: drop constraint lama, create `(company_id, source, external_place_id)`.
2. **`SettingsService.public_configuration()` crash** — masih membaca `self.settings.gemini_mode`/`gemini_model` yang sudah dihapus dari `Settings`. Endpoint `GET /api/settings` akan 500 kalau dipanggil. Hapus dua baris itu atau ganti dengan field local LLM.
3. **`test_real_integrations.py` stale** — masih import `GeminiClient` + field gemini. Putuskan: update ke local LLM / OpenRouter, atau hapus kalau Gemini memang ditinggalkan.
4. **`ANALYSIS_PROVIDER` belum ada di kode** (permintaan "AI fleksibel" Pak Agung baru terpenuhi sebagian via env local LLM). Tambah setting `ANALYSIS_PROVIDER=local_llm|gemini|openrouter` yang memilih client di `AnalysisService`, sekaligus sinkronkan config `GeminiClient`/`OpenRouterClient` yang sekarang refer setting yang tidak ada.

## P2 — Hardening Deployment (setelah jalan di server)

1. **Job asinkron.** Fetch/analysis masih synchronous di request HTTP — request OneBox bisa timeout untuk job besar. Rencana V2 sudah ada: tabel `crawl_jobs` + return job id + worker (RQ/Celery/arq). Ini prasyarat sebelum OneBox pull data dalam volume nyata.
2. **Reverse proxy + HTTPS** (Nginx/Caddy, dibantu Infra Team) + IP whitelist kalau diminta OneBox.
3. **Multi-worker**: ganti uvicorn single-process dengan `--workers N` atau gunicorn+uvicorn worker di entrypoint.

## P3 — Fitur Produk V2 yang Tersisa (dari checklist, SUDAH diverifikasi ke kode 7 Juli)

Catatan penting: beberapa item P0 lama di `checklist-system-design-v2.md` **sudah selesai** dan tidak perlu dikerjakan lagi — bearer token auto-inject di `api.ts` frontend sudah ada, 401 auto-redirect sudah ada, enforcement `ai_enable_flag` dan `analyze_competitor_flag` di backend sudah ada (`EntitlementService`). Jangan buang waktu ke situ.

Yang benar-benar masih kosong:

1. **Quota enforcement** — `total_enable_review` tampil di UI tapi tidak pernah di-enforce di fetch job.
2. **MapPicker belum terpasang di halaman Locations** — komponennya ada (`app/components/map-picker.tsx`, react-leaflet terinstall), form Locations masih manual input lat/lng/place ID. Tinggal wiring.
3. **Date range filter** untuk fetch + reviews (permintaan stakeholder: crawl lebih terstruktur).
4. **Review Inbox** — handling status (`new/triaged/assigned/...`), assignment, notes, detail panel.
5. **AI Taxonomy V2** — product/wilayah/unit kerja/klasifikasi + confidence score di prompt & schema.
6. **Competitor pipeline** — registry CRUD sudah ada; crawl + benchmark + dashboard belum.
7. **Map/Heatmap page** + aggregation API.
8. **Reports & Settings pages** — masih placeholder di FE.
9. **Tenant-isolation test untuk layer API** — test service-layer sudah ada (`test_tenant_isolation.py`), belum ada yang menguji lewat HTTP + JWT.

## Utang Dokumentasi

- `checklist-system-design-v2.md` dan `newer_system.md` saling kontradiksi dan sebagian sudah basi (contoh: klaim "MapPicker dihapus total" itu salah). Sinkronkan sekali, atau tandai keduanya deprecated dan jadikan dokumen ini + `existing-system.md` acuan.
- `api-design.md` (baru dari tim): pastikan tetap sinkron tiap kali response schema berubah — sudah kejadian sekali (field `database` di health hampir ke-strip gara-gara schema tidak di-update).
