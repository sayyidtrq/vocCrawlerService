# Plan - Fetch Review UI and Rating Trend

Status: Draft implementation plan
Owner utama: OneBox
Pairing: Crawler untuk contract, counters, dan snapshot

## Goal

Menyederhanakan UI Fetch Review agar sesuai kemampuan teknis crawler dan tidak menyesatkan user. UI harus menjelaskan bahwa sistem menyisir review berdasarkan lokasi dan rentang waktu, sementara jumlah review adalah batas pengambilan.

## Prinsip UX

1. User memilih apa yang ingin dicapai, bukan parameter teknis Selenium.
2. Sistem harus jujur jika hasil baru kurang dari batas pengambilan.
3. Duplicate dan out-of-range ditampilkan sebagai hasil scan normal.
4. Progress job harus terlihat tanpa refresh manual.
5. Manual fetch tidak boleh diam-diam overlap dengan scheduler.

## Mode Fetch

### Update Terbaru

Default untuk operasional harian.

Field:

- Lokasi
- Rentang otomatis dari `last_seen_review_time` sampai hari ini
- Batas pengambilan, default 50

Copy UI:

- "Ambil ulasan terbaru sejak penarikan terakhir."
- "Jumlah adalah batas pengambilan, bukan jaminan ulasan baru."

### Backfill Awal

Untuk lokasi baru atau data historis belum lengkap.

Field:

- Lokasi
- Rentang awal
- Batch size: 300 sampai 500, bisa disembunyikan sebagai advanced setting

Copy UI:

- "Ambil riwayat ulasan bertahap. Jika data banyak, sistem akan membuat batch lanjutan."

### Rentang Khusus

Untuk audit atau recovery.

Field:

- Lokasi
- Dari tanggal
- Sampai tanggal
- Batas pengambilan
- Rating filter jika dibutuhkan

Copy UI:

- "Crawler tetap menyisir dari ulasan terbaru Google. Rentang lama mungkin membutuhkan scan lebih panjang."

## Layout Fetch Review

### Section Form

Urutan field:

1. Mode fetch
2. Lokasi
3. Rentang tanggal
4. Batas pengambilan
5. Filter rating
6. Action `Mulai`

Action sekunder:

- `Tambah ke antrean`
- `Dry run` hanya untuk admin/dev jika dibutuhkan

### Status Lokasi

Saat lokasi dipilih, tampilkan:

| Informasi | Sumber |
| --- | --- |
| Place ID | Master lokasi/Connection |
| Last successful crawl | Crawler state |
| Last seen review date | Crawler state |
| First run status | Crawler state |
| Scheduler aktif | OneBox scheduler |

### Riwayat Fetch

Kolom wajib:

| Kolom | Tujuan |
| --- | --- |
| Waktu | Kapan job dibuat |
| Cabang | Target bisnis |
| Mode | Update terbaru, Backfill, Rentang khusus |
| Batch | Trace ke crawler batch |
| Status | Queued/running/succeeded/partial/failed |
| Scan | Total disisir |
| Cocok / Batas | Review masuk filter dibanding batas |
| Baru | Inserted ke DB Crawler |
| Duplikat | Review sudah ada |
| Di luar rentang | Review tidak masuk window |
| Stop reason | Kenapa job berhenti |
| Aksi | Detail, ulangi, cancel jika running |

### Detail Job

Detail job perlu menampilkan:

- Request payload yang dikirim OneBox.
- Response Crawler.
- Timeline status.
- Counter lengkap.
- Error message asli jika ada.
- Link ke review yang berhasil masuk jika tersedia.

## Progress Bar

Progress tidak boleh hanya spinner.

Tampilkan:

- Status: Mengantre, Berjalan, Menyimpan, Selesai, Sebagian gagal, Gagal.
- Current counters: scanned, matched, inserted, duplicate.
- Estimasi sederhana: `scanned / scan_limit`.
- Jika scan limit tidak diketahui, gunakan indeterminate progress plus counter live.

## Rating Trend

Kebutuhan stakeholder:

- Melihat rating cabang minggu lalu vs minggu ini.
- Melihat perubahan rating bulanan, kuartalan, tahunan.

Masalah:

- Rating Google saat ini tidak bisa direkonstruksi akurat hanya dari review yang masuk.
- Average rating review internal bukan hal yang sama dengan rating Google official.

Solusi:

Crawler mengirim rating snapshot setiap job:

```json
{
  "target_id": "169:LOC-001",
  "source": "google_maps",
  "google_rating": 4.5,
  "google_review_count": 9422,
  "snapshot_at": "2026-09-01T08:00:00+07:00",
  "crawl_job_id": "uuid"
}
```

OneBox menyimpan snapshot dan menampilkan trend:

| Tab | Isi |
| --- | --- |
| Mingguan | Rating snapshot per minggu, delta dari minggu sebelumnya |
| Bulanan | Rating snapshot per bulan, delta dari bulan sebelumnya |
| Kuartalan | Ringkasan per kuartal |
| Tahunan | Trend high-level per tahun |

## Empty/Error State

Gunakan pesan yang actionable:

- "Belum ada baseline. Jalankan Backfill Awal untuk lokasi ini."
- "Job sedang berjalan untuk lokasi ini. Buka detail job atau tunggu selesai."
- "Tidak ada review baru. Crawler menyisir X review dan menemukan Y duplikat."
- "Google meminta login. Perbarui Selenium profile lalu jalankan ulang."
- "Worklist belum segar. Refresh worklist setelah menambah lokasi."

## Validation Rules

- Lokasi wajib punya `external_place_id` atau resolvable name.
- Date from tidak boleh lebih besar dari date to.
- Batas pengambilan maksimal 300 untuk manual regular/custom.
- Backfill memakai batch size maksimal 500.
- Jika ada job running target/window sama, tombol `Mulai` disabled atau diarahkan ke job existing.

## Definition of Done

- User paham kenapa hasil baru bisa kurang dari batas pengambilan.
- Duplicate tidak terlihat sebagai error.
- Job progress bisa dipantau.
- Rating trend memakai snapshot.
- Fetch Review tetap mengarah ke flow final: Crawler raw DB -> OneBox pull -> Kelola Review -> AI async.
