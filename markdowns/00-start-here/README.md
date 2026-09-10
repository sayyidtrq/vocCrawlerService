# VoC Markdown Knowledge Base

Folder ini adalah pusat dokumentasi enhancement Voice of Customer OneBox dan Crawler Service.

Struktur disusun berdasarkan satu dimensi utama: tujuan dokumen. Jika mencari sesuatu, mulai dari kategori tujuan kerja, bukan dari nama modul atau nama pembuat dokumen.

## Struktur Folder

| Folder | Tujuan | Kapan dibaca |
| --- | --- | --- |
| `00-start-here` | Orientasi, status proyek, dan dokumen lintas modul | Saat onboarding, handoff, atau mencari konteks cepat |
| `01-product-and-backlog` | Grooming, backlog, Jira spec, user story, task breakdown | Saat menyusun scope, sprint, atau copy task ke Jira |
| `02-meetings-and-decisions` | Notulen, revisi stakeholder, ADR, opsi arsitektur | Saat butuh alasan keputusan atau perubahan arah |
| `03-architecture` | ERD, DFD, kontrak integrasi, diagram sistem | Saat memahami boundary OneBox, Crawler, DB, queue, API |
| `04-implementation-plans` | Plan teknis per modul dan work package | Saat mulai development paralel Codex/Claude |
| `05-runbooks` | Prosedur setup, deployment, UAT, Postman, tenant onboarding | Saat menjalankan sistem, demo, testing, atau deploy |
| `06-troubleshooting` | Insiden, diagnosa, dan resolusi masalah berulang | Saat error muncul di UI/log/server |
| `07-data-and-seeding` | SQL seed, mapping field, workbook referensi | Saat setup master data, tenant, atau migrasi data |
| `08-agent-prompts-and-handoffs` | Prompt Claude/Codex dan pembagian kerja agent | Saat delegasi task ke agent lain |
| `09-design-ux-and-research` | Riset, UX, persona, redesign notes | Saat merapikan UI atau validasi pengalaman user |
| `98-sensitive-access` | Dokumen akses/credential lokal | Hanya untuk operator yang berwenang |
| `99-legacy-reference` | Arsip dokumen lama Hermina Crawler | Saat butuh referensi historis, bukan sumber utama |

## Dokumen Utama

Dokumen yang paling berguna untuk memahami state terbaru:

| Status | Dokumen | Alasan |
| --- | --- | --- |
| UTAMA | `MUST_READ.md` | Gerbang konteks sebelum mengerjakan VoC |
| UTAMA | `PROJECT_STATUS.md` | Snapshot status dan arah proyek |
| UTAMA | `VOC_FETCH_LOGIC_TOP_DOWN.md` | Kajian refactor Fetch Review: date window, cursor, duplicate, rating snapshot |
| UTAMA | `VOC_STAKEHOLDER_OVERVIEW.md` | Penjelasan high-level untuk stakeholder |
| BERGUNA | `../04-implementation-plans/key-process/PLAN_KEY_PROCESS_DEMO.md` | Target demo key process |
| BERGUNA | `../04-implementation-plans/key-process/PLAN_FAST_INGEST_LABELING_ON_DEMAND_AI.md` | Flow final ingest cepat, labeling, dan AI async |
| BERGUNA | `../04-implementation-plans/crawler-system/PLAN_REVIEW_FETCH_LOGIC_REFACTOR.md` | Plan teknis refactor fetch crawler |
| BERGUNA | `../04-implementation-plans/onebox/PLAN_FETCH_REVIEW_UI_AND_RATING_TREND.md` | Plan UI Fetch Review dan rating trend |
| UTAMA | `../04-implementation-plans/onebox/PLAN_RELEASE_1_123_0_KE_PRODUKSI.md` | Pemahaman + to-do PR ulang 4 branch VoC ke release/1.123.0 |
| UTAMA | `../04-implementation-plans/onebox/PLAN_RELEASE_1_124_0.md` | Persiapan rilis 1.124.0: keadaan 14 branch VoC tersisa + urutan kerja |
| BERGUNA | `../05-runbooks/VOC_MIGRASI_1123_DI_DEV.md` | Kapan migrasi 1.123.0 ditandai vs dijalankan di dev |
| BERGUNA | `../06-troubleshooting/incidents/MIGRATE_PHP_MENCETAK_PASSWORD_DB.md` | migrate.php mencetak password DB ke stdout |
| BERGUNA | `../03-architecture/integration/FETCH_JOBS_E2E_CONTRACT.md` | Kontrak Fetch Jobs end-to-end |
| BERGUNA | `../01-product-and-backlog/jira-specs/DNGO19-3420_fetch-jobs-crawl-dev-spec.md` | Dev specification Fetch Jobs Crawl |
| BERGUNA | `../01-product-and-backlog/jira-specs/DNGO19-3388_ai-analysis-setup-regrooming.md` | Re-grooming AI Analysis Setup |
| BERGUNA | `../05-runbooks/testing-and-postman/VOC_CRAWL_PROOF_RUNBOOK.md` | Runbook pembuktian crawler |
| BERGUNA | `../06-troubleshooting/incidents/VOC_WORKLIST_REFRESH_DUPLICATE_RESOLUTION.md` | Resolusi worklist stale/duplicate setelah seeding |

## Aturan Penempatan Dokumen Baru

- Backlog atau Jira detail masuk ke `01-product-and-backlog`.
- Keputusan yang sudah disepakati masuk ke `02-meetings-and-decisions/adr`.
- Diagram dan kontrak sistem masuk ke `03-architecture`.
- Rencana implementasi masuk ke `04-implementation-plans`.
- Prosedur yang bisa dijalankan operator masuk ke `05-runbooks`.
- Error, root cause, dan resolusi masuk ke `06-troubleshooting`.
- SQL seed, mapping, dan workbook masuk ke `07-data-and-seeding`.
- Prompt untuk agent masuk ke `08-agent-prompts-and-handoffs`.
- UX, riset, dan design review masuk ke `09-design-ux-and-research`.
- Credential atau akses masuk ke `98-sensitive-access`.
- Dokumen lama yang belum dipercaya sebagai sumber terbaru masuk ke `99-legacy-reference`.

## Aturan Migrasi (Konvensi Tim)

Sumber: Agung Januar, review PR `feature/DNGO19-3385` dan `-3387` → `release/1.123.0` (September 2026). Ini konvensi tim OneCloud, bukan preferensi pribadi.

**1. Satu versi = satu folder.** Migrasi untuk satu versi rilis ditaruh dalam SATU folder versi, tidak dipecah ke banyak folder timestamp.
> "untuk satu versi baiknya dalam satu folder versi, tidak terpecah di beberapa folder timestamp"
> "betul, satu folder saja, lihat versi yg lain"

**2. Satu tabel/skema = satu file.** Semua DDL/DML untuk satu tabel berada di satu file, bukan tersebar.
> "untuk satu table/ skema baiknya dalam satu file"

**3. Perbaikan data testing bukan migrasi.** Boleh dijalankan di lokal, tapi jangan didokumentasikan sebagai migrasi.
> "untuk perbaikan data testing baiknya tidak dibuatkan migration"
> "bisa di lokal, tp migrasinya tidak perlu didokumentasikan"
> "versi 1.123.0 terlalu banyak, sptnya ini hanya patch data di versi yg sama"

### Angka yang membuat keluhan itu wajar

`release/1.123.0` sendiri **belum punya satu pun** folder `_1_123_0` — versinya memang belum tayang. Yang banyak adalah folder yang **ditambahkan oleh PR**:

| | Folder `_1_123_0` |
| --- | --- |
| `release/1.123.0` (kondisi sekarang) | 0 |
| ditambah PR 3385 | 11 |
| ditambah PR 3387 | **23** |
| Versi mana pun yang sudah tayang, terbanyak (`_1_118_0`) | 4 |

Dan kalimat "hanya patch data" itu harfiah benar. Dari **26 file migrasi** di PR 3387, yang benar-benar menyentuh skema hanya **2**:

| Jenis | Jumlah file |
| --- | --- |
| CREATE / ALTER (skema) | 2 |
| INSERT / UPDATE (data) | 24 |

`Menu.php` sendiri muncul di **15 folder berbeda** — satu tabel, 15 berkas.

### Kenapa sampai terpecah: ini bukan sekadar ceroboh

Phalcon mencatat migrasi yang sudah jalan di tabel `phalcon_migrations`, dan yang dicatat adalah **nama folder**, bukan nama file. Sekali sebuah folder tercatat, Phalcon tidak akan pernah menjalankannya lagi — **menambah atau memperbaiki file di dalamnya tidak berefek apa pun**.

Ini sudah pernah menggigit dan tercatat di docblock migrasi kita sendiri:

> "Versinya terlanjur tercatat di phalcon_migrations, sehingga memperbaiki isi file itu TIDAK menolong — Phalcon tidak akan pernah menjalankannya lagi. Karena itu perbaikannya dikirim sebagai versi baru, bukan menyunting versi lama."

Jadi tiap kali sebuah migrasi perlu diperbaiki **setelah** jalan di dev, folder baru adalah satu-satunya jalan. Terpecahnya 23 folder itu akibat wajar dari mengembangkan sambil migrasinya sudah berjalan di dev.

**Cara menyelesaikannya:** konsolidasi dilakukan **sebelum versinya tayang ke produksi**. Selama 1.123.0 belum naik, seluruh migrasinya boleh dibentuk ulang jadi satu folder bersih. Untuk dev yang terlanjur mencatat folder lama, hapus barisnya lalu jalankan ulang — semua migrasi VoC memang ditulis idempotent:

```sql
DELETE FROM phalcon_migrations WHERE version LIKE '%\_1\_123\_0';
```

### Hasil konsolidasi 1.123.0

Satu folder `1786200000000000_1_123_0`, satu berkas per tabel:

| Berkas | Menggabungkan | Isi |
| --- | --- | --- |
| `Menu.php` | 15 migrasi | data menu VoC |
| `Reference.php` | 3 | data referensi |
| `Benefit.php` | 3 | katalog & pemberian benefit |
| `VocSchedule.php` | 2 | CREATE 2 tabel + ALTER-nya |
| `Ticket.php` | 1 | data tipe tiket |
| `MessageContent.php` | 1 | template pesan |
| ~~`User.php`~~ | — | **dikeluarkan** (akun uji → aturan 3) |

23 folder / 26 file → **1 folder / 6 file**. Digabung secara mekanis oleh `/root/voc-merge-migrations.py`, yang memindahkan isi tiap langkah apa adanya dan memverifikasi **217 dari 217** pernyataan SQL terbawa utuh; keenam berkas lolos `php -l`.

## Aturan Naik ke Produksi

Temuan dari PR 3385 & 3387 ke `release/1.123.0`. Semuanya terbukti dari repo, bukan dugaan.

**4. Jangan pernah merge release ke dalam branch feature.** Arahnya selalu feature → release.

Merge `release/1.123.0` masuk ke branch 3387 mengubah **154 berkas**, termasuk `.env`, `.env.devtele`, `.env.proxy-gateway`, `build.yml`, `onecloud/docker-compose.yml`, dan seluruh `docker/`. Nilai-nilai produksi menimpa nilai lokal, dan `build.sh` lokal berhenti bekerja — persis gejala yang muncul.

Kalau branch perlu menyusul release, **salin kode ke branch baru di atas release**, jangan tarik release ke bawah:

```bash
git checkout -b feature/XXXX_pr2 origin/release/1.123.0
git checkout feature/XXXX -- <berkas kode>
```

Arah ini tidak pernah bisa membawa `.env` atau riwayat merge, karena yang berpindah hanya berkas yang kamu sebut.

**5. Berkas config per-mesin tidak pernah ikut PR.** `.env*`, `onecloud/app/config/local.php`, dan `development.php` berisi kredensial per-mesin dan ditandai `skip-worktree`. Di branch 3387, `local.php` ter-commit dengan **6 baris berubah** yang memuat password/host/username. Itu bukan bagian dari fitur.

**6. `build.yml` milik semua tim — hati-hati menyunting daftar branch.** Jangan hapus entri branch orang lain, dan sadari efeknya lintas-branch.

Contoh nyatanya BUKAN kesalahan pengembang VoC. Commit `9d0ea6c344` (Agung Januar, 24 Juli 2026, "update build feature/voc") menukar dua nama branch lama menjadi `feature/voc`:

```diff
-feature/DNGO19-3252_ciptalife-source-broadcast:
-feature/DNGO19-3339_enhancement-customer-recognition-rs:
+feature/voc:
   analyze: false
```

Di jalur `feature/voc`, `3252` hanyalah key kosong satu baris — ia tidak pernah punya blok konfigurasi; yang memilikinya `3339`. Belakangan `release` mengembangkan `3252` jadi blok penuh secara terpisah. Akibatnya `git diff release...3385 -- build.yml` **terlihat** menghapus 32 baris, padahal branch itu tidak pernah memuatnya — ia cuma mewarisi commit Agung karena dicabang dari `feature/voc`.

**Aturannya:** `build.yml` tidak ikut PR fitur. Kalau memang perlu diubah, kirim sebagai perubahan tersendiri, bukan menumpang di PR fitur — efeknya ke release tidak terlihat dari branch tempat kamu menyuntingnya.

**7. Artefak kerja tidak ikut tayang.** `scriptdb/voc/*.sql` (7 berkas) dan `docs/voc/MAPPING_VOC_KE_TICKET.md` ter-commit ke PR 3385. SQL bantu dan catatan kerja tempatnya di `07-data-and-seeding` atau di repo markdown ini, bukan di branch rilis.

**8. Satu PR = satu scope.** Branch 3385, 3392, dan 3420 masing-masing berbeda dari 3385 hanya **5 dan 13 berkas**, tetapi ketiganya membawa **11 folder migrasi yang identik**. Artinya PR "Master Data Locations" juga berisi `reports.volt` dan `fetchjobs.volt` milik tiket lain, dan PR mana pun yang merge duluan akan membuat tiga sisanya konflik. Penyebabnya: semua dicabang dari `feature/voc` yang menumpuk segalanya.

**Urutan yang benar untuk 4 branch ke satu rilis:** merge satu, lalu cabang/rebase yang berikutnya di atas release yang sudah diperbarui — jangan siapkan keempatnya paralel dari basis yang sama.

**9. Uji di lokal sebelum PR, dan pastikan masih bisa diuji.** Kalau `build.sh <env>` tiba-tiba gagal setelah operasi git, curigai dulu `.env` yang tertimpa — `path.sh` membaca `.env` lalu `.env.$BRANCHROOT` lalu `.env.$1`, jadi satu berkas yang tertimpa cukup untuk merusak seluruh rantai.

### Alat bantu

| Perintah | Guna |
| --- | --- |
| `/root/voc-pr-ulang.sh <tiket> --dry` | lihat rencana PR ulang tanpa mengubah apa pun |
| `/root/voc-pr-ulang.sh <tiket>` | susun branch `_pr2` bersih dari release + migrasi tergabung |
| `/root/voc-merge-migrations.py` | gabungkan migrasi satu tabel jadi satu berkas |
| `/root/voc-git.sh <perintah git>` | perintah git yang aman terhadap berkas `skip-worktree` |

## Catatan

Dokumen di `99-legacy-reference` boleh berguna sebagai sejarah, tetapi jangan dijadikan sumber kebenaran tanpa dibandingkan dengan `00-start-here`, `02-meetings-and-decisions/adr`, dan plan terbaru.
