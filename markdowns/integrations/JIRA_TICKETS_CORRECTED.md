## VoC OneBox — Daftar Ticket Jira

> **Keputusan scope terbaru (3 Agustus 2026):**
> - `DNGO19-3346` **tidak lagi dipakai sebagai penampung scope lanjutan**. Pekerjaan yang sebelumnya dicatat di sana dibagi ke ticket feature yang lebih spesifik.
> - Restrukturisasi menu navigasi VoC dinyatakan sudah diimplementasikan pada integration branch `feature/voc`; sisanya adalah verifikasi fungsi, urutan menu, route, dan permission.
> - **Delta Sync dan safe checkpoint** menjadi bagian `DNGO19-3420` — Fetch Jobs Crawl.
> - **Targeted backfill lokasi baru** menjadi bagian `DNGO19-3385` — Master-Data-Locations.
> - **Rekonsiliasi review lama tanpa Ticket OneBox** dibagi antara `DNGO19-3420` (menarik dan mengidentifikasi review) dan `DNGO19-3387` (membuat/menghubungkan Ticket secara idempotent).
> - **Review Detail** tetap digabung ke dalam `DNGO19-3387` — satu ticket untuk seluruh alur Ulasan (detail + aksi kelola).
> - **Batas AI:** Crawler memilih model, provider, prompt runtime, dan strategi eksekusi. OneBox hanya mengatur apakah AI aktif serta memastikan struktur output AI konsisten dan dapat digunakan feature OneBox.
>
> Konvensi tetap: maks 5-6 MD/ticket, 1 screen = 1 ticket, branch 1:1 dengan ticket, jangan campur scope OneBox (PHP, repo `onecloud`) dengan Crawler (Python, repo `hermina_crawler`).

---

## Daftar Ticket (per board, dikonfirmasi dari screenshot)

| Ticket          | Nama                          | Status board         | Branch                                                     |
| --------------- | ----------------------------- | -------------------- | ---------------------------------------------------------- |
| **DNGO19-3385** | VOC : Master-Data-Locations   | IN DEV SPEC REVIEW   | `feature/DNGO19-3385_VOC-Master-Data-Locations`            |
| **DNGO19-3386** | VOC : Master-Data-Competitors | IN DEV SPEC REVIEW   | `feature/DNGO19-3386_VOC-Master-Data-Competitors`          |
| **DNGO19-3387** | VOC : Review Manage Actions   | IN DEV SPEC REVIEW   | `feature/DNGO19-3387_VOC-Review-Manage-Actions`            |
| **DNGO19-3388** | VOC : AI Analysis Setup       | READY TO DEV         | `feature/DNGO19-3388_VOC-AI-Analysis-Setup`                |
| **DNGO19-3407** | VOC : Enhance AI Analysis     | TODO                 | `feature/DNGO19-3407_VOC-Enhance-AI-Analysis`              |
| **DNGO19-3420** | VOC : Fetch Jobs Crawl        | TODO                 | `feature/DNGO19-3420_VOC-Fetch-Jobs-Crawl`                 |
| **DNGO19-3389** | VOC : AI Insights             | TODO                 | `feature/DNGO19-3389_VOC-AI-Insights`                      |
| **DNGO19-3390** | VOC : Crawl Scheduler         | TODO                 | `feature/DNGO19-3390_VOC-Crawl-Scheduler`                  |
| **DNGO19-3391** | VOC : Config Setup            | READY TO DEV         | `feature/DNGO19-3391_VOC-Config-Setup`                     |
| **DNGO19-3392** | VOC : Generate Reports        | READY TO DEV         | `feature/DNGO19-3392_VOC-Generate-Reports`                 |
| **DNGO19-TBD**  | VOC : Dashboard Profile Per Daerah | TODO            | `feature/DNGO19-TBD_VOC-Dashboard-Per-Daerah`              |
| **DNGO19-3396** | VOC : Competitor Analysis     | TODO                 | `feature/DNGO19-3396_VOC-Competitor-Analysis`              |
| DNGO19-3346     | Media Crawler Google Business Review | *scope lanjutan sudah didistribusikan; tidak dipakai sebagai bucket* | `feature/DNGO19-3346_Media-Crawler-Google-Business-Review` |

---

## Audit Implementasi Branch Remote — 3 Agustus 2026

Audit ini membandingkan branch ticket dengan integration branch `feature/voc` pada repository `ciptadra/onecloud`. Status di bawah adalah **status implementasi kode**, bukan pengganti status workflow Jira.

| Ticket | Temuan pada kode terbaru | Kesimpulan tracking |
|---|---|---|
| DNGO19-3385 | Branch ticket masih memiliki 3 commit yang belum ada di `feature/voc`; berisi implementasi PIC Location dan perubahan halaman Location. | **In progress / pending merge dan QA.** Targeted backfill lokasi baru belum teridentifikasi sebagai implementasi khusus dan masih menjadi pekerjaan tersisa. |
| DNGO19-3386 | Isi branch ticket identik dengan `feature/voc`. | **Implemented in integration branch; pending functional verification/QA.** |
| DNGO19-3387 | Branch ticket tidak memiliki commit unik dan tertinggal dari `feature/voc`. Detail review, assign, perubahan status/priority, catatan internal, dan histori sudah ada di `feature/voc`. | **Implemented in integration branch; pending functional verification/QA.** Rekonsiliasi review lama tetap perlu diverifikasi sebagai skenario khusus. |
| DNGO19-3388 | Branch ticket tidak memiliki implementasi unik. Halaman AI Analysis pada `feature/voc` masih berisi data simulasi dan aksi simulasi. | **Not implemented.** Jira dan tracker perlu disesuaikan dengan pembagian tanggung jawab AI terbaru. |
| DNGO19-3389 | Branch ticket tidak memiliki implementasi unik. | **Not implemented / remaining.** |
| DNGO19-3390 | Branch ticket tidak memiliki implementasi unik. | **Not implemented / remaining.** |
| DNGO19-3391 | Branch ticket memiliki 1 commit yang belum ada di `feature/voc`; berisi benefit/quota VoC dan halaman Settings. | **In progress / pending merge dan QA.** |
| DNGO19-3392 | Branch ticket tidak memiliki implementasi unik. | **Not implemented / remaining.** |
| DNGO19-3396 | Branch ticket tidak memiliki implementasi unik. | **Not implemented / remaining.** |
| DNGO19-3407 | Branch ticket tidak memiliki implementasi unik. | **Not implemented / remaining.** |
| DNGO19-3420 | Flow enqueue crawl, monitoring batch, import review, deduplication, dan safe checkpoint sudah terlihat di `feature/voc`; branch ticket masih memiliki 2 commit tambahan yang belum ada di integration branch. | **Substantially implemented; remaining: review 2 commit, merge, legacy reconciliation, dry-run/cancel decision or implementation, retry/resume verification, dan QA end-to-end.** |

> **Catatan menu:** `feature/voc` sudah memiliki perubahan menu/migration VoC. Karena seed lama `scriptdb/voc/voc_setup_all.sql` masih memperlihatkan struktur flat, status menu dicatat sebagai **implemented, pending verification** sampai struktur Transaksi/Output/Setting, urutan, route, dan permission lolos pengecekan di environment Dev.

---
### DNGO19-3385 — Master-Data-Locations
- **Owner:** Sayyid · **Status:** IN DEV SPEC REVIEW · **MD:** ~1.6 MD
#### Description

> Menyediakan pengelolaan master data lokasi/cabang VoC di OneBox agar admin dapat menentukan lokasi yang akan dipantau dan menyimpan informasi penanggung jawab setiap lokasi.
>
> **Scope:**
> - Mempertahankan fungsi tambah, ubah, aktif/nonaktif, dan hapus lokasi yang sudah tersedia.
> - Menambahkan data PIC lokasi berupa nama, nomor WhatsApp, email, dan ID User OneBox.
> - Menyelesaikan form PIC pada halaman Location dan menghubungkannya dengan proses penyimpanan di backend.
> - Menghapus mekanisme push-sync lama pada tombol resync dan toggle setelah consumer worklist Crawler dinyatakan stabil.
> - Memperbaiki `StatusId` Connection 1039 Hermina Depok agar tidak ikut proses penjadwalan yang tidak sesuai.
> - Memastikan lokasi nonaktif tidak ikut proses crawl tanpa menghapus review dan data historisnya.
> - Memicu targeted backfill ketika lokasi baru mulai dipantau agar review historis lokasi tersebut tidak terlewat oleh checkpoint tenant yang sudah berjalan.
>
> **Acceptance Criteria:**
> - Admin dapat mengisi dan memperbarui data PIC lokasi.
> - Data PIC tersimpan dan tampil kembali ketika halaman dibuka ulang.
> - Format email dan nomor WhatsApp divalidasi.
> - Lokasi aktif tersedia pada worklist Crawler.
> - Lokasi nonaktif tidak ikut proses crawl berikutnya.
> - Menonaktifkan lokasi tidak menghapus review atau histori yang sudah ada.
> - Setelah consumer worklist stabil, tombol resync dan toggle tidak lagi memanggil endpoint write lama di Crawler.
> - Connection 1039 Hermina Depok memiliki `StatusId` yang benar dan tidak ikut scheduler yang tidak sesuai.
> - Lokasi baru dapat memperoleh review historis sebelum melanjutkan delta sync reguler.
> - Targeted backfill dapat dijalankan ulang tanpa membuat review atau Ticket duplikat.
> - Perubahan tidak mengganggu fungsi CRUD Location yang sudah tersedia.
>
> **Dependency:**
> - Penghapusan push-sync lama hanya dilakukan setelah consumer worklist Crawler terbukti stabil di environment Dev.
> - Endpoint integration review Crawler mendukung filter lokasi dan rentang waktu historis.
>
> **Out of Scope:**
> - Implementasi consumer worklist di repository `hermina_crawler`.
> - Perubahan scheduler utama.
> - Analisis dan report berdasarkan lokasi.

#### Subtask 1

**Summary**

`VOC - Master Data Locations - Complete Location PIC Form and Persistence`

**Description**

> Lengkapi implementasi data PIC pada Master Data Location.
>
> **Scope:**
> - Tambahkan field Nama PIC, Nomor WhatsApp, Email, dan OneBox User ID pada form Location.
> - Muat data PIC ketika Location diedit.
> - Hubungkan field PIC dengan `VocController::locationSaveAction`.
> - Pastikan penyimpanan data PIC tidak mengubah field Location lainnya.
> - Tambahkan validasi format email dan nomor WhatsApp.
> - Tampilkan pesan validasi yang dapat dipahami user.
>
> **Acceptance Criteria:**
> - Field PIC tersedia pada form tambah dan edit Location.
> - Data PIC berhasil disimpan dan tetap tersedia setelah halaman dimuat ulang.
> - Edit data PIC tidak mengubah Place ID, status, atau data Location lain.
> - Email dan nomor WhatsApp dengan format tidak valid ditolak.
> - Kondisi PIC kosong ditangani sesuai ketentuan field wajib atau opsional.

#### Subtask 2

**Summary**

`VOC - Master Data Locations - Remove Legacy Push-Sync Bridge`

**Description**

> Hapus mekanisme transisi yang masih melakukan push data Location ke endpoint write lama di Crawler.
>
> **Scope:**
> - Hapus pemanggilan endpoint push-sync lama dari tombol resync Location.
> - Hapus pemanggilan endpoint push-sync lama dari proses toggle aktif/nonaktif.
> - Pastikan perubahan Location tetap tersedia bagi Crawler melalui worklist.
> - Pastikan tidak terjadi dual-write antara push-sync lama dan worklist.
>
> **Acceptance Criteria:**
> - Tombol resync dan toggle tidak lagi memanggil endpoint write Location lama.
> - Toggle tetap berfungsi di OneBox.
> - Perubahan Location tetap terbaca oleh Crawler melalui worklist.
> - Tidak ada dua proses sinkronisasi untuk satu perubahan.
> - Smoke test tambah, edit, toggle, dan resync Location berhasil.
>
> **Dependency:**
> - Consumer worklist Crawler telah dinyatakan stabil di environment Dev.

#### Subtask 3

**Summary**

`VOC - Master Data Locations - Fix StatusId Hermina Depok Connection 1039`

**Description**

> Perbaiki `StatusId` Connection ID 1039 untuk Hermina Depok yang menyebabkan connection ikut proses penjadwalan yang tidak sesuai.
>
> **Scope:**
> - Periksa data Connection ID 1039.
> - Ubah `StatusId` menjadi `CNS2` sesuai status yang seharusnya.
> - Periksa query scheduler yang sebelumnya memilih connection tersebut.
> - Pastikan perubahan hanya berlaku untuk Connection ID 1039.
>
> **Acceptance Criteria:**
> - Connection ID 1039 memiliki `StatusId=CNS2`.
> - Connection ID 1039 tidak lagi ikut scheduler yang tidak sesuai.
> - Tidak ada Connection lain yang berubah.
> - Perubahan berhasil diverifikasi pada environment Dev.

#### Subtask 4

**Summary**

`VOC - Master Data Locations - Trigger Targeted Backfill for New Location`

**Description**

> Tambahkan proses targeted backfill ketika lokasi baru berhasil terhubung dengan Crawler, sebelum lokasi tersebut hanya mengikuti checkpoint delta tenant reguler.
>
> **Pembagian tanggung jawab:**
> - Master Data Locations menentukan lokasi mana yang baru dan memicu backfill untuk lokasi tersebut.
> - Fetch Jobs Crawl menjalankan mekanisme pull, safe checkpoint, deduplication, dan pemantauan hasil.
>
> **Scope:**
> - Gunakan identifier lokasi yang sudah dipetakan antara OneBox dan Crawler.
> - Kirim filter lokasi serta rentang waktu historis yang disepakati.
> - Jalankan backfill setelah provisioning lokasi berhasil dan sebelum lokasi hanya bergantung pada checkpoint tenant reguler.
> - Simpan status terakhir: pending, running, success, partial success, atau failed.
> - Sediakan retry yang aman untuk backfill gagal.
>
> **Acceptance Criteria:**
> - Lokasi baru memperoleh review historis yang tersedia dalam periode backfill.
> - Review lama tidak terlewat walaupun checkpoint tenant telah melewati tanggal review tersebut.
> - Retry dan rerun tidak membuat Message atau Ticket duplikat.
> - Kegagalan satu lokasi tidak memajukan checkpoint atau mengganggu lokasi lain.
> - Status, waktu eksekusi, dan counter hasil backfill dapat ditelusuri.
>
> **Status audit 3 Agustus 2026:**
> - Implementasi PIC Location terdeteksi pada branch 3385, tetapi targeted backfill belum teridentifikasi sebagai implementasi khusus. Subtask ini masih perlu dikerjakan dan diuji.


### DNGO19-3386 — Master-Data-Competitors

- **Owner:** OneBox (OB) · **Status:** IN DEV SPEC REVIEW

#### Description

> Menyediakan pengelolaan master data kompetitor di OneBox agar admin dapat menentukan kompetitor yang ingin dipantau dan membedakannya dari lokasi milik sendiri.
>
> **Scope:**
> - Mempertahankan fungsi tambah, ubah, aktif/nonaktif, dan hapus kompetitor yang sudah tersedia.
> - Menggunakan pola pengelolaan yang konsisten dengan Master Data Location.
> - Menetapkan `StatusId=CNS3` untuk Connection kompetitor.
> - Memastikan Connection kompetitor tidak ikut scheduler yang hanya ditujukan untuk lokasi milik sendiri.
> - Memastikan kompetitor aktif tersedia melalui worklist untuk kebutuhan Crawler.
> - Memastikan review kompetitor tidak otomatis dibuat sebagai Ticket OneBox.
>
> **Acceptance Criteria:**
> - Admin dapat menambah, mengubah, menonaktifkan, dan menghapus kompetitor.
> - Kompetitor baru otomatis menggunakan `StatusId=CNS3`.
> - Mengedit kompetitor tidak mengubah `StatusId` menjadi status Location.
> - Kompetitor tidak ikut scheduler lokasi milik sendiri.
> - Kompetitor aktif tersedia pada worklist.
> - Kompetitor nonaktif tidak diproses pada crawl berikutnya.
> - Review kompetitor tidak dibuat sebagai Ticket OneBox.
> - Perubahan tidak memengaruhi Master Data Location.
>
> **Out of Scope:**
> - Halaman perbandingan performa kompetitor; pekerjaan tersebut berada pada DNGO19-3396.
> - Implementasi endpoint `competitor_reviews` di Crawler.
> - Penambahan data PIC kompetitor sebelum mendapatkan konfirmasi dari Product.

#### Subtask 1

**Summary**

`VOC - Master Data Competitors - Verify Status and Scheduler Exclusion`

**Description**

> Verifikasi bahwa seluruh Connection kompetitor menggunakan `StatusId=CNS3` dan tidak ikut scheduler yang hanya ditujukan untuk lokasi milik sendiri.
>
> **Scope:**
> - Periksa proses create dan update kompetitor.
> - Periksa nilai default `StatusId` kompetitor.
> - Periksa query scheduler yang memilih Connection.
> - Uji kompetitor dalam kondisi aktif dan nonaktif.
>
> **Acceptance Criteria:**
> - Kompetitor baru otomatis memperoleh `StatusId=CNS3`.
> - Edit kompetitor tidak mengganti `StatusId` menjadi status Location.
> - Connection dengan `StatusId=CNS3` tidak ikut scheduler Location.
> - Kompetitor nonaktif tidak ikut proses crawl.
> - Hasil verifikasi dicatat sebagai evidence pada subtask.


### DNGO19-3387 — Review Manage Actions

- **Owner:** OneBox (OB) · **Status:** IN DEV SPEC REVIEW · **MD:** 3 + 4 = **7 MD** ⚠️ melebihi cap 5MD

> **Catatan:** tetap satu ticket induk dan satu branch. Implementasi Review Detail dan Manage Actions sudah terdeteksi di `feature/voc`; status belum boleh dianggap Done sebelum functional test dan QA selesai. Rekonsiliasi review lama dicatat sebagai subtask tambahan agar tanggung jawabnya tidak kembali masuk ke 3346.

#### Description

> Menyediakan alur lengkap untuk melihat detail review dan menindaklanjutinya sebagai Ticket OneBox sehingga agent tidak perlu menggunakan sistem pengelolaan yang terpisah.
>
> **Scope:**
> - Menampilkan detail review dari halaman daftar Ulasan.
> - Menampilkan teks review lengkap, rating, sentiment, urgency, kategori, summary, dan recommended action.
> - Menampilkan informasi lokasi, source, dan waktu review apabila tersedia.
> - Menyediakan akses ke Ticket OneBox yang terkait.
> - Menyediakan aksi assign review/Ticket kepada agent.
> - Menyediakan aksi perubahan status sesuai workflow Ticket OneBox.
> - Menyediakan aksi penambahan internal note.
> - Menggunakan mekanisme Ticket OneBox yang sudah tersedia, bukan membuat sistem assignment, status, atau note baru khusus VoC.
> - Membuat atau menghubungkan Ticket untuk review lama yang sudah berhasil ditarik ke OneBox tetapi belum memiliki Ticket, tanpa menghasilkan duplikasi.
>
> **Acceptance Criteria:**
> - User dapat membuka detail dari satu baris review.
> - Detail yang ditampilkan sesuai review yang dipilih.
> - Teks review di-escape sebelum ditampilkan.
> - Field hasil analisis ditampilkan apabila tersedia; field kosong memiliki empty state yang jelas.
> - User dapat membuka Ticket OneBox yang terkait menggunakan `Ticket.Id`.
> - User yang memiliki permission dapat melakukan assign, mengubah status, dan menambahkan internal note.
> - Internal note tersimpan pada histori Ticket.
> - Aksi yang gagal menampilkan pesan error dan tidak menghasilkan perubahan parsial.
> - Permission mengikuti mekanisme permission Ticket OneBox.
> - Review lama tanpa Ticket dapat diproses secara idempotent; review yang sudah memiliki Ticket dilewati.
>
> **Technical Reference:**
> - `TicketController::showTicketDetail`
> - `addTaskAssignTo`
> - `saveTicketUpdate`
> - `saveTicketMessage`
> - `openTabTicketDetail(Id, 'ticket-center', 'Case Detail', 'Ticket/showTicketDetail', 'POST')`
>
> **Out of Scope:**
> - Membuat workflow Ticket baru.
> - Membuat tabel assignment atau note khusus VoC.
> - Reply langsung ke Google Business Review.
> - Mengubah hasil AI dari halaman Review Detail.

#### Subtask 1

**Summary**

`VOC - Review Manage Actions - Implement Review Detail`

**Description**

> Implementasikan halaman atau panel Review Detail yang dapat dibuka dari daftar Ulasan.
>
> **Scope:**
> - Gunakan `id` dari `reviewsDataAction` sebagai `Ticket.Id`.
> - Tampilkan teks review lengkap, rating, sentiment, urgency, kategori, summary, dan recommended action.
> - Tampilkan lokasi, source, dan waktu review apabila tersedia.
> - Tampilkan link atau tombol untuk membuka Ticket OneBox.
> - Tangani data analisis yang kosong atau belum selesai.
> - Escape seluruh konten review yang berasal dari sumber eksternal.
>
> **Acceptance Criteria:**
> - Klik satu review membuka detail yang benar.
> - Seluruh field yang tersedia dapat ditampilkan.
> - Field kosong memiliki placeholder yang konsisten.
> - Teks review tidak dapat mengeksekusi HTML atau JavaScript.
> - User dapat membuka Ticket OneBox terkait.
> - Error ketika memuat detail ditampilkan dengan pesan yang jelas.

#### Subtask 2

**Summary**

`VOC - Review Manage Actions - Implement Assign, Resolve, and Internal Note`

**Description**

> Tambahkan aksi assign, perubahan status, dan internal note dari Review Detail menggunakan mekanisme Ticket OneBox yang sudah tersedia.
>
> **Scope:**
> - Tambahkan aksi assign kepada agent.
> - Tambahkan aksi perubahan status sesuai workflow Ticket.
> - Tambahkan form internal note.
> - Gunakan service dan endpoint Ticket OneBox yang sudah tersedia.
> - Terapkan permission yang sama dengan Ticket OneBox.
>
> **Acceptance Criteria:**
> - User yang berwenang dapat memilih agent dan menyimpan assignment.
> - Assignment terbaru ditampilkan setelah penyimpanan berhasil.
> - Status Ticket dapat diubah mengikuti transition yang valid.
> - Internal note tersimpan pada histori Ticket.
> - Aksi yang berhasil langsung tercermin pada Review Detail.
> - Aksi yang gagal tidak mengubah Ticket secara parsial.
> - User tanpa permission tidak dapat menjalankan action.
> - Tidak ada workflow baru yang menduplikasi mekanisme Ticket OneBox.

#### Subtask 3

**Summary**

`VOC - Review Manage Actions - Reconcile Legacy Reviews Without Tickets`

**Description**

> Rekonsiliasi review lama yang sudah tersedia dari Crawler atau sudah menjadi Message OneBox, tetapi belum memiliki Ticket OneBox yang dapat dikelola pada halaman Ulasan.
>
> **Pembagian tanggung jawab:**
> - DNGO19-3420 menarik review lama, menjalankan delta/catch-up, dan menghasilkan counter hasil import.
> - DNGO19-3387 memproses Message yang belum memiliki Ticket, lalu memastikan Ticket dapat dibuka dan dikelola melalui Review Detail.
>
> **Scope:**
> - Identifikasi Message review VoC aktif yang belum terhubung ke Ticket.
> - Buat Ticket menggunakan pipeline/provider OneBox yang sudah tersedia.
> - Hubungkan Message, Ticket, lokasi, dan metadata hasil analisis yang tersedia.
> - Lewati review yang sudah memiliki Ticket.
> - Sediakan counter `processed`, `created`, `deduped/skipped`, dan `failed`.
> - Catat error per review dengan informasi aman untuk troubleshooting.
>
> **Acceptance Criteria:**
> - Review lama tanpa Ticket dapat dibuat menjadi Ticket OneBox.
> - Review yang sudah memiliki Ticket tidak menghasilkan Ticket kedua.
> - Ticket hasil rekonsiliasi dapat dibuka dari daftar Ulasan dan memakai aksi manage yang sama.
> - Kegagalan sebagian dapat di-retry tanpa mengulang item yang sudah sukses.
> - Hasil rekonsiliasi memiliki counter dan error summary yang dapat ditelusuri.
>
> **Status audit 3 Agustus 2026:**
> - `feature/voc` sudah memiliki pemrosesan pending Message menjadi Ticket pada flow sync. Skenario review historis, retry, counter, dan contoh kasus lokasi lama masih perlu functional verification/QA.

### DNGO19-3388 — AI Analysis Setup

- **Owner:** OneBox (OB) · **Status:** READY TO DEV · **MD:** 4 MD

#### Description

> Menyediakan pengaturan integrasi AI di OneBox tanpa mengambil alih keputusan teknis milik Crawler. OneBox mengatur apakah analisis AI digunakan untuk suatu tenant/Connection, mendefinisikan struktur output yang wajib dikembalikan, dan memastikan hasil tersebut dapat dipakai secara konsisten oleh Review Detail, AI Insights, dan Report.
>
> **Keputusan ownership:**
> - **Crawler:** memilih model/provider, prompt runtime, batching, retry, dan cara eksekusi analisis.
> - **OneBox:** mengatur enable/disable, kebutuhan output, validasi struktur response, default/fallback tampilan, serta penggunaan hasil analisis dalam workflow OneBox.
>
> **Scope:**
> - Menentukan kontrak `ai_enabled` dan `output_schema_version` beserta default yang aman.
> - Menentukan struktur output minimum: `analysis_status`, `sentiment`, `urgency`, `issue_category`, `summary`, `recommended_action`, `analyzed_at`, dan informasi error yang aman bila analisis gagal.
> - Menampilkan pengaturan yang menjadi wewenang OneBox pada halaman AI Analysis Setup.
> - Menyimpan pengaturan OneBox tanpa menimpa option Connection lainnya.
> - Mengirim `ai_enabled` dan versi kontrak output melalui worklist atau kontrak integrasi yang disepakati.
> - Menangani Connection lama yang belum memiliki konfigurasi AI.
> - Memvalidasi output Crawler sebelum hasil ditampilkan atau digunakan oleh feature OneBox.
> - Menjalankan klasifikasi bisnis berbasis `Service\Ruling` pada pipeline OneBox tanpa membuat sistem rule baru dan tanpa menentukan model Crawler.
>
> **Acceptance Criteria:**
> - Admin dapat mengaktifkan atau menonaktifkan analisis AI.
> - Admin tidak perlu dan tidak dapat memilih model/provider Crawler dari scope OneBox ini.
> - Pengaturan OneBox divalidasi sebelum disimpan dan tersimpan pada scope tenant/Connection yang benar.
> - Worklist atau kontrak integrasi mengirim `ai_enabled` dan `output_schema_version` menggunakan nama dan tipe data yang disepakati.
> - Connection lama menggunakan nilai default yang aman.
> - Menonaktifkan AI tidak menghentikan proses crawl.
> - Output Crawler yang valid dapat dibaca dengan struktur yang sama oleh Review Detail, AI Insights, dan Report.
> - Output tidak valid atau gagal tidak ditampilkan sebagai hasil final; status dan fallback-nya jelas.
> - `Service\Ruling` diterapkan pada pipeline bisnis OneBox tanpa mengubah model atau prompt runtime Crawler.
>
> **Out of Scope:**
> - Pemilihan model/provider AI.
> - Pengaturan prompt runtime dan parameter inferensi Crawler.
> - Antrean analisis AI di Crawler.
> - Perhitungan `tokens_used`.
> - Perbaikan koneksi LLM lokal.
> - Perbaikan prompt kategori.
> - Halaman hasil AI Insights.

#### Subtask 1

**Summary**

`VOC - AI Analysis Setup - Define AI Ownership and Output Contract`

**Description**

> Definisikan batas tanggung jawab OneBox dan Crawler serta kontrak output analisis yang stabil untuk seluruh feature OneBox.
>
> **Scope:**
> - Dokumentasikan bahwa model, provider, prompt runtime, dan strategi eksekusi dipilih oleh Crawler.
> - Tentukan tipe data dan default untuk `ai_enabled` dan `output_schema_version`.
> - Definisikan field output minimum: status, sentiment, urgency, category, summary, recommended action, waktu analisis, dan error metadata yang aman.
> - Tentukan enum/nilai yang diperbolehkan untuk sentiment, urgency, dan status analisis.
> - Tentukan perilaku ketika field belum tersedia, output tidak valid, atau versi schema belum dikenali.
> - Tentukan perilaku ketika `ai_enabled=false`.
>
> **Acceptance Criteria:**
> - Matriks ownership OneBox dan Crawler terdokumentasi dan disepakati kedua tim.
> - Nama, tipe data, enum, versi, serta field wajib/opsional pada output terdokumentasi.
> - Nilai default dan perilaku Connection lama disepakati.
> - Tidak ada model atau prompt runtime yang dikunci oleh konfigurasi OneBox.
> - Tim OneBox dan Crawler menggunakan kontrak yang sama.

#### Subtask 2

**Summary**

`VOC - AI Analysis Setup - Persist AI Policy and Validate Crawler Output`

**Description**

> Implementasikan pengaturan AI yang menjadi wewenang OneBox, distribusikan flag dan versi kontrak, lalu validasi output Crawler sebelum digunakan feature lain.
>
> **Scope:**
> - Tampilkan dan simpan `ai_enabled` serta `output_schema_version` pada tempat konfigurasi yang disepakati.
> - Muat pengaturan ketika halaman dibuka kembali.
> - Sertakan flag dan versi kontrak pada response worklist/integrasi.
> - Terapkan default untuk Connection yang belum memiliki konfigurasi.
> - Validasi field wajib dan enum hasil analisis dari Crawler.
> - Simpan atau tampilkan `analysis_status` yang jelas untuk completed, pending, failed, skipped, dan invalid output.
>
> **Acceptance Criteria:**
> - Pengaturan dapat disimpan, diedit, dan dibaca kembali.
> - Update pengaturan AI tidak menghapus option Connection lainnya.
> - Worklist/integrasi mengembalikan flag dan versi kontrak sesuai kesepakatan.
> - Connection lama mendapatkan default yang aman.
> - Output valid dapat dipakai oleh feature OneBox tanpa mapping berbeda-beda.
> - Output invalid/gagal memiliki status jelas dan tidak dianggap completed.
> - API key atau credential tidak ikut dikirim sebagai parameter konfigurasi.

#### Subtask 3

**Summary**

`VOC - AI Analysis Setup - Apply Rule-First Classification`

**Description**

> Integrasikan klasifikasi bisnis berbasis `Service\Ruling` pada pipeline OneBox setelah data review diterima, tanpa mengambil alih proses analisis atau pemilihan model di Crawler.
>
> **Scope:**
> - Gunakan `Service\Ruling` yang sudah tersedia.
> - Jalankan rule pada titik pipeline OneBox yang disepakati sebelum hasil dipakai untuk keputusan workflow/Ticket.
> - Gunakan struktur hasil klasifikasi yang konsisten.
> - Pastikan alur pembuatan Ticket tetap berfungsi ketika AI dinonaktifkan.
>
> **Acceptance Criteria:**
> - `Service\Ruling` dijalankan pada pipeline OneBox sesuai urutan yang disepakati.
> - Tidak dibuat service ruling baru yang menduplikasi implementasi existing.
> - Hasil rule tersimpan atau diteruskan menggunakan struktur yang disepakati.
> - Proses Ticket tetap berfungsi ketika AI tidak aktif.
>
> **Status audit 3 Agustus 2026:**
> - Branch 3388 belum memiliki implementasi unik dan halaman AI Analysis di `feature/voc` masih memakai data/aksi simulasi. Seluruh subtask di atas masih perlu implementasi dan pengujian.

### DNGO19-3407 — Enhance AI Analysis

- **Suggested Summary:** `VOC : Enhance AI Analysis`
- **Owner:** Sayyid
- **Status:** TODO
- **Current Jira Work Type:** Task
- **Recommended Jira Work Type:** New Feature
- **Repository:** `onecloud` (OneBox)
- **Base Branch:** `feature/voc`
- **Branch:** `feature/DNGO19-3407_VOC-Enhance-AI-Analysis`

#### Description

> Meningkatkan performa, kualitas, efisiensi, dan reliability proses AI Analysis yang saat ini masih membutuhkan waktu lama.
>
> Pekerjaan mencakup evaluasi alur integrasi analisis, pengurangan request yang tidak diperlukan, validasi output, dan monitoring dari sisi OneBox. Evaluasi serta pemilihan model tetap dikerjakan dan diputuskan oleh tim Crawler.
>
> **OneCloud Boundary:**
> - Branch DNGO19-3407 di OneCloud menangani orchestration integrasi, pemilihan review yang perlu diminta hasilnya, pengurangan request berulang, validasi response, kompatibilitas schema, dan monitoring dari sisi OneBox.
> - Pemilihan model/provider, prompt runtime, batching inference, serta perubahan runtime Python tetap berada di service VoC/Crawler. Buat linked work item dan branch Crawler terpisah untuk pekerjaan tersebut; jangan memasukkan perubahan dua repository ke branch OneCloud ini.
>
> **Scope:**
> - Ukur baseline proses AI Analysis saat ini, termasuk queue time, waktu proses per review/batch, waktu respons API, jumlah token, error rate, dan jumlah retry.
> - Identifikasi bottleneck pada antrean, preprocessing, pemanggilan API AI, parsing response, dan penyimpanan hasil.
> - Optimalkan logika pemanggilan API agar hanya review yang baru, berubah, atau belum memiliki hasil valid yang dianalisis.
> - Terapkan idempotency dan deduplication agar retry atau trigger berulang tidak menghasilkan pemanggilan API dan pencatatan usage ganda.
> - Evaluasi timeout, retry, backoff, caching, dan idempotency pada pemanggilan OneBox ke service Crawler.
> - Koordinasikan benchmark model melalui linked work item Crawler; OneBox menerima hasil keputusan dan memvalidasi kompatibilitas outputnya.
> - Validasi dan normalisasi response agar tetap mengikuti schema sentiment, urgency, category, summary, dan recommended action.
> - Tambahkan monitoring untuk durasi integrasi, jumlah request, retry, failure, schema version, dan metadata model yang dilaporkan Crawler tanpa menjadikannya konfigurasi pilihan OneBox.
> - Sediakan fallback tampilan/proses ketika output tidak valid atau service analisis bermasalah.
>
> **Acceptance Criteria:**
> - Baseline performa dan bottleneck proses AI Analysis terdokumentasi.
> - Target improvement untuk latency, throughput, error rate, dan token usage disepakati sebelum implementasi optimasi.
> - Tim Crawler mendokumentasikan pemilihan model berdasarkan benchmark menggunakan dataset review yang representatif; OneBox menyetujui kompatibilitas struktur outputnya.
> - Proses setelah optimasi menunjukkan improvement terukur dibandingkan baseline berdasarkan target yang disepakati.
> - Review yang sudah memiliki hasil valid tidak dianalisis ulang tanpa alasan yang jelas.
> - Retry tidak menghasilkan duplicate analysis, duplicate API call yang tidak diperlukan, atau duplicate usage record.
> - Error yang dapat di-retry menggunakan retry dan backoff; error permanen tidak diulang tanpa batas.
> - Response model divalidasi sebelum disimpan.
> - Output tetap kompatibel dengan field sentiment, urgency, category, summary, dan recommended action yang digunakan OneBox.
> - OneBox dapat menonaktifkan penggunaan AI atau menangani output gagal tanpa menentukan model fallback Crawler.
> - Log tidak menyimpan API key, credential, atau teks review lengkap.
>
> **Dependency:**
> - Kontrak ownership dan struktur output AI dari DNGO19-3388.
> - Antrean analisis AI di Crawler.
> - Data `tokens_used` dan status analisis.
> - Dataset review representatif untuk benchmark kualitas.
>
> **Out of Scope:**
> - Perubahan tampilan AI Insights.
> - Perubahan halaman AI Analysis Setup di OneBox, kecuali diperlukan penyesuaian kontrak output.
> - Perubahan runtime/model Python, queue worker, atau provider client di repository Crawler; pekerjaan tersebut harus menggunakan linked work item terpisah.
> - Training custom model dari awal tanpa persetujuan Product dan technical review.
> - Perubahan kategori bisnis tanpa persetujuan Product.

#### Subtask 1

**Summary**

`Dev Specification - VOC - Enhance AI Analysis`

**Description**

> Analisis proses AI Analysis yang berjalan saat ini dan tentukan target optimasi yang terukur.
>
> **Scope:**
> - Petakan alur dari review masuk sampai hasil AI tersimpan.
> - Ukur queue time, processing time, API latency, token usage, retry, dan error rate.
> - Identifikasi bottleneck utama.
> - Tentukan dataset benchmark yang mewakili variasi rating, sentiment, urgency, kategori, dan panjang review.
> - Tentukan target latency, throughput, error rate, dan token usage.
> - Dokumentasikan rencana perubahan dan risiko kompatibilitas.
>
> **Acceptance Criteria:**
> - Baseline performa tersedia dan dapat direproduksi.
> - Bottleneck utama teridentifikasi berdasarkan evidence.
> - Dataset benchmark dan metode penilaian disepakati.
> - Target optimasi disetujui sebelum implementation dimulai.
> - Batas scope antara optimasi Crawler dan konfigurasi OneBox terdokumentasi.

#### Subtask 2

**Summary**

`VOC - Enhance AI Analysis - Optimize Processing and API Call Flow`

**Description**

> Optimalkan alur pemrosesan AI dan logika pemanggilan API agar proses lebih cepat, efisien, dan tidak melakukan request yang tidak diperlukan.
>
> **Scope:**
> - Analisis hanya review baru, berubah, atau belum memiliki hasil valid.
> - Tambahkan idempotency dan deduplication untuk analysis job dan API request.
> - Evaluasi penggunaan batch request apabila didukung provider.
> - Atur concurrency dan rate limit agar throughput meningkat tanpa melampaui kapasitas provider.
> - Terapkan timeout, retry terbatas, exponential backoff, dan error classification.
> - Pastikan status analysis hanya menjadi completed setelah response tervalidasi dan hasil berhasil disimpan.
>
> **Acceptance Criteria:**
> - Trigger atau retry berulang tidak membuat analysis record ganda.
> - Review dengan hasil valid tidak memanggil API kembali tanpa explicit rerun.
> - Timeout dan error sementara di-retry sesuai policy.
> - Error permanen tidak di-retry tanpa batas.
> - Analysis yang gagal tidak ditandai completed.
> - Throughput dan latency memenuhi target yang ditentukan pada Dev Specification.
> - Token dan usage tidak tercatat ganda.

#### Subtask 3

**Summary**

`VOC - Enhance AI Analysis - Coordinate Model Benchmark and Validate Output Compatibility`

**Description**

> Koordinasikan benchmark model yang dikerjakan oleh tim Crawler, lalu validasi bahwa model yang mereka pilih tetap menghasilkan output yang kompatibel dengan kebutuhan OneBox.
>
> **Scope:**
> - Buat linked work item Crawler untuk baseline, kandidat model, benchmark, dan pemilihan model/fallback.
> - Sepakati dataset serta indikator kualitas bisnis yang perlu dipertahankan.
> - Terima hasil benchmark kualitas, latency, token usage, error rate, kebutuhan resource, dan biaya dari tim Crawler.
> - Uji output model terpilih terhadap schema OneBox.
> - Pastikan perubahan model tidak mengharuskan OneBox menyimpan konfigurasi runtime Crawler.
> - Dokumentasikan metadata model yang boleh dikirim sebagai informasi read-only untuk audit/monitoring.
>
> **Acceptance Criteria:**
> - Linked work item Crawler tersedia dan memiliki owner yang jelas.
> - Model existing dan kandidat diuji oleh tim Crawler menggunakan dataset yang sama.
> - Hasil benchmark terdokumentasi dan keputusan model dibuat oleh tim Crawler berdasarkan evidence.
> - Output model terpilih lolos validasi schema OneBox.
> - Penurunan kualitas yang signifikan tidak diterima hanya untuk mengejar kecepatan.
> - Pergantian model di Crawler tidak mengubah data historis dan tidak memerlukan field output baru tanpa versioning.
> - Perubahan runtime/model di Crawler tidak dimasukkan ke branch OneCloud DNGO19-3407.

#### Subtask 4

**Summary**

`VOC - Enhance AI Analysis - Add Monitoring, Reliability, and Rollback`

**Description**

> Tambahkan observability dan mekanisme pengamanan agar integrasi AI Analysis dapat dipantau. Rollback model/runtime tetap dilakukan oleh Crawler, sedangkan OneBox dapat menonaktifkan penggunaan AI atau kembali ke alur integrasi sebelumnya.
>
> **Scope:**
> - Catat metrik yang dikirim Crawler: durasi antrean/proses, API latency, jumlah request, retry, failure, token usage, dan metadata model read-only.
> - Tambahkan correlation ID atau analysis job ID untuk menelusuri satu proses tanpa menyimpan data sensitif.
> - Tambahkan alert atau indikator untuk failure rate tinggi, antrean menumpuk, atau latency melewati target.
> - Sediakan feature flag OneBox untuk menonaktifkan penggunaan AI/flow baru; dokumentasikan bahwa rollback model dilakukan pada linked work item Crawler.
>
> **Acceptance Criteria:**
> - Metrik utama dapat dipantau per run atau periode.
> - Failure dapat ditelusuri menggunakan job/correlation ID.
> - Log tidak memuat API key, credential, atau teks review lengkap.
> - Kondisi antrean menumpuk dan error rate tinggi dapat diketahui sebelum dilaporkan user.
> - Penggunaan AI atau flow integrasi baru dapat dinonaktifkan tanpa menghapus hasil historis; model dipulihkan oleh tim Crawler bila diperlukan.
> - Prosedur rollback terdokumentasi dan berhasil diuji.

### DNGO19-3420 — Fetch Jobs Crawl

- **Suggested Summary:** `VOC : Fetch Jobs Crawl`
- **Jira Work Type:** New Feature
- **Owner:** Sayyid
- **Status:** TODO
- **Repository:** `onecloud` (OneBox)
- **Base Branch:** `feature/voc`
- **Branch:** `feature/DNGO19-3420_VOC-Fetch-Jobs-Crawl`

#### Description

> Menyediakan Fetch Jobs Crawl di OneBox untuk menjalankan proses scraping review melalui service Crawler yang terkontrol, sehingga OneBox tidak menjalankan Selenium atau connector scraping secara langsung.
>
> Feature ini menjadi entry point standar untuk menjalankan crawl satu lokasi atau beberapa lokasi aktif, memantau status proses, dan melihat hasil fetch berupa jumlah review yang ditemukan, disimpan, terdeteksi duplikat, atau gagal.
>
> **Scope:**
> - Sediakan service/client OneCloud untuk mengirim request crawl review ke Crawler.
> - Dukung crawl untuk satu lokasi.
> - Dukung crawl untuk seluruh lokasi aktif apabila disetujui dalam Dev Specification.
> - Terima parameter minimum berupa location, source/connector, target review count, dan dry run.
> - Validasi bahwa lokasi aktif, memiliki company/tenant, dan dapat diakses oleh user atau service pemanggil.
> - Kirim request pembuatan crawl job ke service Crawler.
> - Pastikan controller atau UI OneBox hanya memanggil service/client OneCloud, bukan memanggil Selenium atau connector secara langsung.
> - Gunakan proses non-blocking agar request tidak menunggu Selenium selesai.
> - Kembalikan `job_id` atau `batch_id` agar status proses dapat dipantau.
> - Simpan status job: queued, running, success, partial_success, failed, atau cancelled apabila cancel didukung.
> - Simpan hasil proses berupa fetched, inserted, duplicate/deduped, dan failed.
> - Setelah crawl selesai, jalankan atau hubungkan proses sinkronisasi review sesuai mekanisme delta yang telah disepakati.
> - Kelola safe checkpoint/cursor agar delta sync hanya maju setelah seluruh halaman berhasil diproses.
> - Dukung catch-up/reconciliation untuk review lama yang belum masuk OneBox, kemudian teruskan Message tanpa Ticket ke flow DNGO19-3387.
> - Catat error dan metadata teknis yang aman untuk troubleshooting.
> - Sediakan fetch log atau job detail untuk melihat hasil proses.
>
> **Acceptance Criteria:**
> - Pemanggil dapat membuat Fetch Job untuk satu lokasi aktif.
> - Request mengembalikan `job_id` atau `batch_id` tanpa menunggu seluruh proses scraping selesai.
> - Scraping dijalankan oleh service Crawler; UI dan controller OneBox hanya memanggil service/client OneCloud.
> - Lokasi yang tidak aktif, tidak valid, atau berada di tenant lain ditolak.
> - Job memiliki status yang dapat dipantau dari awal sampai selesai.
> - Hasil job mencatat jumlah review fetched, inserted, deduped, dan failed.
> - Job yang diulang tidak menyebabkan review tersinkron menjadi Ticket ganda.
> - Checkpoint hanya maju setelah seluruh halaman dan review pada siklus tersebut berhasil diproses.
> - Review lama dapat ditarik ulang secara aman dan item yang sudah ada dihitung sebagai duplicate/deduped.
> - Dry run tidak menyimpan review atau mengubah data produksi.
> - Error pada satu lokasi tidak menyebabkan status lokasi lain menjadi tidak jelas.
> - Timeout dan error sementara ditangani menggunakan retry policy yang terbatas.
> - API key, credential, session, dan raw review text tidak ditampilkan pada log.
>
> **Dependency:**
> - Location/worklist telah tersedia dan ter-scope berdasarkan tenant.
> - Endpoint crawl job pada Crawler tersedia dan dapat diakses dari environment OneBox.
> - Queue, worker, dan connector scraping tersedia di sisi Crawler untuk proses non-blocking.
> - Kunci idempotency review telah ditentukan.
>
> **Out of Scope:**
> - Penjadwalan otomatis tiga window; ditangani DNGO19-3390 Crawl Scheduler.
> - Penentuan lokasi baru yang perlu targeted backfill; trigger-nya ditangani DNGO19-3385, sedangkan mekanisme pull aman tetap memakai flow DNGO19-3420.
> - Pembuatan/aksi kelola Ticket dari Message review hasil rekonsiliasi; ditangani DNGO19-3387.
> - Implementasi queue, worker, Selenium, atau connector scraping di Crawler.
> - AI Analysis setelah review tersimpan.
> - Tampilan AI Insights.
> - Competitor Analysis.

#### Subtask 1

**Summary**

`Dev Specification - VOC - Fetch Jobs Crawl`

**Description**

> Finalisasi kontrak, lifecycle, dan boundary Fetch Jobs Crawl sebelum development.
>
> **Scope:**
> - Tentukan request dan response untuk membuat crawl job.
> - Tentukan penggunaan `job_id` atau `batch_id`.
> - Tentukan status lifecycle job.
> - Tentukan parameter location, source, target review count, dry run, dan date range apabila diperlukan.
> - Tentukan aturan fetch satu lokasi dan fetch seluruh lokasi aktif.
> - Tentukan retry, timeout, cancellation, dan idempotency policy.
> - Tentukan hubungan antara crawl job dan fetch log.
>
> **Acceptance Criteria:**
> - Kontrak request dan response terdokumentasi.
> - Status lifecycle dan transition job terdokumentasi.
> - Aturan tenant, permission, dan validasi lokasi disepakati.
> - Batas target review dan quota disepakati.
> - Perilaku dry run disepakati.
> - Dependency terhadap queue, worker, dan connector terdokumentasi.
> - Scope mendapatkan approval sebelum implementasi dimulai.

#### Subtask 2

**Summary**

`VOC - Fetch Jobs Crawl - Implement OneCloud Fetch Job Service Client`

**Description**

> Implementasikan service/client di OneCloud untuk membuat Fetch Job melalui API Crawler secara non-blocking.
>
> **Scope:**
> - Validasi tenant, lokasi, status aktif, source, target review count, dan dry run.
> - Bentuk request sesuai kontrak API Crawler.
> - Kirim request crawl melalui client/service OneCloud.
> - Terima dan simpan `job_id` atau `batch_id` dari Crawler.
> - Simpan status awal job di OneBox untuk kebutuhan monitoring.
> - Terapkan idempotency agar request yang sama tidak membuat job ganda secara tidak sengaja.
>
> **Acceptance Criteria:**
> - Request valid diteruskan ke service Crawler dan menghasilkan job queued.
> - OneBox menerima response tanpa menunggu Selenium selesai.
> - Request invalid tidak membuat job.
> - Lokasi tenant lain tidak dapat diproses.
> - Duplicate request ditangani sesuai idempotency policy.
> - Credential dan konfigurasi internal tidak dikembalikan pada response.

#### Subtask 3

**Summary**

`VOC - Fetch Jobs Crawl - Implement Trigger and Review Sync Orchestration`

**Description**

> Implementasikan orchestration di OneBox untuk memicu crawl melalui service Crawler, memantau penyelesaiannya, dan melanjutkan sinkronisasi review.
>
> **Scope:**
> - Sediakan trigger Fetch Job dari flow OneBox yang telah disepakati.
> - Pantau status `job_id` atau `batch_id` sampai mencapai status terminal.
> - Simpan pembaruan status dan counters dari Crawler.
> - Setelah crawl berhasil atau partial success, jalankan proses delta pull/sinkronisasi review sesuai kontrak.
> - Pastikan dry run tidak menjalankan penyimpanan atau sinkronisasi review.
> - Tangani job gagal tanpa memajukan checkpoint secara tidak aman.
> - Simpan `checkpoint_cursor` hanya setelah siklus halaman selesai tanpa kegagalan.
> - Simpan posisi sementara secara aman apabila proses berhenti sebelum seluruh halaman selesai.
>
> **Acceptance Criteria:**
> - Satu trigger OneBox menghasilkan satu job Crawler sesuai idempotency policy.
> - OneBox tidak menjalankan Selenium atau connector secara langsung.
> - Status dan counters job tetap konsisten untuk success, partial success, dan failed.
> - Delta pull hanya dijalankan setelah hasil crawl siap.
> - Review yang sudah tersinkron tidak dibuat menjadi Ticket ganda.
> - Dry run tidak menyimpan atau menyinkronkan review.
> - Job gagal tidak memajukan checkpoint.
> - Kegagalan pemrosesan review menyebabkan siklus berikutnya mengulang dari checkpoint aman terakhir.

#### Subtask 4

**Summary**

`VOC - Fetch Jobs Crawl - Implement Job Status, Logs, Retry, and Cancel`

**Description**

> Sediakan halaman/endpoint OneBox untuk memantau dan mengelola Fetch Job yang dijalankan melalui service Crawler.
>
> **Scope:**
> - Sediakan detail status berdasarkan `job_id` atau `batch_id`.
> - Tampilkan started time, finished time, duration, status, counters, dan error summary.
> - Teruskan retry untuk job gagal ke service Crawler sesuai retry policy.
> - Teruskan cancel untuk job queued atau running apabila API Crawler mendukung cancellation yang aman.
> - Pastikan retry menggunakan job atau idempotency context yang sama.
>
> **Acceptance Criteria:**
> - Status job dapat dilihat dari queued sampai terminal.
> - Detail job hanya dapat diakses tenant yang berhak.
> - Retry tidak membuat review atau usage ganda.
> - Job yang tidak retryable ditolak ketika diminta retry.
> - Cancel tidak meninggalkan job pada status running tanpa batas.
> - Log tidak memuat credential atau raw review text lengkap.

#### Subtask 5

**Summary**

`VOC - Fetch Jobs Crawl - Reconcile and Import Legacy Reviews`

**Description**

> Gunakan flow Fetch Jobs/delta import untuk menarik review historis yang belum tersedia di OneBox, termasuk lokasi lama yang sebelumnya belum menghasilkan Ticket.
>
> **Pembagian tanggung jawab:**
> - DNGO19-3420 mengambil review dari Crawler, melakukan deduplication, menyimpan Message, dan melaporkan counter.
> - DNGO19-3387 memproses Message tanpa Ticket agar dapat dikelola melalui Review Detail.
>
> **Scope:**
> - Tentukan lokasi dan periode yang perlu direkonsiliasi.
> - Jalankan pull berbasis lokasi/periode atau catch-up dari checkpoint aman.
> - Gunakan kunci idempotency/deduplication review yang sama dengan delta reguler.
> - Laporkan `fetched`, `inserted`, `deduped`, `failed`, dan jumlah Message yang masih menunggu Ticket.
> - Dukung retry/resume tanpa menarik ulang seluruh data yang sudah sukses bila tidak diperlukan.
>
> **Acceptance Criteria:**
> - Review historis yang belum ada dapat masuk sebagai Message OneBox.
> - Review yang sudah ada dilewati dan dihitung sebagai deduped, bukan dibuat ulang.
> - Kegagalan sebagian tidak memajukan checkpoint secara tidak aman.
> - Retry/resume tidak membuat Message atau Ticket ganda.
> - Message tanpa Ticket dapat diteruskan ke flow rekonsiliasi DNGO19-3387.
> - Hasil per lokasi dan ringkasan error dapat ditelusuri.
>
> **Status audit 3 Agustus 2026:**
> - `feature/voc` sudah memiliki enqueue crawl, polling batch, import, deduplication, pemrosesan pending Message, dan safe checkpoint. Branch 3420 masih memiliki 2 commit tambahan; perlu review/merge serta QA skenario legacy review dan retry/resume.

### DNGO19-3389 — AI Insights

- **Owner:** OneBox (OB) · **Status:** TODO · **MD:** 3 MD

#### Description

> Menyediakan halaman AI Insights agar user dapat membaca dan memfilter hasil analisis AI yang telah selesai diproses.
>
> **Scope:**
> - Menampilkan daftar hasil analisis AI berupa sentiment, urgency, kategori, summary, dan recommended action.
> - Menyediakan filter berdasarkan rentang tanggal, lokasi, sentiment, urgency, dan kategori.
> - Menyediakan paging dan filtering di server.
> - Menyediakan akses dari hasil Insight ke Review Detail.
> - Menampilkan status yang jelas untuk analisis yang belum selesai atau gagal.
>
> **Acceptance Criteria:**
> - Halaman hanya membaca hasil analisis dan tidak menjalankan proses AI.
> - User dapat memfilter hasil berdasarkan filter yang telah disepakati.
> - Paging dilakukan di server, bukan di browser.
> - User hanya dapat melihat data tenant-nya.
> - User dapat membuka Review Detail dari hasil Insight.
> - Data yang belum selesai dianalisis tidak ditampilkan sebagai hasil final.
> - Analisis gagal dan field hasil AI yang kosong memiliki status yang jelas.
>
> **Dependency:**
> - DNGO19-3388 AI Analysis Setup.
> - Data hasil analisis dari Crawler.
> - Struktur menu VoC pada `feature/voc` telah lolos verifikasi fungsi, route, urutan, dan permission.
>
> **Out of Scope:**
> - Trigger dan rerun analisis.
> - Konfigurasi model atau prompt.
> - Perbaikan kualitas output AI.
> - Pengeditan manual hasil AI.

#### Subtask 1

**Summary**

`Dev Specification - VOC - AI Insights`

**Description**

> Finalisasi kebutuhan halaman AI Insights sebelum development.
>
> **Scope:**
> - Tentukan field, filter, default rentang tanggal, dan sorting.
> - Tentukan status `pending`, `completed`, `failed`, dan `skipped`.
> - Tentukan apakah MVP hanya berupa list atau membutuhkan KPI/chart.
> - Buat wireframe atau referensi tampilan.
> - Dokumentasikan mapping data Crawler ke field OneBox.
>
> **Acceptance Criteria:**
> - Field, filter, default periode, dan sorting disetujui Product.
> - Status analisis dan mapping data terdokumentasi.
> - Wireframe atau contoh tampilan tersedia.
> - Scope implementasi mendapatkan approval Product.

#### Subtask 2

**Summary**

`VOC - AI Insights - Implement Insights Page`

**Description**

> Implementasikan halaman AI Insights berdasarkan Dev Specification yang telah disetujui.
>
> **Scope:**
> - Implementasikan query hasil analisis.
> - Implementasikan filter dan paging server-side.
> - Tampilkan sentiment, urgency, kategori, summary, recommended action, dan status analisis.
> - Tambahkan link ke Review Detail.
> - Tambahkan loading, empty, dan error state.
>
> **Acceptance Criteria:**
> - Data yang ditampilkan sesuai tenant aktif.
> - Filter menghasilkan data yang benar dan paging dilakukan di server.
> - User dapat membuka Review Detail.
> - Loading, empty, dan error state tersedia.
> - Data pending atau failed tidak ditampilkan sebagai hasil completed.

### DNGO19-3390 — Crawl Scheduler

- **Owner:** OneBox (OB)
- **Status:** TODO
- **MD:** hingga 8 MD
- **Catatan estimasi:** estimasi diletakkan pada dua subtask implementasi agar tidak terjadi double counting pada parent.

#### Description

> Menyediakan scheduler otomatis di OneBox untuk menjalankan crawl tiga kali sehari per site tanpa menjalankan Selenium secara blocking dan tanpa menghasilkan run ganda.
>
> **Scope:**
> - Membuat tiga schedule occurrence per site per tanggal lokal: pagi 05:00–06:59, siang 11:00–12:59, dan malam 21:00–22:59.
> - Menghasilkan `planned_at` secara acak dalam setiap window dan menyimpannya agar tidak berubah setelah restart atau retry.
> - Menggunakan timezone site dengan default `Asia/Jakarta`.
> - Menjalankan crawl melalui endpoint enqueue non-blocking.
> - Menggunakan idempotency key `site:local_date:slot`.
> - Mencegah lebih dari satu run aktif pada site dan slot yang sama.
> - Menyimpan histori planned time, actual time, status, dan counters.
> - Menyediakan tombol `Run now` untuk user yang berwenang.
>
> **Acceptance Criteria:**
> - Setiap site aktif memiliki tepat tiga occurrence per tanggal lokal.
> - `planned_at` berada pada window yang benar dan tidak berubah setelah restart.
> - Dua trigger bersamaan hanya menghasilkan satu run.
> - Trigger crawl menerima `batch_id` tanpa menunggu Selenium selesai.
> - Run memiliki status `planned`, `running`, `success`, `partial_success`, `failed`, atau `skipped`.
> - Counter `fetched`, `inserted`, `deduped`, dan `failed` tersimpan.
> - User berwenang dapat menjalankan `Run now`.
> - Manual run tidak merusak occurrence terjadwal.
> - Credential, token, cursor utuh, dan raw review text tidak ditampilkan pada histori.
>
> **Dependency:**
> - Endpoint enqueue non-blocking dan worker crawl di Crawler.
> - Endpoint atau mekanisme monitoring status batch.
> - Delta Sync dan safe checkpoint pada DNGO19-3420.
>
> **Out of Scope:**
> - Membuat scheduler kedua di Crawler.
> - Implementasi worker Selenium.
> - Implementasi checkpoint delta dan targeted backfill.

#### Subtask 1

**Summary**

`VOC - Crawl Scheduler - Implement Scheduler Core and Concurrency Control`

**Description**

> Implementasikan schedule occurrence, random persistent planning, timezone, locking, dan idempotency.
>
> **Scope:**
> - Buat tabel schedule occurrence dengan unique constraint untuk `site_id`, `local_date`, dan `slot`.
> - Buat tiga occurrence per hari untuk setiap site aktif.
> - Generate `planned_at` secara acak dalam window dan simpan timezone site.
> - Terapkan lock agar hanya satu worker menjalankan occurrence.
> - Gunakan idempotency key `site:date:slot`.
> - Pastikan retry menggunakan occurrence yang sama.
>
> **Acceptance Criteria:**
> - Satu site menghasilkan tepat tiga occurrence per tanggal lokal.
> - `planned_at` berada dalam window dan tidak berubah setelah restart.
> - Duplicate occurrence tidak dapat dibuat.
> - Dua worker tidak dapat menjalankan occurrence yang sama.
> - Retry tidak membuat occurrence baru.
> - Lock dilepas dengan aman ketika proses berhasil atau gagal.

#### Subtask 2

**Summary**

`VOC - Crawl Scheduler - Implement Crawl Trigger, Run History, and Run Now`

**Description**

> Hubungkan scheduler ke endpoint enqueue Crawler dan sediakan monitoring lifecycle run serta manual `Run now`.
>
> **Scope:**
> - Kirim request enqueue ke Crawler dan simpan `batch_id`.
> - Pantau batch sampai status terminal.
> - Jalankan delta pull setelah hasil crawl siap.
> - Simpan `started_at`, `finished_at`, status, dan counters.
> - Buat UI histori run dan tombol `Run now`.
> - Tambahkan confirmation dan permission untuk manual run.
>
> **Acceptance Criteria:**
> - Request OneBox tidak menunggu Selenium selesai.
> - `batch_id` berhasil disimpan dan status batch dapat dipantau.
> - Delta pull tidak dijalankan sebelum hasil crawl siap.
> - Histori menampilkan planned time, actual time, status, dan counters.
> - User tanpa permission tidak dapat menjalankan `Run now`.
> - Manual run memiliki audit trail.
> - Error menampilkan kode atau request ID yang aman.

### DNGO19-3391 — Config Setup

- **Owner:** OneBox (OB)
- **Status:** READY TO DEV
- **MD:** 3 MD

#### Description

> Mendaftarkan benefit VoC pada sistem entitlement OneBox dan menerapkan pengukuran pemakaian agar akses crawl, AI, dan competitor feature dapat dibatasi sesuai benefit tenant.
>
> **Scope:**
> - Mendaftarkan benefit `VOC_SCRAPE`, `VOC_AI`, dan `VOC_COMPETITOR`.
> - Menggunakan `verifyBenefit()` untuk kuota berdasarkan jumlah panggilan crawl.
> - Menggunakan `addUsage()` untuk pemakaian berdasarkan nilai, seperti jumlah token AI.
> - Menangani tenant yang tidak memiliki benefit atau kuotanya telah habis.
> - Mencegah pencatatan pemakaian ganda.
>
> **Acceptance Criteria:**
> - Ketiga benefit tersedia pada `Benefit` dan `SiteBenefit`.
> - Tenant tanpa benefit tidak dapat menggunakan feature terkait.
> - Tenant dengan benefit aktif dapat menggunakan feature sampai batas kuota.
> - Satu panggilan crawl dan satu pemakaian token AI masing-masing dicatat satu kali.
> - `verifyBenefit()` dan `addUsage()` tidak digunakan untuk unit pemakaian yang sama.
> - Error benefit ditampilkan tanpa stack trace atau informasi internal.
>
> **Dependency:**
> - Seeding database Dev yang konsisten.
> - Data `tokens_used` dari Crawler untuk pencatatan usage AI.
>
> **Out of Scope:**
> - Menu dan role VoC.
> - Perbaikan `getUserAllRole`.
> - Perhitungan token di Crawler.
> - Billing dan invoice eksternal.

#### Subtask 1

**Summary**

`VOC - Config Setup - Register VoC Benefit Codes`

**Description**

> Daftarkan benefit `VOC_SCRAPE`, `VOC_AI`, dan `VOC_COMPETITOR` pada sistem `Benefit` dan `SiteBenefit`.
>
> **Acceptance Criteria:**
> - Ketiga benefit tersedia di environment Dev.
> - Benefit dapat dialokasikan kepada site.
> - Seed dapat dijalankan ulang tanpa membuat data duplikat.
> - Nilai default dan satuan masing-masing benefit terdokumentasi.

#### Subtask 2

**Summary**

`VOC - Config Setup - Enforce Crawl Call Quota`

**Description**

> Terapkan `verifyBenefit()` pada entry point crawl untuk memeriksa dan mencatat kuota berdasarkan jumlah panggilan.
>
> **Acceptance Criteria:**
> - Crawl tanpa benefit ditolak.
> - Crawl dengan kuota tersedia dapat dijalankan.
> - Kuota bertambah tepat satu kali untuk satu panggilan.
> - Scheduled run dan `Run now` tidak menyebabkan pencatatan ganda.
> - User mendapatkan pesan yang jelas ketika kuota habis.

#### Subtask 3

**Summary**

`VOC - Config Setup - Record AI Usage`

**Description**

> Gunakan `addUsage()` untuk mencatat nilai pemakaian AI berdasarkan `tokens_used` yang diterima dari Crawler.
>
> **Acceptance Criteria:**
> - Usage dicatat setelah nilai `tokens_used` yang valid diterima.
> - Retry tidak mencatat token yang sama dua kali.
> - Nilai kosong, nol, atau invalid ditangani dengan benar.
> - `addUsage()` tidak dipasangkan dengan `verifyBenefit()` untuk satu unit pemakaian yang sama.
> - Implementasi mengikuti kontrak `tokens_used` dari Crawler.

### DNGO19-3392 — Generate Reports

- **Owner:** OneBox (OB)
- **Status:** READY TO DEV · **MD:** 4 MD

#### Description

> Menyediakan fitur export data review VoC ke format CSV dan PDF untuk kebutuhan analisis serta pelaporan kepada stakeholder.
>
> **Scope:**
> - Menyediakan filter rentang tanggal, lokasi, rating, sentiment, kategori, dan urgency apabila tersedia.
> - Menghasilkan CSV berisi data detail review.
> - Menghasilkan PDF berdasarkan template laporan yang disetujui.
> - Menggunakan timezone site pada periode laporan.
> - Membatasi data berdasarkan tenant dan permission user.
>
> **Acceptance Criteria:**
> - CSV dan PDF menggunakan filter yang dipilih user.
> - Export hanya berisi data tenant aktif.
> - CSV dapat dibuka tanpa encoding atau struktur kolom yang rusak.
> - PDF menampilkan judul, periode, waktu generate, dan filter.
> - Nilai kosong ditampilkan secara konsisten.
> - Dataset kosong menghasilkan pesan yang jelas.
> - Review text diperlakukan sebagai untrusted content.
> - Nama file mencakup jenis laporan dan periode.
>
> **Out of Scope:**
> - Mengirim laporan melalui email.
> - Scheduled report.
> - Menyimpan laporan secara permanen.
> - Custom report builder.

#### Subtask 1

**Summary**

`Dev Specification - VOC - Generate Reports`

**Description**

> Finalisasi kebutuhan CSV dan PDF bersama Product sebelum implementasi.
>
> **Scope:**
> - Tentukan kolom CSV, struktur PDF, filter, dan default periode.
> - Tentukan kebutuhan branding, logo, summary, atau chart.
> - Tentukan batas maksimum data.
> - Buat contoh output atau mockup.
>
> **Acceptance Criteria:**
> - Kolom CSV dan template PDF disetujui Product.
> - Filter dan default periode disetujui.
> - Aturan dataset besar ditentukan.
> - Contoh output tersedia.
> - Scope mendapatkan approval Product.

#### Subtask 2

**Summary**

`VOC - Generate Reports - Implement CSV Export`

**Description**

> Implementasikan export data review ke CSV berdasarkan filter dan permission user.
>
> **Acceptance Criteria:**
> - Kolom dan urutan sesuai specification.
> - Encoding mendukung karakter Bahasa Indonesia.
> - Isi file sesuai filter dan data antar-tenant tidak tercampur.
> - Nilai CSV tidak dapat menyebabkan formula injection.
> - Nama file mengikuti konvensi yang disepakati.

#### Subtask 3

**Summary**

`VOC - Generate Reports - Implement PDF Export`

**Description**

> Implementasikan generate PDF berdasarkan template yang telah disetujui.
>
> **Acceptance Criteria:**
> - Layout sesuai template.
> - Judul, periode, filter, dan waktu generate tersedia.
> - Teks panjang tidak keluar dari layout.
> - Page break dan tabel multi-page ditangani.
> - Data sesuai hasil filter.
> - File PDF dapat dibuka dan diunduh.

### DNGO19-3471 — Dashboard Profile Per Daerah

- **Owner:** OneBox (OB)
- **Status:** TODO
- **Branch:** `feature/DNGO19-3471_VOC-Dashboard-Per-Daerah`

#### Description

> Menyediakan Dashboard Profile VoC per daerah/wilayah dan per lokasi/site agar PIC daerah dapat melihat helicopter view sekaligus detail kondisi cabang/lokasi yang menjadi tanggung jawabnya.
>
> Ticket ini berbeda dari Dashboard Google Review existing yang bersifat dashboard global dengan filter wilayah/lokasi. Dashboard Profile Per Daerah berfokus pada konteks kerja PIC dan executive recap: satu daerah atau satu site menjadi pusat tampilan, lengkap dengan profil lokasi, penanggung jawab, recap bintang, tren bulanan, tren masalah, response rate, response time/SLA, serta daftar cabang yang perlu tindakan.
>
> **Scope:**
> - Menyediakan halaman dashboard profile per daerah/wilayah yang menampilkan seluruh informasi penting terkait cabang/lokasi dalam wilayah tersebut.
> - Menyediakan mode profile per 1 lokasi/site berisi alamat, PIC, kontak penanggung jawab, status integrasi, recap rating, dan performa respons.
> - Membatasi data berdasarkan permission user, mapping PIC, site, wilayah/group, dan lokasi yang diizinkan.
> - Menampilkan KPI operasional utama: total review, rating rata-rata, review hari ini, review bulan ini, review negatif, belum dibalas, response rate, SLA response, dan jumlah lokasi berisiko.
> - Menampilkan tren bulanan rating, volume review, positif/negatif/netral, serta tren masalah per kategori untuk periode yang dipilih.
> - Menampilkan daftar cabang/lokasi dalam wilayah terpilih beserta status risiko, rating, total review, review negatif, status reply, PIC, dan periode agregasi.
> - Menampilkan peta atau ringkasan persebaran risiko lokasi dalam wilayah apabila koordinat tersedia.
> - Menampilkan peta masalah/top issue per wilayah dengan komposisi positif, negatif, dan netral berdasarkan kategori yang tersedia dari backend.
> - Menampilkan review negatif terbaru dan action/follow up yang terkait dengan lokasi dalam scope PIC.
> - Menyediakan drill-down ke halaman Ulasan dan Action & Follow Up dengan filter wilayah/lokasi yang sesuai.
> - Menyediakan tampilan recap executive yang siap dibaca untuk satu daerah atau satu profile site, tanpa perlu user menyusun filter manual dari dashboard global.
>
> **Acceptance Criteria:**
> - PIC daerah hanya melihat lokasi yang berada dalam scope aksesnya.
> - User tanpa mapping PIC atau permission yang sesuai mendapatkan empty/permission state yang jelas.
> - KPI, tabel lokasi, review negatif, dan action tracker hanya menghitung data dari lokasi yang diizinkan.
> - Profile daerah/site menampilkan alamat, PIC, recap bintang, response rate, response time/SLA, tren bulanan, dan tren masalah apabila data backend tersedia.
> - Filter periode, wilayah/group, lokasi, status reply, dan risiko bekerja sesuai data backend yang tersedia tanpa membuat data simulasi.
> - Drill-down ke Ulasan dan Action & Follow Up membawa filter wilayah/lokasi yang benar.
> - Dashboard menampilkan loading, empty, partial-data, error state, tombol muat ulang, dan waktu terakhir data diperbarui.
> - Tidak ada dummy/mock data ketika backend gagal atau data belum tersedia.
> - Angka yang ditampilkan konsisten dengan Dashboard Google Review, halaman Ulasan, dan Action & Follow Up untuk scope yang sama.
> - Perbedaan angka dengan Dashboard Google Review dapat dijelaskan: Dashboard Profile menghitung scope PIC/daerah/site, sedangkan Dashboard Google Review menghitung scope global/filter yang dipilih user.
>
> **Dependency:**
> - Master Data Locations memiliki mapping wilayah/group dan PIC lokasi/daerah yang dapat dibaca oleh OneBox.
> - Backend VoC menyediakan data Google Review dan action tracker berdasarkan SiteId serta scope lokasi user.
> - Permission user/PIC daerah tersedia atau dapat diturunkan dari mapping PIC lokasi.
>
> **Out of Scope:**
> - Membuat connector channel baru.
> - Mengubah crawler Google Review.
> - Mengubah model AI atau prompt analisis.
> - Membuat dashboard competitor.
> - Generate/export PDF khusus daerah; output PDF tetap menjadi scope Generate Reports apabila dibutuhkan.
> - Mengubah relasi backend master lokasi yang sudah berjalan.



#### Subtask 1

**Summary**

`VOC - Dashboard Per Daerah - Permission and PIC Scope`

**Description**

> Implementasikan pembatasan akses dashboard berdasarkan SiteId, permission user, dan mapping PIC daerah/lokasi.
>
> **Scope:**
> - Baca SiteId user aktif.
> - Tentukan daftar lokasi yang boleh dilihat user berdasarkan permission atau mapping PIC.
> - Dukung user top level yang boleh melihat seluruh wilayah.
> - Dukung PIC daerah yang hanya boleh melihat wilayah/lokasi terkait.
> - Tampilkan permission state apabila user tidak memiliki scope lokasi.
>
> **Acceptance Criteria:**
> - User hanya dapat melihat data lokasi dalam scope aksesnya.
> - PIC daerah tidak dapat melihat lokasi di luar wilayahnya.
> - User top level tetap dapat memilih semua wilayah.
> - Kondisi mapping PIC kosong atau tidak valid ditampilkan dengan pesan yang jelas.
> - Pembatasan akses diterapkan pada KPI, chart, tabel, review feed, dan action tracker.

#### Subtask 2

**Summary**

`VOC - Dashboard Per Daerah - Backend Data Scope`

**Description**

> Siapkan data dashboard per daerah dari backend tanpa menggunakan dummy data.
>
> **Scope:**
> - Ambil Google Review dari sumber backend VoC yang sama dengan Dashboard Google Review.
> - Filter data berdasarkan SiteId dan daftar lokasi yang diizinkan.
> - Sediakan KPI agregat per daerah/wilayah.
> - Sediakan data per lokasi: rating, total review, review negatif, belum dibalas, response rate, SLA response, risk flag, PIC, dan periode agregasi.
> - Sediakan data profile per lokasi/site: alamat, PIC, kontak, status integrasi, recap bintang, response rate, response time/SLA, dan periode.
> - Sediakan tren bulanan rating, volume review, sentiment, dan tren masalah per kategori untuk scope daerah/site.
> - Sediakan review negatif terbaru dan action/follow up dalam scope lokasi user.
> - Gunakan data action/ticket yang tersedia dari Ticket OneBox apabila sudah ada.
>
> **Acceptance Criteria:**
> - Backend tidak mengirim data lokasi di luar scope user.
> - KPI konsisten dengan perhitungan dashboard Google Review untuk scope yang sama.
> - Tren bulanan dan tren masalah mengikuti scope daerah/site yang dipilih.
> - Profile site menampilkan data lokasi, PIC, recap bintang, response rate, dan SLA jika tersedia.
> - Review negatif dan action tracker hanya berisi lokasi yang diizinkan.
> - Jika backend gagal, frontend menerima error state, bukan data contoh.
> - Data kosong dikembalikan sebagai empty state yang eksplisit.

#### Subtask 3

**Summary**

`VOC - Dashboard Profile Per Daerah - Build Dashboard UI`

**Description**

> Bangun halaman dashboard profile per daerah/site dengan design system VoC yang konsisten dan mudah dipakai PIC daerah maupun executive.
>
> **Scope:**
> - Tambahkan route/menu dashboard per daerah sesuai struktur navigasi VoC.
> - Tampilkan selector scope daerah/site sebagai konteks utama, bukan sekadar filter tambahan.
> - Tampilkan filter periode, wilayah/group, lokasi, status reply, dan risiko.
> - Tampilkan KPI utama untuk scope daerah/site.
> - Tampilkan panel profile site berisi alamat, PIC, kontak, status integrasi, recap bintang, response rate, dan SLA.
> - Tampilkan tren bulanan rating, volume review, sentiment, dan tren masalah.
> - Tampilkan tabel monitoring lokasi dengan sorting, pagination, dan drill-down.
> - Tampilkan peta/ringkasan risiko lokasi dalam wilayah.
> - Tampilkan peta masalah/top issue dengan komposisi sentimen.
> - Tampilkan review negatif terbaru dan action/follow up terkait.
> - Sediakan loading, empty, partial-data, error state, tombol muat ulang, dan timestamp data.
>
> **Acceptance Criteria:**
> - Dashboard dapat dibuka dari menu/route yang disepakati.
> - Tampilan konsisten dengan Dashboard Google Review dan halaman VoC lain.
> - Selector scope daerah/site memperbarui KPI, tren, profile, tabel, review feed, dan action tracker.
> - Tabel lokasi mudah discan oleh PIC daerah.
> - Profile site dapat dibaca sebagai executive recap tanpa harus membuka halaman lain.
> - Tren bulanan dan tren masalah mudah dibaca untuk satu daerah atau satu lokasi.
> - Peta/ringkasan risiko tidak menampilkan marker kosong tanpa penjelasan.
> - Tidak ada dummy data ketika backend gagal.

#### Subtask 4

**Summary**

`VOC - Dashboard Profile Per Daerah - Site Profile and Executive Recap`

**Description**

> Bangun tampilan profile satu lokasi/site yang dapat dipakai PIC dan executive untuk memahami kondisi lokasi tertentu dalam periode tertentu.
>
> **Scope:**
> - Tampilkan identitas lokasi: nama, alamat, wilayah/group, status integrasi, PIC, nomor WhatsApp, email, dan kontak penanggung jawab.
> - Tampilkan recap bintang: average rating, distribusi rating, review hari ini, review bulan ini, dan total review periode.
> - Tampilkan response performance: sudah dibalas, belum dibalas, response rate, rata-rata waktu response, dan SLA response.
> - Tampilkan trend bulanan rating, volume review, positif/negatif/netral, dan trend masalah per kategori.
> - Tampilkan top issue, review negatif terbaru, dan action/follow up yang masih perlu ditindaklanjuti.
> - Sediakan empty/partial state apabila beberapa data profile belum tersedia dari backend.
>
> **Acceptance Criteria:**
> - User dapat memilih satu lokasi/site dan melihat profile lengkap lokasi tersebut.
> - Profile menampilkan alamat dan PIC dari Master Data Locations.
> - Recap rating dan response performance sesuai data backend pada periode yang dipilih.
> - Trend bulanan dan trend masalah hanya menghitung lokasi/site yang sedang dibuka.
> - Review negatif dan action tracker hanya berisi data lokasi/site tersebut.
> - Tidak ada dummy data untuk field yang belum tersedia.

#### Subtask 5

**Summary**

`VOC - Dashboard Per Daerah - Drilldown and Follow Up Actions`

**Description**

> Hubungkan dashboard per daerah dengan halaman Ulasan dan Action & Follow Up agar PIC dapat mengambil tindakan cepat.
>
> **Scope:**
> - Drill-down KPI, lokasi, issue, dan review negatif ke halaman Ulasan dengan filter wilayah/lokasi yang sesuai.
> - Drill-down action tracker ke halaman Action & Follow Up dengan filter wilayah/lokasi/status yang sesuai.
> - Sediakan akses buat tindak lanjut, eskalasi ke PIC, dan create ticket jika backend action tersedia.
> - Pastikan aksi hanya dapat dilakukan user yang memiliki permission.
> - Tampilkan conflict atau permission message apabila backend menolak perubahan.
>
> **Acceptance Criteria:**
> - Klik KPI/lokasi/issue membawa user ke Ulasan dengan filter yang benar.
> - Klik action membawa user ke Action & Follow Up dengan filter yang benar.
> - PIC dapat membuat tindak lanjut untuk review dalam scope-nya.
> - PIC tidak dapat mengubah review atau ticket di luar scope-nya.
> - Error, conflict, dan permission denial ditampilkan dengan jelas.

### DNGO19-3396 — Competitor Analysis

- **Owner:** OneBox (OB)
- **Status:** TODO

#### Description

> Menyediakan halaman perbandingan performa review antara lokasi milik organisasi dan kompetitor yang telah terdaftar.
>
> **Scope awal yang perlu dikonfirmasi Product:**
> - Menyediakan pemilihan lokasi milik sendiri, kompetitor, rentang tanggal, dan source.
> - Menampilkan average rating lokasi sendiri dan kompetitor.
> - Menampilkan review volume gap, negative sentiment gap, dan critical issue gap.
> - Menampilkan top category atau issue, strengths, weaknesses, dan competitor review feed.
> - Memastikan review kompetitor tidak dibuat sebagai Ticket OneBox.
>
> **Acceptance Criteria:**
> - User dapat memilih lokasi sendiri dan kompetitor.
> - Perbandingan menggunakan periode dan source yang sama.
> - Formula setiap KPI terdokumentasi.
> - Data lokasi sendiri dan kompetitor dapat dibedakan dengan jelas.
> - Review kompetitor tidak dibuat sebagai Ticket.
> - User hanya dapat melihat data tenant-nya.
> - Kondisi data kosong ditampilkan dengan jelas.
> - Nilai KPI konsisten dengan data sumber.
>
> **Dependency:**
> - DNGO19-3386 Master Data Competitors.
> - Endpoint `competitor_reviews` dari Crawler.
> - Consumer review kompetitor di OneBox.
> - Struktur menu pada `feature/voc` telah lolos verifikasi fungsi, route, urutan, dan permission.
>
> **Out of Scope:**
> - CRUD kompetitor.
> - Implementasi crawl worker kompetitor.
> - Membuat Ticket dari review kompetitor.
> - Rekomendasi strategi berbasis AI.

#### Subtask 1

**Summary**

`Dev Specification - VOC - Competitor Analysis`

**Description**

> Finalisasi kebutuhan Competitor Analysis bersama Product.
>
> **Scope:**
> - Tentukan KPI yang masuk MVP dan formula masing-masing KPI.
> - Tentukan apakah user dapat membandingkan satu atau beberapa kompetitor.
> - Tentukan default periode, filter source, dan layout halaman.
> - Tentukan aturan ketika data kompetitor kosong atau tidak seimbang.
> - Buat wireframe atau referensi tampilan.
>
> **Acceptance Criteria:**
> - KPI MVP dan formula disetujui Product.
> - Aturan pemilihan kompetitor ditentukan.
> - Filter dan default periode disetujui.
> - Wireframe tersedia.
> - Scope implementasi mendapatkan approval Product.

#### Subtask 2

**Summary**

`VOC - Competitor Analysis - Implement Comparison Data`

**Description**

> Implementasikan pengambilan dan agregasi data untuk membandingkan review lokasi sendiri dengan review kompetitor.
>
> **Scope:**
> - Ambil data berdasarkan tenant.
> - Terapkan filter lokasi, kompetitor, periode, dan source.
> - Hitung KPI berdasarkan formula yang disetujui.
> - Sediakan paging untuk competitor review feed.
> - Pastikan review kompetitor tidak masuk proses pembuatan Ticket.
>
> **Acceptance Criteria:**
> - Query ter-scope berdasarkan tenant.
> - Filter diterapkan secara konsisten.
> - Formula KPI sesuai specification.
> - Review kompetitor tidak dibuat sebagai Ticket.
> - Paging diterapkan pada review feed.
> - Dataset kosong ditangani dengan benar.

#### Subtask 3

**Summary**

`VOC - Competitor Analysis - Implement Analysis UI`

**Description**

> Implementasikan halaman Competitor Analysis berdasarkan Dev Specification.
>
> **Scope:**
> - Tambahkan filter lokasi, kompetitor, periode, dan source.
> - Tampilkan KPI perbandingan, strengths, weaknesses, dan competitor review feed.
> - Tambahkan loading, empty, dan error state.
> - Terapkan role dan entitlement `VOC_COMPETITOR`.
>
> **Acceptance Criteria:**
> - User dapat mengubah seluruh filter.
> - Tampilan membedakan own location dan competitor.
> - KPI sesuai response data.
> - Loading, empty, dan error state tersedia.
> - Competitor review feed memiliki paging.
> - User tanpa permission atau benefit tidak dapat membuka feature.

---

## Redistribusi Scope Eks-DNGO19-3346

`DNGO19-3346` tidak lagi digunakan sebagai bucket untuk pekerjaan lanjutan. Scope yang sebelumnya ditulis di bawah branch tersebut dipindahkan sebagai berikut:

| Scope lama | Ticket yang bertanggung jawab sekarang | Status audit 3 Agustus 2026 |
|---|---|---|
| Restrukturisasi menu VoC | `feature/voc` / integration work | Dinyatakan implemented; masih perlu verifikasi struktur Transaksi/Output/Setting, route, urutan, seed idempotent, dan permission di Dev. |
| Delta pull dan safe checkpoint | DNGO19-3420 — Fetch Jobs Crawl | Implementasi cursor/checkpoint dan deduplication terdeteksi; perlu merge sisa commit dan QA end-to-end. |
| Targeted backfill lokasi baru | DNGO19-3385 — Master-Data-Locations | Belum teridentifikasi sebagai implementasi khusus; masih remaining. |
| Menarik/reconcile review historis | DNGO19-3420 — Fetch Jobs Crawl | Flow catch-up/import tersedia; skenario legacy location dan retry/resume perlu QA. |
| Membuat/menghubungkan Ticket untuk review lama | DNGO19-3387 — Review Manage Actions | Flow pending Message → Ticket tersedia; idempotency dan kasus review lama perlu QA. |

**Implikasi urutan kerja terbaru:**

1. Verifikasi menu pada `feature/voc`; feature lain tidak perlu lagi menunggu branch 3346.
2. Review dan integrasikan sisa commit DNGO19-3420, lalu uji crawl → polling → delta import → pending Message → Ticket.
3. Implementasikan targeted backfill pada DNGO19-3385 dengan memakai mekanisme pull aman DNGO19-3420.
4. Jalankan rekonsiliasi per lokasi lama dan verifikasi hasilnya melalui flow DNGO19-3387.
5. Crawl Scheduler DNGO19-3390 baru diuji end-to-end setelah safe checkpoint DNGO19-3420 dinyatakan stabil.

---

## 📋 Pending / Perlu Diklarifikasi (list terbuka, jangan diasumsikan selesai)

| # | Item | Kenapa masih terbuka |
|---|---|---|
| 1 | **Isi ticket 3393–3395** | **Hipotesis baru (perlu konfirmasi):** screenshot ticket 3385 menunjukkan subtask `DNGO19-3394 "Dev Specification : VOC : Master-Data-Locations"` — kemungkinan besar 3393/3394/3395 adalah subtask "Dev Specification" milik ticket-ticket induk, bukan ticket fitur yang hilang. Review Detail sudah berada di 3387, sedangkan Delta Sync sekarang berada di 3420. Tetap cek langsung di Jira untuk memastikan pola penomoran subtask ini konsisten. |
| 2 | **Scope persis `Crawl Scheduler` (3390)** | Perlu dikonfirmasi: apakah full M4-01..05 (8MD, exceeds cap) atau sudah dipangkas. Sub-task split direkomendasikan (lihat detail 3390 di atas). |
| 3 | **Scope persis `Competitor Analysis` (3396)** | Pastikan tidak overlap dengan `Master-Data-Competitors` (3386) — 3386 = CRUD/registrasi, 3396 = komparasi/output (asumsi dari notulen meeting, belum dikonfirmasi eksplisit). |
| 4 | **Exception 5MD di 3387 dan 3390** | Dua ticket ini disengaja melebihi cap karena penggabungan scope yang masuk akal secara alur kerja — perlu dikomunikasikan ke Agung sebagai exception yang disadari, bukan kelalaian. |
| 5 | **Target `Enhance AI Analysis` (DNGO19-3407)** | Jira key sudah tersedia. Target latency, throughput, error rate, dan kompatibilitas schema perlu difinalisasi. Kandidat/pemilihan model serta benchmark runtime menjadi linked work item Crawler; OneBox hanya memvalidasi output. Jira Work Type saat ini `Task`; direkomendasikan diubah menjadi `New Feature` agar konsisten dengan feature VoC lain. |
| 6 | **Kontrak `Fetch Jobs Crawl` (DNGO19-3420)** | Jira key dan work type `New Feature` sudah tersedia. Kontrak request/response, lifecycle job, batas target review, dry run, retry, cancel, dan penggunaan `job_id` atau `batch_id` tetap harus difinalisasi pada Dev Specification. |

---

## Item yang Sudah Tidak Berlaku dari Draft Sebelumnya

- ~~T1a/T1b Review-Detail + Review-Manage-Actions terpisah~~ → **digabung jadi 3387**.
- ~~T5a Delta-Sync sebagai ticket sendiri/di 3346~~ → **menjadi scope DNGO19-3420 Fetch Jobs Crawl**.
- ~~T5b/T5c Scheduling-Core + Trigger-UI terpisah~~ → jadi **3390 (Crawl Scheduler)**, kemungkinan perlu sub-task internal karena cap 5MD.
- ~~T8 Menu Navigation Restructure sebagai ticket sendiri/di 3346~~ → **sudah berada di integration branch `feature/voc`; pending verification/QA**.
