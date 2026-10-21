---
title: Multi-Tenant Readiness — Open Questions
aliases:
  - MT Open Questions
  - Pertanyaan Terbuka Multi-Tenant
tags:
  - voc
  - multitenant-readiness
  - open-questions
status: living
updated: 2026-10-21
owner: Sayyid
open_count: 16
answered_count: 15
dropped_count: 2
---

# Multi-Tenant Readiness — Open Questions

> [!abstract] Navigasi
> [[README|Index]] · [[01-PLAN|Plan]] · [[02-DESIGN|Design]] · [[03-IMPLEMENTATION|Implementation]] · [[04-OPEN-QUESTIONS|Open Questions]]

> [!info] Cara pakai register ini
> - **Papan status** di bawah = ringkasan. **Detail** tiap pertanyaan ada di heading `Q-xx` — tautkan dengan `[[04-OPEN-QUESTIONS#Q-07]]`.
> - **Menjawab:** isi blok *Jawaban* (+ sumber & tanggal) di detail Q, pindahkan barisnya dari "Masih terbuka" ke "Sudah terjawab", perbarui `open_count` / `answered_count`, lalu ikuti protokol di [[README#Protokol update (wajib diikuti)]].
> - **Pertanyaan baru:** nomor berikutnya, jangan pakai ulang. Pertanyaan yang tidak relevan lagi → "Di-drop" + alasan.
> - Status: `open` · `proposed` (ada usulan, menunggu konfirmasi) · `partial` (sebagian terjawab) · `answered` · `dropped`.

**Prioritas:** 🔴 menghambat keputusan arsitektur / risiko data · 🟠 menghambat satu fase · 🟢 bisa belakangan

---

## Papan status

### Masih terbuka

| ID | Prio | Topik | Pertanyaan singkat | Ditujukan ke | Menghambat | Status |
|---|---|---|---|---|---|---|
| [[#Q-10]] | 🟢 | Data | Kapan review boleh dibersihkan dari DB Crawler setelah masuk OneBox? | Sayyid | — | partial |
| [[#Q-11]] | 🟠 | Biaya | Apify per tenant: cukup dicatat, atau dibatasi kuota? | Product | MT-41 | partial |
| [[#Q-13]] | 🟠 | Skala | Berapa tenant aktif & review baru per hari yang ditargetkan? | Product / CEO | MT-40, MT-41 | partial |
| [[#Q-15]] | 🟢 | Integrasi | Revert `13ad618` di staging alasannya sama dengan Q-14? | Sayyid | MT-03 | open |
| [[#Q-19]] | 🟢 | Onboarding | Selain aktivasi paket VoC, ada langkah Registration lain untuk site baru? | Tim OneBox | MT-52 | open |
| [[#Q-21]] | 🟠 | Rollout | `company_id` Hermina per environment (dev/staging/prod) untuk backfill | Ops | MT-10 | open |
| [[#Q-22]] | 🟢 | Observability | Alert apa yang wajib per tenant & lewat kanal apa? | Sayyid / ops | MT-42 | open |
| [[#Q-23]] | 🟠 | Governance | ADR-0006 diratifikasi Pak Agung — kapan & format? | Sayyid | MT-01, E8 | open |
| [[#Q-25]] | 🟠 | Istilah | "Proxy check" maksudnya apa? | Sayyid | MT-01 | open |
| [[#Q-26]] | 🔴 | Round robin | Bobot tenant: sumbernya, rumusnya, defaultnya? Ada batas konkurensi per tenant? | Sayyid / product | MT-40 | open |
| [[#Q-28]] | 🟠 | Keamanan | Token di Setup Parameter: siapa yang boleh lihat & regenerate? | Sayyid / security | MT-31 | proposed |
| [[#Q-29]] | 🟠 | Reliability | Crawler mati saat paket diaktifkan — OneBox retry bagaimana? | Sayyid | MT-30 | proposed |
| [[#Q-30]] | 🟢 | AI/ML | Setting per tenant (kategori ML): disimpan di mana & dikirim lewat apa? | Product / ML | MT-44 | open |
| [[#Q-31]] | 🔴 | Inventaris | Apa saja yang sudah diimplementasi/diubah di OneBox untuk multisite? | Sayyid (cek kode OneBox) | Fase 3 | open |
| [[#Q-32]] | 🔴 | Reliability | Queue OneBox untuk push worklist & provisioning (retry, debounce, status) seandal apa? | Sayyid (cek kode OneBox) | MT-33, MT-35 | open |
| [[#Q-33]] | 🟠 | Kontrak | `snapshot_version`: counter per site di OneBox, atau `generated_at` + hash? | Sayyid | MT-13, MT-32 | proposed |

### Sudah terjawab

| ID | Pertanyaan singkat | Jawaban singkat | Sumber | Tanggal |
|---|---|---|---|---|
| [[#Q-01]] | Mekanisme penemuan tenant | Tidak ada service yang loop per site (lambat). OneBox = SoR; tenant terdaftar karena aksi OneBox (aktivasi paket VoC); crawler menjalankan **weighted round robin** antar tenant | Sayyid (chat) | 2026-10-21 |
| [[#Q-02]] | Login tanpa `siteId` sebagai discovery | **Tidak bisa** — satu `site_id` = satu company; akses backend hanya untuk site berpaket VoC aktif | Sayyid (chat) | 2026-10-21 |
| [[#Q-03]] | Kredensial antar sistem | Satu crawler untuk semua tenant. **Opsi D:** crawler tidak memegang kredensial OneBox — OneBox **push** snapshot worklist ke crawler memakai token tenant | Sayyid (chat) | 2026-10-21 |
| [[#Q-04]] | Pembatasan kredensial | **Semua kredensial dikelola di OneBox** | Sayyid (chat) | 2026-10-21 |
| [[#Q-05]] | `ApiClient` tenant baru | Tidak ada proses manual: paket VoC aktif → Connection otomatis → token dibuat & disimpan di Connection; ditampilkan di Setup Parameter OneBox | Sayyid (chat) | 2026-10-21 |
| [[#Q-08]] | Flag entitlement di `companies` Crawler | Tidak di-setup di Crawler; nilainya mengikuti OneBox | Sayyid (chat) | 2026-10-21 |
| [[#Q-09]] | Tenant nonaktif | Job `pending` **dibatalkan**, job `claimed` **dibiarkan selesai**, data tetap | Sayyid (chat) | 2026-10-21 |
| [[#Q-12]] | Keadilan antrean worker | Ya — **weighted round robin per tenant**, logikanya di crawler | Sayyid (chat) | 2026-10-21 |
| [[#Q-14]] | Prompt generik di-revert di staging | Disengaja: staging tetap prompt Hermina sebagai default untuk testing; prompt generik masih di dev, dirilis bertahap | Sayyid (chat) | 2026-10-21 |
| [[#Q-17]] | Bahaya refresh lintas tenant | Diselesaikan oleh desain: refresh on-demand diganti refresh ber-token tenant; guard interim tetap dipasang (MT-02) | Desain baru | 2026-10-21 |
| [[#Q-18]] | Kardinalitas site ↔ company | **Satu site = satu company** | Sayyid (chat) | 2026-10-21 |
| [[#Q-20]] | Site uji tenant kedua | **Site 177** (testing) di dev, berdampingan dengan **site 169** (utama) | Sayyid (chat) | 2026-10-21 |
| [[#Q-24]] | Lokasi uji dua tenant | Dev environment (site 169 + 177 sudah ada); laptop cadangan sedang setup OneBox | Sayyid (chat) | 2026-10-21 |
| [[#Q-07]] | Gerbang paket VoC | Tidak ada lagi panggilan crawler → `VocWorklist`. OneBox hanya provisioning & push untuk site berpaket VoC aktif; paket mati → `PATCH active=false` | Desain opsi D | 2026-10-21 |
| [[#Q-16]] | Pemicu pembaruan worklist | OneBox push snapshot saat paket aktif, cabang/kompetitor berubah, tombol Refresh, dan scheduled push; ketinggalan dicek lewat `GET /tenants/{site_id}` | Desain opsi D | 2026-10-21 |

### Di-drop

| ID | Alasan | Tanggal |
|---|---|---|
| [[#Q-06]] | `crawl_windows` tidak dipakai — penjadwalan antar tenant memakai **bobot** round robin, jam tetap urusan OneBox | 2026-10-21 |
| [[#Q-27]] | Tidak relevan dengan opsi D: crawler tidak login ke OneBox, jadi tidak butuh keanggotaan site | 2026-10-21 |

---

## Detail pertanyaan

### Q-01

**Mekanisme penemuan tenant (discovery): bagaimana crawler tahu harus melayani site mana?**

- **Konteks awal:** spec Opsi C mengusulkan crawler menarik `GET /api/VocTenants`; notulen Pak Agung menyebut pola loop `site_id` + `connection_id` aktif.
- **Jawaban (Sayyid, 2026-10-21):** service yang loop per site **sudah diputuskan tidak dipakai** karena akan lambat. OneBox adalah source of truth; crawler mengambil data company dari OneBox untuk dijalankan. Mekanisme multisite terbaru: **weighted round robin** untuk beberapa tenant sekaligus, masing-masing dengan bobotnya. Method & setup manual (CLI dll.) di crawler harus dikurangi.
- **Turunan desain:** tenant terdaftar di crawler **karena OneBox memanggilnya** saat paket VoC aktif (provisioning), bukan karena crawler mencari sendiri → [[02-DESIGN#3.2 Siklus hidup tenant digerakkan paket VoC]].
- **Sisa:** istilah "proxy check" belum jelas → [[#Q-25]].

### Q-02

**Bisakah login OneBox tanpa `siteId` dipakai sebagai discovery?**

- **Jawaban (Sayyid, 2026-10-21):** tidak bisa. Satu `site_id` mewakili satu company. Bila site punya paket VoC aktif, akses backend-nya di-enable.

### Q-03

**Kredensial antar sistem: satu akun lintas tenant, akun per tenant, atau cara lain?**

- **Jawaban awal (Sayyid, 2026-10-21):** satu crawler untuk semua tenant; akun mengikuti yang ada di OneBox; ke depan tiap tenant punya **setting sendiri** (kategori ML) → [[#Q-30]].
- **Keputusan akhir (Sayyid, 2026-10-21): Opsi D — OneBox push worklist.** Crawler tidak memegang kredensial OneBox apa pun dan tidak pernah memanggil OneBox. OneBox mengirim snapshot worklist ke `PUT /api/integration/v1/worklist` memakai **token tenant** yang sama dengan jalur baca review.
- **Opsi yang dipertimbangkan:**

| Opsi | Cara | Keputusan |
|---|---|---|
| A | Crawler login dengan akun user milik tiap site berlangganan | ❌ Ditolak — crawler menyimpan password banyak tenant; akun manusia dipakai mesin (ganti password → crawl mati); rantai `User→Member→Organization→Site→UserRole` per site rapuh |
| B | Satu akun layanan global, anggota semua site (kondisi sekarang) | ⚠️ Hanya mode transisi `single` |
| C | Satu kredensial mesin, otorisasi berdasarkan paket VoC aktif | Cadangan bila amandemen ADR-0003 ditolak atau queue OneBox rapuh ([[#Q-32]]) |
| **D** | **OneBox push snapshot worklist** | ✅ **Dipilih** |

- **Konsekuensi:** mengamandemen ADR-0003 D1 (pull worklist → push snapshot async, full snapshot, berversi); Q-27 di-drop; OneBox wajib punya queue andal ([[#Q-32]]). Detail: [[02-DESIGN#3.4 Worklist push (opsi D)]].

### Q-04

**Bagaimana kredensial dibatasi?**

- **Jawaban (Sayyid, 2026-10-21):** semua kredensial ada di OneBox dan dikelola dari sana.
- **Catatan desain:** crawler hanya menyimpan **hash** token (pola `api_clients.secret_hash` existing), bukan token mentah.

### Q-05

**Bagaimana tenant baru mendapat token untuk jalur baca review?**

- **Jawaban (Sayyid, 2026-10-21):** tidak ada yang dibuat manual. Saat paket VoC aktif di OneBox, Connection otomatis terbuat; token terbuat setelah paket aktif dan disimpan di Connection. Usulan Sayyid: token idealnya langsung dibuat di crawler juga, atau ditampilkan di halaman **Setup Parameter** OneBox untuk tim admin, sehingga **control panel semuanya di OneBox** (termasuk tombol refresh).
- **Bisa?** Bisa. `ApiClientService` di crawler sudah punya fungsi issue/rotate/revoke (`app/services/api_client_service.py`, saat ini dipanggil lewat CLI `scripts/manage_api_client.py`). Yang perlu dibuat: endpoint provisioning yang dipanggil OneBox, sehingga CLI tidak dibutuhkan lagi → [[02-DESIGN#3.3 Provisioning token per tenant]].
- **Turunan:** siapa yang boleh melihat token → [[#Q-28]]; kalau crawler mati saat aktivasi → [[#Q-29]].

### Q-06

**`crawl_windows` di daftar tenant?** — **Di-drop.** Field itu berasal dari spec lama (jam crawl pagi/siang/malam per tenant). Penjadwalan antar tenant sekarang memakai **bobot** round robin di crawler; jam crawl tetap diputuskan OneBox lewat trigger crawl-jobs (ADR-0003).

### Q-07

**Kalau site tidak punya paket VoC aktif, apa yang terjadi?**

- **Sudah jelas:** gerbangnya adalah **paket VoC** (Sayyid: "paket VoC itu dulu aja"). Paket lain (mis. kuota AI `VOC_AI`) menyusul.
- **Jawaban (desain opsi D, 2026-10-21):** pertanyaan awal ("`VocWorklist` membalas apa?") tidak relevan lagi karena crawler tidak memanggil `VocWorklist`. Gerbang sepenuhnya di OneBox: provisioning & push worklist hanya untuk site berpaket VoC aktif; paket dimatikan → `PATCH /tenants/{site_id} {active:false}`. Token tenant yang paketnya mati tetap bisa **membaca** hasil lama, tapi `PUT /worklist` dan enqueue crawl ditolak `409 TENANT_INACTIVE`.
- **Konsekuensi:** tidak ada self-healing dari sisi crawler; keandalan deaktivasi bergantung pada retry queue OneBox ([[#Q-29]], [[#Q-32]]).
- **Jebakan OneBox tetap berlaku:** cek paket pakai pemeriksaan murni (`hasBenefit`), bukan `verifyBenefit()` yang menaikkan `SiteBenefit.Quantity` ([[ADR-0001-ownership-inversion]] §Konsekuensi teknis).

### Q-08

**Flag `ai_enable_flag`, `total_enable_review`, `analyze_competitor_flag` di `companies` Crawler?**

- **Jawaban (Sayyid, 2026-10-21):** tidak ada setup di crawler; semuanya dari OneBox.
- **Turunan desain:** nilai dikirim OneBox di payload provisioning / setting tenant; `scripts/manage_company.py` tidak lagi dipakai untuk tenant OneBox.

### Q-09

**Tenant menjadi nonaktif: job dan data diperlakukan bagaimana?**

- **Jawaban (Sayyid, 2026-10-21):** job `pending` dibatalkan, job yang sudah `claimed` dibiarkan selesai, data tidak dihapus.
- **Turunan desain:** enqueue baru untuk tenant nonaktif ditolak (`TENANT_INACTIVE`); token baca tetap aktif supaya OneBox masih bisa menarik sisa hasil — kecuali OneBox meminta revoke.

### Q-10

**Review di DB Crawler: cache atau data primer, dan berapa lama disimpan?**

- **Jawaban sebagian (Sayyid, 2026-10-21):** untuk sekarang **disimpan saja** (volume akan makin besar, tapi aman). Ujungnya review masuk ke **history di OneBox**, yang DB-nya lebih besar — jadi OneBox yang memegang histori jangka panjang.
- **Sisa:** kapan crawler boleh membersihkan review yang sudah dipastikan masuk OneBox (mis. setelah N hari + konfirmasi ingest)? Belum perlu diputuskan sekarang.

### Q-11

**Kredit Apify per tenant?**

- **Jawaban sebagian (Sayyid, 2026-10-21):** biaya Apify **sebaiknya dipisah per tenant**, karena VoC punya harga sendiri (perkiraan ± **Rp200.000 per lokasi**). Kredit **$20 Apify sudah sangat banyak** — perkiraan cukup untuk **± 100.000 review**. Jadi pencatatan per tenant bagus.
- **Turunan desain:** minimal **atribusi** — catat jumlah review & biaya Apify per `company_id` per run (MT-41).
- **Sisa:** perlu **batas keras** per tenant (crawl berhenti saat kuota habis) atau cukup laporan? Angka $20 ≈ 100k review adalah perkiraan Sayyid — dicocokkan dengan tagihan Apify nyata setelah ada data per tenant.

### Q-12

**Antrean worker perlu keadilan per tenant?**

- **Jawaban (Sayyid, 2026-10-21):** ya — **weighted round robin per tenant**, berjalan di crawler; logikanya akan dibuat.
- **Turunan desain:** [[02-DESIGN#3.5 Weighted round robin antar tenant]]. Bobot → [[#Q-26]].

### Q-13

**Target skala?**

- **Jawaban sebagian (Sayyid, 2026-10-21):** tenant = company di OneBox, diasumsikan **enterprise / tersebar luas** (contoh: Pertamina, Hermina, Kopi Kenangan). Perkiraan **maksimum ± 100 lokasi per tenant × ± 1.000 review per lokasi**; rata-rata lebih kecil (± **500 review per lokasi**).
- **Hitungan kasar per tenant terbesar:** backfill awal ± 100.000 review → dengan perkiraan di [[#Q-11]], ± $20 kredit Apify.
- **Sisa:** berapa tenant aktif dalam 6–12 bulan, dan berapa review **baru** per hari per lokasi (menentukan beban delta harian, bukan hanya backfill).

### Q-14

**Kenapa prompt generik (`2d47205`) di-revert di staging?**

- **Jawaban (Sayyid, 2026-10-21):** disengaja. Prompt generik **masih tahap develop** (di `dev`). Staging tetap memakai prompt **Hermina sebagai default** supaya bisa dipakai testing; rilis bertahap di rilis berikutnya.
- **Turunan desain:** pemilihan prompt per tenant dimasukkan ke setting tenant (MT-44, [[#Q-30]]); default tetap Hermina di staging sampai rilis.

### Q-15

**Kenapa `13ad618` (resolve lokasi OneBox di dalam tenant) juga di-revert di staging?**

- **Dugaan:** alasannya sama dengan [[#Q-14]] (staging dikunci untuk testing) — `[asumsi]`, belum dikonfirmasi.
- **Jawaban:** _belum_

### Q-16

**Apa yang memicu pembaruan worklist di crawler?**

- **Jawaban (desain opsi D, 2026-10-21):** OneBox mengirim (push) snapshot worklist lengkap saat:
  1. paket VoC baru aktif (setelah provisioning token);
  2. cabang/kompetitor ditambah, diubah, atau dinonaktifkan (dengan **debounce** — beberapa perubahan beruntun → satu kiriman);
  3. tombol **Refresh** di Setup Parameter;
  4. **scheduled push** berkala (usulan: tiap 60 menit atau sebelum tiap window crawl) sebagai jaring pengaman.
- **Deteksi ketinggalan:** OneBox membaca `GET /api/integration/v1/tenants/{site_id}` → `snapshot_version` terakhir yang diterapkan crawler; bila tertinggal, kirim ulang.
- Semua kiriman lewat queue OneBox (tidak menahan jalur simpan) → [[#Q-32]].

### Q-17

**Bahaya refresh worklist lintas tenant.** — **Diselesaikan oleh desain.** Refresh on-demand di dalam enqueue/analisa diganti endpoint refresh yang tenant-nya diturunkan dari token, dan login worklist memakai `site_id` milik company itu. Sampai itu jadi, **MT-02** memasang guard interim. Detail masalah: [[02-DESIGN#2.4 Bahaya laten yang sudah ada hari ini]].

### Q-18

**Kardinalitas site ↔ company.** — **Satu site = satu company** (Sayyid, 2026-10-21). → `companies.onebox_site_id` unik.

### Q-19

**Selain aktivasi paket VoC, ada langkah Registration lain untuk site baru?**

- **Konteks:** notulen Pak Agung §3.2 menyebut menu Pengaturan → Registration (4 sub-menu) untuk site existing. Dengan model "aktifkan paket VoC → semua otomatis", mungkin sudah tidak relevan.
- **Jawaban:** _belum_

### Q-20

**Site uji tenant kedua.** — **Site 177** (testing) di dev, bersama **site 169** (utama, sudah dipakai sejak awal). Five Coffee di spec hanya contoh.

### Q-21

**`company_id` Hermina per environment untuk backfill `onebox_site_id`?**

- Migration MT-10 mengisi dari `worklist_sync_states.site_id`, tetap perlu dicek data nyata per env (dev/staging/prod), termasuk company sisa uji/demo.
- **Jawaban:** _belum_

### Q-22

**Alert per tenant?**

- **Usulan awal:** refresh worklist tenant gagal N kali berturut-turut · umur cache worklist > ambang · kedalaman antrean per tenant · pemakaian Apify per tenant melewati batas · tenant dinonaktifkan · provisioning gagal.
- **Jawaban:** _belum_ (kanal alert belum ada)

### Q-23

**Ratifikasi.** ADR-0001–0003 masih "belum diratifikasi Pak Agung". Usulan: ADR-0006 (model multi-tenant ini) dibawa satu paket. **Jawaban:** _belum_

### Q-24

**Uji dua tenant di mana?** — Dev environment: site 169 dan 177 sudah ada. Laptop cadangan sedang menginstal OneBox.

### Q-25

**"Proxy check" maksudnya apa?**

- **Konteks:** Sayyid menyebut Q-01 "lebih condong ke proxy check". Kemungkinan tafsiran: (a) crawler mengecek ke OneBox setiap kali akan bekerja; (b) OneBox jadi perantara (proxy) — semua perintah dan data ke crawler lewat OneBox; (c) hal lain.
- Opsi D yang dipilih (OneBox push semua, crawler tidak memanggil OneBox) sama dengan tafsiran (b). Bila itu maksudnya, pertanyaan ini bisa ditutup.
- **Jawaban:** _belum_

### Q-26

**Bobot round robin: sumber, rumus, default?**

- **Pilihan sumber bobot:** tier paket VoC · jumlah lokasi aktif · diatur manual di Setup Parameter OneBox · kombinasi.
- **Pertanyaan lanjutan:** perlukah **batas konkurensi per tenant** (mis. maks 2 job berjalan per tenant) supaya backfill satu tenant besar tidak mengambil semua worker? Perlukah job `regular_delta` didahulukan dari `initial_backfill`?
- **Usulan default:** bobot `1` untuk semua tenant sampai ada aturan bisnis; batas konkurensi per tenant = `ceil(jumlah_worker / 2)`.
- **Jawaban:** _belum_

### Q-27

**Apakah akun layanan crawler otomatis menjadi anggota site saat paket VoC aktif?** — **Di-drop (2026-10-21).** Dengan opsi D crawler tidak login ke OneBox, jadi keanggotaan site tidak dibutuhkan. Lihat [[#Q-03]].

### Q-28

**Siapa yang boleh melihat & me-regenerate token di Setup Parameter?**

- **Usulan:** token ditampilkan **sekali saat dibuat**, selanjutnya hanya tampil **ter-mask** (`vocsk_…a1b2`) + status (aktif, terakhir dipakai). Tombol **Regenerate** memakai rotasi dengan masa tumpang tindih (fitur `rotate --overlap-hours` sudah ada di crawler). Hanya admin OneBox yang boleh melihat; admin client cukup melihat status koneksi, karena token ini kredensial antar-sistem, bukan untuk dipakai manusia.
- **Jawaban:** _menunggu konfirmasi usulan_

### Q-29

**Kalau crawler mati/lambat saat OneBox mengirim provisioning, push worklist, atau deaktivasi?**

- **Usulan:** aksi admin di OneBox tetap sukses seketika; panggilan ke crawler masuk **queue OneBox** dengan retry + exponential backoff; Setup Parameter menampilkan status per tenant: `menunggu crawler` / `tersinkron (versi N)` / `gagal — mencoba lagi` + pesan error terakhir.
- Semua endpoint crawler yang dipanggil **idempoten**: provisioning per `site_id`, `PUT /worklist` per `snapshot_version`, `PATCH active` per nilai.
- Dengan opsi D ini satu-satunya jalur deaktivasi, jadi retry **tidak boleh menyerah diam-diam** — setelah N kali gagal harus terlihat di Setup Parameter / alert ([[#Q-22]]).
- **Jawaban:** _menunggu konfirmasi usulan_

### Q-30

**Setting per tenant (kategori ML, prompt) — disimpan di mana & dikirim lewat apa?**

- **Konteks:** Sayyid: ke depan tiap tenant punya setting sendiri karena akan ada machine learning dengan penyesuaian kategori. Worklist hari ini sudah membawa konfigurasi AI per target (test `test_worklist_stores_the_ai_config_onebox_chose`).
- **Pilihan:** setting tenant dikirim lewat payload provisioning (berubah jarang) · lewat worklist (selalu segar) · endpoint setting terpisah.
- **Jawaban:** _belum_ (bukan penghambat fase awal)

### Q-31

**Apa saja yang sudah diimplementasi atau diubah di OneBox untuk multisite?**

- **Konteks:** Sayyid: sebagian sudah diimplementasikan dan diubah. Dokumen ini disusun tanpa membaca kode OneBox (belum ada di laptop cadangan), jadi semua klaim sisi OneBox berstatus `[asumsi]` sampai dicek.
- **Yang perlu diinventaris:** aktivasi paket VoC → Connection otomatis? · field token di `Connection.Options`? · gerbang paket di `VocWorklist`? · halaman Setup Parameter? · keanggotaan akun layanan ([[#Q-27]]).
- **Jawaban:** _belum_ — dikerjakan setelah repo OneBox ter-clone.

### Q-32

**Seandal apa mekanisme queue di OneBox untuk panggilan ke crawler?**

- **Konteks:** dengan opsi D, OneBox memikul retry untuk provisioning, push worklist, dan deaktivasi. Dibutuhkan: job tahan restart, retry + backoff, debounce per site, status yang bisa ditampilkan, dan tidak ada dua push untuk site yang sama berjalan bersamaan.
- **Yang perlu dicek di kode OneBox:** mekanisme queue/worker yang sudah ada (worker Swoole? tabel job? task terjadwal seperti `SonarTask`), cara retry, dan cara memantau kegagalan.
- **Bila ternyata rapuh:** pertimbangkan opsi C (crawler tetap pull dengan kredensial mesin) supaya retry tetap di antrean durable crawler yang sudah teruji.
- **Jawaban:** _belum_ — bagian dari inventaris [[#Q-31]].

### Q-33

**`snapshot_version` diambil dari mana?**

- **Usulan:** counter integer per site di OneBox yang naik setiap kali cabang/kompetitor site itu berubah. Lebih aman daripada timestamp (jam server bisa berbeda; dua perubahan bisa di detik yang sama).
- **Alternatif:** `generated_at` + hash isi snapshot (tanpa kolom baru; hash sama → crawler balas `unchanged`).
- **Aturan crawler:** versi ≤ versi tersimpan → `200 {"status": "stale"}` tanpa perubahan.
- **Jawaban:** _menunggu konfirmasi usulan_

