# Aktivasi Crawler untuk OneBox Staging 1.123

## Keputusan arsitektur

Instance crawler staging 1.123 harus terisolasi dari instance dev yang sudah
aktif. Konfigurasi `ONEBOX_BASE_URL`, akun service, `ONEBOX_SITE_ID`, dan
`ONEBOX_COMPANY_ID` berlaku global per proses. Mengganti konfigurasi port 8000
akan memutus atau mencampur worklist OneBox dev.

Topologi yang digunakan:

| Komponen | Dev aktif | Staging 1.123 |
|---|---|---|
| Host | `192.168.1.3` | `192.168.1.3` |
| API WireGuard | `10.13.13.90:8000` | `10.13.13.90:8001` |
| Compose project | `herminacrawler` | `voc-staging-1123` |
| Database | database lama | `voc_staging_1123` |
| Profil Selenium | volume lama | volume khusus staging |
| OneBox upstream | dev | `https://staging.onebox.co.id/1_123_0` |
| SiteId | 169 | 169 |

## Prasyarat dari sisi OneBox

1. Pulihkan menu versi 1.123 sesuai `VOC_PULIHKAN_MENU_1123_STAGING.sql`.
2. Pastikan provider VoC adalah `PVD99` dan `Code='Voc'`.
3. Siapkan akun service staging yang dapat login ke SiteId 169 dan membaca
   `GET /api/VocWorklist`.
4. Pastikan Connection 985 dan 986 masih membawa metadata lokasi yang benar.
5. Jangan jalankan ulang `voc_setup_all.sql` dan jangan memakai rollback lama.

## Bootstrap crawler

Jalankan dari `/home/ubuntu/crawlerService` setelah perubahan ini sudah masuk
branch `staging`:

```bash
chmod +x scripts/bootstrap-staging-1123.sh scripts/deploy-staging-1123.sh
./scripts/bootstrap-staging-1123.sh
./scripts/deploy-staging-1123.sh --initial
```

Bootstrap meminta kredensial akun service secara interaktif, membuat database
dan secrets terpisah, lalu menyimpan `.env.staging-1123` dengan mode `600`.
Script berhenti jika database atau file env sudah ada supaya tidak menimpa state.

Terbitkan token setelah company staging terbentuk. Jangan tempel token ke chat,
log, Git, atau dokumen:

```bash
docker compose --env-file .env.staging-1123 \
  -p voc-staging-1123 \
  -f docker-compose.staging-1123.yml \
  exec api python -m scripts.manage_api_client issue \
  --company-id 1 \
  --name onebox-staging-1.123 \
  --scope crawl:enqueue \
  --scope crawl:read \
  --expires-days 90
```

`reviews:read` selalu ditambahkan oleh CLI. Tambahkan `analysis:write` hanya saat
fitur analisis AI memang masuk scope pengujian staging.

## Konfigurasi Connection OneBox

Gunakan `VOC_BOOTSTRAP_CONNECTION_STAGING.sql` setelah mengisi variabel:

- `@crawler_url = 'http://10.13.13.90:8001'`
- `@token = token staging yang baru diterbitkan`
- `@company = 1`

Script hanya boleh mengubah Connection 985 dan 986. Setelah itu, dari sisi
OneBox jalankan `whoami`; hasil wajib menunjukkan company staging, bukan company
3 milik dev.

## Verifikasi berurutan

1. `curl http://127.0.0.1:8001/api/health` menghasilkan HTTP 200 dan database OK.
2. Dari host OneBox staging, `curl http://10.13.13.90:8001/api/health` berhasil.
3. `whoami` dari OneBox mengembalikan tenant staging.
4. Refresh worklist menghasilkan dua lokasi, tanpa fallback ke cache dev.
5. Jalankan fetch satu lokasi dengan target 1 terlebih dahulu.
6. Poll batch hingga terminal; job harus `succeeded` atau `partial_success`.
7. Pull review dari OneBox dan cocokkan `onebox_location_id` ke lokasi staging.
8. Ulangi target 10 hanya setelah pengujian target 1 lolos.

## Rollback

Rollback crawler tidak menyentuh port 8000:

```bash
docker compose --env-file .env.staging-1123 \
  -p voc-staging-1123 \
  -f docker-compose.staging-1123.yml down
```

Kembalikan Connection 985/986 ke `mock=true` dari OneBox jika UI harus segera
dipulihkan. Jangan hapus database staging sebelum bukti crawl dan audit token
diamankan.

## Handoff untuk Claude (OneBox)

Claude mengerjakan boundary OneBox berikut:

1. Jalankan diagnosis menu dan permission sebelum migration runner.
2. Pulihkan menu memakai migration aplikasi, lalu buktikan 27 menu VoC unik,
   tepat satu `HEADERMENU`, dan permission tidak nol.
3. Buat atau validasi akun service staging untuk SiteId 169 dan endpoint
   `/api/VocWorklist`; kirim kredensial melalui secret channel.
4. Uji koneksi keluar dari host OneBox ke `10.13.13.90:8001`.
5. Setelah token tersedia, update hanya Connection 985/986 dengan URL, token,
   company id, dan `mock=false`; jangan membawa TargetId dev.
6. Jalankan `whoami`, refresh worklist, fetch target 1, polling, dan import review.
7. Laporkan HTTP status, batch id, location id, jumlah fetched/imported, dan
   error code tanpa menampilkan token atau password.
