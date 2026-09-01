# Plan - Review Fetch Logic Refactor

Status: Draft implementation plan
Owner utama: Crawler System
Pairing: OneBox team untuk contract dan UI

## Goal

Membuat crawler lebih reliable untuk Fetch Review, Scheduler, dan demo key process VoC dengan mengubah logika dari count-first menjadi window-first, cursor-aware, dan overlap-safe.

## Non Goal

- Tidak membangun ulang fitur Kelola Review di Crawler.
- Tidak memindahkan ownership scheduler UI dari OneBox ke Crawler.
- Tidak membuat rule sentiment baru.
- Tidak menjamin Google Maps dapat langsung lompat ke review historis tanpa scanning.

## P0 - Audit State Saat Ini

Checklist:

- Identifikasi tabel target/location di Crawler.
- Identifikasi tabel crawl job/batch/fetch log.
- Cek field yang sudah ada untuk `last_fetched_at`, status, duplicate, scanned, inserted.
- Cek endpoint `POST /api/integration/v1/crawl-jobs`.
- Cek endpoint status job dan review delta.
- Cek worker lock/antrian saat job dibuat dari scheduler/manual.

Output:

- Matrix field existing vs field baru.
- Daftar migrasi minimal.
- Keputusan apakah field state masuk tabel location, tabel baru, atau metadata JSON.

## P1 - Data Model

Tambahkan atau normalisasi state per target crawl:

| Field | Scope | Tujuan |
| --- | --- | --- |
| `first_run_completed_at` | target | Menandai backfill baseline sudah pernah selesai |
| `last_successful_crawl_at` | target | Waktu job terakhir sukses |
| `last_seen_review_time` | target | Review terbaru yang terlihat di source |
| `oldest_scanned_review_time` | target/job | Review terlama yang tersisir |
| `cursor_source_review_id` | target/job | Continuation/dedupe anchor |
| `crawl_mode` | job | `initial_backfill`, `regular_delta`, `custom_range` |
| `scan_limit` | job | Batas keamanan scraping |
| `target_match_count` | job | Target review dalam window, bukan janji inserted |
| `stop_reason` | job | Kenapa job berhenti |
| `has_more` | job | Apakah backfill masih bisa dilanjutkan |

Rating snapshot:

| Field | Tujuan |
| --- | --- |
| `target_id` | Lokasi/cabang/kompetitor |
| `source` | `google_maps` |
| `google_rating` | Rating saat crawl |
| `google_review_count` | Total review saat crawl |
| `snapshot_at` | Waktu snapshot dibuat |
| `crawl_job_id` | Trace ke job |

## P2 - API Contract

Request create crawl job:

```json
{
  "source": "google_maps",
  "crawl_mode": "regular_delta",
  "targets": [
    {
      "location_id": "169:LOC-001",
      "external_place_id": "ChIJ...",
      "name": "Hermina Depok"
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

Backward compatibility:

- Jika OneBox masih mengirim `target_review_count`, map ke `max_reviews_to_collect`.
- Jika `crawl_mode` kosong, gunakan:
  - `initial_backfill` jika target belum punya `first_run_completed_at`
  - `regular_delta` jika target sudah punya state

Response:

```json
{
  "batch_id": "uuid",
  "status": "queued",
  "accepted_targets": 1,
  "reused_existing_job": false,
  "limits": {
    "max_reviews_to_collect": 50,
    "scan_limit": 300
  }
}
```

## P3 - Selenium Crawl Algorithm

### Regular Delta

1. Buka Google Maps target.
2. Sort newest jika memungkinkan.
3. Ambil rating dan review count snapshot.
4. Scroll review list.
5. Untuk setiap review:
   - parse reviewer, rating, text, review time, source id/hash
   - jika review lebih baru dari `date_range.to`, skip as out_of_range_newer
   - jika review masuk date range, coba insert/upsert
   - jika duplicate, increment duplicate
   - jika review lebih lama dari `date_range.from`, stop dengan `older_than_window`
6. Stop jika:
   - matched mencapai `max_reviews_to_collect`
   - scan mencapai `scan_limit`
   - duplicate streak mencapai threshold
   - timeout
   - halaman tidak menambah item
7. Update target cursor jika job valid.

### Initial Backfill

1. Mulai dari newest.
2. Gunakan batch 300 sampai 500 scan/review.
3. Jangan anggap selesai jika `scan_limit` tercapai.
4. Simpan `has_more=true` dan cursor untuk lanjut.
5. Tandai `first_run_completed_at` hanya jika:
   - window historis terpenuhi, atau
   - source tidak lagi memberi review baru setelah scroll stabil.

### Custom Range

1. Hormati date range user.
2. Jangan update cursor regular delta secara agresif kecuali job sukses penuh.
3. Tampilkan out-of-range dan duplicate secara eksplisit.

## P4 - Lock, Idempotency, dan Overlap Control

Lock key:

```text
tenant_id + source + target_id + crawl_mode + normalized_date_window
```

Policy:

- Jika ada job queued/running untuk key yang sama, return job existing.
- Scheduler tidak boleh membuat job target yang sedang manual running.
- Manual run boleh dibuat untuk target yang sama hanya jika window berbeda atau `force=true`.
- `Idempotency-Key` dari OneBox wajib disimpan.

## P5 - Counters dan Status

Job status:

- `queued`
- `running`
- `succeeded`
- `partially_failed`
- `failed`
- `cancelled`
- `expired`

Counters:

| Counter | Arti |
| --- | --- |
| `scanned` | Review card yang berhasil dibaca dari Google |
| `matched` | Review yang masuk filter tanggal/rating/source |
| `inserted` | Review baru masuk DB Crawler |
| `duplicate` | Review sudah ada |
| `out_of_range_newer` | Review di atas batas tanggal |
| `out_of_range_older` | Review di bawah batas tanggal |
| `failed_items` | Review gagal parse/insert |
| `snapshots_created` | Snapshot rating tersimpan |

Stop reason:

- `target_reached`
- `older_than_window`
- `scan_limit_reached`
- `duplicate_streak`
- `timeout`
- `no_more_reviews`
- `blocked_by_google_login`
- `target_not_found`

## P6 - Tests

Minimal automated tests:

- Create job dengan `target_review_count` lama tetap kompatibel.
- Create job dengan `max_reviews_to_collect` baru.
- Duplicate-heavy run tetap `succeeded` atau `partially_failed`, bukan hard failed.
- Date range berisi review kurang dari target tetap sukses dengan stop reason jelas.
- Running lock mengembalikan existing batch.
- Backfill yang kena scan limit menghasilkan `has_more=true`.
- Rating snapshot dibuat saat crawl job berjalan.

## P7 - Rollout

1. Deploy backward-compatible contract.
2. Update OneBox UI label dan payload.
3. Jalankan satu target kecil sebagai smoke test.
4. Jalankan satu target duplicate-heavy.
5. Jalankan satu initial backfill terbatas.
6. Aktifkan scheduler setelah state target valid.

## Definition of Done

- Job tidak gagal hanya karena duplicate tinggi.
- Manual dan scheduler tidak overlap untuk target/window sama.
- History menjelaskan kenapa hasil baru bisa kurang dari target.
- Rating snapshot tersedia untuk target yang dicrawl.
- OneBox tetap bisa pull raw review dan Kelola Review langsung usable.
