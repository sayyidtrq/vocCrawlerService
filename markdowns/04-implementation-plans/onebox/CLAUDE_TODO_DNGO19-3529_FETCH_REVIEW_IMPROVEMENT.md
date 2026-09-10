# Claude Todo — DNGO19-3529 Fetch Review Improvement (Lajur OneBox)

Status: **kode selesai & ter-deploy di dev; sebagian sudah dibuktikan berjalan**
Tanggal: 2026-09-01 (diperbarui sesudah verifikasi di dev)
Branch: `feature/DNGO19-3529_Fetch-Review-Improvement` (repo `onecloud`, dari `feature/voc`) — PR terbuka ke `feature/voc`, 6 commit
Pasangan: `08-agent-prompts-and-handoffs/CODEX_TODO_REVIEW_FETCH_LOGIC_REFACTOR.md`
Dasar: `03-architecture/integration/VOC_FETCH_LOGIC_PEMAHAMAN.md` + `VOC_TANGGAL_SENDIRI_DAN_BATCHING.md`

---

## RINGKASAN PROGRES

| # | Pekerjaan | Kode | Terbukti jalan di dev |
| --- | --- | --- | --- |
| CL-1 | Simpan rating Google di `VocRatingLog` | ✅ | ⏸ kolom sudah ada, **belum ada baris berisi angkanya** |
| CL-1b | Konsumsi `rating_snapshot` dari Crawler | ✅ | ⏸ belum terpancing (lihat temuan di bawah) |
| CL-1c | Tampilkan rating Google + selisih cakupan di grafik tren | ✅ | ⏸ butuh ≥2 titik data dulu |
| CL-2 | Watermark jadwal (rentang menyempit sendiri) | ✅ | ✅ **terbukti** |
| CL-3 | Cegah manual bentrok dengan jadwal | ✅ | ⏸ belum terpancing |
| CL-4 | Alasan berhenti dalam bahasa manusia | ✅ | ✅ **terbukti tampil di layar** |
| CL-4b | Batch campuran lewat histogram `stop_reasons` | ✅ | ⏸ belum ada batch campuran di dev |
| CL-5a | Kirim `scan_limit` + `crawl_mode` | ✅ | ✅ **terbukti** |
| CL-5a2 | Negosiasi kontrak (fallback 422) | ✅ | — tidak terpancing; Crawler dev sudah versi baru |
| CL-5b | Rencana batch first-run | ❌ | butuh `place_review_count` per cabang |
| CL-6 | Dua sumbu waktu di layar | ❌ | menunggu keputusan produk |
| — | **Ubah label "Jumlah ulasan" di UI** | ❌ | **belum dikerjakan sama sekali** — lihat catatan di bawah |

### Bukti verifikasi di dev (1 Sep 2026)

Diambil langsung dari API integrasi Crawler dan dari layar OneBox dev.

**CL-5a — `scan_limit` + `crawl_mode` benar-benar terkirim.** Batch `2b4ecae9` (09:00, slot `schedule`):

```
crawl_mode : custom_range
scan_limit : 500          <- persis rumus: max(500, 10 x target(10))
```

Batch jam 07:00 masih `scan_limit: 50`. Perbedaan dua jam itu memperlihatkan kapan kode ini mulai dipakai — bukan sekadar ada di repo.

**CL-2 — watermark benar-benar menyempitkan rentang.** Job yang sama membawa:

```
date_from : 2026-08-26T08:38:09+00:00
```

Bukan kelipatan hari yang bulat dari `LookbackDays`, melainkan timestamp ganjil ≈ ulasan terbaru dikurangi margin 1 hari. Itu tanda watermark, bukan lookback tetap.

**CL-4 — alasan berhenti tampil di Riwayat Fetch dev.** Baris nyata:

```
1 Sep 16:00 · Hermina Bogor    · Selesai — jumlah yang diminta sudah terpenuhi.        · 10/10
1 Sep 13:39 · RS Anak Negeri   · Selesai — sudah sampai ulasan yang lebih tua dari
                                  rentang tanggal.                                     · 0/1, disisir 1
```

Endpoint `crawlHistory` juga mengembalikan `alasan_berhenti` dan `berhenti_belum_tuntas` dengan benar. **Tidak ada console error** dari perubahan ini; yang muncul di layar itu (Google Maps API dobel-muat, DataTables 404) sudah ada sebelumnya.

**Snapshot P5 dari Crawler sudah berisi data nyata:**

```
rating_snapshot : {place_rating: 4.6, place_review_count: 46, snapshot_at: 2026-09-01T09:00:09Z}
```

### ⚠️ Temuan: snapshot rating hanya tercatat pada import MANUAL

`VocRatingLog` di dev hanya berisi **2 baris, keduanya 2026-08-31 04:29:50** — padahal jadwal berjalan 07:00 dan 09:00 pada 1 September.

Sebabnya: `recordRatingSnapshot()` hanya dipanggil dari `VocController::crawlImportAction` — yaitu tombol tarik ulasan manual. `VocTask.php` (scheduler) tidak memuat satu pun panggilan import; ia hanya menaruh pekerjaan ke antrean Crawler.

**Ini bukan regresi dari DNGO19-3529** — perilakunya sudah begitu sejak `VocRatingLog` dibuat; pekerjaan ini hanya menambahkan angka Google ke fungsi yang sudah ada.

> **feedback:** *THIS RULE IS NOT APPLICABLE — justru main function untuk
> snapshot adalah pada scheduler, dan untuk divisualisasikan pada kategori tren
> di chart.*

**✅ SUDAH DIKERJAKAN — commit `972a97304a`.** Feedback di atas benar, dan
menaruhnya sebagai "di luar lingkup" adalah keputusan yang salah: kalau
snapshot hanya lahir dari tombol manual, grafik tren tidak akan pernah punya
titik yang teratur, dan seluruh fitur rating Google jadi tidak ada gunanya.

Yang diubah:

- **`Service\VocRatingSnapshot`** — pencatatnya dikeluarkan dari controller menjadi satu penulis untuk semua pemicu.
- Dipanggil dari **`VocProvider::receive()`**, satu-satunya titik yang dilewati **kedua** jalur: manual (`crawlImportAction`) dan terjadwal (`Messaging::receiveConnection` ← worker). Tidak ada jalur yang perlu diingat dua kali.
- **Diredam 30 menit per koneksi, hanya untuk jalur otomatis.** Putaran worker yang rapat kalau tidak diredam akan melahirkan deretan titik kembar pada menit yang sama — itu tidak menambah informasi, hanya menyulitkan melihat perubahan nyata. Penarikan manual **tidak** diredam: yang menekan tombol berhak melihat hasilnya seketika.
- **`Library\VocReviewSql`** — definisi potongan SQL review dipindah ke satu tempat supaya jalur terjadwal memakai rumus yang sama persis dengan layar Ulasan. Komentar lama di `ratingSnapshotMetrics` sudah memperingatkan bahaya dua salinan; menyalinnya ke worker justru akan mewujudkan peringatan itu.
- `insertRatingLog` di controller **dihapus** setelah menjadi mati — penulis kedua yang bisa menyimpang justru hal yang sedang dihilangkan.

Diverifikasi: keempat potongan SQL hasil pemindahan **byte-identik** dengan
aslinya, jadi perilaku layar tidak berubah.

**Cara membuktikan di dev:** biarkan satu siklus jadwal berjalan (atau jalankan
worker receive), lalu:

```sql
SELECT Id, RecordedAt, Source, ConnectionId, AvgRating, GoogleRating
FROM VocRatingLog ORDER BY Id DESC LIMIT 5;
```

Harapan: baris baru dengan `Source = 'sync'` — itu penanda bahwa titiknya lahir
dari jalur terjadwal, bukan dari tombol manual (`Source = 'import'`).

### Catatan: label "Jumlah ulasan" masih ada di UI

Benar, dan itu **belum pernah dikerjakan** — bukan terlewat. Jawaban Sayyid #1 berbunyi *"boleh aja masih ada jumlah ulasan/batas pengambilan batch"*, jadi labelnya sengaja tidak disentuh. Kalau nanti diputuskan diganti menjadi **"Batas pengambilan per batch"** beserta keterangan bahwa itu batas biaya (bukan janji hasil), pekerjaannya kecil dan berdiri sendiri.

### Cara menguji sisanya secara manual

1. **Rating Google** — Fetch Jobs → satu cabang → target 10 → Mulai → tunggu selesai → tekan tarik/import.
   Periksa: `SELECT Id, RecordedAt, AvgRating, GoogleRating, GoogleReviewCount FROM VocRatingLog ORDER BY Id DESC LIMIT 3;`
   Harapan: baris baru dengan `GoogleRating` terisi.
2. **Grafik tren** — sesudah nomor 1 menghasilkan ≥2 titik: layar Ulasan → tab Tren → garis merah putus-putus "Rating Google" + tooltip "Belum tertarik: N ulasan".
3. **Guard manual vs jadwal** — saat jadwal sedang berjalan, tekan fetch manual untuk cabang yang sama. Harapan: ditolak, menyebut nama jadwal dan jam mulainya.
4. **Alasan berhenti versi kuning** — fetch dengan rentang tanggal jauh ke belakang dan target besar, sampai berhenti karena batas. Harapan: kalimat kuning dengan ⚠, bukan abu-abu.

### Migrasi

`1786190000000000_1_123_0` (kolom `GoogleRating` + `GoogleReviewCount`) sudah diterapkan di dev pada 1 Sep 2026 lewat `ALTER TABLE` manual di PMA. Migrasinya idempoten, jadi `migrate.php` tetap aman dijalankan menyusul — ia akan melaporkan "kolom sudah ada, dilewati".

Migrasi `1786180000000000_1_123_0` (VocWilayah, DNGO19-3513) **masih tertunda** di dev — di luar lingkup 3529, tapi masih relevan karena satu kelas masalah yang sama.

## Pembagian lajur: Claude vs Codex

Codex sudah punya scope sendiri (P0–P7) yang **seluruhnya di sisi Crawler System dan kontrak integrasi**. Supaya tidak ada dua orang menyentuh berkas yang sama, pembagiannya dikunci begini:

| Area | Pemilik | Catatan |
| --- | --- | --- |
| Endpoint `crawl-jobs`, skema payload, `crawl_mode` | **Codex** (P1) | Claude hanya *mengonsumsi* |
| Algoritma stop condition + counters + stop reason | **Codex** (P3, P6) | Claude *menampilkan* hasilnya |
| Cursor/state di tabel `locations` Crawler | **Codex** (P2) | |
| Lock & idempotency di Crawler | **Codex** (P4) | Claude tambah pencegahan di UI |
| Pengambilan rating Google dari halaman Maps | **Codex** (P5) | Claude yang **menyimpan & menampilkan** |
| **Penyimpanan & visualisasi rating snapshot** | **Claude** | Jawaban Sayyid #4: "OneBox SIMPAN" |
| **Scheduler OneBox & rentang efektif** | **Claude** | `VocCrawlQueue`, `VocTask` |
| **Seluruh UI OneBox + validasi + alert** | **Claude** | Jawaban Sayyid #5 dan catatan penutup |
| **Perencanaan batch (berapa batch, ukurannya)** | **Claude** | OneBox = control plane, sesuai keputusan arsitektur |

**Berkas yang TIDAK boleh disentuh Claude** (milik Codex): apa pun di repo `hermina_crawler` — `app/`, `apps/`, `tests/`. Repo itu juga sedang punya perubahan yang belum di-commit (fallback Place ID, task #66), jadi menyentuhnya berisiko menabrak kerja orang lain.

> ✅ **SELESAI — celah T1 sudah ditutup Codex.** Temuan T1 (hash dedupe memakai `review_relative_time` yang berubah seiring waktu) semula tidak ada di scope Codex P0–P7. Setelah diangkat, dikerjakan sebagai P0.5 pada commit Crawler `0ce172e`: `generate_selenium_review_hash()` tidak lagi memakai teks relatif, dan insert review ikut di-dedupe lewat `external_review_id` — termasuk jalur kompetitor. Tes Crawler: 115 lulus.
>
> Sisi OneBox **tidak perlu diubah** untuk ini: `VocProvider::sudahPernahMasuk()` sudah lebih dulu mencocokkan `external_review_id`, dan docblock-nya sudah menyebut alasannya — *"review_hash tidak bisa dipakai karena Crawler menerbitkannya ulang untuk ulasan yang sama."* Jadi penjaganya kini rangkap dua: di Crawler dan di OneBox.

---

## Jawaban Sayyid yang menjadi dasar to-do ini

Dikutip dari `VOC_FETCH_LOGIC_PEMAHAMAN.md` bagian 8:

1. **Batas pengambilan boleh tetap ada** — tapi hanya sah kalau ulasan diambil berurutan dari `last_fetched_at` ke depan, sehingga tidak ada ulasan yang bolong di tengah.
2. **First run wajib**, dan sebelum jalan **cek dulu total ulasannya berapa**; kalau di atas ambang (±350) pecah jadi beberapa batch.
3. Batch berbasis anggaran waktu — **disetujui**.
4. **OneBox yang menyimpan** rating snapshot — dibutuhkan untuk tren dan visualisasi dashboard.
5. Manual **tidak boleh** memotong antrean, dan **harus dicegah lewat validasi UI**.
6. Catatan penutup: UI OneBox harus mencegah keadaan yang tidak diinginkan sejak awal, tidak membuat orang bekerja dua kali, dan **alert/pesan sangat dibutuhkan**.

### Jawaban atas dua pertanyaan balik Sayyid

**"Cek jumlah ulasan dulu — ini bisa nggak ya?"**
**Bisa.** Angka total ulasan ada di header halaman Google Maps, di tempat yang sama dengan rating agregat yang akan diambil Codex di P5. Jadi tidak butuh mekanisme baru — begitu P5 jalan, `place_review_count` ikut terbawa dan OneBox tinggal memakainya untuk merencanakan batch. Sebelum P5 selesai, OneBox memakai perkiraan dari jumlah review yang sudah dipunyai (pasti lebih kecil dari sebenarnya, jadi aman: paling banter merencanakan batch lebih sedikit dari yang perlu, lalu menambah saat data sebenarnya masuk).

**"Mending isi penuh 350 atau dibagi rata?"**
Secara matematis: **batch kecil dulu, batch besar belakangan** — bukan dibagi rata, dan bukan isi penuh di depan.

Alasannya, tiap batch harus menggulir ulang seluruh jalan batch sebelumnya (Google Maps tidak punya cursor). Batch yang berada di urutan awal ikut terlewati berkali-kali, jadi biayanya berlipat sesuai berapa batch yang datang sesudahnya. Untuk N=1000 dengan 2 batch:

| Susunan | Total kartu dilewati |
| --- | --- |
| 300 lalu 700 | 300×2 + 700×1 = **1.300** ← paling murah |
| 500 lalu 500 | 500×2 + 500×1 = 1.500 |
| 700 lalu 300 | 700×2 + 300×1 = 1.700 |

Tapi yang jauh lebih menentukan daripada susunannya adalah **jumlah batch-nya** — makin sedikit batch, makin murah. Jadi aturan praktisnya: **pakai batch sebesar yang muat dalam anggaran waktu, dan kalau harus memecah, taruh yang kecil di depan.** Dan begitu fast-forward (Codex) terpasang, seluruh pemborosan ini mengecil drastis sehingga susunannya tidak lagi kritis.

---

## Daftar tugas

### CL-1 — Simpan rating agregat Google di `VocRatingLog` ✅

Menjawab keputusan #4. Dibuat **forward-compatible**: kolomnya ada dan diisi begitu Codex P5 mengirim datanya; sebelum itu tetap `NULL` tanpa merusak apa pun.

- [x] Migrasi `VocRatingLogGoogle` — tambah `GoogleRating decimal(4,2) NULL` dan `GoogleReviewCount int NULL`
- [x] Pakai pola migrasi VoC yang berlaku: `tableExists()` guard, dan **tidak gagal** kalau tabel induknya belum ada
- [x] `insertRatingLog()` menulis kedua kolom itu, dengan jumlah kolom/placeholder diverifikasi untuk kedua cabang (kolom ada / belum ada)
- [x] `recordRatingSnapshot()` menerima angka Google lewat parameter
- [x] Guard `vocRatingLogGoogleSiap()` — **terpisah** dari `vocRatingLogSiap()`, karena tabel dan kolomnya datang dari migrasi berbeda dan di dev betul-betul pernah ada keadaan "tabel ada, kolom belum"
- [x] Angka Google hanya ditulis pada baris LOKASI, tidak pada baris gabungan site — Google tidak mengenal "gabungan cabang kita"
- [x] **Pengisinya sudah tersambung** (Codex P5 selesai). `rating_snapshot` hanya ikut pada endpoint DETAIL satu batch — daftar batch diserialisasi tanpa job — jadi `crawlBatch()` dipanggil saat import.
- [x] Dicocokkan ke `onebox_location_id` cabangnya, **tidak pernah menebak**. Satu batch bisa memuat banyak cabang; mengambil job pertama begitu saja akan menempelkan rating cabang lain — angka yang terlihat masuk akal, tidak memicu galat apa pun, dan salah.
- [x] Hanya pada panggilan pertama; `resume` tidak menarik ulang jawaban yang sama
- [x] Kredensial memakai koneksi cabang itu sendiri lebih dulu (`vocCredentialTemplate($siteId, $conn)`)
- [x] **Tampil di grafik tren**: garis merah putus-putus "Rating Google" berdampingan dengan rating sendiri, plus tooltip yang menyebut `coverage_gap` — berapa ulasan yang Google punya tapi belum kita tarik. Selisih itulah nilai sesungguhnya dari menyimpan dua angka.
- [x] Kolom Google hanya disebut di `SELECT` bila migrasinya sudah jalan; kalau belum, grafik tetap hidup tanpa angka Google

### CL-2 — Watermark milik OneBox untuk scheduler ✅

Menjawab keputusan #1: batas pengambilan baru sah kalau pengambilannya berurutan dari watermark. **Tidak menunggu Codex** — OneBox sudah tahu ulasan terbaru yang dipunyainya per koneksi, jadi watermark bisa dihitung sendiri.

- [x] Fungsi baru: ulasan terbaru per koneksi dari data OneBox sendiri
- [x] `VocCrawlQueue::dateRangeForSchedule()` memakai watermark sebagai batas bawah untuk mode delta
- [x] `LookbackDays` **tetap dipertahankan** sebagai jaring pengaman kalau watermark kosong
- [x] Watermark **tidak dipakai** kalau jadwalnya memang memakai rentang tanggal eksplisit (itu custom range, bukan delta)

### CL-3 — Cegah tumpang tindih manual vs jadwal di UI ✅

Menjawab keputusan #5 dan catatan penutup: dicegah, dan **diberi tahu alasannya** — bukan ditolak diam-diam.

- [x] Endpoint fetch manual memeriksa apakah ada run terjadwal yang masih berjalan untuk cabang yang sama
- [x] Kalau ada: tolak dengan pesan yang menyebut jadwalnya dan perkiraan selesainya
- [x] Pesan memakai bahasa manusia, bukan kode status

### CL-4 — Terjemahkan alasan berhenti ke bahasa manusia ✅

Menjawab catatan penutup. Data `stopped_reason` **sudah dikirim Crawler hari ini** dan tidak pernah ditampilkan — jadi ini murni pekerjaan OneBox, tanpa menunggu siapa pun.

- [x] Peta `stopped_reason` → kalimat yang bisa dibaca orang
- [x] Termasuk nilai yang akan datang dari Codex P6, supaya tidak perlu diubah lagi nanti
- [x] Baca **dua nama field**: `stop_reason` (nama publik hasil normalisasi Codex) dan `stopped_reason` (metadata mentah). Mencari satu saja membuat kolomnya kosong di salah satu versi Crawler tanpa ada yang tahu kenapa.
- [x] Bedakan **"sudah selesai semua"** dari **"berhenti karena batas"** — ini yang menghentikan tuduhan "fetch-nya gagal" padahal crawler bekerja benar
- [x] **Tampil di layar Riwayat Fetch**, bukan cuma ada di JSON: kuning + ⚠ kalau masih ada sisa, abu kalau memang sudah habis. Tidak memakai merah — merah sudah dipakai alasan gagal, dan menyamakannya membuat "sudah selesai" terbaca sebagai kerusakan.

### CL-5a — Kirim `crawl_mode` + `scan_limit` ✅

Dibuka oleh kontrak baru Codex. **Inilah yang membuat review lama bisa dijangkau**: `scan_limit` membatasi yang DISISIR (sampai 5000), terpisah dari target yang membatasi yang DIKUMPULKAN (tetap 300).

- [x] `scan_limit` = 10× target, lantai 500, plafon 5000 (batas kontrak)
- [x] `crawl_mode`: `custom_range` kalau ada rentang tanggal, selain itu `regular_delta`
- [x] Ditentukan di `VocCrawlQueue::enqueue()` — satu tempat, jadi manual/jadwal/jalankan-sekarang otomatis konsisten
- [x] **Negosiasi kontrak di klien**: skema Crawler memakai `extra="forbid"`, jadi OneBox yang dideploy lebih dulu akan mematikan SELURUH penarikan dengan 422. Ditangani: kirim bentuk baru, kalau ditolak 422 ulangi sekali dengan bentuk lama. Idempotency-Key boleh dipakai ulang karena permintaan pertama tertolak di validasi — tidak ada batch yang terbentuk.
- [x] Jawaban "Crawler masih lama" **tidak** di-cache: proses Swoole berumur panjang, dan mengingatnya berarti OneBox tetap pakai bentuk lama sampai container di-restart padahal Crawler sudah diperbarui.
- [ ] `initial_backfill` belum pernah dikirim — lihat CL-5b.

### CL-5b — Rencana batch untuk first run ⏸️

Menjawab keputusan #2. **Masih menunggu Codex P5**, karena butuh `place_review_count` untuk tahu satu cabang punya berapa ulasan sebelum memutuskan berapa batch. Rancangannya sudah ditetapkan di atas (batch kecil dulu, besar belakangan; ambang ±350).

Catatan bentuk kontrak: satu batch memakai SATU `crawl_mode` untuk semua cabang di dalamnya. Jadi "sebagian backfill, sebagian delta" baru mungkin setelah batch dipecah per cabang.

### CL-6 — Bedakan dua sumbu waktu di layar ⏸️

Dari `VOC_TANGGAL_SENDIRI_DAN_BATCHING.md`. **Menunggu keputusan produk** ("apakah kita menerima dua sumbu waktu?") — belum dijawab, dan mengubah banyak layar sekaligus tanpa keputusan itu berisiko.

---

## Batas lingkup

- **Tidak** menyentuh repo `hermina_crawler` sama sekali
- **Tidak** mengubah kontrak `crawl-jobs` — itu Codex P1; OneBox hanya mengonsumsi
- **Tidak** merombak cursor tarik OneBox←Crawler (sudah matang)
- **Tidak** mengubah ticket routing (itu DNGO19-3515, branch terpisah)
