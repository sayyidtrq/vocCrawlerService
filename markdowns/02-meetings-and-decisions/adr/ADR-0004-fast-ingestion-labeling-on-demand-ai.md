# ADR-0004 - Fast Review Ingestion, OneBox Labeling, dan On-Demand AI Analysis

- **Status:** Accepted untuk implementasi
- **Tanggal:** 2026-07-31
- **Pengambil keputusan:** Sayyid
- **Terkait:** ADR-0001, ADR-0002, ADR-0003, `LABELING_rule-first-strategy.md`

## Context

Proof Dev membuktikan crawl real, persistence, dedup, dan delta review berjalan. Kendala
berikutnya adalah latency AI: local LLM memproses review secara serial dan estimasi awal
untuk 50 review masih 30-90 menit. Jika review baru hanya dikirim ke OneBox setelah AI
selesai, pengguna menunggu terlalu lama sebelum dapat melihat dan mengelola review.

Menyelesaikan AI juga menggerakkan watermark review. Tanpa membedakan discovery dengan
enrichment, review historis dapat terlihat seperti review baru dan berisiko dibuat ulang
sebagai Ticket.

OneBox sudah mempunyai program labeling yang dapat dipakai untuk klasifikasi sentiment
`positive`, `negative`, dan `neutral`. Lokasi implementasi persisnya harus ditemukan dan
diverifikasi oleh agent Claude pada codebase OneBox. Keputusan ini tidak mengizinkan
pembuatan labeling engine baru sebelum discovery tersebut selesai.

## Decision

### 1. Crawl tidak menunggu AI

Alur utama menjadi:

```text
Google Maps
  -> Crawler scrape + normalize + dedup
  -> review disimpan di DB Crawler
  -> OneBox menarik raw review melalui delta
  -> OneBox menyimpan review/Ticket
  -> labeling sentiment native OneBox dijalankan
  -> review langsung terlihat dan dapat dikelola
```

AI analysis tidak lagi menjadi bagian wajib dari proses crawl atau syarat agar review
masuk ke OneBox.

### 2. Labeling dan AI analysis adalah dua kemampuan berbeda

| Kemampuan | Pemilik | Waktu eksekusi | Output utama |
|---|---|---|---|
| Labeling sentiment | OneBox | Otomatis setelah review masuk | `positive`, `negative`, `neutral` |
| AI analysis | OneBox mengendalikan, Crawler mengeksekusi | Atas aksi pengguna, single atau bulk | summary, recommended action, urgency, issue category, dan metadata AI |

Program labeling existing OneBox menjadi sumber implementasi. Claude harus membuktikan
class/service, entry point, field output, dan apakah labeling berjalan otomatis saat
Ticket dibuat atau perlu dipanggil eksplisit.

### 3. AI analysis bersifat on-demand dan asynchronous

Pengguna dapat:

- memilih satu review lalu menjalankan AI analysis;
- memilih beberapa review lalu menjalankan bulk AI analysis;
- melihat status `pending`, `processing`, `completed`, `partial`, atau `failed`;
- mencoba ulang hanya review yang gagal.

Request UI tidak boleh menunggu LLM selesai. OneBox mengirim job, menerima `202` dan
`analysis_batch_id`, lalu polling status atau menerima hasil melalui mekanisme sync.

### 4. Discovery dan enrichment dipisahkan

Review memiliki dua lifecycle terpisah:

```text
Discovery:  discovered -> ingested_to_onebox -> manageable
Analysis:   not_requested -> pending -> processing -> completed/failed
```

Hasil AI adalah enrichment terhadap review/Ticket yang sudah ada. Hasil AI tidak boleh
membuat Ticket baru. Identity wajib menggunakan tenant + location + `review_hash` atau
remote review ID yang stabil.

### 5. Review historis dikendalikan dengan ingestion eligibility

Minimal metadata yang harus tersedia:

- `source_review_time`: waktu review pada platform sumber;
- `first_seen_at`: pertama kali ditemukan Crawler;
- `analysis_completed_at`: waktu enrichment selesai;
- `ingestion_mode`: `live` atau `backfill`;
- `eligible_for_ticket`: apakah review boleh menjadi Ticket operasional;
- `analysis_status`: status lifecycle AI.

Setiap lokasi memiliki `activation_at` dan kebijakan lookback. Default usulan:

- review sejak `activation_at`, atau masih dalam lookback yang dikonfigurasi, masuk mode
  `live` dan dapat menjadi Ticket;
- review lebih lama masuk mode `backfill`, tersedia untuk histori/dashboard, tetapi tidak
  otomatis menjadi Ticket operasional;
- `analysis_completed_at` tidak pernah mengubah review backfill menjadi review live.

Nilai lookback final adalah parameter OneBox dan harus dapat berbeda per tenant/site.

## Ownership

| Area | Crawler System | OneBox |
|---|---|---|
| Scrape, normalize, dedup | Owner | - |
| Raw review storage | Owner | Consumer copy |
| Discovery delta | Provider | Consumer/checkpoint |
| Sentiment labeling | - | Owner, reuse program existing |
| Pemilihan single/bulk | - | Owner/UI |
| AI job execution | Owner | Trigger, policy, entitlement |
| Token metering dan konfigurasi | Melaporkan usage | Owner |
| Ticket lifecycle | - | Owner |
| Backfill/live policy | Menyediakan metadata | Menentukan dan menegakkan eligibility |

## Consequences

### Positif

- Review masuk dan dapat dikelola tanpa menunggu AI.
- AI lambat tidak memblokir crawling maupun ingestion.
- Label sentiment murah dan cepat karena memakai kemampuan existing OneBox.
- Single/bulk analysis sesuai keputusan pengguna dan pemakaian token lebih terkendali.
- Review historis tidak berubah menjadi Ticket baru hanya karena analysis selesai.

### Negatif

- Diperlukan queue/status untuk AI analysis.
- OneBox harus mendukung create raw lalu update enrichment secara idempotent.
- Terdapat dua checkpoint atau event semantics: discovery dan enrichment.
- UI harus menangani data analysis yang belum tersedia.

## Guardrails

- Jangan memanggil AI otomatis dari worker crawl.
- Jangan menyimpan service token Crawler di browser.
- Jangan membuat labeling sentiment baru sebelum Claude menyelesaikan discovery OneBox.
- Jangan memakai `analysis_completed_at` sebagai waktu discovery review.
- Jangan membuat Ticket baru ketika menerima enrichment untuk `review_hash` yang sama.
- Jangan menandai seluruh batch gagal hanya karena sebagian review gagal dianalisis.