# Prompt Claude - Tuntaskan Fetch Jobs End-to-End di OneBox

Kerjakan implementasi berikut langsung pada repo OneBox. Jangan berhenti pada analisis dan
jangan meminta saya memilih opsi. Ikuti ADR-0003, ADR-0004, dan kontrak
`FETCH_JOBS_E2E_CONTRACT.md`.

## Objective

Satu klik `Mulai Crawl` harus menghasilkan:

```text
crawl real -> raw review di Crawler -> auto-pull ke OneBox -> raw review tersimpan
-> native sentiment labeling -> Kelola Review siap
```

Tidak boleh ada tombol `Tarik Review Sekarang` sebagai langkah wajib. AI analysis tidak
boleh dipanggil dalam flow ini.

## Kondisi Crawler yang sudah tersedia

Kontrak terbaru menerima target per run:

```json
{
  "slot": "manual",
  "targets": [
    {
      "onebox_location_id": 656,
      "target_review_count": 10
    }
  ]
}
```

Status batch menambahkan:

```json
{
  "review_counts": {
    "target": 10,
    "fetched": 10,
    "inserted": 3,
    "duplicate": 7,
    "failed": 0
  }
}
```

Scope token tetap `reviews:read`, `crawl:enqueue`, `crawl:read`.

Source dan date range belum didukung durable crawl API. Untuk demo:

- source dikunci ke Selenium;
- kontrol source dibuat read-only atau disembunyikan;
- kontrol date range dinonaktifkan dan diberi state unavailable;
- jangan mengirim atau berpura-pura menerapkan date range.

## File utama

- `onecloud/app/views/Voc/fetchjobs.volt`
- `onecloud/app/controllers/VocController.php`
- `onecloud/app/library/VoiceOfCustomerSystemClient.php`
- `onecloud/app/services/Provider/VocProvider.php`
- `onecloud/app/services/Ticketing.php`
- `onecloud/app/services/Ruling.php`
- `onecloud/app/views/Voc/reviews.volt`

Worktree sudah dirty. Pertahankan perubahan existing dan integrasikan patch dengan hati-hati.

## Task 1 - Browser request yang nyata

Pada handler `#fj-run`:

1. baca Connection/lokasi yang dipilih;
2. baca target review;
3. validasi target 1-300;
4. buat `client_request_id` UUID sekali per klik;
5. retry request yang sama harus memakai ID yang sama;
6. kirim POST:

```json
{
  "id": 123,
  "target_review_count": 10,
  "client_request_id": "uuid"
}
```

Hapus/nonaktifkan flow simulasi `doFetch()` agar tidak ada progress palsu.

## Task 2 - Controller enqueue

Ubah `VocController::crawlStartAction()`:

- POST only, CSRF/permission existing tetap berlaku;
- validasi Connection milik SiteId sesi dan Enabled;
- validasi target integer 1-300;
- map Connection ke `onebox_location_id`;
- gunakan `client_request_id` sebagai bagian utama Idempotency-Key;
- kirim target lengkap ke client Crawler;
- return `batch_id`, target, status, dan payload status awal.

Jangan lagi membuat key hanya dari lokasi + menit karena dua klik berbeda dalam satu menit
harus dapat menjadi dua run berbeda, sedangkan retry klik yang sama harus idempotent.

## Task 3 - Client Crawler OneBox

Ubah `VoiceOfCustomerSystemClient::enqueueCrawl()` menjadi menerima target lengkap:

```php
enqueueCrawl(array $targets, string $idempotencyKey, array $options = [])
```

Payload minimal:

```php
[
    'slot' => 'manual',
    'targets' => [[
        'onebox_location_id' => $oneboxLocationId,
        'target_review_count' => $targetReviewCount,
    ]],
]
```

Service token hanya berada di backend. Jangan kirim token ke browser atau log.

## Task 4 - State machine dan progress

Implementasikan state:

```text
IDLE -> ENQUEUING -> CRAWLING -> IMPORTING -> LABELING -> COMPLETE
                                      |                    |
                                      +-> PARTIAL_FAILED    +-> FAILED
```

Polling `Voc/crawlStatus` setiap 3-5 detik dengan retry/backoff. Satu network error tidak
boleh menghentikan flow. Batas keseluruhan sekitar 30 menit.

Kenali batch/job status:

- `queued`;
- `running`;
- `retry_wait`;
- `completed`;
- `partial_failed`;
- `failed`;
- `succeeded`;
- `skipped`.

Progress Selenium harus indeterminate saat running. Setelah terminal, tampilkan counter
aktual dari `review_counts`:

```text
Target 10 | Terbaca 10 | Baru 3 | Duplikat 7 | Gagal 0
```

Jangan menghitung review percent dari timer atau angka simulasi.

## Task 5 - Auto-import scoped

Setelah:

- `completed`: jalankan import otomatis;
- `partial_failed`: import review dari job sukses lalu tampilkan warning;
- `failed`: jangan import, tampilkan retry.

Ubah `syncnowAction()` atau buat `crawlImportAction()` yang memakai pipeline receive existing,
tetapi menerima `id=<connection_id>` dan hanya memproses Connection terpilih milik SiteId.
Jangan lagi mengimpor semua Connection aktif untuk satu manual crawl.

Request browser:

```http
POST Voc/crawlImport

id=<connection_id>&crawl_batch_id=<batch_id>
```

Response wajib terstruktur:

```json
{
  "ok": true,
  "connection_id": 123,
  "batch_id": "uuid",
  "pulled": 10,
  "inserted": 3,
  "updated": 0,
  "duplicate": 7,
  "failed": 0,
  "review_url": "#/voc/reviews"
}
```

Jika receive pipeline belum menyediakan semua counter, tambahkan penghitung tanpa mengubah
semantik cursor/checkpoint.

Guardrail:

- checkpoint hanya maju jika seluruh page sukses;
- dedup tetap SiteId + provider + `review_hash`/RemoteId;
- auto-import boleh dipanggil ulang tanpa Message/Ticket ganda;
- `analysis=null` wajib diterima;
- partial item failure harus terlihat dan tidak ditelan.

## Task 6 - Native sentiment labeling

Buktikan program native OneBox sebelum menambah engine baru:

1. inspeksi `Ticketing::creatingTicket()` dan `Ruling::apply()`;
2. inspeksi Rule aktif `RLS1` untuk SiteId demo;
3. buktikan input, output, dan field penyimpanan label;
4. buat tiga data uji positive/negative/neutral;
5. catat nilai sebelum/sesudah pada `Ticket.Sentiment` dan `MessageContent.Meta`.

Query awal:

```sql
SELECT Id, Name, Priority, Conditions, Actions, Enabled
FROM Rule
WHERE SiteId = 169
  AND Enabled = 1
  AND RuleType = 'RLS1'
ORDER BY Priority, Id;
```

Fakta existing yang harus dijaga:

- `Ticket.Sentiment` sekarang juga dipakai untuk rating bintang;
- UI membaca label teks dari `MessageContent.Meta.ai_sentiment`;
- fallback kosong menjadi Netral adalah salah dan harus menjadi `Belum dilabeli` sampai
  labeling benar-benar selesai.

Jika Rule native tidak menghasilkan label teks, laporkan bukti tersebut dan implementasikan
adapter paling tipis yang memanggil program existing, bukan labeling engine baru.

## Task 7 - Completion UX

Setelah import + labeling:

- progress 100%;
- tampilkan ringkasan crawl dan import;
- tampilkan CTA `Buka Kelola Review`;
- CTA menuju `#/voc/reviews`;
- data terbaru harus tampil tanpa menunggu AI.

AI single/bulk merupakan task terpisah. Jangan memanggil endpoint analysis dari Fetch Jobs.

## Acceptance test wajib

1. Target UI 10 terlihat sebagai `target_review_count=10` di status Crawler.
2. Klik ganda/retry request yang sama menghasilkan satu batch.
3. Klik baru menghasilkan batch baru walau pada menit yang sama.
4. UI menangani queued/running/retry/completed/partial_failed/failed/skipped.
5. Network error polling sementara pulih otomatis.
6. Completed memicu auto-import tepat sekali secara logis.
7. Import hanya Connection terpilih.
8. Import ulang menghasilkan inserted 0 dan tidak membuat Ticket ganda.
9. Review langsung terlihat pada Kelola Review tanpa tombol tarik manual.
10. Ollama mati tidak menggagalkan crawl, import, labeling, dan Kelola Review.
11. Label native dibuktikan lewat code path dan data DB.
12. Semua response error aman untuk UI dan tidak membocorkan token.

## Output yang harus diberikan kembali

- daftar file yang diubah;
- ringkasan implementasi per task;
- bukti request/response target 10;
- bukti auto-import;
- bukti native labeling atau blocker berbasis code/DB;
- hasil test;
- command deploy/restart OneBox Dev;
- blocker yang benar-benar memerlukan Sayyid/Infra saja.
