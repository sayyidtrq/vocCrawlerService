# Key Process VoC di OneBox — Peta Implementasi untuk Demo

> Disusun 2026-07-21 dari pembacaan langsung codebase VoC + OneBox dan probe ke
> API staging (`192.168.1.3:8000`). Semua angka di dokumen ini hasil pengukuran,
> bukan perkiraan.
> **Koreksi status 31 Juli 2026:** bagian risiko Selenium dan LLM di bawah adalah snapshot
> historis 21 Juli. Proof Dev terbaru membuktikan Chromium headed melalui Xvfb dengan
> profile Google persisten berhasil mengambil 40 review real tanpa kegagalan, idempotency
> dan dedup lulus, serta delta API mengembalikan 40 review. Ollama sekarang memakai
> `gemma3:1b`; satu analysis valid menggunakan 839 token, tetapi batch penuh masih berjalan
> lambat karena request diproses serial. Acuan status aktif adalah
> `VOC_CRAWL_PROOF_RUNBOOK.md` dan `PLAN_KEY_PROCESS_DEMO.md`.

## 1. Ringkasan status

Lima key process yang diminta, apa adanya hari ini:

| # | Key process | Status di OneBox | Catatan |
|---|---|---|---|
| 1 | Ambil review | **jalan** — tombol "Tarik Review Sekarang" | crawling Google Maps tetap milik VoC (lihat §2.1) |
| 2 | Menampilkan data review | **jalan** | 75 review real |
| 3 | Filter review | **jalan** — filter + paging server-side | |
| 4 | AI analysis | **hasilnya tampil, prosesnya tidak** | LLM salah konfigurasi; kategori tidak diskriminatif |
| 5 | Kelola review | **jalan** — tombol Kelola → ticket detail | perlu satu kali cek di browser |

Sync/pull (contract v1 service token, delta sync cursor, guard tenant) selesai dan
terverifikasi. Detail perubahan ada di §7.

## 2. Tiga temuan yang mengancam demo

Ini yang paling penting dibaca sebelum menyusun skenario.

### 2.1 Crawler selenium tidak layak dijalankan live

Riwayat `GET /api/fetch-logs` — **6 dari 8 run gagal**:

| # | Lokasi | Status | Error |
|---|---|---|---|
| 13 | HGA Depok | success | 50 fetched |
| 12 | HGA Depok | failed | `no such window: target window already closed` |
| 11 | Hermina Depok | success | 25 fetched |
| 10, 9, 8, 7, 6 | campur | failed | `Review container was not found` / browser crash |

Penyebabnya struktural, bukan kebetulan: crawler ini **scraper DOM Google Maps**
dengan `selenium_headless: false` — butuh sesi browser ber-GUI dan patuh pada
layout Google yang bisa berubah kapan saja.

> **Jangan jalankan crawling live di depan penonton.** Peluang gagalnya lebih besar
> daripada berhasil, dan gagalnya di menit pertama demo.

### 2.2 LLM analisis sedang mati

`LOCAL_LLM_BASE_URL=http://192.168.1.115:11434` (Ollama) — **tidak reachable** dari
mesin ini (`http=000`). Selama itu mati, `POST /api/analysis/*` akan gagal, jadi
analisis AI juga tidak bisa didemokan live.

Efek sampingnya sudah terlihat di data: 2 dari 75 review masih `analyzed=false`
(VoC id 88 & 109, dua-duanya rating 1 di HGA Depok).

### 2.3 Kategori AI tidak diskriminatif — ini yang paling merusak cerita

| Kategori | Jumlah |
|---|---|
| `doctor_service` (Pelayanan Dokter) | **73** |
| belum dianalisis | 2 |

Dari 18 kategori yang tersedia, AI memilih **satu** untuk semua review. Artinya
panel "Top Issue" di dashboard akan tampil sebagai satu batang tunggal — persis di
tempat yang seharusnya membuktikan nilai AI-nya.

Kabar baiknya, dimensi lain **sehat** dan layak ditonjolkan:

| Dimensi | Sebaran |
|---|---|
| Sentimen | positive 46 / negative 27 |
| Prioritas | TP1 46 / TP2 10 / TP3 17 |
| Rating | Hermina Depok 4.40 · HGA Depok 3.22 |

**Saran demo:** bangun narasi di sekitar sentimen, prioritas, dan rating per cabang.
Jangan tampilkan panel kategori sampai prompt-nya diperbaiki.

## 3. Peta teknis per proses

### 3.1 Ambil review

Dua hal berbeda yang sering tertukar:

| | Siapa | Bisa dipicu dari OneBox? |
|---|---|---|
| (a) crawling Google Maps → DB VoC | VoC (selenium) | **tidak** |
| (b) tarik dari VoC → Ticket OneBox | OneBox provider | ya, tapi baru lewat CLI |

Endpoint VoC untuk (a) — **semuanya `Depends(get_current_user)`, artinya JWT user,
bukan service token:**

| Endpoint | Fungsi |
|---|---|
| `POST /api/fetch-jobs` | crawl 1 lokasi |
| `POST /api/fetch-jobs/all-active` | crawl semua lokasi aktif |
| `POST /api/pipeline/location` | **fetch → analyze → export dalam satu panggilan** |
| `GET /api/fetch-logs` | riwayat crawling |

`POST /api/pipeline/location` adalah kandidat terbaik kalau nanti OneBox mau punya
tombol "jalankan pipeline" — satu panggilan, hasilnya `steps.fetch` + `steps.analysis`.

> **Blokade:** service token hanya diperiksa di `integration_reviews.py`. Router lain
> tidak mengenal `ServicePrincipal` sama sekali. Jadi OneBox **tidak bisa** memicu
> crawl/analisis tanpa penambahan di sisi VoC (lihat §6).

### 3.2 Menampilkan data review

Sudah jalan. `VocController::reviewsDataAction` membaca Ticket+Message+MessageContent
di-scope `SiteId` + `ProviderId='PVD97'`. Dashboard Volt memakai
`dashboardDataAction`. Keduanya menampilkan 75 review asli.

### 3.3 Filter review

Jalan, tapi **client-side**: `fetchReviews($siteId, 200)` menarik 200 baris terakhir,
lalu `reviews.volt` menyaring di browser (`#rv-q`, `#rv-floc`, `#rv-fsent`, `#rv-furg`).

Untuk 75 review sekarang aman. Begitu satu cabang saja menembus 200 review, filter
mulai berbohong — hasilnya terlihat benar padahal hanya menyaring potongan terakhir.

### 3.4 AI analysis

Hasil analisis **sudah** mengalir ke OneBox: `summary` → `Ticket.Description`,
`recommended_action` → `Ticket.Solution`, `urgency` → `PriorityId`, `issue_category`
→ `CategoryId`, `sentiment` → `Meta.ai_sentiment`, `rating` → `Ticket.Sentiment`.

Yang belum ada: **memicu** analisis. Tombol `#an-run` / `#an-rerun` di `analysis.volt`
saat ini hanya memunculkan `alert()` berisi perintah CLI.

### 3.5 Kelola review — peluang terbesar dengan biaya terkecil

Review VoC **sudah menjadi Ticket OneBox seutuhnya**:

```
Id 59220  StatusId TS2  PriorityId TP2  Responder NULL  AssigneeTextList NULL  DueDate NULL
```

Artinya seluruh mesin ticketing OneBox (`TicketController`: `showTicketDetail`,
`addTaskAssignTo`, `saveTicketUpdate`, `saveTicketMessage`) sudah berlaku untuk
review ini — cuma belum pernah ada yang membukanya, dan UI VoC belum menautkannya.

Sudah ada helper global siap pakai di `public/js/navigation.js:588`:

```js
openTabTicketDetail(Id, 'ticket-center', 'Case Detail', 'Ticket/showTicketDetail', 'POST')
```

`reviewsDataAction` sudah mengembalikan `id` = `Ticket.Id`. Jadi menautkan baris review
ke ticket detail praktis tinggal menambahkan tombol per baris.

**Ini yang mengubah demo dari "OneBox menampilkan review" menjadi "OneBox tempat
review ditindaklanjuti" — dan itulah pembeda OneBox dari FE VoC sendiri.**

## 4. Prioritas pekerjaan

| Prioritas | Pekerjaan | Kenapa | Risiko |
|---|---|---|---|
| **P0** | Tautkan baris review → ticket detail OneBox | menutup key process ke-5, biaya paling kecil, dampak cerita paling besar | rendah — reuse helper yang sudah ada |
| **P0** | Tombol "Tarik Review Sekarang" di UI VoC | key process ke-1 versi OneBox jadi bisa ditunjukkan live tanpa menyentuh selenium | rendah — jalur `receive` sudah terbukti |
| **P1** | Filter + paging server-side | filter sekarang bohong di atas 200 baris | sedang |
| **P1** | Sembunyikan/ganti panel kategori | mencegah "Top Issue" tampil sebagai satu batang | rendah |
| **P2** | Tombol pipeline (crawl+analyze) dari OneBox | butuh pekerjaan sisi VoC dulu (§6) | tinggi — tergantung pihak lain |
| **P2** | Riwayat crawling VoC di layar Fetch Jobs | butuh `/fetch-logs` via service token | sedang |

## 5. Skenario demo yang disarankan

Dibangun hanya dari jalur yang terbukti stabil:

1. **Konteks** — Media Monitoring → Voice of Customer. Tunjukkan ini hidup di dalam
   OneBox, bukan aplikasi terpisah.
2. **Tarik data (live)** — klik "Tarik Review Sekarang". Aman: sudah diuji, ~2 detik,
   dan delta sync membuat run kedua `fetched=0` (tidak ada duplikat).
3. **Bukti crawler** — tampilkan riwayat fetch VoC sebagai *bukti*, bukan dijalankan
   live. Jelaskan pembagian peran: crawler = VoC, tindak lanjut = OneBox.
4. **Lihat & saring** — Reviews: cari kata kunci, saring per cabang, per sentimen,
   per urgensi.
5. **Hasil AI** — buka satu review negatif: ringkasan, rekomendasi tindakan, prioritas
   TP3, rating. Tekankan bahwa ini otomatis, bukan diketik manusia.
6. **Kelola (penutup)** — dari review itu langsung buka ticket detail OneBox:
   assign ke PIC, balas, ubah status. **Inilah yang tidak bisa dilakukan VoC sendirian.**
7. **Dashboard** — tutup dengan sebaran sentimen, prioritas, dan perbandingan rating
   antar cabang (Hermina 4.40 vs HGA 3.22 — kontras yang bagus untuk ditutup).

Yang **tidak** dijalankan live: crawling selenium (§2.1) dan analisis AI (§2.2).

## 6. Yang perlu diminta ke agent VoC (kalau mau P2)

Supaya OneBox bisa memicu crawl/analisis, VoC perlu:

1. Memberlakukan `require_service_principal` pada `fetch_jobs`, `analysis`, `pipeline`,
   `fetch_logs` — sebagai **alternatif** `get_current_user`, bukan pengganti (FE VoC
   masih memakainya).
2. Scope baru: `fetch:write`, `analysis:write`, `fetch_logs:read`. Pola pengecekannya
   sudah ada di `integration_reviews.py:137`.
3. **Perbaiki prompt kategorisasi** (§2.3) — 73/75 jatuh ke `doctor_service`. Ini
   yang paling mendesak; tanpa ini panel Top Issue tidak bisa dipakai.
4. Hidupkan kembali Ollama, atau sediakan fallback provider AI.

Catatan temuan sampingan: di `pipeline.py:73`, `SeleniumFetchService()` dipanggil
**tanpa** `company_id`, padahal `fetch_jobs.py:85` memanggilnya dengan `company_id`.
Perlu dicek apakah itu celah tenant.

Prompt siap kirim: `PROMPT_VOC_AGENT_ACTION_SCOPES.md`.

## 7. Yang sudah dikerjakan (2026-07-21)

| Perubahan | File |
|---|---|
| Filter + paging server-side | `VocController::reviewsDataAction` |
| Tombol "Tarik Review Sekarang" | `VocController::syncnowAction` + `reviews.volt` |
| Tombol "Kelola" → ticket detail | `reviews.volt` |
| Panel kategori tidak lagi tampil sebagai satu balok | `dashboard.volt` |

Hasil verifikasi:

| Uji | Hasil |
|---|---|
| `Voc/reviewsData` tanpa filter | `total=75`, 25 halaman @3 |
| `?q=Fajrina` | 1 baris, nama benar |
| `?sentiment=negative&urgency=high` | 17 |
| `?location=1703` | 25 (Hermina Depok) |
| `POST Voc/syncnow` | 2 koneksi ok, 4.7s, "tidak ada review baru" (cursor di watermark) |
| `GET Voc/syncnow` | `405 Gunakan POST.` |
| Render 5 layar VoC | semua `200`, tanpa error Volt |

### Bug yang ketemu saat pengerjaan

Kolom "Nama Pasien" sebelumnya selalu kosong. Penyebabnya `Meta` **tidak** menyimpan
`reviewer_name` — nama reviewer masuk sebagai `Contact` saat Ticket dibuat. Query
sekarang mengambilnya lewat `Ticket.ContactId → Contact.Name`, dan pencarian nama
ikut memakai kolom itu (bukan JSON), jadi lebih tepat sekaligus lebih murah.

### Catatan cara kerja tombol Tarik

`syncnowAction` menjalankan pipeline yang sama dengan CLI `receive`, lalu memproses
message yang belum jadi Ticket dan menjalankan `applyAnalysis` sekali lagi. Langkah
kedua itu perlu karena Ticket normalnya dibuat asinkron oleh worker; di lingkungan
demo tanpa worker, message akan menggantung tanpa Ticket. Hanya message dengan
`ObjectId IS NULL` yang disentuh — sama seperti task `processpending` — sehingga
tidak dobel kalau worker ternyata hidup.

### Alternatif untuk masalah kategori (§2.3)

Selain meminta VoC memperbaiki prompt, OneBox bisa menentukan kategori sendiri lewat
rule engine yang sudah ada (`app/services/Ruling.php`, dipanggil otomatis di
`Ticketing.php:263` saat Ticket dibuat) — ini keputusan **D11 rule-first** di
`implementation-plan-onebox/LABELING_rule-first-strategy.md`. Untuk site 169 sudah
ada 41 row `Rule` (semuanya `Enabled=0`) dan 125 Category ber-`Remarks`.

Keunggulannya: deterministik, bisa diaudit, dan **tidak bergantung pada pihak lain**.
`applyAnalysis` hanya mengisi `CategoryId` kalau masih kosong, jadi kategori hasil
rule tidak akan ditimpa hasil AI. Belum dikerjakan — perlu keputusan dulu.
