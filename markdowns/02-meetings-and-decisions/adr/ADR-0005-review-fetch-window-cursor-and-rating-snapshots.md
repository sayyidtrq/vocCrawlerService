# ADR-0005 - Review Fetch Window, Cursor, and Rating Snapshots

Status: Proposed
Date: 2026-09-01

## Context

Fetch Review VoC saat ini masih cenderung count-first: user memilih jumlah ulasan dan crawler berhenti ketika jumlah scan atau target tertentu terpenuhi. QA menemukan model ini tidak cocok untuk Google Maps review karena source disisir newest-first dan data sering overlap dengan scheduler/manual sebelumnya.

Masalah yang muncul:

- Target count rawan menghasilkan duplicate.
- Rentang tanggal tertentu bisa berisi review lebih sedikit dari target.
- Pengambilan review historis harus melewati banyak review baru yang sudah pernah disimpan.
- Manual fetch dan scheduler dapat overlap.
- KPI rating trend tidak bisa dipercaya tanpa snapshot rating berkala.

ADR sebelumnya tetap berlaku:

- ADR-0003: OneBox adalah control plane; Crawler menarik worklist dan menjalankan crawl.
- ADR-0004: Review harus cepat masuk DB Crawler, OneBox pull raw review, labeling native OneBox, AI on-demand async.

## Decision

Fetch Review akan menggunakan prinsip window-first dan cursor-aware.

1. `location`, `source`, `date_range`, `crawl_mode`, dan cursor menjadi dasar crawl.
2. `target_review_count` tidak lagi diperlakukan sebagai janji jumlah review baru. Field ini menjadi safety limit/chunk size dengan label UI yang lebih jujur.
3. Setiap target crawl menyimpan state terpisah:
   - `last_successful_crawl_at`
   - `last_seen_review_time`
   - `oldest_scanned_review_time`
   - `first_run_completed_at`
   - `cursor_source_review_id`
4. Crawl dibagi menjadi mode:
   - `initial_backfill`
   - `regular_delta`
   - `custom_range`
5. Manual fetch dan scheduler memakai lock/idempotency per tenant, source, target, mode, dan date window agar tidak menjalankan target yang sama secara paralel.
6. Dedupe adalah metric normal dan tidak otomatis membuat job gagal.
7. Rating trend memakai rating snapshot berkala:
   - `google_rating`
   - `google_review_count`
   - `snapshot_at`
   - `source`
   - `target_id`
8. OneBox tetap bertanggung jawab atas UX, business grouping, RUD/Kelola Review, sentiment native, ticket, dan KPI. Crawler bertanggung jawab atas source discovery, raw crawl, dedupe source, cursor, dan metadata teknis.

## Consequences

Positif:

- Fetch review lebih mudah dijelaskan ke user.
- Scheduler dan manual fetch tidak saling tabrak.
- Review historical dapat di-backfill bertahap.
- Trend rating bisa dihitung dari snapshot yang benar.
- Status job menjadi lebih informatif: scanned, matched, inserted, duplicate, out of range, has more.

Trade-off:

- Butuh migrasi kecil pada state target/job.
- Butuh update kontrak API dan wording UI.
- Crawler masih tidak bisa "lompat" langsung ke review lama jika Google Maps tidak menyediakan cursor publik; sistem tetap perlu menyisir review terbaru terlebih dahulu.

## Rejected Alternatives

### Tetap Count-First

Ditolak karena tidak menyelesaikan duplicate, overlap scheduler, dan misleading untuk user.

### Semua Algoritma Dipindah ke OneBox

Ditolak karena OneBox tidak melakukan scraping dan tidak memegang detail cursor Google Maps. OneBox cukup mengatur scope bisnis dan menampilkan hasil.

### Semua Processing Dipindah ke Crawler

Ditolak karena Kelola Review, sentiment native, ticket, permission, dan KPI adalah domain OneBox.

## Open Questions

1. Nama final field API: tetap `target_review_count` atau migrasi bertahap ke `max_reviews_to_collect`.
2. Batch size backfill default: 300, 400, atau 500.
3. Retensi rating snapshot: semua disimpan permanen atau diringkas per periode.
4. Apakah custom date range boleh mengabaikan cursor regular delta.

## Acceptance Criteria

- Kontrak Fetch Jobs membedakan mode `initial_backfill`, `regular_delta`, dan `custom_range`.
- UI tidak lagi menjanjikan jumlah review baru berdasarkan target count.
- Crawler menyimpan cursor dan snapshot per target.
- Manual dan scheduler tidak bisa menjalankan target/window yang sama secara paralel tanpa explicit force.
- Job history menampilkan duplicate dan out-of-range sebagai metric normal.
- Rating trend mengambil data dari snapshot, bukan perkiraan dari review yang kebetulan masuk.
