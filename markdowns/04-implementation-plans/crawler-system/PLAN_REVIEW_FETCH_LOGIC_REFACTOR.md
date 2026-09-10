# Plan - Review Fetch Logic Refactor

Status: In progress - sebagian besar perbaikan kontrak, stop reason, dedupe, dan rating snapshot sudah merged ke `main`
Owner utama: Crawler System
Pairing: OneBox team untuk contract dan UI
Last update: 2026-09-01

## Progress Update - 2026-09-01

Branch Crawler yang sudah masuk `main`:

| PR | Commit | Isi utama | Status |
| --- | --- | --- | --- |
| #9 | `81b1e0e` | Window-aware crawl job: `crawl_mode`, `max_reviews_to_collect`, `scan_limit`, date range, counters dasar, active job reuse | Merged + deployed |
| #10 | `79e2a8a` / `ebf3543` | Google rating snapshot dari Selenium dan expose ke detail batch | Merged + deployed |
| #11 | `0c3c1b3` / `0ce172e` | Stable Selenium review identity, legacy external-id dedupe, batch-level `stop_reason` dan `stop_reasons` | Merged + deployed |

Verifikasi server pada 2026-09-01:

- Server `ciptadra-svr` sudah di `main` commit `0c3c1b3`.
- `hermina-review-api` healthy.
- `hermina-crawl-worker` running dengan headed Chromium di virtual display.
- `http://127.0.0.1:8000/api/health` dan `http://10.13.13.90:8000/api/health` mengembalikan `200 OK`.
- Smoke endpoint `/api/integration/v1/crawl-jobs?limit=3` berhasil dan response list sudah memuat `stop_reason` + `stop_reasons`.
- Automated tests Crawler: `115 passed`.

Ringkasan status:

| Area                   | Status                    | Catatan                                                                                                                                                                                     |
| ---------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P0 audit existing      | Done                      | Endpoint, worker, model, worklist, dan gap contract sudah diaudit selama debugging fetch jobs.                                                                                              |
| P1 contract/payload    | Done untuk kebutuhan demo | Payload lama `target_review_count` tetap kompatibel; payload baru mendukung `max_reviews_to_collect`, `scan_limit`, `crawl_mode`, dan date range.                                           |
| P3 crawl algorithm     | Partial done              | Stop by target, scan limit, date window, timeout/no more review, sort warning, counters dasar sudah ada. Duplicate streak eksplisit belum dibuat.                                           |
| P4 lock/idempotency    | Partial done              | `Idempotency-Key` dan active batch reuse untuk target/window tunggal sudah ada. Lock granular manual-vs-scheduler lintas seluruh mode masih perlu hardening.                                |
| P5 rating snapshot     | Done                      | Snapshot Google diambil dari header Maps, tidak menggagalkan crawl, tersimpan di metadata, dan expose ke detail batch. OneBox sudah consume.                                                |
| P6 counters/status     | Partial done              | Job detail dan batch list sudah punya counters + `stop_reason`; histogram `stop_reasons` tersedia untuk batch campuran. Standard status final belum sepenuhnya selaras dengan istilah plan. |
| P2 cursor/target state | Not started               | Watermark durable di Crawler (`last_seen_review_id`, `first_run_completed_at`, dll.) belum dibuat. OneBox sementara memakai watermark dari data sendiri.                                    |
| P7 E2E proof           | Partial                   | Smoke API dan real historical batch terbaca. Proof penuh OneBox import -> Kelola Review -> rating trend masih perlu dijalankan setelah sisi OneBox selesai deploy/migrasi.                  |

**Findings** 
- Schedule jalan namun ulasan yang masuk lewat scheduler kenapa tidak terekam di rating snapshot ? contoh 1 september scheduler eka hospital margonda nyala namun tidak saat di lihat visualisaisnya di chart bagian tren , belum ada snapshot yang amsuk sama sekali saat memilih eka hospital margonda. sebenernya ini tidak tahu ya masalah UI , menempatan dataa ke UI, atau BE (cek lebih lanjut lagi)
- Kerjakan yang lainnya secara bertahap
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

**Findings** :

- U forgot the most important thing. Definition of done dalam segi User Interface dan user experience. Reflecting basaed on my story perlu ada DoD yang memang khusus untuk ui/ux apakah sudah mengarahkan user untuk melakukan fetch review yang benar dan layout serta komponen - komponen yang intuitif. sebenernya ini salah satu alesan gua bilang ulasan sepertinya dihilangkan aja ya. Lalu pemberitahuan seperti first run dan scheduler, autofill form based on the rules, and form validation jika kurang
