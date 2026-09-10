# VoC Fetch Logic — Pemahaman Top-Down (Grounded di Kode)

Status: hasil audit kode aktual, siap jadi dasar keputusan
Tanggal: 2026-09-01
Sumber kebutuhan: `VoC System Document Design.md` (Fix & Improve: Logika Pengambilan Review)
Repo yang diaudit: `hermina_crawler` (branch `codex/server-deploy-scripts`) + `onecloud` (branch `feature/voc`)

## Posisi dokumen ini

Sudah ada dua draft dari sumber kebutuhan yang sama:

- `00-start-here/VOC_FETCH_LOGIC_TOP_DOWN.md` — model konseptual (window-first, 3 mode, boundary)
- `04-implementation-plans/crawler-system/PLAN_REVIEW_FETCH_LOGIC_REFACTOR.md` — rencana, yang P0-nya masih berbunyi "audit state saat ini"

Dokumen INI adalah P0 itu, dikerjakan. Isinya bukan konsep ulang melainkan **apa yang benar-benar ada di kode hari ini**, lengkap dengan lokasi barisnya, plus koreksi atas beberapa asumsi kedua draft di atas yang ternyata tidak sesuai kenyataan. Konsep 3 mode di draft pertama tetap dipakai dan tidak diulang di sini.

---

## 1. Ringkasan eksekutif

Lima temuan yang mengubah cara kita harus membaca masalah ini:

| # | Temuan | Dampak | Biaya perbaikan |
| --- | --- | --- | --- |
| T1 | Hash dedupe review Selenium memakai `review_relative_time` ("2 minggu lalu") yang **berubah seiring waktu** | Review yang sama, di-crawl ulang minggu depan, masuk sebagai **baris baru** — duplikat nyata di DB Crawler, lalu menular ke OneBox | **Sangat murah**, identitas stabilnya sudah ditangkap tapi tidak dipakai |
| T2 | `target_review_count` adalah **kondisi berhenti**, rentang tanggal hanya penyaring | "50 review dari 1 Agustus" berarti "sisir 50 kartu lalu buang yang di luar rentang" — bisa pulang dengan 3 | Sedang |
| T3 | Tidak ada watermark per cabang sama sekali (`last_fetched_at` dkk) | Tiap run mengulang tanah yang sama dari paling atas; review lama makin mustahil dijangkau | Sedang |
| T4 | `review_time` adalah **hasil taksiran** dari teks relatif, bukan tanggal asli dari Google | Seluruh desain berbasis rentang tanggal berdiri di atas angka yang kasar dan menggeser | Perlu keputusan, bukan sekadar coding |
| T5 | Rating agregat resmi Google (bintang + total ulasan) **tidak pernah diambil** | "Rating di OneBox sesuai Google" secara struktural mustahil hari ini | Kecil-sedang, tapi wajib |

Kalimat yang paling penting untuk dibawa ke diskusi: **masalah utamanya bukan "count vs window"** — itu penting tapi nomor dua. Masalah nomor satu adalah **identitas review yang tidak stabil (T1)**, dan itu perbaikan paling murah dengan dampak paling besar. Kedua draft sebelumnya melewatkan ini karena tidak membaca kode.

---

## 2. Peta jalur, dari atas ke bawah

Jalur ini yang benar-benar berjalan hari ini, bukan yang seharusnya:

```
[1] User isi form Fetch Review di OneBox
        ↓  jumlah ulasan, rentang tanggal / preset hari, sort
[2] VocController::crawlDateRange() + crawlSortBy()        VocController.php:8103-8161
        ↓  normalisasi tanggal ke UTC, paksa sort=newest kalau ada rentang
[3] VocCrawlQueue::enqueue()                                app/services/VocCrawlQueue.php
        ↓  POST /api/integration/v1/crawl-jobs  (+ idempotency key)
[4] Crawler terima batch → pecah jadi CrawlJob per target   app/db/models.py:199-281
        ↓  worker klaim job pakai lease
[5] SeleniumFetchService::fetch_location()                  selenium_fetch_service.py:90
        ↓  limit=target, keep_check=rentang, sort_by
[6] SeleniumGoogleMapsReviewClient.fetch_reviews()          selenium_google_maps_client.py:43
        ↓  scroll Google Maps, berhenti saat target/limit/waktu/keluar-rentang
[7] normalize_review() → review_hash → insert               fetch_service.py:109-162
        ↓  unique constraint di reviews.review_hash
[8] OneBox tarik delta: VocProvider::receive()              app/services/Provider/VocProvider.php
        ↓  keyset cursor di sync_updated_at, checkpoint di Connection.Options
[9] OneBox simpan Message + labeling native
        ↓
[10] recordRatingSnapshot() → VocRatingLog                  VocController.php:5048, 5129
```

Titik yang rusak: **[7]** (identitas), **[5]/[6]** (kapan berhenti), **[4]** (tidak ada state antar-run), **[10]** (mengukur diri sendiri, bukan Google).
Titik yang sudah sehat: **[8]** — jangan disentuh, lihat bagian 5.

---

## 3. Jawaban langsung atas pertanyaan di dokumen kebutuhan

Dokumen sumber menitipkan beberapa pertanyaan eksplisit. Ini jawabannya berdasarkan kode.

### "Bisa jadi review dari 1 Agustus–sekarang tidak berjumlah 50 — kalau implementasi sekarang teknis seperti ini gimana?"

Yang terjadi: crawler **tidak pernah mencari sampai dapat 50 yang cocok**. Ia menyisir sampai `limit` kartu terkumpul, lalu tiap kartu diuji rentang tanggalnya.

- `selenium_fetch_service.py:174-181` — `limit=requested_target` diteruskan apa adanya sebagai batas atas jumlah kartu
- `selenium_fetch_service.py:212-214` — kartu di luar rentang dihitung `total_skipped_out_of_range`, lalu dibuang
- Jadi kalau dari 50 kartu terbaru hanya 12 yang jatuh di dalam rentang, hasilnya **12**, bukan 50. Tidak ada kelanjutan untuk menutup kekurangannya.

Ada kabar baik yang perlu dicatat, karena dua draft sebelumnya menganggap ini belum ada: **penghentian dini berbasis tanggal SUDAH ada**. `selenium_fetch_service.py:150-172` mengembalikan `"stop"` begitu menemukan review yang lebih tua dari `date_from`, dan `sort_by` dipaksa ke `newest` kalau ada rentang (`:111-113`). Jadi permintaan ke masa lampau tidak lagi menghabiskan jatah di ulasan terbaru. Yang **belum** ada adalah kebalikannya: menambah jangkauan ketika rentangnya justru berisi lebih banyak dari `limit`.

Catatan penting: ini hanya berlaku di `SeleniumFetchService`. Jalur lama `FetchService.fetch_location()` masih memfilter tanggal murni di akhir tanpa mengirim apa pun ke scraper (`fetch_service.py:82-89` cuma mengirim `limit`; filter di `:224`). Perlu dipastikan tidak ada pemanggil produksi yang masih lewat sana.

### "Kalau sudah pernah ada scheduler/manual di rentang itu, akan banyak duplicate"

Benar, dan penyebabnya ada dua lapis yang harus dibedakan:

**Lapis 1 — pemborosan (wajar, tapi mahal).** Karena tidak ada watermark, tiap run mulai lagi dari kartu paling atas. Review yang sudah punya berulang kali di-scroll, di-parse, dan diuji. Ini bukan data rusak, ini biaya.

**Lapis 2 — duplikat nyata (bug, T1).** Lihat bagian 4.1. Ini yang membuat baris kembar benar-benar muncul, bukan cuma terhitung sebagai `total_duplicate`.

### "Kalau Depok punya 1000 review dan yang baru 250, 750 sisanya lebih sulit diambil bukan?"

Benar, dan lebih parah dari dugaan. Karena `target_review_count` dibatasi kontrak di **maksimal 300** (`integration_crawl_schemas.py:20`, `le=300`) dan divalidasi ulang di `selenium_fetch_service.py:397` (`min(selenium_max_target_reviews, 300)`), satu job **tidak akan pernah** bisa menjangkau review ke-301 dan seterusnya — berapa kali pun diulang, karena selalu mulai dari atas. 750 review lama itu hari ini **tidak terjangkau sama sekali** lewat jalur normal, bukan sekadar "lebih sulit".

Inilah yang membuat mode backfill berbatch (300–500) di draft pertama bukan sekadar optimasi, melainkan **satu-satunya jalan** ke data historis.

### "Rating di Google sesuai dengan yang di OneBox"

Hari ini tidak mungkin, karena OneBox mengukur dirinya sendiri:

- `VocController.php:5091-5127` `ratingSnapshotMetrics()` menghitung `AVG()` dari **baris review yang OneBox punya** (Message/MessageContent), bukan dari Google
- Crawler juga tidak pernah mengambil angka agregat Google: `RATING_SELECTORS` di `google_maps_selectors.py:31` hanya untuk rating **per kartu ulasan**; tidak ada selector untuk header tempat (bintang keseluruhan + jumlah total ulasan). Pencarian `place_rating|total_review_count|overall_rating|aggregate` di seluruh `app/` dan `apps/` **nihil**.

Selama kita hanya memegang sebagian ulasan, rata-rata kita **pasti** berbeda dari Google — dan bias-nya sistematis (kita cenderung memegang yang terbaru). Menambah kolom snapshot rating Google adalah syarat, bukan pelengkap.

### "Algoritma paling optimal ditaruh di OneBox atau Crawler, atau hybrid?"

Berdasarkan pembagian yang sudah berjalan, jawabannya **hybrid, dan pembagiannya sudah hampir benar** — tinggal dipertegas:

| Keputusan | Tempat | Alasan berbasis kode |
| --- | --- | --- |
| Kapan crawl, cabang mana, mode apa | **OneBox** | `VocSchedule` + `VocTask::dispatchOne()` sudah jadi control plane; jadwal, izin, dan kuota semuanya di sini |
| Rentang efektif satu run (dari watermark) | **OneBox** | OneBox yang tahu riwayat bisnisnya; Crawler tidak boleh punya kebijakan sendiri yang diam-diam berbeda |
| Kapan berhenti menggulir | **Crawler** | Hanya Crawler yang melihat kartu berikutnya; keputusan ini mustahil dari jauh |
| Identitas & dedupe review | **Crawler** | Di sinilah `review_hash` dan unique constraint hidup — satu penjaga, bukan dua |
| Pemecahan batch backfill | **Crawler** melapor, **OneBox** memutuskan lanjut | Crawler tahu di mana ia berhenti; OneBox tahu apakah masih boleh lanjut (kuota, jadwal) |
| Snapshot rating Google | **Crawler** ambil, **OneBox** simpan riwayat | Crawler yang membuka halamannya; `VocRatingLog` sudah punya bentuk yang pas |

Prinsipnya: **Crawler melaporkan fakta ("saya berhenti di sini, karena ini"), OneBox memutuskan kebijakan ("kalau begitu lanjutkan / cukup")**. Jangan taruh kebijakan di Crawler — itu akan melahirkan dua sumber kebenaran yang menyimpang perlahan, persis masalah yang sudah kita alami dengan `sort_by` dipaksa di dua tempat.

---

## 4. Temuan berbukti, diurutkan menurut dampak

### 4.1 T1 — Identitas review tidak stabil (akar duplikat)

Ini temuan paling penting di dokumen ini.

`app/utils/hashing.py:19-31`:

```python
def generate_selenium_review_hash(review: dict) -> str:
    hash_input = "|".join([
        str(review.get("source") or ""),
        str(review.get("location_id") or ""),
        str(review.get("reviewer_name") or ""),
        str(review.get("rating") or ""),
        str(review.get("review_text") or ""),
        str(review.get("review_relative_time") or ""),   # ← "2 minggu lalu"
        str(review.get("reviewer_profile_url") or ""),
    ])
```

`review_relative_time` adalah teks mentah dari Google: "2 minggu lalu", "sebulan lalu", "setahun lalu". **Teks itu berubah seiring waktu untuk review yang sama.** Konsekuensinya berantai:

1. Minggu ini review X ter-hash sebagai `H1` → tersimpan
2. Minggu depan teksnya jadi "3 minggu lalu" → hash jadi `H2`
3. `reviews.review_hash` unique (`models.py:403`) tidak melihat tabrakan → **baris kedua masuk**
4. `sync_updated_at` baris baru itu maju → OneBox menariknya sebagai review baru
5. OneBox dedupe juga pakai `review_hash` (`VocProvider.php:178-211`) → ikut lolos → **baris kembar di layar Ulasan**

Ini menjelaskan tiket-tiket lama yang selama ini diperlakukan sebagai insiden terpisah: baris kembar di layar Ulasan, dan 43 baris kembar yang masih menunggu keputusan pembersihan. Keduanya kemungkinan besar gejala dari satu sebab ini.

**Yang membuat perbaikannya murah:** identitas stabil dari Google **sudah ditangkap dan sudah punya kolomnya**, hanya tidak dipakai di hash.

- `selenium_google_maps_client.py` `_extract_review()` membaca `card.get_attribute("data-review-id")` dan mengirimnya sebagai `external_review_id`
- `models.py:384` — kolom `external_review_id` sudah ada

Jadi perbaikannya: jadikan `external_review_id` sebagai sumber identitas utama, dan **buang `review_relative_time` dari hash**.

Dua hal yang wajib diperhatikan saat mengerjakannya:

- `data-review-id` bisa `None` pada sebagian kartu. Perlu fallback yang tetap **tidak mengandung apa pun yang berubah seiring waktu** — misalnya `reviewer_profile_url + review_text` (keduanya stabil).
- Mengubah rumus hash membuat **seluruh baris lama tidak cocok lagi** dengan baris baru. Satu crawl berikutnya akan menghasilkan satu duplikat terakhir untuk tiap review yang pernah ada. Karena itu perubahan hash **harus disertai migrasi backfill** yang menghitung ulang hash baris lama, bukan dilepas sendirian. Ini bagian yang paling gampang terlewat.

### 4.2 T2 — Count adalah kondisi berhenti, window cuma penyaring

Sudah dijelaskan di bagian 3. Yang perlu ditambahkan: `validate_target()` (`selenium_fetch_service.py:392-406`) **menolak** target di luar 1–300 dengan melempar `ValueError`. Jadi "jumlah ulasan" bukan cuma menyesatkan secara makna, ia juga plafon keras yang tidak bisa dilewati satu job.

Arah perbaikan (sejalan dengan draft pertama): jadikan count sebagai **batas biaya per batch**, bukan janji hasil. Yang menentukan selesai atau belum adalah **window + watermark**, dan kekurangan ditutup oleh batch berikutnya.

### 4.3 T3 — Tidak ada watermark per cabang

Dicari di kedua repo, hasilnya nihil:

- Crawler: `locations` (`models.py:284-352`) tidak punya `last_fetched_at`, `last_seen_review_time`, atau penanda first-run apa pun. Yang ada hanya `worklist_synced_at` (waktu sinkron worklist, bukan waktu crawl).
- OneBox: `VocCrawlQueue::dateRangeForSchedule()` (`app/services/VocCrawlQueue.php:171-199`) hanya mengenal dua sumber rentang — tanggal custom tetap, atau `LookbackDays` tetap. Tidak ada satu pun pembacaan hasil run sebelumnya.

Artinya jadwal harian dengan `LookbackDays=7` akan **selalu** meminta 7 hari terakhir, tiap hari, selamanya. Enam dari tujuh hari itu sudah pasti kita punya.

`FetchLog` (`models.py:468-499`) menyimpan `started_at`/`finished_at` per lokasi, jadi "kapan terakhir sukses" bisa **diturunkan** tanpa kolom baru. Tapi yang benar-benar dibutuhkan bukan itu, melainkan **`last_seen_review_time`** — tanggal review terbaru yang pernah kita lihat di sumber. Itu yang menjadi batas bawah run berikutnya, dan itu belum ada di mana pun.

### 4.4 T4 — `review_time` adalah taksiran, bukan tanggal asli

Ini batasan fundamental yang harus disepakati bersama sebelum menjanjikan apa pun soal akurasi tanggal.

- `selenium_google_maps_client.py` `_extract_review()` mengembalikan `"review_time": None` — Google Maps tidak mengekspos tanggal absolut di DOM kartu ulasan
- `fetch_service.py:98-107` `_resolve_review_time()` menghitungnya dari teks relatif
- `date_parser.py:93-123` `parse_relative_datetime("2 minggu lalu", reference=now)` → `now - 14 hari`

Konsekuensi yang harus jujur disampaikan ke product:

1. **Granularitas kasar.** "setahun lalu" → tepat `now - 365 hari`. Semua ulasan berumur 1–2 tahun menumpuk di beberapa titik tanggal buatan. Filter rentang pada data lama hampir tidak bermakna.
2. **Menggeser antar-crawl.** `reference` adalah waktu scraping. Review yang sama, di-crawl di dua waktu berbeda, bisa menghasilkan `review_time` yang berbeda.
3. **Review tanpa tanggal selalu lolos filter.** `date_parser.py:136-137` — `review_time is None` dianggap masuk rentang, sengaja, agar tidak ada data hilang diam-diam. Benar sebagai pilihan, tapi berarti hitungan "berapa yang masuk rentang" tidak pernah presisi.

**Implikasi desain yang penting:** justru karena tanggal rapuh, **watermark berbasis identitas lebih dapat dipercaya daripada watermark berbasis tanggal**. Berhenti pada "review yang ID-nya sudah pernah kita lihat" jauh lebih tajam daripada berhenti pada "review yang tanggal taksirannya lebih tua dari X". Ini memperkuat T1: memperbaiki identitas menyelesaikan lebih dari satu masalah.

### 4.5 T5 — Rating agregat Google tidak pernah diambil

Sudah dijelaskan di bagian 3. Bentuk penyimpanannya sudah siap: `VocRatingLog` (migrasi `1786140000000000_1_123_0`) punya `RecordedAt`, `ReviewCount`, `AvgRating`, `Star1..Star5`, plus `BatchId` dan `Source` yang komentarnya sendiri sudah mengantisipasi "nanti diisi instrumentasi Crawler". Yang perlu ditambah hanya **dua kolom** untuk angka resmi Google, agar bisa disandingkan dengan angka kita sendiri di baris yang sama.

Menyandingkan keduanya justru lebih berguna daripada menggantikan: selisihnya adalah ukuran **seberapa lengkap** data kita untuk cabang itu.

Catatan terpisah soal tren mingguan/bulanan/kuartalan/tahunan: `VocRatingLog` mencatat **satu baris tiap kali fetch**, jadi kepadatan titiknya mengikuti kepadatan fetch — tidak teratur. Untuk tren yang bisa dibandingkan antar-periode, agregasi perlu di-bucket per periode (ambil satu titik representatif per minggu/bulan, misalnya yang terakhir di periode itu), bukan merata-ratakan semua baris mentah. Ini pekerjaan query di OneBox, bukan perubahan skema.

### 4.6 T6 — Overlap manual vs scheduler

Yang **sudah** ada, dan lebih baik dari dugaan draft sebelumnya:

- `VocTask::dispatchOne()` (`app/tasks/VocTask.php:75`) mengambil slot lewat unique constraint sebelum mengerjakan apa pun — dua proses scheduler tidak bisa menjalankan slot yang sama
- `:84-103` — kalau run sebelumnya untuk jadwal yang sama belum selesai, slot dilewati dengan status `SKIPPED_OVERLAP`
- Idempotency key per batch (`crawl_batches.idempotency_key`, unique per company) mencegah klik ganda melahirkan dua batch
- `crawl_jobs` unique per `(batch_id, location_id)` — satu cabang tidak bisa dobel dalam satu batch

Yang **belum** ada: penguncian **lintas jalur**. Batch manual dan batch terjadwal untuk cabang yang sama, dalam waktu berdekatan, adalah dua batch berbeda dengan idempotency key berbeda — keduanya lolos, keduanya menyisir tanah yang sama.

Yang dibutuhkan: penjagaan di tingkat **target**, bukan batch — "cabang ini sedang di-crawl, tolak/antrekan permintaan lain untuk cabang ini". Kolom `crawl_jobs.status` + `lease_expires_at` sudah menyediakan bahannya; yang kurang adalah pemeriksaannya saat batch dibuat.

---

## 5. Yang sudah benar — jangan dirombak

Penting dicatat supaya refactor tidak merusak yang sehat:

| Bagian | Kenapa jangan disentuh |
| --- | --- |
| **Cursor tarik OneBox ← Crawler** (`VocProvider.php:116-120, 245-250`) | Sudah keyset pagination di `sync_updated_at`, checkpoint tersimpan di `Connection.Options._sync_cursor`, dan cursor **sengaja tidak maju** kalau ada kegagalan di siklus itu. Draft sebelumnya menyiratkan cursor perlu dibangun — tidak, ini sudah matang. |
| **Early-stop rentang tanggal** (`selenium_fetch_service.py:150-181`) | Sudah benar dan sudah lengkap dengan penanganan beda timezone dan peringatan kalau sort gagal terpasang. |
| **Pemaksaan `sort=newest` saat ada rentang** | Sudah dilakukan di dua sisi dengan alasan berbeda yang keduanya sah (OneBox agar layar bisa menjelaskan, Crawler agar aman dari pemanggil lain). |
| **Idempotency batch + lease job** | Fondasi antrian sudah kokoh. Yang kurang cuma penguncian per target (T6). |
| **`is_within_date_range` meloloskan review tanpa tanggal** | Pilihan sadar dan benar — jangan diubah jadi membuang. |

---

## 6. Urutan perbaikan yang disarankan

Diurutkan menurut (dampak ÷ biaya), bukan menurut urutan di dokumen kebutuhan:

1. **T1 identitas review** — paling murah, paling besar dampaknya, dan menyembuhkan gejala yang selama ini dikira beberapa bug terpisah. **Wajib satu paket dengan migrasi backfill hash.**
2. **T5 snapshot rating Google** — kecil, berdiri sendiri, dan langsung menjawab pertanyaan supervisor yang paling sering muncul.
3. **T3 watermark** — kunci agar run berikutnya tidak mengulang tanah yang sama. Bergantung pada T1 kalau watermark-nya berbasis identitas.
4. **T2 mode fetch (backfill / delta / custom)** — paling besar, dan paling aman dikerjakan setelah tiga di atas beres.
5. **T6 lock per target** — kecil, tapi baru benar-benar terasa setelah mode-mode di atas jalan.

Detail tugas, urutan hari, dan kriteria selesai ada di dokumen pasangannya:
`04-implementation-plans/crawler-system/VOC_FETCH_LOGIC_TODO.md`

Dua pertanyaan lanjutan — **"bagaimana kalau tanggalnya kita hitung sendiri?"** dan
**"kenapa maksimal 300, memangnya sudah pernah diuji?"** — dibahas terpisah di
`VOC_TANGGAL_SENDIRI_DAN_BATCHING.md`. Dokumen itu mengoreksi dua hal di sini:
rekomendasi batch size 300 (bagian 8), dan menambahkan jalan keluar untuk T4
yang di sini masih dianggap buntu.

---

## 7. Risiko dan batas yang harus disampaikan jujur

Hal-hal yang tidak boleh dijanjikan, apa pun refactornya:

- **Tanggal review lama tidak akan pernah presisi.** Selama sumbernya teks relatif, "1 Agustus–31 Agustus" untuk data tahun lalu adalah perkiraan. Kalau presisi dibutuhkan, itu ganti sumber data (Google Business Profile API), bukan ganti algoritma.
- **Backfill 1000 review tetap mahal.** Google Maps hanya bisa disisir berurutan dari atas. Batch membuatnya bisa dilanjutkan dan diawasi, bukan membuatnya cepat.
- **Rating kita tidak akan sama persis dengan Google** sampai seluruh ulasan cabang itu tertarik. Yang bisa dijanjikan: menampilkan angka resmi Google **berdampingan** dengan angka kita, plus selisihnya.
- **Perubahan rumus hash adalah operasi sekali jalan yang berisiko.** Tanpa migrasi backfill, ia justru melahirkan satu gelombang duplikat baru. Ini harus diuji di lokal dengan data nyata sebelum menyentuh dev.

---

## 8. Keputusan yang perlu disepakati sebelum eksekusi

Draft pertama sudah mengajukan lima pertanyaan. Berdasarkan temuan kode, ini rekomendasi jawabannya — tinggal dikonfirmasi:

| Pertanyaan | Rekomendasi | Alasan dari kode |
| --- | --- | --- |
| Istilah UI "Jumlah ulasan"? | Ganti jadi **"Batas pengambilan per batch"** | Karena memang itu artinya di `validate_target()`, dan plafonnya 300 |
| First run wajib sebelum scheduler? | **Ya** | Tanpa baseline, watermark tidak punya titik awal yang bermakna |
| Batch size backfill? | ~~**300**~~ → **jangan diukur dengan jumlah review sama sekali** | **DIKOREKSI 2026-09-01.** Alasan awal ("300 itu plafon yang sudah ada") ternyata tidak sahih: 300 masuk pada commit pertama tanpa pernah diukur, dan biaya batching bersifat kuadratik sehingga batch kecil justru **3× lebih mahal** daripada sekali jalan. Batasi dengan anggaran waktu, bukan jumlah. Lihat `VOC_TANGGAL_SENDIRI_DAN_BATCHING.md` bagian 2.4–2.6. |
| Rating snapshot disimpan di mana? | **Crawler ambil, OneBox simpan** | `VocRatingLog` sudah ada dan sudah disiapkan untuk diisi Crawler |
| Manual boleh memotong antrean scheduler? | **Tidak, tapi tidak ditolak diam-diam** | Antrekan dan beri tahu alasannya; menolak diam-diam adalah pola yang sudah pernah menyusahkan di fitur ini |


1. Sebenernya bisa aja masi ada jumlah ulasan/ batas pengambila batch, namun hal ini bisa diimplement apabila ulasan diambil dari belakang ke depan dari last fetched at ke depan. jadi tidak ada ulasan yang berada di tengah . 
2. Iya , jangan lupa cek dlu jumlah ulasan ada berapa (ini bisa ga ya?) if count(sum(ulasan)) => certain number mungkin 350 maka dibagi bagi jadi beberapa batch, ya sesuain aja algoritmanya. ini mending fill in 350 atau dibagi rata baiknya gmn yang optimal aja
3. sip
4. Onebox SIMPAN ini sangat erlu untuk tren dan visualisasi dashboard
5. Tidak, perlu ada validasi UI

Onebox diharapkan memiliki UI yang dapat mencegah hal - hal yang tidak diharapkan, ajdi memang memudahakan dan tidak perlu bekerja 2 kali, alert - alert dan lain - lainnya sangat diperlukan , message alert pun akan sangat berugna

Satu pertanyaan tambahan yang belum ada di draft mana pun, dan ini yang paling menentukan jadwal:

> **Backfill hash lama: dihitung ulang, atau data lama dibiarkan dan dedupe dimulai dari nol?**

Menghitung ulang lebih benar tapi butuh migrasi yang menyentuh seluruh tabel `reviews`. Membiarkan lebih cepat tapi menyisakan duplikat historis yang sudah ada. Keputusan ini mengubah besar-kecilnya Tahap 1 secara signifikan.
