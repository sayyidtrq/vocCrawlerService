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
updated: 2026-10-26
owner: Sayyid
open_count: 21
answered_count: 20
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
| [[#Q-13]] | 🟠 | Skala | Berapa tenant aktif & review baru per hari yang ditargetkan? | Product / CEO | MT-40, MT-41 | partial |
| [[#Q-15]] | 🟢 | Integrasi | Revert `13ad618` di staging alasannya sama dengan Q-14? | Sayyid | MT-03 | open |
| [[#Q-19]] | 🟢 | Onboarding | Selain aktivasi paket VoC, ada langkah Registration lain untuk site baru? | Tim OneBox | MT-52 | open |
| [[#Q-21]] | 🟠 | Rollout | `company_id` Hermina per environment (dev/staging/prod) untuk backfill | Ops | MT-10 | open |
| [[#Q-22]] | 🟢 | Observability | Alert apa yang wajib per tenant & lewat kanal apa? | Sayyid / ops | MT-42 | open |
| [[#Q-23]] | 🟠 | Governance | ADR-0006 diratifikasi Pak Agung — kapan & format? | Sayyid | MT-01, E8 | open |
| [[#Q-25]] | 🟠 | Istilah | "Proxy check" maksudnya apa? | Sayyid | MT-01 | open |
| [[#Q-26]] | 🟠 | Round robin | Weight is decided (number from OneBox, Plus = 2). Still open: per-tenant concurrency cap, `regular_delta` before `initial_backfill`. | Sayyid | MT-40 | partial |
| [[#Q-28]] | 🟠 | Keamanan | Token di Setup Parameter: siapa yang boleh lihat & regenerate? | Sayyid / security | MT-31 | proposed |
| [[#Q-29]] | 🟠 | Reliability | Crawler mati saat paket diaktifkan — OneBox retry bagaimana? | Sayyid | MT-30 | proposed |
| [[#Q-30]] | 🟢 | AI/ML | Setting per tenant (kategori ML): disimpan di mana & dikirim lewat apa? | Product / ML | MT-44 | open |
| [[#Q-31]] | 🔴 | Inventaris | Apa saja yang sudah diimplementasi/diubah di OneBox untuk multisite? | Sayyid (lanjutan MT-03) | Fase 3 | partial |
| [[#Q-32]] | 🔴 | Reliability | Outbox/queue OneBox untuk push worklist & provisioning: pakai apa (RabbitMQ, tabel DB)? | Sayyid | MT-33, MT-35 | partial |
| [[#Q-33]] | 🟠 | Kontrak | `snapshot_version`: counter per site di OneBox, atau `generated_at` + hash? | Sayyid | MT-13, MT-32 | proposed |
| [[#Q-34]] | 🟠 | Biaya | Apify account is free now, moving to the $19 plan. Still open: concurrent-run limit and monthly cap on the new plan, alerts. | Sayyid (check Apify account) | MT-40, MT-41 | partial |
| [[#Q-36]] | 🟠 | Kredensial | Token tenant disimpan di level site (Setting) atau disalin ke tiap Connection cabang? | Sayyid | MT-30, MT-31 | proposed |
| [[#Q-37]] | 🟠 | Quota | Apify quota unit is assumed to be reviews per month (volumes given). Still open: what the Plus "AI credit" is. | Sayyid / product | MT-30, MT-41 | partial |
| [[#Q-38]] | 🔴 | Quota | Who enforces the per-tenant quotas, and when? | Sayyid | MT-30, MT-41 | proposed |
| [[#Q-42]] | 🟠 | Pricing | Do competitor targets count toward the 10 purchased locations? They cost Apify like any other target. | COO / product | MT-30, MT-41 | open |
| [[#Q-43]] | 🟠 | Quota | The flat Jev budget ($10 Default) does not scale with locations: a heavy 310-location backfill needs about $18. Proposed: $0.25 per location per month, floor $10. | Sayyid / product | MT-30 | proposed |

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
| [[#Q-11]] | Akun & biaya Apify | **Satu akun Apify milik platform**, anonim bagi tenant; tidak ada akun/rotasi/top-up per tenant. Biaya tetap **dicatat per tenant** (atribusi) untuk harga VoC | Sayyid (chat) | 2026-10-21 |
| [[#Q-07]] | Gerbang paket VoC | Tidak ada lagi panggilan crawler → `VocWorklist`. OneBox hanya provisioning & push untuk site berpaket VoC aktif; paket mati → `PATCH active=false` | Desain opsi D | 2026-10-21 |
| [[#Q-16]] | Pemicu pembaruan worklist | OneBox push snapshot saat paket aktif, cabang/kompetitor berubah, tombol Refresh, dan scheduled push; ketinggalan dicek lewat `GET /tenants/{site_id}` | Desain opsi D | 2026-10-21 |
| [[#Q-35]] | Active VoC package | Active = the tenant has a VoC package, **Default** or **Plus**. Default: review, scrape, sched, comp (not built yet), ticket, AI analysis with Jev. Plus: Default + AI summary with OpenAI + auto reply (soon). Quotas per tenant per month: Default Jev $10 + Apify 100,000; Plus Jev $20 + Apify 500,000 + AI credit. Values may change. | Sayyid (chat) | 2026-10-26 |
| [[#Q-39]] | Does the crawler need the package? | No. OneBox sends a numeric weight (Default 1, Plus 2); the crawler stores a number only | Sayyid (chat) | 2026-10-26 |
| [[#Q-40]] | Jev price per token | Jev 1.13 by TypeSafe: $0.042 per 1M input tokens, $0 output. Kept in OneBox config | Sayyid (chat) | 2026-10-26 |
| [[#Q-41]] | Does the first backfill count against the Apify quota? | Yes, as a separate bucket: backfill cap = max(100,000, 2,500 × locations), lifetime per tenant; operating cap = 2,000 per location per month | Sayyid (chat, measured on HGA) | 2026-10-26 |

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
- **Catatan MT-03:** "paket VoC" di OneBox ternyata enam benefit terpisah → definisi gerbangnya di [[#Q-35]].
- **Konsekuensi:** tidak ada self-healing dari sisi crawler; keandalan deaktivasi bergantung pada retry queue OneBox ([[#Q-29]], [[#Q-32]]).
- **Jebakan OneBox tetap berlaku:** cek paket pakai pemeriksaan murni (`hasBenefit`), bukan `verifyBenefit()` yang menaikkan `SiteBenefit.Quantity` ([[ADR-0001-ownership-inversion]] §Konsekuensi teknis).

### Q-08

**Flag `ai_enable_flag`, `total_enable_review`, `analyze_competitor_flag` di `companies` Crawler?**

- **Jawaban (Sayyid, 2026-10-21):** tidak ada setup di crawler; semuanya dari OneBox.
- **Turunan desain:** nilai dikirim OneBox di payload provisioning / setting tenant; `scripts/manage_company.py` tidak lagi dipakai untuk tenant OneBox.

### Q-09

**Tenant menjadi nonaktif: job dan data diperlakukan bagaimana?**

- **Jawaban (Sayyid, 2026-10-21):** job `pending` dibatalkan, job yang sudah `claimed` dibiarkan selesai, data tidak dihapus.
- **Terjemahan ke kode (2026-10-22):** status job asli adalah `queued` / `retry_wait` / `awaiting_source` (menunggu) dan `running`; tidak ada `pending`/`claimed`. Jadi: yang menunggu → `cancelled`, yang `running` dibiarkan selesai.
- **Turunan desain:** enqueue baru untuk tenant nonaktif ditolak (`TENANT_INACTIVE`); token baca tetap aktif supaya OneBox masih bisa menarik sisa hasil — kecuali OneBox meminta revoke.

### Q-10

**Review di DB Crawler: cache atau data primer, dan berapa lama disimpan?**

- **Jawaban sebagian (Sayyid, 2026-10-21):** untuk sekarang **disimpan saja** (volume akan makin besar, tapi aman). Ujungnya review masuk ke **history di OneBox**, yang DB-nya lebih besar — jadi OneBox yang memegang histori jangka panjang.
- **Sisa:** kapan crawler boleh membersihkan review yang sudah dipastikan masuk OneBox (mis. setelah N hari + konfirmasi ingest)? Belum perlu diputuskan sekarang.

### Q-11

**Akun dan biaya Apify: per tenant atau bersama?**

- **Jawaban (Sayyid, 2026-10-21):** perubahan desain — Apify dipakai lewat **satu akun milik platform**. Tidak perlu rotate akun dan tidak perlu mengisi kredit per tenant. Dari sisi user/tenant, engine-nya **anonim**: tenant tidak tahu ada Apify di belakang dan tidak pernah memberi akun apa pun.
- **Perkiraan angka (Sayyid):** harga VoC ± **Rp200.000 per lokasi**; $20 kredit Apify ≈ ± **100.000 review**.
- **Pricing update (COO via Sayyid, 2026-10-26, latest proposal):** **Rp2,000,000 per month** for a package of **10 locations**, plus **Rp200,000 per month for each additional location**. The Rp200,000-per-location figure is therefore per month, and revenue is `2,000,000 + 200,000 × max(0, locations − 10)` a month. Per 1,000 reviews the variable cost is about $0.24 (Rp 4,235 at 17,500) for Default, so the minimum package keeps variable cost near 1–2% of revenue in steady state.
- **Turunan desain:**
  - `ApifyTokenPool` multi-akun dengan rotasi saat *exhausted* tidak lagi dibutuhkan; cukup `APIFY_API_TOKENS` berisi **satu** token (pool dengan satu token sudah didukung kode, jadi tidak ada perubahan kode wajib). Logika exhausted tidak dihapus — kegagalan akun tetap harus muncul sebagai error jelas, bukan crawl diam-diam berhenti.
  - Tenant tidak punya kredensial atau konfigurasi Apify; tidak ada field Apify di provisioning, Setup Parameter, maupun worklist.
  - **Atribusi per tenant tetap perlu** — bukan untuk menagih akun, melainkan untuk menghitung biaya pokok per tenant/lokasi terhadap harga VoC (MT-41).
- **Risiko baru (karena satu akun dipakai semua tenant):** batas akun (concurrent runs, plafon pengeluaran) bersifat bersama → [[#Q-34]]; berinteraksi dengan batas konkurensi round robin ([[#Q-26]]).

### Q-12

**Antrean worker perlu keadilan per tenant?**

- **Jawaban (Sayyid, 2026-10-21):** ya — **weighted round robin per tenant**, berjalan di crawler; logikanya akan dibuat.
- **Turunan desain:** [[02-DESIGN#3.5 Weighted round robin antar tenant]]. Bobot → [[#Q-26]].

### Q-13

**Target skala?**

- **Jawaban sebagian (Sayyid, 2026-10-21):** tenant = company di OneBox, diasumsikan **enterprise / tersebar luas** (contoh: Pertamina, Hermina, Kopi Kenangan). Perkiraan **maksimum ± 100 lokasi per tenant × ± 1.000 review per lokasi**; rata-rata lebih kecil (± **500 review per lokasi**).
- **Hitungan kasar per tenant terbesar:** backfill awal ± 100.000 review → dengan perkiraan di [[#Q-11]], ± $20 kredit Apify.
- **Sisa:** berapa tenant aktif dalam 6–12 bulan, dan berapa review **baru** per hari per lokasi (menentukan beban delta harian, bukan hanya backfill).
- **Update (Sayyid, 2026-10-26):** initial pull about 100,000 reviews per site; ongoing about **5,000–10,000 reviews per site per month**; about **10–15 sites** (not branches) expected, COO still to confirm. Rough load: 50,000–150,000 new reviews a month across all tenants, plus about 100,000 per newly onboarded site. The backfill, not the delta, is the load that needs the concurrency cap ([[#Q-26]]).

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
- **Dev answered (Sayyid, 2026-10-26, queried `hermina_crawler`):** Hermina is **company 3 (`HGA`)**: site 169, 307 items, last sync 2026-10-22, 26 active tokens. MT-10 left every `onebox_site_id` empty on purpose because site 169 appeared for two companies (3 and 16). Company 16 `Puskesmas Kota Depok` is a *group* of the debug site, not a tenant (see `voc-industry-taxonomy-decisions`); it held only a user and a sync-state row.
  - Applied manually in dev: `onebox_site_id = 169` on company 3; company 16 deactivated (not deleted). Verified.
  - Left alone: company 2 `Hermina Kemayoran` (60 reviews, 1 location, 2 fetch logs: real old data), company 1 `Default Company` (1 token), companies 7 `a` and 15 `string` (API test leftovers).
  - Check query: `companies` LEFT JOIN `worklist_sync_states`, plus a per-table row count by `company_id`.
- **Still open:** staging and prod. Run the same query there before applying MT-10.
- **Jawaban:** _sebagian_ (dev done)

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
- **New input (2026-10-26):** packages now exist ([[#Q-35]]). Option: weight from package, Default 1 and Plus 2, sent by OneBox as a number ([[#Q-39]]).
- **Answer (Sayyid, 2026-10-26):** yes, weight comes from the package as a number: **Default 1, Plus 2**, set in OneBox config. The crawler stores the integer (`companies.weight`, MT-40).
- **Implemented (MT-40, commit e18fc8e):** weight is stored on `companies.weight` and accepted on `POST/PATCH /tenants`; the cap is the setting `CRAWL_MAX_CONCURRENCY_PER_TENANT`, **default 0 = off**; delta runs before backfill inside a tenant. Under contention a worker may find no job and retries at its next poll.
- **Still open:** the value of the per-tenant concurrency cap (proposal: `ceil(workers / 2)`) and whether `regular_delta` runs before `initial_backfill` (proposal: yes). With 10–15 tenants and a 100,000-review backfill per new site ([[#Q-13]]), the cap matters more than the weights.
- **Jawaban:** _sebagian_

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

- **Status: sebagian terjawab** (MT-03 putaran 1, 2026-10-21). Repo: WSL distro `onebox`, `/var/www/html/onecloud`, branch `feature/DNGO19-3549_VOC-AI-Ticket-Entitlement`. Semua di bawah `[code]`, dibaca langsung.
- **Sudah ada dan bisa dipakai ulang:**
  - `services/VocWorklist.php` — `VocWorklist::forSite($siteId)` menyusun worklist satu site (dari registry `VocTarget`, fallback ke Connection). Bentuk item: `onebox_connection_id`, `onebox_target_id`, `onebox_location_id`, `kind`, `external_place_id`, `branch_name`, `organization_name`, `city`, `target_review_count`, `google_maps_url`, `active`, `crawl_enabled`, `ingest_reviews`, `mock`, `voc_target_id`, `provisioning_status`, `updated_at`, `ai_enabled`, `ai_model`, `ai_output_schema_version`. Ini yang akan menjadi `items[]` snapshot (MT-32); kunci ini sudah sama dengan yang di-parse `WorklistSyncService._validate_payload` di crawler.
  - `controllers/api/v1/VocWorklistController.php` — tenant dari JWT (`sid`), bukan dari request.
  - `services/VocCrawlQueue.php` — jalur tunggal enqueue crawl (tombol Fetch Jobs + scheduler cron); `clientForSite($siteId)` sudah membuat client crawler **per site** dari Connection.
  - `library/VoiceOfCustomerSystemClient.php` — dua mode: `service` (`Options.service_token`, jalur baca) dan `user` (username/password, jalur tulis lama). Ada `whoami()` sebagai guard tenant.
  - Benefit VoC: `VOC_AI`, `VOC_REVIEW`, `VOC_SCRAPE`, `VOC_SCHED`, `VOC_COMP`, `VOC_TICKET` (`VocController::VOC_BENEFITS`, `benefitPackages()`); belum ada alur pembayaran — memilih paket langsung menambah kuota.
  - Model: `VocSchedule`, `VocScheduleRun`, `VocTarget`, `VocKelompok`, `VocLocationKelompok`.
- **Masih tersisa dari desain lama (push sinkron ADR-0001):** `VocController::provisionLocation` / `provisionCompetitor` / `locationResyncAction`, dan field `provisioning_status` di item worklist. Ini jalur lama yang menulis ke crawler lewat login user; ADR-0003 menyatakannya usang. Harus diputuskan nasibnya di MT-30/33 (diganti, bukan dibiarkan dua jalur).
- **Belum ditemukan (perlu dicek/dibangun):** hook "aktivasi paket VoC → provisioning tenant" (benefit dibeli per-kode, tidak ada satu event "paket VoC aktif" → [[#Q-35]]); halaman **Setup Parameter** (belum dicari); counter `snapshot_version` per site ([[#Q-33]]).
- **Sisa untuk putaran 2:** `VocTargetRegistry` dan `VocTarget` (cara cabang disimpan), cara scheduler cron menjalankan `VocSchedule`, ada tidaknya UI tombol Refresh, dan tempat menyimpan token ([[#Q-36]]).
- **Jawaban:** _sebagian_

### Q-32

**Seandal apa mekanisme queue di OneBox untuk panggilan ke crawler?**

- **Konteks:** dengan opsi D, OneBox memikul retry untuk provisioning, push worklist, dan deaktivasi. Dibutuhkan: job tahan restart, retry + backoff, debounce per site, status yang bisa ditampilkan, dan tidak ada dua push untuk site yang sama berjalan bersamaan.
- **Temuan MT-03 putaran 1 (`[code]`, 2026-10-21):**
  - **Tidak ada outbox/queue khusus VoC untuk panggilan keluar.** `VoiceOfCustomerSystemClient::withRetry` hanya retry **di dalam request**: maksimal 2 kali, backoff 2 detik dan 8 detik, hanya untuk kegagalan sementara (curl error / HTTP 5xx). Kalau proses mati atau semua percobaan gagal, panggilan hilang.
  - Yang ada dan **tahan restart**: tabel `VocSchedule` / `VocScheduleRun` untuk jadwal crawl yang dijalankan cron (`VocCron`, `VoiceOfCustomerSystemTask`) — bisa jadi pola untuk tabel outbox.
  - OneBox punya infrastruktur **RabbitMQ** (`library/Rabbitmq.php`, `RabbitBroker.php`, `RabbitTask`, dipakai `Monitor*Task` dan `ReportTask`). Belum dicek apakah dipakai untuk VoC dan apakah ada di semua environment.
  - Jalur lama `locationResyncAction` (tombol kirim ulang cabang yang gagal) adalah preseden UI "status + kirim ulang" untuk Setup Parameter.
- **Artinya:** opsi D **bukan** tinggal memakai queue yang sudah ada; outbox perlu dibangun. Dua cara: (1) tabel outbox DB + task cron (mengikuti pola `VocScheduleRun`, tidak tergantung RabbitMQ), (2) RabbitMQ bila terbukti tersedia di dev/staging/prod. **Usulan:** mulai dari tabel outbox DB — paling sedikit ketergantungan, mudah ditampilkan statusnya di Setup Parameter.
- **Bila ternyata terlalu mahal dibangun:** fallback opsi C (crawler pull dengan kredensial mesin).
- **Jawaban:** _sebagian_ — keputusan outbox DB vs RabbitMQ menunggu konfirmasi.

### Q-33

**`snapshot_version` diambil dari mana?**

- **Usulan:** counter integer per site di OneBox yang naik setiap kali cabang/kompetitor site itu berubah. Lebih aman daripada timestamp (jam server bisa berbeda; dua perubahan bisa di detik yang sama).
- **Alternatif:** `generated_at` + hash isi snapshot (tanpa kolom baru; hash sama → crawler balas `unchanged`).
- **Aturan crawler:** versi ≤ versi tersimpan → `200 {"status": "stale"}` tanpa perubahan.
- **Sudah terimplementasi (MT-13):** crawler mensyaratkan **integer positif yang naik terus** (`bigint`). Opsi counter per site cocok langsung. Opsi alternatif `generated_at` + hash **tidak** didukung oleh implementasi ini; bila dipilih, perlu perubahan di `apply_snapshot` dan migration (menyimpan hash, bukan integer).
- **Jawaban:** _menunggu konfirmasi usulan_

### Q-34

**Apa batas akun Apify bersama, dan apa yang harus dipantau?**

- **Konteks:** dengan satu akun platform ([[#Q-11]]), semua tenant berbagi batas akun Apify: jumlah run bersamaan, memori total, dan plafon pengeluaran bulanan. Kode saat ini sudah membedakan batas konkurensi dari kredit habis (commit `b5de735`, `673db8a`).
- **Yang perlu dicek:** paket akun Apify yang dipakai · maksimum run bersamaan · apakah ada plafon pengeluaran bulanan dan apa yang terjadi saat tercapai · kanal alert ([[#Q-22]]).
- **Kaitan desain:** `CRAWL_MAX_CONCURRENCY_PER_TENANT` dan jumlah total worker harus ≤ batas run bersamaan akun, kalau tidak weighted round robin hanya memindahkan antrean ke sisi Apify.
- **Update (Sayyid, 2026-10-26):** the Apify account is on the **free plan now and will move to the $19 plan**. Concurrent-run limit and monthly spend cap on the new plan are not recorded yet: read them after the upgrade from `GET https://api.apify.com/v2/users/me/limits` (run it yourself with the token; do not paste the token).
- **Risk to check:** with the earlier estimate of about $20 per 100,000 reviews ([[#Q-11]]), one new site's backfill may use a whole month of a $19 plan's usage, and 10–15 sites add 50,000–150,000 reviews a month ([[#Q-13]]). Confirm what usage the $19 plan includes before onboarding more than one large tenant.
- **Cost model from the Q-41 caps (2026-10-26, `$0.20` per 1,000 fetched is still an estimate):** expected operating use is tiny, about 4,500–45,000 reviews a month for 15 tenants of 10–100 locations, which is $0.9–$9 of Apify. The cost is one-time backfill: typical $15–$154 and heavy $42–$418 across 15 tenants. HGA's remaining backfill is about $20 typical and $74 heavy. If every tenant hit both caps the Apify bill would be $60–$600 a month plus $300–$750 one-time.
- **Proposed plan (awaiting confirmation):**
  1. Read the real limits right after the upgrade with `GET https://api.apify.com/v2/users/me/limits` (run it yourself; do not paste the token). Steady state needs only about $1–$10 a month, so the plan matters for the backfill spikes and the concurrent-run limit.
  2. Set the Apify monthly usage limit to about $50 while HGA backfills, then about $25 in steady state; alert at 70%. Raise it per onboarding batch.
  3. Onboard one heavy tenant at a time and none while the account is above 50% of its monthly limit.
  4. Keep total workers at or below the account's concurrent-run limit; per-tenant cap `ceil(workers / 2)` ([[#Q-26]]).
  5. After 30 days, reconcile the Apify bill against `sum(total_fetched)` and replace the $0.20 estimate.
- **Apify plan facts (read from apify.com/pricing on 2026-10-26, not from the Apify account):**

  | Plan | Monthly billing | Annual billing | Prepaid usage / month | Actor RAM | Max concurrent runs | Compute unit |
  |---|---|---|---|---|---|---|
  | Free | $0 | $0 | $5 | 16 GB | 5 | $0.20 |
  | Starter | $19 | **$17 / month** ($204 a year, 10% off) | $19 | 64 GB | 32 | $0.20 |
  | Scale | $199 | $179 / month | $199 | 256 GB | 128 | $0.16 |

  - Prepaid usage **does not roll over**: unused credit expires at the end of each billing cycle.
  - On a **paid plan** extra usage is billed as overage up to the usage limit set in Billing; on the **Free plan access is blocked** until the next cycle once the $5 is gone (every tenant would stop).
  - Upgrades are prorated and a plan can be changed or cancelled at any time.
  - The cost per 1,000 reviews depends on the Actor's own pricing (pay per event or per usage), which the pricing page does not show; the $0.20 per 1,000 estimate still needs the reconciliation in step 5.
- **Plan recommendation (2026-10-26):** Starter, billed **monthly for the first 2–3 months**, then switch to annual ($17) once the real cost per 1,000 reviews and steady spend are known. Reason: the saving is only $24 a year, steady use ($1–$10 a month) leaves most of the $19 prepaid to expire, and the real value of Starter is no hard block plus 32 concurrent runs instead of 5. Free is too risky: 15 tenants of 100 locations would use about $9 a month and be blocked after $5. Scale is not needed.
- **Jawaban:** _sebagian_

### Q-35

**What defines an "active VoC package", i.e. which benefit gates a tenant?**

- **Answer (Sayyid, 2026-10-26):** a tenant is active when it has a VoC package. There are two packages:

| Package | Features | Monthly quota per tenant |
|---|---|---|
| **Default** | review, scrape, sched, comp (not built yet), ticket, AI analysis with Jev | Jev: **$10** · Apify: **100,000** |
| **Plus** | everything in Default + AI summary with OpenAI + auto reply (soon) | Jev: **$20** · Apify: **500,000** · plus AI credit |

- These values are the current target and may change, so they must be configuration in OneBox, not constants in code.
- **Follow-ups:** unit of the Apify quota and meaning of "AI credit" → [[#Q-37]]; who enforces quotas → [[#Q-38]]; whether the crawler needs the package → [[#Q-39]]; Jev price per token → [[#Q-40]]. The package may also drive round-robin weights → [[#Q-26]].
- **Earlier context:** OneBox implements this as six separate benefits (`VOC_AI`, `VOC_REVIEW`, `VOC_SCRAPE`, `VOC_SCHED`, `VOC_COMP`, `VOC_TICKET`); a package is a bundle of those. Gate checks must use `hasBenefit`, not `verifyBenefit()` (which increments `SiteBenefit.Quantity`).
- **Update (2026-10-26):** the Apify quota numbers above (100,000 and 500,000) are replaced by the two-bucket formula in [[#Q-41]]. The Jev dollar figures are under review in [[#Q-43]].

### Q-36

**Token tenant disimpan di level site atau disalin ke tiap Connection cabang?**

- **Temuan (`[code]`):** token baca sekarang ada di `Connection.Options.service_token`, dan satu Connection = satu cabang. `VocCrawlQueue::clientForSite()` mengambil Connection cabang pertama yang layak, jadi secara efektif token diperlakukan sebagai milik site. Rotasi token berarti mengubah semua Connection site itu bila disalin.
- **Usulan:** simpan satu token per site di tempat level site (mis. baris `Setting` per site, pola `VocKelompokScope`); `clientForSite()` membacanya dulu dan jatuh ke `Connection.Options.service_token` selama masa transisi. Regenerate dari Setup Parameter cukup mengubah satu tempat.
- **Jawaban:** _menunggu konfirmasi usulan_

### Q-37

**What unit are the Apify quotas in, and what is the Plus "AI credit"?**

- **Context:** Q-35 gives Apify quotas of 100,000 (Default) and 500,000 (Plus). The earlier estimate was "$20 ≈ 100,000 reviews", so the number most likely means **reviews fetched per month**, but it could also be read as a currency amount.
- **Assumption until answered:** reviews fetched per tenant per calendar month.
- **Input (Sayyid, 2026-10-26):** real volumes are about 100,000 reviews for the initial pull and 5,000–10,000 per site per month ([[#Q-13]]). The quotas (100,000 / 500,000) are far above the monthly delta, which supports reading them as review counts. The unit itself was not stated; the first-pull overlap is [[#Q-41]].
- **Also unclear:** "Plus ... with AI credit": is that an OpenAI budget for AI summary, separate from the Jev $20? Amount and unit?
- **Answer:** _partial_: unit still assumed; "AI credit" pending

### Q-38

**Who enforces the per-tenant quotas, and when?**

- **Proposal:** OneBox enforces, because it owns entitlements (ADR-0001/0002) and is the one that triggers crawls and analyses.
  - **Jev budget:** the analysis API already returns `tokens_used` per run (`AnalysisService` result, passed through by `integration_analysis`). OneBox converts tokens to dollars ([[#Q-40]]), adds them to the tenant's monthly total, and refuses to trigger analysis once the budget is reached.
  - **Apify quota:** OneBox refuses to enqueue a crawl once the tenant's reviews fetched this month reach the quota. The crawler already records `company_id` + `total_fetched` per run in `fetch_logs`; it would expose the monthly total in `GET /api/integration/v1/tenants/{site_id}` (small crawler change, MT-41) so OneBox does not need to aggregate it itself.
  - **Accepted overshoot:** a batch that is already running is not cut off mid-way, so a tenant can exceed its quota by at most one batch.
- **Alternative (not recommended):** the crawler enforces. It would need the quotas, the price list and the package, which duplicates entitlement outside OneBox.
- **Update (2026-10-26, from [[#Q-41]]):** the Apify quota is now two buckets (backfill lifetime, operating monthly). The crawler's part is small: expose `backfill_fetched_total` and `operating_fetched_month` in `GET /api/integration/v1/tenants/{site_id}` (MT-41); OneBox holds the caps and does the alerting and pausing. OneBox must send the purchased location count.
- **Also needed (not per tenant):** an alert on the shared Apify account itself (for example at 70% of its monthly usage), because generous per-tenant caps no longer protect it ([[#Q-34]]).
- **Answer:** _partial_: OneBox enforcement still proposed, awaiting confirmation

### Q-39

**Does the crawler need to know a tenant's package (Default / Plus)?**

- **Proposal:** no, not for features. OneBox is the one calling AI summary and auto reply, so it gates those by package itself, and the crawler stays package-agnostic.
- **Only exception:** if round-robin weights come from the package ([[#Q-26]], e.g. Default 1, Plus 2), OneBox sends the weight (not the package name) when registering or updating the tenant. The crawler stores a number, not business rules.
- **Answer (Sayyid, 2026-10-26):** confirmed. The weight (Default 1, Plus 2) is the only package-derived value the crawler receives ([[#Q-26]]).

### Q-40

**What is the Jev price per token, and where is it configured?**

- **Context:** the Jev budget is in dollars ([[#Q-35]]), but the crawler reports tokens (`tokens_used`, `token_usage.prompt_tokens/completion_tokens`). Something must convert them.
- **Proposal:** the price (per 1M input and output tokens) is OneBox configuration, next to the package quotas, so a price change needs no deploy. The repo already has a reference: `scripts/simulate_onebox_to_ai.py` / commit `f17ae22` ("correct Jev AI per-million token pricing formula").
- **Answer (Sayyid, 2026-10-26):** Jev 1.13 by TypeSafe costs **$0.042 per 1M input tokens** ($42 per billion) and **$0.00 for output tokens**. Keep both prices in OneBox configuration.
- **Consequence (corrected 2026-10-26; the first version said "billion" and was 1,000× too large):** $10 buys about **238 million** input tokens and $20 about 476 million. At roughly 1,000 input tokens per analyzed review (`[asumsi]`: about 400 for the review plus about 600 for the taxonomy prompt, [[voc_taxonomy_tagging_reply_master_plan]]; the spike has not measured it) that is about 238,000 reviews for $10, so a Default tenant analyzing its full 100,000 Apify quota spends about $4.20 of the $10. The Jev budget is therefore not binding in normal use, but repeated re-analysis could reach it, so it is still worth enforcing ([[#Q-38]], [[#Q-41]]).

### Q-41

**Does the first backfill count against the Default monthly Apify quota?**

- **Context:** the Default quota is 100,000 Apify per month ([[#Q-35]]), and a new site's initial pull is about 100,000 reviews ([[#Q-13]]). Counted as ordinary usage, the first backfill alone uses the whole first month, and an enforcing OneBox ([[#Q-38]]) would block the tenant's regular delta right after onboarding.
- **Options:** (a) exclude `initial_backfill` from the monthly quota; (b) count it, with a one-time larger allowance in the first month; (c) count it as is and size the Default quota above 100,000.
- **Decision (Sayyid, 2026-10-26):** count the backfill against the quota (option b or c), not exclude it. Allowance size asked of Claude.
- **Proposed allowance (awaiting confirmation):** option (b): a one-time onboarding allowance of **100,000 reviews** on top of the monthly quota, valid for the **first 30 days after activation** (not the calendar month). Default first-30-days cap 200,000, then 100,000; Plus 600,000 then 500,000 (the extra is optional). Stored in OneBox config as `onboarding_allowance_reviews`. Basis: worst-case first pull is 100 locations × 1,000 = 100,000 plus up to 10,000 delta, so 110,000 is the floor ([[#Q-13]]). Option (c), a permanent 200,000 Default quota, was rejected: steady use is 5,000–10,000 a month, so it would double the maximum cost exposure for every tenant every month for no benefit.
- **Cost check:** at about $20 per 100,000 reviews ([[#Q-11]]), a worst-case backfill for 15 sites is about $300 of Apify usage (typical about $150), more than a $19 plan covers at once, so onboarding should be staggered ([[#Q-34]]).
- **Revised proposal (2026-10-26, after the COO pricing in [[#Q-11]]):** make the onboarding allowance scale with the purchased locations instead of a flat 100,000: **1,000 reviews × purchased locations** (1,000 is the per-location maximum in [[#Q-13]]), valid for the first 30 days. A 10-location tenant (Rp2,000,000 a month) gets 10,000, worst-case cost about Rp 42,000; a 100-location tenant (Rp20,000,000 a month) gets 100,000. The flat 100,000 was sized for the largest tenant and would be 10× oversized for the entry package (up to Rp 424,000 of cost, 21% of its Rp2,000,000 a month). Needs the location count from OneBox on each snapshot or tenant update.
- **Earlier proposal (not chosen):** (a). If `fetch_logs` or the job rows carry the job type (to verify in MT-41), the crawler can report backfill and delta totals separately in `GET /api/integration/v1/tenants/{site_id}`, and OneBox applies the quota to the delta only.
- **Measured on HGA (dev `hermina_crawler`, 2026-10-26; company 3, 310 locations, only 33 finished backfill):**
  - `full_backfill`: 75 runs, 44 locations, 61,248 fetched (53,169 new), **1,392 fetched per location**.
  - `delta`: 181 runs, 46 locations, 1,586 fetched, about **27–36 per location per month** (use 30).
  - Stored reviews per location: average 447, median 65, maximum 4,458. The 44 backfilled locations hold 84% of all stored reviews.
  - Backfill is about 17–46 months of operating volume; operating cost is about 0.06% of revenue.
  - Correction: the Context line above ("the first backfill alone uses the whole first month") holds only for a heavy 100-location tenant. A 10-location first pull is at most about 14,000.
- **Answer (Sayyid, 2026-10-26):** two separate buckets, counted by crawl type from `fetch_logs.metadata->>'coverage'`.
  - **Backfill bucket:** `max(100,000, 2,500 × purchased locations)` fetched reviews, **lifetime per tenant** (HGA's backfill has run 5+ weeks, so no monthly reset). Consumed by `full_backfill`. Each location added later adds 2,500. A re-backfill consumes it, so a "re-crawl everything" is blocked until an admin raises the cap.
  - **Operating bucket:** `2,000 × purchased locations` fetched reviews **per month** (about 67× the observed 30). Consumed by `delta` and `date_window`.
  - **Behaviour:** the quota is a circuit breaker, not a limiter. Operating: alert at 50%, pause new crawls at 100% and notify an admin, with a manual raise. Backfill: alert at 80%, pause at 100%. Both are enforced by OneBox ([[#Q-38]]).
  - **Cost at cap:** operating 4.2% of monthly revenue; backfill (one-time) 5.3% for tenants above 40 locations and up to 21% of one month's revenue for a 10-location tenant (the 100,000 floor).
  - **Replaces** the flat Apify numbers in [[#Q-35]] (Default 100,000, Plus 500,000). Plus is not decided: its price is unknown.
- **Still to verify (MT-41):** every new run records `coverage` (older runs show none, 732 runs / 16,040 fetched).
- **Limit:** one tenant, a hospital group, 33 of 310 locations finished. Other industries (SPBU, coffee) may receive reviews much faster; re-measure after the remaining backfills and a full month of delta (about the end of November 2026).

### Q-42

**Do competitor targets count toward the 10 purchased locations?**

- **Context:** the COO pricing is Rp2,000,000 a month for 10 locations plus Rp200,000 a month per extra location ([[#Q-11]]). The worklist also carries `kind = competitor` targets, and each costs Apify like a location. The competitor feature is not built yet ([[#Q-35]], `comp`).
- **Options:** (a) competitors are free and only locations are billed; (b) each competitor counts as a location; (c) a separate competitor allowance.
- **Why it matters:** if (a), cost per tenant can grow with unbilled targets, so the quota and the onboarding allowance ([[#Q-41]]) must count competitor reviews too.
- **Answer:** _pending_ (COO)

### Q-43

**Should the Jev dollar budget scale with purchased locations?**

- **Context:** the Default Jev budget is a flat $10 a month ([[#Q-35]]); at about 1,000 input tokens per review and $0.042 per 1M tokens ([[#Q-40]]) that is about 238,000 analyzed reviews. A heavy 310-location backfill (about 432,000 reviews, [[#Q-41]]) needs about 432M tokens, or about $18, so analysis would pause partway through the backfill of a Rp62M-a-month tenant. Taxonomy prompts may raise tokens per review to about 2,000, doubling this.
- **Proposal:** Jev budget = **$0.25 × purchased locations per month, floor $10** (Default). That is 10 locations $10, 100 locations $25, 310 locations about $78, enough for about 6,000 reviews per location at 1,000 tokens (about 3,000 at 2,000 tokens), against a heavy backfill of 1,392 per location. Worst-case cost at the cap is about 2.2% of revenue. Plus: double the rate and floor, to be confirmed with its price.
- **Check against the Q-41 caps (2026-10-26, 1,000 tokens per review, $0.042 per 1M):** Jev cost if a tenant fills both caps in month 1: 10 locations $5.04, 25 locations $6.30, 50 locations $9.45, 100 locations $18.90, 310 locations $58.59. The proposed budget ($10, $10, $12.50, $25, $77.50) leaves 2.0×, 1.6×, 1.3×, 1.3× and 1.3× headroom.
- **Behaviour:** alert at 80% of the budget, pause new analysis at 100% with an admin raise; never block ingestion. Rate-limit full re-analysis (rollback and re-run) per tenant, since a loop there is the main way to burn Jev. Measure tokens per review in the taxonomy spike and rescale (for example $0.50 per location) if it is above about 2,000.
- **Alternative:** drop the dollar budget and derive it from the review caps in [[#Q-41]] (reviews analyzed × tokens × price), since Jev only analyzes reviews that were fetched.
- **Answer:** _waiting for confirmation_
