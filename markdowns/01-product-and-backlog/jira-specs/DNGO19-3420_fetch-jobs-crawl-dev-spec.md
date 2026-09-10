# Dev Specification - DNGO19-3420 Fetch Jobs Crawl

**Parent issue:** DNGO19-3420 Fetch Jobs Crawl  
**Tanggal:** 14 Agustus 2026  
**Scope repo:** OneBox / OneCloud dan Crawler System  
**Status:** contract finalization sebelum development lanjutan dan QA end-to-end

---

## Parent Issue Desc

Fetch Jobs Crawl menyediakan mekanisme bagi OneBox untuk memicu proses crawling review secara non-blocking ke Crawler System. Fitur ini dipakai dari layar Fetch Jobs agar admin dapat memilih satu cabang atau seluruh cabang aktif, menentukan target jumlah review, rentang tanggal, dan sumber crawling, lalu menerima `batch_id` untuk memantau proses tanpa menunggu Selenium selesai di request web OneBox.

Branch ini menjadi boundary kontrak antara OneBox dan Crawler System. Setelah crawl selesai, review harus sudah tersimpan cepat di database Crawler, kemudian OneBox melakukan import otomatis melalui pipeline delta yang sudah ada, menyimpan raw review sebagai data VoC, menjalankan labeling sentiment native OneBox, dan membuat layar Kelola Review langsung dapat digunakan. AI analysis tidak masuk critical path Fetch Jobs Crawl; AI dipicu terpisah setelah review tersedia.

---

## Overview

Alur utama yang disepakati:

```text
User OneBox klik Mulai Crawl
  -> OneBox validasi Connection/lokasi/permission
  -> OneBox enqueue crawl ke Crawler System
  -> Crawler balas 202 + batch_id
  -> Crawler worker menjalankan Selenium di background
  -> Crawler menyimpan raw review dan status job
  -> OneBox polling status batch
  -> Saat batch terminal, OneBox auto-import review
  -> OneBox upsert Message/MessageContent
  -> OneBox labeling sentiment native
  -> Kelola Review siap dipakai
```

Kontrak ini mengikuti implementasi yang sudah ada:

- Crawler endpoint: `POST /api/integration/v1/crawl-jobs`.
- Crawler endpoint status: `GET /api/integration/v1/crawl-jobs/{batch_id}`.
- Crawler endpoint history: `GET /api/integration/v1/crawl-jobs?limit=...`.
- OneBox client: `VoiceOfCustomerSystemClient::enqueueCrawl()`.
- OneBox controller: `VocController::crawlStartAction()`, `crawlStatusAction()`, dan `crawlImportAction()`.
- OneBox Fetch Jobs page: `onecloud/app/views/Voc/fetchjobs.volt`.

---

## Current Implementation Status

### Merged / Available

- Service-to-service token sudah digunakan untuk endpoint integration Crawler.
- Scope `crawl:enqueue` digunakan untuk membuat crawl batch.
- Scope `crawl:read` digunakan untuk membaca status dan riwayat batch.
- Endpoint enqueue Crawler sudah non-blocking dan mengembalikan HTTP `202`.
- Crawler sudah memakai `batch_id` publik untuk dipantau OneBox.
- Crawler menyimpan satu `CrawlBatch` per request dan satu `CrawlJob` per target.
- Crawler sudah mendukung idempotency melalui header `Idempotency-Key`.
- Crawler sudah menolak idempotency key yang sama dengan payload berbeda melalui `409 IDEMPOTENCY_CONFLICT`.
- Crawler sudah mendukung `target_review_count` per target dengan batas `1-300`.
- Crawler sudah mendukung optional `date_from`, `date_to`, dan `sort_by`.
- OneBox sudah mengirim `target_review_count` dari layar, bukan membiarkan Crawler memakai default worklist.
- OneBox sudah memakai `client_request_id` sebagai bagian dari idempotency key supaya retry satu klik tidak membuat batch ganda.
- OneBox sudah menyiapkan auto-import melalui `Voc/crawlImport` setelah batch selesai.

### Remaining / Needs Final Decision

- Dry run belum menjadi bagian dari kontrak endpoint Crawler yang aktif. Perlu diputuskan apakah masuk DNGO19-3420 atau dibuat sebagai task terpisah.
- Cancellation belum tersedia di Crawler endpoint. Perlu diputuskan apakah cukup "stop polling di UI" untuk MVP atau perlu cancel durable queue.
- Retry manual dari UI perlu dikunci agar memakai idempotency baru jika user memang ingin run baru.
- Progress bar UI harus memakai status dan counter aktual, bukan estimasi palsu.
- Hubungan formal antara `CrawlJob` dan `FetchLog` perlu disepakati untuk audit/history.
- QA end-to-end harus membuktikan: enqueue -> Selenium crawl -> import -> Kelola Review.

---

## General Design

### Scope

1. Menentukan kontrak request dan response untuk membuat crawl job dari OneBox ke Crawler System.
2. Menentukan pemakaian `batch_id` sebagai public tracking id dan `job_id` sebagai internal per-target id.
3. Menentukan lifecycle status batch dan job.
4. Menentukan parameter target: lokasi, source, target review count, date range, sort order, dan dry run.
5. Menentukan aturan fetch satu lokasi dan fetch seluruh lokasi aktif.
6. Menentukan retry, timeout, cancellation, dan idempotency policy.
7. Menentukan hubungan `CrawlBatch`, `CrawlJob`, dan `FetchLog`.
8. Menentukan boundary tenant, permission, dan validasi lokasi.
9. Menentukan dependency queue, worker, Selenium connector, worklist cache, dan OneBox import.

### Out of Scope

- CRUD master data lokasi.
- CRUD competitor, kecuali bentuk target competitor yang sudah ada di kontrak Crawler.
- Implementasi AI analysis dan analysis jobs.
- Pembuatan Ticket otomatis dari semua review.
- Scheduler harian/randomized slot.
- Migrasi database PostgreSQL ke MySQL.
- Desain ulang dashboard VoC.

---

## Specifics Design

### 1. API Contract - Enqueue Crawl

Endpoint:

```http
POST /api/integration/v1/crawl-jobs
Authorization: Bearer <service_token>
Idempotency-Key: onebox-<site_id>-<target_ids>-<client_request_id>
Content-Type: application/json
```

Request body:

```json
{
  "slot": "manual",
  "targets": [
    {
      "kind": "location",
      "onebox_location_id": 656,
      "target_review_count": 10,
      "date_from": "2026-08-01T00:00:00+07:00",
      "date_to": "2026-08-14T23:59:59+07:00",
      "sort_by": "newest"
    }
  ]
}
```

Rules:

- `slot` optional, dipakai untuk audit asal run. Nilai awal: `manual`.
- `targets` wajib, minimal 1 dan maksimal 500.
- `kind` default `location`.
- `onebox_location_id` wajib untuk `kind=location`.
- `target_review_count` optional di Crawler, tetapi wajib dikirim oleh OneBox UI agar angka yang dipilih user tidak diabaikan.
- `target_review_count` valid `1-300`.
- `date_from` dan `date_to` optional. Jika keduanya kosong, crawler mengambil review tanpa batas tanggal.
- Jika `date_from > date_to`, request ditolak `400`.
- `sort_by` default `newest`.
- Jika date range dipakai, sort harus efektif `newest` karena filtering tanggal hanya aman pada urutan terbaru.

Response sukses:

```json
{
  "data": {
    "batch_id": "4d7a5fae-fd45-4c8b-9d67-15a1e81b9d01",
    "status": "queued",
    "slot": "manual",
    "job_count": 1,
    "counts": {
      "queued": 1,
      "running": 0,
      "retry_wait": 0,
      "succeeded": 0,
      "partial_success": 0,
      "skipped": 0,
      "failed": 0
    },
    "review_counts": {
      "target": 10,
      "scanned": 0,
      "fetched": 0,
      "matched": 0,
      "out_of_range": 0,
      "inserted": 0,
      "duplicate": 0,
      "failed": 0
    },
    "created_at": "2026-08-14T08:00:00+00:00",
    "started_at": null,
    "finished_at": null,
    "targets": [656],
    "kind": "location",
    "competitors": [],
    "jobs": [
      {
        "job_id": 991,
        "onebox_location_id": 656,
        "competitor_id": null,
        "kind": "location",
        "target_review_count": 10,
        "status": "queued",
        "attempts": 0,
        "max_attempts": 3,
        "result": {},
        "error": null,
        "started_at": null,
        "finished_at": null
      }
    ]
  },
  "meta": {
    "api_version": "v1",
    "request_id": "request-id"
  }
}
```

### 2. API Contract - Read Batch Status

Endpoint:

```http
GET /api/integration/v1/crawl-jobs/{batch_id}
Authorization: Bearer <service_token>
```

Usage:

- Dipakai OneBox untuk polling progress Fetch Jobs.
- Scope wajib: `crawl:read`.
- `batch_id` hanya bisa dibaca oleh company yang sama dengan service token.

Response mengikuti bentuk `CrawlBatchResponse` yang sama dengan enqueue, tetapi `status`, `counts`, `review_counts`, dan `jobs[].result` berubah sesuai progress worker.

Contoh response saat running:

```json
{
  "data": {
    "batch_id": "4d7a5fae-fd45-4c8b-9d67-15a1e81b9d01",
    "status": "running",
    "job_count": 1,
    "counts": {
      "queued": 0,
      "running": 1,
      "retry_wait": 0,
      "succeeded": 0,
      "partial_success": 0,
      "skipped": 0,
      "failed": 0
    },
    "review_counts": {
      "target": 10,
      "scanned": 18,
      "fetched": 6,
      "matched": 6,
      "out_of_range": 0,
      "inserted": 0,
      "duplicate": 0,
      "failed": 0
    },
    "jobs": [
      {
        "job_id": 991,
        "onebox_location_id": 656,
        "status": "running",
        "attempts": 1,
        "max_attempts": 3,
        "result": {
          "progress_fetched": 6,
          "progress_scanned": 18
        },
        "error": null
      }
    ]
  },
  "meta": {
    "api_version": "v1",
    "request_id": "request-id"
  }
}
```

### 3. API Contract - List Batch History

Endpoint:

```http
GET /api/integration/v1/crawl-jobs?limit=20
Authorization: Bearer <service_token>
```

Rules:

- Scope wajib: `crawl:read`.
- `limit` minimal 1 dan maksimal 100.
- Response hanya menampilkan batch milik tenant service token.
- `jobs` boleh tidak disertakan pada list untuk menjaga response ringan.
- `targets`, `kind`, dan `competitors` tetap disertakan agar OneBox tidak perlu memanggil detail batch satu per satu hanya untuk menampilkan riwayat.

### 4. Job Identity

Keputusan:

- `batch_id` adalah ID publik yang dikembalikan ke OneBox dan dipakai untuk polling, history, import, dan debugging lintas sistem.
- `job_id` adalah ID internal Crawler untuk satu target di dalam batch.
- OneBox tidak perlu menyimpan `job_id` sebagai primary tracking; cukup tampilkan `job_id` di detail teknis/log jika perlu.
- Satu batch bisa berisi satu job atau banyak job.
- Satu job hanya boleh mewakili salah satu dari:
  - `location` dengan `onebox_location_id`;
  - `competitor` dengan `external_place_id`.

Rationale:

- UI dan operator berpikir dalam satu aksi "run crawl", jadi `batch_id` lebih cocok sebagai tracking id.
- Worker dan retry berpikir dalam satu target, jadi `job_id` tetap diperlukan secara internal.

### 5. Lifecycle Status

Status job:

| Status | Arti | Terminal |
|---|---|---|
| `queued` | Job sudah dibuat dan menunggu worker. | Tidak |
| `running` | Job sedang diklaim worker. | Tidak |
| `retry_wait` | Job gagal sementara dan menunggu retry berikutnya. | Tidak |
| `succeeded` | Crawl target selesai sukses. | Ya |
| `partial_success` | Crawl menghasilkan sebagian data tetapi ada batasan non-fatal. | Ya |
| `skipped` | Target tidak lagi eligible saat worker mengeksekusi. | Ya |
| `failed` | Job gagal setelah retry habis atau error fatal. | Ya |

Status batch:

| Status | Aturan |
|---|---|
| `queued` | Batch baru dibuat dan seluruh job masih queued. |
| `running` | Minimal satu job belum terminal, termasuk `queued`, `running`, atau `retry_wait`. |
| `completed` | Seluruh job terminal dan tidak ada `failed`. |
| `partial_failed` | Sebagian job terminal sukses/skipped/partial, tetapi ada job `failed`. |
| `failed` | Seluruh job terminal dan semuanya `failed`. |

Status yang belum diimplementasikan:

| Status | Rekomendasi |
|---|---|
| `cancelling` | Tambahkan hanya jika cancel endpoint diputuskan masuk scope. |
| `cancelled` | Tambahkan hanya jika cancel endpoint diputuskan masuk scope. |

### 6. Fetch Satu Lokasi

OneBox menerima `id` Connection dari layar Fetch Jobs.

Flow:

1. OneBox validasi user permission dan CSRF.
2. OneBox validasi Connection ada pada `SiteId` aktif.
3. OneBox memastikan Connection `Enabled=1`.
4. OneBox membaca `onebox_location_id` dari Options/metadata Connection.
5. OneBox membuat payload `targets[]` berisi satu target.
6. OneBox mengirim request enqueue ke Crawler.
7. Crawler memvalidasi target terhadap `company_id` service token dan local worklist cache.
8. Jika target belum ada, Crawler mencoba refresh worklist satu kali.
9. Jika tetap tidak ada, Crawler menolak dengan `404 TARGET_NOT_FOUND`.

### 7. Fetch Seluruh Lokasi Aktif

Keputusan:

- Tidak dibuat mode API baru seperti `mode=all_active` di Crawler.
- OneBox tetap menjadi source of truth untuk daftar Connection/lokasi aktif.
- Jika user memilih "seluruh lokasi aktif", OneBox mengekspansi Connection aktif menjadi `targets[]`.
- Crawler hanya menerima target eksplisit dan melakukan validasi tenant/worklist.

Rationale:

- Permission, SiteId, dan Connection aktif adalah domain OneBox.
- Crawler tidak perlu mengetahui menu, role, atau aturan UI OneBox.
- Payload eksplisit membuat idempotency fingerprint lebih jelas dan audit lebih mudah.

Rules:

- Target maksimal per request: 500.
- Setiap target memakai `target_review_count` yang sama dari input user, kecuali nanti ada kebutuhan override per lokasi.
- Jika tidak ada target valid, OneBox menolak sebelum memanggil Crawler.
- Jika sebagian target valid dan sebagian invalid di OneBox, OneBox harus menolak request dan menampilkan target yang perlu diperbaiki, bukan mengirim sebagian diam-diam.

### 8. Source Policy

Untuk DNGO19-3420:

- Source UI yang didukung: `selenium`.
- OneBox menolak source selain `selenium`.
- Crawler tidak menerima field `source` langsung pada endpoint integration. Crawler memakai `source_snapshot` dari master Location/Competitor di worklist/cache.
- Google Maps review adalah target utama.

Rationale:

- Endpoint integration adalah perintah "crawl target", bukan konfigurasi connector.
- Connector/source harus dikelola di master data agar tidak bisa disuntik bebas dari browser.

### 9. Date Range dan Sort Policy

Request target boleh membawa:

- `date_from`
- `date_to`
- `sort_by`

Rules:

- `date_from/date_to` optional.
- Jika range dikirim, `sort_by` efektif harus `newest`.
- Jika user memilih sort selain `newest` bersama range, OneBox/Crawler harus memaksa ke `newest` dan mencatat alasannya di metadata job.
- `target_review_count` berarti target review yang match filter, bukan batas absolut kartu yang discan.
- Dengan date range, Crawler boleh membaca lebih banyak kartu dari target sampai mendapat review yang match atau berhenti karena batas scroll/timeout.

Counters:

- `scanned`: jumlah kartu review yang ditelusuri.
- `matched`: jumlah review yang sesuai filter tanggal.
- `fetched`: jumlah review yang berhasil dibaca/normalisasi.
- `out_of_range`: jumlah review yang dilewati karena tanggal.
- `inserted`: review baru di DB Crawler.
- `duplicate`: review yang sudah ada di DB Crawler.

### 10. Dry Run Policy

Keputusan rekomendasi:

- `dry_run` tidak dimasukkan ke endpoint enqueue aktif sampai ada kebutuhan demo/ops yang jelas.
- Jika dry run dibutuhkan, bentuk terbaik adalah endpoint/parameter validation-only yang tidak membuat `CrawlBatch` durable dan tidak menjalankan Selenium.

Perilaku dry run yang disepakati bila diimplementasikan:

- Memvalidasi service token, scope, tenant, target, date range, source, dan quota.
- Mengembalikan daftar target yang akan di-crawl beserta effective config.
- Tidak menulis Review.
- Tidak membuat Message/MessageContent di OneBox.
- Tidak menjalankan Selenium.
- Tidak mengubah cursor/checkpoint.
- Boleh menulis audit log ringan, tetapi tidak boleh terlihat sebagai Fetch Job sungguhan.

Catatan:

- Saat ini schema `CrawlBatchCreateRequest` memakai `extra="forbid"`, sehingga field `dry_run` akan ditolak jika dikirim. OneBox jangan mengirim field ini sebelum kontraknya resmi.

### 11. Idempotency Policy

Rules:

- Header `Idempotency-Key` wajib.
- Panjang key: 8 sampai 128 karakter.
- Scope idempotency: per `company_id`.
- Key sama + payload sama mengembalikan `batch_id` yang sama.
- Key sama + payload berbeda menghasilkan `409 IDEMPOTENCY_CONFLICT`.
- Payload fingerprint mencakup:
  - `slot`;
  - daftar `onebox_location_id`;
  - `target_review_count`;
  - `date_from/date_to`;
  - `sort_by`;
  - target competitor jika ada.

OneBox key pattern:

```text
onebox-<site_id>-<target_ids>-<client_request_id>
```

Rules OneBox:

- `client_request_id` dibuat sekali saat user memulai satu job dari UI.
- Retry karena network error memakai `client_request_id` yang sama.
- Run baru yang disengaja user harus membuat `client_request_id` baru.

### 12. Retry Policy

Current Crawler behavior:

- Worker mengambil job dengan status `queued` atau `retry_wait`.
- Jika job `running` lease-nya expired, job dapat diklaim ulang.
- Max attempts mengikuti setting `crawl_worker_max_attempts`.
- Default operational target: 3 attempts.
- Backoff menggunakan `crawl_worker_retry_base_seconds * 5^(attempts-1)`.
- Jika attempts belum habis, status menjadi `retry_wait`.
- Jika attempts habis, status menjadi `failed`.

Rules:

- Retry tidak boleh membuat batch baru.
- Retry memakai `job_id` dan `batch_id` yang sama.
- Error code dan message terakhir harus tersimpan di job.
- OneBox menampilkan retry sebagai status, bukan sebagai error final.

### 13. Timeout Policy

Rules:

- Request enqueue harus selesai cepat dan tidak menunggu Selenium.
- Target response time enqueue: di bawah 1 detik pada kondisi normal.
- Worker Selenium punya timeout per job.
- Current code memakai batas eksekusi job sekitar 600 detik.
- Jika timeout terjadi:
  - job masuk retry jika attempts masih tersedia;
  - job menjadi failed jika attempts habis;
  - batch status dihitung ulang dari status semua job.

OneBox UI:

- Polling status sekitar 3-5 detik.
- UI harus punya deadline lokal agar tidak polling selamanya.
- Deadline UI tidak boleh membatalkan job Crawler kecuali cancel endpoint resmi tersedia.

### 14. Cancellation Policy

Current status:

- Cancel endpoint belum tersedia di Crawler integration API.
- OneBox tidak boleh menampilkan tombol cancel yang mengklaim menghentikan Selenium jika backend belum mendukungnya.

Keputusan rekomendasi untuk MVP:

- Cancellation tidak masuk scope DNGO19-3420 MVP.
- UI boleh menyediakan "Tutup" atau "Berhenti memantau" yang hanya menghentikan polling di browser.
- Job tetap berjalan sampai terminal.

Jika cancellation diputuskan masuk scope lanjutan:

```http
POST /api/integration/v1/crawl-jobs/{batch_id}/cancel
Authorization: Bearer <service_token>
```

Rules cancel lanjutan:

- Scope baru yang disarankan: `crawl:cancel`, atau gunakan `crawl:enqueue` jika ingin tetap minimal.
- Job `queued` dan `retry_wait` bisa langsung `cancelled`.
- Job `running` hanya bisa diberi flag `cancel_requested`; worker berhenti di safe checkpoint.
- Review yang sudah tersimpan tidak dihapus.
- Import OneBox tetap boleh menarik hasil parsial dari job yang selesai sebelum cancel.

### 15. Tenant, Permission, and Location Validation

Crawler tenant rules:

- Service token terikat ke satu `company_id`.
- Token company A tidak bisa enqueue target company B.
- Token company A tidak bisa membaca `batch_id` company B.
- Scope `crawl:enqueue` wajib untuk enqueue.
- Scope `crawl:read` wajib untuk status/history.

OneBox permission rules:

- Browser user harus punya permission menu/aksi Fetch Jobs.
- Browser user tidak pernah menerima service token.
- Service token disimpan di Connection Options/server-side config.
- OneBox backend yang melakukan call ke Crawler, bukan JavaScript browser langsung.

Location validation:

- OneBox memvalidasi Connection aktif di SiteId aktif.
- Crawler memvalidasi target pada local worklist/cache berdasarkan `company_id`.
- Jika local worklist stale, Crawler mencoba refresh worklist sekali.
- Jika target tetap tidak valid, error final `TARGET_NOT_FOUND`.

### 16. Relationship: Crawl Batch, Crawl Job, Fetch Log

Model konseptual:

```text
CrawlBatch
  1..N CrawlJob
       1..N FetchLog / execution audit
```

Current durable model:

- `crawl_batches`: satu request enqueue dari OneBox.
- `crawl_jobs`: satu target lokasi/kompetitor dalam batch.
- `fetch_logs`: riwayat fetch/crawl yang dipakai existing service untuk audit hasil pengambilan.

Rules:

- `CrawlBatch.public_id` menjadi `batch_id` publik.
- `CrawlJob.id` menjadi `job_id` internal.
- `FetchLog` harus bisa ditelusuri ke company, location/competitor, waktu, status, dan counter hasil.
- Jika memungkinkan, `FetchLog` perlu menyimpan `batch_id` atau metadata `crawl_batch_id` agar debugging dari OneBox ke Crawler tidak perlu membaca log mentah.
- Untuk all active, satu batch punya banyak job dan banyak fetch log.
- Untuk retry, fetch log boleh lebih dari satu per job selama attempts dibedakan.

### 17. OneBox Auto Import Boundary

Fetch Jobs Crawl selesai secara fungsional hanya jika OneBox melakukan auto-import setelah batch terminal.

Rules:

- OneBox memanggil `Voc/crawlImport` setelah batch `completed` atau `partial_failed`.
- `crawlImport` menerima `id` Connection dan `crawl_batch_id`.
- Import memakai pipeline receive/delta yang sudah ada.
- Checkpoint/cursor hanya maju jika pull page sukses.
- Dedup tetap memakai kombinasi SiteId/provider/review identity.
- `analysis=null` tidak boleh menggagalkan raw ingestion.
- Ticket tidak dibuat otomatis untuk semua review.
- Label sentiment native OneBox dijalankan setelah raw review masuk.

### 18. Error Contract

Common Crawler errors:

| HTTP | Code | Arti | Tindakan OneBox |
|---|---|---|---|
| 400 | `INVALID_IDEMPOTENCY_KEY` | Header idempotency kosong/terlalu pendek/terlalu panjang. | Perbaiki generator key. |
| 400 | `INVALID_TARGETS` | Tidak ada target valid atau override target salah. | Tampilkan validasi input. |
| 401 | auth error | Token tidak valid/expired/revoked. | Ganti service token. |
| 403 | `INSUFFICIENT_SCOPE` | Token tidak punya scope yang dibutuhkan. | Terbitkan token dengan `crawl:enqueue`/`crawl:read`. |
| 404 | `TARGET_NOT_FOUND` | Target tidak ada, disabled, atau beda tenant. | Cek lokasi aktif, worklist, dan tenant token. |
| 409 | `IDEMPOTENCY_CONFLICT` | Key sama dipakai untuk payload berbeda. | Buat `client_request_id` baru untuk run baru. |
| 422 | validation error | Payload tidak sesuai schema. | Perbaiki field request. |

OneBox harus menerjemahkan error menjadi pesan operasional yang jelas, bukan menampilkan stack trace.

---

## User Actions

### Action 1 - Fetch Satu Cabang

1. User membuka Fetch Jobs.
2. User memilih satu cabang.
3. User mengisi target review `1-300`.
4. User memilih rentang tanggal jika diperlukan.
5. User klik `Mulai Crawl`.
6. UI menampilkan progress: enqueue, queued/running, importing, labeling, completed.
7. Setelah selesai, user klik `Buka Kelola Review`.

Expected:

- Satu `batch_id` dibuat.
- Satu `job_id` dibuat.
- Review masuk ke Crawler.
- OneBox auto-import review.
- Kelola Review menampilkan data baru/duplikat sesuai hasil import.

### Action 2 - Fetch Semua Cabang Aktif

1. User memilih mode semua cabang aktif.
2. OneBox membangun daftar Connection aktif.
3. OneBox mengirim `targets[]` eksplisit ke Crawler.
4. UI menampilkan ringkasan jumlah target.
5. Polling berjalan sampai batch terminal.
6. Import dijalankan per Connection yang relevan.

Expected:

- Satu batch berisi banyak jobs.
- Target invalid tidak dikirim diam-diam.
- Status partial tetap bisa mengimpor cabang yang sukses.

### Action 3 - Retry Run

1. User melihat run gagal/partial di riwayat.
2. User klik ulang dari riwayat.
3. OneBox menyusun ulang target, target count, date range, dan sort dari metadata run.
4. User menekan `Mulai`.
5. OneBox membuat idempotency key baru karena ini run baru yang disengaja.

Expected:

- Batch baru dibuat.
- Review duplicate tidak menghasilkan data ganda.
- Error lama tidak menempel ke run baru.

### Action 4 - Monitor History

1. User membuka Fetch Jobs.
2. OneBox memanggil history Crawler.
3. UI menampilkan batch terbaru, status, target, counters, dan waktu.
4. User membuka detail batch bila perlu.

Expected:

- Riwayat berasal dari Crawler System, bukan mock/static data.
- Data ditampilkan ringkas dan bisa dipakai untuk audit.

---

## Acceptance Criteria

- Kontrak request dan response `POST /api/integration/v1/crawl-jobs` terdokumentasi.
- Kontrak response status dan history batch terdokumentasi.
- Keputusan `batch_id` sebagai public tracking id dan `job_id` sebagai internal target id terdokumentasi.
- Status lifecycle job dan batch terdokumentasi.
- Transition status terminal dan non-terminal terdokumentasi.
- Aturan tenant, service token, scope, permission, dan validasi lokasi terdokumentasi.
- Batas target review `1-300` terdokumentasi.
- Batas target per request maksimal 500 terdokumentasi.
- Aturan date range dan sort order terdokumentasi.
- Aturan fetch satu lokasi dan fetch seluruh lokasi aktif terdokumentasi.
- Perilaku dry run disepakati, termasuk keputusan bahwa field ini belum aktif pada endpoint sekarang.
- Retry, timeout, cancellation, dan idempotency policy terdokumentasi.
- Hubungan `CrawlBatch`, `CrawlJob`, dan `FetchLog` terdokumentasi.
- Dependency terhadap queue, worker, Selenium connector, worklist cache, dan OneBox import terdokumentasi.
- Scope mendapatkan approval sebelum implementasi lanjutan dimulai.

---

## QA Checklist

### Crawler System

- `POST /api/integration/v1/crawl-jobs` dengan scope `crawl:enqueue` menghasilkan `202`.
- Request tanpa `Idempotency-Key` ditolak.
- Key sama + payload sama mengembalikan `batch_id` sama.
- Key sama + payload beda menghasilkan `409`.
- Token tanpa `crawl:enqueue` menghasilkan `403`.
- Token tenant lain tidak bisa enqueue/read target tenant lain.
- `GET /api/integration/v1/crawl-jobs/{batch_id}` membutuhkan `crawl:read`.
- Worker mengubah status dari `queued` ke `running` lalu terminal.
- Result akhir memuat `review_counts` yang benar.

### OneBox

- Fetch satu cabang mengirim `target_review_count`.
- Fetch semua cabang aktif mengirim `targets[]` eksplisit.
- Source selain Selenium ditolak.
- UI tidak freeze saat Selenium berjalan.
- UI polling status memakai `batch_id`.
- Setelah terminal, UI memanggil auto-import.
- Review muncul di Kelola Review tanpa tombol tarik review kedua.
- Label sentiment native terisi setelah import.
- Error `INSUFFICIENT_SCOPE`, `TARGET_NOT_FOUND`, dan `IDEMPOTENCY_CONFLICT` diterjemahkan menjadi pesan operasional.

---

## Approval Notes

Hal yang perlu disetujui sebelum development lanjutan:

1. `batch_id` menjadi satu-satunya public tracking id untuk OneBox.
2. `all active` diekspansi oleh OneBox menjadi `targets[]`, bukan mode baru di Crawler.
3. `dry_run` belum aktif di endpoint DNGO19-3420; jika dibutuhkan, dibuat task terpisah.
4. `cancel` belum masuk MVP; UI hanya boleh berhenti memantau sampai endpoint cancel resmi dibuat.
5. AI analysis tetap terpisah dari Fetch Jobs Crawl.
6. Ticket tidak dibuat otomatis dari semua review; eskalasi tetap aksi manusia.
