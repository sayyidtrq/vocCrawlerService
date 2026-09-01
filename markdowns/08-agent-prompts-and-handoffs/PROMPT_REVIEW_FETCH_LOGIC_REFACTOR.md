# Prompt - Review Fetch Logic Refactor

Gunakan prompt ini untuk Claude/Codex agent yang mengerjakan refactor Fetch Review.

## Context

Kita sedang memperbaiki logika Fetch Review VoC. Problem utama: implementasi sekarang terlalu count-first sehingga rawan duplicate, sulit backfill review lama, overlap dengan scheduler/manual, dan belum cukup kuat untuk rating trend.

Baca dokumen berikut dulu:

1. `markdowns/00-start-here/MUST_READ.md`
2. `markdowns/00-start-here/VOC_FETCH_LOGIC_TOP_DOWN.md`
3. `markdowns/02-meetings-and-decisions/adr/ADR-0003-crawl-execution-pull-queue.md`
4. `markdowns/02-meetings-and-decisions/adr/ADR-0004-fast-ingestion-labeling-on-demand-ai.md`
5. `markdowns/02-meetings-and-decisions/adr/ADR-0005-review-fetch-window-cursor-and-rating-snapshots.md`
6. `markdowns/04-implementation-plans/crawler-system/PLAN_REVIEW_FETCH_LOGIC_REFACTOR.md`

## Target Architecture

- OneBox adalah control plane dan entry point user.
- Crawler adalah execution plane untuk Google Maps crawl.
- Review cepat masuk DB Crawler.
- OneBox pull raw review.
- OneBox menyimpan review, menjalankan labeling sentiment native, dan menyediakan Kelola Review.
- AI analysis berjalan async setelah user memilih single/bulk review.

## Main Task

Implementasikan Fetch Review agar window-first dan cursor-aware:

1. Tambahkan mode crawl:
   - `initial_backfill`
   - `regular_delta`
   - `custom_range`
2. Jadikan `target_review_count` backward compatible, tetapi secara internal perlakukan sebagai `max_reviews_to_collect`.
3. Tambahkan `scan_limit`, `stop_reason`, `has_more`, dan counters lengkap.
4. Simpan cursor/state per target:
   - `last_successful_crawl_at`
   - `last_seen_review_time`
   - `oldest_scanned_review_time`
   - `first_run_completed_at`
   - `cursor_source_review_id`
5. Tambahkan lock/idempotency agar manual dan scheduler tidak overlap pada target/window yang sama.
6. Tambahkan rating snapshot dari Google Maps setiap crawl.

## Important Rules

- Duplicate bukan otomatis failure.
- Date range dengan hasil kurang dari target tetap bisa sukses.
- Jangan memindahkan business logic Kelola Review ke Crawler.
- Jangan membangun rule sentiment baru; OneBox sudah punya native labeling.
- Jangan membuat AI analysis blocking crawl.
- Jangan mengubah public contract secara breaking tanpa backward compatibility.

## Tests Required

- Backward compatibility `target_review_count`.
- New payload `max_reviews_to_collect`.
- Duplicate-heavy job.
- Date range dengan hasil kurang dari target.
- Lock/idempotency same target/window.
- Backfill scan limit menghasilkan `has_more=true`.
- Rating snapshot dibuat.

## Deliverables

- Code changes.
- Migration jika ada field baru.
- Unit/integration tests.
- Update API docs.
- Short summary untuk OneBox team:
  - endpoint contract
  - status lifecycle
  - counters
  - UI copy implication
  - rollback note
