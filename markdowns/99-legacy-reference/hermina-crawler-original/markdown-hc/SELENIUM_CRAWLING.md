# Selenium Crawling — Dokumentasi Teknis

Dokumen ini menjelaskan cara kerja modul crawling review Google Maps berbasis Selenium yang dipakai di project ini, beserta kelebihan, kekurangan, risiko, dan dampaknya. Ditulis berdasarkan kode aktual, bukan template umum.

**File terkait:**

| File | Peran |
|---|---|
| `app/integrations/selenium_google_maps_client.py` | Driver Chrome, buka halaman, scroll, ekstraksi tiap kartu review |
| `app/services/selenium_fetch_service.py` | Orkestrasi: ambil → normalisasi → filter tanggal → simpan + logging |
| `app/integrations/google_maps_selectors.py` | Daftar CSS/XPath selector (titik paling rapuh) |
| `app/config.py` | Parameter runtime (`SELENIUM_*`) |
| `app/utils/hashing.py` | Deduplikasi review |

---

## 1. Kenapa Selenium, bukan API

Google **tidak menyediakan API publik untuk membaca review** sebuah tempat. Google Places API hanya mengembalikan maksimal 5 review dan tidak bisa dipaginasi. Karena kebutuhannya menarik puluhan sampai ratusan review per lokasi, satu-satunya jalan adalah **mengotomasi browser sungguhan** yang membuka halaman Google Maps seperti manusia, lalu membaca DOM-nya.

Itu keputusan yang memaksa banyak trade-off di bawah — bukan pilihan gaya, tapi konsekuensi dari tidak adanya API.

---

## 2. Cara Kerja (alur aktual)

```
fetch_location(location_id, target)
        │
        ▼
SeleniumGoogleMapsReviewClient.fetch_reviews(location, limit)
  1. Resolve URL   → google_reviews_url / google_maps_url / bikin dari place_id
  2. Validate URL  → wajib http(s), host google.*, path mengandung /maps
  3. Buka Chrome   → headless atau tampil, lokal id-ID, 1440×1000
  4. driver.get(url)
  5. Terima consent "Terima semua / Accept all" bila muncul
  6. Tunggu kartu review muncul (atau klik tombol buka panel review)
  7. Temukan scroll container
  8. Urutkan "Terbaru / Newest" bila opsinya ada
  9. LOOP scroll:
        - baca semua kartu yang terlihat
        - klik "Selengkapnya" agar teks penuh
        - ekstraksi field → dedup in-memory
        - scroll container ke bawah
        - berhenti bila: target tercapai / mentok scroll / tidak ada kartu baru
 10. driver.quit()  (selalu, di finally)
        │
        ▼
Per review: normalize → filter rentang tanggal → insert_review() (dedup by hash)
        │
        ▼
FetchLog dicatat (status, jumlah, metadata) — sukses / partial / gagal
```

### Kondisi berhenti loop (penting untuk dipahami)

Loop di `_collect_reviews` berhenti pada **salah satu** dari tiga hal, dan `stopped_reason` dicatat ke log:

| `stopped_reason` | Artinya |
|---|---|
| `target_reached` | Jumlah target terpenuhi — hasil ideal |
| `no_new_review_cards` | 5 kali scroll berturut tanpa kartu baru → dianggap sudah mentok |
| `max_scroll_attempts` | Batas scroll (default 100) tercapai duluan |

Dua yang terakhir berarti **hasil lebih sedikit dari target** dan status jadi `partial_success`. Ini normal, bukan bug — Google memang tidak selalu memuat semua review.

---

## 3. Parameter Konfigurasi

Semua lewat environment variable (lihat `.env.example`). Nilai default dari `app/config.py`:

| Variable | Default | Fungsi | Catatan |
|---|---|---|---|
| `SELENIUM_HEADLESS` | `false` | Jalan tanpa jendela browser | Non-headless lebih jarang kena "limited view" |
| `SELENIUM_DEFAULT_TARGET_REVIEWS` | `100` | Target review default per lokasi | |
| `SELENIUM_MAX_TARGET_REVIEWS` | `300` | Batas atas target | **Di-hard-cap 300** di kode, apa pun isinya |
| `SELENIUM_SCROLL_DELAY_SECONDS` | `2` | Jeda antar scroll | **Minimal dipaksa 2 detik** — jangan diturunkan |
| `SELENIUM_MAX_SCROLL_ATTEMPTS` | `100` | Batas jumlah scroll | Di-clamp ke rentang 1–100 |
| `SELENIUM_WAIT_TIMEOUT_SECONDS` | `20` | Timeout tunggu elemen muncul | |
| `SELENIUM_USER_DATA_DIR` | `.selenium-profile` | Folder profil Chrome | Menyimpan sesi login manual |

> Batas `target` efektif = `min(request, SELENIUM_MAX_TARGET_REVIEWS, 300, kuota company)`. Jadi walau minta 1000, tidak akan pernah melebihi 300 atau kuota entitlement company.

---

## 4. Deduplikasi

Ada **dua lapis**, karena Google Maps tidak selalu memberi ID review yang stabil:

1. **In-memory saat crawling** (`_collect_reviews`) — kartu yang sama tidak diproses dua kali dalam satu sesi, memakai gabungan `external_review_id | reviewer_name | rating | text | relative_time`.
2. **Persisten saat simpan** (`generate_selenium_review_hash`) — hash SHA-256 dari `source | location_id | reviewer_name | rating | text | relative_time | profile_url`. Review dengan hash sama tidak diinsert ulang antar-sesi (dihitung sebagai `duplicate`).

> ⚠️ **Keterbatasan yang harus disadari:** dedup memakai `review_relative_time` ("2 minggu lalu"), **bukan timestamp absolut** — karena Google Maps tidak mengekspos tanggal pasti di DOM. Konsekuensinya, review yang sama bisa dianggap "baru" saat teks relatifnya berubah ("2 minggu lalu" → "1 bulan lalu"). Ini sumber duplikat semu yang paling mungkin terjadi.

---

## 5. Kelebihan (Pros)

| Kelebihan | Penjelasan |
|---|---|
| **Satu-satunya cara ambil review massal** | Google tidak punya API untuk ini; Selenium membuka akses yang secara resmi tertutup. |
| **Melihat apa yang user lihat** | Karena browser sungguhan, konten yang dirender JavaScript (review dinamis) ikut terbaca — tidak bisa dilakukan HTTP request biasa. |
| **Tahan banting terhadap variasi layout** | Selector disimpan sebagai daftar (`*_SELECTORS`) dan dicoba satu per satu, plus fallback cari scroll container via JavaScript. Satu selector mati tidak langtsung mematikan seluruh crawl. |
| **Bilingual** | Menangani UI Indonesia dan Inggris ("Terbaru"/"Newest", "Terima semua"/"Accept all", "Selengkapnya"/"More"). |
| **Gagal dengan sopan** | `driver.quit()` selalu jalan di `finally`; error dibungkus jadi `ReviewSourceError` dengan pesan actionable; kartu yang gagal diekstrak dihitung terpisah (`failed_review_cards`) tanpa menghentikan sisanya. |
| **Sesi login bisa dipersisten** | `SELENIUM_USER_DATA_DIR` memungkinkan login manual sekali, lalu dipakai ulang — mengurangi "limited view". |
| **Observability** | Setiap fetch tercatat di `FetchLog`: target, jumlah loaded/scraped/failed, `scroll_attempts`, `stopped_reason`, URL final. |

---

## 6. Kekurangan (Cons)

| Kekurangan | Penjelasan |
|---|---|
| **Rapuh terhadap perubahan Google** | Class CSS Google digenerate acak dan bisa berubah kapan saja tanpa pemberitahuan. Saat itu terjadi, `google_maps_selectors.py` harus diperbarui manual — dan crawl akan gagal total sampai itu dilakukan. **Ini utang perawatan yang permanen.** |
| **Lambat** | Ada `time.sleep` di banyak titik (min 2 detik per scroll). Menarik 300 review bisa memakan **beberapa menit per lokasi**. Tidak cocok untuk request sinkron/real-time. |
| **Boros resource** | Tiap fetch menjalankan instance Chrome penuh (RAM ratusan MB). Menjalankan banyak lokasi paralel bisa membebani server. |
| **Butuh Chrome + ChromeDriver** | Dependency di luar Python. Versi Chrome dan ChromeDriver harus cocok; di server headless perlu setup tambahan. |
| **Tanggal tidak presisi** | Hanya waktu relatif ("2 minggu lalu") yang tersedia; `review_time` diisi `None` di ekstraksi. Filter tanggal jadi kurang akurat dan dedup jadi rentan (lihat §4). |
| **Tidak deterministik** | Hasil tergantung apa yang Google putuskan untuk memuat saat itu. Dua run bisa memberi jumlah berbeda. |
| **Login tidak diotomasi (sengaja)** | Kalau kena "limited view", butuh intervensi manual login sekali. Tidak ada bypass otomatis. |

---

## 7. Risiko dan Dampak

Diurut dari yang paling perlu diperhatikan.

### 7.1 Kepatuhan / Legal — **Dampak: Tinggi**

Scraping Google Maps **melanggar Google Terms of Service**. Ini bukan soal teknis, tapi soal risiko organisasi.

- **Dampak:** IP bisa diblokir; secara teori ada risiko tindakan hukum untuk skala besar/komersial; data review pihak ketiga menyangkut **PII** (nama, foto, URL profil reviewer) sehingga tunduk pada UU PDP.
- **Mitigasi:** batasi volume dan frekuensi; jangan mengekspos PII reviewer keluar sistem tanpa dasar; pastikan penggunaan internal/riset punya justifikasi; simpan `raw_payload` seaman data sensitif.
- **Catatan:** ini keputusan bisnis, bukan hanya keputusan engineering. Dokumentasikan siapa yang menyetujui penggunaan ini.

### 7.2 Kerapuhan Selector — **Dampak: Tinggi, Peluang: Sering**

Google mengubah struktur DOM-nya secara berkala.

- **Dampak:** crawl berhenti total; `stopped_reason` atau error di `FetchLog` akan menunjukkan "container not found" / "no reviews loaded". Semua lokasi gagal serentak.
- **Mitigasi:** pantau `FetchLog` untuk lonjakan status `failed`; siapkan proses cepat memperbarui `google_maps_selectors.py`; jalankan smoke test berkala pada satu lokasi.
- **Sinyal deteksi:** tiba-tiba banyak fetch `failed` dengan pesan "Review container was not found" atau "Google Maps layout may have changed".

### 7.3 Rate Limiting / Blokir IP — **Dampak: Sedang–Tinggi**

Terlalu banyak request dari satu IP memicu CAPTCHA atau "limited view".

- **Dampak:** fetch mengembalikan pesan "Google Maps is showing a limited view"; hasil kosong sampai diintervensi.
- **Mitigasi:** hormati `SELENIUM_SCROLL_DELAY_SECONDS` (jangan turunkan di bawah 2 dtk); beri jeda antar lokasi; hindari menjalankan semua lokasi sekaligus; gunakan profil login manual bila diblokir.

### 7.4 Kualitas Data — **Dampak: Sedang**

Ekstraksi berbasis heuristik teks bisa meleset.

- **Dampak:** rating salah parse, review terpotong bila "Selengkapnya" gagal diklik, duplikat semu karena waktu relatif berubah (§4), sebagian kartu masuk `failed_review_cards`.
- **Mitigasi:** monitor rasio `failed_review_cards` terhadap `loaded_review_cards` di `FetchLog`; validasi rating di rentang 1–5 (sudah ada CheckConstraint di DB); sadari `review_time` selalu `None` dari sumber ini.

### 7.5 Operasional / Resource — **Dampak: Sedang**

Chrome berat dan lambat.

- **Dampak:** server bisa kehabisan RAM bila banyak instance paralel; fetch lama menahan koneksi (ini juga alasan endpoint fetch **tidak boleh** dipanggil sinkron di balik proxy dengan timeout pendek — lihat catatan deployment).
- **Mitigasi:** jalankan fetch sebagai job background, bukan request sinkron; batasi konkurensi; pastikan `driver.quit()` selalu jalan (sudah, di `finally`) agar tidak ada Chrome zombie.

### 7.6 Ketergantungan Lingkungan — **Dampak: Sedang**

Butuh Chrome + ChromeDriver versi cocok.

- **Dampak:** setelah Chrome auto-update, ChromeDriver bisa tidak kompatibel → "Selenium browser failed to start".
- **Mitigasi:** pin versi Chrome/ChromeDriver di image Docker; sertakan health check; siapkan langkah update terkontrol.

---

## 8. Ringkasan Matriks Risiko

| Risiko | Peluang | Dampak | Prioritas |
|---|---|---|---|
| Melanggar ToS / legal / PII | Selalu berlaku | Tinggi | **Kelola di level kebijakan** |
| Selector berubah (crawl mati) | Sering | Tinggi | **Pantau aktif** |
| Blokir IP / limited view | Sedang | Sedang–Tinggi | Batasi laju |
| Kualitas data meleset | Sedang | Sedang | Monitor FetchLog |
| Resource / Chrome zombie | Rendah (sudah dimitigasi) | Sedang | Jalankan background |
| Chrome/Driver tak kompatibel | Rendah | Sedang | Pin versi |

---

## 9. Rekomendasi Penggunaan

**Lakukan:**
- Jalankan sebagai **job background**, bukan di jalur request sinkron.
- Batasi target wajar (default 100; maksimum keras 300).
- Beri jeda antar lokasi; pertahankan delay scroll ≥ 2 detik.
- Pantau `FetchLog` secara rutin untuk `stopped_reason` dan rasio `failed`.
- Perlakukan `raw_payload` dan PII reviewer sebagai data sensitif.

**Hindari:**
- Menjalankan semua lokasi paralel tanpa batas.
- Menurunkan delay demi kecepatan (memicu blokir).
- Mengandalkan `review_time` absolut dari sumber ini (selalu `None`).
- Mengekspos data review pihak ketiga keluar sistem tanpa dasar hukum.

**Rencana kontinjensi bila crawl mati serentak:** hampir pasti selector berubah → periksa `google_maps_selectors.py` terlebih dulu, bukan kode logika.
