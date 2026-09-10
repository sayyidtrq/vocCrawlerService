# Codex Todo Scope - Review Fetch Logic Refactor

Status: In progress - P1/P3/P4 partial, P5 done, P0.5/T1 done
Tanggal: 2026-09-01
Modul besar: VoC Fetch Review / Fetch Jobs Crawl

## Status Implementasi Terakhir - 2026-09-01

Sudah merged ke `main` dan sudah smoke di server `ciptadra-svr`:

| Scope | Status | Commit/PR | Catatan |
| --- | --- | --- | --- |
| P1 - Contract dan payload normalization | Done untuk demo | PR #9 `81b1e0e` | `target_review_count` tetap kompatibel; `max_reviews_to_collect`, `scan_limit`, `crawl_mode`, dan date range sudah diterima. |
| P3 - Crawl algorithm/counters dasar | Partial | PR #9 `81b1e0e` | Scan limit, date window stop, out-of-range counters, dan partial/success logic sudah membaik. Duplicate streak eksplisit belum ada. |
| P4 - Lock/idempotency | Partial | PR #9 `81b1e0e` | Idempotency dan active batch reuse target/window sudah ada; hardening manual-vs-scheduler penuh masih tersisa. |
| P5 - Rating snapshot | Done | PR #10 `79e2a8a`, commit `ebf3543` | Snapshot Google Maps diambil dan expose pada detail batch. OneBox sudah consume. |
| P6 - Status/observability | Partial | PR #11 `0c3c1b3`, commit `0ce172e` | Batch list expose `stop_reason` dan `stop_reasons`; job detail tetap granular. |
| P0.5/T1 - Stable review identity | Done | PR #11 `0c3c1b3`, commit `0ce172e` | Selenium hash tidak memakai `review_relative_time`; insert review dan competitor review dedupe via `external_review_id`. |
| P2 - Cursor dan target state | Not started | - | Belum ada durable watermark di tabel `locations` Crawler. |
| P7 - E2E proof | Partial | - | Smoke API berhasil; E2E penuh dengan OneBox import/Kelola Review masih perlu evidence. |

Bukti test:

- Local Crawler: `python -m pytest tests -q` -> `115 passed`.
- Server health: `127.0.0.1:8000/api/health` dan `10.13.13.90:8000/api/health` -> `200 OK`.
- Integration smoke: `/api/integration/v1/crawl-jobs?limit=3` mengembalikan `stop_reason` dan `stop_reasons`.

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

- [x] Baca ulang current implementation endpoint `POST /api/integration/v1/crawl-jobs`.
- [x] Baca service worker/antrian crawl.
- [x] Baca model/tabel untuk location, worklist, crawl job, dan reviews.
- [x] Identifikasi field existing yang bisa dipakai untuk cursor:
  - `last_fetched_at`
  - `last_success_at`
  - `last_review_date`
  - `metadata`
  - `batch_id`
- [x] Catat gap field yang belum tersedia.
- [x] Pastikan backward compatibility dengan payload OneBox saat ini.

Deliverable:

- Ringkasan file yang perlu diedit.
- Matrix existing field vs required field.

## Scope P1 - Contract dan Payload Normalization

- [x] Tambahkan normalisasi payload agar `target_review_count` tetap diterima.
- [x] Tambahkan internal field baru:
  - `crawl_mode`
  - `max_reviews_to_collect`
  - `scan_limit`
  - `date_range.from`
  - `date_range.to`
- [x] Default `crawl_mode`:
  - `regular_delta` jika tidak ada date range.
  - `custom_range` jika user mengirim date range eksplisit.
  - `initial_backfill` belum aktif karena baseline target state belum tersedia.
- [x] Response create job wajib berisi:
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

- [x] Ubah logika stop condition crawler:
  - stop saat matched mencapai `max_reviews_to_collect`
  - stop saat scan mencapai `scan_limit`
  - stop saat review lebih tua dari date range
  - stop saat duplicate streak melewati threshold (**belum eksplisit**)
  - stop saat timeout/no more review
- [x] Pisahkan counter:
  - `scanned`
  - `matched`
  - `inserted`
  - `duplicate`
  - `out_of_range_newer`
  - `out_of_range_older`
  - `failed_items`
- [x] Pastikan duplicate tinggi tidak otomatis `failed`.
- [x] Pastikan date range dengan hasil kurang dari target tetap bisa `succeeded`.

Deliverable:

- Crawl result punya counters lengkap.
- Stop reason jelas.
- Regression test duplicate-heavy dan date-range-fewer-than-target.

## Scope P4 - Lock dan Idempotency

- [ ] Buat lock key:

```text
tenant_id + source + target_id + crawl_mode + normalized_date_window
```

- [x] Jika job dengan key sama masih `queued/running`, return existing job.
- [ ] Manual fetch tidak membuat job duplikat saat scheduler sedang berjalan untuk target/window sama.
- [x] Simpan dan hormati `Idempotency-Key` dari OneBox.
- [x] Tambahkan response `reused_existing_job=true` saat job lama dipakai ulang.

Deliverable:

- Test idempotency.
- Test overlap manual vs scheduler.

## Scope P5 - Rating Snapshot

- [x] Saat crawler membuka Google Maps target, ambil:
  - rating Google saat ini
  - total review Google saat ini
  - waktu snapshot
- [x] Simpan snapshot terhubung ke target dan crawl job.
- [x] Expose snapshot dalam API yang bisa ditarik OneBox.
- [x] Jangan hitung rating trend dari review yang berhasil masuk saja.

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
- [x] Standardisasi stop reason:
  - `target_reached`
  - `older_than_window`
  - `scan_limit_reached`
  - `duplicate_streak`
  - `timeout`
  - `no_more_reviews`
  - `blocked_by_google_login`
  - `target_not_found`
- [x] Tambahkan logging batch/job yang cukup untuk debug UI OneBox.
- [x] Pastikan error asli tidak hilang di generic message.

Deliverable:

- Job detail bisa menjawab kenapa crawl berhenti.
- UI OneBox bisa menampilkan progress dan alasan berhenti.

## Scope P7 - E2E Proof

- [x] Jalankan test dengan satu lokasi kecil.
- [x] Jalankan test duplicate-heavy.
- [x] Jalankan test custom date range.
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
