# Rencana: Membuktikan Key Process End-to-End di Dev

> Dibuat 2026-07-28 · Otoritas: [ADR-0001](../../02-meetings-and-decisions/adr/ADR-0001-ownership-inversion.md) · [ADR-0002](../../02-meetings-and-decisions/adr/ADR-0002-ai-execution-split.md) · [ADR-0003](../../02-meetings-and-decisions/adr/ADR-0003-crawl-execution-pull-queue.md)
> Tandai setiap klaim **[verified] / [assumption] / [blocked]**.

**Sasaran:** menunjukkan satu alur utuh yang bisa didemokan —
**tambah lokasi di OneBox → review Google ter-crawl → dianalisa AI → muncul sebagai tiket yang bisa ditindaklanjuti.**

Ini bukan membangun fitur baru. Sebagian besar kodenya sudah ada; yang belum ada adalah **bukti bahwa rantainya nyambung**.

## 0. Update proof Dev - 31 Juli 2026

Status ini menggantikan klaim lama yang masih menyebut crawl real sebagai blocker:

- X1 lulus dengan limit: target 50, fetched/inserted 40, failed 0; scraper berhenti
  setelah 18 scroll tanpa kartu baru.
- X2 lulus: company `3`, lokasi Crawler `8`, lokasi OneBox `656`, place mapping benar,
  dan seluruh 40 review memiliki hash unik.
- Idempotency lulus dan rerun dedup menghasilkan `inserted=0`, `duplicate=40`.
- X4 raw lulus: delta mengembalikan 40 review, final page, dan checkpoint cursor.
- X5 lulus di Dev: enqueue non-blocking dan worker durable berjalan.
- X3 parsial: `gemma3:1b` menghasilkan satu analysis valid dengan 839 token; batch penuh
  belum selesai karena pemanggilan LLM masih serial.

Jalur kritis terbaru adalah **X3 analysis -> X4 delta enriched -> ingestion dan Ticket
OneBox**. Risiko Selenium sudah ditutup melalui profile Google persisten dan Chromium
headed di Xvfb.

Estimasi sementara analysis 50 review adalah **30-90 menit**, dengan budget aman
**maksimal 120 menit**. Dasarnya 30-90 detik per review secara serial ditambah cold start,
validasi, penyimpanan DB, dan retry. Angka ini provisional dan harus diganti dengan
throughput aktual setelah batch selesai.

---

## 1. Peta status tiap tahap

| # | Tahap | Status | Pemilik |
|---|---|---|---|
| 1 | Tambah lokasi di OneBox (tersimpan ke DB) | ✅ **[verified]** 28 Jul | OneBox |
| 2 | Crawler menarik worklist dari OneBox | ✅ **[verified]** `fetched:1, upserted:1` | VoC |
| 3 | **Crawl review Google untuk target itu** | **[verified-dev, partial target]** 40/50 fetched, 0 gagal | **VoC** |
| 4 | Review tersimpan + dianalisa AI di VoC | **[in-progress-dev]** persistence/dedup lulus; batch AI serial masih berjalan | VoC |
| 5 | OneBox menarik review (delta) dari VoC | **[verified-dev, analysis pending]** 40 review raw + checkpoint; ulangi setelah X3 | OneBox |
| 6 | Review → Ticket + kategori + prioritas | ⚠️ kode ada **[verified di lokal]**, belum di dev | OneBox |
| 7 | Tampil di Dashboard / Reviews | ✅ **[verified]** | OneBox |

**Jalur kritis: tahap 3 → 5 → 6.** Tahap 3 adalah risiko terbesar dan harus diuji lebih dulu.

---

## 2. Analisis blocker

### B1 — Selenium & login Google di container *(KRITIS, tahap 3)*
Catatan lama: *"Selenium mode tidak jalan di container (butuh manual Google login GUI)"* **[assumption — perlu diverifikasi ulang]**.

Kalau masih berlaku, seluruh rencana otomatisasi (antrean M2, penjadwalan M4) berdiri di atas sesuatu yang belum tentu bisa dieksekusi tanpa manusia.

**Karena itu ini diuji PALING AWAL.** Gagal sekarang murah; gagal setelah scheduler jadi, mahal.

Kemungkinan hasil & konsekuensinya:
- **Bisa crawl tanpa login** → lanjut sesuai rencana.
- **Butuh sesi login yang bisa disimpan** → simpan profil browser/cookie, perpanjang masa berlaku, jadikan bagian runbook.
- **Wajib GUI tiap kali** → arsitektur berubah: crawl tidak bisa sepenuhnya otomatis. Perlu dibawa ke Pak Agung, dan ADR-0003 (penjadwalan otomatis) harus ditinjau.

### B2 — Connection VoC di dev menunjuk ke alamat yang salah *(tahap 5)*
Baris `977` (Hermina depok) mewarisi kredensial dari koneksi lama `959`, yang `Options`-nya berisi `{"Host":"space.datakelola.com","Url":"https://sp..."}` **[verified dari phpMyAdmin]**.

Itu **bukan** alamat API VoC. Tanpa `Url`, `api_mode`, dan `service_token` yang benar, OneBox tidak akan bisa menarik review — sekalipun crawling berhasil.

### B3 — Jaringan dev ⇄ crawler *(tahap 5)*
OneBox **lokal tidak bisa** menjangkau server crawler (`10.13.13.90` tertutup) **[verified]**. Jadi pengujian tahap 5–6 **harus dilakukan di dev**, bukan di laptop.

Dev (`10.13.13.42`) dan crawler (`10.13.13.90`) sama-sama di WireGuard — menurut Infra semestinya tersambung **[assumption — belum diuji dua arah]**.

### B4 — Letak eksekusi AI
ADR-0002: **parameter & kuota di OneBox, eksekusi AI di VoC**. Yang didemokan di OneBox adalah **hasil** analisa (sentimen, urgensi, kategori, ringkasan), bukan pemanggilan LLM-nya.

Perlu disepakati sebelum demo supaya narasinya tidak salah.

### B5 — Kuota/Benefit belum aktif
Kode `VOC_*` belum diregistrasi. Untuk demo tidak menghalangi, tapi artinya **pemakaian token AI belum dibatasi**.

---

## 3. Alur kerja & deployment

Pertanyaan yang sering muncul: *"apakah setiap uji coba harus push ke `feature/voc`?"* — **tergantung tahapnya.**

| Tahap diuji | Perlu deploy OneBox? | Alasan |
|---|---|---|
| 3 — crawl Google | **Tidak** | murni di server crawler, OneBox tidak terlibat |
| 4 — simpan + analisa di VoC | **Tidak** | idem |
| 2, 5, 6 — melibatkan OneBox | **Ya, di dev** | crawler & OneBox harus saling menjangkau; laptop tidak masuk jaringan itu |

**Alur perubahan kode OneBox** (aturan Pak Agung, 28 Jul):
```
koding di feature/DNGO19-3346  →  push  →  merge ke feature/voc  →  Jenkins auto-build + auto-migration  →  dev.onebox.co.id/feature/voc/
```
Tidak ada koding langsung di `feature/voc` — branch itu hanya untuk merge. PR mengikuti kebiasaan tim; yang wajib adalah **koding di branch DNGO**, karena itu yang naik ke release.

---

## 4. Pembagian kerja dua agen

### Agen VoC (Codex) — **jalan duluan, memblokir yang lain**

| ID | Tugas | Selesai bila |
|---|---|---|
| **X1** | **Selesai** - crawl target Hermina Depok di server | 40 review real tersimpan; login Google satu kali melalui profile persisten |
| X2 | **Selesai** - verifikasi persistence dan dedup | Mapping lokasi benar; 40 hash unik; rerun 40 duplikat dan 0 insert |
| X3 | **Berjalan** - selesaikan analysis dan ukur throughput aktual | Satu review sukses/839 token; tunggu aggregate seluruh review |
| X4 | **Parsial** - delta raw lulus, ulangi setelah X3 | 40 review dan checkpoint terbukti; field analysis belum lengkap |
| X5 | **Selesai** - enqueue non-blocking dari service API | API, token scope, queue, dan worker terbukti di Dev |

> Gerbang aktif sekarang adalah **X3**. Jangan ingest final ke OneBox sebelum X4 menunjukkan field analysis lengkap atau kegagalan per review sudah tercatat.

### Agen OneBox (Claude)

| ID | Tugas | Selesai bila |
|---|---|---|
| **C1** | **Perbaiki Connection VoC di dev** — `Url`, `api_mode`, `service_token`, `company_id` (blocker B2). Kredensial **tidak lewat git** | `whoami` dari dev mengembalikan company yang benar |
| C2 | Jalankan ingest di dev: `voice_of_customer_system receive <connId>` | Review VoC masuk jadi Message/Ticket |
| C3 | Verifikasi `Options.location_map` memetakan lokasi VoC → `Location` OneBox | `Ticket.LocationId` terisi, bukan "Unknown" |
| C4 | Verifikasi hasil analisa mendarat di Ticket (sentimen, kategori, prioritas) | Dashboard menampilkan angka nyata, bukan 0/Netral semua |
| C5 | Halaman **Fetch Jobs** memicu crawl lewat X5 + menampilkan riwayat | Demo bisa dijalankan dari UI, bukan terminal |

### Urutan & titik temu
```
X1 (gerbang) ─┬─> X2 ─> X3 ─> X4 ─┐
              │                    ├─> C2 ─> C3 ─> C4 ─> demo
C1 (paralel) ─┴────────────────────┘
C5 menyusul (memoles demo)
```
C1 bisa dikerjakan **paralel** dengan X1 — tidak saling menunggu.

---

## 5. Skenario demo & kriteria sukses

**Yang ditunjukkan (dari UI, bukan terminal):**
1. Tambah cabang di OneBox → hanya butuh Nama + Google Place ID
2. Crawler menariknya sendiri (tunjukkan `refresh_worklist`)
3. Crawl berjalan → review Google masuk
4. Review muncul di **Reviews** lengkap dengan sentimen & urgensi
5. Review negatif menjadi **Tiket** yang bisa ditugaskan
6. Dashboard memperlihatkan cabang mana yang berisiko

**Kriteria sukses (harus terukur, bukan "kelihatan jalan"):**
- Minimal 1 cabang baru menempuh seluruh rantai tanpa langkah manual di sisi crawler
- Review tidak dobel saat proses diulang (idempotent)
- `Ticket.LocationId` terisi benar — bukan "Unknown"
- Minimal 1 review negatif menjadi tiket berstatus terbuka

**Yang jujur disebut sebagai belum jalan:** penjadwalan otomatis 3 window, antrean crawl, kuota AI, review kompetitor.

---

## 6. Rencana cadangan bila X1 gagal

Kalau Selenium tidak bisa jalan tanpa GUI:
1. **Jangan** memaksakan penjadwalan otomatis — itu menjanjikan sesuatu yang tidak bisa ditepati.
2. Demokan rantainya memakai review yang **sudah ada** di cache VoC (tahap 4–6 tetap nyata dan bernilai).
3. Angkat ke Pak Agung sebagai keputusan: crawl semi-otomatis dengan sesi yang diperbarui berkala, atau cari sumber data alternatif.
4. ADR-0003 bagian penjadwalan ditinjau ulang — bukan dibatalkan, tapi diberi prasyarat.

---

## 7. Yang dikerjakan lebih dulu

1. **X1** — uji crawl di server *(Codex, hari ini)*
2. **C1** — benahi Connection VoC di dev *(OneBox, paralel)*
3. Baru lanjut sesuai bagan di §4
