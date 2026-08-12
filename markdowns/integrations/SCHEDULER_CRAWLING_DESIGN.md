# Scheduler Crawling — Sistem, Mekanisme, dan Pengalaman Pakai

Status: rancangan. Belum ada satu pun endpoint scheduler di Crawler
(`apps/api/app_api/routers/` tidak memuat `schedule`, `cancel`, maupun `retry`).
Dokumen ini menetapkan bentuk yang dituju sebelum baris pertama ditulis.

Pembaca yang dituju: pengembang Crawler dan pengembang OneBox. Bagian 5 ditujukan
untuk siapa pun yang merancang layarnya.

---

## 1. Kenapa scheduler, dan kenapa ia berbahaya

Hari ini penarikan dijalankan manual dari layar Fetch Jobs. Itu jujur: satu orang
menekan tombol, menunggu, dan melihat hasilnya. Scheduler menghapus orang itu
dari lingkaran — dan bersamanya menghapus satu-satunya yang selama ini menyadari
ketika ada yang aneh.

Karena itu urutan kerjanya bukan "bikin cron dulu, rapikan belakangan".
Otomatisasi memperbanyak kejadian; kalau satu run bisa gagal diam-diam, seratus
run terjadwal akan gagal diam-diam seratus kali dan tidak ada yang tahu sampai
seseorang bertanya kenapa dashboard sepi.

### Bukti dari produksi yang harus dijawab lebih dulu

Satu run manual pada 11 Agustus 2026, batch `db916555`:

| target | `sort_applied` | `scanned` | `inserted` | `stopped_reason` | status yang dilaporkan |
|---|---|---|---|---|---|
| 5 | **false** | 250 | 0 | `time_limit` (600 dtk) | **`success`** |

Run itu membakar sepuluh menit worker, tidak menyimpan apa pun, dan melapor
berhasil. Run pembanding ke lokasi yang sama, rentang tanggal yang sama, dua
menit kemudian, dengan `sort_applied: true` selesai dalam hitungan detik dengan
10 dari 10 masuk.

Kalau perilaku ini dijadwalkan tiap jam, hasilnya adalah worker yang sibuk
sepanjang hari, nol data, dan papan status hijau. **Ini prasyarat, bukan catatan
kaki** — lihat §7.

---

## 2. Model data

Tiga tabel. Pemisahan `schedule` (niat) dari `schedule_run` (kejadian) disengaja:
mengubah jadwal tidak boleh menulis ulang sejarah, dan sejarah harus tetap
terbaca setelah jadwalnya dihapus.

### 2.1 `crawl_schedules`

| kolom | tipe | catatan |
|---|---|---|
| `id` | bigint PK | |
| `company_id` | bigint | penyekat tenant, wajib di setiap query |
| `name` | varchar(100) | dibaca manusia, mis. "Hermina harian pagi" |
| `location_ids` | jsonb | daftar `onebox_location_id` |
| `target_review_count` | int | sama artinya dengan target manual |
| `lookback_days` | int null | rentang RELATIF, mis. 7 = "7 hari terakhir" |
| `cron_expr` | varchar(64) | mis. `0 6 * * *` |
| `timezone` | varchar(64) | IANA, mis. `Asia/Jakarta` |
| `enabled` | bool | |
| `max_runtime_seconds` | int | batas atas satu run |
| `catchup` | bool | default **false**, lihat §3.4 |
| `next_run_at` | timestamptz | dihitung, diindeks |
| `last_run_at` | timestamptz null | |
| `created_by` / `created_at` / `updated_at` | | |

`lookback_days` disimpan **relatif**, bukan sebagai tanggal absolut. Jadwal
berarti "tujuh hari terakhir, setiap hari" — menyimpan tanggal absolut akan
membuat jadwal menua dan menarik jendela yang sama berulang-ulang.

Ini berbeda dari tombol **Ulangi** di riwayat, yang justru memakai tanggal
absolut karena artinya "ulangi hal yang sama persis". Dua arti berbeda, dua
penyimpanan berbeda; menyamakannya akan salah di salah satu sisi.

### 2.2 `crawl_schedule_runs`

| kolom | tipe | catatan |
|---|---|---|
| `id` | bigint PK | |
| `schedule_id` | bigint FK | `ON DELETE SET NULL` — riwayat hidup lebih lama dari jadwalnya |
| `company_id` | bigint | |
| `scheduled_for` | timestamptz | **waktu yang seharusnya**, bukan waktu jalan |
| `batch_id` | uuid null | batch yang dihasilkan, null bila gagal sebelum enqueue |
| `status` | enum | `skipped_overlap`, `enqueued`, `succeeded`, `partial`, `failed` |
| `reason` | text null | kenapa dilewati/gagal, dalam kalimat |
| `started_at` / `finished_at` | timestamptz null | |

`UNIQUE (schedule_id, scheduled_for)` — **inilah idempotensinya**. Dua proses
scheduler yang menyala bersamaan akan berebut menulis baris yang sama dan yang
kalah mendapat pelanggaran unique, bukan run kedua. Ini lebih kokoh daripada
distributed lock karena tidak bisa bocor akibat proses mati mendadak.

### 2.3 Perluasan `crawl_jobs`

Tambahkan `origin` (`manual` | `schedule`) dan `schedule_run_id` nullable.
Tanpa ini tidak ada cara menjawab "kenapa worker sibuk jam 3 pagi", dan kuota
manual tidak bisa dipisahkan dari kuota terjadwal.

---

## 3. Mekanisme

### 3.1 Bentuk loop

```
tiap 30 detik:
  ambil jadwal WHERE enabled AND next_run_at <= now()
  untuk tiap jadwal:
    scheduled_for = next_run_at
    coba INSERT crawl_schedule_runs (schedule_id, scheduled_for, 'enqueued')
      -> gagal unique = instance lain sudah mengambilnya, lewati tanpa suara
    kalau jadwal ini masih punya run yang belum selesai:
      tandai 'skipped_overlap', catat alasannya, lanjut
    enqueue batch lewat jalur yang SAMA dengan manual
    next_run_at = hitung berikutnya (cron_expr, timezone)
```

Interval 30 detik, bukan per menit: cron bergranularitas menit, dan polling
tepat semenit akan melewatkan tepat pada perpindahan menit yang sial.

### 3.2 Pakai ulang antrean yang sudah ada, jangan bikin jalur kedua

Scheduler **tidak** memanggil Selenium. Ia hanya menaruh baris di
`crawl_jobs` lewat `CrawlJobService.enqueue()` — jalur yang sama persis dengan
tombol manual. Worker tidak perlu tahu asal-usul job.

Ini yang menjaga agar perbaikan pada jalur manual otomatis berlaku untuk jalur
terjadwal. Jalur kedua yang "mirip" adalah cara paling pasti melahirkan dua
perilaku yang menyimpang perlahan sampai tidak ada yang hafal keduanya.

### 3.3 Idempotency key

```
schedule-{schedule_id}-{scheduled_for dalam ISO8601 UTC}
```

Diturunkan dari **waktu yang seharusnya**, bukan waktu sekarang. Scheduler yang
terlambat 40 detik karena worker padat harus menghasilkan kunci yang sama
dengan yang tepat waktu — kalau tidak, keterlambatan berubah menjadi run ganda.

### 3.4 Tumpang tindih dan run yang terlewat

**Tumpang tindih** — jadwal tiap jam, run sebelumnya belum selesai. Default:
**lewati**, catat `skipped_overlap` dengan alasannya. Menumpuk run atas lokasi
yang sama tidak menghasilkan data lebih banyak; ia hanya memperebutkan worker
dengan dirinya sendiri.

**Run terlewat** karena sistem mati — default `catchup = false`. Saat menyala
kembali, jalankan **satu** run untuk waktu terdekat dan lewati sisanya dengan
`reason` yang menyebutkan berapa yang dilewati. Menyusul enam jam yang hilang
dengan enam run sekaligus akan membanjiri worker tepat pada saat sistem baru
pulih — waktu paling rapuh untuk dibebani.

### 3.5 Zona waktu

Simpan `cron_expr` + `timezone` IANA, hitung `next_run_at` dalam zona itu, simpan
sebagai UTC. Jangan simpan offset (`+07:00`): offset adalah nilai pada satu saat,
bukan aturan, dan akan salah begitu ada perubahan aturan waktu.

Untuk Asia/Jakarta yang tidak mengenal DST ini terasa berlebihan hari ini. Ia
menjadi penting pada tenant pertama di zona yang mengenalnya, dan pada saat itu
data lama sudah terlanjur tersimpan dalam bentuk yang salah.

### 3.6 Concurrency dan backoff

- Batas **per company**: maksimum N job berjalan bersamaan. Satu tenant dengan
  80 lokasi tidak boleh memenuhi antrean tenant lain.
- Batas **per lokasi**: satu job aktif. Sudah ditegakkan oleh
  `uq_crawl_jobs_batch_location`, pastikan tetap berlaku untuk job terjadwal.
- Backoff: jadwal yang gagal berturut-turut mendapat jeda meningkat
  (1×, 2×, 4× interval) sampai satu run berhasil. Jadwal yang gagal karena
  lokasinya dihapus akan gagal selamanya; menjalankannya tiap jam hanya
  memenuhi log.
- **Auto-disable**: setelah K kegagalan beruntun (usul: 10), matikan jadwal dan
  beri tahu. Jadwal rusak yang menyala selamanya adalah cara sistem membuang
  sumber daya tanpa ada yang memperhatikan.

---

## 4. Langkah implementasi

Tiap tahap berdiri sendiri dan bisa dikirim tanpa menunggu tahap berikutnya.

### Tahap 0 — Prasyarat (WAJIB lebih dulu)

Bukan bagian scheduler, tetapi menjadwalkan perilaku yang rusak hanya
memperbanyak kerusakannya. Lihat §7 untuk rinciannya.

1. `sort_applied=false` + rentang tanggal harus menghentikan run dengan status
   jujur, bukan sekadar menulis `range_warning`.
2. Beri batas pada **pemindaian**, bukan hanya pada penerimaan.
3. Run yang berhenti karena `time_limit` dengan 0 tersimpan jangan `success`.

**Selesai bila:** run bertarget 5 dengan rentang tanggal tidak akan pernah
memindai 250 kartu, dan run yang tidak menyimpan apa pun tidak pernah tampil
hijau.

### Tahap 1 — Skema dan perhitungan waktu

Migrasi untuk ketiga tabel/kolom di §2. Fungsi `hitung_next_run(cron, tz, dari)`
dengan uji: tengah malam, akhir bulan, 29 Februari, dan pergantian aturan zona
waktu.

**Selesai bila:** `next_run_at` bisa dihitung dan diperiksa tanpa satu pun job
dijalankan.

### Tahap 2 — Loop scheduler, satu instance

Loop §3.1 dengan pengambilan idempotent. Belum ada UI; jadwal dibuat lewat SQL.

**Selesai bila:** jadwal tiap 5 menit menghasilkan tepat satu batch tiap 5 menit
selama satu jam, dan `crawl_schedule_runs` mencatat semuanya.

### Tahap 3 — Ketahanan

Uji dua instance scheduler berjalan bersamaan — harus tetap satu run per slot.
Uji tumpang tindih, catchup, backoff, auto-disable.

**Selesai bila:** dua instance selama satu jam menghasilkan nol run ganda, dan
mematikan lalu menyalakan proses selama 30 menit menghasilkan satu run susulan,
bukan enam.

### Tahap 4 — API

| endpoint | guna |
|---|---|
| `GET/POST /integration/v1/crawl-schedules` | daftar, buat |
| `PATCH/DELETE /integration/v1/crawl-schedules/{id}` | ubah, hapus |
| `POST /integration/v1/crawl-schedules/{id}/run-now` | jalankan sekarang, tanpa mengubah `next_run_at` |
| `GET /integration/v1/crawl-schedules/{id}/runs` | riwayat |

Scope baru: `schedule:read`, `schedule:write`. Jangan menumpang `crawl:enqueue` —
kemampuan menjadwalkan berbeda dari kemampuan menjalankan sekali.

**Sekalian minta di sini, karena layar butuh keduanya:**
`POST /crawl-jobs/{batch_id}/cancel` dan `POST /crawl-jobs/{batch_id}/retry`.
Keduanya belum ada, dan tanpa cancel sebuah run terjadwal yang salah hanya bisa
ditunggu sampai batas waktunya habis.

### Tahap 5 — UI OneBox

Lihat §5.

### Tahap 6 — Pemantauan

Metrik: jadwal aktif, run per status per hari, waktu tunggu antrean, rasio
`scanned/inserted`. Peringatan bila jadwal ter-auto-disable, atau bila sebuah
jadwal gagal 3× beruntun.

Rasio `scanned/inserted` sengaja dijadikan metrik utama: itulah angka yang
membedakan sistem yang bekerja dari sistem yang sibuk.

---

## 5. Pengalaman pakai: menyetel waktu crawling

Yang menyetel jadwal ini adalah staf humas rumah sakit, bukan pengembang.
Mereka tidak akan mengetik `0 6 * * 1-5`, dan tidak seharusnya.

### 5.1 Tanyakan tiga hal, bukan tujuh

Susunan formulir yang diusulkan:

```
Nama jadwal      [ Hermina harian pagi                    ]

Cabang           [ 12 cabang dipilih            ▾ ]
Ambil            [ 50 ] ulasan terbaru per cabang
Rentang          [ 7 hari terakhir              ▾ ]

Jalankan         ( ) Tiap hari     pukul [ 06:00 ]
                 (•) Hari kerja    pukul [ 06:00 ]
                 ( ) Tiap minggu   [ Senin ▾ ] pukul [ 06:00 ]
                 ( ) Tiap jam
                 ( ) Lanjutan (cron)

                 Waktu Indonesia Barat (WIB)

 ┌──────────────────────────────────────────────────┐
 │ Berikutnya: Senin, 12 Agu 2026 · 06:00 WIB       │
 │ Sesudahnya: Selasa 06:00 · Rabu 06:00            │
 │ Perkiraan: ±12 menit, 12 cabang berurutan        │
 └──────────────────────────────────────────────────┘
```

Kotak pratinjau itu bagian terpenting di layar ini. Cron tidak bisa dibaca
sekilas, dan kesalahan jadwal tidak menampakkan diri sampai besok pagi — atau
tidak pernah, kalau salahnya membuat jadwal tidak pernah menyala. Menampilkan
**tiga waktu berikutnya secara harfiah** mengubah verifikasi dari "percaya" jadi
"lihat".

Perkiraan durasi dihitung dari riwayat nyata lokasi itu, bukan angka tetap.
Kalau belum ada riwayat, tulis "belum bisa diperkirakan" — jangan mengarang.

### 5.2 Jam yang ditawarkan bukan sembarang jam

Preset default sebaiknya **06:00** dan bukan tengah malam:

- Ulasan yang masuk semalam sudah terkumpul.
- Humas membuka OneBox pagi hari; data yang baru tiba pukul 06:00 terasa segar,
  data pukul 00:00 sudah berumur delapan jam saat dibaca.
- Selenium bersaing dengan lebih sedikit beban lain.

Kalau banyak cabang, **sebar** jadwalnya. Dua belas cabang pada 06:00 berarti
antrean panjang dan cabang terakhir selesai jauh setelah yang pertama. Tawarkan
"sebar dalam 30 menit" sebagai centang, dan jelaskan akibatnya dalam satu
kalimat.

### 5.3 Katakan biayanya sebelum disimpan

Satu run bisa memakan sepuluh menit worker. Jadwal tiap jam untuk 12 cabang
adalah dua ribu run sebulan. Layar harus menyebut itu **sebelum** tombol Simpan,
bukan sesudah tagihan kuota membengkak:

> Jadwal ini menghasilkan sekitar **288 run per hari** (12 cabang × 24 jam).
> Ulasan Google jarang berubah secepat itu — **tiap hari** biasanya sudah cukup.

Tidak melarang. Menyebutkan, lalu membiarkan orangnya memutuskan.

### 5.4 Riwayat harus menjelaskan, bukan sekadar mencatat

Riwayat jadwal wajib menampilkan run yang **dilewati** berikut alasannya, bukan
hanya yang berjalan:

```
12 Agu 06:00   selesai      12 cabang · 143 ulasan baru        4 mnt
11 Agu 06:00   dilewati     run kemarin belum selesai
10 Agu 06:00   sebagian     9 dari 12 cabang · 3 gagal          11 mnt
09 Agu 06:00   selesai      12 cabang · 87 ulasan baru          4 mnt
```

Baris "dilewati" adalah yang paling sering ditanyakan dan paling sering hilang
dari rancangan. Tanpa baris itu, orang melihat lubang di tanggal dan menyimpulkan
sistemnya rusak.

Kolom "ulasan baru" harus berisi yang **benar-benar masuk**, bukan yang dipindai.
Layar Fetch Jobs pernah menampilkan "250 dari 5 review terbaca" untuk run yang
menyimpan nol — kesalahan yang sama tidak boleh diulang di layar jadwal.

### 5.5 Matikan, jangan hapus

Sediakan sakelar aktif/nonaktif yang menonjol, dan letakkan Hapus jauh darinya.
Orang yang ingin "berhenti sebentar" hampir selalu bermaksud menonaktifkan;
menghapus akan membawa serta riwayatnya dan tidak bisa dibatalkan.

### 5.6 Jangan sembunyikan kegagalan

Jadwal yang gagal 3× beruntun harus terlihat dari daftar jadwal — lencana merah
pada barisnya, bukan hanya di halaman rincian. Jadwal yang di-auto-disable harus
mengatakannya dengan jelas dan menyebut apa yang perlu diperbaiki.

---

## 6. Yang sengaja TIDAK dikerjakan

| Bukan | Alasan |
|---|---|
| Retensi dan pembersihan riwayat | Dibutuhkan, tetapi bukan bagian scheduler. Putuskan terpisah. |
| Jadwal per-lokasi dengan jam berbeda-beda | Tunggu ada yang memintanya. Menebak akan melahirkan model data yang lebih rumit tanpa pemakai. |
| Penjadwalan adaptif (sering kalau ramai) | Menarik, tetapi mustahil dievaluasi sebelum jadwal tetap terbukti jalan. |
| Antarmuka cron mentah sebagai jalur utama | Disediakan sebagai "Lanjutan", bukan bawaan. |

---

## 7. Prasyarat yang menghalangi, dengan buktinya

**Jangan mulai Tahap 1 sebelum ketiganya beres.**

### 7.1 Pemindaian tak berbatas ketika penerimaan nol

Syarat berhenti loop scraper adalah `len(reviews) < target` — hanya menghitung
ulasan yang **diterima**. Ketika `sort_applied=false` dan rentang tanggal
dipakai, urutan Google jatuh ke "paling relevan" sehingga menemukan satu ulasan
di luar rentang tidak membuktikan apa pun tentang sisanya. Penyaring kehilangan
daya berhentinya; loop menggulir sampai batas waktu.

Akibatnya target berhenti berfungsi sebagai batas kerja. Batch `db916555`:
target 5, dipindai 250, tersimpan 0, berhenti karena `time_limit`.

### 7.2 Run gagal dilaporkan berhasil

Batch yang sama: `status: "success"`, `counts.succeeded: 1`. Bagi scheduler,
"berhasil" adalah dasar untuk memajukan `next_run_at` dan menganggap tidak ada
masalah. Selama sinyal ini berbohong, seluruh backoff dan auto-disable di §3.6
dibangun di atas masukan yang salah — dan justru akan menyembunyikan kegagalan
lebih rapi daripada sekarang.

### 7.3 Tidak ada cancel

Tidak ada `POST /crawl-jobs/{id}/cancel`. Run terjadwal yang salah hanya bisa
ditunggu sampai batas waktunya habis. Untuk pekerjaan manual itu merepotkan;
untuk pekerjaan otomatis yang berulang tiap jam, itu berarti tidak ada rem.

---

## 8. Ringkasan keputusan

| Keputusan | Pilihan | Alasan singkat |
|---|---|---|
| Idempotensi | `UNIQUE (schedule_id, scheduled_for)` | tidak bisa bocor karena proses mati |
| Kunci idempotency | dari `scheduled_for`, bukan `now()` | keterlambatan tidak menjadi run ganda |
| Tumpang tindih | lewati, catat alasannya | run bertumpuk berebut worker dengan dirinya |
| Catchup | mati, satu run susulan | jangan membanjiri sistem yang baru pulih |
| Zona waktu | IANA + cron, hitung ke UTC | offset adalah nilai, bukan aturan |
| Jalur enqueue | pakai ulang jalur manual | satu perbaikan berlaku untuk keduanya |
| Rentang tanggal | relatif (`lookback_days`) | jadwal tidak boleh menua |
| Bentuk UI utama | preset + pratinjau 3 waktu berikutnya | jadwal salah tidak menampakkan diri sampai besok |
| Gagal beruntun | backoff lalu auto-disable | jadwal rusak jangan menyala selamanya |
