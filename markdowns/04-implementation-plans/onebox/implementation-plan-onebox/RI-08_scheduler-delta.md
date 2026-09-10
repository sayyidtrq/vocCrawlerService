# RI-08 - Scheduler, Delta Sync, dan Riwayat Crawl (maks. 5 MD)

> ⚠️ **DI-AMANDEMEN [ADR-0003](../../../02-meetings-and-decisions/adr/ADR-0003-crawl-execution-pull-queue.md) (2026-07-23).**
> Yang **tetap berlaku**: OneBox adalah **satu-satunya owner scheduler**; occurrence tiga slot,
> planned_at random ter-persist, timezone site, unique `(site_id, local_date, slot)`, no-overlap,
> retry policy, dua histori. Yang **berubah**: bentuk trigger dari **fetch sinkron menunggu Selenium**
> → **kick non-blocking** (`POST /api/integration/v1/crawl-jobs`, balas `batch_id` seketika) lalu pull
> delta review. VoC kini punya **antrean crawl durable + worker** — mengisi gap yang RI-08 tandai di
> §3/§14 ("fetch synchronous/blocking, belum punya worker/scheduler durable"). Beban Selenium dikendalikan
> concurrency worker + rate limit, bukan satu request panjang.

> Keputusan utama: scheduler dijalankan di OneBox untuk memicu pull dari Crawler System. Crawler System tetap menjadi provider data dan tidak membuat scheduler kedua untuk flow OneBox.

## 1. Tujuan dan Definition of Done

VoiceOfCustomerSystemTask::syncAction berjalan tiga kali per hari pada waktu yang tersebar secara acak di dalam window bisnis, menarik data secara incremental, aman saat task terpicu dua kali, dan dapat diaudit oleh user.

Selesai jika:
- setiap SiteId aktif memiliki paling banyak satu run untuk setiap kombinasi tanggal lokal dan slot;
- tersedia tiga slot: pagi 05:00-07:00, siang 11:00-13:00, malam 21:00-23:00;
- waktu dipilih ulang setiap tanggal, tetapi pilihan disimpan sehingga restart atau retry tidak mengubah jadwal hari itu;
- run memakai checkpoint delta dan tidak membuat Ticket atau Message duplikat;
- UI menampilkan next scheduled run dan histori run dengan status serta ringkasan hasil;
- kegagalan satu slot tidak membuat catch-up storm atau memajukan checkpoint secara prematur.

## 2. Challenge terhadap randomisasi

Randomisasi masuk akal untuk mengurangi pola trafik yang mudah ditebak dan menyebarkan beban. Namun scheduler tidak boleh menghitung jam baru setiap restart atau retry. Jika iya, user tidak dapat memperkirakan jadwal dan satu hari bisa memiliki beberapa crawling.

Keputusan yang direkomendasikan:
1. Gunakan granularitas menit dan uniform random di dalam window setengah terbuka: pagi 05:00-06:59, siang 11:00-12:59, malam 21:00-22:59.
2. Generate satu planned_at per SiteId + local_date + slot, lalu persist sebelum task dijalankan. Jangan generate now + random pada setiap tick.
3. Retry tetap memakai occurrence dan planned_at yang sama.
4. Gunakan timezone SiteId, default Asia/Jakarta, bukan timezone container.
5. Jika banyak SiteId, randomize per SiteId atau batch kecil. Jangan menembakkan semua lokasi secara paralel pada menit yang sama.
6. Jika run melewati batas window, biarkan selesai; jangan memotong data. Slot berikutnya tidak boleh overlap karena distributed lock.

Randomisasi adalah jitter operasional, bukan mekanisme keamanan dan bukan jaminan review selalu tampil sebelum jam tujuh. UI tetap harus menampilkan waktu terencana dan waktu aktual.

## 3. Boundary sistem

Flow yang benar:

OneBox scheduler
  -> VoiceOfCustomerSystemTask per SiteId/Connection
  -> VoiceOfCustomerSystemClient pull delta
  -> Crawler System GET /api/integration/v1/reviews
  -> Ticket + Message + MessageContent + Contact

Crawler System saat ini memiliki POST /api/fetch-jobs dan /all-active yang synchronous/blocking. Endpoint tersebut cocok untuk manual/admin atau worker terkontrol, bukan request scheduler yang menunggu Selenium lama. Crawler System memiliki fetch_logs untuk histori crawling source, tetapi belum memiliki entitas jadwal OneBox.

Jangan membuat dua scheduler independen yang sama-sama menarik data untuk OneBox. Itu menggandakan beban Selenium, membuat waktu hasil sulit dijelaskan, dan menyulitkan checkpoint.

## 4. Prasyarat

- RI-05: VoiceOfCustomerSystemTask dan ingestion idempotent stabil.
- RI-09: error handling, retry, dan ringkasan run selesai sebelum jadwal bersama diaktifkan.
- RI-04: client memakai timeout dan service token.
- RI-03: base URL dari container OneBox sudah terbukti.
- Crawler System: updated_since/checkpoint contract dan dedup tersedia.

## 5. Model data dan state

### 5.1 Schedule occurrence di OneBox

Persist occurrence di database OneBox, atau gunakan storage scheduler existing bila durable dan tenant-scoped. Minimum field:

| Field | Fungsi |
|---|---|
| site_id / connection_id | Scope tenant dan target OneBox |
| local_date | Tanggal berdasarkan timezone site |
| slot | morning, afternoon, night |
| window_start, window_end | Window yang digunakan |
| planned_at | Menit random yang telah dipersist |
| timezone | Contoh Asia/Jakarta |
| status | planned, running, success, partial_success, failed, skipped |
| started_at, finished_at | Waktu aktual |
| attempt_count | Jumlah attempt pada occurrence |
| fetched, inserted, deduped, failed | Ringkasan hasil |
| error_code, request_id | Troubleshooting tanpa credential |

Constraint wajib: unique (site_id, local_date, slot). Redis boleh dipakai untuk lock atau cursor, tetapi jangan sebagai satu-satunya histori.

### 5.2 Checkpoint delta

Checkpoint tetap di OneBox per SiteId. Checkpoint hanya maju setelah semua halaman dan mapping dalam occurrence sukses sesuai policy. Jika partial failure, status menjadi partial/failed dan checkpoint tidak dianggap selesai. Cursor dari Crawler System disimpan opaque.

### 5.3 Dua histori yang berbeda

- Histori scheduler OneBox: kapan direncanakan, dijalankan, status pull, dan berapa data masuk ke OneBox.
- fetch_logs Crawler System: kapan Selenium mengambil source per lokasi dan berapa review baru, duplikat, atau gagal.

User perlu histori scheduler di OneBox. Engineer memakai fetch_logs dan container log Crawler untuk diagnosis source. Keduanya jangan dicampur.

## 6. Algoritma jadwal harian

Pada awal setiap tanggal lokal, scheduler melakukan upsert tiga occurrence untuk setiap SiteId aktif:

for site in active_sites:
  for slot in [morning, afternoon, night]:
    if occurrence belum ada:
      planned_at = uniform_random_minute(window[slot])
      insert occurrence dengan status planned

Worker hanya mengeksekusi occurrence yang planned_at <= now, status planned, dan lock berhasil. Idempotency key adalah site_id:local_date:slot. Setelah lock dilepas, status final wajib tercatat walaupun gagal.

Jangan membuat occurrence baru untuk retry. Jika satu hari terlewat karena outage, default terbaik adalah menandai slot skipped atau failed lalu menunggu slot berikutnya. Catch-up hanya melalui command manual eksplisit.

## 7. Locking dan concurrency

- Gunakan lock existing OneBox sesuai pola scheduler yang ditemukan.
- TTL lock lebih panjang dari timeout normal dan diperbarui heartbeat bila task lama.
- Lock key: voc:sync:{site_id}:{local_date}:{slot}.
- Cek status occurrence dan idempotency key dalam transaksi sebelum pull.
- Jangan menjalankan dua sync untuk SiteId yang sama bersamaan.
- Banyak lokasi diproses sequential atau bounded concurrency, bukan parallel tanpa batas.

## 8. Retry dan failure policy

| Kondisi | Policy |
|---|---|
| 401 token | Tidak loop; tandai auth failure dan rotate credential |
| 403 scope/tenant | Tidak retry otomatis; konfigurasi salah |
| 404 mapping | Tidak retry otomatis; perbaiki mapping |
| timeout/5xx | Maksimal 2 retry dengan exponential backoff dan jitter kecil |
| satu review gagal dipetakan | Isolasi item; lanjutkan batch; partial_success |
| Crawler down sepanjang window | failed, checkpoint tidak maju, tunggu slot berikutnya |
| duplicate saat rerun | Normal/idempotent, tampilkan sebagai deduped |

Retry tidak boleh membuat jadwal baru atau mengulang seluruh hari secara agresif. Cursor hanya maju setelah halaman dan persist Ticket selesai.

## 9. UI dan histori

User minimal melihat:
- status scheduler enabled/disabled;
- timezone dan tiga window;
- next scheduled run per SiteId;
- actual start/finish dan durasi;
- status planned/running/success/partial_success/failed/skipped;
- fetched, inserted, deduped, failed;
- error code dan request ID aman;
- Run now dengan confirmation untuk admin.

Endpoint OneBox yang direkomendasikan, menyesuaikan convention existing:

GET  /api/voice-of-customer/schedules
GET  /api/voice-of-customer/schedules/next
GET  /api/voice-of-customer/schedule-runs?site_id=...&from=...&to=...
POST /api/voice-of-customer/schedule-runs/manual

Response harus memiliki planned_at, started_at, finished_at, slot, status, dan counters. Jangan mengembalikan credential, raw review text, atau service token.

## 10. Audit scheduler existing

Verifikasi di repo/deployment OneBox sebelum coding:

rg -n "SonarTask|CrawlerTask|scheduler|cron|Gearman|supervisor|receiveConnection" .
docker service ls
docker service inspect <scheduler-service>
crontab -l

Ikuti pola scheduler existing. Jangan menambahkan Celery atau Redis Queue baru hanya untuk tiga window jika Gearman atau scheduler OneBox sudah menjadi standar deployment.

## 11. Cara verifikasi

1. Freeze clock atau gunakan interval pendek di dev.
2. Pastikan satu SiteId menghasilkan tepat tiga occurrence per tanggal.
3. Restart worker sebelum planned_at; planned_at tetap sama.
4. Trigger worker dua kali bersamaan; hanya satu occurrence running.
5. Simulasikan timeout; retry memakai occurrence yang sama dan checkpoint tidak maju saat gagal.
6. Rerun setelah sebagian data masuk; Ticket dan Message tidak duplikat.
7. UI menampilkan planned dan actual time serta histori minimal tujuh hari.
8. Uji server UTC dan browser Asia/Jakarta; window tetap sesuai timezone SiteId.

Evidence minimum:
- site_id/date/slot unik;
- planned_at stabil setelah restart;
- maksimal satu run aktif per site;
- page dan checkpoint konsisten;
- rerun menghasilkan inserted baru dan deduped benar;
- planned/started/finished/status/counters tampil.

## 12. Risiko tambahan

- Randomisasi terlalu lebar membuat sistem terasa tidak predictable. Tampilkan planned time dan window.
- Tiga crawl per hari terlalu berat untuk Selenium. Jadwalkan pull OneBox tiga kali, ukur durasi dan rate limit sebelum menaikkan concurrency.
- Semua SiteId jatuh pada menit sama. Randomize per SiteId dan batasi concurrency.
- Run melewati window. Pakai lock, timeout, status running, dan no-overlap policy.
- Restart menghasilkan jadwal baru. Persist occurrence dengan unique constraint.
- Clock skew. Pakai timezone eksplisit, NTP, simpan UTC dan tampilkan timezone site.
- Scheduler OneBox dan Crawler sama-sama aktif. Tetapkan satu owner scheduler.
- Histori hanya stdout. Simpan occurrence atau run history durable di OneBox; fetch_logs tetap untuk diagnosis source.

## 13. Rollout dan rollback

1. Deploy logic dengan schedule disabled.
2. Generate occurrence untuk satu SiteId dev.
3. Jalankan satu manual dan satu scheduled window.
4. Validasi delta, dedup, log, dan histori.
5. Enable bertahap per SiteId.
6. Rollback dengan disable schedule flag; jangan menghapus checkpoint atau histori.

Jika jadwal hari berjalan salah, tandai occurrence skipped dan buat manual run dengan approval. Jangan mengedit planned_at historis.

## 14. Temuan implementasi saat ini

- [verified] Crawler System memiliki fetch_logs dengan started_at, finished_at, status, dan counters per lokasi.
- [verified] Crawler System memiliki fetch API synchronous/blocking dan belum memiliki worker/scheduler durable.
- [verified] POST /api/fetch-jobs/all-active memproses lokasi aktif secara sequential.
- [verified] RI-08 sebelumnya hanya menyebut scheduler existing, Redis cursor, dan delta; belum memiliki schedule occurrence atau history contract.
- [verified] OneBox plan menyebut scheduler existing dan VoiceOfCustomerSystemTask; implementasi final harus diverifikasi di repo OneBox atau WSL deployment target.
- [decision] Scheduler owner untuk integrasi pull adalah OneBox. Scheduler source-ingestion Crawler, jika dibutuhkan nanti, adalah fitur terpisah dengan ownership dan idempotency key berbeda.

## 15. Breakdown estimasi (5 MD)

- 0.75 MD audit scheduler existing dan keputusan owner/window/timezone.
- 1.25 MD persistence occurrence, unique constraint, lock, dan next-run calculation.
- 1 MD integrasi delta task, retry, no-overlap, dan manual trigger.
- 1 MD histori endpoint/UI dan counters per run.
- 0.75 MD test restart/concurrency/failure/timezone, evidence, dan self-review.
