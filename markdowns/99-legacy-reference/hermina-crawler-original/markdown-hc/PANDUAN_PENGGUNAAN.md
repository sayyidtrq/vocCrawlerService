# Panduan Penggunaan Review System

Dokumen ini menjelaskan cara menjalankan aplikasi dari awal dan menggunakan
setiap fitur yang tersedia.

## 1. Gambaran Alur

Alur penggunaan normal:

```text
Siapkan PostgreSQL dan .env
        ↓
Jalankan migrasi database
        ↓
Jalankan python main.py
        ↓
Tambahkan lokasi Hermina
        ↓
Lakukan dry run fetch
        ↓
Fetch dan simpan review
        ↓
Analisis review
        ↓
Lihat ringkasan
        ↓
Export data
```

Untuk penggunaan awal, gunakan mode mock:

```env
REVIEW_SOURCE_MODE=mock
GEMINI_MODE=mock
```

Mode mock tidak mengambil data asli dari Google. Aplikasi akan menghasilkan
10 review contoh untuk setiap lokasi agar seluruh alur dapat diuji.

---

## 2. Persiapan Pertama Kali

### 2.1 Persyaratan

Pastikan komputer sudah memiliki:

- Python 3.11 atau lebih baru
- PostgreSQL
- Database PostgreSQL bernama `hermina_reviews`

### 2.2 Buat virtual environment

Jalankan dari folder proyek:

```powershell
python -m venv venv
venv\Scripts\activate
```

### 2.3 Install dependency

```powershell
pip install -r requirements.txt
```

### 2.4 Siapkan `.env`

Jika `.env` belum ada:

```powershell
Copy-Item .env.example .env
```

Konfigurasi minimum:

```env
APP_ENV=local
APP_NAME=Review System
LOG_LEVEL=INFO
EXPORT_DIR=exports

DATABASE_URL=postgresql://postgres:password@localhost:5432/hermina_reviews

REVIEW_SOURCE_MODE=mock
GEMINI_MODE=mock

FETCH_LIMIT_PER_LOCATION=50
FETCH_TIMEOUT_SECONDS=30
FETCH_MAX_RETRY=3

ANALYSIS_BATCH_SIZE=20
PROMPT_VERSION=v1
PAGE_SIZE=20
SHOW_RAW_PAYLOAD=false
```

Ganti `password` dengan password PostgreSQL lokal.

Jika password mengandung spasi, ubah spasi menjadi `%20`. Contoh:

```text
Password asli : contoh password
Dalam URL     : contoh%20password
```

Jangan membagikan atau menyimpan `.env` ke Git.

### 2.5 Buat database

Contoh menggunakan command PostgreSQL:

```powershell
createdb -U postgres hermina_reviews
```

Database juga dapat dibuat melalui pgAdmin.

### 2.6 Jalankan migrasi

```powershell
python -m alembic upgrade head
```

Perintah ini membuat tabel:

- `locations`
- `reviews`
- `review_analysis`
- `fetch_logs`

---

## 3. Menjalankan Aplikasi

Jalankan:

```powershell
python main.py
```

Aplikasi akan menampilkan:

```text
Main Menu

1. Manage Hermina Locations
2. Fetch / Sync Reviews
3. View Review Data
4. Analyze Reviews with Gemini
5. View Analysis Summary
6. Export Data
7. View Fetch Logs
8. System Settings
0. Exit
```

Masukkan nomor menu lalu tekan Enter.

- Pilih `0` untuk kembali atau keluar.
- Setelah suatu proses selesai, tekan Enter untuk melanjutkan.
- Input menu yang salah tidak akan menghentikan aplikasi.

---

## 4. Flow Penggunaan Pertama

### Langkah 1 — Periksa database

1. Pilih `8. System Settings`.
2. Pilih `1. Check Database Connection`.
3. Pastikan muncul:

```text
Database connection: OK
```

Jika gagal, periksa PostgreSQL, nama database, username, password, port, dan
`DATABASE_URL` di `.env`.

### Langkah 2 — Tambahkan lokasi

1. Kembali ke Main Menu.
2. Pilih `1. Manage Hermina Locations`.
3. Pilih `1. Add New Location`.
4. Isi data lokasi.

Contoh untuk mode mock:

```text
Hospital Name [default: Hermina]: 
Branch Name: Hermina Depok
City: Depok
Address: Jl. Siliwangi No. 50, Depok
Latitude:
Longitude:
Source [default: google_places]:
External Place ID: hermina-depok
Is Active? [Y/n]:
```

Menekan Enter pada `Hospital Name`, `Source`, dan `Is Active` akan memakai
nilai default.

Tentang `External Place ID`:

- Merupakan ID unik untuk sebuah lokasi.
- Dalam mode mock boleh memakai slug buatan seperti `hermina-depok`.
- Setiap lokasi harus memakai ID berbeda.
- Dalam mode Google Places, field ini harus berisi Google Place ID asli.
- Kombinasi `Source + External Place ID` tidak boleh duplikat.

### Langkah 3 — Uji fetch tanpa menyimpan

1. Pilih `2. Fetch / Sync Reviews`.
2. Pilih `3. Dry Run Fetch for One Location`.
3. Masukkan ID lokasi.
4. Periksa lima review contoh yang ditampilkan.

Dry run tidak memasukkan review ke database, tetapi tetap membuat fetch log
berstatus `dry_run`.

### Langkah 4 — Simpan review

1. Masih di menu Fetch, pilih `1. Fetch Reviews for One Location`.
2. Masukkan ID lokasi.
3. Pada fetch pertama, mode mock akan memasukkan 10 review.

Jika fetch diulang untuk lokasi yang sama:

```text
Inserted  : 0
Duplicate : 10
```

Ini normal dan menunjukkan deduplikasi bekerja.

### Langkah 5 — Analisis review

1. Kembali ke Main Menu.
2. Pilih `4. Analyze Reviews with Gemini`.
3. Pilih `1. Analyze All Pending Reviews`.

Mode mock akan menghasilkan sentiment, kategori masalah, urgency, ringkasan,
rekomendasi, dan keyword.

### Langkah 6 — Lihat hasil

Gunakan:

- `3. View Review Data` untuk melihat review individual.
- `5. View Analysis Summary` untuk melihat ringkasan.
- `6. Export Data` untuk membuat CSV atau JSON.

---

## 5. Fitur Manage Hermina Locations

### 5.1 Add New Location

Digunakan untuk menambahkan cabang Hermina.

Field yang wajib:

- `Branch Name`
- `Source`
- `External Place ID`

Field latitude dan longitude boleh dikosongkan.

### 5.2 View All Locations

Menampilkan semua lokasi, termasuk yang tidak aktif.

Kolom yang ditampilkan:

- ID
- Hospital
- Branch
- City
- Source
- Active

Catat nilai `ID` karena digunakan pada menu fetch, filter, analisis, dan
export.

### 5.3 View Active Locations

Menampilkan lokasi yang statusnya aktif. Hanya lokasi aktif yang diproses oleh
`Fetch Reviews for All Active Locations`.

### 5.4 Update Location

1. Pilih lokasi berdasarkan ID.
2. Pilih nomor field yang ingin diubah.
3. Masukkan nilai baru.

Field yang dapat diubah:

1. `hospital_name`
2. `branch_name`
3. `city`
4. `address`
5. `latitude`
6. `longitude`
7. `source`
8. `external_place_id`
9. `is_active`

Untuk `is_active`, gunakan nilai seperti `y`, `yes`, `true`, atau `1` untuk
mengaktifkan lokasi.

### 5.5 Activate / Deactivate Location

Pilih ID lokasi untuk membalik status:

- Lokasi aktif menjadi nonaktif.
- Lokasi nonaktif menjadi aktif.

Menonaktifkan lokasi tidak menghapus review yang sudah tersimpan.

### 5.6 Delete Location

Menghapus lokasi beserta review, hasil analisis, dan fetch log terkait.

Fitur ini meminta konfirmasi. Gunakan dengan hati-hati karena data yang sudah
dihapus tidak dapat dikembalikan dari aplikasi.

---

## 6. Fitur Fetch / Sync Reviews

### 6.1 Fetch Reviews for One Location

Mengambil review untuk satu lokasi aktif, melakukan normalisasi, membuat hash,
mencegah duplikat, menyimpan review baru, dan mencatat fetch log.

Hasil menampilkan:

- Total fetched
- Inserted
- Duplicate
- Failed
- Status

### 6.2 Fetch Reviews for All Active Locations

Memproses seluruh lokasi aktif satu per satu.

Jika satu lokasi gagal, aplikasi tetap melanjutkan lokasi berikutnya.

### 6.3 Dry Run Fetch for One Location

Mengambil dan menampilkan contoh review tanpa memasukkannya ke tabel review.

Gunakan fitur ini untuk memastikan konfigurasi source benar sebelum melakukan
fetch sebenarnya.

### 6.4 View Last Fetch Result

Menampilkan fetch log terbaru, termasuk status, jumlah review, waktu mulai,
waktu selesai, dan pesan error jika ada.

### Arti status fetch

- `success`: semua review berhasil diproses.
- `partial_success`: sebagian review gagal diproses.
- `failed`: proses fetch gagal.
- `dry_run`: fetch uji coba tanpa penyimpanan review.

---

## 7. Fitur View Review Data

Review ditampilkan maksimal sesuai `PAGE_SIZE`, default 20 data per halaman.

Saat data memiliki beberapa halaman:

- Ketik `N` untuk halaman berikutnya.
- Ketik `P` untuk halaman sebelumnya.
- Ketik `Q` atau tekan Enter untuk selesai.

### 7.1 View All Reviews

Menampilkan seluruh review yang tersimpan.

### 7.2 View Reviews by Location

Pilih ID lokasi untuk hanya menampilkan review dari cabang tersebut.

### 7.3 View Reviews by Rating

Masukkan rating dari `1` sampai `5`.

Contoh penggunaan:

- Rating `1` atau `2` untuk mencari keluhan.
- Rating `5` untuk melihat pujian.

### 7.4 View Reviews by Sentiment

Nilai yang dapat digunakan:

```text
positive
neutral
negative
mixed
unknown
```

Filter ini baru menghasilkan data setelah review dianalisis.

### 7.5 Search Review Text

Masukkan kata kunci, misalnya:

```text
antrean
parkir
farmasi
dokter
```

Pencarian tidak membedakan huruf besar dan kecil.

### 7.6 View Latest Reviews

Menampilkan review berdasarkan waktu review terbaru.

Kolom `Analyzed` menunjukkan apakah review sudah memiliki hasil analisis.

---

## 8. Fitur Analyze Reviews with Gemini

Dalam mode mock, analisis tidak menghubungi Gemini API. Hasil dibuat secara
lokal berdasarkan rating dan isi review.

### 8.1 Analyze All Pending Reviews

Menganalisis semua review yang belum pernah dianalisis.

Review pending adalah review yang belum memiliki record di
`review_analysis`.

### 8.2 Analyze Reviews by Location

Pilih lokasi untuk menganalisis review pending dari lokasi tersebut saja.

### 8.3 Analyze Reviews by Rating

Masukkan rating `1` sampai `5`.

Fitur ini berguna untuk memprioritaskan review rating `1` dan `2`.

### 8.4 Re-run Analysis for Selected Review

1. Cari Review ID melalui menu `View Review Data`.
2. Masukkan Review ID.
3. Periksa detail review.
4. Konfirmasi re-run.

Hasil lama tidak dihapus. Aplikasi membuat record analisis baru sehingga
riwayat analisis tetap tersimpan.

### 8.5 Re-run Analysis by Location

Menganalisis ulang seluruh review di satu lokasi, termasuk review yang sudah
pernah dianalisis.

Karena setiap re-run membuat record baru, gunakan fitur ini hanya saat memang
dibutuhkan.

### Data hasil analisis

Setiap analisis dapat berisi:

- Sentiment
- Sentiment score
- Issue category
- Urgency
- Summary
- Recommended action
- Keywords
- Potential viral flag
- Patient safety issue flag
- Model name
- Prompt version

---

## 9. Fitur View Analysis Summary

Jalankan analisis terlebih dahulu agar menu ini memiliki data.

### 9.1 Summary for All Locations

Menampilkan:

- Total lokasi
- Total review
- Review yang sudah dianalisis
- Review pending
- Distribusi sentiment
- Kategori isu teratas
- Jumlah isu high/critical
- Waktu fetch terakhir

### 9.2 Summary by Location

Menampilkan ringkasan satu lokasi:

- Total review
- Rata-rata rating
- Jumlah review negatif
- Jumlah isu kritis
- Kategori isu teratas
- Contoh review negatif
- Fokus tindakan manajemen

### 9.3 Negative Review Summary

Menampilkan review dengan sentiment `negative`.

### 9.4 Critical Issue Summary

Menampilkan review dengan urgency:

```text
high
critical
```

### 9.5 Top Issue Categories

Menampilkan lima kategori masalah yang paling sering ditemukan.

### 9.6 Sentiment Distribution

Menampilkan jumlah review berdasarkan sentiment:

- Positive
- Neutral
- Negative
- Mixed
- Unknown

---

## 10. Fitur Export Data

File hasil export disimpan di folder:

```text
exports/
```

### 10.1 Export All Reviews to CSV

Menghasilkan:

```text
reviews_all_YYYYMMDD_HHMMSS.csv
```

### 10.2 Export Reviews by Location to CSV

Pilih ID lokasi. File yang dihasilkan:

```text
reviews_location_{location_id}_YYYYMMDD_HHMMSS.csv
```

### 10.3 Export Analysis Summary to CSV

Menghasilkan ringkasan analisis per lokasi:

```text
analysis_summary_YYYYMMDD_HHMMSS.csv
```

### 10.4 Export Raw Reviews to JSON

Menghasilkan payload review mentah untuk audit:

```text
raw_reviews_YYYYMMDD_HHMMSS.json
```

File export dapat memuat data reviewer. Jangan mengunggah atau membagikannya
tanpa memperhatikan privasi dan kebijakan organisasi.

---

## 11. Fitur View Fetch Logs

### 11.1 View Latest Fetch Logs

Menampilkan maksimal 20 fetch log terbaru.

### 11.2 View Fetch Logs by Location

Pilih ID lokasi untuk melihat riwayat fetch cabang tersebut.

### 11.3 View Failed Fetch Logs

Hanya menampilkan fetch dengan status `failed`.

Gunakan kolom `Error` untuk membantu memeriksa kegagalan API, database, atau
konfigurasi.

---

## 12. Fitur System Settings

### 12.1 Check Database Connection

Memastikan aplikasi dapat terhubung ke PostgreSQL dan tabel utama sudah ada.

Jika schema belum siap:

```powershell
python -m alembic upgrade head
```

### 12.2 Check Gemini API Key

Memeriksa apakah `GEMINI_API_KEY` tersedia. Nilai lengkap tidak ditampilkan.

API key tidak diperlukan selama:

```env
GEMINI_MODE=mock
```

### 12.3 Check Review Source API Key

Memeriksa apakah `GOOGLE_MAPS_API_KEY` tersedia. Nilai lengkap tidak
ditampilkan.

API key tidak diperlukan selama:

```env
REVIEW_SOURCE_MODE=mock
```

### 12.4 Show App Configuration

Menampilkan konfigurasi aktif tanpa membuka password database atau API key.

Gunakan fitur ini untuk memastikan aplikasi sedang memakai mode mock dan nilai
konfigurasi yang diharapkan.

---

## 13. Rekomendasi Pemakaian Harian

Untuk penggunaan rutin:

1. Jalankan `python main.py`.
2. Periksa database melalui `System Settings`.
3. Jalankan `Fetch Reviews for All Active Locations`.
4. Periksa `View Last Fetch Result` atau `View Fetch Logs`.
5. Jalankan `Analyze All Pending Reviews`.
6. Buka `Negative Review Summary`.
7. Buka `Critical Issue Summary`.
8. Periksa `Summary by Location`.
9. Export data jika diperlukan.
10. Pilih `0. Exit`.

---

## 14. Troubleshooting

### Database connection failed

Periksa:

- Service PostgreSQL sedang berjalan.
- Database `hermina_reviews` sudah dibuat.
- Port PostgreSQL sesuai, biasanya `5432`.
- Username dan password di `DATABASE_URL` benar.
- Password dengan spasi sudah diubah menjadi `%20`.

### Database schema is not ready

Jalankan:

```powershell
python -m alembic upgrade head
```

### No Hermina locations found

Tambahkan lokasi melalui:

```text
Manage Hermina Locations → Add New Location
```

### No active Hermina locations found

Aktifkan lokasi melalui:

```text
Manage Hermina Locations → Activate / Deactivate Location
```

### Fetch selalu menunjukkan duplicate

Ini normal jika review yang sama sudah tersimpan. Sistem sengaja mencegah
review duplikat berdasarkan review hash.

### View Reviews by Sentiment kosong

Jalankan analisis terlebih dahulu:

```text
Analyze Reviews with Gemini → Analyze All Pending Reviews
```

### Summary kosong

Pastikan lokasi sudah memiliki review dan review tersebut sudah dianalisis.

### API key tidak ditemukan

Dalam mode mock hal ini tidak menjadi masalah. API key baru diperlukan saat
integrasi real diaktifkan.

---

## 15. Catatan MVP

Versi ini:

- Menggunakan terminal interaktif.
- Menggunakan PostgreSQL sebagai database utama.
- Mendukung fetching mock dan Google Places API resmi.
- Mendukung analisis mock dan Gemini API.
- Tidak memiliki web dashboard.
- Tidak memiliki scheduler otomatis.
- Tidak memakai command-line argument.

Seluruh aktivitas dilakukan dari menu setelah menjalankan:

```powershell
python main.py
```

---

## 16. Mengaktifkan Mode Real

Ubah konfigurasi `.env` menjadi:

```env
REVIEW_SOURCE_MODE=google_places
GOOGLE_MAPS_API_KEY=masukkan_api_key_google_maps
GOOGLE_PLACES_LANGUAGE_CODE=id
GOOGLE_PLACES_REGION_CODE=ID

GEMINI_MODE=real
GEMINI_API_KEY=masukkan_api_key_gemini
GEMINI_MODEL=gemini-2.5-flash
```

Setelah `.env` diubah, tutup aplikasi yang masih berjalan lalu jalankan ulang:

```powershell
python main.py
```

### Persiapan Google Places

1. Aktifkan **Places API (New)** pada Google Cloud project.
2. Pastikan billing Google Maps Platform aktif.
3. Batasi API key agar hanya dapat mengakses **Places API (New)**.
4. Gunakan Google Place ID asli untuk setiap lokasi.

Contoh Google Place ID:

```text
ChIJxxxxxxxxxxxxxxxx
```

Jika lokasi lama dibuat dalam mode mock dengan ID seperti `hermina-depok`:

1. Buka `Manage Hermina Locations`.
2. Pilih `Update Location`.
3. Pilih lokasi.
4. Ubah field `external_place_id`.
5. Masukkan Google Place ID asli.

`Source` lokasi tetap dapat diisi `google_places`.

Google Places Place Details (New) hanya mengembalikan maksimal lima review
yang dipilih berdasarkan relevansi. API resmi ini tidak menyediakan pagination
untuk mengambil seluruh histori review. Karena itu, nilai
`FETCH_LIMIT_PER_LOCATION=50` tetap tidak akan menghasilkan lebih dari lima
review per lokasi pada satu request Google Places.

### Persiapan Gemini

1. Buat API key Gemini melalui Google AI Studio atau project Google yang sesuai.
2. Isi `GEMINI_API_KEY`.
3. Gunakan model stabil:

```env
GEMINI_MODEL=gemini-2.5-flash
```

Gemini mengembalikan structured JSON yang divalidasi sebelum disimpan.
Jika satu review gagal dianalisis, aplikasi mencatat error dan melanjutkan
review berikutnya.

### Urutan pengujian mode real

1. Jalankan `System Settings → Check Database Connection`.
2. Jalankan `System Settings → Check Review Source API Key`.
3. Jalankan `System Settings → Check Gemini API Key`.
4. Pastikan satu lokasi memiliki Google Place ID asli.
5. Jalankan `Fetch / Sync Reviews → Dry Run Fetch for One Location`.
6. Periksa nama reviewer, rating, teks, dan waktu review.
7. Jika hasil benar, jalankan `Fetch Reviews for One Location`.
8. Jalankan `Analyze Reviews with Gemini → Analyze All Pending Reviews`.
9. Periksa hasil melalui `View Review Data` dan `View Analysis Summary`.

### Jika fetch real gagal

Periksa:

- Places API (New) sudah aktif.
- Billing Google Maps Platform sudah aktif.
- API key tidak kedaluwarsa atau diblokir.
- Pembatasan API key mengizinkan Places API (New).
- `external_place_id` adalah Google Place ID asli.
- Komputer memiliki koneksi internet.

### Jika Gemini real gagal

Periksa:

- API key Gemini benar dan masih aktif.
- Project memiliki akses ke model yang dipilih.
- Model di `.env` adalah model yang tersedia.
- Kuota dan billing belum habis.
- Komputer memiliki koneksi internet.

Jangan menggunakan API key yang pernah dipublikasikan. Rotasi key lama dan
gunakan pembatasan API/key restriction sebelum pemakaian operasional.

---

## 17. Selenium Scraping Review Google Maps

Mode ini ditujukan untuk POC lokal dan riset internal, bukan metode produksi
default. Pastikan penggunaan sudah sesuai kebijakan Google dan persetujuan
organisasi.

Konfigurasi:

```env
REVIEW_SOURCE_MODE=selenium
SELENIUM_HEADLESS=false
SELENIUM_DEFAULT_TARGET_REVIEWS=100
SELENIUM_MAX_TARGET_REVIEWS=300
SELENIUM_SCROLL_DELAY_SECONDS=2
SELENIUM_MAX_SCROLL_ATTEMPTS=100
SELENIUM_WAIT_TIMEOUT_SECONDS=20
SELENIUM_USER_DATA_DIR=.selenium-profile
```

Setelah mengubah `.env`, tutup proses aplikasi lama dan jalankan ulang.

### Setup profil Selenium satu kali

Google dapat menampilkan **tampilan terbatas** pada profil Chrome baru dan
menyembunyikan daftar review. Aplikasi tidak mengotomatisasi login dan tidak
mengakali pembatasan tersebut.

Jalankan:

```powershell
python -m scripts.setup_selenium_profile
```

Pada jendela Chrome yang terbuka:

1. Login ke Google secara manual.
2. Selesaikan pengaturan **Optimalkan penggunaan Google Maps** jika muncul.
3. Kembali ke halaman lokasi Hermina.
4. Buka panel **Ulasan/Reviews**.
5. Tunggu sampai terminal menampilkan `selenium-profile-login-ready`.

Sesi disimpan di `.selenium-profile/` dan tidak masuk Git. Jangan mengarahkan
`SELENIUM_USER_DATA_DIR` ke profil Chrome utama yang sedang digunakan.

### Menyiapkan lokasi

Pada `Manage Hermina Locations`, lokasi Selenium mendukung:

- `google_maps_url`
- `google_reviews_url`
- `target_review_count`

Urutan URL yang digunakan:

1. `google_reviews_url`, jika tersedia.
2. `google_maps_url`, jika tersedia.
3. URL Maps yang dibuat dari `external_place_id`.

Untuk mengubah lokasi lama:

```text
Manage Hermina Locations
→ Update Location
→ pilih google_maps_url / google_reviews_url / target_review_count
```

### Menjalankan scraping

```text
Fetch / Sync Reviews
→ Selenium Fetch from Review URL
→ pilih lokasi
→ pilih 100 / 150 / 200 / custom
```

Custom target tidak boleh melebihi 300. Scraper akan:

1. Membuka Google Maps.
2. Membuka panel review jika diperlukan.
3. Scroll perlahan minimal dua detik.
4. Berhenti saat target tercapai, tidak ada review baru, atau batas scroll
   tercapai.
5. Menyimpan review baru dan melewati duplikat.
6. Menutup browser.
7. Menyimpan fetch log beserta metadata scroll.

Source review yang tersimpan adalah:

```text
selenium_google_maps
```

Scraping dan Gemini tetap proses terpisah. Setelah scraping selesai, jalankan:

```text
Analyze Reviews with Gemini → Analyze All Pending Reviews
```

### Batas perilaku

Implementasi ini tidak menggunakan:

- Proxy rotation
- CAPTCHA bypass
- Login automation
- Account automation
- Parallel scraping
- Anti-bot bypass

Jika muncul pesan limited view, ulangi setup profil manual. Jika selector gagal,
Google Maps kemungkinan mengubah tampilan dan selector perlu diperbarui.
