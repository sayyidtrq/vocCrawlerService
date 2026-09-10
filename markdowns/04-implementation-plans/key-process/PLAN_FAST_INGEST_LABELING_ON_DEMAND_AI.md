# Implementation Plan - Fast Ingestion, OneBox Labeling, dan On-Demand AI

> Acuan keputusan: `../decisions/ADR-0004-fast-ingestion-labeling-on-demand-ai.md`
> Tujuan: review cepat masuk ke OneBox dan dapat dikelola, sementara AI analysis berjalan
> terpisah hanya untuk review yang dipilih pengguna.

## 1. Target flow

```text
1. Add/enable Location di OneBox
2. OneBox enqueue crawl
3. Crawler scrape, normalize, dedup, dan persist raw review
4. OneBox menarik discovery delta tanpa menunggu AI
5. OneBox menyimpan review ke database
6. OneBox menjalankan labeling sentiment existing
7. Review tampil dan fungsi Kelola Review langsung aktif
8. User memilih satu atau beberapa review
9. OneBox enqueue AI analysis
10. Crawler AI worker memproses job
11. OneBox meng-update review/Ticket existing dengan hasil AI
```

Definition of success utama: langkah 1-7 selesai cepat dan tetap berfungsi ketika layanan
AI lambat atau tidak tersedia.

## 2. Kondisi existing dan gap

### Sudah tersedia

- crawl job non-blocking dan durable;
- Selenium real crawl berhasil di Dev;
- persistence, dedup, dan review hash;
- service-token tenant binding;
- discovery/delta review contract;
- `AnalysisService` dan local/cloud LLM clients;
- endpoint user JWT untuk pending, rerun lokasi, dan rerun satu review;
- penyimpanan analysis dan token usage.

### Gap

- analysis endpoint existing masih synchronous dan memakai JWT user;
- belum ada service endpoint untuk enqueue single/bulk analysis dari OneBox;
- analysis masih serial;
- belum ada durable analysis queue, progress, retry per item, atau dead-letter state;
- discovery dan enrichment masih dapat muncul pada delta yang sama tanpa event semantics;
- metadata live/backfill dan eligibility belum final;
- lokasi program labeling sentiment existing OneBox belum diverifikasi oleh Claude.

## 3. Kontrak lifecycle review

### 3.1 Review discovery

Review raw harus dapat dikirim walaupun seluruh field AI `null`.

Field minimum:

```json
{
  "id": 123,
  "review_hash": "stable-hash",
  "location_id": 8,
  "onebox_location_id": 656,
  "source_review_time": "2026-07-31T01:00:00Z",
  "first_seen_at": "2026-07-31T02:00:00Z",
  "ingestion_mode": "live",
  "eligible_for_ticket": true,
  "analysis_status": "not_requested",
  "analysis": null
}
```

### 3.2 Analysis enrichment

Enrichment mengacu pada identity review yang sama:

```json
{
  "review_id": 123,
  "review_hash": "stable-hash",
  "analysis_status": "completed",
  "analysis_completed_at": "2026-07-31T03:00:00Z",
  "analysis": {
    "summary": "...",
    "recommended_action": "...",
    "urgency": "high",
    "issue_category": "waiting_time"
  },
  "token_usage": {
    "prompt_tokens": 600,
    "completion_tokens": 200,
    "total_tokens": 800
  }
}
```

OneBox wajib melakukan update terhadap Ticket/review existing, bukan create baru.

## 4. Target API AI asynchronous

### Enqueue

```http
POST /api/integration/v1/analysis-jobs
Authorization: Bearer <service-token>
Idempotency-Key: <unique-key>
Content-Type: application/json
```

Single review:

```json
{
  "review_ids": [123]
}
```

Bulk review:

```json
{
  "review_ids": [123, 124, 125],
  "priority": "normal"
}
```

Response:

```json
{
  "analysis_batch_id": "uuid",
  "status": "queued",
  "total": 3
}
```

### Read status

```http
GET /api/integration/v1/analysis-jobs/{analysis_batch_id}
```

Response minimum:

```json
{
  "status": "processing",
  "total": 3,
  "pending": 1,
  "processing": 1,
  "completed": 1,
  "failed": 0,
  "tokens_used": 839
}
```

Scope service yang disarankan:

- `analysis:enqueue`;
- `analysis:read`;
- `reviews:read` tetap untuk delta.

Batas awal bulk: maksimum 50 review per request. Request harus tenant-scoped dan menolak
review ID milik company lain.

## 5. Implementasi Crawler System - Codex

### CS-A1 - Pisahkan crawl dari analysis

- Pastikan crawl worker berhenti setelah raw review dipersist.
- Jangan memanggil `AnalysisService` otomatis dari crawl job.
- Pertahankan pipeline legacy hanya untuk operasi internal; jangan dipakai flow OneBox.

**DoD:** crawl tetap sukses ketika Ollama mati.

### CS-A2 - Metadata discovery dan eligibility

- Tambahkan/konfirmasi `first_seen_at` dan `source_review_time`.
- Tambahkan `ingestion_mode`, `eligible_for_ticket`, dan `analysis_status` bila belum ada.
- Buat migration dan projection contract secara backward-compatible.
- Jangan mengganti makna `review_hash`.

**DoD:** raw review dapat dibedakan antara live dan backfill tanpa melihat waktu analysis.

### CS-A3 - Durable analysis queue

- Buat `analysis_batch` dan `analysis_job` atau struktur setara.
- Simpan lease, attempt, error tersanitasi, timestamps, dan token usage.
- Implementasikan retry per review dan status batch partial.
- Mulai satu worker dengan concurrency `2`; naikkan hanya setelah benchmark.

**DoD:** restart worker tidak menghilangkan job dan satu item gagal tidak menggagalkan item lain.

### CS-A4 - Service API single/bulk

- Implementasikan enqueue dan status endpoint.
- Terapkan scope, tenant binding, idempotency, dan bulk limit.
- Response enqueue harus `202` dalam waktu singkat.

**DoD:** browser/UI tidak pernah menunggu inference selesai.

### CS-A5 - Discovery vs enrichment sync

Opsi pilihan: satu delta contract dengan `event_type`/`change_type`, atau dua cursor
terpisah. Pilih bentuk yang paling sedikit mematahkan consumer existing, tetapi wajib
membedakan:

- `review.discovered`;
- `review.analysis_completed`.

**DoD:** analysis review lama hanya menghasilkan update dan tidak dapat dianggap discovery baru.

### CS-A6 - Performance benchmark

Uji 1, 10, dan 50 review menggunakan `gemma3:1b`:

- elapsed time;
- average seconds/review;
- p50 dan p95 latency;
- success/failed;
- tokens/review;
- CPU/RAM;
- concurrency 1 vs 2.

Target awal: 50 review selesai 15-30 menit tanpa merusak stabilitas Ollama. Jika target
tidak tercapai, gunakan provider cloud sebagai fallback atau turunkan scope output AI.

## 6. Implementasi OneBox - Claude

### OB-A1 - Discovery program labeling existing

Claude harus mencari dan melaporkan:

- class/service/function labeling sentiment;
- entry point yang memanggilnya;
- input yang dibutuhkan dari review;
- output dan field penyimpanan `positive/negative/neutral`;
- apakah otomatis dijalankan oleh `Ticketing::addTicket`/`Service\Ruling` atau mekanisme lain;
- tenant/SiteId scoping;
- test atau penggunaan produksi existing.

Kandidat awal dari dokumen existing adalah `Service\Ruling`, `Ticketing::addTicket`, tabel
`Rule`, dan pola Media Monitoring. Ini hanya petunjuk, bukan kesimpulan. Jangan membuat
engine baru sebelum hasil discovery ditulis.

### OB-A2 - Fast raw ingestion

- Consumer menerima review walaupun `analysis=null`.
- Upsert memakai provider + tenant + `review_hash`.
- Simpan review ke database dan tampilkan segera.
- Jalankan labeling sentiment existing.
- Aktifkan Kelola Review tanpa menunggu AI.
- Terapkan live/backfill policy sebelum membuat Ticket operasional.

**DoD:** review dapat dilihat, difilter, dibuka, di-assign, dan diberi tindak lanjut saat AI offline.

### OB-A3 - UI single dan bulk selection

Tambahkan:

- checkbox per review dan select-all halaman;
- aksi `Analisis AI` untuk satu atau beberapa review;
- confirmation yang menampilkan jumlah item;
- status badge `Belum dianalisis`, `Menunggu`, `Diproses`, `Selesai`, `Gagal`;
- progress batch dan tombol retry item gagal;
- disable action untuk item yang sedang diproses.

Service token hanya berada di backend OneBox. Browser memanggil controller OneBox.

### OB-A4 - AI entitlement dan metering

- Verifikasi feature flag/benefit sebelum enqueue.
- Batasi jumlah review bulk sesuai kuota.
- Simpan `analysis_batch_id` dan request identity.
- Setelah selesai, catat token usage secara idempotent.

### OB-A5 - Apply enrichment

- Update Ticket/Message existing berdasarkan remote review identity.
- Isi summary, recommended action, urgency, dan issue category sesuai mapping final.
- Jangan menimpa label sentiment native kecuali keputusan produk berikutnya menyatakan demikian.
- Jangan membuat Ticket baru dari event analysis.

## 7. Urutan implementasi dua agent

```text
Claude: OB-A1 discovery labeling --------------------+
                                                       |
Codex: CS-A1 + CS-A2 -> raw contract -----------------+-> OB-A2 fast ingestion
                                                       |
Codex: CS-A3 + CS-A4 -> analysis async API -----------+-> OB-A3 UI single/bulk
                                                       |
Codex: CS-A5 + CS-A6 ------------------------------- OB-A4 + OB-A5
```

Prioritas:

1. Pastikan review raw cepat masuk dan bisa dikelola.
2. Tutup risiko review historis dengan eligibility.
3. Bangun analysis queue/API asynchronous.
4. Bangun UI single/bulk.
5. Benchmark dan optimasi concurrency.

## 8. Acceptance test end-to-end

| Test | Expected |
|---|---|
| Crawl ketika AI mati | Review tetap tersimpan dan crawl sukses |
| Pull raw review | Review masuk OneBox dengan analysis null |
| Native labeling | Sentiment positive/negative/neutral terisi melalui program existing |
| Kelola sebelum AI | Assign/status/note dapat dilakukan |
| Single analysis | Satu job queued, UI tidak blocking, Ticket existing ter-update |
| Bulk analysis | Maksimum 50 item, progress dan partial failure terlihat |
| Rerun idempotent | Tidak ada Ticket atau usage ganda |
| Historical review | Tersimpan sebagai backfill dan tidak otomatis menjadi Ticket operasional |
| Enrichment review lama | Hanya update identity existing, bukan create |
| Tenant isolation | Review/job tenant lain ditolak tanpa kebocoran data |

## 9. Rollout aman

1. Deploy metadata dan raw-ingestion behavior di belakang feature flag.
2. Aktifkan satu site Dev dan verifikasi labeling native.
3. Aktifkan single AI analysis.
4. Aktifkan bulk maksimum 10, lalu naikkan ke 50 setelah benchmark.
5. Pantau duplicate Ticket, queue age, analysis failure rate, dan token usage.
6. Baru aktifkan pada tenant/site berikutnya.

## 10. Definition of Done

- Review hasil scrape masuk OneBox tanpa menunggu AI.
- Label sentiment native OneBox berjalan dan terbukti lokasi kodenya.
- Review dapat dikelola segera setelah ingestion.
- AI analysis hanya berjalan setelah user memilih single/bulk.
- Enqueue AI non-blocking dan statusnya terlihat.
- Hasil AI meng-update review/Ticket existing secara idempotent.
- Review historis tidak berubah menjadi Ticket baru akibat analysis.
- Benchmark 50 review dan kapasitas server terdokumentasi.