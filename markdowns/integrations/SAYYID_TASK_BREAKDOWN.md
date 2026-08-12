# Task Breakdown Sayyid - Voice of Customer System

Sumber: Google Sheets `TRACKER TERBARU` (`gid=20260803`)  
Filter: hanya task dengan `PIC = Sayyid`  
Tanggal baca: 10 Agustus 2026

Dokumen ini merangkum dan memperjelas seluruh task Sayyid dari tracker agar bisa dipakai sebagai working checklist harian. Status dan persentase mengikuti sheet, sedangkan detail scope, dependency, dan acceptance criteria diturunkan dari konteks implementasi Voice of Customer System, Crawler System, dan integrasi OneBox.

## Ringkasan Prioritas

| Prioritas | Fokus | Catatan |
|---|---|---|
| P0 / Critical | Fetch Jobs, crawling metadata, official reply, escalation, AI setup contract, scheduler core | Berdampak langsung ke demo key process dan flow production-ready. |
| P1 / High | Backfill lokasi, review list/detail, maker/reviewer tracking, workspace API | Memastikan data real bisa dipakai konsisten oleh user dan tim internal. |
| P2 / Medium | UI status, icon/action polish, scheduler UI | Mengurangi kebingungan user dan merapikan usability. |

## Urutan Eksekusi Rekomendasi

1. Selesaikan sisa `DNGO19-3420 - Fetch Jobs Crawl`, karena modul ini menjadi pintu masuk data review real dari Crawler System.
2. Rapikan `DNGO19-3387 - Review Manage Actions`, supaya review yang masuk bisa langsung dikelola, dibalas, atau dieskalasi.
3. Kunci kontrak `DNGO19-3388 - AI Analysis Setup`, agar analisis AI tidak liar dan tetap kompatibel dengan Crawler System.
4. Validasi `DNGO19-3385 - Master Data Locations` dan `Workspace & Navigation`, karena keduanya menentukan tenant, lokasi, menu, dan data yang tampil.
5. Mulai `DNGO19-3390 - Crawl Scheduler` setelah fetch jobs manual sudah stabil, supaya otomatisasi tidak membawa bug ke jadwal berulang.

---

## DNGO19-3385 - Master Data Locations

### 1. Implementasikan backfill khusus untuk lokasi baru dan pastikan lokasi masuk ke proses crawl yang benar

| Field | Detail |
|---|---|
| Status | Needs QA |
| Progress | 80% |
| Prioritas | High |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Memastikan lokasi baru yang ditambahkan dari OneBox tidak hanya tersimpan sebagai master data, tetapi juga ikut masuk ke worklist Crawler System dan dapat dipakai untuk fetch/crawl Google Review.

**Scope teknis**

- Validasi flow setelah lokasi baru dibuat atau diaktifkan.
- Pastikan lokasi memiliki mapping minimum: `company_id`, `site_id`, `source`, external place/worklist identifier, dan status aktif.
- Pastikan lokasi baru muncul dalam worklist yang dipakai Crawler System.
- Jalankan backfill hanya untuk lokasi yang belum pernah masuk cache/worklist agar tidak menduplikasi data lama.
- Cek bahwa lokasi nonaktif atau competitor tidak ikut diproses sebagai lokasi internal.

**Dependency**

- Worklist endpoint OneBox sudah bisa diakses oleh Crawler System.
- Struktur master data location sudah konsisten dengan seed/migration OneBox.
- Mapping `company_id` dan `site_id` benar.

**Acceptance criteria**

- Lokasi baru muncul di list lokasi OneBox.
- Lokasi baru muncul di worklist Crawler System setelah refresh.
- Fetch job bisa dibuat untuk lokasi tersebut.
- Tidak ada duplikasi location row atau worklist cache.
- Lokasi competitor/nonaktif tidak ikut sebagai lokasi internal.

### 2. QA penghapusan legacy push-sync serta perbaikan StatusId Connection 1039 agar scheduler tidak salah jalan

| Field | Detail |
|---|---|
| Status | Done |
| Progress | 100% |
| Prioritas | Critical |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Memastikan arsitektur final menggunakan pola OneBox pull dari Crawler System, bukan legacy push-sync, dan memastikan Connection 1039 tidak ikut diproses oleh scheduler lama yang salah scope.

**Scope teknis**

- Pastikan tidak ada job lama yang masih melakukan push data dari crawler ke OneBox.
- Pastikan Connection 1039 memiliki `StatusId` yang sesuai untuk jalur VoC.
- Validasi scheduler hanya membaca connection yang memang aktif untuk VoC.
- Pastikan perubahan tidak memutus flow worklist dan fetch jobs.

**Acceptance criteria**

- Legacy push-sync tidak lagi berjalan.
- Connection 1039 tidak diproses oleh scheduler lama.
- Fetch jobs tetap bisa dibuat dan dipantau.
- Pull review dari Crawler System tetap berjalan.

---

## DNGO19-3387 - Review Manage Actions

### 1. QA Review Detail dan seluruh action: assign, status, priority, internal note, history, dan delete

| Field | Detail |
|---|---|
| Status | Done |
| Progress | 100% |
| Prioritas | High |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Memastikan halaman detail review bisa dipakai sebagai pusat tindak lanjut keluhan pelanggan, bukan hanya halaman baca data.

**Scope teknis**

- Uji action assign PIC.
- Uji perubahan status review/ticket.
- Uji perubahan priority.
- Uji internal note dan history.
- Uji delete sesuai permission.
- Pastikan semua action menulis ke entity yang benar di OneBox.

**Acceptance criteria**

- Semua action berhasil dan tersimpan.
- History mencatat perubahan penting.
- Error dan loading state jelas.
- Permission dicek sebelum action sensitif.

### 2. Implementasikan tombol AI Config atau sembunyikan sementara sampai fiturnya benar-benar tersedia

| Field | Detail |
|---|---|
| Status | Done |
| Progress | - |
| Prioritas | Medium |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Menghindari tombol kosong atau fitur palsu di UI yang membuat user mengira konfigurasi AI sudah bisa dipakai penuh.

**Scope teknis**

- Jika config sudah tersedia, tombol harus membuka konfigurasi valid.
- Jika belum tersedia, tombol disembunyikan atau diberi state disabled yang jelas.
- Tidak ada dummy modal atau text generik.

**Acceptance criteria**

- User tidak melihat action AI Config yang tidak bisa dipakai.
- UI tetap konsisten dengan role dan permission.

### 3. Tambahkan flag official/non official di list/detail ulasan dan tentukan action reply yang tersedia per sumber

| Field | Detail |
|---|---|
| Status | Done |
| Progress | 100% |
| Prioritas | Critical |
| Target selesai | - |

**Tujuan**  
Membedakan review dari kanal official dan non-official agar user tahu apakah review bisa dibalas langsung melalui sistem atau hanya bisa ditindaklanjuti internal.

**Scope teknis**

- Tambahkan flag sumber pada list review.
- Tampilkan status official/non-official di detail.
- Tentukan capability action: reply, escalate, internal note, atau view-only.
- Hindari tombol reply untuk source yang tidak mendukung official response.

**Acceptance criteria**

- User bisa membedakan sumber review secara cepat.
- Tombol reply hanya muncul untuk sumber yang mendukung.
- Data tetap backward-compatible untuk review lama.

### 4. Di tabel ulasan tampilkan message/review text 2 baris, status sudah dibalas/belum, waktu review masuk, dan response terakhir

| Field | Detail |
|---|---|
| Status | Partial |
| Progress | - |
| Prioritas | High |
| Target selesai | - |

**Tujuan**  
Membuat list review lebih berguna untuk scanning cepat tanpa harus membuka detail satu per satu.

**Scope teknis**

- Tampilkan potongan review maksimal 2 baris.
- Tampilkan status reply: sudah dibalas, belum dibalas, atau tidak tersedia.
- Tampilkan waktu review masuk atau waktu ingestion.
- Tampilkan ringkasan response terakhir jika ada.
- Pastikan tabel tetap rapi di resolusi kecil.

**Dependency**

- Metadata review harus tersedia dari Crawler System atau mapping OneBox.
- Field response/reply status harus tersedia di Message/Ticket/meta.

**Acceptance criteria**

- List review bisa dibaca cepat oleh CS/manager.
- Kolom tidak terlalu ramai.
- Empty value tampil sebagai `-` atau label yang jelas, bukan text debug.

### 5. Di detail ulasan tampilkan URL review asli, indikasi/foto review jika tersedia, serta panel preview kanan selengkap mungkin

| Field | Detail |
|---|---|
| Status | Partial |
| Progress | - |
| Prioritas | High |
| Target selesai | - |

**Tujuan**  
Memberi konteks lengkap pada user sebelum mengambil tindakan terhadap review.

**Scope teknis**

- Tampilkan URL review asli jika tersedia.
- Tampilkan indikator review memiliki foto.
- Tampilkan foto atau link foto jika tersedia.
- Panel kanan berisi metadata penting: rating, source, lokasi, reviewer, waktu, reply status, dan ticket relation.
- Jangan menampilkan JSON mentah ke user.

**Acceptance criteria**

- User bisa membuka sumber asli review.
- Metadata penting bisa dibaca tanpa scroll berlebihan.
- Review tanpa foto tetap tampil normal.

### 6. Untuk Google Business official, aktifkan tombol reply dari detail ulasan dan simpan tanggal/jam response

| Field | Detail |
|---|---|
| Status | Partial |
| Progress | - |
| Prioritas | Critical |
| Target selesai | - |

**Tujuan**  
Mendukung workflow operasional untuk membalas review official langsung dari OneBox jika source dan permission mengizinkan.

**Scope teknis**

- Tombol reply hanya aktif untuk Google Business official.
- Simpan body response, responder, timestamp response, dan status response.
- Pastikan action reply punya loading, success, dan error state.
- Pastikan response tidak terkirim ganda ketika user double-click.
- Jika API reply official belum tersedia, simpan sebagai draft/internal action dengan label yang jelas.

**Dependency**

- Capability source official/non-official sudah valid.
- Endpoint atau service untuk reply official sudah dikonfirmasi.
- Permission user untuk reply sudah jelas.

**Acceptance criteria**

- Reply dapat dibuat dari detail review.
- Timestamp response tersimpan.
- Status review berubah menjadi sudah dibalas.
- Jika gagal, user menerima pesan error yang actionable.

### 7. Tambahkan action eskalasi ke PIC terkait, termasuk nama PIC, nomor WhatsApp, dan opsi kirim WA via OneBox bila berlangganan

| Field | Detail |
|---|---|
| Status | Partial |
| Progress | - |
| Prioritas | Critical |
| Target selesai | - |

**Tujuan**  
Mengubah review negatif atau urgent menjadi tindak lanjut operasional yang bisa diteruskan ke PIC terkait.

**Scope teknis**

- Tambahkan action escalate pada detail review.
- Pilih PIC berdasarkan lokasi, kategori issue, atau user selection.
- Simpan nama PIC, nomor WhatsApp, catatan eskalasi, dan timestamp.
- Jika tenant memiliki layanan WhatsApp OneBox, tampilkan opsi kirim WA.
- Jika tidak berlangganan, action tetap bisa mencatat eskalasi internal.

**Dependency**

- Data PIC lokasi tersedia.
- Integrasi WhatsApp OneBox atau capability entitlement sudah jelas.
- Rule escalation per kategori/urgency disepakati.

**Acceptance criteria**

- Review bisa dieskalasi ke PIC.
- Riwayat eskalasi tercatat.
- Action WA hanya muncul jika tersedia.
- User tahu apakah eskalasi berhasil dikirim atau hanya dicatat internal.

### 8. Simpan maker_id dan reviewer_id/humas yang membuat jawaban atau tindak lanjut review

| Field | Detail |
|---|---|
| Status | Not Started |
| Progress | - |
| Prioritas | High |
| Target selesai | - |

**Tujuan**  
Membuat audit trail jelas untuk setiap jawaban, eskalasi, dan tindak lanjut review.

**Scope teknis**

- Simpan `maker_id` untuk user yang membuat draft/jawaban/tindak lanjut.
- Simpan `reviewer_id` atau user Humas yang melakukan review/approval.
- Pastikan field ini tercatat pada action reply, escalate, internal note, dan status change.
- Tampilkan nama user di history.

**Acceptance criteria**

- Setiap action penting punya actor.
- History bisa menjawab siapa melakukan apa dan kapan.
- Tidak ada action anonim pada workflow review.

### 9. Tambahkan KPI bintang pada page ulasan yang dapat diklik untuk filter tabel

| Field | Detail |
|---|---|
| Status | Done |
| Progress | - |
| Prioritas | High |
| Target selesai | - |

**Tujuan**  
Mempermudah manager melihat distribusi rating dan langsung memfilter review berdasarkan bintang.

**Acceptance criteria**

- KPI bintang muncul di halaman ulasan.
- Klik KPI mengubah filter tabel.
- Filter aktif terlihat jelas.

### 10. Ganti ikon aksi edit menjadi ikon aksi yang lebih sesuai untuk tindak lanjut/reply/escalate

| Field | Detail |
|---|---|
| Status | Done |
| Progress | - |
| Prioritas | Medium |
| Target selesai | - |

**Tujuan**  
Mengurangi ambiguitas UI; action review bukan sekadar edit, melainkan tindak lanjut, reply, atau eskalasi.

**Acceptance criteria**

- Ikon action lebih sesuai dengan fungsi.
- Tooltip/action label jelas.
- Tidak ada ikon edit generik untuk workflow tindak lanjut.

---

## DNGO19-3388 - AI Analysis Setup

### 1. Perbarui scope: Crawler memilih model AI; OneBox hanya mengatur ai_enabled dan output_schema_version

| Field | Detail |
|---|---|
| Status | Not Started |
| Progress | - |
| Prioritas | Critical |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Menjaga boundary arsitektur: Crawler System bertanggung jawab pada model AI dan eksekusi analisis, sedangkan OneBox hanya mengatur apakah AI aktif dan versi output yang diharapkan.

**Scope teknis**

- Hapus atau hindari konfigurasi model AI detail dari OneBox.
- OneBox hanya menyimpan `ai_enabled` dan `output_schema_version`.
- Crawler System menentukan model, prompt, batching, retry, dan fallback.
- Pastikan perubahan kompatibel dengan worklist dan connection options.

**Dependency**

- Contract Crawler System untuk AI output sudah stabil.
- `output_schema_version` disepakati antara OneBox dan Crawler System.

**Acceptance criteria**

- OneBox tidak perlu tahu nama model Ollama/Gemini/detail provider.
- Crawler bisa mengganti model tanpa migration OneBox.
- Worklist mengirim konfigurasi minimal yang diizinkan.

### 2. Simpan konfigurasi AI OneBox pada Connection.Options dan kirim konfigurasi yang diizinkan melalui worklist

| Field | Detail |
|---|---|
| Status | Not Started |
| Progress | - |
| Prioritas | High |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Menyediakan konfigurasi tenant-level untuk AI tanpa membuat tabel baru yang terlalu cepat atau menyebarkan config ke banyak tempat.

**Scope teknis**

- Simpan konfigurasi AI di `Connection.Options`.
- Validasi JSON config saat save.
- Kirim hanya field yang aman melalui worklist.
- Pastikan default value jelas jika config belum diisi.
- Jangan mengirim credential rahasia di worklist.

**Acceptance criteria**

- Config AI bisa dibaca dari Connection.
- Worklist memuat `ai_enabled` dan `output_schema_version`.
- Field tidak valid tidak membuat worklist rusak.
- Credential rahasia tidak ikut keluar.

---

## DNGO19-3420 - Fetch Jobs Crawl

### 1. QA alur utama yang sudah ada: enqueue, polling batch, import, dedup, checkpoint, dan Message ke Ticket

| Field | Detail |
|---|---|
| Status | Done |
| Progress | 100% |
| Prioritas | Critical |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Memastikan fetch jobs adalah jalur utama untuk mengambil review dari Crawler System hingga tersimpan di entity OneBox.

**Scope teknis**

- Enqueue crawl job dari OneBox ke Crawler System.
- Polling status batch.
- Import review raw dari Crawler System.
- Deduplicate review.
- Simpan checkpoint cursor.
- Mapping review ke Message/Ticket.

**Acceptance criteria**

- Job bisa dibuat dari OneBox.
- Status batch bisa dipantau.
- Review tersimpan tanpa perlu tombol tarik review terpisah.
- Review tidak duplikat ketika fetch ulang.
- Message dan Ticket terbentuk sesuai rule yang berlaku.

### 2. Review dan merge dua commit terbaru dari branch DNGO19-3420 ke feature/voc

| Field | Detail |
|---|---|
| Status | Done |
| Progress | 100% |
| Prioritas | Critical |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Menjaga branch integrasi `feature/voc` membawa perubahan fetch jobs terbaru yang dibutuhkan demo dan QA.

**Acceptance criteria**

- Commit terbaru sudah masuk branch integrasi.
- Tidak ada regression pada route VoC utama.
- Fetch jobs tetap bisa dijalankan setelah merge.

### 3. Ganti sample job history dan log dengan data dari endpoint/service yang sebenarnya

| Field | Detail |
|---|---|
| Status | Partial |
| Progress | 25% |
| Prioritas | High |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Menghilangkan data simulasi dari halaman Fetch Jobs agar user melihat histori dan log job real.

**Scope teknis**

- Identifikasi endpoint/service OneBox untuk job history.
- Ambil data batch/job dari Crawler System atau cache OneBox.
- Tampilkan status real: queued, running, completed, failed, canceled.
- Tampilkan timestamp, lokasi, jumlah target, jumlah fetched, jumlah imported, dan error summary.
- Hindari fallback sample saat API gagal.

**Dependency**

- Endpoint Crawler System untuk crawl job read/status tersedia.
- Token service punya scope `crawl:read`.
- OneBox punya tempat penyimpanan run history atau bisa membaca dari response Crawler.

**Acceptance criteria**

- Job history berasal dari data real.
- Ketika belum ada job, tampil empty state.
- Ketika API gagal, tampil error state, bukan sample data.

### 4. Lengkapi filter tanggal, dry run, retry, cancel, dan penanganan job gagal

| Field | Detail |
|---|---|
| Status | Partial |
| Progress | 25% |
| Prioritas | High |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Membuat Fetch Jobs aman untuk operasional, bukan hanya tombol trigger sederhana.

**Scope teknis**

- Filter job berdasarkan tanggal/periode.
- `dry_run` untuk simulasi tanpa menyimpan/import.
- Retry job gagal dengan idempotency yang aman.
- Cancel job queued/running jika Crawler System mendukung.
- Error detail ditampilkan dalam bahasa yang bisa dipahami user.

**Dependency**

- Contract endpoint Crawler System untuk retry/cancel.
- Policy idempotency key disepakati.

**Acceptance criteria**

- User bisa mencari job berdasarkan tanggal.
- Dry run tidak mengubah data produksi.
- Retry tidak membuat duplicate review.
- Cancel punya status akhir yang jelas.

### 5. QA delta sync dan rekonsiliasi review lama agar checkpoint aman serta tidak menghasilkan data duplikat

| Field | Detail |
|---|---|
| Status | Done |
| Progress | 100% |
| Prioritas | Critical |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Menjamin sinkronisasi incremental aman walaupun ada data historis, retry, atau pull ulang dari OneBox.

**Acceptance criteria**

- Checkpoint cursor tersimpan.
- Pull berikutnya hanya mengambil delta yang relevan.
- Review lama tidak menjadi duplicate.
- Review historis tidak otomatis membuat Ticket baru jika tidak eligible.

### 6. Rapikan status job, counter, loading, empty state, dan pesan error pada tampilan Fetch Jobs

| Field | Detail |
|---|---|
| Status | Partial |
| Progress | 70% |
| Prioritas | Medium |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Membuat halaman Fetch Jobs jelas untuk user operasional ketika job sedang berjalan, selesai, gagal, atau belum ada data.

**Scope teknis**

- Tampilkan loading saat enqueue/polling/import.
- Tampilkan counter fetched/imported/skipped/failed.
- Empty state untuk belum ada job.
- Error state yang menjelaskan penyebab: auth, network, crawler unavailable, quota, atau validation.
- Hindari text teknis mentah yang terlalu panjang.

**Acceptance criteria**

- User tahu job sedang berada di tahap apa.
- Error dapat dipahami tanpa membuka console.
- Counter konsisten dengan hasil backend.

### 7. Rapikan screen list hasil crawling: filter waktu, status, sumber official/non official, widget, kolom, dan icon aksi

| Field | Detail |
|---|---|
| Status | Needs UI Fix |
| Progress | - |
| Prioritas | High |
| Target selesai | - |

**Tujuan**  
Membuat hasil crawling bisa dipakai sebagai worklist review yang mudah dipantau oleh user.

**Scope teknis**

- Filter waktu review masuk dan waktu review dibuat.
- Filter status import/analysis/reply.
- Tampilkan official/non-official.
- Rapikan widget KPI agar tidak terlalu ramai.
- Kolom utama: lokasi, reviewer, rating, review text, status, waktu, action.
- Icon action harus sesuai fungsi.

**Acceptance criteria**

- List mudah discan.
- Filter tidak membingungkan antara tanggal crawling dan tanggal review.
- Tidak ada UI copy yang terasa seperti demo/internal.

### 8. Simpan metadata crawling Google Review: review URL, ada/tidak foto, photo URL bila tersedia, waktu datang, reply status, dan response

| Field | Detail |
|---|---|
| Status | Partial |
| Progress | - |
| Prioritas | Critical |
| Target selesai | - |

**Tujuan**  
Menyimpan metadata penting dari Google Review agar OneBox bisa menampilkan, memfilter, membalas, dan menganalisis review dengan konteks lengkap.

**Scope teknis**

- Simpan URL review asli.
- Simpan flag ada/tidak foto.
- Simpan photo URL jika tersedia.
- Simpan waktu review masuk ke Crawler System.
- Simpan reply status dan response terakhir jika tersedia.
- Pastikan metadata masuk ke raw payload dan mapping OneBox.

**Dependency**

- Crawler System berhasil mengekstrak metadata tersebut dari Google Maps/Google Business source.
- Contract response review mendukung field metadata.
- OneBox mapping Message/Ticket/meta siap menerima field tersebut.

**Acceptance criteria**

- Metadata tampil di detail review.
- Review tanpa metadata tetap aman.
- Metadata tidak mengganggu deduplication.
- Dashboard dan list bisa memakai field reply status/waktu masuk.

### 9. Tambahkan deduplication index berdasarkan message_id, tanggal review, dan pengirim agar review tidak double

| Field | Detail |
|---|---|
| Status | Done |
| Progress | - |
| Prioritas | Critical |
| Target selesai | - |

**Tujuan**  
Menjamin review yang sama tidak masuk berkali-kali walaupun job diulang, cursor berubah, atau review tidak punya external id yang sempurna.

**Acceptance criteria**

- Review yang sama tidak membuat Message/Ticket baru.
- Retry job aman.
- Dedup tetap bekerja untuk review lama dan review baru.

---

## DNGO19-3390 - Crawl Scheduler

### 1. Implementasikan scheduler core: jadwal berulang, timezone, locking, dan idempotency

| Field | Detail |
|---|---|
| Status | Not Started |
| Progress | - |
| Prioritas | Critical |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Membuat crawling bisa berjalan otomatis sesuai jadwal tenant tanpa double-run dan tanpa bentrok antar worker.

**Scope teknis**

- Scheduler mendukung jadwal berulang.
- Timezone mengikuti tenant/site, default `Asia/Jakarta`.
- Locking mencegah job yang sama berjalan bersamaan.
- Idempotency key dibuat per tenant, lokasi, session time window, dan tanggal.
- Scheduler memicu fetch/crawl secara non-blocking.

**Acceptance criteria**

- Jadwal pagi/siang/malam bisa dibuat.
- Job tidak double walaupun scheduler restart.
- Timezone konsisten.
- Log scheduler mencatat run yang dibuat atau dilewati.

### 2. Implementasikan trigger crawl non-blocking, run history, counter, retry, dan pencatatan hasil

| Field | Detail |
|---|---|
| Status | Not Started |
| Progress | - |
| Prioritas | Critical |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Scheduler tidak boleh membuat UI atau worker OneBox menunggu crawling selesai; hasil harus bisa dipantau melalui run history.

**Scope teknis**

- Trigger crawl job secara asynchronous.
- Simpan run history per jadwal.
- Simpan counter: requested, fetched, imported, skipped, failed.
- Simpan error summary.
- Retry hanya untuk failure yang aman diulang.

**Acceptance criteria**

- Scheduler cepat mengembalikan response.
- Run history menampilkan progres dan hasil akhir.
- Retry tidak membuat duplicate review.

### 3. Tambahkan Run Now beserta pengecekan permission dan quota

| Field | Detail |
|---|---|
| Status | Not Started |
| Progress | - |
| Prioritas | High |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Memberikan kontrol manual kepada user berwenang untuk menjalankan crawl di luar jadwal.

**Scope teknis**

- Tombol Run Now di halaman scheduler atau fetch jobs.
- Cek permission user.
- Cek quota/benefit tenant.
- Kirim job dengan idempotency key.
- Tampilkan status job setelah trigger.

**Acceptance criteria**

- User tanpa permission tidak bisa Run Now.
- Quota habis ditolak dengan pesan jelas.
- Job berhasil masuk ke run history.

### 4. Buat tampilan pengaturan jadwal dan riwayat dengan loading, empty, dan error state

| Field | Detail |
|---|---|
| Status | Not Started |
| Progress | - |
| Prioritas | Medium |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Membuat user bisa memahami kapan crawl akan berjalan dan apa hasil run sebelumnya.

**Scope teknis**

- UI konfigurasi jadwal.
- UI riwayat run.
- Loading, empty, dan error state.
- Tampilkan next run dan last run.
- Tampilkan status active/inactive.

**Acceptance criteria**

- User tahu jadwal berikutnya.
- User bisa melihat history tanpa membuka log teknis.

### 5. Tambahkan scheduler test untuk banyak akun, banyak company, dan banyak site dengan hasil run per akun

| Field | Detail |
|---|---|
| Status | Not Started |
| Progress | - |
| Prioritas | Critical |
| Target selesai | - |

**Tujuan**  
Menguji kesiapan scheduler untuk skenario multi-tenant dan multi-site.

**Scope teknis**

- Test minimal beberapa company.
- Test beberapa site dalam satu company.
- Test beberapa akun/service account.
- Pastikan hasil run terpisah per tenant/site.
- Pastikan credential/config tidak bocor antar tenant.

**Acceptance criteria**

- Tenant A tidak memproses lokasi tenant B.
- Run history terbaca per tenant/site.
- Tidak ada race condition antar jadwal.

### 6. Naikkan engine crawler ke gateway agar scheduler bisa berjalan non-blocking dan stabil

| Field | Detail |
|---|---|
| Status | Not Started |
| Progress | - |
| Prioritas | Critical |
| Target selesai | - |

**Tujuan**  
Menghindari scheduler bergantung pada proses lokal yang rapuh, serta membuat trigger crawl lebih stabil untuk production.

**Scope teknis**

- Evaluasi penempatan crawler worker/gateway.
- Pastikan queue atau gateway menerima job dari OneBox.
- Pastikan worker dapat memproses job tanpa blocking request.
- Pisahkan API request, queue, dan worker execution.

**Acceptance criteria**

- Request Run Now/scheduler tidak menunggu Selenium selesai.
- Worker bisa restart tanpa kehilangan job.
- Job status tetap bisa dipantau.

### 7. Tambahkan monitoring stabilitas scheduler: concurrency, quota, retry/backoff, locking, dan alert ketika gagal

| Field | Detail |
|---|---|
| Status | Not Started |
| Progress | - |
| Prioritas | High |
| Target selesai | - |

**Tujuan**  
Membuat scheduler aman dipakai jangka panjang dan mudah di-debug saat gagal.

**Scope teknis**

- Batasi concurrency per tenant/site.
- Monitor quota usage.
- Retry dengan backoff.
- Lock visibility dan timeout.
- Alert atau log penting saat job gagal berulang.

**Acceptance criteria**

- Failure terlihat jelas.
- Scheduler tidak spam request.
- Retry tidak membanjiri Crawler System.

---

## Workspace & Navigation

### 1. QA workspace API dan proses update data menggunakan data tenant yang sebenarnya

| Field | Detail |
|---|---|
| Status | Needs QA |
| Progress | - |
| Prioritas | High |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Memastikan workspace VoC membaca data tenant real, bukan snapshot atau fallback demo.

**Scope teknis**

- Uji endpoint workspace dengan user tenant real.
- Pastikan menu, location, review, dashboard, dan fetch jobs scoped ke tenant.
- Pastikan role/permission mempengaruhi menu dan action.
- Pastikan tidak ada data tenant lain muncul.

**Acceptance criteria**

- Data yang muncul sesuai tenant login.
- Workspace tetap aman saat data kosong.
- Permission menu dan action konsisten.

### 2. Hapus demo snapshot fallback ketika backend kosong atau gagal

| Field | Detail |
|---|---|
| Status | Needs UI Fix |
| Progress | - |
| Prioritas | High |
| Target selesai | 07-Aug-2026 |

**Tujuan**  
Mencegah user melihat data palsu saat backend kosong atau gagal, karena ini berbahaya untuk dashboard operasional.

**Scope teknis**

- Cari fallback demo snapshot di workspace/dashboard/review/fetch jobs.
- Ganti dengan empty state atau error state.
- Pastikan state kosong tetap terlihat profesional.
- Jangan menutupi error API dengan sample data.

**Acceptance criteria**

- Backend kosong menampilkan empty state.
- Backend gagal menampilkan error state.
- Tidak ada sample data di environment non-demo.

---

## Checklist Singkat

### Done

- QA legacy push-sync dan StatusId Connection 1039.
- QA Review Detail actions.
- AI Config button diselesaikan/disembunyikan.
- Official/non-official flag.
- KPI bintang clickable.
- Icon action diperbaiki.
- QA Fetch Jobs utama.
- Merge commit Fetch Jobs.
- QA delta sync dan rekonsiliasi review lama.
- Deduplication index.

### Masih Partial / Needs QA / Needs UI Fix

- Backfill lokasi baru.
- List review 2 baris + reply status + response terakhir.
- Detail review dengan URL/foto/preview kanan.
- Reply official Google Business.
- Eskalasi ke PIC/WhatsApp.
- Job history/log real.
- Filter tanggal, dry run, retry, cancel.
- Status/counter/loading/empty/error Fetch Jobs.
- List hasil crawling.
- Metadata crawling Google Review.
- Workspace API.
- Hapus demo snapshot fallback.

### Belum Mulai

- Maker/reviewer tracking.
- AI scope final: Crawler memilih model, OneBox hanya `ai_enabled` dan `output_schema_version`.
- AI config di `Connection.Options` dan worklist.
- Scheduler core.
- Trigger scheduler non-blocking dan run history.
- Run Now dengan permission/quota.
- Scheduler UI.
- Scheduler multi-account/multi-company/multi-site test.
- Crawler gateway untuk scheduler.
- Monitoring scheduler.

