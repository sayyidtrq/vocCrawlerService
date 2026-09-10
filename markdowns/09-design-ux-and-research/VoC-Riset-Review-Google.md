# VoC — Riset Review Google: Identitas Reviewer, Dua Jalur Pengambilan, dan Rencana Implementasi

Dokumen gabungan
Konteks: OneBox VoC / Kelola Review + herminaCrawler
Terakhir diperbarui: 2026-08-21

---

## Daftar Isi

- [0. Ringkasan Eksekutif](#0-ringkasan-eksekutif)
- [BAGIAN I — Identitas Reviewer & Jejak Maker](#bagian-i--identitas-reviewer--jejak-maker)
- [BAGIAN II — Dua Jalur Pengambilan Review](#bagian-ii--dua-jalur-pengambilan-review)
- [BAGIAN III — Rencana Implementasi](#bagian-iii--rencana-implementasi)
- [BAGIAN IV — Temuan dari Repo Crawler](#bagian-iv--temuan-dari-repo-crawler)
- [Lampiran — Query Verifikasi](#lampiran--query-verifikasi)

---

## 0. Ringkasan Eksekutif

Tiga pertanyaan yang dijawab dokumen ini:

| # | Pertanyaan | Jawaban singkat |
|---|---|---|
| 1 | Bisakah reviewer Google dikenali unik? | **Sudah bisa, dan sudah jalan** — tapi ada satu lubang yang menggabungkan orang berbeda |
| 2 | Bisakah kita ambil review lewat Google Business API? | **Bisa**, tapi butuh persetujuan Google dan tidak bisa menggantikan crawler |
| 3 | Bagaimana membedakan review official vs hasil scraping? | Dua field terpisah — bukan satu, dan alasannya penting |

**Tiga temuan yang paling perlu ditindaklanjuti:**

1. **Fallback nama menggabungkan orang berbeda.** Setiap "Budi Santoso" dalam satu site menjadi satu Contact. Ini berjalan sekarang, bukan risiko teoretis.
2. **`review_hash` Selenium memakai teks waktu relatif.** "3 bulan lalu" berubah seiring waktu → hash berubah → ulasan yang sama masuk lagi. Ini akar penggandaan 16% yang pernah terjadi.
3. **`is_official` tidak bisa disetel dari layar mana pun.** Akibatnya tombol Balas permanen mati di seluruh site.

---

# BAGIAN I — Identitas Reviewer & Jejak Maker

## I.1 Yang sudah berjalan

Identitas reviewer **sudah terimplementasi** di `VocProvider::buildReviewerIdentity()`. Dipanggil saat ingest, hasilnya jadi `$message->From['id']`, lalu `ContactService::ensureContact()` melakukan find-or-create `Contact` berdasarkan **SiteId + GbusinessId**.

```php
return 'voc-reviewer:' . hash('sha256', $identitySource);
```

Prioritas sumbernya berlapis tiga:

| # | Sumber | Bentuk | Penilaian |
|---|---|---|---|
| 1 | `reviewer_profile_url` | `profile:<url tanpa slash akhir>` | **Benar.** URL memuat contributor id Google yang menempel pada akun — bertahan walau nama dan foto diganti. |
| 2 | `reviewer_name` ternormalisasi | `name:<lowercase, spasi rapat>` | **Berbahaya — lihat I.2** |
| 3 | Anonymous | `anonymous-review:<review_hash>` | **Benar.** Sengaja membuat tiap ulasan anonim jadi Contact sendiri, supaya orang anonim yang berbeda tidak digabung. |

Lapis 1 dan 3 sudah tepat. Lapis 3 khususnya menunjukkan pertimbangan yang bagus dari penulisnya.

## I.2 Lubangnya: fallback nama

Ketika `reviewer_profile_url` kosong dan reviewer bukan Anonymous, identitasnya menjadi `name:<nama>`.

Akibatnya **setiap "Budi Santoso" dalam satu site menjadi satu Contact yang sama** — lintas cabang, lintas tahun.

Untuk grup rumah sakit dengan belasan cabang di Indonesia, nama berulang bukan kemungkinan kecil; itu keniscayaan. Konsekuensinya:

- "Ulasan ke-4 dari reviewer ini" bisa sebenarnya empat orang berbeda
- Riwayat seorang pasien tercampur dengan orang asing yang kebetulan senama
- Kalau dipakai untuk memutuskan prioritas atau menandai pelanggan bermasalah, keputusannya berdiri di atas data yang salah

Komentar di kode sudah jujur menyebut ini "fallback karena contract belum punya `reviewer_id` khusus". Masalahnya, begitu tersimpan, fallback ini **tidak bisa dibedakan** dari identitas yang benar — keduanya sama-sama `voc-reviewer:<sha256>`.

## I.3 Rekomendasi

### I.3.1 Simpan asal-usul identitas (prioritas utama)

```
Contact.ReviewerIdSource VARCHAR(16) NULL   -- 'profile' | 'name' | 'anonymous'
```

Aturan pemakaian:

- Fitur yang **menyatakan orang yang sama** — "ulasan ke-N dari reviewer ini", riwayat reviewer — **hanya boleh memakai `profile`**
- `name` diperlakukan sebagai Contact biasa, tanpa klaim identitas
- Tidak ada data lama yang perlu dipindahkan; kolom diisi maju ke depan lalu di-backfill

Ini menutup bahaya di I.2 **tanpa** memutus Contact yang sudah terbentuk.

### I.3.2 Jangan ganti skema hash-nya

Godaan merapikan jadi `BINARY(16)` sebaiknya ditolak:

- `'voc-reviewer:' + 64 hex` ≈ 76 karakter memang lebih boros daripada 16 byte
- Tapi mengubahnya berarti memigrasi **seluruh** Contact reviewer yang ada, dan satu langkah salah memutus riwayat
- Bebannya tidak pernah jadi hambatan nyata: pencariannya selalu `WHERE SiteId = ? AND GbusinessId = ?` — satu baris, lewat indeks

Hemat 60 byte per Contact tidak sebanding dengan risiko memutus jejak.

### I.3.3 Soal pepper

Hash saat ini tanpa pepper. Untuk sumber `profile` ini **dapat diterima**: masukannya URL publik, dan nilainya tidak dipakai sebagai rahasia.

Satu hal yang perlu disadari: `GbusinessId` ikut keluar di payload webhook (`WebhookService.php`). Selama webhook hanya menuju sistem pelanggan sendiri, ini wajar. Kalau suatu saat ada webhook ke pihak ketiga, tinjau ulang.

## I.4 Jejak maker

| Aksi | Jejak yang tersimpan | Lokasi |
|---|---|---|
| Draft balasan | `reply_draft.maker`, `.at` | `VocController::reviewManageAction()` |
| Eskalasi ke PIC | `escalations[].by`, `.by_name`, `.at`, `.status`, `.message_id` | `VocController::reviewForwardAction()` |
| Ubah urgensi / kategori / status | hanya log aktivitas umum | — |

Sudah ada untuk dua aksi, tapi namanya berbeda-beda (`maker` vs `by`) dan aksi lain belum punya.

**Bentuk seragam yang diusulkan:**

```json
{
  "action": "reply_draft | escalate | urgency | category | status | note",
  "maker_id": "<UserId OneBox>",
  "maker_name": "<nama saat itu>",
  "at": "YYYY-MM-DD HH:MM:SS"
}
```

- `reply_draft.maker` → `maker_id`; **tetap baca kunci lama** supaya data yang ada tidak jadi yatim
- `escalations[].by` → `maker_id`, `.by_name` → `maker_name`
- `maker_name` disimpan ikut, bukan cuma id: kalau orangnya keluar dan barisnya terhapus, jejaknya tetap terbaca

---

# BAGIAN II — Dua Jalur Pengambilan Review

## II.1 Jalur resmi — Google Business Profile API

```
GET https://mybusiness.googleapis.com/v4/accounts/{accountId}/locations/{locationId}/reviews
PUT https://mybusiness.googleapis.com/v4/accounts/{accountId}/locations/{locationId}/reviews/{reviewId}/reply
```

> **Wajib diverifikasi ulang sebelum eksekusi.** Google memecah Business Profile API menjadi beberapa layanan, tetapi *reviews* tertinggal di endpoint v4. Bentuk persisnya harus dicek ke dokumentasi terbaru saat implementasi dimulai.

Yang dikembalikan per review:

| Field | Catatan |
|---|---|
| `reviewId` | **Identitas ulasan milik Google.** Kunci terpenting untuk dokumen ini. |
| `reviewer.displayName` | Nama tampilan |
| `reviewer.profilePhotoUrl` | Foto profil |
| `reviewer.isAnonymous` | Kalau `true`, nama pun tidak ada |
| `starRating` | Enum `ONE`…`FIVE`, bukan angka |
| `comment` | Teks ulasan |
| `createTime`, `updateTime` | Waktu resmi, bukan hasil parsing |
| `reviewReply.comment` | **Balasan pemilik beserta waktunya** |

**Syaratnya berat, dan ini penentu jadwal:**

1. Project Google Cloud + OAuth 2.0, scope `https://www.googleapis.com/auth/business.manage`
2. **Kuota awal nol.** Akses harus diajukan lewat formulir Google dan menunggu persetujuan — antreannya bisa berminggu-minggu
3. Token OAuth per akun Google yang **mengelola** lokasi, lengkap dengan refresh token
4. Hanya untuk lokasi yang benar-benar kita kelola dan terverifikasi

**Perhatikan:** API resmi **tidak memberi identitas reviewer**. `reviewId` adalah identitas ulasan, bukan penulis. Dua ulasan dari orang yang sama tidak punya field penghubung apa pun.

## II.2 Jalur crawler — yang berjalan hari ini

`VocProvider` (ProviderId `\Provider::VOC`, MediaId `GBUSINESS`) menarik dari herminaCrawler.

**Kelebihannya justru pada hal yang mustahil bagi jalur resmi:**

- **Kompetitor.** API resmi hanya melayani lokasi milik sendiri. Seluruh modul Kompetitor mustahil tanpa crawler.
- **Lokasi yang belum kita kelola.** Cabang baru, atau yang akun Google-nya dipegang pihak lain.
- **Identitas reviewer.** URL profil kontributor hanya ada di hasil goresan.
- **Tanpa menunggu persetujuan Google.**

**Kekurangannya nyata:**

- `review_hash` tidak stabil — akar penyebabnya ditemukan, lihat [BAGIAN IV](#bagian-iv--temuan-dari-repo-crawler)
- Waktu ulasan hasil parsing teks relatif, bukan timestamp resmi
- Rapuh terhadap perubahan tata letak Google
- Balasan pemilik sering terambil teksnya tanpa waktunya

## II.3 Kesimpulan: berdampingan permanen, bukan menggantikan

| Peran | Pemilik |
|---|---|
| Sumber kebenaran untuk cabang ber-OAuth | **GBP API** |
| Kompetitor | **Crawler** (selamanya) |
| Cabang tanpa OAuth | **Crawler** |
| Mengirim balasan | **GBP API** (satu-satunya yang sah) |
| Identitas reviewer | **Crawler** — walau cabangnya sudah ber-OAuth |

Baris terakhir berarti kedua jalur tetap berjalan bersamaan pada cabang yang sama. Itu bukan pemborosan — keduanya menyumbang hal berbeda. Tapi justru karena itu, dedup lintas sumber jadi **wajib**.

## II.4 `GoogleBusinessProvider.php` adalah stub mati

Berkas `app/services/Provider/GoogleBusinessProvider.php` (452 baris, `ProviderId = PVD21`) **bukan** integrasi Google Business.

Ia salinan mentah provider Bukalapak:

- `$this->log = \Library\Logger::get('Bukalapak');`
- Komentar header: `// MediaId = BKL`
- Contoh payload berisi `bukalapak.com` dan teks pemblokiran lapak
- **Nol** panggilan ke `googleapis.com`

Siapa pun yang mulai mengerjakan ini akan mengira sudah ada fondasi. Tidak ada.

> **Rekomendasi:** hapus atau ganti nama menjadi jelas-jelas stub, sebelum ada yang membangun di atasnya.

## II.5 `is_official` hari ini adalah jalan buntu

Nilainya hanya bisa disetel lewat POST:

```php
$opts['is_official'] = $this->request->hasPost('is_official')
    ? ((int) $this->request->getPost('is_official', 'int', 0) === 1)
    : (isset($opts['is_official']) ? (bool) $opts['is_official'] : false);
```

**Tidak ada satu pun view yang mengirim field itu.** Penyapuan seluruh `app/views` tidak menemukan `is_official` di mana pun.

Akibatnya pada pemakaian normal:

1. Nilainya tidak pernah berubah dari `false`
2. Setiap lokasi selamanya non-official
3. Tombol Balas **permanen mati** di seluruh site
4. Setiap baris di Kelola Review menampilkan penanda "kepemilikan akun belum ditandai"

Jadi fitur ini bukan "belum dipakai" — ia **tidak bisa dipakai**. Menurunkannya dari token OAuth tidak menghilangkan apa pun yang sedang berjalan.

**Konsekuensi praktis:** tidak perlu memikirkan migrasi data `is_official`. Nilainya seragam `false` di mana-mana.

---

# BAGIAN III — Rencana Implementasi

## III.1 Bahaya terbesar

Kalau jalur resmi dinyalakan begitu saja, tiap ulasan pada cabang ber-OAuth masuk **dua kali**. Bukan kekhawatiran teoretis — penggandaan 16% pernah terjadi di modul ini karena sebab serupa.

Karena itu rencananya memakai **mode bayangan**: jalur resmi ditarik dan dibandingkan lebih dulu **tanpa menulis satu pun Message**, sampai terbukti pencocokannya benar.

## III.2 Jembatannya sudah ada

`external_review_id` dari crawler dan `reviewId` dari API **seharusnya nilai yang sama** — keduanya id ulasan milik Google. Nilai ini sudah disimpan dan sudah dipakai `VocProvider::sudahPernahMasuk()` sebagai penjaga dedup kedua.

> **Asumsi ini wajib dibuktikan di Fase 0.** Jangan ada baris kode ditulis sebelum satu `reviewId` dari API terbukti sama persis dengan satu `external_review_id` di basis data kita.

Catatan penting: **`RemoteId` tidak boleh sekadar ditukar.** Komentar di `VocProvider` sudah memperingatkan — menukarnya membuat seluruh review lama tidak dikenali, dan penarikan berikutnya menggandakan semuanya sekali lagi. Solusinya menambah lapisan pencocokan, bukan mengganti kunci.

## III.3 Perubahan model data

### Penanda sumber

```
MessageContent.Meta.review_source   -- 'gbp_api' | 'crawler'
MessageContent.Meta.gbp_review_id   -- reviewId dari API, saat tersedia
```

Meta dipilih, bukan kolom baru, karena `MessageContent` dipakai seluruh media di OneBox.

### Indeks pencocokan lintas sumber

**Pilihan A — tabel pemetaan (disarankan)**

```sql
CREATE TABLE VocReviewIndex (
  SiteId          INT           NOT NULL,
  GoogleReviewId  VARCHAR(255)  NOT NULL,
  MessageId       BIGINT        NOT NULL,
  Source          VARCHAR(16)   NOT NULL,
  CreateDate      DATETIME      NOT NULL,
  PRIMARY KEY (SiteId, GoogleReviewId),
  KEY idx_message (MessageId)
);
```

**Pilihan B — kolom generated pada `MessageContent`**

```sql
ALTER TABLE MessageContent
  ADD COLUMN GoogleReviewId VARCHAR(255)
    GENERATED ALWAYS AS (JSON_UNQUOTE(JSON_EXTRACT(Meta,'$.external_review_id'))) STORED,
  ADD INDEX idx_google_review (GoogleReviewId);
```

Lebih ringkas dan mengisi dirinya sendiri, **tetapi** `STORED` memaksa penulisan ulang seluruh `MessageContent` — tabel terbesar dan paling panas, dipakai semua media. Untuk kebutuhan yang hanya menyangkut VoC, ongkosnya tidak sepadan.

### Mode autentikasi per koneksi

```
Connection.Options.auth_mode      -- 'oauth' | 'crawler'
Connection.Options.gbp_account_id
Connection.Options.gbp_location_id
```

Refresh token **tidak disimpan di `Options`** — lihat III.6.

## III.4 Percabangan

```
                    tarik review untuk sebuah Connection
                                   │
                    auth_mode == 'oauth' && token sah?
                          ┌────────┴────────┐
                         ya                tidak
                          │                  │
                   GBP API reader      crawler reader
                          │                  │
                          └────────┬─────────┘
                                   │
                    cari VocReviewIndex(SiteId, GoogleReviewId)
                          ┌────────┴────────┐
                     ketemu              tidak ketemu
                          │                  │
                   perbarui baris        buat Message baru
                    yang sudah ada       + catat di index
```

### Dua pertanyaan berbeda yang gampang tertukar

Keputusan produk: **official = lewat Google Business API (ada token). Non-official = hasil Selenium, tanpa login.** Itu benar, tapi satu pembedaan harus tetap dijaga:

| Pertanyaan | Melekat pada | Menentukan |
|---|---|---|
| "Cabang ini bisa dibalas?" | **Connection** — punya token sah? | Tombol Balas hidup/mati |
| "Baris ini datangnya dari mana?" | **Meta review** — `gbp_api` / `crawler` | Penanda "Terverifikasi Google" |

Biasanya sejalan, **tetapi tidak selalu.** Cabang yang baru tersambung OAuth hari ini tetap punya ratusan baris lama hasil Selenium. Baris itu asalnya goresan, tapi cabangnya sekarang **memang** bisa dibalas.

Kalau dipaksa jadi satu field, salah satu pasti keliru:

- pakai asal data → tombol Balas mati pada ulasan yang sebenarnya bisa dibalas
- pakai status cabang → baris hasil goresan ikut mengaku "Terverifikasi Google"

Dua field itu murah, dan menghindari kedua kesalahan itu.

### Siapa berwenang atas field apa

| Field | Berwenang | Alasan |
|---|---|---|
| `starRating`, teks, `createTime` | **GBP API** | Resmi, bukan hasil parsing |
| `reviewReply` + waktunya | **GBP API** | Crawler kerap kehilangan waktunya |
| `reviewer_profile_url` | **Crawler** | API tidak punya identitas reviewer |
| `reviewer_local_guide_level`, `reviewer_total_reviews` | **Crawler** | Tidak ada di API |
| Hasil analisa AI, urgensi, tiket | **OneBox** | Milik kita, jangan pernah ditimpa ingest |

Baris terakhir kritis: penarikan ulang **tidak boleh** menghapus label AI, urgensi, kategori manual, atau draft balasan.

## III.5 Fase

### Fase 0 — Pembuktian (gerbang, wajib)

Belum ada kode produksi.

1. Tarik reviews satu lokasi yang kita kelola lewat API secara manual
2. Bandingkan `reviewId` dengan `Meta.external_review_id`
3. Hitung sebarannya (lihat [Lampiran](#lampiran--query-verifikasi))

**Gerbang:** kalau `reviewId` bukan nilai yang sama dengan `external_review_id`, hentikan — seluruh rencana berdiri di atas asumsi itu.

Paralel, jalur kritis administratif: **ajukan akses Business Profile API sekarang.**

### Fase 1 — Penanda sumber + indeks (tanpa perubahan perilaku)

- Buat `VocReviewIndex` lewat migrasi Phalcon
- Isi `Meta.review_source = 'crawler'` pada ingest sekarang
- Backfill index dari data yang ada
- Bersihkan `GoogleBusinessProvider.php` (II.4)

### Fase 2 — Plumbing OAuth

- Simpan kredensial + refresh token di luar `Options`
- Alur consent per cabang di layar Kelola Lokasi
- Penyegaran token dan penanganan kedaluwarsa
- Belum ada review yang ditarik

### Fase 3 — Pembaca GBP dalam mode bayangan

- Reader menarik dari API tetapi **tidak menulis Message sama sekali**
- Hasilnya ke log perbandingan: berapa cocok dengan index, berapa tidak
- Minimal satu siklus penuh pada cabang percontohan

**Gerbang:** kecocokan harus mendekati 100%. Fase inilah yang mencegah bencana penggandaan.

### Fase 4 — Nyalakan + tampilkan pembedanya

- Reader GBP mulai menulis, melalui `VocReviewIndex`
- Field digabung menurut III.4

Soal tampilan, ikuti prinsip yang sudah dipakai di halaman itu — **yang lumrah diam, yang menyimpang bersuara.** Jangan tempelkan lencana "Crawler" pada setiap baris. Tandai hanya yang bermakna tindakan:

> **Terverifikasi Google** — hanya pada review bersumber `gbp_api`, karena hanya itu yang bisa dibalas dari OneBox.

### Fase 5 — Kirim balasan

- `reviews.updateReply` lewat API
- Hanya untuk review bersumber `gbp_api`
- Draft balasan yang tersimpan hari ini jadi masukannya — akhirnya kata "draft" bisa berubah jadi "terkirim" dengan jujur

### Fase 6 — `is_official` menjadi kenyataan

- Diturunkan dari "punya token OAuth yang sah untuk lokasi ini"
- Tidak perlu masa transisi (lihat II.5 — semuanya `false`)
- Jalur POST `is_official` lama dihapus, supaya tidak ada dua sumber kebenaran

## III.6 Status koneksi di layar Kelola Lokasi

Inilah wujud "tokennya ditampilkan di OneBox". Yang ditampilkan **status**, bukan tokennya:

| Yang tampil | Contoh |
|---|---|
| Keadaan sambungan | `Tersambung` / `Belum tersambung` / `Token kedaluwarsa` |
| Akun Google pengelola | `humas.depok@…` |
| Sinkron terakhir | `21 Agu 2026, 09:14` |
| Aksi | `Sambungkan` / `Sambungkan ulang` / `Putuskan` |

**Aturan tegas:** token dan refresh token tidak pernah dirender ke halaman, tidak pernah masuk response JSON, dan tidak disimpan di `Connection.Options`.

Alasannya bukan kehati-hatian abstrak. `Options` pernah terkirim utuh ke browser, dan sejak itu query di `VocController` sengaja hanya mengambil satu kunci:

```sql
-- HANYA satu kunci yang diambil, bukan conn.Options utuh: Options memuat
-- service_token, dan seluruh isi baris ini berakhir di browser.
JSON_UNQUOTE(JSON_EXTRACT(conn.Options,'$.is_official')) AS ConnOfficial
```

Menaruh refresh token Google di tempat yang sama = mengulang persis kesalahan yang sudah ditambal.

Keadaan "Token kedaluwarsa" harus **terlihat**, bukan gagal diam-diam. Cabang yang berhenti tersinkron tanpa suara adalah cara paling halus untuk kehilangan data berminggu-minggu.

## III.7 Risiko

| Risiko | Dampak | Penanganan |
|---|---|---|
| `reviewId` ≠ `external_review_id` | Rencana batal | Fase 0 sebagai gerbang |
| Akses API tidak disetujui Google | Fase 2–6 mati | Ajukan di hari pertama; crawler tetap jalan |
| Penggandaan saat penyalaan | Layar kotor, angka salah | Mode bayangan Fase 3 |
| Ingest menimpa hasil analisa | Kerja humas hilang | Aturan kewenangan III.4 |
| Refresh token kedaluwarsa diam-diam | Cabang berhenti sinkron tanpa suara | Pantau umur token, tampilkan di layar |
| Token bocor lewat `Options` | Kebocoran kredensial | Disimpan terpisah sejak awal (III.6) |
| Kuota API habis | Penarikan gagal sebagian | Mundur ke crawler untuk siklus itu, catat |
| Salah gabung dua orang | Data menyesatkan | Larangan hash-nama (I.3.1) |

## III.8 Penggulingan dan cara mundur

| Fase | Bisa digulirkan sendiri? | Cara mundur |
|---|---|---|
| 1 | Ya | Drop tabel index; Meta tambahan diabaikan |
| 2 | Ya | Matikan alur consent |
| 3 | Ya | Matikan reader bayangan |
| 4 | **Tidak** — butuh Fase 3 lulus | Kembalikan `auth_mode` ke `crawler` |
| 5 | Ya | Sembunyikan tombol kirim |
| 6 | Ya | Kembalikan ke flag manual |

Fase 4 satu-satunya yang tidak punya jalan mundur murah begitu Message terlanjur tertulis. Karena itu Fase 3 tidak boleh dipercepat.

## III.9 Perkiraan

| Pekerjaan | Perkiraan |
|---|---|
| **Identitas reviewer** (I.3) | |
| Ukur sebaran sumber identitas | 0.5 hari |
| Kolom `ReviewerIdSource` + isi saat ingest | 0.5 hari |
| Seragamkan `maker_id` / `maker_name` | 1 hari |
| Tampilkan riwayat reviewer (hanya `profile`) | 1 hari |
| Backfill `ReviewerIdSource` | 0.5 hari |
| **Dua jalur review** (III.5) | |
| Fase 0 — pembuktian | 1 hari |
| Fase 1 — penanda + indeks | 1 hari |
| Fase 2 — OAuth | 2–3 hari |
| Fase 3 — mode bayangan | 1 hari + observasi |
| Fase 4 — nyalakan | 2 hari |
| Fase 5 — kirim balasan | 1–2 hari |
| Fase 6 — official | 0.5 hari |

Kerja kodenya ±12,5 hari. **Jadwal sebenarnya ditentukan persetujuan Google, bukan angka di atas.**

---

# BAGIAN IV — Temuan dari Repo Crawler

Bagian ini disusun setelah repo `herminaCrawler` diperiksa langsung. Isinya membuktikan dua klaim di atas dan menemukan satu bug yang belum pernah dicatat.

## IV.1 Terbukti: contributor URL memang yang diincar

`app/integrations/google_maps_selectors.py:54`

```python
"a[href*='/maps/contrib/']",
```

Selector Selenium secara eksplisit mengincar tautan kontributor. Ini mengonfirmasi bahwa `reviewer_profile_url` memang memuat contributor id Google — dasar identitas di BAGIAN I bukan dugaan.

Field-nya juga nyata di model (`app/db/models.py:339` dan `:540`, dua tabel):

```python
external_review_id: Mapped[str | None] = mapped_column(String(255))
reviewer_name: Mapped[str | None] = mapped_column(String(255))
reviewer_profile_url: Mapped[str | None] = mapped_column(Text)
reviewer_photo_url: Mapped[str | None] = mapped_column(Text)
reviewer_local_guide_level: Mapped[str | None] = mapped_column(String(100))
reviewer_total_reviews: Mapped[int | None] = mapped_column(Integer)
```

## IV.2 Akar penggandaan 16% — ditemukan

`app/utils/hashing.py` punya **dua** fungsi hash:

```python
def generate_review_hash(review: dict) -> str:          # jalur Apify
    hash_input = "|".join([
        str(review.get("source") or ""),
        str(review.get("external_place_id") or ""),
        str(review.get("external_review_id") or ""),     # ← stabil
        str(review.get("reviewer_name") or ""),
        str(review.get("rating") or ""),
        str(review.get("review_text") or ""),
        str(review.get("review_time") or ""),
    ])
    return sha256(hash_input.encode("utf-8")).hexdigest()


def generate_selenium_review_hash(review: dict) -> str:  # jalur Selenium
    hash_input = "|".join([
        str(review.get("source") or ""),
        str(review.get("location_id") or ""),
        str(review.get("reviewer_name") or ""),
        str(review.get("rating") or ""),
        str(review.get("review_text") or ""),
        str(review.get("review_relative_time") or ""),   # ← BERUBAH SEIRING WAKTU
        str(review.get("reviewer_profile_url") or ""),
    ])
    return sha256(hash_input.encode("utf-8")).hexdigest()
```

**Inilah sebabnya.** `review_relative_time` adalah teks relatif Google — "3 bulan lalu", "setahun lalu". Nilainya **berubah sendiri seiring waktu**.

Ulasan yang sama:

| Kapan di-scrape | `review_relative_time` | Hash |
|---|---|---|
| Juni | `"2 bulan lalu"` | `32dbb525…` |
| Agustus | `"4 bulan lalu"` | `5c6faf51…` |

Hash berbeda → dianggap ulasan baru → masuk lagi. Persis pola yang dicatat `VocProvider`: `review_hash` berbeda, `voc_review_id` 87 dan 137, sementara `external_review_id`, teks, dan bintangnya identik.

Lebih menohok lagi: **`generate_selenium_review_hash` tidak memakai `external_review_id` sama sekali**, padahal nilainya tersedia — ditangkap di `selenium_google_maps_client.py:443` dan diteruskan di `fetch_service.py:138`.

### Rekomendasi

Ganti `review_relative_time` dengan `external_review_id` pada `generate_selenium_review_hash`:

```python
def generate_selenium_review_hash(review: dict) -> str:
    hash_input = "|".join([
        str(review.get("source") or ""),
        str(review.get("location_id") or ""),
        str(review.get("external_review_id") or ""),     # ganti relative_time
        str(review.get("reviewer_name") or ""),
        str(review.get("rating") or ""),
        str(review.get("review_text") or ""),
        str(review.get("reviewer_profile_url") or ""),
    ])
    return sha256(hash_input.encode("utf-8")).hexdigest()
```

**Peringatan penting:** perubahan ini membuat **seluruh hash lama berubah**, sehingga penarikan berikutnya akan menganggap semua ulasan sebagai baru dan menggandakan sekali lagi. Jadi harus dibarengi:

1. Backfill hash untuk baris yang sudah ada, **atau**
2. Penjaga dedup berbasis `external_review_id` dijalankan lebih dulu di kedua sisi (OneBox sudah punya lewat `sudahPernahMasuk()`)

Jangan digulirkan sendirian tanpa salah satu dari dua langkah itu.

### Kaitannya dengan BAGIAN III

Kalau perbaikan ini dijalankan, `review_hash` menjadi stabil dan `VocReviewIndex` (III.3) jadi jauh lebih sederhana — karena `RemoteId` sendiri sudah bisa dipercaya. Tapi indeksnya tetap dibutuhkan untuk menjembatani dua sumber yang berbeda kunci.

---

## Lampiran — Query Verifikasi

Belum bisa dijalankan saat dokumen ini ditulis: DB lokal tidak terjangkau dari kontainer (`host.docker.internal` ditolak).

### Sebaran identitas reviewer

```sql
SELECT
  COUNT(*)                                                     AS total_review,
  SUM(JSON_EXTRACT(Meta,'$.reviewer_profile_url') IS NOT NULL) AS punya_profile_url
FROM MessageContent
WHERE JSON_VALID(Meta);
```

### Contact yang mencurigakan (indikasi masalah I.2)

```sql
SELECT ct.Id, ct.Name, COUNT(*) AS jumlah
FROM Contact ct
JOIN MessageUser mu ON mu.ContactId = ct.Id
WHERE ct.GbusinessId LIKE 'voc-reviewer:%'
GROUP BY ct.Id
HAVING jumlah > 5
ORDER BY jumlah DESC
LIMIT 20;
```

Contact bernama umum dengan puluhan ulasan lintas cabang hampir pasti gabungan beberapa orang.

### Kesiapan jembatan dua sumber (gerbang Fase 0)

```sql
SELECT
  COUNT(*)                                                     AS total,
  SUM(JSON_EXTRACT(Meta,'$.external_review_id') IS NOT NULL)   AS punya_ext_id
FROM MessageContent
WHERE JSON_VALID(Meta);
```

### Deteksi penggandaan yang tersisa (masalah IV.2)

```sql
SELECT JSON_UNQUOTE(JSON_EXTRACT(mc.Meta,'$.external_review_id')) AS ext_id,
       COUNT(*) AS salinan
FROM Message m
JOIN MessageContent mc ON mc.Id = m.Id
WHERE JSON_VALID(mc.Meta)
  AND JSON_EXTRACT(mc.Meta,'$.external_review_id') IS NOT NULL
GROUP BY ext_id
HAVING salinan > 1
ORDER BY salinan DESC
LIMIT 30;
```

---

## Pertanyaan untuk PM

1. **Ajukan akses Business Profile API sekarang atau tunda?** Ini menentukan seluruh jadwal BAGIAN III.
2. Siapa pemilik akun Google tiap cabang, dan bersediakah mereka menjalankan consent?
3. Setuju crawler tetap jalan **berdampingan** pada cabang ber-OAuth, demi identitas reviewer?
4. Setuju penanda "Terverifikasi Google" hanya muncul pada review bersumber API, bukan pada semua baris?
5. Setuju membatasi fitur "riwayat reviewer" hanya pada identitas bersumber `profile`? Konsekuensinya sebagian reviewer tidak akan pernah punya riwayat — dan itu memang lebih jujur.
6. Apakah menyimpan identitas reviewer sudah ditinjau dari sisi data pribadi? Nilainya turunan dari akun Google seseorang.
7. Perbaikan hash Selenium (IV.2) mau digulirkan terpisah atau sekalian dengan Fase 1?

---

## Catatan Revisi

- Versi pertama dokumen identitas reviewer menyimpulkan fiturnya **belum ada**. Itu keliru — penyapuan awal hanya mencakup `VocController`, sementara implementasinya di `VocProvider`. Dikoreksi setelah `buildReviewerIdentity()` ditemukan.
- BAGIAN IV ditambahkan setelah repo `herminaCrawler` diperiksa langsung, yang membuktikan klaim contributor URL dan menemukan akar penyebab penggandaan yang sebelumnya hanya diketahui gejalanya.
