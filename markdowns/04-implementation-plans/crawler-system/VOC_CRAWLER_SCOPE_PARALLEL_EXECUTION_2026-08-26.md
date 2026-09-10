# VoC Crawler Scope - Parallel Execution Plan

**Tanggal:** 2026-08-26  
**Sumber:** `markdowns/02-meetings-and-decisions/meeting-notes/2026-08-21-voc-progress-review.md` dan `markdowns/01-product-and-backlog/grooming/2026-08-25-voc-grooming-sprint.md`  
**Acuan arsitektur:** ADR-0003, ADR-0004, `FETCH_JOBS_E2E_CONTRACT.md`, `PLAN_FAST_INGEST_LABELING_ON_DEMAND_AI.md`  
**Tujuan:** memecah scope Crawler System agar dapat dikerjakan paralel dengan Claude di OneBox tanpa saling menunggu hal yang tidak perlu.

---

## 1. Executive Summary

Review CEO tanggal 21 Agustus mengubah fokus pekerjaan dari "fitur tampil" menjadi "produk dapat membuktikan value dengan data nyata".

Untuk sisi Crawler System, perubahan terpenting adalah:

1. Crawler harus bisa membuktikan kapasitas engine, bukan hanya berhasil mengambil review satu kali.
2. Fetch Jobs harus benar-benar end-to-end: klik `Mulai Crawl` di OneBox -> Selenium scrape -> review persist di Crawler -> OneBox auto-import -> Kelola Review siap, tanpa tombol `Tarik Review` kedua.
3. Date range tidak boleh kalah oleh `target_review_count`. Jika user meminta rentang tanggal, target count bukan batas jumlah kartu yang dibaca, melainkan jumlah review yang match filter atau batas operasional tercapai.
4. Setiap batch crawl harus punya observability: source manual/scheduler, started_at, finished_at, duration, counters, error sanitized, dan snapshot rating platform.
5. AI analysis tidak boleh memblokir crawl dan ingestion. Raw review harus cepat masuk; AI analysis berjalan on-demand, async, single/bulk.
6. Crawler harus siap untuk skala Hermina: kira-kira 80 cabang x 3 window per hari = 240 crawl/hari, lalu skenario lebih besar seperti jaringan SPBU.

Dokumen ini fokus ke Crawler System. Bagian OneBox hanya ditulis sebagai boundary dan handoff untuk Claude.

---

## 2. Non-Negotiable Architecture

| Keputusan | Implikasi untuk Crawler |
|---|---|
| OneBox adalah System of Record | Crawler tidak menjadi master lokasi, user, role, category, ticket, atau setting bisnis. |
| Crawler adalah worker/headless engine | Selenium, normalization, dedup, raw review storage, queue, dan analysis execution tetap di Crawler. |
| Worklist pull | Crawler menarik target dari OneBox dan menyimpannya sebagai cache operasional. |
| Crawl non-blocking | Endpoint enqueue hanya membuat job dan mengembalikan `batch_id`; Selenium berjalan di worker. |
| Fast ingestion | Crawl menyimpan raw review tanpa menunggu AI. |
| AI on-demand | Analysis dipicu user dari OneBox untuk single/bulk review, bukan otomatis di critical path crawl. |
| Tenant dari service identity | `company_id` berasal dari token/service credential, bukan dari body request. |

---

## 3. Target Demo Flow

Target demo key process:

```text
Admin OneBox setup lokasi aktif
  -> OneBox menampilkan Fetch Jobs
  -> User pilih lokasi dan target review
  -> OneBox enqueue crawl ke Crawler
  -> Crawler worker menjalankan Selenium
  -> Raw review disimpan di DB Crawler
  -> OneBox polling batch sampai terminal
  -> OneBox auto-import review dari Crawler
  -> OneBox simpan review sebagai data VoC
  -> OneBox menjalankan native sentiment labeling
  -> Kelola Review langsung bisa dipakai
  -> User pilih 1 atau bulk review
  -> OneBox enqueue AI analysis async ke Crawler
  -> Crawler AI worker memproses
  -> OneBox update review/Ticket existing dengan hasil AI
  -> User eskalasi/kelola tiket
```

Fetch Jobs dianggap selesai hanya jika review sudah bisa dilihat dan dikelola di OneBox tanpa langkah import manual.

---

## 4. Work Ownership

| Lane | Agent | Repo | Fokus |
|---|---|---|---|
| Crawler Lane | Codex | `herminaCrawler` | FastAPI, SQLAlchemy/Alembic, worker, Selenium, API contract, auth, queue, observability, tests, runbook. |
| OneBox Lane | Claude | `onecloud` | PHP/Phalcon, Connection.Options, UI Fetch Jobs, auto-import, native labeling, Ticket/Message mapping, Kelola Review. |
| Ops Lane | Sayyid/Infra | Server dev | Deploy, Google profile login, service token, DB access, network/WireGuard, final demo evidence. |

Rule kerja:

- Crawler tidak menunggu UI selesai untuk membuat endpoint dan fixture.
- OneBox tidak menunggu load test selesai untuk mengonsumsi kontrak basic.
- Claude tidak boleh membuat crawler workaround di OneBox jika kekurangannya ada di API Crawler.
- Codex tidak boleh memindahkan business logic OneBox ke Crawler.

---

## 5. Parallel Execution Map

```text
Codex C1: Instrumentasi crawl batch
  -> Claude OB1: tampilkan durasi/source/counter di Riwayat Fetch

Codex C2: Fix semantics date range + target count
  -> Claude OB2: kirim date range dan jelaskan behavior UI

Codex C3: Stabilkan one-click Fetch Jobs E2E contract
  -> Claude OB3: auto-import + labeling + progress UI

Codex C4: Load test 20/50/80 targets dan anti-block strategy
  -> Claude OB4: siapkan scheduler/multi-select tanpa menunggu hasil akhir

Codex C5: Async AI analysis API single/bulk
  -> Claude OB5: UI pilih review + polling analysis status

Codex C6: Tenant, auth, runbook, failure drill
  -> Claude OB6: permission, token placement, operational error message
```

---

## 6. Scope Crawler Per Workstream

### C1 - Crawl Instrumentation

**Jira terkait:** DNGO19-3508 - VOC: Crawl Instrumentation  
**Branch usulan:** `feature/DNGO19-3508_VOC-Crawl-Instrumentation`  
**Owner utama:** Codex  
**Handoff utama:** Claude untuk kolom Riwayat Fetch dan progress UI

#### Problem

Saat review CEO, tim tidak bisa menjawab "berapa lama engine jalan" karena manual crawl dan scheduler tercampur, dan log tidak cukup menjelaskan durasi/counter.

#### Scope Crawler

- Tambahkan atau verifikasi field batch/job:
  - `started_at`
  - `finished_at`
  - `duration_seconds`
  - `source` atau `slot` (`manual`, `scheduler`, `backfill`, `test`)
  - `target_count`
  - `scanned_count`
  - `matched_count`
  - `fetched_count`
  - `inserted_count`
  - `duplicate_count`
  - `failed_count`
  - `platform_rating_snapshot`
  - `platform_review_count_snapshot`
  - `last_error_code`
  - `last_error_message_sanitized`
- Pastikan batch gagal tetap punya `finished_at` dan `duration_seconds`.
- Jika worker mati di tengah, job yang lease expired harus dapat ditandai retry/failed dengan durasi yang tetap dapat diaudit.
- Response status batch harus mengembalikan counter yang sama, minimal:

```json
{
  "data": {
    "batch_id": "uuid",
    "status": "running",
    "slot": "manual",
    "started_at": "2026-08-26T01:00:00Z",
    "finished_at": null,
    "duration_seconds": 42,
    "review_counts": {
      "target": 50,
      "scanned": 70,
      "matched": 38,
      "fetched": 38,
      "inserted": 10,
      "duplicate": 28,
      "failed": 0
    },
    "platform_snapshot": {
      "rating": 4.3,
      "review_count": 9422
    }
  }
}
```

#### Out of Scope

- Redesign Riwayat Fetch di OneBox.
- Membuat scheduler baru di Crawler.
- Mengubah business definition open/close review.

#### Acceptance Criteria

- Setiap batch terminal punya `started_at`, `finished_at`, dan `duration_seconds`.
- Manual dan scheduler bisa dibedakan dari API response.
- Snapshot rating platform disimpan sebagai field sendiri, bukan dihitung dari sample.
- Error tidak memuat token, cookie, cursor lengkap, atau teks review penuh.
- Unit/integration test membuktikan success, failed, dan retry tetap mengisi metadata.

#### Verification

```bash
docker compose exec api pytest tests/test_integration_crawl_jobs.py
docker compose exec api python -m scripts.smoke_crawl_job --target-location-id <id> --target-review-count 5
curl -sS -H "Authorization: Bearer <token>" http://127.0.0.1:8000/api/integration/v1/crawl-jobs/<batch_id>
```

---

### C2 - Date Range Completeness and Target Count Semantics

**Jira terkait:** bagian dari DNGO19-3420 / follow-up Crawler correctness  
**Branch usulan:** `feature/DNGO19-3420_VOC-Fetch-Jobs-Date-Range-Completeness`  
**Owner utama:** Codex  
**Handoff utama:** Claude untuk form input date range dan copy UI

#### Problem

Notulen mencatat cacat fungsi: ketika worklist meminta 20 review dengan filter tanggal tertentu, crawler berhenti di 20 kartu walaupun review yang match tanggal sebenarnya lebih banyak. Untuk manual fetch dengan date range, sistem harus mengejar semua review di range sampai target match tercapai atau batas operasional tercapai.

#### Scope Crawler

- Definisikan ulang arti `target_review_count`:
  - tanpa date range: jumlah review yang ingin dibaca dari urutan terbaru;
  - dengan date range: jumlah review yang match filter tanggal, bukan batas absolut kartu yang discan;
  - jika user memilih "ambil semua dalam range", `target_review_count` boleh null atau memakai mode khusus `fetch_until_range_exhausted`.
- Paksa `sort_by=newest` ketika `date_from/date_to` dikirim.
- Tambahkan counter:
  - `scanned`
  - `matched`
  - `out_of_range_before`
  - `out_of_range_after`
  - `range_exhausted`
  - `stop_reason`
- Stop condition yang eksplisit:
  - `target_reached`
  - `date_range_exhausted`
  - `max_scroll_reached`
  - `timeout`
  - `google_blocked`
  - `target_not_found`
- Jangan memajukan crawl cursor/checkpoint sebelum page/unit of work sukses.
- Scheduler boleh tetap memakai target count sebagai batas harian untuk kontrol beban, tetapi manual date range harus jujur terhadap range.

#### Acceptance Criteria

- Date range tidak berhenti hanya karena jumlah kartu yang discan sudah sama dengan target.
- API response membedakan `scanned`, `matched`, `fetched`, `inserted`, dan `duplicate`.
- Jika tidak semua range berhasil dibaca, response tidak boleh terlihat sukses penuh; gunakan `partial_success` atau `completed` dengan `stop_reason` yang jelas.
- Test fixture membuktikan 50 review dalam range tetap terbaca walaupun 20 kartu pertama tidak cukup.
- OneBox dapat menampilkan warning jika stop reason bukan `target_reached` atau `date_range_exhausted`.

---

### C3 - Fetch Jobs One-Click End-to-End

**Jira terkait:** DNGO19-3420 - Fetch Jobs Crawl  
**Branch usulan:** `feature/DNGO19-3420_Fetch-Jobs-Crawl` atau branch follow-up kecil dari `feature/voc`  
**Owner utama:** Codex + Claude  
**Boundary:** Codex menuntaskan Crawler API/status/review delta; Claude menuntaskan auto-import dan labeling di OneBox.

#### Scope Crawler

- Pastikan `POST /api/integration/v1/crawl-jobs`:
  - membutuhkan `crawl:enqueue`;
  - menerima `Idempotency-Key`;
  - mengembalikan `202` dan `batch_id` cepat;
  - tidak menunggu Selenium selesai;
  - menerima target eksplisit dari OneBox;
  - menerima `target_review_count` per target;
  - tenant scoped dari service token.
- Pastikan `GET /api/integration/v1/crawl-jobs/{batch_id}`:
  - membutuhkan `crawl:read`;
  - mengembalikan status batch/job dan counters aktual;
  - batch tenant lain tidak bisa dibaca.
- Pastikan `GET /api/integration/v1/reviews`:
  - dapat dipakai OneBox untuk pull raw review setelah batch terminal;
  - mengirim review walaupun `analysis=null`;
  - tidak menganggap AI enrichment sebagai discovery baru tanpa event semantics.
- Pastikan dedup review stabil:
  - tenant + provider/source + stable remote id jika ada;
  - fallback `review_hash` dari author + source_review_time + text normalized.
- Pastikan idempotency:
  - key sama + payload sama -> batch sama;
  - key sama + payload beda -> `409 IDEMPOTENCY_CONFLICT`.

#### Handoff untuk Claude

Claude harus memanggil auto-import saat batch `completed` atau `partial_failed`, bukan menunggu user klik tombol kedua. Crawler hanya menyediakan data dan status yang cukup.

#### Acceptance Criteria

- Klik `Mulai Crawl` target 10 menghasilkan satu batch.
- Batch terminal punya `review_counts`.
- Review muncul di Crawler DB.
- OneBox dapat pull delta raw review dengan `analysis=null`.
- Rerun tidak membuat review ganda.
- Ollama mati tidak menggagalkan fetch jobs.

---

### C4 - Engine Load Test and Anti-Blocking Strategy

**Jira terkait:** engine load test dari grooming Sprint 1  
**Branch usulan:** `feature/DNGO19-NEW02_VOC-Engine-Load-Test` atau Jira key aktual bila sudah dibuat  
**Owner utama:** Codex + Ops  
**Koordinasi:** Bang Sam untuk akun Google/profile

#### Problem

Skala target bukan 1-3 lokasi. Hermina kira-kira 80 cabang x 3 window = 240 crawl/hari. Review CEO juga menyebut kemungkinan client jauh lebih besar. Risiko terbesar adalah Google blocking, bukan syntax error.

#### Scope Crawler

- Buat load test runner yang bisa menjalankan:
  - 20 target x 1 run;
  - 50 target x 1 run;
  - 80 target x 1 run;
  - simulasi 80 target x 3 window/hari.
- Ukur:
  - total duration;
  - avg duration per target;
  - p50/p95 duration;
  - success rate;
  - failure rate by error code;
  - retry count;
  - queue wait time;
  - CPU/RAM;
  - browser/profile health;
  - indication of Google block/captcha/login expired.
- Uji minimal dua strategi:
  - satu Google account + satu Chrome profile;
  - beberapa worker/profile/container bila feasible.
- Buat output dokumen hasil, bukan hanya log mentah.

#### Acceptance Criteria

- Ada tabel hasil per level beban.
- Titik jenuh teridentifikasi: mulai gagal di target berapa dan kenapa.
- Ada rekomendasi: single profile cukup atau perlu distributed profile/container.
- Gejala block Google terdokumentasi dengan timestamp, status, dan screenshot/log sanitized.
- Tidak ada token/cookie/profile secret masuk log atau markdown.

#### Blocker

- Akun Google/profile bisa expired.
- Google Maps dapat memunculkan CAPTCHA atau throttling.
- Server dev mungkin tidak cukup CPU/RAM untuk banyak Chromium paralel.
- Network dari WireGuard/LAN harus stabil.

---

### C5 - Worklist Cache and Multi-Tenant Readiness

**Jira terkait:** master data location, tenant kedua, scheduler/fetch jobs  
**Owner utama:** Codex untuk Crawler cache; Claude untuk endpoint OneBox worklist

#### Scope Crawler

- Consumer worklist menarik target dari OneBox per `company_id` eksplisit.
- Cache worklist menyimpan:
  - `company_id`
  - `site_id`
  - `onebox_connection_id`
  - `onebox_location_id`
  - `external_place_id`
  - `source`
  - `active`
  - `target_review_count_default`
  - `ai_enabled`
  - `output_schema_version`
  - optional region/group metadata untuk display/debug, bukan source of truth.
- Target yang hilang/nonaktif di worklist ditandai inactive, bukan langsung dihapus.
- Refresh worklist otomatis ketika enqueue menemukan target tidak ada, lalu retry lookup sekali.
- Tenant B harus tidak bisa membaca batch/review tenant A.

#### Acceptance Criteria

- `python -m scripts.refresh_worklist --company-id <id>` sync berhasil.
- Enqueue target valid setelah refresh berhasil.
- Target beda tenant menghasilkan `404 TARGET_NOT_FOUND` atau `403` tanpa bocor detail.
- Tidak ada hardcode `company_id=3` di flow runtime kecuali command manual.

---

### C6 - Scheduler Support Without Owning Scheduler

**Jira terkait:** DNGO19-3390 Crawl Scheduler, scheduler bulk select  
**Owner utama:** Claude untuk scheduler; Codex untuk batch capacity/status support

#### Scope Crawler

- Crawler tidak membuat scheduler kedua.
- Crawler menerima `slot` dari OneBox:
  - `manual`
  - `morning`
  - `noon`
  - `night`
  - `scheduler`
  - `backfill`
- Crawler bisa menerima banyak target dalam satu batch.
- Worker harus punya concurrency, rate limit, retry, dan backpressure yang dapat dikonfigurasi.
- Batch status harus tetap berguna untuk banyak target:
  - aggregate counts;
  - per-job status;
  - partial failure.

#### Acceptance Criteria

- Satu batch 40+ target bisa dibuat tanpa request timeout.
- Response enqueue tetap cepat.
- Batch partial tetap dapat mengimpor review dari target sukses.
- Slot scheduler bisa dibedakan di Riwayat Fetch.

---

### C7 - AI Analysis Async API

**Jira terkait:** DNGO19-3388 AI Analysis Setup, Enhance AI Analysis  
**Owner utama:** Codex untuk execution API; Claude untuk UI/config/entitlement

#### Scope Crawler

- Analysis tidak dipanggil otomatis dari crawl job.
- Tambahkan durable analysis queue:
  - analysis batch;
  - analysis item/job per review;
  - status `queued`, `processing`, `completed`, `failed`, `partial_failed`;
  - attempts, lease, timestamps, error sanitized;
  - token usage.
- Service API:

```http
POST /api/integration/v1/analysis-jobs
GET /api/integration/v1/analysis-jobs/{analysis_batch_id}
```

- Scope token:
  - `analysis:enqueue`
  - `analysis:read`
- Bulk limit awal: 1-50 review.
- Tenant validation: review IDs harus milik company service token.
- Output harus mengikuti schema version yang disepakati:

```json
{
  "summary": "Ringkasan masalah",
  "recommended_action": "Tindakan yang disarankan",
  "urgency": "low|medium|high|critical",
  "issue_category": "parking|cleanliness|doctor_service|registration|other",
  "confidence": 0.83,
  "model": "llama3.2:1b",
  "prompt_version": "voc-v1",
  "output_schema_version": "2026-08-01"
}
```

#### Acceptance Criteria

- POST analysis jobs mengembalikan `202` tanpa menunggu inference selesai.
- Satu review bisa dianalisis.
- Bulk 50 review bisa queued.
- Satu item gagal tidak menggagalkan semua batch.
- Token usage dikembalikan untuk OneBox metering.
- Hasil analysis hanya enrichment, tidak membuat review baru.
- Crawl tetap sukses ketika AI/Ollama mati.

---

### C8 - Competitor and Benchmark Data Support

**Jira terkait:** competitor analysis, regional comparison, benchmark kedua  
**Owner utama:** Codex untuk scraping/provider; Claude untuk dashboard/benchmark UI

#### Scope Crawler

- Pastikan target competitor dari worklist bisa dibedakan dari own location.
- Review competitor tidak boleh masuk sebagai Ticket operasional.
- Expose competitor review delta atau endpoint terpisah sesuai kontrak final.
- Simpan snapshot rating platform competitor saat crawl.
- Counters competitor harus terpisah dari location review.

#### Acceptance Criteria

- Crawler bisa crawl competitor target dari worklist.
- OneBox bisa menarik competitor review tanpa membuat Ticket.
- Benchmark dapat memakai rating platform snapshot, bukan hitungan sampel.

#### Catatan

Ini bukan blocker pertama untuk demo Google Review Hermina, tetapi diperlukan untuk benchmark kedua yang diminta CEO.

---

### C9 - Reliability, Security, and Operational Runbook

**Owner utama:** Codex  
**Handoff:** Ops dan Claude untuk pesan error UI

#### Scope Crawler

- Health endpoint membedakan:
  - app alive;
  - DB OK;
  - worker heartbeat;
  - queue depth;
  - browser/profile readiness bila memungkinkan.
- Error contract distandarkan:
  - `INSUFFICIENT_SCOPE`
  - `TARGET_NOT_FOUND`
  - `IDEMPOTENCY_CONFLICT`
  - `GOOGLE_LOGIN_REQUIRED`
  - `GOOGLE_BLOCKED`
  - `SELENIUM_TIMEOUT`
  - `WORKLIST_UNAVAILABLE`
  - `QUEUE_BACKPRESSURE`
- Sanitasi log:
  - tidak log token;
  - tidak log cookie;
  - tidak log full cursor;
  - tidak log full review text.
- Runbook:
  - setup Google profile;
  - clear stale Chromium lock;
  - issue/rotate service token;
  - smoke test health;
  - smoke test worklist;
  - smoke test crawl;
  - rollback deploy.

#### Acceptance Criteria

- Operator bisa tahu service healthy atau tidak tanpa membaca log panjang.
- Token expired/scope kurang menghasilkan pesan operasional jelas.
- Login Google expired terdeteksi sebagai action item, bukan generic failed.
- Runbook bisa diikuti dari server dev.

---

### C10 - SIT Evidence Package

**Jira terkait:** SIT End-to-End  
**Owner utama:** Sayyid + Codex + Claude  
**Target:** materi bukti untuk demo, bukan hanya test internal.

#### Scope Crawler

- Siapkan command/script untuk menjalankan test satu lokasi:
  - refresh worklist;
  - enqueue target 10;
  - poll batch;
  - ambil review delta;
  - tampilkan counter.
- Siapkan command/script untuk load subset:
  - 20 lokasi;
  - 50 lokasi;
  - 80 lokasi jika resource cukup.
- Export sanitized evidence:
  - batch id;
  - target;
  - timestamps;
  - counters;
  - stop reason;
  - sample review hash, bukan teks penuh jika tidak perlu.

#### Acceptance Criteria

- Satu alur demo bisa diulang dengan command yang sama.
- Evidence dapat ditempel ke PR/Jira tanpa membocorkan credential.
- Jika gagal, failure reason jelas dan actionable.

---

## 7. Contract Checkpoints Between Codex and Claude

### Checkpoint A - Fetch Jobs Status Contract

Codex deliver:

- example `POST /crawl-jobs` request;
- example running response;
- example completed response;
- error examples;
- list of final counter names.

Claude can start:

- progress bar state machine;
- Riwayat Fetch columns;
- auto-import trigger after terminal batch.

### Checkpoint B - Review Delta Contract

Codex deliver:

- raw review fixture with `analysis=null`;
- `source_review_time`;
- `first_seen_at`;
- `ingestion_mode`;
- `eligible_for_ticket`;
- `analysis_status`;
- `platform_snapshot` if available.

Claude can start:

- raw ingestion;
- native sentiment labeling;
- Kelola Review data display;
- prevent historical reviews from creating operational Ticket automatically.

### Checkpoint C - Analysis Jobs Contract

Codex deliver:

- enqueue/status API for analysis;
- output schema version;
- error contract;
- token usage fields.

Claude can start:

- single review analysis button;
- bulk selection 1-50;
- polling/progress;
- apply enrichment to existing review/Ticket.

---

## 8. Open Decisions and Blockers

| Blocker | Owner | Impact | Recommendation |
|---|---|---|---|
| Transkrip setelah menit 30 belum ada | Ops | Bisa ada requirement belum tercatat | Jangan klaim scope final product sebelum transkrip lengkap. Untuk crawler, lanjut scope engine dan Fetch Jobs karena sudah eksplisit. |
| Target rating resmi per site belum final | Product/OneBox | Dashboard coloring dan regional benchmark | Crawler hanya simpan platform snapshot; target internal tetap di OneBox. |
| Aturan close non-official perlu dikunci | Product/OneBox | Review lifecycle/widget | Tidak memblokir crawler. |
| Daftar unit penerima tiket belum ada | Product/Hermina | Ticket routing | Crawler tidak mengarang unit; hanya kirim category/analysis. |
| Google Business API reply >5 berbayar | Ops/Bang Sam | Reply official | Tidak memblokir crawling raw review. |
| Google profile/login expired | Ops/Codex | Selenium crawl gagal | Buat health/runbook dan error `GOOGLE_LOGIN_REQUIRED`. |
| Google blocking/CAPTCHA | Codex/Ops | Risiko eksistensial | Load test dan anti-block strategy harus jadi Sprint 1. |
| DB migration PostgreSQL ke MySQL | Architect/Ops | Infrastruktur jangka menengah | Jangan gabungkan dengan demo Fetch Jobs kecuali P0-A sudah disetujui. |

---

## 9. Definition of Done for Crawler Scope

Sebuah scope Crawler boleh disebut selesai hanya jika:

- Ada endpoint/behavior yang berjalan di dev atau local.
- Ada test otomatis atau smoke command.
- Ada curl/request example tanpa token asli.
- Ada response actual atau fixture yang bisa dipakai Claude.
- Ada migration bila schema berubah.
- Ada rollback note bila menyentuh deploy/schema.
- Tidak ada credential, cookie, token, atau review text penuh di log/dokumen.
- Handoff ke Claude ditandai:
  - `verified`: sudah dibuktikan;
  - `assumption`: belum dibuktikan tetapi reasonable;
  - `blocked`: butuh pihak luar.

---

## 10. Recommended Execution Order

### Day 1 - Contract and Instrumentation

1. C1 Crawl Instrumentation.
2. C3 Fetch Jobs status response stabilization.
3. Checkpoint A ke Claude.

Output wajib:

- status response final;
- counters final;
- error contract final.

### Day 2 - Correctness and E2E

1. C2 Date range completeness.
2. C3 review delta raw with `analysis=null`.
3. Checkpoint B ke Claude.

Output wajib:

- satu lokasi target 10 berhasil;
- raw review masuk delta;
- crawler tetap jalan tanpa AI.

### Day 3 - Load Test

1. C4 load test 20.
2. C4 load test 50.
3. Evaluasi profile/anti-block.

Output wajib:

- tabel hasil;
- failure modes;
- rekomendasi capacity.

### Day 4 - Scheduler and Bulk Readiness

1. C6 many-target batch.
2. Backpressure/rate-limit config.
3. Partial failure behavior.

Output wajib:

- satu batch banyak target tidak timeout;
- status partial dapat dibaca.

### Day 5 - AI Async Skeleton and SIT Evidence

1. C7 analysis jobs skeleton/contract jika Fetch Jobs sudah stabil.
2. C10 SIT evidence package.
3. Final handoff.

Output wajib:

- single analysis queued;
- bulk max 50 validated;
- demo runbook terbarui.

---

## 11. Minimal Commands for Evidence

Ganti placeholder sebelum dipakai. Jangan commit token.

```bash
# Health
curl -i http://127.0.0.1:8000/api/health

# Refresh worklist
docker compose exec api python -m scripts.refresh_worklist --company-id 3 --json

# Enqueue crawl
curl -i -X POST http://127.0.0.1:8000/api/integration/v1/crawl-jobs \
  -H "Authorization: Bearer <service-token>" \
  -H "Idempotency-Key: onebox-169-656-demo-$(date +%s)" \
  -H "Content-Type: application/json" \
  -d '{
    "slot": "manual",
    "targets": [
      {
        "onebox_location_id": 656,
        "target_review_count": 10,
        "sort_by": "newest"
      }
    ]
  }'

# Poll status
curl -sS -H "Authorization: Bearer <service-token>" \
  http://127.0.0.1:8000/api/integration/v1/crawl-jobs/<batch_id>

# Pull review delta
curl -sS -H "Authorization: Bearer <service-token>" \
  "http://127.0.0.1:8000/api/integration/v1/reviews?limit=10"
```

---

## 12. References

- `markdowns/02-meetings-and-decisions/meeting-notes/2026-08-21-voc-progress-review.md`
- `markdowns/01-product-and-backlog/grooming/2026-08-25-voc-grooming-sprint.md`
- `markdowns/02-meetings-and-decisions/adr/ADR-0003-crawl-execution-pull-queue.md`
- `markdowns/02-meetings-and-decisions/adr/ADR-0004-fast-ingestion-labeling-on-demand-ai.md`
- `markdowns/03-architecture/integration/FETCH_JOBS_E2E_CONTRACT.md`
- `markdowns/04-implementation-plans/key-process/PLAN_FAST_INGEST_LABELING_ON_DEMAND_AI.md`
- `markdowns/01-product-and-backlog/jira-specs/DNGO19-3420_fetch-jobs-crawl-dev-spec.md`
