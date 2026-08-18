# Multi-tenancy VoC — Tasklist Pengujian

Pasangan dari [MULTITENANCY_VOC_PEMAHAMAN.md](MULTITENANCY_VOC_PEMAHAMAN.md).
Baca dokumen itu dulu; tasklist ini menganggap isinya sudah dipahami.

**Sasaran hari ini:** membuktikan bahwa site kedua dengan company kedua benar-benar
terpisah dari site 169 / company 3 — dan menemukan di mana ia **tidak** terpisah.

**Prinsipnya:** uji negatif lebih penting daripada uji positif. Kegagalan tenancy
yang mahal adalah yang tidak berbunyi. Fase C adalah inti pengujian ini; kalau
waktunya mepet, kerjakan A, B ringkas, lalu langsung C.

**Aturan main:**

- Setiap tugas punya **Lulus bila** yang bisa dijawab ya/tidak, bukan "kelihatannya jalan".
- Bukti dikumpulkan (tangkapan layar / keluaran SQL), bukan diyakini.
- Semua SQL di sini **read-only** kecuali yang ditandai TULIS.
- Ganti `<SITE_B>`, `<COMPANY_B>`, `<TOKEN_B>` sesuai yang dipakai.

---

## Ringkasan fase

| Fase | Isi | Perkiraan |
|---|---|---|
| A | Siapkan tenant kedua | 60–90 mnt |
| B | Isolasi jalur baca (layar & API) | 30 mnt |
| C | **Uji negatif — lintas tenant** | 60 mnt |
| D | Isolasi jalur tulis (crawl & scheduler) | 45 mnt |
| E | Putuskan celah yang ditemukan | 30 mnt |

---

## FASE A — Siapkan tenant kedua

### A1. Tentukan dulu bentuk ujinya

Ada dua kemungkinan, dan **hasil ujinya berbeda**. Pastikan mana yang dipakai:

| Bentuk | Site OneBox | Company Crawler | Yang diuji |
|---|---|---|---|
| **Penuh** | site baru `<SITE_B>` | company baru `<COMPANY_B>` | pemisahan sungguhan, dua sumbu sekaligus |
| Separuh | site baru `<SITE_B>` | company sama (3) | hanya pemisahan sisi OneBox |

**Pakai bentuk Penuh.** Bentuk separuh tidak menguji `assertTenant()` sama sekali,
karena `whoami()` akan selalu cocok.

Prasyarat dari tim Crawler: satu company baru + satu service token dengan scope
`reviews:read`, plus lokasi uji milik company itu.

- [ ] Bentuk uji disepakati
- [ ] `<COMPANY_B>` dan `<TOKEN_B>` diterima dari tim Crawler

### A2. Buat Site B di OneBox

- [ ] Baris `Site` baru dibuat (catat `<SITE_B>`)
- [ ] User uji dibuat dan diikat ke `<SITE_B>` lewat `UserRole`
- [ ] Login memakai user itu berhasil dan sesi membawa `siteid = <SITE_B>`

**Lulus bila:** login sebagai user B menampilkan sidebar, dan `getSiteId()`
mengembalikan `<SITE_B>` (paling cepat dibuktikan dari data yang tampil di
layar VoC — harus kosong, bukan data Hermina).

### A3. Jalankan migrasi & entitlement untuk Site B

Menu VoC hanya tampil kalau ada baris `Permission` untuk role yang dipakai, dan
sebagian layar bergantung `Benefit`/`SiteBenefit`.

- [ ] `php migrate.php` sudah pernah jalan di environment ini
- [ ] Menu VoC muncul di sidebar Site B
- [ ] Paket & Kuota Site B terisi (atau sengaja dikosongkan, dicatat)

**Lulus bila:** enam layar VoC bisa dibuka sebagai user B tanpa 500.

Kalau menu tidak muncul, periksa ini dulu — bukan menebak:

```sql
SELECT m.Code, m.Enabled, p.RoleId, p.SiteId, p.ActionId
  FROM Menu m
  LEFT JOIN Permission p ON p.ObjectId = m.Id AND p.ObjectName = 'Menu'
 WHERE m.Code LIKE 'voc%' AND p.SiteId = <SITE_B>
 ORDER BY m.Code;
```

Ingat: yang menentukan menu tampil adalah `Menu.Enabled`, **bukan** `ExpireDate`.

### A4. Buat lokasi & koneksi VoC untuk Site B

- [ ] Minimal **2 lokasi** dibuat untuk Site B (satu saja tidak cukup untuk
      menguji pemilihan `$base`)
- [ ] Koneksi VoC dibuat untuk tiap lokasi, dengan `Options` berisi
      `company_id = <COMPANY_B>`, `service_token = <TOKEN_B>`, `api_mode = service`,
      `onebox_location_id` menunjuk lokasi yang benar

**Lulus bila** kueri ini menunjukkan dua tenant yang bersih dan terpisah:

```sql
SELECT c.SiteId,
       COUNT(*)                                                                     AS koneksi,
       GROUP_CONCAT(DISTINCT JSON_UNQUOTE(JSON_EXTRACT(c.Options,'$.company_id')))  AS company_id,
       COUNT(DISTINCT SHA1(JSON_UNQUOTE(JSON_EXTRACT(c.Options,'$.service_token')))) AS token_unik,
       COUNT(DISTINCT c.Url)                                                         AS url_unik
  FROM Connection c
 WHERE c.ProviderId = 'PVD99'
 GROUP BY c.SiteId;
```

Harapan: **dua baris**, `company_id` beda, `token_unik` = 1 per site, dan tidak
ada satu pun site yang punya lebih dari satu `company_id`.

### A5. Pastikan lokasi tidak bertabrakan

`Location` global, jadi ini tidak dijaga skema — harus diperiksa manual.

```sql
SELECT JSON_UNQUOTE(JSON_EXTRACT(c.Options,'$.onebox_location_id')) AS lokasi_id,
       COUNT(DISTINCT c.SiteId) AS dipakai_berapa_site,
       GROUP_CONCAT(DISTINCT c.SiteId) AS site
  FROM Connection c
 WHERE c.ProviderId = 'PVD99'
 GROUP BY lokasi_id
HAVING dipakai_berapa_site > 1;
```

**Lulus bila: nol baris.** Kalau ada, hentikan dan bereskan dulu — seluruh uji
berikutnya jadi tidak berarti.

---

## FASE B — Isolasi jalur baca

Semua dilakukan **login sebagai user B**, lalu diulang sebagai user A.

### B1. Enam layar VoC tidak membocorkan data tenant lain

- [ ] Ulasan
- [ ] Fetch Jobs
- [ ] Lokasi
- [ ] Jadwal Crawl
- [ ] Tren Bulanan
- [ ] Paket & Kuota

**Lulus bila:** sebagai user B, tidak satu pun nama cabang Hermina/Eka/Five Coffee
muncul di layar mana pun. Sebagai user A, tidak satu pun cabang Site B muncul.

Pembanding angka:

```sql
SELECT m.SiteId, COUNT(*) AS ulasan
  FROM Message m
  JOIN Connection c ON c.Id = m.ConnectionId AND c.ProviderId = 'PVD99'
 GROUP BY m.SiteId;
```

Angka di layar tiap site harus cocok dengan barisnya sendiri.

### B2. KPI dan dashboard ikut tersaring

Layar Jadwal Crawl punya lima kartu KPI dari endpoint agregat.

- [ ] `Voc/schedulesKpi` sebagai user B menampilkan `cabang_tersedia` = jumlah
      cabang Site B saja, bukan total dua site

**Lulus bila:** `cabang_tersedia` user A + user B ≠ dijumlah dobel; masing-masing
melaporkan miliknya sendiri.

### B3. Worklist API hanya mengembalikan target site pemilik token

Ini jalur yang dipakai Crawler menarik daftar target.

- [ ] `GET /api/VocWorklist` dengan JWT Site A → hanya lokasi Site A
- [ ] JWT Site B → hanya lokasi Site B
- [ ] Tanpa JWT / JWT rusak → ditolak, **bukan** mengembalikan daftar kosong
      dengan status 200

**Lulus bila:** ketiganya sesuai. Butir ketiga penting: kode menjaga
`$siteId <= 0` supaya token tak sah tidak berubah jadi query `SiteId = 0`.

---

## FASE C — Uji negatif (inti pengujian)

Semua tugas di fase ini **sengaja membuat keadaan salah** dan memastikan sistem
menolaknya. Setelah tiap butir, kembalikan nilainya seperti semula.

### C1. Token tenant lain dipasang di koneksi site A

TULIS — pada satu koneksi Site B saja, sementara.

1. Catat `service_token` asli koneksi Site B (simpan di luar dokumen ini)
2. Ganti dengan `<TOKEN_A>` milik company 3
3. Jalankan sinkronisasi ulasan untuk Site B
4. Kembalikan token aslinya

**Lulus bila:** sync **abort** dengan pesan `TENANT MISMATCH`, menyebut
`company_id` yang sebenarnya dan yang diharapkan. **Tidak boleh** ada satu pun
`Message` baru masuk ke Site B.

Bukti:

```sql
SELECT COUNT(*) FROM Message m
  JOIN Connection c ON c.Id = m.ConnectionId
 WHERE c.SiteId = <SITE_B> AND m.CreateDate >= '<waktu mulai uji>';
```

Harus **0**.

> Ini uji paling penting di seluruh dokumen. Kalau ini lolos masuk, artinya
> review milik rumah sakit lain bisa mendarat di tenant yang salah tanpa error.

### C2. `company_id` dikosongkan

TULIS — sementara.

1. Hapus `Options.company_id` dari satu koneksi Site B
2. Jalankan sync
3. Kembalikan

**Lulus bila:** sync abort dengan pesan yang menyebut connection dan site mana
yang kehilangan `company_id` — bukan diam-diam menarik data.

### C3. Scope token kurang

Kalau tim Crawler bisa menyediakan token tanpa scope `reviews:read`:

- [ ] Sync memakai token itu → abort **sebelum** paging dimulai

**Lulus bila:** gagal di awal, bukan 403 di tengah setelah sebagian data masuk.

### C4. Jadwal memilih cabang milik site lain

Tanpa TULIS langsung ke DB — lewat API, meniru penyalahgunaan.

```bash
curl -b <cookie_site_B> -X POST https://dev.onebox.co.id/Voc/scheduleSave \
  -d "name=UAT lintas tenant" \
  -d "cron_expr=0 6 * * *" -d "timezone=Asia/Jakarta" \
  -d "target_review_count=5" -d "lookback_days=7" \
  -d "location_ids[]=676"        # 676 = Hermina Bogor, milik Site A
```

**Lulus bila:** ditolak dengan `"ok":false`, dan **tidak ada** baris `VocSchedule`
baru untuk `<SITE_B>`.

### C5. Membaca jadwal & riwayat milik site lain lewat id

- [ ] `Voc/scheduleRuns?id=<id jadwal Site A>` sebagai user B
- [ ] `Voc/scheduleToggle` dengan id jadwal Site A sebagai user B
- [ ] `Voc/scheduleDelete` dengan id jadwal Site A sebagai user B

**Lulus bila:** ketiganya ditolak atau mengembalikan kosong, dan jadwal Site A
**tidak berubah sedikit pun**. Periksa sesudahnya:

```sql
SELECT Id, SiteId, Name, Enabled, ExpireDate FROM VocSchedule WHERE SiteId = 169;
```

### C6. Site B memiliki dua koneksi dengan tenant berbeda

Ini menguji celah `$base` yang sudah diketahui (lihat Pemahaman §3).

TULIS — sementara.

1. Pada Site B, ubah **satu** koneksi (yang `Id`-nya lebih besar) supaya memakai
   `company_id` dan token milik company 3
2. Jalankan Fetch Jobs untuk cabang milik koneksi yang **kedua** itu
3. Kembalikan

**Yang diharapkan terjadi:** kredensial koneksi ber-`Id` terkecil yang dipakai,
sehingga Crawler menolak dengan `TARGET_NOT_FOUND` atau `TENANT MISMATCH`, dan
jadwal/fetch-nya gagal dengan alasan yang bisa dibaca.

**Lulus bila:** gagal dengan pesan yang menyebut sebab tenant — **bukan** berhasil
menarik data. Kalau ternyata berhasil, itu temuan serius: catat batch id dan
hentikan pengujian.

Catat apa adanya, karena inilah satu-satunya jalur yang belum punya pra-periksa.

---

## FASE D — Isolasi jalur tulis

### D1. Fetch manual per site

- [ ] Fetch dari Site A → batch masuk, ulasan mendarat di Site A
- [ ] Fetch dari Site B → batch masuk, ulasan mendarat di Site B
- [ ] Tidak ada ulasan yang menyeberang

```sql
SELECT m.SiteId,
       COALESCE(JSON_UNQUOTE(JSON_EXTRACT(mc.Meta,'$.onebox_location_id')),'(kosong)') AS lokasi,
       COUNT(*) AS jml
  FROM Message m
  JOIN MessageContent mc ON mc.Id = m.Id
 WHERE m.CreateDate >= '<waktu mulai uji>'
 GROUP BY m.SiteId, lokasi
 ORDER BY m.SiteId, jml DESC;
```

**Lulus bila:** tiap `lokasi` hanya muncul di bawah satu `SiteId`, dan `SiteId`
itu memang pemiliknya.

### D2. Koneksi penampung tidak menyeberang site

Menindaklanjuti temuan 13 Agustus (ulasan Bogor tersimpan di koneksi Depok).

```sql
SELECT m.SiteId AS site_pesan, c.SiteId AS site_koneksi, COUNT(*) AS jml
  FROM Message m
  JOIN Connection c ON c.Id = m.ConnectionId
 WHERE c.ProviderId = 'PVD99'
 GROUP BY m.SiteId, c.SiteId
HAVING site_pesan <> site_koneksi;
```

**Lulus bila: nol baris.** Kalau ada baris, ulasan satu tenant tersimpan di bawah
koneksi tenant lain — hentikan dan catat sebagai temuan P0.

### D3. Scheduler menjalankan dua tenant tanpa saling mengganggu

Prasyarat: `VOC_WORKERS=1` dan `SCHEDULER_REPLICAS >= 1` di stack yang diuji.

- [ ] Satu jadwal di Site A dan satu di Site B, waktunya berdekatan
- [ ] Keduanya berjalan sendiri pada waktunya, tanpa tombol Play
- [ ] Tiap run memakai kredensial tenant-nya sendiri

```sql
SELECT r.SiteId, r.ScheduleId, r.ScheduledFor, r.Status, r.Inserted, r.BatchId
  FROM VocScheduleRun r
 WHERE r.ScheduledFor >= '<waktu mulai uji>'
 ORDER BY r.ScheduledFor;
```

**Lulus bila:** tiap `VocScheduleRun.SiteId` cocok dengan `VocSchedule.SiteId`
induknya, dan `Inserted` masuk ke tenant yang benar.

### D4. Satu tenant bermasalah tidak menjatuhkan tenant lain

- [ ] Buat jadwal Site B menunjuk cabang yang sengaja salah (mis. lokasi tak
      dikenal Crawler)
- [ ] Biarkan gagal
- [ ] Pastikan jadwal Site A pada slot yang sama tetap berjalan normal

**Lulus bila:** jadwal Site B dimatikan dengan alasan konfigurasi, jadwal Site A
tetap `succeeded`. Ini menguji `dispatchDueSchedules()` yang menangkap `Throwable`
per jadwal.

---

## FASE E — Putuskan celah yang ditemukan

### E1. Rekap temuan

Isi tabel ini setelah A–D selesai:

| Uji | Hasil | Temuan | Tingkat |
|---|---|---|---|
| C1 token silang | | | |
| C2 company_id kosong | | | |
| C4 cabang site lain | | | |
| C5 akses lewat id | | | |
| C6 dua tenant satu site | | | |
| D2 koneksi menyeberang | | | |

### E2. Keputusan untuk celah `$base` (jalur enqueue)

Kalau C6 menunjukkan perilakunya memang bergantung Crawler, ada tiga pilihan.
**Ini keputusan senior dev, bukan diputuskan sendiri di sini:**

1. **Pra-periksa tenant sebelum enqueue** — panggil `whoami()` dan adu dengan
   `Options.company_id`, sama seperti jalur sync. Paling aman, menambah satu
   panggilan jaringan per enqueue.
2. **Tolak site yang punya lebih dari satu `company_id`** — pemeriksaan murah,
   tanpa panggilan jaringan, tetapi tidak menangkap token yang salah paste.
3. **Biarkan, andalkan Crawler** — sah kalau Crawler memang selalu menolak. Perlu
   bukti dari C6, bukan asumsi.

### E3. Keputusan untuk `Location` global

- [ ] Apakah `Location` perlu kolom `SiteId`, atau kepemilikan cukup lewat
      `Connection`?
- [ ] Kalau cukup lewat `Connection`, apakah perlu kueri pemantau (seperti A5)
      yang dijalankan berkala?

Catat keputusannya, apa pun itu — supaya tidak dibahas ulang dari nol bulan depan.

---

## Yang TIDAK diuji dokumen ini

Disebut supaya tidak dikira sudah aman:

- **Isolasi di sisi Crawler.** Semua uji di sini melihat dari OneBox. Apakah
  company 3 bisa membaca data company B lewat API Crawler langsung adalah
  pengujian milik tim Crawler.
- **Kebocoran lewat pencarian global / Elasticsearch**, kalau ada indeks yang
  tidak ber-`SiteId`.
- **Laporan & ekspor** di luar modul VoC.
- **Beban dua tenant bersamaan.** Ini uji kebenaran, bukan uji performa.
