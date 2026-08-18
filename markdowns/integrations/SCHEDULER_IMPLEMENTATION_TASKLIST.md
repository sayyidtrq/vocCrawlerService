# Crawl Scheduler — Tasklist Implementasi (OneBox)

Berurutan. Tiap tugas berdiri di atas yang sebelumnya dan punya **garis selesai**
yang bisa diperiksa, bukan "kira-kira jalan".

Rancangan besarnya ada di [`SCHEDULER_CRAWLING_DESIGN.md`](SCHEDULER_CRAWLING_DESIGN.md).
Dokumen ini hanya urutan kerjanya.

---

## Kemajuan

Branch: `feature/DNGO19-3390_VOC-Crawl-Scheduler`

| Tugas | Status | Bukti |
|---|---|---|
| A1 migrasi skema | **selesai** | tabel ada, `UNIQUE` menolak duplikat (SQLSTATE 23000), round-trip up→down→up bersih |
| A2 model | **selesai** | `php -l` bersih; `daftarLokasi()` tahan JSON rusak |
| B1 parser cron + `berikutnya()` | **selesai** | 8/8 kasus lulus, termasuk 29 Feb 2028, tanggal 31 melewati Februari, dan aturan OR hari-bulan/hari-pekan |
| B2 validator | **selesai** | `*/5` ditolak dengan kalimat yang menyebut batasnya; cron/zona/target/cabang ngawur ditolak |
| C2 enqueue jalur bersama | **selesai** | aturan koneksi pindah ke `VocConnectionRule`; `VocController` berkurang 97 baris; regresi 4 layar 200 dan 5/3/200 tetap sama |
| C1 loop scheduler | **selesai** | 1 jadwal jatuh tempo → 1 run, `NextRunAt` maju ke 06:00 WIB; **8 instance bersamaan → tetap 1 run** |
| C3 pasang cron | **selesai** | baris cron diuji di lingkungan cron tiruan: tanpa flag diam, dengan flag `./run voc schedule` jalan |
| D1 nilai ulang dari data | **selesai** | `judgeBatch()` menandai gagal saat `inserted=0` dengan `time_limit` atau sort gagal, meski Crawler bilang sukses |
| D2 backoff & auto-disable | **selesai** | gagal ke-10 → jadwal mati sendiri dengan alasan tertulis, backoff mendorong 3 hari; overlap dicatat tanpa menaikkan FailStreak |
| E1 endpoint | **selesai** | 7 endpoint; 4 penolakan validasi tepat sasaran; Run Now tidak menggeser `NextRunAt` |
| E2 layar | **selesai** | halaman sendiri; pratinjau dihitung server; `node --check` lolos atas 15 KB JS hasil render |
| E3 riwayat jujur | **selesai** | run dilewati tampil dengan alasannya; kolom Masuk = yang tersimpan |
| E4 menu | **selesai** | tampil di sidebar (11 submenu VoC), hilang saat rollback |
| F1 pra-terbang | **selesai** | DDL lolos di **MySQL 5.7.44 STRICT**; unique menolak `1062`; bug `BASH_ENV` ditemukan & dihindari |
| F2 UAT dev | **menunggu deploy** | butuh akses dev — lihat [runbook](SCHEDULER_DEV_UAT_RUNBOOK.md) |

### Catatan urutan untuk C

C2 didahulukan dari C1. Task tidak boleh menyalin logika enqueue dari
`crawlStartAction()` — aturan "Connection mana yang benar-benar milik VoC"
sudah dua kali menjadi sumber bug serius (PVD97 diserobot IKS, PVD98 diserobot
Apps Kesehatan), dan menyalinnya berarti perbaikan berikutnya harus diingat di
dua tempat. Yang kedua pasti terlupa.

Bentuk yang dituju: pindahkan aturan itu ke satu pemilik (`Library\VocConnectionRule`),
lalu `VocController` dan service enqueue sama-sama memanggilnya. Sesudah itu C1
tinggal memakai service tersebut.

---

## Keputusan yang mengunci rancangan

Ditetapkan Sayyid, 11 Agustus 2026:

| Hal | Keputusan |
|---|---|
| Tempat scheduler | **OneBox (PHP)**, memakai container scheduler yang sudah ada |
| Prasyarat Crawler belum beres | **Lanjut, dengan rem di sisi OneBox** |
| Bentuk jadwal | **1 jadwal = banyak lokasi**, satu target, satu rentang, satu waktu |
| Garis UAT | kelimanya di UAT, termasuk alur utuh form → crawl terjadwal → review terlihat |

### Arsitektur yang disepakati

```
cron (* * * * *)  →  ./runx voc schedule
                          │
                          │ baca VocSchedule (MySQL OneBox)
                          │ ambil jadwal yang jatuh tempo
                          ▼
                   POST /api/integration/v1/crawl-jobs
                          │  (jalur SAMA dengan tombol manual)
                          ▼
                   Crawler queue → Selenium worker
                          │
                          ▼
                   crawlImport → Message/Ticket OneBox → layar Ulasan
```

**Scheduler tidak memanggil Selenium dan tidak menyentuh Postgres Crawler.** Ia
hanya menaruh pekerjaan lewat jalur enqueue yang sudah dipakai tombol manual.
Itu yang menjaga agar perbaikan pada jalur manual otomatis berlaku juga untuk
jalur terjadwal — jalur kedua yang "mirip" adalah cara paling pasti melahirkan
dua perilaku yang menyimpang perlahan.

### Penyimpangan yang disadari dari dokumen rancangan

| Rancangan | Di sini | Alasan |
|---|---|---|
| Loop tiap 30 detik | tiap **60 detik** (cron) | cron OneBox bergranularitas menit. Cukup, karena jadwal terkasar adalah per jam. |
| Postgres Crawler | MySQL OneBox | scheduler pindah rumah, ikut skemanya |
| Status dipercaya dari Crawler | **dinilai ulang dari data** | prasyarat §Rem belum beres di Crawler |

---

## Tahap A — Skema

### A1. Migrasi tabel `VocSchedule` dan `VocScheduleRun`

**Berkas:** `app/migrations/<ts>_1_123_0/VocSchedule.php`

`VocSchedule` (niat):

| kolom | tipe | catatan |
|---|---|---|
| `Id` | bigint PK AI | |
| `SiteId` | bigint NOT NULL | penyekat tenant, wajib di setiap query |
| `Name` | varchar(100) | dibaca manusia |
| `LocationIds` | longtext | JSON array `onebox_location_id` |
| `TargetReviewCount` | int | 1..300, sama batasnya dengan manual |
| `LookbackDays` | int NULL | rentang RELATIF; NULL = semua tanggal |
| `CronExpr` | varchar(64) | mis. `0 6 * * *` |
| `Timezone` | varchar(64) | IANA, default `Asia/Jakarta` |
| `Enabled` | tinyint(1) | |
| `Catchup` | tinyint(1) | default **0** |
| `NextRunAt` | datetime NULL | UTC, diindeks |
| `LastRunAt` | datetime NULL | |
| `FailStreak` | int default 0 | untuk backoff & auto-disable |
| `DisabledReason` | varchar(255) NULL | diisi saat auto-disable |
| `CreateDate/Creator/ModifyDate/Modifier/ExpireDate` | | ikut konvensi OneBox |

`VocScheduleRun` (kejadian):

| kolom | tipe | catatan |
|---|---|---|
| `Id` | bigint PK AI | |
| `ScheduleId` | bigint | |
| `SiteId` | bigint | |
| `ScheduledFor` | datetime NOT NULL | **waktu yang seharusnya**, UTC |
| `BatchId` | varchar(64) NULL | null bila gagal sebelum enqueue |
| `Status` | varchar(20) | `enqueued`/`succeeded`/`partial`/`failed`/`skipped_overlap`/`skipped_disabled` |
| `Reason` | varchar(500) NULL | kenapa dilewati/gagal, dalam kalimat |
| `Inserted/Scanned/OutOfRange` | int default 0 | untuk menilai ulang keberhasilan |
| `StartedAt/FinishedAt` | datetime NULL | |

**Kunci mati:** `UNIQUE KEY uq_schedule_slot (ScheduleId, ScheduledFor)`.

Inilah idempotensinya. Dua proses scheduler yang menyala bersamaan berebut
menulis baris yang sama, dan yang kalah mendapat pelanggaran unique — bukan run
kedua. Lebih kokoh daripada lock, karena lock bisa bocor kalau prosesnya mati
mendadak sementara unique constraint tidak bisa.

`ScheduleId` sengaja **tanpa foreign key**: riwayat harus tetap terbaca setelah
jadwalnya dihapus.

**Selesai bila:** migrasi `up` lalu `down` lalu `up` lagi bersih di lokal, dan
menyisipkan dua baris `VocScheduleRun` dengan `(ScheduleId, ScheduledFor)` sama
ditolak database.

### A2. Model Phalcon

**Berkas:** `app/models/VocSchedule.php`, `app/models/VocScheduleRun.php`

Model tipis. Semua aturan bisnis di service, bukan di model.

**Selesai bila:** `VocSchedule::findFirst()` mengembalikan baris di tinker/CLI.

---

## Tahap B — Mesin waktu

### B1. Parser cron + `hitungNextRun()`

**Berkas:** `app/library/VocCron.php`

Subset cron 5 kolom: menit, jam, hari-bulan, bulan, hari-pekan. Dukung `*`,
angka, daftar `1,3,5`, rentang `1-5`, langkah `*/15`. Tidak perlu `@yearly`,
`L`, `#` — tidak ada preset UI yang menghasilkannya, dan yang tidak dipakai
tidak perlu diuji.

Hitung dalam zona waktu jadwal, simpan hasilnya sebagai UTC.

Jangan simpan offset (`+07:00`): offset adalah nilai pada satu saat, bukan
aturan, dan akan salah begitu aturan waktunya berubah.

**Selesai bila** semua ini benar lewat skrip uji:

| ekspresi | dari | berikutnya (WIB) |
|---|---|---|
| `0 6 * * *` | 12 Agu 05:59 | 12 Agu 06:00 |
| `0 6 * * *` | 12 Agu 06:00 | 13 Agu 06:00 |
| `0 6 * * 1-5` | Jum 12 Agu 07:00 | Sen 15 Agu 06:00 |
| `*/15 * * * *` | 12 Agu 06:07 | 12 Agu 06:15 |
| `0 6 29 2 *` | 1 Jan 2026 | 29 Feb 2028 |
| `0 6 31 * *` | 31 Jan 06:30 | 31 Mar 06:00 (Feb dilewati) |

### B2. Validator jadwal

**Berkas:** `app/library/VocCron.php` (lanjutan)

Tolak: cron tidak sah, zona waktu tidak dikenal, `LocationIds` kosong, target di
luar 1..300, dan **frekuensi lebih rapat dari 1 jam**.

Batas frekuensi itu rem yang disepakati: satu run bisa memakan sepuluh menit
worker, jadi jadwal tiap 5 menit dijamin menumpuk pada dirinya sendiri.

**Selesai bila:** `*/5 * * * *` ditolak dengan kalimat yang menyebut batasnya,
`0 * * * *` diterima.

---

## Tahap C — Mesin scheduler

### C1. `VocTask::scheduleAction()` — pengambilan idempotent

**Berkas:** `app/tasks/VocTask.php`

```
untuk tiap VocSchedule WHERE Enabled=1 AND NextRunAt <= UTC_NOW():
    scheduledFor = NextRunAt
    INSERT VocScheduleRun (ScheduleId, scheduledFor, 'enqueued')
        -> gagal duplicate = instance lain sudah mengambilnya, LANJUT diam-diam
    kalau jadwal ini masih punya run 'enqueued' yang belum selesai:
        ubah jadi 'skipped_overlap' + alasan, majukan NextRunAt, lanjut
    enqueue lewat jalur yang sama dengan manual
    NextRunAt = VocCron::hitungNextRun(...)
```

Idempotency key ke Crawler:

```
sched-{ScheduleId}-{ScheduledFor ISO8601 UTC}
```

Diturunkan dari **waktu yang seharusnya**, bukan `now()`. Scheduler yang
terlambat 40 detik karena worker padat harus menghasilkan kunci yang sama dengan
yang tepat waktu — kalau tidak, keterlambatan berubah menjadi run ganda.

**Selesai bila:** dijalankan manual dua kali beruntun untuk satu jadwal yang
jatuh tempo hanya menghasilkan **satu** `VocScheduleRun` dan **satu** batch.

### C2. Enqueue lewat jalur bersama

**Berkas:** `app/controllers/VocController.php` (ekstraksi), `app/tasks/VocTask.php`

Pisahkan inti `crawlStartAction()` menjadi metode yang tidak bergantung
`$this->request`, lalu panggil dari dua sisi.

Jangan menyalin logikanya ke task. Penyalinan berarti perbaikan berikutnya harus
diingat dua kali, dan yang kedua pasti terlupa.

**Selesai bila:** batch hasil scheduler tampil di Riwayat Fetch dengan bentuk
yang persis sama dengan batch manual.

### C3. Pasang cron

**Berkas:** `crontab.txt`

```
* * * * * [ "${VOC_WORKERS:-0}" != "0" ] && ./runx voc schedule
```

Dijaga variabel lingkungan supaya hanya menyala di container yang memang
ditugaskan, dan bisa dimatikan tanpa deploy ulang kalau ada masalah.

Variabelnya wajib ikut didaftarkan di `onecloud/docker-compose.yml` **dan**
`onecloud/docker-compose.base.yml`: blok `environment:` di sana daftar-putih,
jadi variabel yang tidak disebut tidak pernah sampai ke dalam container.

**Selesai bila:** log cron menunjukkan task berjalan tiap menit dan berhenti
tanpa error ketika tidak ada jadwal jatuh tempo.

---

## Tahap D — Rem keselamatan

Ini bagian yang disepakati sebagai pengganti prasyarat Crawler yang belum beres.

### D1. Nilai keberhasilan dari DATA, bukan dari field status

**Berkas:** `app/tasks/VocTask.php`

Crawler melaporkan `status: "success"` untuk run yang memindai 250 kartu,
menyimpan nol, dan mati kena batas waktu — terbukti pada batch `db916555`.
Bagi scheduler, "berhasil" adalah dasar untuk memajukan jadwal dan menganggap
tidak ada masalah. Selama sinyal itu berbohong, seluruh backoff di D2 dibangun
di atas masukan yang salah.

Aturan penilaian ulang:

| kondisi | dicatat sebagai |
|---|---|
| `inserted > 0` | `succeeded` |
| `inserted = 0` dan `stopped_reason = time_limit` | **`failed`** |
| `inserted = 0` dan `sort_applied = false` dengan rentang tanggal | **`failed`** |
| `inserted = 0`, berhenti wajar, tidak ada anomali | `succeeded` (memang tidak ada ulasan baru) |
| sebagian cabang gagal | `partial` |

Baris terakhir penting: nol ulasan baru **bukan** kegagalan kalau memang tidak
ada yang baru. Menganggapnya gagal akan mematikan jadwal yang justru bekerja
benar.

**Selesai bila:** batch `db916555` (tersedia di dev) dinilai `failed`, dan batch
`beb57fcf` dinilai `succeeded`.

### D2. Backoff dan auto-disable

**Berkas:** `app/tasks/VocTask.php`

- gagal beruntun 3× → `NextRunAt` dimundurkan berlipat (1×, 2×, 4× interval)
- gagal beruntun 10× → `Enabled=0`, `DisabledReason` diisi kalimat yang menyebut
  apa yang perlu diperbaiki
- satu run berhasil → `FailStreak` kembali 0

Jadwal rusak yang menyala selamanya adalah cara sistem membuang sumber daya
tanpa ada yang memperhatikan.

**Selesai bila:** disimulasikan 10 kegagalan beruntun, jadwal mati sendiri dengan
alasan tertulis, dan tidak dijalankan lagi pada menit berikutnya.

---

## Tahap E — API dan layar

### E1. Endpoint CRUD jadwal

**Berkas:** `app/controllers/VocController.php`

| aksi | guna |
|---|---|
| `schedulesData` | daftar + ringkasan run terakhir |
| `scheduleSave` | buat/ubah, lewat validator B2 |
| `scheduleToggle` | aktif/nonaktif (**bukan** hapus) |
| `scheduleDelete` | hapus jadwal, riwayat tetap tinggal |
| `scheduleRunNow` | jalankan sekarang **tanpa** mengubah `NextRunAt` |
| `scheduleRuns` | riwayat run satu jadwal |

`scheduleRunNow` tidak boleh menggeser jadwal berikutnya: "coba sekarang" adalah
tindakan uji, dan menggesernya diam-diam akan membuat orang kehilangan slot
paginya karena menekan tombol uji.

**Selesai bila:** keenamnya balas 200 dengan bentuk JSON yang konsisten, dan
`scheduleSave` menolak masukan tidak sah dengan kalimat yang menyebut apa yang
salah.

### E2. Layar Jadwal Crawl

**Berkas:** `app/views/Voc/schedules.volt`, migrasi menu

Formulir sesuai §5 dokumen rancangan:

- nama, pilih banyak cabang, target, rentang (preset)
- waktu: **preset** (tiap hari / hari kerja / tiap minggu / tiap jam) dan
  "Lanjutan (cron)" sebagai jalan keluar, bukan jalan utama
- **kotak pratinjau berisi tiga waktu berikutnya secara harfiah**

Kotak pratinjau itu bagian terpenting di layar ini. Cron tidak bisa dibaca
sekilas, dan jadwal yang salah tidak menampakkan diri sampai besok pagi — atau
tidak pernah, kalau salahnya membuat jadwal tidak menyala sama sekali.

Sebutkan biayanya sebelum Simpan: "jadwal ini menghasilkan ±N run per hari".
Tidak melarang, hanya menyebutkan.

**Selesai bila:** membuat jadwal dari layar menghasilkan `NextRunAt` yang sama
dengan yang tertulis di pratinjau.

### E3. Riwayat jadwal yang jujur

**Berkas:** `app/views/Voc/schedules.volt`

Tampilkan run yang **dilewati** berikut alasannya, bukan hanya yang berjalan.
Tanpa baris itu orang melihat lubang di tanggal dan menyimpulkan sistemnya rusak.

Kolom "ulasan baru" berisi yang **benar-benar masuk**, bukan yang dipindai —
kesalahan "250 dari 5 review terbaca" tidak boleh terulang di layar ini.

**Selesai bila:** run `skipped_overlap` tampil sebagai baris dengan alasannya,
bukan hilang.

### E4. Menu

**Berkas:** migrasi `Menu.php` baru

Tambah `voc_schedules` di bawah grup Setting, ikut pola migrasi menu yang sudah
ada. **Salin audience dari menu sekelompok**, jangan tulis RoleId langsung —
RoleId berbeda di tiap environment.

Ingat: yang menentukan menu tampil adalah **`Enabled`**, bukan `ExpireDate`.

**Selesai bila:** menu muncul di sidebar dev untuk role yang sama dengan Fetch Jobs.

---

## Tahap F — Dev dan UAT

### F1. Deploy dan migrasi di dev

Migrasi dev = **MySQL 5.7**, lokal 8.0. Periksa tidak ada sintaks khusus MySQL 8
sebelum jalan. Pastikan `VOC_WORKERS=1` terpasang di container scheduler dev.

### F2. UAT

Garis selesai sesuai kesepakatan:

| # | Skenario | Bukti yang dikumpulkan |
|---|---|---|
| 1 | **Alur utuh**: buat jadwal dari form → tunggu waktunya → crawl jalan sendiri → review baru terlihat di layar Ulasan | tangkapan layar form, baris riwayat, dan review baru dengan waktu masuk sesudah jadwal |
| 2 | Jadwal jalan sendiri tanpa disentuh, batch terbentuk di Crawler | `batch_id` di Riwayat Fetch cocok dengan `VocScheduleRun.BatchId` |
| 3 | Riwayat jujur termasuk yang dilewati | baris `skipped_overlap` tampil dengan alasannya |
| 4 | Tahan banting | dua instance bersamaan → nol run ganda; restart container di tengah → satu run susulan, bukan enam |
| 5 | Run Now + aktif/nonaktif | Run Now tidak menggeser `NextRunAt`; nonaktif menghentikan tanpa menghapus riwayat |

**UAT dianggap lulus hanya bila kelimanya terbukti dengan bukti, bukan dengan
keyakinan.**

---

## Yang sengaja TIDAK dikerjakan

| Bukan | Alasan |
|---|---|
| Cancel run terjadwal | Butuh endpoint Crawler yang belum ada |
| Dry run | Sama, butuh sisi Crawler |
| Retensi/pembersihan riwayat | Dibutuhkan, tetapi keputusan terpisah |
| Jadwal per-lokasi dengan jam berbeda | Sudah diputuskan: 1 jadwal = banyak lokasi |
| Notifikasi email/WA saat auto-disable | Tahap berikutnya; untuk sekarang cukup terlihat di layar |
