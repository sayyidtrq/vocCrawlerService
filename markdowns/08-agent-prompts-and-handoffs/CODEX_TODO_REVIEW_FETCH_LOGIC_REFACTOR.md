# Codex Todo Scope - Review Fetch Logic Refactor

Status: Draft kerja Codex
Tanggal: 2026-09-01
Modul besar: VoC Fetch Review / Fetch Jobs Crawl

## Tujuan Codex

Codex fokus pada sisi Crawler System dan kontrak integrasi agar Fetch Review tidak lagi count-first, tetapi window-first, cursor-aware, dan aman untuk scheduler/manual.

Target akhir:

- Review hasil crawl cepat masuk DB Crawler.
- OneBox bisa pull raw review tanpa tombol tambahan yang membingungkan user.
- Fetch manual dan scheduler tidak overlap.
- Duplicate tidak dianggap failure.
- Job history punya counters dan stop reason yang jelas.
- Rating snapshot tersedia untuk KPI trend.

## Scope P0 - Validasi Existing System

- [ ] Baca ulang current implementation endpoint `POST /api/integration/v1/crawl-jobs`.
- [ ] Baca service worker/antrian crawl.
- [ ] Baca model/tabel untuk location, worklist, crawl job, dan reviews.
- [ ] Identifikasi field existing yang bisa dipakai untuk cursor:
  - `last_fetched_at`
  - `last_success_at`
  - `last_review_date`
  - `metadata`
  - `batch_id`
- [ ] Catat gap field yang belum tersedia.
- [ ] Pastikan backward compatibility dengan payload OneBox saat ini.

Deliverable:

- Ringkasan file yang perlu diedit.
- Matrix existing field vs required field.

## Scope P1 - Contract dan Payload Normalization

- [ ] Tambahkan normalisasi payload agar `target_review_count` tetap diterima.
- [ ] Tambahkan internal field baru:
  - `crawl_mode`
  - `max_reviews_to_collect`
  - `scan_limit`
  - `date_range.from`
  - `date_range.to`
- [ ] Default `crawl_mode`:
  - `initial_backfill` jika target belum pernah baseline.
  - `regular_delta` jika target sudah punya cursor.
  - `custom_range` jika user mengirim date range eksplisit.
- [ ] Response create job wajib berisi:
  - `batch_id`
  - `status`
  - `accepted_targets`
  - `reused_existing_job`
  - `limits`

Deliverable:

- Endpoint tetap bisa dipanggil dari OneBox lama.
- Endpoint siap dipakai OneBox baru.
- Test contract untuk old payload dan new payload.

## Scope P2 - Cursor dan Target State

- [ ] Tambahkan atau gunakan state per crawl target:
  - `first_run_completed_at`
  - `last_successful_crawl_at`
  - `last_seen_review_time`
  - `oldest_scanned_review_time`
  - `cursor_source_review_id`
- [ ] Update state hanya saat job valid selesai.
- [ ] Jangan merusak cursor regular delta dari custom range yang gagal/partial.
- [ ] Simpan `has_more=true` jika backfill berhenti karena scan limit.

Deliverable:

- Migration jika butuh field baru.
- Unit test update cursor.
- Unit test custom range tidak merusak cursor delta.

## Scope P3 - Crawl Algorithm

- [ ] Ubah logika stop condition crawler:
  - stop saat matched mencapai `max_reviews_to_collect`
  - stop saat scan mencapai `scan_limit`
  - stop saat review lebih tua dari date range
  - stop saat duplicate streak melewati threshold
  - stop saat timeout/no more review
- [ ] Pisahkan counter:
  - `scanned`
  - `matched`
  - `inserted`
  - `duplicate`
  - `out_of_range_newer`
  - `out_of_range_older`
  - `failed_items`
- [ ] Pastikan duplicate tinggi tidak otomatis `failed`.
- [ ] Pastikan date range dengan hasil kurang dari target tetap bisa `succeeded`.

Deliverable:

- Crawl result punya counters lengkap.
- Stop reason jelas.
- Regression test duplicate-heavy dan date-range-fewer-than-target.

## Scope P4 - Lock dan Idempotency

- [ ] Buat lock key:

```text
tenant_id + source + target_id + crawl_mode + normalized_date_window
```

- [ ] Jika job dengan key sama masih `queued/running`, return existing job.
- [ ] Manual fetch tidak membuat job duplikat saat scheduler sedang berjalan untuk target/window sama.
- [ ] Simpan dan hormati `Idempotency-Key` dari OneBox.
- [ ] Tambahkan response `reused_existing_job=true` saat job lama dipakai ulang.

Deliverable:

- Test idempotency.
- Test overlap manual vs scheduler.

## Scope P5 - Rating Snapshot

- [ ] Saat crawler membuka Google Maps target, ambil:
  - rating Google saat ini
  - total review Google saat ini
  - waktu snapshot
- [ ] Simpan snapshot terhubung ke target dan crawl job.
- [ ] Expose snapshot dalam API yang bisa ditarik OneBox.
- [ ] Jangan hitung rating trend dari review yang berhasil masuk saja.

Deliverable:

- Tabel/model snapshot atau metadata snapshot.
- Test snapshot tersimpan.
- Response API menyediakan snapshot untuk OneBox.

## Scope P6 - Status dan Observability

- [ ] Standardisasi status:
  - `queued`
  - `running`
  - `succeeded`
  - `partially_failed`
  - `failed`
  - `cancelled`
  - `expired`
- [ ] Standardisasi stop reason:
  - `target_reached`
  - `older_than_window`
  - `scan_limit_reached`
  - `duplicate_streak`
  - `timeout`
  - `no_more_reviews`
  - `blocked_by_google_login`
  - `target_not_found`
- [ ] Tambahkan logging batch/job yang cukup untuk debug UI OneBox.
- [ ] Pastikan error asli tidak hilang di generic message.

Deliverable:

- Job detail bisa menjawab kenapa crawl berhenti.
- UI OneBox bisa menampilkan progress dan alasan berhenti.

## Scope P7 - E2E Proof

- [ ] Jalankan test dengan satu lokasi kecil.
- [ ] Jalankan test duplicate-heavy.
- [ ] Jalankan test custom date range.
- [ ] Jalankan test backfill dengan scan limit kecil.
- [ ] Pastikan OneBox bisa pull review setelah Crawler selesai.
- [ ] Simpan evidence:
  - request payload
  - response create job
  - batch id
  - final status
  - counters
  - screenshot Kelola Review setelah data masuk

Deliverable:

- Update runbook dengan hasil test.
- Summary ke user/Claude: apa yang sudah proof dan apa yang masih blocker.

## Bukan Scope Codex Saat Ini

- Tidak redesign full UI OneBox.
- Tidak membangun AI analysis UI.
- Tidak membuat rule sentiment baru.
- Tidak mengubah ticket routing.
- Tidak mengganti DB engine.
- Tidak membuat endpoint breaking tanpa backward compatibility.

## Output Yang Harus Diberikan Codex Setiap Selesai Step

Gunakan format ini:

```text
Done:
- ...

Changed files:
- ...

Tests:
- ...

Remaining:
- ...

Blocker:
- ...
```

## Prioritas Eksekusi

1. P0 existing audit.
2. P1 payload normalization.
3. P3 counters dan stop reason.
4. P4 lock/idempotency.
5. P2 cursor state.
6. P5 rating snapshot.
7. P7 E2E proof.

Urutan ini dipilih supaya demo cepat membaik dulu: kontrak aman, status jelas, duplicate tidak terlihat seperti failure, lalu baru cursor dan KPI trend diperkuat.
