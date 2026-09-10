# Meeting Notes — Sinkronisasi VoC × OneBox dengan Pak Agung

> **Sumber:** transkrip notulen mentah (`Notul meet 1.md`), disintesis ulang di sini secara tematik (bukan kronologis) untuk kejelasan.
> **Tanggal meeting:** *(isi tanggal pasti — tidak tercantum eksplisit di notulen; berdasarkan konteks siklus sprint yang disebut, sekitar akhir Juli 2026, sebelum siklus 27 Jul–7 Agu dimulai)*
> **Peserta:** Pak Agung (+ kemungkinan Bang Sam disebut sekali), tim VoC (Sayyid dkk.)
> **Status dokumen:** Ringkasan & sintesis — bagian yang ambigu/putus di rekaman asli **ditandai eksplisit**, tidak diisi dengan tebakan.
> **Dampak ke ADR existing:** dokumen ini **mengonfirmasi ADR-0001**, **merevisi framing ADR-0002 dan ADR-0004** — lihat §7.

---

## Ringkasan Eksekutif (8 Poin)

1. Arsitektur multi-tenant: **1 deployment crawler**, bukan 1 per klien — loop berdasarkan `site_id` + `connection_id` aktif.
2. **Master data 100% di OneBox** — konfirmasi langsung, memvalidasi ADR-0001.
3. **AI tetap di sisi Crawler/VoC**, model dipilih bebas oleh scraper — merevisi framing ADR-0002.
4. **Database: opsional Postgres/MySQL** — prioritas sebenarnya server DB dedicated (bukan migrasi engine) — merevisi ADR-0004.
5. **Struktur menu VoC final**: header menu + 3 grup (Transaksi / Output / Setting).
6. **Proses kerja formal wajib**: Jira 1:1 per screen, branch 1:1 per tiket, alur testing 5 tahap.
7. **Tim VoC = 1 scrum team sendiri**, ada scrum-of-scrum, ikut siklus sprint 27 Jul–7/8 Agu.
8. **5 action item segera** + rencana minggu depan: simulasi crawling & ulasan masuk.

---

## 1. Status Saat Ini (dilaporkan tim ke Agung)

| Area | Status |
|---|---|
| Dashboard | Mock data |
| Ulasan (Reviews) | Backend masih ada masalah di sistem crawling |
| Frontend | Fokus: dashboard |
| Backend | Fokus: key process — mengambil review di Fetch Jobs, mengelola review masuk di Ulasan (**ada kendala**) |
| Plan | Minggu depan, key process ditargetkan bisa ditampilkan & di-showcase dengan baik |

---

## 2. Pertanyaan yang Diajukan Tim (Konfirmasi + Testing)

Lima hal yang dikonfirmasi ke Agung:

1. **Multi-tenant** — apakah crawler system perlu 1 deployment per penyewa, atau 1 deployment melayani daftar penyewa (dengan konsep "OneBox tenant" ber-`company_id`/`site_id`)?
2. **Desain integrasi master data** — arsitektur saat ini menaruh semua setup (lokasi, kompetitor, config) di OneBox. Bagaimana alur onboarding company baru? Apakah VoC otomatis terintegrasi, atau tetap terpisah?
3. **Posisi AI** — saat ini AI ada di sisi Crawler System (pakai local LLM). Sedang dikaji plus-minus: AI di Crawler vs Crawler murni untuk scraping (Selenium) lalu data diserahkan ke AI di platform OneBox.
4. **Database VoC** — dipakai untuk menyimpan raw review hasil scrape Crawler.
5. **Minta bantuan QC + testing** dari tim OneBox.

---

## 3. Jawaban & Keputusan per Topik

### 3.1 Arsitektur Multi-Tenant — Konfirmasi: 1 Deployment

**Jawaban Agung (pola existing OneBox):**
Crawling yang sudah berjalan di OneBox itu crawling **ke service**, bukan langsung ke AI/Google. Satu media crawling dicatat sebagai 1 media, media punya beberapa provider (a, b, c). Pola yang dipakai: **cukup 1 service** — service itu loop berdasarkan `site_id` dan `provider_id` yang **aktif**. Kalau ada beberapa site aktif untuk 1 media, tiap site punya `connection_id` yang mengarah ke provider mana. `connection_id` + provider = 1 metode crawling; di dalam 1 provider itu terjadi looping. **Secara desain, cukup 1** — sisanya deteksi otomatis via loop `site_id`/`provider_id` aktif.

**Follow-up tim (soal beban konkurensi):** kalau Hermina, Kopi Kenangan, Mitra crawling bersamaan (misal 5000 review masing-masing), apakah sistem bisa handle secara optimal?

**Jawaban:** Bisa. Secara service bisa ada beberapa di OneBox, loop berdasarkan `provider_id`, atau dari sisi engine crawler jalan paralel (produksi sekarang **4 worker aktif**, meski desain mendukung sampai 8). **Locking terjadi per sesi/connection**: kalau Hermina masih diproses (misal sesi 5000 crawl), trigger baru untuk Hermina akan **antre** menunggu lock selesai. Tapi company **baru** (misal "KS") punya `connection_id` berbeda → lock berbeda → **bisa diproses paralel**, tidak menunggu Hermina selesai. Kesimpulan: **konkurensi dimungkinkan berdasarkan `connection_id`** — tiap company dapat `connection_id` sendiri, provider-nya bisa sama; `connection_id` yang jadi pembeda.

> ⚠️ **Catatan penting — belum sepenuhnya selesai:** pola di atas menjelaskan cara kerja crawler **existing** OneBox (analog dengan `SonarTask`/`GbusinessProvider` yang sudah diverifikasi sebelumnya di codebase). Ini **mendukung arah** `SPEC-multi-tenant-opsi-c.md` (1 deployment untuk semua tenant), tapi **mekanisme detail belum tentu identik** dengan desain "Crawler pull daftar tenant lewat `/api/VocTenants`" yang diusulkan di spec itu. Tim sendiri mengakui di notulen: *"belum kegambar saat konfigurasi site id dan connection id dalam VoC, lalu workflow VoC apabila dalam 1 schedule yang sama..."* — **ini item follow-up teknis yang masih terbuka**, bukan keputusan final yang sudah dieksekusi.

### 3.2 Onboarding Company Baru & Master Data

**Konfirmasi Agung:** master data (lokasi, kompetitor, config, setup) semuanya di OneBox — **sesuai arah yang sudah diputuskan tim** (ADR-0001).

**Detail onboarding site baru:**
- Ada fitur **registrasi** yang sudah dibuat tapi **belum di-publish**.
- Untuk site benar-benar baru: dibuat di tabel `Site` → **config lokal harus diatur dulu** sebelum bisa dipakai → setelah itu, saat login sudah bisa setup data awal (user, dll).
- Untuk site **existing** (contoh: site 169): setup ada di menu **Pengaturan → Registration**, ada **4 sub-menu** yang perlu dilengkapi (isi spesifik 4 menu ini **tidak disebutkan detail** di notulen — perlu dieksplorasi langsung di UI).

**Follow-up tim (soal parameter VoC):** parameter seperti "crawler review by default on VoC", "AI analysis", "competitor flag" (untuk komparasi) — sebaiknya di-setting di VoC sendiri, atau ikut parameter yang sudah ada di OneBox?

→ **Jawabannya bercampur dengan diskusi struktur menu** — lihat §3.3 di bawah, karena Agung menjawabnya lewat penataan ulang navigasi menu.

### 3.3 Struktur Menu VoC — KEPUTUSAN FINAL

Ini bagian paling konkret dan **wajib diimplementasikan** — mengganti struktur menu flat yang sudah di-seed sebelumnya.

**Keputusan:** VoC menjadi **header menu** tersendiri (bukan submenu Mediamonitoring), sejajar level dengan "Semua Sumber", "Pesan Keluar", dll di sidebar. Di dalamnya dikelompokkan menjadi **3 grup fungsional**:

| Grup | Sub-menu | Penjelasan |
|---|---|---|
| **Transaksi** | Ulasan | Raw review yang baru masuk dari Fetch Jobs, **belum** dianalisis AI |
| | Analisis | **Transaction process untuk AI** — setup/trigger sebelum hasil ada (bukan hasil itu sendiri) |
| | Insight | Hasil analisis AI yang sudah selesai — user melihat output AI di sini |
| **Output** | Dashboard | Chart/grafik — rename dari "Dashboard" jadi lebih spesifik, mis. "Dashboard Google Review" atau "Google Review". Bisa ada beberapa: dashboard Google Review, dashboard Omnichannel |
| | Report | Export ke PDF/CSV; nama menu disesuaikan judul laporan stakeholder |
| **Setting** | Setup Parameter | Konfigurasi Fetch Jobs (trigger crawling) dan setting lain |
| | Master Data | Lokasi, Kompetitor |

**Prinsip pembagian yang dipakai Agung (kutipan disarikan):**
> *"Harus dikelompokkan mana yang jadi setup, transaksi, output (baik itu dashboard atau report), setting parameter, master data."*

**Perbedaan istilah penting** yang diklarifikasi Agung:
- **Analisis** ≠ **Insight**. Analisis = proses/setup SEBELUM ada hasil (transaction process untuk AI). Insight = hasil yang sudah jadi, ditampilkan ke user.
- **Ulasan** = data mentah, langsung dari Fetch Jobs (hasil scraping), **belum** melalui AI.
- **Kompetitor** dikategorikan sebagai bagian dari **Output** (karena fungsinya bikin komparasi), bukan transaksi.

> ⚠️ **Dampak teknis:** seed menu yang sudah ada (`scriptdb/voc/voc_setup_all.sql` — 9 submenu flat: `voc_dashboard`, `voc_reviews`, `voc_locations`, `voc_competitors`, `voc_fetchjobs`, `voc_analysis`, `voc_insights`, `voc_reports`, `voc_settings`, semua level 2 di bawah 1 parent `voc`) **perlu direstrukturisasi** menjadi hierarki 3-level ini (Header VoC → Grup → Sub-menu). Ini **item kerja baru** yang belum ada di `VOC_DEV_TASKLIST.md` (kandidat masuk M8, terkait M8-07).

### 3.4 Posisi AI — Rekomendasi: Lanjutkan yang Sekarang

**Konteks pertanyaan:** AI bisa di-setup dari OneBox, atau tetap pakai service yang ada di VoC sekarang.

**Jawaban Agung:**
> *"Yang sekarang itu sedang diimplementasikan tapi belum selesai, itu di Crawler System (backend FastAPI Python). Modelnya: AI diserahkan ke level scraper — lingkup scraper itu yang menentukan mau akses model AI mana. Untuk VoC ini, struktur sudah di OneBox — kalau ada scraper lain, tinggal masukin ke struktur yang sudah ada, output-nya sama. Secara struktur desain database dan struktur perlu direview lagi dari yang sudah berjalan; sisanya bisa dijadikan general untuk scraper lain."*

**Rekomendasi eksplisit:** **lanjutkan AI di service scraper (Crawler/VoC) yang sekarang berjalan.**

> ⚠️ **Ini merevisi framing ADR-0002.** ADR-0002 sebelumnya menetapkan *"kendali di OneBox, eksekusi di VoC"* — menyiratkan OneBox mengatur parameter AI (model, prompt, threshold). Jawaban Agung lebih longgar: **OneBox mengontrol STRUKTUR/OUTPUT** (supaya scraper lain nanti kompatibel), tapi **pemilihan model AI tetap wewenang scraper/VoC sendiri**, bukan dikendalikan parameter dari OneBox. **ADR-0002 perlu direvisi** untuk mencerminkan nuansa ini — bukan dibatalkan total, tapi bagian "kendali penuh di OneBox" perlu diperlunak jadi "OneBox standarisasi struktur output, VoC bebas menentukan model/eksekusi AI."

### 3.5 Database — Opsional Postgres/MySQL, Prioritas Sebenarnya Hosting

**Follow-up tim:** terkait migrasi, sebaiknya migrasi database lokal dari Postgres ke MySQL?

**Jawaban Agung:**
> *"Kalau mau sendiri (terpisah), bebas mau Postgres atau MySQL. Kalau digabung (ke database OneBox), lanjut pakai MySQL. Jadi itu optional, bebas menyesuaikan preferensi."*

**Follow-up lanjutan:** saat ini masih pakai Supabase (Postgres) versi **gratisan** — tim ingin cari opsi berbayar yang reasonable supaya scraping tidak lambat.

**Jawaban Agung:**
> *"Ini untuk nampung data kan ya? ... Bisa bikin server database sendiri, pakai Postgres. Karena service crawler bikin service sendiri, kalau bisa database di-host di server yang sama supaya tidak keluar [jaringan]."*

**Follow-up:** crawler sekarang langsung di host atau virtualisasi? → **Docker, di server Ciptadra.** Maka service database juga sebaiknya format Docker — **dikonfirmasi bisa.**

**Keputusan Sayyid (dicatat langsung di notulen):** *"Coba dulu Postgres, kalau nggak bisa baru MySQL."*

> ⚠️ **Ini merevisi ADR-0004.** ADR-0004 sebelumnya memutuskan **migrasi proaktif ke MySQL sekarang**, dengan alasan biaya migrasi murah selama data masih berupa cache. Hasil meeting ini: **migrasi engine DB bukan lagi prioritas** — Agung bilang opsional/bebas, dan Sayyid sendiri memilih **bertahan di Postgres dulu**. **Yang justru jadi prioritas nyata: minta server database sendiri** (Postgres, format Docker, host di server Ciptadra yang sama dengan crawler) untuk lepas dari Supabase free tier — ini **beda fokus** dari rencana migrasi engine di ADR-0004. **ADR-0004 perlu ditinjau ulang statusnya** (kemungkinan: superseded/revised — permintaan server dedicated Postgres menggantikan rencana migrasi ke MySQL, minimal untuk saat ini).

### 3.6 Bantuan QC & Proses Testing

**Follow-up tim:** perlu bantuan tim OneBox untuk testing, dan supaya tetap on-track perlu ada PM.

**Jawaban Agung — tahapan testing di OneBox:**

1. **Developer testing** — environment dev sudah disiapkan. Development cukup di local, tapi butuh environment lain untuk testing sampai semua fungsi dalam scope selesai.
2. Standarisasi task management pakai **Jira** — harus aktif, update berkala.
3. Alur per tiket Jira (1 scope):
   - **Perencanaan & desain** — spesifikasi teknis, struktur data baru
   - **Use case / skenario testing**
   - **Mockup**
   - Koordinasi dengan mentor: cukup atau perlu penyesuaian desain
   - Kalau cukup → masuk status **"in development"**
4. **Deploy ke server environment (dev)** — kalau ada temuan, diperbaiki di local, naik lagi ke dev.
5. Setelah server dev selesai → update Jira ke **"resource developer"** → masuk antrian jadwal rilis berikutnya → **testing oleh tim QC**.

**Alur lengkap (dari local sampai rilis):**
```
local (OK) → dev → update Jira → versi release → versi staging
  (developer merge ke release) → development testing di staging
  → update status internal → update tim QC
  → (kalau ada temuan) balik ke development → fix → merge lagi ke staging
```

**Aturan branch:** commit **tidak boleh** di branch yang salah — penting untuk menentukan lingkup/scope kerja dengan benar.

**Saran struktur Jira:** buat sesuai menu — **1 screen = 1 tiket Jira**. Saat ini ada **6 menu** → 6 tiket. Antrian kerja mengikuti **FIFO + prioritas** — "harap bersabar."

**Follow-up:** perlu request tiket Jira baru untuk tiap screen?

**Jawaban:** Boleh minta, atau bikin sendiri kalau sudah punya login (project development), format ikuti yang sudah ada. **Tipe tiket:**
- Screen **baru** → tipe **Development**
- Screen sudah ada, mau **nambah opsi/fitur baru** → tipe **New Feature**
- Screen & fitur sudah ada, mau **ditingkatkan** → tipe **Improvement**

### 3.7 Struktur Tim & Sprint

*(Bagian ini sebagian tidak tertangkap jelas di rekaman — notulen asli menyebut "ga gue catet ga kedengeran". Disajikan apa adanya.)*

- Ada batas maksimal ukuran tim per sprint. Tim VoC bisa disebut **1 scrum team sendiri**, dengan sprint sendiri.
- Kalau ada sprint planning/review, **Pak Agung atau Bang Sam bisa join** untuk mentoring.
- Ada **"scrum of scrum"** — alignment antar tim scrum diwakili masing-masing PMO, supaya tidak ada konflik jadwal ketika beberapa tim jalan di sprint yang sama.
- **Timeline:** ikuti siklus yang sedang berjalan, mulai **27 Juli – 7/8 Agustus**. Sprint review kemungkinan bukan tanggal 7, tapi **Senin setelahnya**.

### 3.8 Pemisahan (Item Belum Diputuskan)

Notulen mencatat satu baris singkat: *"Pemisahan akan di[putusk]an antara digabung atau dipisah."* — **konteks tidak jelas** (kemungkinan lanjutan diskusi database §3.5, atau bisa juga soal repo/deployment). **Ditandai sebagai item terbuka**, perlu diklarifikasi di sesi berikutnya, jangan diasumsikan.

---

## 4. Action Items Segera

Daftar eksplisit dari Agung (*"Action terdekat"*):

| # | Action | Detail |
|---|---|---|
| 1 | **Jira ditertibkan** | Buat/rapikan tiket sesuai 6 menu (§3.6) |
| 2 | **Navigasi menu disesuaikan** | Implementasikan struktur 3 grup (Transaksi/Output/Setting) — §3.3 |
| 3 | **Struktur data Connection/Provider (Sayyid) disesuaikan** | *"yang belum sesuai"* — bagian spesifiknya tidak dirinci di notulen, perlu klarifikasi langsung ke Agung soal bagian mana yang dimaksud |
| 4 | **Database: coba Postgres dulu** | Kalau gagal, baru pindah ke MySQL (§3.5) |
| 5 | **Request server database dedicated** | Postgres, format Docker, host di server Ciptadra (bukan Supabase free tier) |

**Prioritas branch (penutup dari Agung):** branch harus disesuaikan dengan Jira, per-screen. Contoh: fitur Location = branch sendiri. Kalau sudah kerja di 1 branch, tidak masalah — checkout dulu dari `develop`, lalu checkout branch baru dengan ID tiket Jira terkait.

## 5. Plan Minggu Depan

**Simulasi crawling dan ulasan yang masuk** — ditampilkan/showcase dengan baik ke stakeholder.

---

## 6. Item Terbuka / Butuh Klarifikasi Lanjutan

Ditandai eksplisit supaya tidak hilang:

1. **Mekanisme detail multi-tenant** (§3.1) — pola looping `site_id`/`connection_id` dikonfirmasi arahnya, tapi implementasi konkret (bagaimana VoC tahu tenant mana yang aktif, workflow schedule bersamaan) **belum digambar** — perlu sesi teknis terpisah, kemungkinan revisi `SPEC-multi-tenant-opsi-c.md`.
2. **Isi 4 sub-menu di Pengaturan → Registration** (§3.2) — perlu dieksplorasi langsung di UI, tidak dirinci di notulen.
3. **Bagian mana dari struktur data Connection/Provider Sayyid yang "belum sesuai"** (§4, action #3) — perlu klarifikasi spesifik ke Agung.
4. **Konteks baris "Pemisahan digabung atau dipisah"** (§3.8) — ambigu, perlu klarifikasi.
5. **Bagian sprint/scrum yang terputus di rekaman** (§3.7) — kemungkinan ada detail penting yang tidak tertangkap.

---

## 7. Dampak ke Dokumen Existing (Rangkuman)

| Dokumen | Dampak dari meeting ini |
|---|---|
| **ADR-0001** (Ownership Inversion) | ✅ **Dikonfirmasi langsung** oleh Agung — master data 100% di OneBox. Status ratifikasi bisa di-upgrade dari "internal dev" menjadi "dikonfirmasi lead" untuk poin kepemilikan master data (belum ratifikasi formal tertulis, tapi sudah ada persetujuan verbal eksplisit). |
| **ADR-0002** (AI Execution Split) | ⚠️ **Perlu direvisi** — framing "kendali AI di OneBox" terlalu kuat; realitanya OneBox hanya standarisasi struktur/output, pemilihan model AI tetap di scraper/VoC. |
| **ADR-0003** (Pull Queue) | 🟡 Didukung secara analogi (pola Connection/Provider existing), tapi mekanisme spesifik multi-tenant belum sepenuhnya sinkron — lihat item terbuka #1. |
| **ADR-0004** (DB Postgres→MySQL) | ⚠️ **Perlu ditinjau ulang statusnya** — migrasi engine bukan lagi prioritas; fokus bergeser ke minta server Postgres dedicated. Rekomendasikan status baru: superseded/revised sebagian. |
| **SPEC-multi-tenant-opsi-c.md** | 🟡 Arah besar (1 deployment) didukung, detail mekanisme perlu direvisi sesuai temuan §3.1. |
| **`scriptdb/voc/voc_setup_all.sql`** (seed menu) | ❌ **Perlu direstrukturisasi total** mengikuti hierarki 3 grup baru (§3.3) — ini bukan revisi kecil, tapi perubahan struktur menu. |
| **`VOC_DEV_TASKLIST.md`** | Perlu task baru untuk: (a) restrukturisasi menu (kandidat M8), (b) request server DB dedicated (kandidat M0/ops), (c) revisi mekanisme multi-tenant. |

---

## 8. Rekomendasi Langkah Berikutnya

1. **Buat 6 tiket Jira** sesuai 6 menu (action item #1) — prioritas pertama karena eksplisit diminta Agung.
2. **Update ADR-0002 dan ADR-0004** untuk mencerminkan revisi di §3.4 dan §3.5 — jangan biarkan dokumen keputusan lama menyesatkan kerja berikutnya.
3. **Restrukturisasi seed menu VoC** sesuai §3.3 — dampak besar ke UI, worth dikerjakan lebih awal karena tim frontend sedang aktif di dashboard.
4. **Klarifikasi 5 item terbuka di §6** ke Agung secepatnya — terutama action item #3 (bagian struktur data Connection/Provider yang "belum sesuai") karena itu langsung memblokir kerja Sayyid.
5. **Request server database dedicated** — koordinasi dengan tim infra (Nabil/Ridho, sesuai pola komunikasi sebelumnya).
