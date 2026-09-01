# Runbook - VOC Fetch Logic E2E Test Plan

Status: Draft
Tujuan: Membuktikan Fetch Review bekerja end-to-end setelah refactor window/cursor.

## Precondition

- OneBox dev bisa login.
- Crawler service reachable dari OneBox.
- Token service memiliki scope:
  - `reviews:read`
  - `crawl:enqueue`
  - `crawl:read`
- Worklist sudah refresh setelah lokasi ditambah.
- Selenium profile sudah login Google jika target membutuhkan login.

## Test 1 - Setup Lokasi Baru

Langkah:

1. Tambahkan lokasi di OneBox.
2. Isi nama, source Google, dan Place ID.
3. Simpan.
4. Refresh worklist ke Crawler.
5. Cek lokasi muncul di Crawler worklist.

Expected:

- Lokasi aktif di OneBox.
- Lokasi aktif di Crawler.
- Tidak ada duplicate active worklist untuk target yang sama.

## Test 2 - Initial Backfill Kecil

Payload contoh:

```json
{
  "source": "google_maps",
  "crawl_mode": "initial_backfill",
  "targets": [
    {
      "location_id": "169:LOC-001",
      "external_place_id": "ChIJ...",
      "name": "Five Coffee Forest"
    }
  ],
  "date_range": {
    "from": "2026-08-01",
    "to": "2026-09-01"
  },
  "max_reviews_to_collect": 50,
  "scan_limit": 300,
  "dry_run": false
}
```

Expected:

- Job status `queued`, lalu `running`.
- Crawler membuat rating snapshot.
- Crawler menyimpan raw review baru jika ada.
- Jika hasil kurang dari 50, job tetap sukses dengan stop reason jelas.

## Test 3 - Regular Delta Setelah Backfill

Langkah:

1. Jalankan fetch mode `regular_delta` untuk lokasi yang sama.
2. Gunakan date range dari last seen review sampai hari ini.
3. Pantau counters.

Expected:

- Duplicate mungkin tinggi, tetapi job tidak hard failed.
- `last_successful_crawl_at` terupdate.
- `last_seen_review_time` tidak mundur.

## Test 4 - Duplicate Heavy

Langkah:

1. Jalankan ulang regular delta di lokasi yang sama.
2. Jangan ubah date range.

Expected:

- `duplicate` > 0.
- `inserted` bisa 0.
- Job selesai dengan `stop_reason=duplicate_streak`, `target_reached`, atau `older_than_window`.
- UI menampilkan "tidak ada review baru" dengan counters.

## Test 5 - Custom Date Range Lama

Langkah:

1. Pilih rentang tanggal lama.
2. Jalankan dengan scan limit terbatas.

Expected:

- Sistem menyisir review terbaru dulu.
- Jika belum sampai range lama, status menjelaskan `scan_limit_reached` dan `has_more=true`.
- User tidak diberi kesan sistem gagal hanya karena belum mencapai review lama.

## Test 6 - Overlap Manual vs Scheduler

Langkah:

1. Buat scheduler untuk target A.
2. Saat scheduler queued/running, jalankan manual fetch target A dengan window sama.

Expected:

- Sistem mengembalikan job existing atau menolak dengan pesan jelas.
- Tidak ada dua worker menjalankan target/window sama secara paralel.

## Test 7 - OneBox Pull Raw Review

Langkah:

1. Setelah crawler selesai, jalankan pull raw review dari OneBox.
2. Cek data masuk ke DB OneBox.
3. Buka Kelola Review.

Expected:

- Review baru muncul di Kelola Review.
- Review duplicate tidak membuat row ganda.
- Sentiment native OneBox berjalan.

## Test 8 - AI Async Dari Kelola Review

Langkah:

1. Pilih satu review.
2. Klik analisis AI dari detail review.
3. Pantau job analysis.
4. Cek hasil balik ke review atau Ticket existing.

Expected:

- Analysis job dibuat async.
- UI tidak blocking.
- Hasil mengupdate review/Ticket existing.

## Evidence Yang Harus Disimpan

- Screenshot request UI.
- Batch ID/job ID.
- Response create job.
- Status job akhir.
- Counter akhir.
- Screenshot Kelola Review setelah pull.
- Screenshot sentiment native.
- Screenshot hasil AI jika diuji.

## Fail Fast Checklist

Jika job gagal:

1. Cek Crawler health.
2. Cek token scope.
3. Cek worklist target ada dan aktif.
4. Cek Place ID valid.
5. Cek Selenium profile login.
6. Cek worker running.
7. Cek apakah ada job overlapping.
8. Cek logs untuk stop reason atau exception asli.
