# Validasi Status & Urutan Kerja — Sayyid (VoC)

**Divalidasi:** 10 Agustus 2026
**Sumber klaim:** `SAYYID_TASK_BREAKDOWN.md` (tracker)
**Metode:** pemeriksaan langsung ke basis data dev (`onecloud_rel`), basis data lokal,
kode di `feature/voc`, dan kontrak OpenAPI Crawler. Setiap koreksi di bawah membawa
buktinya.

---

## 1. Koreksi status — tracker vs kenyataan

### 1.1 Diklaim **Done**, sebenarnya belum

| Task                                                     | Klaim     | Kenyataan                                                                                                                                                                                       | Bukti                                                                                                                                                                                              |
| -------------------------------------------------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Fetch Jobs — merge dua commit ke `feature/voc`**       | Done 100% | **Gagal acceptance-nya sendiri.** Kriteria "tidak ada regression pada route VoC utama" tidak terpenuhi                                                                                          | Sesudah merge: layar Lokasi mati total (syntax error JS `.prop()` tanpa penerima), `dashboardData` balas 500 (`count()` atas null karena 4 inisialisasi variabel hilang saat merge)                |
| **Deduplication index by message_id, tanggal, pengirim** | Done      | **Tidak ada index basis data sama sekali.** Yang ada penjaga di PHP memakai `external_review_id`, dan ia memindai seluruh review cabang tiap instance — `JSON_EXTRACT` tidak bisa memakai index | Diukur 28 ms per panggilan di DB lokal; komentar di `VocProvider::sudahPernahMasuk()`                                                                                                              |
| **Ticket type** (tersirat pada QA Fetch Jobs)            | —         | **Tiket VoC masih lahir TT1**                                                                                                                                                                   | 113 tiket `MediaId=GBUSINESS` ber-TT1 di dev, 9 di antaranya 4–6 Agu dari koneksi PVD99. Akar: `Ticketing.php` menentukan TypeId dari setting site `messaging`, dan site 169 tidak punya baris itu |

### 1.2 Diklaim **Partial/Not Started**, sebenarnya sudah selesai

Dikerjakan dan diverifikasi 7–10 Agustus, belum tercermin di tracker:

| Task | Status sebenarnya | Bukti |
|---|---|---|
| List review 2 baris + reply status | **Selesai** | Kolom BALASAN + cuplikan 2 baris; `replied`/`reply_text`/`reply_time` di `reviewsData` |
| Official/non-official flag | **Selesai** | `Connection.Options.is_official`; diuji ujung-ke-ujung, `official=True` hanya pada koneksi yang ditandai |
| Reply official → draft | **Selesai sebagai draft** | Tombol mati pada non-official dengan alasan tertulis; draft tersimpan di `Meta.reply_draft` beserta maker & waktu |
| KPI bintang clickable | **Selesai** | Filter bintang berdiri sendiri, chip cocok dengan hasil kliknya (57/11/6/15/429) |
| Ikon aksi | **Selesai** | Tombol `Review` berlabel, bukan pensil |
| Filter tanggal Fetch Jobs | **Selesai** | Preset + rentang start/end, ditolak bila tanggal palsu (`2026-02-31`) |
| Maker id (sebagian) | **Sebagian** | `Meta.reply_draft.maker` sudah tersimpan; `reviewer_id`/approval belum |

### 1.3 Status yang sudah benar

Legacy push-sync, QA Review Detail actions, AI Config button, QA delta sync/checkpoint,
QA Fetch Jobs utama — semuanya cocok dengan pemeriksaan.

---

## 2. Penghalang yang tidak ada di tracker

Empat hal ini **memblokir QA task lain**, jadi harus lebih dulu.

| # | Penghalang | Dampak | Bukti |
|---|---|---|---|
| **B1** | **Service token dev ditolak Crawler** — `401 INVALID_SERVICE_TOKEN` | Riwayat Fetch, status crawl, dan tarik review **semuanya mati di dev**. Seluruh QA Fetch Jobs & Scheduler terhambat | 14 koneksi PVD99 memakai token identik (MD5 `75f0e58a`); jaringan sehat (dapat 401, bukan connection error) |
| **B2** | **Kategori `TC1` tidak ada di dev** | Dropdown kategori kosong; koreksi kategori tidak bisa di-QA | Site 169 dev hanya punya `TC2`, `TC3`, `SMS`, `QC`. Lokal punya 18 TC1 lengkap dengan slug |
| **B3** | **Koordinat lokasi semuanya 0** | Peta dashboard kosong; monitoring lokasi tidak bisa didemokan | `Location.Latitude/Longitude` = 0 untuk seluruh cabang VoC |
| **B4** | **Lokal MySQL 8 vs dev MySQL 5.7** | Kelas bug SQL yang **mustahil** ketahuan sebelum deploy | Alias query luar di klausa `ON` subquery: diterima 8.0, ditolak 5.7 (`#1054`) — pernah mematikan layar Lokasi |

---

## 3. Urutan kerja

### Tahap 0 — Buka jalan (blocker, 0,5 hari)

| # | Kerjaan | Kenapa duluan |
|---|---|---|
| 0.1 | Merge perbaikan regresi: `locations.volt` (JS), `dashboardDataAction` (init variabel), `Ticketing.php` (TT3) | Tanpa ini `feature/voc` rusak dan tidak bisa di-QC sama sekali |
| 0.2 | Minta token Crawler baru, perbarui `Options.service_token` di dev | Membuka **seluruh** QA Fetch Jobs & Scheduler |
| 0.3 | Jalankan `scriptdb/voc/voc_setup_all.sql` di dev (kategori TC1) | Membuka QA kategori & analisis |
| 0.4 | Isi koordinat 6 cabang lewat layar Lokasi | Membuka demo peta |

### Tahap 1 — Amankan yang sudah jalan (1–2 hari)

| # | Kerjaan | Prioritas |
|---|---|---|
| 1.1 | Migrasi data: 113 tiket TT1 lama → TT3 (butuh persetujuan senior dev) | Critical |
| 1.2 | **Index dedup sungguhan** — kolom terindeks untuk `external_review_id`, bukan `JSON_EXTRACT` | Critical |
| 1.3 | Backfill lokasi baru ke worklist Crawler | High |
| 1.4 | Buang demo snapshot fallback di workspace/dashboard | High |
| 1.5 | QA workspace API dengan tenant real | High |

### Tahap 2 — Lengkapi Review Manage (2–3 hari)

| # | Kerjaan | Prioritas |
|---|---|---|
| 2.1 | Eskalasi ke PIC + jalur WhatsApp | Critical |
| 2.2 | Panel kanan detail: URL review asli, metadata lengkap | High |
| 2.3 | `maker_id` + `reviewer_id` pada semua action | High |
| 2.4 | Create ticket + klasifikasi otomatis | High |
| 2.5 | Rapikan list hasil crawling (filter waktu/status/sumber) | High |

### Tahap 3 — Fetch Jobs produksi (2–3 hari)

| # | Kerjaan | Prioritas |
|---|---|---|
| 3.1 | Job history & log dari data real (buang sample) | High |
| 3.2 | Dry run, retry, cancel | High |
| 3.3 | Status/counter/loading/empty/error | Medium |

### Tahap 4 — Kontrak AI (1 hari)

| # | Kerjaan | Prioritas |
|---|---|---|
| 4.1 | Kunci scope: Crawler pilih model, OneBox hanya `ai_enabled` + `output_schema_version` | Critical |
| 4.2 | Simpan config AI di `Connection.Options`, kirim lewat worklist | High |

### Tahap 5 — Scheduler (4–6 hari) — **paling berat**

| # | Kerjaan | Prioritas |
|---|---|---|
| 5.1 | Engine crawler naik ke gateway | Critical — **prasyarat semua di bawahnya** |
| 5.2 | Scheduler core: jadwal, timezone, locking, idempotency | Critical |
| 5.3 | Trigger non-blocking + run history + counter | Critical |
| 5.4 | Run Now + permission + quota | High |
| 5.5 | Test multi-account / multi-company / multi-site | Critical |
| 5.6 | Monitoring: concurrency, backoff, alert | High |
| 5.7 | UI jadwal & riwayat | Medium |

---

## 4. Apakah semuanya doable?

**Sebagian besar ya. Tiga tidak, dengan kondisi sekarang.**

| Task | Doable? | Catatan |
|---|---|---|
| **Simpan photo URL review** | **Tidak** | Skema `ReviewResponse` Crawler **tidak punya field foto lampiran** sama sekali. `reviewer_photo_url` itu foto profil, dan kosong di seluruh data uji. Butuh perubahan sisi Crawler lebih dulu |
| **Simpan waktu response** | **Tidak** | `owner_response_time` terisi **0 dari 87**, sementara teksnya terisi 70. Crawler mengambil isinya tetapi tidak waktunya. **SLA response tidak bisa dihitung sama sekali** sampai ini diperbaiki |
| **Reply official ke Google** | **Tidak sekarang** | Butuh Google Business Profile API + OAuth. Saat ini disimpan sebagai draft — itu keputusan yang sudah diambil, bukan kekurangan |
| Sisanya | **Ya** | Sepanjang Tahap 0 selesai |

---

## 5. Yang paling mahal

Diurutkan dari yang paling banyak memakan waktu dan paling besar risikonya.

### 🔴 1. Scheduler + gateway (Tahap 5) — **jauh paling berat**

Ini bukan satu fitur, melainkan **perubahan arsitektur**. Yang membuatnya mahal:

- **Kebenaran konkurensi tidak bisa dibuktikan dengan membaca kode.** Locking, idempotency, dan race condition hanya terbukti lewat pengujian yang benar-benar menjalankan dua worker bersamaan.
- **Menyentuh dua sistem sekaligus** — OneBox dan Crawler — dengan kontrak antar keduanya yang harus disepakati dulu.
- **Uji multi-tenant butuh data multi-tenant.** Saat ini hanya ada satu site (169) dengan data nyata.
- **Gagalnya senyap.** Job yang double atau terlewat tidak melempar error; ia hanya menghasilkan angka yang salah, dan baru ketahuan berhari-hari kemudian.

Perkiraan: **4–6 hari**, dan itu pun bila 5.1 (gateway) beres lebih dulu.

### 🟠 2. Index dedup sungguhan (1.2)

Terlihat kecil, sebenarnya tidak. `external_review_id` sekarang berada **di dalam JSON**,
dan MySQL tidak bisa mengindeks isi JSON tanpa generated column. Berarti: migrasi
menambah kolom, mengisi ulang seluruh baris lama, mengganti query, lalu memastikan
dedup lama tetap bekerja selama transisi. Dan ini menyentuh jalur yang **setiap
review** lewati. **1–2 hari.**

### 🟠 3. Eskalasi WhatsApp (2.1)

Bergantung pada entitlement tenant yang belum jelas kontraknya, plus jalur mundur
bila tidak berlangganan. Logika bercabang selalu lebih mahal daripada kelihatannya.
**1 hari.**

### 🟡 4. Migrasi TT1 → TT3 (1.1)

Kodenya sepele. Yang mahal: memastikan **hanya** tiket VoC yang tersentuh. Site 169
punya 986 tiket WhatsApp dan 416 Twitter yang juga TT1 dan **tidak boleh ikut
berubah**. Salah predikat = merusak modul lain. **0,5 hari, tapi butuh review.**

### 🟢 Yang murah

Job history real, dry run/retry/cancel, panel kanan detail, maker/reviewer id,
create ticket, rapikan list — semuanya di dalam satu berkas dengan pola yang sudah
ada. **0,5–1 hari masing-masing.**

---

## 6. Rekomendasi

1. **Jangan mulai Scheduler sebelum Tahap 0 dan 1 beres.** Otomatisasi yang dibangun
   di atas fetch yang belum stabil akan melipatgandakan bug-nya, bukan menemukannya.
2. **Kejar B1 (token) hari ini.** Ia memblokir paling banyak pekerjaan lain dan
   penyelesaiannya ada di tangan orang lain — makin cepat diminta makin baik.
3. **Naikkan dua item Crawler jadi permintaan resmi:** foto lampiran dan
   `owner_response_time`. Keduanya memblokir task yang di tracker tertulis
   "Partial", padahal sebenarnya **tidak bisa dikerjakan dari sisi OneBox sama sekali**.
4. **Samakan versi MySQL lokal dengan dev.** Selisih 8.0 vs 5.7 sudah sekali
   mematikan layar Lokasi di dev sementara lokal bersih. Selama masih beda,
   setiap QA lokal punya titik buta yang tidak bisa ditutup dengan ketelitian.
