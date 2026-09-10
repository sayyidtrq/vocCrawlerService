# Newer System - Review System (V2)

Tanggal update: 2026-07-02

Dokumen ini merangkum perubahan, penambahan fitur, dan perbaikan arsitektur sistem yang telah diimplementasikan dari kondisi awal (**existing-system.md**) menuju **Voice of Customer V2**.

---

## 1. Perubahan Utama (Key Changes)

Dari audit *gap* awal, berikut adalah modul-modul yang kini **sudah berhasil diimplementasikan**:
1. **Multi-tenancy & Organization Model**: Menambahkan entitas `Company` (Perusahaan/Rumah Sakit) sebagai basis pembatasan data.
2. **Sistem Auth & Pengguna**: Mengaktifkan sistem login, registrasi, dan perlindungan JWT Token (Bearer Auth).
3. **Feature Entitlement (Hak Akses Fitur)**: Mengimplementasikan pembatasan fitur berbasis perusahaan (`ai_enable_flag`, `total_enable_review`, `analyze_competitor_flag`).
4. **Competitor Entity & CRUD**: Menambahkan pengelolaan kompetitor rumah sakit untuk perbandingan performa.
5. **Google Place ID Manual Input**: Sistem sekarang mewajibkan pengguna untuk memasukkan *Google Place ID* secara manual, memberikan kontrol penuh tanpa ketergantungan API pihak ketiga untuk resolusi tempat, karena komponen Map Picker (Leaflet) dan API resolver terkait telah dihapus.
6. **Frontend & Backend Security**: Seluruh rute dashboard Frontend dilindungi oleh pengecekan sesi (redirection). Di sisi Backend, *semua endpoint API* (Locations, Places, Competitors, Dashboard, Reviews, Analysis, Fetch Jobs, Fetch Logs, Exports, Pipeline, Settings) kini dijaga dengan `Depends(get_current_user)`, mengharuskan JWT token di setiap request HTTP secara otomatis.

---

## 2. Pembaruan Struktur Codebase

Beberapa berkas telah ditambahkan/diperbarui pada struktur sistem:

```text
app/
  db/
    models.py             <-- [MODIFIED] Menambahkan model Company, User, Competitor, CompetitorReview
  services/
    location_service.py   <-- [MODIFIED] Membaca & memfilter data berdasarkan company_id
    competitor_service.py <-- [NEW] Service logic untuk CRUD kompetitor

apps/api/
  app_api/
    dependencies.py       <-- [NEW] JWT verification & get_current_user dependencies
    routers/
      auth.py             <-- [NEW] Endpoint login, register, dan me
      competitors.py      <-- [NEW] Endpoint CRUD kompetitor
      [ALL ROUTERS]       <-- [MODIFIED] Menerapkan Depends(get_current_user)
  main.py                 <-- [MODIFIED] Registrasi router baru (auth, competitors)

herminaCrawler-fe/
  app/
    lib/
      auth-context.tsx    <-- [NEW] State management pengguna, token, login/logout
      api.ts              <-- [MODIFIED] Auto-inject Header Authorization Bearer token
    components/
      app-shell.tsx       <-- [MODIFIED] Integrasi rute terproteksi, tombol keluar, dan widget hak akses
    login/
      page.tsx            <-- [NEW] UI login admin & registrasi perusahaan
    competitors/
      page.tsx            <-- [NEW] Halaman modul kompetitor
      competitors-client.tsx <-- [NEW] UI kelola kompetitor (CRUD) dengan input manual Place ID
    locations/
      locations-client.tsx<-- [MODIFIED] Input manual Place ID tanpa peta

create_tables.sql         <-- [MODIFIED] Skema SQL terbaru + sinkronisasi id sequence SERIAL untuk mencegah duplicate key.
```

---

## 3. Skema Database Baru (V2)

### 3.1 `companies` [NEW]
Menyimpan data tenant/perusahaan beserta batasan fiturnya (*entitlements*).
- `id` (SERIAL PRIMARY KEY)
- `name` (VARCHAR)
- `ai_enable_flag` (BOOLEAN) - Mengontrol fitur analisis LLM/Gemini.
- `total_enable_review` (INTEGER) - Batasan kuota scraping review.
- `analyze_competitor_flag` (BOOLEAN) - Mengontrol akses pelacakan kompetitor.

### 3.2 `users` [NEW]
Menyimpan akun kredensial administrator.
- `id` (SERIAL PRIMARY KEY)
- `company_id` (INTEGER, Foreign Key ke `companies`)
- `email` (VARCHAR, UNIQUE)
- `password_hash` (VARCHAR)
- `full_name` (VARCHAR)
- `is_active` (BOOLEAN)

### 3.3 `competitors` [NEW]
Menyimpan data master rumah sakit pesaing milik per-perusahaan.
- `id` (SERIAL PRIMARY KEY)
- `company_id` (INTEGER, Foreign Key ke `companies`)
- `name` (VARCHAR)
- `city` (VARCHAR)
- `address` (TEXT)
- `latitude` (NUMERIC)
- `longitude` (NUMERIC)
- `source` (VARCHAR)
- `external_place_id` (VARCHAR)
- `google_maps_url` (TEXT)
- `google_reviews_url` (TEXT)
- `target_review_count` (INTEGER)
- `is_active` (BOOLEAN)

### 3.4 `competitor_reviews` [NEW]
Menampung review hasil scraping kompetitor terdaftar.
- Struktur tabel mirip dengan `reviews` lama, namun berelasi dengan `competitor_id` alih-alih `location_id`.

### 3.5 Kolom Tambahan (`company_id`)
Kolom `company_id` bertipe `INTEGER` (Foreign Key ke `companies`) ditambahkan ke tabel:
- `locations`
- `reviews`
- `fetch_logs`

---

## 4. API Endpoints (Backend)

### 4.1 Otentikasi (`/api/auth`)
- **POST `/api/auth/register`**: Registrasi perusahaan baru + akun admin pertama secara bersamaan.
- **POST `/api/auth/login`**: Penukaran kredensial (username/password) dengan JWT Token (menggunakan OAuth2 standard flow).
- **GET `/api/auth/me`**: Mengembalikan profil admin yang sedang login beserta informasi *entitlement* perusahaannya. (Protected by JWT)

### 4.2 Kelola Kompetitor (`/api/competitors`)
- CRUD lengkap untuk kompetitor:
  - `GET /api/competitors` (Membaca daftar kompetitor per-perusahaan)
  - `POST /api/competitors` (Menambah kompetitor baru)
  - `GET /api/competitors/{id}` (Detail kompetitor)
  - `PATCH /api/competitors/{id}` (Memperbarui data kompetitor)
  - `POST /api/competitors/{id}/toggle-active` (Mengaktifkan/menonaktifkan pelacakan kompetitor)
  - `DELETE /api/competitors/{id}` (Menghapus kompetitor)
*Semua endpoint kompetitor memerlukan Bearer Auth JWT.*

### 4.3 Security Standar
Semua entitas data (`locations`, `reviews`, `competitors`, dll) telah dilindungi JWT Authentication Barrier secara menyeluruh di backend dengan `Depends(get_current_user)`, yang mana pengguna tidak lagi bisa mengambil atau mengubah data apapun jika tidak menyertakan JWT token valid.

---

## 5. Implementasi Frontend Baru (V2)

### 5.1 Rute Terproteksi & Penanganan Token
Setiap rute di bawah `AppShell` dilindungi oleh pengecekan sesi. Jika token kosong, sistem secara otomatis mengalihkan *viewport* ke `/login`. Ketika memanggil API backend, berkas `api.ts` secara otomatis menyisipkan token tersebut sebagai header `Authorization: Bearer <token>`.

### 5.2 Form Registrasi & Hak Akses
Form pendaftaran memfasilitasi penyesuaian hak akses perusahaan (`ai_enable_flag`, `total_enable_review`, `analyze_competitor_flag`) secara interaktif. Pengaturan ini langsung disimpan ke entitas `companies`.

### 5.3 Google Place ID Manual Input
Komponen peta pihak ketiga (MapPicker) di frontend serta API resolusi peta backend kini dihapus total dari project, memaksa input manual *Google Place ID* untuk menambah lokasi/kompetitor sehingga user punya fleksibilitas mutlak.

### 5.4 Sidebar Menu Dinamis
Menu navigasi samping (`AppShell`) sekarang menampilkan:
- Nama rumah sakit/perusahaan dari profil pengguna yang login.
- Nama lengkap admin beserta tombol **Keluar** (Log Out).
- Rangkuman hak akses aktif (*AI Analysis*, *Comp Tracker*, *Scrape Limit*).
- Opsi menu **Competitors** yang hanya muncul apabila perusahaan tersebut memiliki lisensi pelacakan kompetitor (`analyze_competitor_flag` bernilai `true`).

---

## 6. Sisa Gap Menuju V2 Penuh

Sistem saat ini sudah kokoh sebagai SaaS multi-tenant dengan deteksi kompetitor. Beberapa gap minor dari V2 yang masih tersisa adalah:
- Integrasi pipeline scraping/fetching otomatis untuk competitor reviews (saat ini master data sudah ada namun run crawler-nya masih perlu diarahkan).
- Heatmap visualisasi persebaran review negatif / positif di dashboard.
- Background worker/task queue untuk menghindari request timeout saat melakukan scraping Selenium berukuran besar (misalnya menggunakan Celery/Arq).
