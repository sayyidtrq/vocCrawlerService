# Resolusi Worklist Setelah Seeding Lokasi Banyak

Tanggal investigasi: 2026-08-28  
Lingkungan: Crawler staging, `company_id=3`, `site_id=169`

## Ringkasan

Setelah penambahan banyak lokasi di OneBox, tombol run jadwal dapat gagal dengan pesan bahwa cabang belum dikenal Crawler. Penyebab yang ditemukan bukan koneksi WireGuard, bukan token, dan bukan worker mati. Penyebabnya adalah refresh worklist dari OneBox ke Crawler gagal karena payload worklist berisi duplicate `external_place_id`.

Satu baris duplicate membuat seluruh proses sync ditolak, sehingga lokasi baru yang sebenarnya valid belum masuk ke cache `locations` Crawler. Akibatnya endpoint `POST /api/integration/v1/crawl-jobs` mengembalikan `404 TARGET_NOT_FOUND`.

## Gejala

Di OneBox:

- Toast: `Run belum dimulai`
- Pesan menjelaskan Crawler menolak cabang dan menyarankan refresh worklist atau cek master lokasi.
- Jadwal yang memakai lokasi baru hasil seeding tidak bisa dimulai.

Di log API Crawler:

```text
OneBox worklist sync failed for company_id=3 site_id=169:
Duplicate worklist item: location/<external_place_id>.

refresh worklist otomatis gagal untuk [923, 924, ...]:
Duplicate worklist item: location/<external_place_id>.

POST /api/integration/v1/crawl-jobs HTTP/1.1" 404 Not Found
```

## Root Cause

Worklist OneBox mengirim lebih dari satu item `kind=location` dengan `external_place_id` yang sama.

Kasus yang ditemukan:

| External Place ID | Baris 1 | Baris 2 | Dampak |
| --- | --- | --- | --- |
| `ChIJf7JjNY_raS4Rn-bJQO0X2FU` | `RSUD ASA` / location `949` / connection `1063` | `RSUD ANUGERAH SEHAT AFIAT` / location `979` / connection `1093` | Duplicate target Google yang sama |
| `ChIJa2cQy-foaS4R591h7Il1NlA` | `RSUD KISA` / location `950` / connection `1064` | `RSUD KHIDMAT SEHAT AFIAT` / location `980` / connection `1094` | Duplicate target Google yang sama |

Crawler sebelumnya strict: duplicate worklist langsung dianggap invalid dan sync berhenti total. Itu membuat lokasi lain yang tidak duplicate ikut belum tersinkron.

## Perbaikan Yang Dilakukan

Crawler diubah agar duplicate worklist tidak menjatuhkan seluruh sync.

Perilaku baru:

- Item pertama untuk kombinasi `kind + external_place_id` dipakai.
- Item duplicate berikutnya di-skip.
- Refresh tetap sukses.
- Warning tetap dicatat supaya data duplicate di OneBox bisa dibersihkan.

Contoh hasil refresh setelah perbaikan:

```json
{
  "status": "synced",
  "company_id": 3,
  "site_id": 169,
  "fetched": 114,
  "upserted": 114,
  "deactivated": 0,
  "cache_age_seconds": 0,
  "warning": "Duplicate worklist item skipped: ..."
}
```

Setelah refresh sukses, lokasi baru `923` sampai `947` sudah masuk ke Crawler dan berstatus aktif.

## Verifikasi Yang Sudah Dilakukan

Smoke test melalui endpoint integrasi yang sama dengan OneBox:

- Endpoint: `POST /api/integration/v1/crawl-jobs`
- Target: `onebox_location_id=923`
- Target review: `1`
- Hasil enqueue: `202 Accepted`
- Batch: `1b7917c1-fd06-4ab4-a07d-e3399b78d134`
- Hasil worker: `completed`
- Review count: `target=1`, `fetched=1`, `inserted=1`, `duplicate=0`, `failed=0`

Artinya jalur berikut sudah terbukti:

```text
OneBox target location
-> Crawler API enqueue
-> worker mengambil job
-> Selenium crawl
-> review tersimpan di DB Crawler
```

## Prosedur Setelah Menambah Lokasi

Jalankan ini di server Crawler setelah seeding lokasi banyak di OneBox:

```bash
cd ~/herminaCrawler
docker compose exec -T api python -m scripts.refresh_worklist --company-id 3 --json
```

Output yang sehat:

```json
{
  "status": "synced",
  "company_id": 3,
  "site_id": 169,
  "fetched": 100,
  "upserted": 100,
  "deactivated": 0,
  "cache_age_seconds": 0,
  "warning": null
}
```

Kalau `warning` berisi duplicate, jadwal untuk lokasi lain tetap bisa jalan, tetapi data duplicate tetap perlu dibersihkan di OneBox.

## Command Cek Cepat

Cek service:

```bash
cd ~/herminaCrawler
docker compose ps
curl -fsS http://127.0.0.1:8000/api/health
```

Cek state worklist:

```bash
cd ~/herminaCrawler
docker compose exec -T api python -c "from app.db.session import get_session_factory; from app.db.models import Location, WorklistSyncState; from sqlalchemy import select, func; s=get_session_factory()(); st=s.scalar(select(WorklistSyncState).where(WorklistSyncState.company_id==3)); print({'item_count': getattr(st,'item_count',None), 'last_success_at': str(getattr(st,'last_success_at',None)), 'last_error': getattr(st,'last_error',None)}); print({'total': s.scalar(select(func.count()).select_from(Location).where(Location.company_id==3)), 'eligible': s.scalar(select(func.count()).select_from(Location).where(Location.company_id==3, Location.is_active.is_(True), Location.crawl_enabled.is_(True), Location.ingest_reviews.is_(True)))})"
```

Cek apakah target lokasi sudah dikenal Crawler:

```bash
cd ~/herminaCrawler
docker compose exec -T api python -c "from app.db.session import get_session_factory; from app.db.models import Location; from sqlalchemy import select; ids=[923,924,925,926,930,931,932,933,934,935,936,937,938,939,940,941,942,943,944,945,946,947]; s=get_session_factory()(); rows=s.execute(select(Location.onebox_location_id, Location.branch_name, Location.is_active, Location.crawl_enabled, Location.ingest_reviews).where(Location.company_id==3, Location.onebox_location_id.in_(ids)).order_by(Location.onebox_location_id)).all(); [print(tuple(r)) for r in rows]"
```

## Tindak Lanjut Data OneBox

Duplicate `external_place_id` harus tetap dibereskan di master data OneBox.

Aturan yang disarankan:

- Satu physical Google Business Place hanya boleh punya satu `external_place_id` aktif per `kind=location` dalam satu tenant.
- Kalau dua nama menunjuk tempat yang sama, pilih satu canonical Connection dan nonaktifkan/ubah yang lain.
- Kalau dua lokasi memang berbeda, isi `external_place_id` yang benar untuk masing-masing lokasi.
- Setelah koreksi OneBox, jalankan ulang `scripts.refresh_worklist`.

## Catatan Desain

Crawler sengaja tidak membuat dua `Location` untuk satu `external_place_id` yang sama. Review Google berasal dari satu tempat, sehingga kalau satu Place ID dipakai dua cabang, sistem tidak bisa menentukan review itu milik cabang yang mana dengan aman.

Karena itu perbaikan crawler hanya mencegah seluruh sync gagal. Ia bukan pengganti pembersihan data duplicate di OneBox.

