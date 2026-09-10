# Eksplorasi: Menghitung Tanggal Sendiri, dan Membongkar Batas 300

Status: eksplorasi teknis — belum keputusan, tapi sudah ada rekomendasi berbukti
Tanggal: 2026-09-01
Induk: `VOC_FETCH_LOGIC_PEMAHAMAN.md` (temuan T4 dan bagian 3)
Pasangan rencana: `04-implementation-plans/crawler-system/VOC_FETCH_LOGIC_TODO.md`

Dokumen ini menjawab dua pertanyaan yang muncul setelah pemahaman awal:

1. **"Gimana kalau kita yang ngitung tanggalnya sendiri, berdasarkan tanggal ulasan masuk?"**
2. **"Kenapa maksimal 300? Emangnya udah pernah dicoba? Kalau cabang A punya 1500 review berarti dibagi 5 batch — explore ini."**

Keduanya ternyata bertemu di satu titik yang sama, dan itu dibahas di bagian 3.

---

# BAGIAN 1 — Menghitung tanggal sendiri

## 1.1 Kenapa ide ini kuat

Hari ini `review_time` dihitung dengan satu cara saja: ambil teks relatif dari Google ("2 minggu lalu"), kurangkan dari waktu scraping, jadikan satu titik tanggal (`fetch_service.py:98-107` → `date_parser.py:93-123`).

Itu membuang informasi yang sebenarnya sudah kita punya. Kita ini **mengamati Google berkali-kali dari waktu ke waktu**, dan tiap pengamatan itu adalah bukti. Kita cuma belum pernah memakainya.

Analoginya: kalau kemarin sore rak masih kosong dan pagi ini ada barang di situ, kita tahu barang itu datang **semalam** — tidak peduli label di kardusnya menulis "dikirim bulan lalu". Pengamatan mengalahkan label.

## 1.2 Dua sumbu waktu yang selama ini tercampur

Ini pembedaan paling penting di dokumen ini. Ada **dua** tanggal berbeda, dan menyamakannya adalah sumber kebingungan:

| | Sumbu peristiwa | Sumbu pengamatan |
| --- | --- | --- |
| **Artinya** | Kapan pelanggan menulis ulasannya | Kapan ulasan itu masuk ke sistem kita |
| **Sumbernya** | Teks relatif Google — taksiran | Jam kita sendiri — pasti |
| **Presisi** | Kasar, dan makin lama makin kasar | Detik |
| **Stabil?** | Tidak, bisa bergeser antar-crawl | Ya, tidak pernah berubah |
| **Sudah ada di DB?** | `reviews.review_time` | **Ya — `reviews.created_at` dan `scraped_at`** |

Poin yang mengejutkan: **"tanggal ulasan masuk" yang lo maksud itu sudah tersimpan sejak awal.** `Review.created_at` (`models.py:404-406`, `server_default=func.now()`) terisi otomatis saat baris pertama kali masuk. Kita tidak perlu membangun apa pun untuk memilikinya — kita cuma belum pernah memakainya untuk apa pun.

**Aturan pakainya:**

- Pertanyaan **"apa yang terjadi pada bisnis kita minggu ini"** → sumbu **pengamatan**. Ini pertanyaan operasional: kapan kita tahu, kapan kita bisa bertindak. Tanggal masuk justru **lebih benar** di sini, bukan kompromi.
- Pertanyaan **"ulasan yang ditulis Agustus"** → sumbu **peristiwa**. Ini yang tidak akan pernah presisi.

Yang berbahaya adalah mencampur keduanya diam-diam di satu grafik. Itu yang harus dihentikan.

> Catatan: tren rating (`VocRatingLog`) **sudah** memakai sumbu pengamatan — `RecordedAt` adalah waktu pengukuran, dan komentar migrasinya menyebut alasannya dengan tepat ("yang dilacak adalah kapan kita mengukur"). Jadi untuk pertanyaan "minggu lalu 4.8, minggu ini 4.5", desainnya sudah benar dan tidak perlu diapa-apakan.

## 1.3 Empat teknik menghitung sendiri, dari yang paling kuat

### Teknik A — Batas dari pengamatan (first-seen bounding)

**Idenya:** kalau pada crawl tanggal 1 review X **tidak ada**, lalu pada crawl tanggal 2 review X **ada**, maka X ditulis di antara keduanya.

```
crawl T1 (1 Sep, 08:00) → X tidak ada
crawl T2 (2 Sep, 08:00) → X ada
⟹ tanggal asli X ∈ (1 Sep 08:00, 2 Sep 08:00]
```

Presisinya = **jarak antar-crawl**. Scheduler harian → presisi ±1 hari. Bandingkan dengan "2 minggu lalu" yang presisinya ±7 hari. **Peningkatan 7–14 kali lipat**, dan sifatnya pasti, bukan taksiran.

**Syarat yang harus dipenuhi — ini yang gampang salah:** "tidak ada" hanya jadi bukti kalau crawl T1 **benar-benar menyisir sampai lebih dalam dari posisi X**. Kalau T1 cuma ambil 50 kartu teratas dan X ada di posisi 80, ketidakhadiran X di T1 tidak membuktikan apa pun.

Karena Google mengurutkan terbaru-dulu, syarat ini otomatis terpenuhi untuk **review baru** dalam mode delta: apa pun yang lebih baru dari watermark pasti muncul di atas, jadi kalau tidak terlihat, memang belum ada. Jadi teknik ini **valid persis untuk kasus yang paling kita butuhkan** (review baru), dan tidak valid untuk backfill.

**Prasyarat:** identitas review harus stabil dulu (temuan T1 di dokumen induk). Tanpa itu kita tidak bisa membedakan "review baru" dari "review lama yang hash-nya berubah", dan seluruh teknik ini runtuh. **Teknik A tidak bisa dikerjakan sebelum T1 selesai.**

### Teknik B — Batas dari urutan (order constraints)

**Idenya:** Google mengembalikan terbaru-dulu. Jadi untuk kartu berurutan di posisi 1, 2, 3, …:

```
tanggal(r₁) ≥ tanggal(r₂) ≥ tanggal(r₃) ≥ …
```

Kalau ada beberapa review yang tanggalnya sudah kita ketahui pasti (dari Teknik A), review di antaranya **terkurung** di antara keduanya:

```
posisi 5  : 20 Agu  ← pasti (dari first-seen)
posisi 6  : ?        ⟹ pasti antara 1 Jul dan 20 Agu
posisi 7  : ?        ⟹ pasti antara 1 Jul dan 20 Agu
...
posisi 40 : 1 Jul   ← pasti (dari first-seen)
```

Ini tidak memberi tanggal pasti, tapi memberi **batas yang benar** — dan batas yang benar jauh lebih berguna daripada titik yang salah. Makin banyak jangkar pasti dari Teknik A, makin sempit kurungannya.

Bonus: teknik ini juga **mendeteksi data rusak**. Kalau hasil taksiran teks relatif melanggar urutan (posisi 6 "lebih baru" dari posisi 5), berarti parsing-nya salah. Hari ini pelanggaran seperti itu lewat tanpa ada yang tahu.

**Peringatan:** urutan hanya terjamin kalau `sort_applied = true`. Kalau pemasangan urutan "Terbaru" gagal, Google memakai urutan relevansi yang tidak kronologis, dan seluruh teknik ini **tidak boleh dipakai**. Untungnya `sort_applied` sudah dicatat di metadata (`selenium_fetch_service.py:191-197`), jadi penjagaannya tinggal dipasang.

### Teknik C — Simpan bucket sebagai rentang, bukan titik

**Masalah sekarang:** `parse_relative_datetime("sebulan lalu")` mengembalikan tepat `now - 30 hari`. Padahal "sebulan lalu" di Google berarti **di suatu tempat antara 30 dan 60 hari lalu**. Kita menyimpan presisi yang tidak kita miliki.

**Perbaikannya:** simpan dua angka, bukan satu.

| Teks Google | Batas bawah | Batas atas |
| --- | --- | --- |
| "seminggu lalu" | −14 hari | −7 hari |
| "2 minggu lalu" | −21 hari | −14 hari |
| "sebulan lalu" | −60 hari | −30 hari |
| "setahun lalu" | −730 hari | −365 hari |

Rentangnya lebar, dan itu justru **jujur**. Nilainya baru terasa saat digabung: rentang dari Teknik C **diiriskan** dengan kurungan dari Teknik B dan jangkar dari Teknik A. Irisan dari tiga batas selalu lebih sempit daripada masing-masing.

Ini juga membereskan cacat halus yang ada sekarang: `is_within_date_range` (`date_parser.py:126-142`) meloloskan review tanpa tanggal, tapi menguji review bertanggal seolah tanggalnya pasti. Dengan rentang, pertanyaannya berubah jadi lebih tepat: *"apakah rentang review ini beririsan dengan jendela yang diminta?"*

### Teknik D — Pengamatan pertama adalah yang paling presisi

Ini temuan yang menghemat kerja, sekaligus peringatan.

Teks relatif **memburuk seiring waktu**. Review yang ditulis hari ini akan berturut-turut berlabel: "baru saja" (presisi jam) → "2 hari lalu" (presisi hari) → "sebulan lalu" (presisi bulan) → "setahun lalu" (presisi tahun). **Pengamatan pertama selalu yang paling tajam.**

Artinya: begitu kita mencatat tanggal sebuah review, **jangan pernah ditimpa** oleh hasil crawl berikutnya — itu justru menurunkan kualitas data.

Kabar baiknya, arsitektur sekarang sudah melakukan ini **secara tidak sengaja**: `insert_review` (`review_service.py:44-46`) mengembalikan `(None, True)` untuk duplikat — **skip, tidak pernah update**. Jadi nilai pertama bertahan.

Tapi ini kebetulan, bukan keputusan — dan kebetulan bisa hilang saat orang lain menambah fitur "update review yang berubah". **Harus dijadikan aturan tertulis**, dengan pengecualian yang disengaja: field yang memang boleh diperbarui (balasan owner, jumlah like) diperbarui, sedangkan **tanggal tidak pernah**.

### Yang sengaja ditolak — Teknik E: menebak secara statistik

Menyebar tanggal berdasarkan laju kedatangan rata-rata ("cabang ini biasanya dapat 3 ulasan/hari, jadi 30 ulasan ini disebar 10 hari ke belakang").

**Jangan.** Ini mengarang data yang tidak bisa dibedakan dari data asli oleh siapa pun yang membacanya nanti. Batas yang lebar tapi jujur selalu lebih baik daripada titik yang rapi tapi fiktif. Kalau presisi benar-benar dibutuhkan, jawabannya ganti sumber data (Google Business Profile API), bukan menebak lebih rapi.

## 1.4 Bentuk data yang diusulkan

Ganti satu kolom `review_time` dengan satu himpunan kecil:

| Kolom | Isi |
| --- | --- |
| `event_date_lower` | Batas paling awal yang mungkin |
| `event_date_upper` | Batas paling akhir yang mungkin |
| `event_date_source` | `observed` \| `bounded` \| `relative_only` — dari mana batas itu berasal |
| `first_seen_at` | Kapan kita pertama melihatnya (= `created_at`, sudah ada) |

`review_time` **tetap dipertahankan** sebagai titik tengah untuk ditampilkan, supaya tidak ada layar atau query yang rusak. Yang berubah: ia tidak lagi jadi satu-satunya kebenaran.

`event_date_source` adalah kolom yang paling berguna untuk kepercayaan pengguna — ia membuat layar bisa berkata jujur:

- `observed` → "Masuk 2 Sep" (presisi jam, dari Teknik A)
- `bounded` → "Antara 1 Jul – 20 Agu" (dari Teknik B)
- `relative_only` → "Sekitar Agustus 2025" (dari Teknik C saja — data lama)

## 1.5 Batas jujur dari pendekatan ini

- **Backfill tidak tertolong.** Saat 1500 review lama ditarik sekaligus, semuanya punya `first_seen_at` yang sama. Teknik A tidak memberi apa-apa; yang bekerja hanya B dan C. **Data historis akan tetap kasar selamanya** — itu tidak bisa diperbaiki oleh algoritma mana pun.
- **Nilainya menumpuk ke depan, bukan ke belakang.** Makin lama sistem berjalan dengan crawl teratur, makin banyak review yang punya tanggal `observed`. Setahun dari sekarang, mayoritas data akan presisi. Hari ini, hampir tidak ada.
- **Presisi terikat pada rajinnya crawl.** Scheduler harian → ±1 hari. Seminggu sekali → ±7 hari, tidak lebih baik dari teks relatif. **Jadi nilai teknik ini bergantung penuh pada scheduler yang benar-benar jalan teratur.**

---

# BAGIAN 2 — Membongkar batas 300

## 2.1 Jawaban singkat: tidak, belum pernah diuji

Angka 300 masuk pada **commit pertama repo ini** (`9a61e0f`, "vhang", 29 Jun 2026), bersamaan dengan `validate_target()` itu sendiri. Tidak ada commit, ADR, atau catatan uji mana pun yang menurunkannya dari pengukuran.

Itu **konstanta pengaman yang dipasang untuk berjaga-jaga**, bukan plafon teknis yang ditemukan lewat percobaan. Dugaan lo benar.

## 2.2 Bukti empiris: 464 kartu sudah pernah disisir dalam satu job

Ini yang menyelesaikan perdebatan. Dari `01-product-and-backlog/jira-specs/DNGO19-3420_Fetch-Jobs-Crawl.md:33`:

> "Contoh terukur: target 10 ulasan, disisir **464**, 444 di luar rentang, 10 masuk."

Satu job **sudah pernah menggulir dan mem-parsing 464 kartu** di dev, tanpa kecelakaan. Itu 55% lebih dalam dari plafon 300 yang katanya batas.

Sebabnya: **300 membatasi jumlah yang DISIMPAN, bukan yang DISISIR.** Loop-nya berbunyi `while kept < target` (`selenium_google_maps_client.py:394`), dan `kept` hanya bertambah untuk kartu yang lolos saringan. Kedalaman penyisiran sudah lama bebas — dan sudah terbukti sampai 464.

Jadi pertanyaannya bukan "apakah bisa lebih dari 300", tapi **"apa yang sebenarnya membatasi"**.

## 2.3 Batas yang sesungguhnya

Ada empat, dan tidak satu pun bernama 300:

| Batas | Nilai | Peran |
| --- | --- | --- |
| `time_limit_seconds` | **600 detik** | **Ini yang sebenarnya mengikat** |
| `crawl_worker_lease_seconds` | 900 detik | Plafon keras di atasnya |
| `selenium_max_scroll_attempts` | 400 (plafon 1000) | Jarang tercapai duluan |
| `max_no_new_scroll_attempts` | 5 | Pendeteksi ujung daftar — **paling rapuh** |

**Rantai yang wajib dijaga:**

```
time_limit_seconds (600)  <  crawl_worker_lease_seconds (900)
```

Kalau `time_limit` dinaikkan melewati lease, lease kedaluwarsa di tengah job → worker lain **mengklaim ulang job yang masih berjalan** → dua worker menyisir cabang yang sama → kerja ganda dan berpotensi baris ganda. Menaikkan satu **wajib** menaikkan yang lain, dengan jarak aman. Ini jebakan paling berbahaya di seluruh dokumen ini.

Sementara `SELENIUM_MAX_TARGET_REVIEWS` sebetulnya sudah env var yang bisa diubah (default 300, `config.py:228`) — **tapi percuma**, karena `validate_target()` menimpanya:

```python
maximum = min(self.settings.selenium_max_target_reviews, 300)   # selenium_fetch_service.py:397
```

Naikkan env var ke 1000 pun hasilnya tetap 300. Ada **tiga tempat** yang mengunci angka ini dan ketiganya harus diubah bersama-sama:

1. `apps/api/app_api/integration_crawl_schemas.py:20` — `le=300` (Pydantic menolak permintaannya sebelum sampai mana-mana)
2. `app/services/selenium_fetch_service.py:397` — `min(..., 300)`
3. OneBox `VocController.php` — beberapa `max(1, min(300, ...))`

Melewatkan salah satunya menghasilkan kegagalan yang membingungkan: OneBox mengirim 500, Pydantic menolak 422, dan layar cuma bilang "fetch gagal".

`max_no_new_scroll_attempts = 5` layak diwaspadai terpisah: lima gulir berturut-turut tanpa kartu baru dianggap "habis". Pada crawl dalam yang panjang, Google kadang lambat memuat — lima kali meleset berjeda 1 detik bisa terjadi karena jaringan, bukan karena datanya habis. **Ini penyebab paling mungkin sebuah backfill berhenti diam-diam sebelum waktunya**, dan hari ini kita tidak bisa membedakannya dari "memang sudah habis". Untuk backfill, angka ini perlu dinaikkan.

## 2.4 Matematika batching — dan kenapa 5 batch justru pilihan terburuk

Di sinilah usulan lo ("1500 dibagi 5 batch @300") perlu diperiksa, karena ada biaya tersembunyi yang besar.

**Google Maps tidak punya cursor.** Tidak ada cara meminta "beri saya review ke-301 sampai ke-600". Satu-satunya jalan ke posisi 301 adalah **menggulir melewati 300 yang di atasnya lagi, dari nol**.

Jadi tiap batch berikutnya harus mengulang seluruh jalan batch sebelumnya:

```
Batch 1: gulir 0 →  300   (biaya 300)
Batch 2: gulir 0 →  600   (biaya 600, 300 di antaranya terbuang)
Batch 3: gulir 0 →  900   (biaya 900, 600 terbuang)
Batch 4: gulir 0 → 1200   (biaya 1200, 900 terbuang)
Batch 5: gulir 0 → 1500   (biaya 1500, 1200 terbuang)
────────────────────────────────────────────────
Total                       4500 kartu dilewati untuk 1500 review
```

**3× lipat pemborosan.** Rumusnya, untuk N review dengan batch B:

```
total kartu dilewati ≈ N² / (2B) + N/2
```

Biayanya **kuadratik terhadap N**, dan **berbanding terbalik dengan B**. Konsekuensinya berlawanan dengan intuisi:

| Batch size | Jumlah batch | Total kartu dilewati | Pemborosan |
| --- | --- | --- | --- |
| 300 | 5 | 4.500 | 3,0× |
| 500 | 3 | 3.000 | 2,0× |
| 750 | 2 | 2.250 | 1,5× |
| 1500 (sekali jalan) | 1 | 1.500 | 1,0× |

**Batch kecil bukan lebih aman — ia lebih mahal.** Memilih 300 untuk backfill berarti membayar tiga kali lipat kerja. Semakin besar batch yang muat dalam anggaran waktu, semakin murah totalnya.

Ini juga berarti pertanyaan di ADR-0005 ("batch 300, 400, atau 500?") sebenarnya salah bingkai. **Batch tidak seharusnya diukur dengan jumlah review sama sekali** — lihat 2.6.

## 2.5 Fast-forward: memangkas pemborosan itu 5–10×

Pemborosan di atas terlihat fatal, tapi sebenarnya bisa ditekan drastis — dan perbaikannya sangat kecil.

Melewati kartu ada dua biaya yang sangat berbeda:

| Kegiatan | Biaya |
| --- | --- |
| Menggulir melewati kartu | Murah — beberapa milidetik |
| **Mem-parsing** kartu | **Mahal** — klik "Lainnya" (`_expand_review`), lalu ~12 pencarian DOM |

Saat mengulang jalan batch sebelumnya, kita **tidak perlu mem-parsing** — kartu-kartu itu sudah kita punya. Cukup lewati.

Dan strukturnya sudah siap menerima ini. Di `selenium_google_maps_client.py:422-427`:

```python
card_id = self._card_identity(card)     # ← murah: satu baca atribut
...
self._expand_review(card, driver)       # ← mahal: klik + banyak query DOM
```

Identitas kartu **sudah dibaca lebih dulu** (baris 422) **sebelum** pekerjaan mahal dimulai (baris 427). Jadi tinggal disisipkan: kalau `card_id` sudah ada di daftar yang kita punya, `continue` — jangan expand, jangan extract.

Dampaknya pada contoh 1500 review, batch 300:

```
Sebelum : 4500 kartu di-parsing penuh
Sesudah : 1500 kartu di-parsing penuh + 3000 kartu digulir cepat
```

Karena menggulir jauh lebih murah daripada mem-parsing, biaya nyatanya turun mendekati kasus tanpa pemborosan. **Ini perbaikan paling menguntungkan di seluruh dokumen ini** — beberapa baris kode, menghapus sebagian besar biaya batching.

Syaratnya sama seperti sebelumnya: **identitas kartu harus stabil** (temuan T1). `_card_identity()` sudah memakai `data-review-id`, jadi bahannya sudah benar — tinggal disambungkan dengan daftar yang sudah tersimpan di DB.

## 2.6 Rekomendasi: batch dibatasi WAKTU, dilanjutkan lewat POSISI

Kesimpulan dari 2.3–2.5: **jumlah review adalah satuan yang salah untuk membatasi batch.**

Alasannya, 300 review bisa berarti dua hal yang biayanya jauh berbeda:

- 300 review baru di puncak daftar → cepat, beberapa menit
- 300 review setelah melewati 1200 yang sudah dipunyai → jauh lebih lama, bisa kehabisan waktu sebelum dapat satu pun yang baru

Satu-satunya hal yang benar-benar perlu dijaga adalah **job tidak boleh melampaui lease-nya**. Jadi batasi dengan itu langsung:

| Aspek | Sekarang | Usulan |
| --- | --- | --- |
| Batas batch | 300 review | **Anggaran waktu** (mis. 12 menit) |
| Lease worker | 900 detik | **Naikkan** ke 1500 detik, selalu > anggaran waktu |
| Berhenti karena | `target_reached` | `time_budget_reached` + laporkan posisi berhenti |
| Lanjut ke batch berikutnya | Tidak ada | `resume_anchor` = identitas kartu terakhir |
| Melewati yang sudah punya | Parsing penuh | **Fast-forward** (2.5) |
| Ukuran yang dilaporkan | "300 dari 300" | "sampai kartu ke-780 dari ±1500, lanjut" |

Dengan bentuk ini, `target_review_count` berubah peran menjadi **pagar pengaman opsional** ("berhenti kalau sudah dapat sebanyak ini"), bukan penentu selesai. Dan pertanyaan "berapa batch untuk 1500 review" jawabannya jadi: *sebanyak yang dibutuhkan* — sistem yang menghitung, bukan manusia yang menebak di muka.

## 2.7 Cara membuktikan sebelum mengubah kontrak

Karena 300 tidak pernah diuji, **jangan diganti dengan angka tebakan lain.** Ukur dulu — dan ini murah, cukup satu hari:

1. Ambil satu cabang nyata yang ulasannya banyak (Hermina Depok, ±1000+).
2. Jalankan crawl dengan `time_limit_seconds` dinaikkan bertahap: 600 → 900 → 1200 detik. **Naikkan lease-nya lebih dulu**, jangan sampai lease kedaluwarsa (lihat 2.3).
3. Catat tiap kali: berapa kartu tersisir, berapa detik, apa `stopped_reason`-nya, berapa MB memori Chrome.
4. Cari titik di mana ia berhenti karena `no_new_review_cards` **padahal daftarnya belum habis** — itu batas rapuh yang sesungguhnya, dan itu yang perlu dinaikkan (bukan 300).
5. Baru dari angka itu tentukan anggaran waktu per batch.

Hasil yang diharapkan berdasarkan bukti 464 kartu: **satu job semestinya sanggup 500–1000 kartu** dalam 10–20 menit. Kalau benar, cabang 1500 review selesai dalam **2–3 batch**, bukan 5 — dan dengan fast-forward, pemborosannya nyaris hilang.

---

# BAGIAN 3 — Kenapa dua pertanyaan ini sebenarnya satu

Keduanya bertemu di **T1, identitas review yang stabil**:

```
                    ┌──────────────────────────────┐
                    │  T1: identitas stabil        │
                    │  (external_review_id)        │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
   Teknik A: first-seen bounding          Fast-forward batching (2.5)
   → tanggal presisi ±1 hari              → pemborosan backfill hilang
   (butuh: tahu mana yang benar-benar     (butuh: tahu kartu mana yang
    baru, bukan hash yang berubah)         sudah dipunyai)
```

Keduanya bertanya hal yang sama ke sistem: **"review ini sudah pernah kita lihat atau belum?"** Selama hash masih memakai `review_relative_time` yang berubah seiring waktu, jawabannya salah — dan kedua ide di dokumen ini mustahil dikerjakan.

Ini menguatkan urutan di dokumen rencana: **T1 dulu, tidak bisa ditawar.** Bukan karena duplikatnya saja, tapi karena ia **pintu masuk** ke dua perbaikan besar berikutnya.

## Urutan yang disarankan

| Urutan | Pekerjaan | Kenapa di sini |
| --- | --- | --- |
| 1 | **T1 — identitas stabil** | Prasyarat semuanya |
| 2 | **Fast-forward** (2.5) | Beberapa baris, dampak terbesar per baris kode |
| 3 | **Uji batas waktu** (2.7) | Sehari, dan menggantikan tebakan dengan angka |
| 4 | **Teknik D — bekukan tanggal pertama** | Nyaris gratis: jadikan perilaku yang sudah ada sebagai aturan tertulis |
| 5 | **Teknik A — first-seen bounding** | Butuh kolom baru; nilainya menumpuk seiring waktu |
| 6 | **Batch berbasis waktu** (2.6) | Ubah kontrak — kerjakan setelah 3 memberi angkanya |
| 7 | **Teknik B + C — batas rentang** | Paling besar, paling bisa ditunda |

Nomor 1–4 semuanya kecil, dan berempat sudah menyelesaikan bagian terbesar dari kedua pertanyaan di dokumen ini.

## Yang harus disepakati

1. **Apakah kita menerima dua sumbu waktu?** Kalau ya, tiap layar dan tiap grafik harus menyatakan sedang memakai sumbu yang mana. Ini keputusan produk, bukan teknis.
2. **Boleh menaikkan lease worker?** Ini menyentuh perilaku antrian, bukan cuma crawl. Tanpa ini, anggaran waktu per batch tidak bisa dinaikkan sama sekali.
3. **Tanggal historis dibiarkan kasar?** Rekomendasi: ya, dan **ditandai jujur** di layar (`event_date_source = relative_only`), bukan dirapikan dengan tebakan.
4. **Berapa anggaran waktu per batch?** Jangan dijawab sekarang — jawab dengan hasil pengukuran 2.7.
