# Panduan Deploy Backend Review Intelligence dengan Docker

Dokumen ini adalah runbook praktis untuk deploy backend Review System sebagai 3rd party service yang menyediakan REST API untuk dipull oleh OneBox.

Target pembaca:
- Developer yang diberi akses server dev/staging.
- Infra team yang menyiapkan server deployment.
- Engineer OneBox yang butuh tahu base URL dan health check API.

## 1. Kesimpulan Arsitektur Deployment

Backend crawler berjalan sebagai service terpisah dari OneBox.

Flow integrasi:

    OneBox PR UI
        -> REST API request dengan Bearer Token
        -> Backend Crawler Service Docker Container
        -> PostgreSQL
        -> AI Provider configurable, sementara local LLM
        -> JSON response balik ke OneBox

Service ini dianggap 3rd party service oleh OneBox karena berjalan terpisah dan diakses melalui REST API.

## 2. Kondisi Repo Saat Ini

Repo backend:

    https://github.com/sayyidtrq/herminaCrawler

Repo frontend:

    https://github.com/sayyidtrq/herminaCrawler-fe

Entry point backend FastAPI:

    apps.api.main:app

Local command backend:

    python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000

Health check:

    GET /api/health

API docs:

    GET /api/docs

## 3. Catatan Tentang FE di Dalam BE (SUDAH DIBERESKAN)

Status: resolved.

Sebelumnya repo backend menyimpan dua entry gitlink (mode 160000) tanpa `.gitmodules`:

    hermina-crawler-fe   -> frontend asli (repo GitHub terpisah), tertinggal 5 commit
    herminaCrawler-fe    -> entry hantu, folder kosong 0 byte

Plus satu `package-lock.json` kosong di root yang tidak punya `package.json` pasangan.

Semua sudah dibersihkan:
- Kedua gitlink di-untrack dari index (`git rm --cached`); folder `hermina-crawler-fe` tetap ada di disk untuk local dev, tapi tidak lagi di-track repo backend.
- Folder kosong `herminaCrawler-fe` dihapus dari disk.
- `package-lock.json` root dihapus.
- `.gitignore` ditambah entry `herminaCrawler-fe` dan `package-lock.json` supaya tidak ke-add ulang.

Repo backend sekarang murni backend/API — fresh clone di server tidak akan membawa folder FE sama sekali. Frontend tetap hidup di repo-nya sendiri:

    https://github.com/sayyidtrq/herminaCrawler-fe

## 4. File Deployment yang Sudah Ada di Repo

Semua file berikut sudah dibuat dan masuk repo (bukan lagi rencana):

    Dockerfile
    docker-compose.yml
    .dockerignore
    entrypoint.sh
    .gitattributes      (memaksa entrypoint.sh selalu LF, aman di-checkout dari Windows)
    .env.example        (sudah termasuk CORS_ALLOWED_ORIGINS dan JWT_SECRET_KEY)

## 5. Dockerfile Backend (versi final di repo)

    FROM python:3.11-slim

    ENV PYTHONDONTWRITEBYTECODE=1 \
        PYTHONUNBUFFERED=1

    WORKDIR /app

    # curl is required by the docker-compose healthcheck
    RUN apt-get update && apt-get install -y --no-install-recommends \
            build-essential \
            curl \
        && rm -rf /var/lib/apt/lists/*

    COPY requirements.txt /app/requirements.txt
    COPY apps/api/requirements.txt /app/apps/api/requirements.txt

    RUN pip install --no-cache-dir --upgrade pip \
        && pip install --no-cache-dir -r /app/apps/api/requirements.txt

    COPY app /app/app
    COPY apps /app/apps
    COPY alembic /app/alembic
    COPY alembic.ini /app/alembic.ini
    COPY entrypoint.sh /app/entrypoint.sh

    RUN chmod +x /app/entrypoint.sh \
        && mkdir -p /app/exports

    EXPOSE 8000

    ENTRYPOINT ["/app/entrypoint.sh"]

Isi `entrypoint.sh` — migration jalan otomatis setiap container start, lalu server dinyalakan:

    #!/bin/sh
    set -e

    echo "[entrypoint] Running alembic migrations..."
    python -m alembic upgrade head

    echo "[entrypoint] Starting API server..."
    exec python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000

Catatan:
- Dockerfile ini fokus backend FastAPI. Frontend tidak ikut dicopy.
- Root `main.py` (terminal app) sengaja TIDAK dicopy — tidak ada yang meng-import-nya dari `app/`/`apps/`/`alembic/`, container hanya butuh API.
- `entrypoint.sh` wajib LF (bukan CRLF); sudah dikunci lewat `.gitattributes`. Kalau container gagal start dengan error aneh "no such file or directory" pada entrypoint, hampir pasti line ending-nya berubah jadi CRLF.
- Selenium mode tidak didukung di container (lihat bagian 13). Gunakan REVIEW_SOURCE_MODE=mock atau google_places.

## 6. .dockerignore (versi final di repo)

    .git
    .gitignore
    .gitattributes

    .env
    .env.*
    !.env.example

    venv
    .venv
    __pycache__
    *.pyc
    .pytest_cache
    .ruff_cache

    exports
    .selenium-profile
    create_tables.sql
    selenium_debug.html
    selenium_debug.png

    hermina-crawler-fe
    node_modules
    .next

    markdowns
    req-sayyid
    tests
    scripts
    .agents
    .codex

    Dockerfile
    docker-compose.yml
    .dockerignore

Catatan:
- `tests/` dan `scripts/` di-exclude karena bukan runtime asset (scripts berisi setup Selenium profile yang tidak relevan di container).
- `markdowns/` tidak dibutuhkan runtime production.
- `herminaCrawler-fe` tidak perlu di-list lagi — folder itu sudah dihapus dari repo (bagian 3).

## 7. docker-compose.yml (versi final di repo — Supabase-only)

Update 7 Jul 2026: compose disederhanakan jadi **Supabase-only**. Service `db` bundled dihapus; `api` mengambil `DATABASE_URL` (Supabase pooler) dari `.env`. Versi di repo sekarang:

    services:
      api:
        build:
          context: .
          dockerfile: Dockerfile
        container_name: hermina-review-api
        restart: unless-stopped
        env_file:
          - .env
        ports:
          - "8000:8000"
        volumes:
          - ./exports:/app/exports
        healthcheck:
          test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
          interval: 15s
          timeout: 5s
          retries: 5
          start_period: 20s

Catatan:
- Kredensial DB TIDAK boleh ditaruh di compose (file ke-track git) — semua dari `.env` yang gitignored.
- Migration jalan otomatis via `entrypoint.sh` terhadap Supabase tiap container start (idempotent).
- Butuh Postgres lokal bundled untuk dev offline? Versi lama (service `db` + `api`) ada di git history commit `c4fcf0e`. Snippet di bawah ini dipertahankan sebagai referensi opsi bundled.

<details>
<summary>Referensi lama: compose dengan Postgres bundled (dev/staging offline)</summary>

    services:
      db:
        image: postgres:16-alpine
        container_name: hermina-review-db
        restart: unless-stopped
        environment:
          POSTGRES_DB: hermina_reviews
          POSTGRES_USER: hermina
          POSTGRES_PASSWORD: change_me
        volumes:
          - postgres_data:/var/lib/postgresql/data
        ports:
          - "5432:5432"
        healthcheck:
          test: ["CMD-SHELL", "pg_isready -U hermina -d hermina_reviews"]
          interval: 10s
          timeout: 5s
          retries: 5

      api:
        build:
          context: .
          dockerfile: Dockerfile
        container_name: hermina-review-api
        restart: unless-stopped
        env_file:
          - .env
        environment:
          DATABASE_URL: postgresql://hermina:change_me@db:5432/hermina_reviews
        ports:
          - "8000:8000"
        depends_on:
          db:
            condition: service_healthy
        volumes:
          - ./exports:/app/exports
        healthcheck:
          test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
          interval: 15s
          timeout: 5s
          retries: 5
          start_period: 20s

    volumes:
      postgres_data:

Catatan penting:
- JEBAKAN UMUM: blok `environment:` MENANG atas `env_file:` menurut aturan precedence Compose. `DATABASE_URL` sengaja dipin di `environment:` supaya container api selalu mengarah ke service `db`, apa pun isi `.env` developer (misalnya `.env` lokal yang mengarah ke Supabase pooler untuk dev non-Docker). Kalau kamu edit `DATABASE_URL` di `.env` dan bingung kenapa "tidak ngefek" di compose — ini alasannya.
- Service `db` bawaan compose ini hanya untuk dev/staging. Deployment yang pakai managed Postgres/Supabase cukup set `DATABASE_URL` ke instance tersebut, hapus/override baris `environment.DATABASE_URL`, dan jalankan `docker compose up -d api` tanpa service `db`.
- `depends_on.condition: service_healthy` memastikan api baru start setelah Postgres benar-benar siap menerima koneksi, bukan sekadar container-nya hidup.
- localhost di dalam container berarti container itu sendiri, bukan host server.
- Password database wajib diganti di server.

</details>

## 8. Environment Variable Minimum

Isi .env di server.

    APP_ENV=staging
    APP_NAME=Review System
    LOG_LEVEL=INFO
    EXPORT_DIR=exports

    DATABASE_URL=postgresql://hermina:change_me@db:5432/hermina_reviews

    # WAJIB: generate value random panjang per deployment. Kode punya fallback
    # default yang insecure — jangan pernah biarkan unset di server.
    JWT_SECRET_KEY=ganti-dengan-random-string-panjang

    # Origin yang boleh akses API (comma-separated). Tambahkan origin OneBox
    # di sini begitu diketahui — tidak perlu redeploy kode, cukup restart.
    CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

    REVIEW_SOURCE_MODE=mock
    GOOGLE_MAPS_API_KEY=
    GOOGLE_PLACES_LANGUAGE_CODE=id
    GOOGLE_PLACES_REGION_CODE=ID

    LOCAL_LLM_BASE_URL=http://host.docker.internal:11434/v1/
    LOCAL_LLM_API_KEY=ollama
    LOCAL_LLM_MODEL=qwen2.5:7b

    FETCH_LIMIT_PER_LOCATION=50
    FETCH_TIMEOUT_SECONDS=30
    FETCH_MAX_RETRY=3

    SELENIUM_HEADLESS=true
    SELENIUM_DEFAULT_TARGET_REVIEWS=100
    SELENIUM_MAX_TARGET_REVIEWS=300
    SELENIUM_SCROLL_DELAY_SECONDS=2
    SELENIUM_MAX_SCROLL_ATTEMPTS=100
    SELENIUM_WAIT_TIMEOUT_SECONDS=20
    SELENIUM_USER_DATA_DIR=.selenium-profile

    ANALYSIS_BATCH_SIZE=20
    PROMPT_VERSION=v1
    PAGE_SIZE=20
    SHOW_RAW_PAYLOAD=false

Untuk local LLM:
- Kalau Ollama/local LLM jalan di host server, pastikan container bisa akses host.
- Di Linux Docker, host.docker.internal kadang perlu extra_hosts.
- Alternatif: deploy local LLM sebagai container/service sendiri dan arahkan LOCAL_LLM_BASE_URL ke service name.

## 9. Step Deploy Saat Sudah Diberi Akses Server

### 9.1 Masuk ke server

    ssh username@server-ip

### 9.2 Cek Docker

    docker --version
    docker compose version

Kalau belum ada Docker, minta Infra Team install Docker Engine dan Docker Compose plugin.

### 9.3 Clone backend repo

    git clone https://github.com/sayyidtrq/herminaCrawler.git
    cd herminaCrawler

### 9.4 Sanity check hasil clone

    ls -la

Fresh clone sekarang hanya berisi backend (folder FE sudah tidak di-track,
lihat bagian 3). Pastikan `Dockerfile`, `docker-compose.yml`, `.dockerignore`,
dan `entrypoint.sh` ada di root.

### 9.5 Buat .env server

    cp .env.example .env
    nano .env

Ubah minimal:
- APP_ENV=staging
- DATABASE_URL sesuai compose/server
- REVIEW_SOURCE_MODE sesuai mode yang mau dipakai
- LOCAL_LLM_BASE_URL sesuai lokasi local LLM
- API key provider jika pakai provider external

### 9.6 Build image

    docker compose build api

### 9.7 Start stack

    docker compose up -d

### 9.8 Cek log

    docker compose logs -f api
    docker compose logs -f db

### 9.9 Migrasi database (otomatis)

Migration TIDAK perlu dijalankan manual — `entrypoint.sh` menjalankan
`alembic upgrade head` otomatis setiap kali container api start, dan
perintah itu idempotent (aman diulang di schema yang sudah ter-migrate).

Kalau perlu re-run manual (misalnya debugging):

    docker compose exec api python -m alembic upgrade head
    docker compose exec api python -m alembic current

### 9.10 Test health check dari server

    curl http://localhost:8000/api/health

Expected response (field `database` ikut memverifikasi koneksi + schema):

    {"status":"ok","app":"Review System","env":"staging","database":{"ok":true,"message":"OK"}}

Kalau `database.ok` bernilai false, endpoint tetap balas 200 (by design,
supaya healthcheck Docker tidak me-restart container gara-gara DB blip
sesaat) — tapi `database.message` akan menjelaskan masalahnya (koneksi
gagal atau schema belum ter-migrate).

### 9.11 Test API docs

Buka dari browser atau curl:

    http://server-ip:8000/api/docs

Jika server tidak expose port 8000 public, minta Infra Team setup reverse proxy.

## 10. Reverse Proxy Nginx Opsional

Jika ingin API punya domain:

    https://crawler-dev.company.com/api/health

Minta Infra Team setup Nginx/Caddy/Traefik dengan upstream ke:

    http://127.0.0.1:8000

Checklist reverse proxy:
- HTTPS aktif.
- Request ke /api diarahkan ke container API.
- Timeout cukup panjang untuk endpoint fetch/analysis.
- Header Authorization diteruskan ke backend.
- IP whitelist jika diminta OneBox.

## 11. Checklist Integrasi OneBox

Data yang perlu dikasih ke tim OneBox:

- Base URL backend crawler.
- Health check URL.
- API docs URL.
- Auth method: Bearer Token atau API Key.
- Endpoint list yang akan dipull OneBox.
- Contoh request/response JSON.
- Rate limit atau batas request.
- Error response format.
- Mapping company_id/user_id/role dari OneBox ke backend crawler.

Contoh base URL:

    https://crawler-dev.company.com

Contoh endpoint:

    GET /api/health
    GET /api/dashboard/summary
    GET /api/locations
    GET /api/reviews
    GET /api/fetch-logs
    POST /api/pipeline/location

Endpoint final harus disesuaikan dengan route existing di backend.

## 12. Mode AI Provider yang Fleksibel

Pak Agung minta koneksi AI fleksibel. Maka deployment harus pakai env/config.

Untuk sementara pakai local LLM:

    LOCAL_LLM_BASE_URL=http://local-llm:11434/v1/
    LOCAL_LLM_API_KEY=ollama
    LOCAL_LLM_MODEL=qwen2.5:7b

Ke depan bisa ditambah konsep:

    ANALYSIS_PROVIDER=local_llm

Nilai yang mungkin:
- local_llm
- gemini
- openrouter
- onebox_ai

Kalau belum ada ANALYSIS_PROVIDER di kode, catat sebagai improvement agar provider analysis bisa diganti tanpa ubah kode.

## 13. Selenium / Google Maps Scraping Note

Selenium scraping di Docker jauh lebih rumit dibanding API mode karena butuh:
- Chrome atau Chromium dalam container.
- ChromeDriver compatible.
- Profile/session handling.
- Headless browser stability.
- Compliance dengan Google anti-automation policy.

Rekomendasi deployment awal:
- Jangan jadikan Selenium sebagai production default.
- Gunakan REVIEW_SOURCE_MODE=mock untuk smoke test.
- Gunakan google_places jika API key tersedia.
- Selenium hanya untuk controlled POC/manual environment.

## 14. Troubleshooting Cepat

### API container mati

    docker compose ps
    docker compose logs api

Cek:
- DATABASE_URL benar.
- Dependency build sukses.
- apps.api.main:app bisa diimport.

### Database connection refused

Cek DATABASE_URL. Di Docker Compose, host database adalah db, bukan localhost.

Benar:

    postgresql://hermina:change_me@db:5432/hermina_reviews

Salah di dalam container:

    postgresql://hermina:change_me@localhost:5432/hermina_reviews

### Migration gagal

    docker compose exec api python -m alembic current
    docker compose exec api python -m alembic upgrade head

Cek apakah alembic.ini dan folder alembic tercopy ke image.

### API docs tidak bisa dibuka

Cek:
- Container expose port 8000.
- docker compose ports benar.
- Firewall server membuka port yang sesuai.
- Reverse proxy sudah diarahkan ke container.

### Local LLM tidak bisa diakses dari container

Cek:
- LOCAL_LLM_BASE_URL benar.
- Jika LLM jalan di host, container bisa reach host.
- Jika LLM jalan di container lain, pakai service name Docker network.

## 15. Pre-flight Checklist Sebelum Meeting dengan Infra

Siapkan jawaban untuk pertanyaan ini:

- Server pakai OS apa?
- Docker dan Docker Compose sudah tersedia?
- Deployment pakai public domain atau internal IP?
- PostgreSQL ikut container atau pakai managed DB?
- Reverse proxy dan HTTPS disiapkan siapa?
- Environment dev/staging/prod dipisah atau tidak?
- Secret disimpan di .env, vault, atau platform secret manager?
- OneBox akses via public internet, VPN, atau internal network?
- Perlu IP whitelist?
- Local LLM jalan di server yang sama atau server lain?

## 16. Status Action Item

Sudah selesai:
1. [x] Dockerfile ditambahkan ke repo backend.
2. [x] docker-compose.yml untuk dev/staging.
3. [x] .dockerignore (FE dan file non-runtime di-exclude dari build).
4. [x] Repo backend dibersihkan dari nested FE dan file nyasar.
5. [x] entrypoint.sh: migration otomatis + uvicorn di container.
6. [x] /api/health diperkaya dengan DB connectivity + schema check.
7. [x] CORS origins jadi configurable via env (CORS_ALLOWED_ORIGINS).

Berikutnya (butuh pihak lain / belum scope sekarang):
8. [ ] Verifikasi end-to-end di server dev yang disiapkan Infra Team.
9. [ ] Kirim base URL dan API contract ke tim OneBox.
10. [ ] Future hardening: gunicorn/multi-worker, CI/CD, reverse proxy + HTTPS,
       ANALYSIS_PROVIDER switch di kode (bagian 12).

## 17. Rekomendasi Penataan Repo BE dan FE

Opsi paling bersih untuk kondisi sekarang:

    parent-folder/
      herminaCrawler/       backend only
      herminaCrawler-fe/    frontend only

Backend repo sebaiknya hanya berisi:
- app/
- apps/
- alembic/
- tests/
- scripts/
- requirements.txt
- Dockerfile
- docker-compose.yml
- .dockerignore
- .env.example

Frontend repo sebaiknya hanya berisi:
- app/
- public/
- package.json
- package-lock.json
- next.config.ts
- tsconfig.json

Jika tetap ingin satu repo, ubah menjadi monorepo resmi:

    herminaCrawler/
      backend/
      frontend/
      docker-compose.yml

Tapi karena sekarang sudah ada dua GitHub repo terpisah, rekomendasi gua: jangan monorepo dulu. Pisahkan BE dan FE supaya deploy backend sebagai 3rd party service lebih simpel.
