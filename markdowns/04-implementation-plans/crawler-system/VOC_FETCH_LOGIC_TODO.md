# VoC Fetch Logic — To-Do Bertahap (Timeline Mepet)

Status: in progress; Tahap 1 dan Tahap 2 dipercepat dan sudah masuk `main`
Tanggal susun: 2026-09-01
Update terakhir: 2026-09-01
Dokumen pemahaman: `03-architecture/integration/VOC_FETCH_LOGIC_PEMAHAMAN.md`
Draft konseptual terkait: `00-start-here/VOC_FETCH_LOGIC_TOP_DOWN.md`, `PLAN_REVIEW_FETCH_LOGIC_REFACTOR.md`

## Snapshot progress hari ini - 2026-09-01

| Tahap | Status | Bukti |
| --- | --- | --- |
| Tahap 0 - keputusan & persiapan | Partial | Keputusan hash diambil: tidak backfill massal dulu, tetapi insert dilindungi dengan dedupe `external_review_id` agar row lama tidak jadi duplikat baru. Baseline data nyata belum dicatat formal. |
| Tahap 1 - identitas review & dedupe | Done untuk release awal | Commit Crawler `0ce172e`; Selenium hash tidak memakai `review_relative_time`; insert review dan competitor review dedupe via `external_review_id`; test hijau. |
| Tahap 2 - snapshot rating Google | Done di Crawler, consumed oleh OneBox | Commit Crawler `ebf3543`; OneBox commit Claude `bb3a7cac17` consume snapshot; snapshot terbukti muncul di API detail batch. |
| Tahap 3 - watermark per cabang | Not started di Crawler | OneBox punya watermark berbasis data sendiri, tetapi field durable `locations.last_seen_review_id` dkk. belum dibuat di Crawler. |
| Tahap 4 - mode fetch & UI | Partial | Kontrak Crawler sudah punya `crawl_mode`, `max_reviews_to_collect`, `scan_limit`, date range. Perbaikan label/UI OneBox masih terpisah. |
| Tahap 5 - lock + e2e | Partial | Active batch reuse dan idempotency ada. Smoke server berhasil; e2e penuh OneBox -> Crawler -> OneBox -> Kelola Review masih perlu bukti final. |

Deploy/status server:

- `main` server: `0c3c1b3 Merge pull request #11 from sayyidtrq/codex/fetch-review-dedupe-stop-reason`
- API healthy, worker running, WireGuard health `200 OK`
- Smoke `/api/integration/v1/crawl-jobs?limit=3` sudah mengembalikan `stop_reason` dan `stop_reasons`
- Test lokal sebelum merge: `python -m pytest tests -q` -> `115 passed`

## Cara membaca dokumen ini

Timeline-nya **10 hari kerja (1–14 Sep 2026)**, sengaja padat. Supaya tetap maksimal meski mepet, urutannya disusun berdasarkan **dampak dibagi biaya**, bukan urutan di dokumen kebutuhan. Konsekuensinya:

- **Tahap 1–2 sudah menghasilkan perbaikan yang terasa** (duplikat berhenti, rating Google muncul) walaupun sisanya belum jalan
- Tiap tahap punya **titik potong yang aman** — kalau waktu habis, yang sudah selesai tetap layak rilis dan tidak menggantung setengah jalan
- Yang paling berisiko (ubah rumus hash) dikerjakan **paling awal saat energi dan waktu buffer masih penuh**, bukan di ujung

Prioritas kalau harus dipotong: **Tahap 1 dan 2 tidak bisa ditawar.** Tahap 4 adalah yang pertama dikorbankan.

---

## Kalender

| Hari | Tanggal | Isi |
| --- | --- | --- |
| H1 | Sel, 1 Sep | Tahap 0 — keputusan + persiapan uji |
| H2–H3 | Rab–Kam, 2–3 Sep | Tahap 1 — identitas review & dedupe (T1) |
| H4 | Jum, 4 Sep | Tahap 2 — snapshot rating Google (T5) |
| H5–H6 | Sen–Sel, 7–8 Sep | Tahap 3 — watermark per cabang (T3) |
| H7–H9 | Rab–Jum, 9–11 Sep | Tahap 4 — mode fetch & UI (T2) |
| H10 | Sen, 14 Sep | Tahap 5 — lock per target (T6) + verifikasi e2e |

Buffer: tidak ada. Kalau satu tahap meleset, yang bergeser adalah Tahap 4 (dipersempit), bukan Tahap 1–3.

---

## Tahap 0 — Keputusan & persiapan (H1)

Tanpa ini Tahap 1 tidak bisa mulai, jadi selesaikan di hari pertama.

- [x] **0.1 Putuskan: backfill hash lama atau tidak.** Ini yang paling menentukan besar-kecilnya Tahap 1.
  - Opsi A (disarankan): hitung ulang `review_hash` seluruh baris lama lewat migrasi. Lebih benar, +1 hari kerja.
  - Opsi B: biarkan data lama, dedupe dimulai dari nol. Lebih cepat, tapi duplikat historis tetap tinggal dan tetap perlu dibersihkan manual nanti.
  - **Keputusan 2026-09-01:** pakai Opsi B yang diperkuat. Tidak ada migrasi backfill massal hari ini, tetapi insert review sekarang juga mencocokkan `external_review_id`, sehingga data lama dengan hash versi lama tetap tidak diinsert ulang sebagai review baru.
- [~] **0.2 Konfirmasi 5 keputusan** di bagian 8 dokumen pemahaman (istilah UI, first-run wajib, batch size 300, lokasi snapshot, perilaku manual vs jadwal). Semua sudah ada rekomendasi + alasannya — ini konfirmasi, bukan diskusi dari nol.
  - Snapshot disepakati disimpan/ditampilkan di OneBox.
  - Manual vs jadwal dicegah di OneBox.
  - First-run batching masih perlu keputusan final berdasarkan `place_review_count`.
- [ ] **0.3 Siapkan data uji di lokal.** Minimal satu cabang dengan ≥100 review nyata dan riwayat crawl lebih dari sekali, supaya kasus duplikat benar-benar bisa direproduksi sebelum diperbaiki.
- [ ] **0.4 Ambil angka dasar (baseline).** Catat sebelum apa pun diubah — nanti ini yang jadi bukti perbaikan:
  - jumlah baris `reviews` per lokasi
  - jumlah dugaan duplikat: `GROUP BY external_review_id HAVING COUNT(*) > 1`
  - jumlah baris dengan `external_review_id IS NULL` (menentukan seberapa penting fallback hash)

**Selesai kalau:** kedua keputusan tercatat, dan angka baseline tersimpan.

---

## Tahap 1 — Identitas review & dedupe (H2–H3) — **PRIORITAS TERTINGGI**

Menyelesaikan T1. Ini akar duplikat, dan kemungkinan besar juga akar tiket "baris kembar di layar Ulasan" serta "43 baris kembar" yang selama ini dianggap terpisah.

- [x] **1.1 Ubah `generate_selenium_review_hash()`** (`app/utils/hashing.py:19-31`)
  - Pakai `external_review_id` sebagai identitas utama saat tersedia
  - **Buang `review_relative_time` dari hash** — ini inti bug-nya
  - Fallback saat `external_review_id` kosong: `source + location_id + reviewer_profile_url + review_text`. Syarat mutlak: **tidak boleh mengandung apa pun yang berubah seiring waktu**
- [x] **1.2 Tulis unit test yang gagal dulu** sebelum perbaikan, lalu hijau sesudahnya:
  - review sama dengan `review_relative_time` berbeda → hash **sama**
  - dua review berbeda dengan teks sama dari reviewer berbeda → hash **beda**
  - review tanpa `external_review_id` → tetap dapat hash stabil lintas waktu
  - Tempat: `tests/test_selenium_scraping.py` (sudah ada tes hash di `:261`)
- [x] **1.3 Migrasi backfill hash** — **tidak dijalankan karena Opsi A tidak dipilih**
  - Hitung ulang `review_hash` seluruh baris `reviews` + `competitor_reviews`
  - Tangani tabrakan: baris yang setelah dihitung ulang ternyata kembar → sisakan yang `id` terkecil, sisanya hapus (ini justru pembersihan duplikat lama yang kita mau)
  - Wajib idempoten dan wajib bisa dijalankan ulang
- [~] **1.4 Uji di lokal dengan data nyata:** crawl cabang yang sama **dua kali berturut-turut**. Kriteria lulus: crawl kedua menghasilkan `total_inserted = 0` dan `total_duplicate = jumlah review`. Hari ini hasilnya pasti bukan itu — itulah bug-nya.
  - Unit/integration test sudah membuktikan duplicate legacy via `external_review_id`.
  - Uji real dua kali berturut-turut di Google Maps masih perlu dijalankan sebagai evidence E2E.

**Selesai kalau:** crawl berulang tidak lagi menambah baris baru, dan tes 1.2 hijau.
**Titik potong aman:** ya. Berdiri sendiri, tidak butuh tahap lain.

> ✅ Risiko utama tahap ini sudah dikurangi tanpa 1.3: deploy `1.1` tidak berdiri sendirian, karena insert review juga sekarang melakukan dedupe via `external_review_id`. Row lama dengan hash versi lama tetap dikenali sebagai duplikat selama Google memberi `external_review_id`.

---

## Tahap 2 — Snapshot rating Google (H4)

Menyelesaikan T5. Kecil, berdiri sendiri, dan langsung menjawab pertanyaan supervisor yang paling sering muncul.

- [x] **2.1 Tambah selector header tempat** di `app/integrations/google_maps_selectors.py` — bintang keseluruhan dan total jumlah ulasan. Hari ini `RATING_SELECTORS` hanya untuk kartu per-ulasan.
- [x] **2.2 Ambil angkanya di `fetch_reviews()`** dan sertakan di `last_metadata` sebagai `place_rating` + `place_review_count`. Gagal mengambil **tidak boleh menggagalkan crawl** — kosongkan saja dan catat alasannya, ikut pola `sort_applied` yang sudah ada.
- [x] **2.3 Teruskan ke hasil job** lewat `result["metadata"]` di `selenium_fetch_service.py`, lalu ke respons batch supaya OneBox bisa membacanya.
- [x] **2.4 Migrasi OneBox: dua kolom baru di `VocRatingLog`** — `GoogleRating decimal(4,2) NULL` dan `GoogleReviewCount int NULL`.
  - Ikuti pola migrasi VoC yang sudah ada (`tableExists()` guard, latin1 untuk varchar)
  - **Wajib**: pasang guard `SHOW TABLES` di endpoint yang membacanya, pola `vocRatingLogSiap()`. Migrasi rutin tertinggal di dev — ini sudah dua kali bikin layar mati.
- [x] **2.5 Isi kolomnya di `insertRatingLog()`** (`VocController.php:5129`) dari metadata batch.
- [x] **2.6 Tampilkan berdampingan** di layar: rating kita, rating Google, dan selisihnya. Selisih itu **bukan error** — itu ukuran seberapa lengkap data kita, dan harus dijelaskan begitu di UI.

Catatan 2026-09-01:

- Crawler mengirim `rating_snapshot` pada detail batch.
- OneBox sudah consume dengan mencocokkan `onebox_location_id`, bukan mengambil job pertama.
- Grafik tren sudah siap menampilkan garis "Rating Google" jika data tersedia.
- Jalur scheduler belum otomatis mencatat `VocRatingLog`; saat ini bukti rating snapshot paling aman lewat import manual.

**Selesai kalau:** satu crawl menghasilkan satu baris `VocRatingLog` yang memuat rating Google dan rating kita sekaligus.
**Titik potong aman:** ya.

---

## Tahap 3 — Watermark per cabang (H5–H6)

Menyelesaikan T3. Ini yang menghentikan pemborosan menyisir tanah yang sama.

- [ ] **3.1 Tambah kolom watermark di `locations`** (Crawler, Alembic):
  - `last_seen_review_id` — identitas review terbaru yang pernah terlihat (**lebih dapat dipercaya daripada tanggal**, lihat T4 di dokumen pemahaman)
  - `last_seen_review_time` — pendamping, untuk ditampilkan ke manusia
  - `last_successful_crawl_at`
  - `first_run_completed_at` — penanda baseline historis pernah selesai
  - Semua nullable. Cabang lama tanpa nilai harus jatuh ke perilaku sekarang, bukan error.
- [ ] **3.2 Perbarui watermark di akhir job sukses** di `selenium_fetch_service.py`. Hanya kalau job benar-benar sukses — job gagal/parsial **tidak boleh** memajukan watermark, mengikuti prinsip cursor OneBox yang sudah terbukti (`VocProvider.php`: cursor tidak maju kalau ada kegagalan).
- [ ] **3.3 Berhenti dini berbasis identitas.** Perluas `keep_check` di `selenium_fetch_service.py:150-172`: selain berhenti saat lebih tua dari `date_from`, berhenti juga saat menemukan `external_review_id` yang **sama dengan `last_seen_review_id`** — artinya sisanya sudah kita punya semua. Ini penghematan terbesar untuk crawl rutin.
- [ ] **3.4 Laporkan watermark di respons job** supaya OneBox bisa menampilkan "terakhir tersinkron sampai ulasan tanggal X".
- [ ] **3.5 OneBox: pakai watermark untuk jadwal.** Ubah `VocCrawlQueue::dateRangeForSchedule()` (`app/services/VocCrawlQueue.php:171-199`) agar mode delta memakai watermark sebagai batas bawah, bukan `LookbackDays` tetap. **`LookbackDays` tetap dipertahankan** sebagai jaring pengaman kalau watermark kosong.

**Selesai kalau:** jadwal harian pada cabang yang sudah pernah ditarik berhenti setelah beberapa kartu saja, bukan menyisir ulang 7 hari penuh.
**Titik potong aman:** ya, tapi bergantung pada Tahap 1 (identitas harus stabil dulu — kalau tidak, 3.3 justru berbahaya).

---

## Tahap 4 — Mode fetch & UI (H7–H9)

Menyelesaikan T2. Paling besar, karena itu ditaruh setelah tiga tahap di atas beres. **Ini tahap pertama yang dikorbankan kalau waktu habis.**

- [ ] **4.1 Kenalkan `mode` di kontrak crawl job** (`apps/api/app_api/integration_crawl_schemas.py`): `first_run` | `delta` | `custom_range`.
  - Default **wajib** `delta` supaya pemanggil lama tidak berubah perilakunya diam-diam
  - `extra="forbid"` sudah aktif di skema — pastikan OneBox dan Crawler dirilis selaras, jangan kirim field yang belum dikenal
- [ ] **4.2 Perilaku tiap mode:**
  - `first_run` — sisir sejauh mungkin, batch 300 per job, lapor di mana berhenti agar bisa dilanjutkan
  - `delta` — dari watermark sampai sekarang, berhenti begitu ketemu yang sudah dikenal (Tahap 3)
  - `custom_range` — perilaku sekarang, tetap dipertahankan untuk audit dan recovery
- [ ] **4.3 Kelanjutan backfill.** Laporkan `resume_anchor` (identitas kartu terakhir) di hasil job. **OneBox yang memutuskan** apakah membuat job lanjutan — Crawler melapor fakta, OneBox memegang kebijakan. Jangan taruh keputusan lanjut/berhenti di Crawler.
- [ ] **4.4 UI OneBox — inti perubahannya di bahasa, bukan di kontrol:**
  - "Jumlah ulasan" → **"Batas pengambilan per batch"**, dan jelaskan bahwa ini batas biaya, bukan janji hasil
  - Kunci field-nya untuk mode `delta` (dokumen kebutuhan minta ini di-lock di FE) — nilai default dari sistem, bukan diisi user
  - Tampilkan hasil apa adanya: berapa disisir, berapa baru, berapa sudah punya, **berapa dilewati karena di luar rentang**, dan kenapa berhenti (`stopped_reason` sudah tersedia di metadata dan hari ini belum ditampilkan)
- [ ] **4.5 Terjemahkan `stopped_reason` ke bahasa manusia.** Nilai yang sudah ada: `target_reached`, `out_of_range`, `time_limit`, `no_new_review_cards`, `max_scroll_attempts`. Ini yang menghentikan tuduhan "fetch-nya gagal" padahal crawler bekerja benar.

**Selesai kalau:** user bisa membedakan "sudah semua" dari "berhenti karena batas", tanpa bertanya ke engineer.
**Titik potong aman:** 4.4 + 4.5 saja sudah bernilai besar walaupun 4.1–4.3 ditunda — perbaikan bahasa dan transparansi tidak butuh perubahan kontrak.

---

## Tahap 5 — Lock per target & verifikasi e2e (H10)

- [ ] **5.1 Tolak/antrekan job untuk target yang sedang berjalan.** Saat batch dibuat, periksa apakah ada `crawl_jobs` aktif (`status` berjalan dan `lease_expires_at` belum lewat) untuk `location_id` yang sama. Bahannya sudah ada di tabel, tinggal diperiksa.
  - **Beri tahu alasannya, jangan tolak diam-diam.** Menolak diam-diam adalah pola yang sudah pernah menyusahkan di fitur ini.
- [ ] **5.2 Verifikasi e2e di stack lokal:**
  - first_run cabang baru → backfill berbatch, watermark terisi
  - delta run kedua → berhenti cepat, `inserted = 0`
  - manual saat jadwal berjalan → ditolak/diantre dengan pesan yang jelas
  - `VocRatingLog` berisi rating Google dan rating kita
  - **bandingkan dengan baseline 0.4** — jumlah duplikat harus turun, idealnya nol
- [ ] **5.3 Catat batasan yang tersisa** di dokumen pemahaman bagian 7, khususnya soal presisi tanggal review lama. Ini harus sampai ke product, bukan berhenti di engineering.

---

## Di luar lingkup

Supaya tidak melebar saat waktu sudah mepet:

- **Tidak** mengganti sumber data ke Google Business Profile API. Itu satu-satunya cara mendapat tanggal presisi, tapi itu proyek tersendiri.
- **Tidak** merombak cursor tarik OneBox←Crawler. Sudah matang, lihat bagian 5 dokumen pemahaman.
- **Tidak** memindahkan kepemilikan scheduler UI dari OneBox.
- **Tidak** membuat aturan sentiment atau analisis AI baru.
- **Tidak** membersihkan duplikat historis di luar yang otomatis terbawa migrasi 1.3.

---

## Ketergantungan antar tahap

```
Tahap 0 (keputusan)
   └─> Tahap 1 (identitas)  ──> Tahap 3 (watermark) ──> Tahap 4 (mode)
   └─> Tahap 2 (rating)  [berdiri sendiri, bisa paralel]
                                                          └─> Tahap 5 (lock + e2e)
```

Tahap 2 tidak bergantung pada apa pun — kalau ada orang kedua, ini yang paling enak dikerjakan paralel dengan Tahap 1.

---

## Definisi selesai (keseluruhan)

1. Crawl cabang yang sama dua kali tidak menambah satu baris pun — dibuktikan dengan angka, dibandingkan dengan baseline 0.4
2. Jadwal rutin berhenti setelah beberapa kartu, bukan menyisir ulang seluruh lookback
3. Rating Google dan rating OneBox tampil berdampingan beserta selisihnya
4. User bisa membaca sendiri kenapa sebuah fetch berhenti
5. Manual dan scheduler tidak lagi menyisir cabang yang sama bersamaan
6. Backfill cabang baru berjalan berbatch dengan riwayat yang jelas dan bisa dilanjutkan
