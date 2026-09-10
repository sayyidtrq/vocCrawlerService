# ADR-0003 — Model Eksekusi Crawl: Pull Worklist + Antrean Job Berjadwal

- **Status:** Accepted
- **Tanggal:** 2026-07-23
- **Pengambil keputusan:** Sayyid (dev) — ⚠️ belum diratifikasi Pak Agung
- **Terkait / meng-amandemen:**
  - [ADR-0001](ADR-0001-ownership-inversion.md) — **mekanisme** provisioning diganti (push sinkron → pull worklist). Keputusan inti "OneBox = System of Record" **tetap berlaku dan diperkuat**.
  - [ADR-0002](ADR-0002-ai-execution-split.md) — analisa AI menjadi tahap konsumen event review baru (tidak berubah, diperjelas penempatannya).
  - `implementation-plan-onebox/RI-08_scheduler-delta.md` — **di-amandemen**: scheduler owner tetap OneBox, tetapi VoC kini punya antrean crawl durable (mengisi gap yang RI-08 tandai). Bukan scheduler kedua.

---

## Context

[ADR-0001](ADR-0001-ownership-inversion.md) menetapkan OneBox sebagai System of Record dan VoC sebagai crawler headless, dengan mekanisme **auto-provisioning push**: saat user menyimpan lokasi, `VocController` memanggil `POST /api/locations` VoC **secara sinkron di jalur simpan**. Mekanisme ini sudah diimplementasikan (T2–T4).

Setelah dipakai, tiga masalah muncul — dua struktural, satu dari skenario bisnis nyata:

1. **Kerja terjadi di jalur yang dilihat user.** Menyimpan lokasi menunggu panggilan lintas-service ke VoC. Kalau VoC lambat/mati, simpan ikut lambat/gagal. Seluruh kerumitan T3/T4 (status `provisioning`, tombol retry, state `failed`, "batalkan delete kalau VoC mati biar tak ada crawl target yatim", hack `CNS3` untuk kompetitor) **ada semata-mata karena push + mirror**.

2. **Dual-write.** Master data hidup di dua tempat dan disinkronkan sinkron per operasi. Divergensi mungkin; rekonsiliasi manual (kasus Bekasi di ADR-0001 §Temuan data).

3. **Skenario bisnis:** review datang tiap hari; crawl diinginkan tiga window (pagi sebelum masuk, siang saat makan siang, malam saat tidur); sistem **tidak boleh terasa lambat** saat user membuka app. RI-08 sudah mendesain penjadwalan tiga slot ini, tetapi menandai gap: *fetch VoC synchronous/blocking, "cocok untuk manual/admin, bukan request scheduler yang menunggu Selenium lama"*, dan *"VoC belum memiliki worker/scheduler durable"*.

Referensi praktik industri (Apify, Firecrawl): pisahkan "kapan mau data" dari "kapan crawl jalan" — API cuma melempar job ke antrean, worker terpisah mengeksekusi; skala diukur dari kedalaman antrean, bukan volume request. Crawl inkremental (dedup by key, resume dari cursor). Retry sadar-jenis-error + rate limit adaptif.

---

## Decision

Prinsip tunggal: **semua kerja crawl & analisa terjadi di background berjadwal; user hanya membaca hasil yang sudah jadi (pre-computed).** "Lambat" datang dari kerja di jalur baca — hilangkan jalur itu.

Tiga keputusan konkret:

### D1 — Provisioning: PUSH sinkron → PULL worklist

OneBox **tidak lagi** memanggil VoC saat menyimpan master data. Sebaliknya, VoC **menarik daftar target** dari OneBox.

- OneBox menyediakan endpoint **worklist** (baca, service-token): daftar crawl target aktif per tenant + parameter.
- Menyimpan lokasi/kompetitor di OneBox = commit lokal, **selesai instan**. Target itu otomatis muncul di worklist berikutnya.
- Tabel `Location`/`Competitor` di VoC tetap ada sebagai **cache worklist** (bukan master; konsisten ADR-0001 "crawl target registry"). Di-refresh dari pull, bukan dari push.

### D2 — Eksekusi crawl: fetch blocking → antrean job durable + worker

VoC mengeksekusi crawl lewat **antrean job durable**, bukan panggilan sinkron yang menunggu Selenium.

- Trigger dari OneBox bersifat **non-blocking**: "enqueue crawl untuk target-target ini" → balas cepat dengan batch id. Tidak ada penunggu Selenium di jalur request.
- Worker VoC menguras antrean: klaim job atomik, rate limit per target, retry sadar-jenis-error + backoff, backpressure saat CPU/RAM tinggi.
- **Mengisi gap RI-08** tanpa memindahkan owner scheduler: OneBox tetap yang menentukan **kapan** (occurrence tiga slot RI-08); VoC yang menentukan **bagaimana** crawl dieksekusi.

### D3 — Crawl inkremental (cursor) + pipeline berlapis

- **Cursor crawl per target di VoC**: scrape terbaru-dulu, **berhenti begitu menyentuh review yang sudah dimiliki**. Satu window harian menarik segelintir review baru, bukan seluruh riwayat. (Beda dari checkpoint ingestion OneBox di RI-08 §5.2 — lihat §"Dua cursor" di bawah.)
- **Analisa AI = tahap konsumen event review baru** (ADR-0002), di antrean terpisah, **di luar jalur baca**. Dashboard/insights membaca hasil yang sudah tersimpan.

### Bagan pipeline

```
  OneBox (Control Plane — "APA & KAPAN")            VoC (Worker — "EKSEKUSI")
  ┌────────────────────────────┐
  │ Master data lokasi/komp.   │   1. pull worklist   ┌─────────────────────────┐
  │ + jadwal window (RI-08)    │◄─────────────────────│ cache worklist + cursor │
  │ + param AI (ADR-0002)      │                      └───────────┬─────────────┘
  └─────┬──────────────────────┘   2. kick (non-block)            │ window slot (RI-08)
        │ user CUMA baca          ─────────────────────►          ▼
        │ (pre-computed)                              ┌─────────────────────────┐
        │                          3. review delta    │  CRAWL JOB QUEUE        │
        ▼                          ◄───── pull ────────│  pending→claimed→done   │
  ┌────────────────────────────┐                      │  attempts, next_retry,  │
  │ Ticket + Dashboard +       │                      │  locked_by + worker(s)  │
  │ Insight (hasil analisa)    │                      └─────────────────────────┘
  └─────┬──────────────────────┘
        │ event: review baru
        ▼
  ┌────────────────────────────┐
  │ ANALYSIS QUEUE (AI, ADR-0002) di luar jalur baca  │
  └────────────────────────────┘
```

Tiga tahap (crawl → simpan → analisa) dipisah antrean. User hanya menyentuh kotak kiri-bawah.

---

## Kontrak API (arah panggilan)

Setiap sisi **membaca data otoritatif** milik sisi lain. Semua memakai service-token (`HTTPBearer`), tenant-scoped.

| # | Arah | Endpoint (usulan) | Fungsi |
|---|---|---|---|
| 1 | VoC → OneBox | `GET /api/integration/v1/worklist` | Daftar crawl target aktif per tenant: `company_id`, `kind` (location/competitor), `external_place_id`, `onebox_location_id`, `active`, hint cursor, param AI (`ai_enabled`, `model`, `prompt_version`, `threshold`). **Menggantikan** push `POST /api/locations`. |
| 2 | OneBox → VoC | `POST /api/integration/v1/crawl-jobs` | **Non-blocking.** Enqueue crawl untuk target di satu slot; balas `batch_id` seketika. Menggantikan pemanggilan fetch sinkron. |
| 3 | OneBox → VoC | `GET /api/integration/v1/reviews?updated_since=<cursor>` | Pull delta review hasil crawl (sudah ada; RI-08 tetap berlaku). |
| 4 | OneBox → VoC | `GET /api/integration/v1/crawl-jobs/<batch_id>` | Status batch untuk UI histori (opsional; melengkapi occurrence RI-08). |

> Worklist pull (#1) dan review pull (#3) bukan redundansi: #1 mengalirkan **konfigurasi turun** ke worker, #3 mengalirkan **hasil naik** ke SoR. Masing-masing membaca data otoritatif sisi lain.

---

## Model data

### Antrean crawl job (baru, di VoC)

Untuk skala pilot (puluhan–ratusan target), pakai **tabel Postgres + `SELECT ... FOR UPDATE SKIP LOCKED`**, bukan Redis/Celery. Naik ke broker khusus **hanya bila** kedalaman antrean terbukti jadi masalah. (Sejalan RI-08 §10: jangan tambah Celery/Redis untuk sekadar tiga window.)

Minimum field: `id`, `company_id`, `kind`, `target_key` (place id), `slot`/`batch_id`, `status` (pending/claimed/done/failed), `attempts`, `next_retry_at`, `locked_by`, `locked_at`, `last_error`, `finished_at`.

### Dua cursor yang berbeda (jangan dicampur)

| Cursor | Lokasi | Arti | Sumber |
|---|---|---|---|
| **Crawl cursor** | VoC, per target | Sampai mana Selenium sudah scrape (inkremental) | Baru (ADR-0003 D3) |
| **Ingestion checkpoint** | OneBox, per SiteId | Sampai mana OneBox sudah tarik review jadi Ticket | RI-08 §5.2 (tetap) |

### Idempotency

Upsert review keyed by id stabil Google, atau hash `author+tanggal+teks` bila id tak tersedia *[assumption — perlu cek apa scraper menangkap id stabil]*. Dedup di storage; retry job tak pernah menggandakan Ticket.

---

## Windowed scheduling (hubungan dengan RI-08)

**Tidak ada scheduler kedua.** RI-08 tetap otoritas "kapan": occurrence tiga slot (pagi 05–07, siang 11–13, malam 21–23), planned_at random ter-persist, timezone site, unique `(site_id, local_date, slot)`, no-overlap lock, retry policy. Yang berubah hanya bentuk trigger-nya:

- **Sebelum:** occurrence → panggil fetch VoC **sinkron** (menunggu Selenium) → pull review.
- **Sesudah:** occurrence → **kick non-blocking** (#2, enqueue) → worker VoC crawl async → OneBox pull delta review (#3) saat batch selesai / slot berikut.

Ini persis menyelesaikan kekhawatiran RI-08 §3 & §12 ("tiga crawl per hari terlalu berat untuk Selenium bila blocking"). Beban Selenium kini dikendalikan concurrency worker + rate limit, bukan oleh satu request panjang.

---

## Consequences

### Positif
1. **Simpan instan.** Jalur baca/tulis user tak lagi menyentuh VoC. Data pagi selesai sebelum user masuk.
2. **Kerumitan T3/T4 luruh:** tak perlu status provisioning sinkron, tombol retry provisioning, two-phase delete "yatim", atau hack `CNS3`.
3. **Sumber kebenaran tunggal** untuk master data; tak ada dual-write.
4. **Beban crawl terkendali:** concurrency + rate limit + backoff, bukan request blocking.
5. **Freshness nyata:** badge jadi "Terakhir di-crawl HH:MM", bukan "record ter-mirror".

### Negatif / biaya
1. **Rework kode yang baru ditulis.** Provisioning sinkron T3/T4 (`provisionLocation`/`provisionCompetitor`, kolom `provisioning`, tombol retry) menjadi usang — dihapus/diganti. Biaya sunk, tapi lebih murah dikoreksi sekarang sebelum T5/T6 menumpuk.
2. **Dua endpoint baru sisi VoC** (worklist #1, crawl-jobs #2) + tabel antrean + worker. Dikerjakan tim VoC (dev sama).
3. **VoC bergantung OneBox untuk tahu target.** Mitigasi: crawl dari **cache worklist terakhir** bila OneBox tak terjangkau — otonomi crawler tetap terjaga.
4. **Eventual consistency:** target baru muncul di crawl pada window/pull berikutnya, bukan seketika. Dapat diterima; UI menampilkan "menunggu window berikutnya".

### Risiko
- Cache worklist basi bila OneBox lama mati. **Mitigasi:** TTL + tampilkan umur cache; worklist pull sebelum tiap window.
- Antrean menumpuk bila worker kurang. **Mitigasi:** monitor kedalaman antrean; backpressure; alarm.
- Delete master di OneBox tapi target masih di cache VoC → crawl target yatim (risiko lama, bentuk baru). **Mitigasi:** worklist bersifat otoritatif — target yang hilang dari worklist ditandai non-aktif oleh VoC pada pull berikut (rekonsiliasi, bukan two-phase delete sinkron).

---

## Alternatif yang ditolak

1. **Push async (outbox) — tetap mirror.** OneBox simpan lokal, worker background push ke VoC. Menyembuhkan *latency* saja; **dual-write tetap ada**. Ditolak karena kita memiliki VoC, jadi tak ada alasan berhenti di setengah jalan.
2. **VoC punya scheduler window sendiri.** Melanggar RI-08 (satu owner scheduler), bikin waktu hasil sulit dijelaskan & checkpoint ganda.
3. **VoC stateless murni.** Sudah ditolak di ADR-0001 (re-analisa boros token). ADR-0003 **menambah** state VoC (cache + cursor + antrean), bukan menghilangkan — konsisten.
4. **Redis/Celery dari awal.** Over-engineering untuk skala pilot. Postgres `SKIP LOCKED` dulu (RI-08 §10).

---

## Yang berubah di kode

| # | Perubahan | Sisi | Status |
|---|---|---|---|
| 1 | Hapus provisioning sinkron di jalur simpan (`provisionLocation`/`provisionCompetitor`); simpan jadi commit lokal murni | OneBox | usang → hapus |
| 2 | Endpoint worklist `GET /api/integration/v1/worklist` | OneBox | baru |
| 3 | Endpoint enqueue `POST /api/integration/v1/crawl-jobs` (non-blocking) | VoC | baru |
| 4 | Tabel antrean crawl job + worker (`SKIP LOCKED`, retry/backoff, rate limit, backpressure) | VoC | baru |
| 5 | Crawl cursor inkremental per target | VoC | baru |
| 6 | Trigger occurrence RI-08: fetch sinkron → kick non-blocking + pull delta | OneBox | ubah |
| 7 | Cache worklist menggantikan tabel master VoC (di-refresh dari pull) | VoC | ubah |
| 8 | UI: badge "provisioned" → "Terakhir di-crawl"; buang tombol retry provisioning | OneBox | ubah |

**Di-supersede oleh ADR ini:**
- ADR-0001 §"Mekanisme: auto-provisioning" (push sinkron) dan baris "Yang harus berubah di kode" #2.
- ADR-0001 §Risiko two-phase delete → diganti rekonsiliasi via worklist.
- RI-08 §3/§12 bentuk trigger blocking → kick non-blocking (occurrence & owner scheduler tetap).

---

## Handoff / API gap

1. **Sepakati skema worklist** (#1): field, filter tenant, format cursor hint, param AI (selaras ADR-0002).
2. **Sepakati kontrak enqueue** (#2): payload target, `batch_id`, kode status.
3. VoC: bangun tabel antrean + worker; putuskan kunci dedup review (id vs hash).
4. OneBox: ganti trigger occurrence RI-08 dari fetch sinkron ke kick + delta pull.

---

## Tindak lanjut
1. Bawa ADR-0003 ke Pak Agung bersama ADR-0001/0002 (satu paket ratifikasi).
2. Tandai bagian ADR-0001 & RI-08 yang di-amandemen dengan pointer ke ADR ini.
3. Eksekusi bertahap: (a) worklist pull + hapus push, (b) antrean + worker VoC, (c) cursor inkremental, (d) retry/backoff/observability, (e) analysis queue (ADR-0002/T6).
