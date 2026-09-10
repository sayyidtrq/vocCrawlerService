# Cara Menjalankan Web App Review System

Web app ini butuh dua proses:

1. Backend FastAPI di `http://localhost:8000`
2. Frontend Next.js di `http://localhost:3000`

Frontend tidak memakai mock data. Kalau backend belum nyala atau tidak bisa diakses, halaman akan menampilkan warning.

## Opsi 1 - Jalankan FE dan BE Sekaligus

Dari root project `hermina_crawler`:

```powershell
.\scripts\run_web_dev.ps1
```

Kalau kena execution policy PowerShell, pakai:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_web_dev.ps1
```

Lalu buka:

```txt
http://localhost:3000
```

API docs:

```txt
http://localhost:8000/api/docs
```

## Opsi 2 - Jalankan Manual

Terminal 1, dari root project:

```powershell
python -m uvicorn apps.api.main:app --reload --port 8000
```

Terminal 2, dari folder frontend:

```powershell
cd hermina-crawler-fe
npm run dev -- --hostname 127.0.0.1 --port 3000
```

## Environment Frontend

File frontend:

```txt
hermina-crawler-fe/.env.local
```

Isi default:

```txt
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Kalau backend jalan di port lain, ubah value itu lalu restart frontend.

## Endpoint Backend yang Dipakai Frontend

```txt
GET /api/health
GET /api/settings
GET /api/locations
GET /api/reviews
GET /api/dashboard/overview
GET /api/fetch-logs/latest
POST /api/locations
PATCH /api/locations/{location_id}
POST /api/locations/{location_id}/toggle-active
DELETE /api/locations/{location_id}
POST /api/fetch-jobs
POST /api/fetch-jobs/all-active
POST /api/analysis/pending
POST /api/exports/reviews/location/{location_id}.csv
POST /api/pipeline/location
GET /api/settings/database-check
```

## Catatan

- Terminal MVP lama tetap jalan dengan `python main.py`.
- Web MVP sekarang bisa membaca dashboard/lokasi/review/fetch log dan menjalankan action dasar dari UI.
- Action yang tersedia: run fetch per lokasi, analyze pending per lokasi, dan export CSV per lokasi.
- Fetch Selenium dari UI tetap memakai backend lokal dan bisa membuka browser/berjalan lama sesuai konfigurasi Selenium.

