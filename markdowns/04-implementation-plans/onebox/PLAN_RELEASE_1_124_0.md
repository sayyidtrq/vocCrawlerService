# Roadmap Rilis VoC — 1.123.0, 1.124.0, 1.125.0

Pembagian tiket per rilis beserta keadaan branch-nya di repo. Semua status dibaca langsung dari `git` pada 3 September 2026 terhadap `origin/release/1.123.0`.

---

## Aturan branch

> **`feature/voc` adalah branch DEV.** Ia dipakai untuk menampilkan VoC di server dev, dan **tidak pernah di-merge ke release manapun.**
>
> Yang naik ke release adalah **branch feature per tiket**, sesuai antrean rilisnya.

### Konsekuensi yang harus disadari

Branch feature dicabang **dari `feature/voc`**. Artinya sebuah branch feature ikut membawa **seluruh isi `feature/voc` pada saat ia dicabang** — termasuk pekerjaan tiket lain yang sudah lebih dulu masuk ke sana.

Begitu satu branch feature di-merge ke release, **semua yang menempel padanya ikut tayang**, tanpa PR sendiri dan tanpa muncul di antrean rilis.

Itu bukan teori. Di 1.123.0 hal ini terjadi pada empat tiket sekaligus.

---

## 1.123.0 — sudah tayang

### Sesuai rencana

| Kategori | Tiket | Branch | Jalur |
| --- | --- | --- | --- |
| Transaksi | 3387 Review Manage Actions | `DNGO19-3387_VOC-Review-Manage-Actions` | PR #72 |
| Output | 3392 Generate Reports | `DNGO19-3392_VOC-Generate-Reports` | terbawa |
| Setting | 3420 Fetch Jobs | `DNGO19-3420_VOC-Fetch-Jobs-Crawl` | terbawa |
| Setting | 3385 Master Data Lokasi | `DNGO19-3385_VOC-Master-Data-Locations` | PR #73 |
| Setting | 3386 Master Data Kompetitor | `DNGO19-3386_VOC-Master-Data-Competitors` | terbawa |

### ⚠️ IKUT TAYANG DI LUAR RENCANA

Empat tiket berikut **direncanakan untuk 1.124 dan 1.125, tetapi kodenya sudah ada di `release/1.123.0`**. Semuanya nol commit unik — tidak ada lagi yang tersisa untuk di-merge.

| Tiket | Direncanakan | Branch | Status |
| --- | --- | --- | --- |
| **3390** Crawl Scheduler | 1.124 Setting | `DNGO19-3390_VOC-Crawl-Scheduler` | **sudah di 1.123** |
| **3396** Fetch Job Kompetitor | 1.124 Setting | `DNGO19-3396_VOC-Competitor-Analysis` | **sudah di 1.123** |
| **3471** Dashboard Profile Per Daerah | 1.125 Output | `DNGO19-3471_VOC-Dashboard-Per-Daerah` | **sudah di 1.123** |
| **3347** Dashboard Omnichannel | 1.125 Output | `DNGO19-3347_Dashboard-Voice-Of-Customer` | **sudah di 1.123** |

Ditambah `fix/DNGO19-3390_VOC-Migrasi-Kompetitor-Enabled` yang juga sudah tayang.

**Yang perlu diputuskan:** apakah keempatnya dianggap selesai di 1.123.0 dan dicoret dari antrean berikutnya, atau tetap tercatat di 1.124/1.125 sebagai "sudah tayang lebih awal". Yang jelas, **tidak ada pekerjaan merge tersisa** untuk keempatnya — PR-nya tidak bisa dibuat karena GitHub akan bilang *"there isn't anything to compare"*.

**Catatan untuk 3471:** tiket ini di rencana muncul dua kali — sebagai "Dashboard Profile Per Daerah/Lokasi" dan "Workspace Branch Manager", dengan tautan yang sama. Perlu dipastikan apakah keduanya memang satu tiket.

---

## 1.124.0

### Punya branch dan masih ada kerjaan

| Kategori | Tiket | Branch | Commit unik |
| --- | --- | --- | ---: |
| Transaksi | 3388 Analisis AI | `DNGO19-3388_VOC-AI-Analysis-Setup` | 6 |
| Transaksi | 3389 AI Insights | `DNGO19-3389_VOC-AI-Insights` | 27 |
| Transaksi | 3517 Escalate Review to WhatsApp | `DNGO19-3517_VOC-Review-To-Whatsapp-Escalation` | 57 |
| Transaksi | 3509 Manual Classification | `DNGO19-3509_VOC-Manual-Classification` | 56 |
| Transaksi | 3515 Ticket Routing | `DNGO19-3515_VOC-Ticket-Routing` | 73 |
| Transaksi | 3523 Review Manage Actions Improvement | `DNGO19-3523_VOC-Review-Manage-Action-Improvement` | 53 |
| Setting | 3391 Setup Parameter + Paket & Kuota | `DNGO19-3391_VOC-Config-Setup` | 6 |
| Setting | 3507 Rating Target Threshold | `DNGO19-3507_VOC-Rating-Target-Threshold` | 63 |
| Setting | 3513 Region Master Data | `DNGO19-3513_VOC-Region-Master-Data` | 73 |
| Output | Regional Comparison | `DNGO19-3512_VOC-Regional-Comparison` | 83 |

### Belum punya branch sama sekali

| Tiket | Catatan |
| --- | --- |
| **3508** Crawl Instrumentation | tidak ada branch `feature/*3508*` di remote |
| **3510** Review Status Lifecycle | tidak ada branch feature; yang ada hanya `hotfix/1.117.4_SNGOC-3510`, tiket berbeda |
| **Trend dimension** | tidak ada nomor tiket maupun branch |

Ketiganya perlu dibuatkan branch, atau dikonfirmasi bahwa pekerjaannya belum dimulai.

### Catatan tautan di rencana

- **Escalate Review to WhatsApp** tertaut ke DNGO19-3389, sama dengan AI Insights. Branch yang sebenarnya `DNGO19-3517`.
- **Setup Parameter VoC** dan **Paket & Kuota VoC** tertaut ke DNGO19-3391 yang sama. Kalau memang dua tiket berbeda, salah satunya perlu nomor sendiri.

---

## 1.125.0

| Kategori | Tiket | Branch | Commit unik |
| --- | --- | --- | ---: |
| Transaksi | 3407 Enhance AI Analysis | `DNGO19-3407_VOC-Enhance-AI-Analysis` | 26 |
| Transaksi | 3529 Fetch Review Improvement | `DNGO19-3529_Fetch-Review-Improvement` | 84 |
| Output | 3471 Dashboard Profile Per Daerah | — | **sudah tayang di 1.123** |
| Output | 3347 Dashboard Omnichannel | — | **sudah tayang di 1.123** |
| Output | 3471 Workspace Branch Manager | — | tautan sama dengan Dashboard Profile |

Setelah dikurangi yang sudah tayang, **1.125.0 berisi dua tiket: 3407 dan 3529.**

---

## Branch punya kerjaan tapi tidak ada di rencana

| Branch | Commit unik | Perlu diputuskan |
| --- | ---: | --- |
| `fix/DNGO19-3513_wilayah-500-locations` | 74 | digabung ke 3513 atau berdiri sendiri? |
| `fix/VOC-Benefit-Tabrakan-Versi` | 1 | masih relevan? |

**Diperbarui 4 September 2026:** 3515 dan 3523 sudah masuk 1.124, 3529 masuk 1.125. Sisa yang belum punya slot hanya dua branch `fix/` di atas.

---

## Branch kembar yang perlu dibereskan

| Tiket | Branch | Commit unik | Tindakan |
| --- | --- | ---: | --- |
| 3509 | `DNG019-3509_...` — angka **nol** | 8 | **hapus** |
| 3509 | `DNGO19-3509_...` — huruf **O** | 56 | **pakai ini** |
| 3388 | `DNGO19-3388_AI-Analysis-Setup` | 1 | pastikan mana yang dipakai |
| 3388 | `DNGO19-3388_VOC-AI-Analysis-Setup` | 6 | kemungkinan ini |

Branch 3509 yang benar sudah dikonfirmasi: **yang 56 commit**.

---

## Urutan kerja per branch

Untuk **tiap** branch yang masuk rilis, langkahnya tetap sama:

- [ ] **1. Periksa apakah masih ada kerjaan.** Nol commit unik berarti sudah tayang — tutup PR-nya, jangan dipaksa merge.
      ```bash
      git rev-list --count origin/release/1.124.0..<branch>
      ```

- [ ] **2. Buang folder `_1_123_0` yang terbawa.** Tiap branch VoC yang tersisa membawa 26–34 folder migrasi lama yang semuanya sudah tayang di 1.123.0.

- [ ] **3. Migrasi baru masuk satu folder `_1_124_0`,** dibuat lewat `./migration.sh <env> generate <Tabel> 1_124_0`. Satu tabel satu berkas.

- [ ] **4. Keluarkan yang tidak layak rilis:** `.env*` (kecuali variabel fitur yang memang dibutuhkan), `app/config/local.php`, `app/config/development.php`, `build.yml`, `scriptdb/`, `docs/`.

- [ ] **5. Jangan merge release ke dalam branch feature.** Kalau perlu menyusul, salin kode ke branch baru di atas release.

- [ ] **6. Uji di lokal** — jalankan migrasinya lawan DB, bukan cuma `php -l`.

- [ ] **7. Petakan bersarangnya sebelum menetapkan urutan merge.**
      ```bash
      git merge-base --is-ancestor <branch-A> <branch-B> && echo "A ADA DI DALAM B"
      ```
      Yang lebih tua merge duluan. Kalau terbalik, yang tertinggal wajib di-rebase, dan hasil auto-merge-nya **wajib dibaca isinya** — di 1.123.0 auto-merge yang "bersih" menduplikasi handler dan memundurkan kode tanpa konflik.

---

## Risiko putaran ini

| Risiko | Kenapa | Penanganan |
| --- | --- | --- |
| Tiket tayang tanpa direncanakan | branch dicabang dari `feature/voc` yang sudah memuat tiket lain | periksa commit unik tiap branch **sebelum** menyusun antrean |
| 14 branch × 26–34 folder migrasi lama | dicabang sebelum konsolidasi 1.123.0 | buang folder `_1_123_0` sebagai langkah baku |
| Menu ter-wipe di dev | migrasi Menu membangun ulang, bukan menambal | ikuti `05-runbooks/VOC_MIGRASI_1123_DI_DEV.md` |
| Branch bersarang | semua dari `feature/voc` | petakan ancestor sebelum menetapkan urutan |
| Migrasi ditambahkan ke folder `_1_124_0` yang sudah jalan di dev | `phalcon_migrations` mencatat nama folder | jangan jalankan migrasi 1.124 di dev sampai isinya final |

---

## Yang masih perlu diputuskan

1. Empat tiket yang sudah tayang lebih awal (3390, 3396, 3471, 3347) — dicoret dari antrean, atau tetap tercatat?
2. Slot rilis untuk dua branch `fix/` (3513-wilayah-500 dan VOC-Benefit-Tabrakan-Versi).
3. Branch untuk 3508, 3510, dan "Trend dimension" — belum ada.
4. Tautan ganda: Escalate WhatsApp (3389 vs 3517), Setup Parameter vs Paket & Kuota (3391), Dashboard Profile vs Workspace Branch Manager (3471).
5. Kapan dev boleh menjalankan migrasi 1.124 — menentukan apakah jebakan folder-sudah-tercatat menggigit.

---

## Utang dari 1.123.0

- [ ] Tandai migrasi `1786200000000000_1_123_0` di dev — `05-runbooks/VOC_MIGRASI_1123_DI_DEV.md`
- [ ] Sampaikan kebocoran password `migrate.php` ke tim — `06-troubleshooting/incidents/MIGRATE_PHP_MENCETAK_PASSWORD_DB.md`
- [ ] Jalankan migrasi 3513 (`VocWilayah`) dan 3529 (kolom rating Google) di dev
- [ ] Tutup PR yang sudah tidak punya isi: 3392, 3420, dan keempat tiket yang tayang lebih awal
- [ ] Hapus branch kembar `DNG019-3509`
- [ ] Rotasi API key Google Maps yang ter-hardcode di `dashboard.volt`
