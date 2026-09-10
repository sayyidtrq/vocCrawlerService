# Cara Jalanin Backend via Docker (Quickstart)

Panduan singkat sehari-hari. Untuk runbook deployment lengkap ke server (reverse proxy, integrasi OneBox, troubleshooting), lihat `DOCKER_BACKEND_DEPLOYMENT_GUIDE.md`.

## Topologi Database

Compose ini **Supabase-only**: hanya ada 1 service (`api`). `DATABASE_URL` diambil dari `.env` dan menunjuk ke Supabase pooler (bukan Postgres bundled). Tidak ada container database lokal — data hidup di Supabase.

> Butuh Postgres lokal ephemeral untuk dev offline? Versi compose dengan service `db` bundled ada di git history commit `c4fcf0e` (sebelum di-switch ke Supabase).

## Prasyarat

- Docker Desktop (Windows/Mac) atau Docker Engine + Compose plugin (Linux) sudah jalan.
- File `.env` ada di root repo dengan `DATABASE_URL` Supabase yang valid (`cp .env.example .env` lalu isi).

## Jalanin

```sh
docker compose up -d
```

Yang terjadi otomatis:

1. Image api di-build kalau belum ada.
2. Container api start → `entrypoint.sh` jalankan `alembic upgrade head` terhadap **Supabase** (idempotent; kalau sudah di head = no-op) → uvicorn start di port 8000.

> Karena migration jalan terhadap Supabase produksi tiap container start, hati-hati kalau ada migration baru yang destruktif. Saat ini DB sudah di head jadi aman (no-op).

Cek status:

```sh
docker compose ps          # dua-duanya harus "healthy"
docker compose logs -f api # lihat log migration + server
```

Smoke test:

```sh
curl http://localhost:8000/api/health
# {"status":"ok","app":"Review System","env":"local","database":{"ok":true,"message":"OK"}}
```

API docs: http://localhost:8000/api/docs

## Perintah Umum

```sh
docker compose up -d            # start (build otomatis kalau perlu)
docker compose build api        # rebuild image setelah ubah kode backend
docker compose restart api      # restart api saja
docker compose logs -f api      # tail log
docker compose down             # stop container api (data di Supabase tidak tersentuh)
docker compose exec api python -m alembic current   # cek posisi migration
```

Catatan: `docker compose down` cuma mematikan container api — datanya di Supabase, jadi tidak ada risiko kehilangan data lokal.

## Test Flow Lengkap (register → login → hit API)

```sh
# register company + admin
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Test Co","admin_email":"test@example.com","admin_password":"testpass1"}'

# login, ambil token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=testpass1"

# pakai token
curl http://localhost:8000/api/locations -H "Authorization: Bearer <access_token>"
```

## Hal yang Sering Bikin Bingung

**Ganti DB tinggal edit `.env`.**
`DATABASE_URL` dibaca dari `.env` (via `env_file`), gak ada override hardcoded di compose lagi. Ubah `.env`, `docker compose up -d` ulang, selesai. JANGAN taruh password DB di `docker-compose.yml` — file itu ke-track git.

**`REVIEW_SOURCE_MODE=selenium` di container?**
Tidak didukung — Selenium butuh Chrome profile yang di-login manual (GUI). Di container pakai `mock` atau `google_places`. Config selenium di `.env` tidak bikin container error selama fetch selenium tidak dipanggil.

**Container api restart terus?**
`docker compose logs api` — hampir selalu antara: DATABASE_URL salah, migration gagal, atau entrypoint.sh kena CRLF (jangan save ulang file itu pakai editor yang maksa CRLF; sudah dikunci via `.gitattributes`).

**Frontend?**
FE tidak ikut Docker ini. Jalanin terpisah seperti biasa (`npm run dev` di folder `hermina-crawler-fe`), dia nunjuk ke `http://localhost:8000` yang sekarang dilayani container.
