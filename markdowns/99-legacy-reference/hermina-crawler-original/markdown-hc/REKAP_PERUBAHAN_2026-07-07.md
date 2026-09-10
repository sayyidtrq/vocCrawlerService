# Rekap Perubahan — 7 Juli 2026

Konteks: arahan Pak Agung (Discord, 6-7 Juli) — backend crawler dianggap **3rd party service** yang datanya di-**pull** oleh OneBox via REST API, deploy pakai **Docker** supaya fleksibel diinstal di mana pun, AI provider fleksibel (sementara local LLM).

Semua perubahan di bawah sudah di-commit ke branch `main` lokal (belum di-push).

## 1. Pembersihan Struktur Repo (commit `7387e88`)

Masalah yang ditemukan:

- `hermina-crawler-fe` ke-track sebagai gitlink (mode 160000) **tanpa `.gitmodules`** — bukan submodule sah, bukan folder biasa. Fresh clone menghasilkan folder kosong, dan pointer-nya tertinggal 5 commit dari HEAD repo FE asli.
- `herminaCrawler-fe` adalah gitlink hantu: folder 0 byte, remote-nya malah nunjuk ke repo backend sendiri.
- `package-lock.json` kosong di root (tanpa `package.json`) — sisa `npm install` nyasar.

Yang dilakukan:

- `git rm --cached` kedua gitlink. Folder `hermina-crawler-fe` **tetap ada di disk** untuk dev lokal, hanya berhenti di-track. Folder hantu `herminaCrawler-fe` dihapus dari disk.
- `package-lock.json` root dihapus.
- `.gitignore` ditambah `herminaCrawler-fe` dan `package-lock.json`.

Hasil: repo backend murni backend. FE tetap hidup di repo GitHub-nya sendiri (`herminaCrawler-fe.git`).

## 2. Dockerization Backend (commit `c4fcf0e`)

File baru:

| File | Isi |
|---|---|
| `Dockerfile` | `python:3.11-slim`, hanya copy `app/`, `apps/`, `alembic/`, `alembic.ini`, `entrypoint.sh`. FE, tests, docs, Selenium profile tidak ikut. |
| `entrypoint.sh` | Jalankan `alembic upgrade head` otomatis lalu start uvicorn di port 8000. |
| `docker-compose.yml` | Service `db` (postgres:16-alpine) + `api`, dua-duanya ber-healthcheck; `api` nunggu `db` benar-benar sehat sebelum start. |
| `.dockerignore` | Exclude FE, markdowns, tests, scripts, cache, `.env`. |
| `.gitattributes` | Kunci `entrypoint.sh` selalu LF (aman di-checkout dari Windows). |

Perubahan kode:

- `app/config.py` + `apps/api/main.py`: CORS origins tidak lagi hardcoded — sekarang env var `CORS_ALLOWED_ORIGINS` (comma-separated). Origin OneBox nanti tinggal ditambah tanpa redeploy kode. Default tetap `localhost:3000` jadi dev lokal tidak berubah.
- `apps/api/app_api/routers/health.py`: `/api/health` sekarang ikut memeriksa koneksi database + kelengkapan schema. DB mati → tetap balas 200 dengan `database.ok:false` (by design, supaya Docker tidak me-restart container gara-gara DB blip).
- `.env.example`: ditambah `CORS_ALLOWED_ORIGINS` dan `JWT_SECRET_KEY` (sebelumnya tidak terdokumentasi sama sekali padahal kode punya fallback insecure), plus catatan bahwa `DATABASE_URL` dan `LOCAL_LLM_BASE_URL` wajib di-set per deployment (default LOCAL_LLM nunjuk IP LAN kantor).

Catatan arsitektur: **Selenium tidak didukung di container** — setup-nya butuh login Google manual di Chrome GUI (`scripts/setup_selenium_profile.py`), tidak bisa headless. Container jalan dengan `REVIEW_SOURCE_MODE=mock` atau `google_places`. Selenium tetap workflow manual lokal yang nulis ke DB yang sama.

## 3. Merge Kerjaan Tim (commit `504bf75`)

Engineer lain push API contract work (`schemas.py` 239 baris + `markdowns/api-design.md` 443 baris + `response_model` di semua router). Konflik di-resolve:

- `health.py`: gabungan — `response_model=HealthResponse` dari kerjaan dia + probe database dari kerjaan Docker. `HealthResponse` di `schemas.py` di-extend dengan field `database` (kalau tidak, FastAPI diam-diam membuang field itu karena schema pakai `extra="ignore"`).
- `.gitignore`: kedua sisi digabung.
- Gitlink `herminaCrawler-fe`: dipertahankan terhapus sesuai keputusan decoupling.

## 4. Fix Bug Migration + Test Suite (commit `fa5d417`)

Dua bug pre-existing ketemu saat verifikasi (bukan disebabkan kerjaan Docker, tapi kebongkar olehnya):

**Migration chain rusak di DB fresh.** `495376efebcb` men-drop index `idx_fetch_logs_company_id` dkk yang tidak pernah dibuat oleh chain — index itu hanya ada di DB yang di-bootstrap manual via `create_tables.sql`. Di Postgres fresh (container), `alembic upgrade head` crash. Fix: `DROP INDEX IF EXISTS`. Perilaku di DB lama (Supabase) tidak berubah karena migration di sana sudah applied.

**Test suite basi pasca multi-tenancy.** `test_mvp.py` dan `test_selenium_scraping.py` masih membuat `Settings` dengan field `gemini_*` yang sudah dihapus, dan mengoper `session_factory` secara posisional ke slot `company_id` — akibatnya query test diam-diam lari ke `DATABASE_URL` asli (Supabase!) bukannya SQLite in-memory. Fix: fixture company per test, keyword args, `MockGeminiClient` di-inject eksplisit. Hasil: **12/12 pass**. (`test_real_integrations.py` masih stale — butuh API key live dan masih refer field gemini yang sudah dihapus; di luar scope.)

## 5. Verifikasi End-to-End (semua lulus)

Di stack `docker compose` dengan Postgres fresh:

1. 4 migration jalan bersih dari nol.
2. `GET /api/health` → 200, `database.ok:true`.
3. `POST /api/auth/register` → company + admin terbuat.
4. `POST /api/auth/login` → JWT keluar.
5. `GET /api/locations` dengan Bearer → 200; tanpa token → 401.
6. Header CORS muncul untuk origin yang diizinkan.
7. Restart container → migration re-run idempotent, tidak error.
8. DB dimatikan → health tetap 200 dengan `database.ok:false` + pesan jelas; DB nyala lagi → `ok:true`.

## Yang Belum (lihat NEXT_IMPLEMENTATION.md)

Push ke origin, deploy ke server Infra Team, kirim API contract ke tim OneBox, dan item-item lanjutan lainnya.
