# ADR-0001 — Inversi Kepemilikan: OneBox jadi System of Record

- **Status:** Accepted — ⚠️ **mekanisme provisioning di-amandemen [ADR-0003](ADR-0003-crawl-execution-pull-queue.md)** (push sinkron → pull worklist). Keputusan inti "OneBox = System of Record" tetap berlaku.
- **Tanggal:** 2026-07-21
- **Pengambil keputusan:** Sayyid (dev) — ⚠️ belum diratifikasi Pak Agung
- **Menggantikan (supersedes):** `crawler_system/erd.md`, `crawler_system/dfd.md`, `integrations/architecture_diagram.md` (+`.drawio`), `implementation-plan-onebox/RI-06_tenant-mapping.md`, sebagian `RI-02` (D2, D6)

---

## Context

Desain awal VoC System dibuat saat ia diposisikan sebagai **produk standalone**: punya FE Next.js sendiri, punya `Company`, `User`, `Location`, `Competitor` sendiri, dengan auth JWT user-based.

Kemudian keputusan berubah: **VoC menjadi fitur di dalam OneBox**. Namun **kepemilikan master data tidak ikut ditinjau ulang.** Akibatnya sistem yang sudah dibangun sampai RI-07 memiliki cacat desain:

| Data | Pemilik (sebelum ADR ini) | Masalah |
|---|---|---|
| Location | VoC | OneBox mereferensi ID sistem lain (`Connection.TargetId` = `location_id` VoC) |
| Competitor | VoC | Setup di luar OneBox |
| Company / User | VoC (auth sendiri) | Duplikasi identitas & tenant |
| Review + Analysis | VoC | ✅ ini benar |

**Gejala nyata yang terverifikasi di kode:**
- `Connection.TargetId` = `location_id` milik VoC → OneBox bukan sumber kebenaran.
- Menambah 1 lokasi = kerja manual di **2 sistem** (buat Location di VoC → insert Connection di OneBox).
- Halaman Locations di OneBox (`VocController::locationsDataAction`) hanya **agregat dari review**, bukan manajemen lokasi.
- VoC punya FE sendiri → dua permukaan konfigurasi untuk satu produk.

---

## Decision

**OneBox adalah System of Record untuk SELURUH modul VoC, kecuali proses scraping.**

VoC System direduksi menjadi **crawler engine headless** — tanpa tampilan, tanpa kepemilikan master data.

### Pembagian final

| Modul | Pemilik | Catatan |
|---|---|---|
| Dashboard | **OneBox** | |
| Review management | **OneBox** | |
| Location management | **OneBox** | VoC hanya menerima hasilnya |
| Competitor management | **OneBox** | |
| Reports | **OneBox** | |
| Insights | **OneBox** | |
| Setup parameter/benefit | **OneBox** | pakai `Benefit`/`SiteBenefit` existing |
| AI Analysis | **kendali OneBox, eksekusi VoC** | lihat [ADR-0002](ADR-0002-ai-execution-split.md) |
| **Scrape review** | **VoC** | satu-satunya milik VoC |
| Review + Analysis storage di VoC | VoC (sebagai **cache**) | bukan master data — lihat Reframe |

### Reframe yang menyelesaikan ketegangan

Tabel `Location`/`Competitor` di VoC **bukan master data** — itu **"crawl target registry"**, turunan yang **hanya boleh ditulis oleh OneBox**. Analoginya seperti index pencarian: turunan, bukan sumber kebenaran.

Penyimpanan `Review`+`ReviewAnalysis` di VoC dipertahankan sebagai **cache** — supaya tidak re-scrape dan tidak re-analisa (hemat token). Bukan karena VoC memilikinya.

### Mekanisme: auto-provisioning

> ⚠️ **DI-AMANDEMEN oleh [ADR-0003](ADR-0003-crawl-execution-pull-queue.md).** Mekanisme push sinkron di
> bawah ini **tidak lagi dipakai** — diganti **pull worklist** (VoC menarik daftar target dari OneBox).
> Simpan lokasi di OneBox kini commit lokal instan, tanpa panggilan sinkron ke VoC. Blok di bawah
> dipertahankan sebagai histori keputusan awal.

User **hanya menyentuh OneBox**. Saat menyimpan lokasi di OneBox:

```
OneBox: simpan Location
  → panggil VoC POST /api/locations        (endpoint SUDAH ADA [verified])
  → terima location_id
  → auto-create/update Connection (TargetId=location_id, Options.company_id, credential)
```

Tidak ada langkah manual di VoC.

---

## Consequences

### Positif
1. Satu permukaan konfigurasi — user cukup paham OneBox.
2. Tidak ada lagi setup manual 2 sistem per lokasi.
3. Tenant/identitas tunggal (OneBox `SiteId`), VoC cukup service account.
4. Kuota & entitlement terpusat di `Benefit`/`SiteBenefit`.

### Negatif / biaya
1. **Rework:** OneBox butuh CRUD Location & Competitor (sekarang belum ada — hanya agregat).
2. **Data ter-mirror** → butuh aturan tegas: OneBox authoritative, VoC read-only bagi manusia.
3. **FE Next.js VoC menjadi dead code** untuk alur produksi (dipertahankan dev-only/benchmark).
4. **`User`/`Company` di VoC** dipensiunkan menjadi service account saja.
5. Dokumen desain lama harus ditandai basi (lihat Supersedes).

### Risiko
- Kalau lokasi dihapus di OneBox tapi gagal terhapus di VoC → crawl target yatim. **Mitigasi:** operasi tulis ke VoC harus punya retry + status tersimpan di OneBox.
- `BenefitService` mengambil site dari **JWT** — di konteks web session bisa kosong. **Wajib diverifikasi** sebelum dipakai di `VocController`.

---

## Yang harus berubah di kode

| # | Perubahan | Sisi |
|---|---|---|
| 1 | CRUD Location (form + simpan) | OneBox |
| 2 | Auto-provisioning: simpan Location → `POST /api/locations` → auto-create Connection | OneBox |
| 3 | CRUD Competitor + auto-provisioning serupa | OneBox |
| 4 | Registrasi Benefit code `VOC_*` + `verifyBenefit`/`addUsage` | OneBox |
| 5 | FE Next.js dikeluarkan dari alur produksi | VoC |
| 6 | Auth user-based → service account saja | VoC |

---

## Alternatif yang ditolak

**VoC jadi stateless murni** (OneBox kirim perintah tiap crawl, VoC tidak menyimpan apa pun).
Ditolak karena: VoC akan lupa apa yang sudah dianalisa → **re-analisa AI tiap crawl → boros token**, bertabrakan langsung dengan strategi rule-first (D11) yang justru menghemat token.

---

## Ratifikasi internal — 2026-07-22

Sayyid menetapkan daftar berikut **non-negotiable**: seluruh modul di bawah dikelola di OneBox,
scraping tetap milik VoC.

| Modul | Status implementasi |
|---|---|
| Setup lokasi / location management | ✅ CRUD jalan (`VocController::locationSave/Toggle/Delete`) |
| Setup competitor / competitor management | ⏳ belum — pola sama dengan lokasi |
| Dashboard | ✅ jalan |
| Review management | ✅ jalan |
| Reports | ⏳ stub |
| Insights | ⏳ stub — **cakupannya masih dikaji ulang** |
| AI analysis | ⏳ parameter masih di VoC — **cakupannya masih dikaji ulang** |
| Setup parameter/benefit | ⏳ terhalang cacat `BenefitService` (lihat Konsekuensi teknis) |

⚠️ **Ini ratifikasi internal dev, bukan persetujuan Pak Agung.** Baris "Pengambil keputusan"
di atas tetap berlaku: ADR ini belum dibawa ke lead.

### Konsekuensi teknis yang ditemukan saat eksekusi (2026-07-22)

Dua asumsi di ADR ini ternyata tidak akurat, terverifikasi langsung ke kode dan ke API staging:

1. **"`POST /api/locations` SUDAH ADA [verified]"** — endpoint-nya memang ada, tapi memakai
   `OAuth2PasswordBearer` (JWT user), sementara OneBox berjalan dengan service token
   (`HTTPBearer`). Dari 39 operasi di VoC, hanya 2 yang menerima service token.
   `require_service_principal` cuma di-import oleh `integration_reviews.py`.
   **Solusi yang dipakai:** satu Connection membawa dua kredensial — service token untuk
   BACA review, akun user untuk TULIS lokasi/kompetitor. Tidak perlu perubahan di sisi VoC.

2. **Risiko `BenefitService` ternyata lebih besar dari yang tertulis** — tiga cacat, semua
   sudah diperbaiki 2026-07-22:

   | Cacat | Akibat |
   |---|---|
   | `getSiteBenefitById()` baca `jwt->get('sid')`; `sid` hanya di-set `ReactController` & `api/v1/AuthenticateController` | Di web session site = null → `hasBenefit()` **selalu false, gagal senyap** |
   | `addUsage()` menaikkan `Benefit->Amount` — **tabel `Benefit` tidak punya kolom `Amount`** | Set properti dinamis, `update()` tidak menyimpan apa pun. Pemakaian tercatat **ke mana-mana tidak**. Metering token [ADR-0002](ADR-0002-ai-execution-split.md) mustahil |
   | `hasBenefit()` memanggil `$benefit->Id` tanpa cek null | Kode benefit tidak dikenal → fatal error |

   Perbaikan: lookup site pakai rantai `jwt → session → config` (JWT tetap didahulukan supaya
   jalur API `RESTController` tidak berubah), `addUsage()` menulis ke `SiteBenefit.Amount`
   milik site aktif, dan semua lookup dikasih guard null + bound parameter.

   **Masih berlaku sebagai jebakan:** `verifyBenefit()` bukan pemeriksaan murni — ia
   menaikkan `SiteBenefit.Quantity`. Memasangkannya dengan `addUsage()` untuk satuan yang
   sama = hitung dobel. Pakai `verifyBenefit()` untuk kuota **jumlah panggilan**,
   `addUsage()` untuk kuota **nilai** (token).

### Temuan data

VoC punya 3 lokasi (`2` HGA Depok, `4` Hermina Depok, `5` Bekasi); OneBox hanya punya
Connection untuk 2 dan 4. **Bekasi di-crawl VoC tapi review-nya tidak pernah masuk OneBox** —
contoh konkret masalah yang ADR ini selesaikan. Rekonsiliasi masuk lingkup auto-provisioning.

---

## Tindak lanjut
1. Bawa ADR ini ke Pak Agung untuk ratifikasi (mengubah asumsi RI-06 & RI-02 D2/D6).
2. Tandai dokumen basi dengan banner deprecation.
3. Eksekusi perubahan kode sesuai tabel di atas.
