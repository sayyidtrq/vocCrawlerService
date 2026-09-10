# Laporan Progress: Frontend Profile Management V2

**Role:** Frontend Developer  
**Fokus Utama:** Penyesuaian UI & Form Schema `settings-client.tsx` terhadap spesifikasi `system-design-v2.md`

## 1. Pekerjaan yang Sudah Diselesaikan (Done)

### A. Penyesuaian Schema Data Organisasi (Sesuai Konsep V2)
Sesuai dengan arahan mentor bahwa halaman *Settings* difokuskan pada manajemen **Profil Organisasi / Tenant** (bukan sekadar akun user), beberapa penyesuaian telah ditambahkan secara aman di sisi Frontend:
- **Penambahan Field Baru:** Menambahkan `organization_type` dan `status` ke dalam *form schema* (Zod) dan tampilan antarmuka.
- **Pendekatan Placeholder (Aman untuk BE):** Menggunakan data sementara (*placeholder/mock*) pada form form tersebut. Dengan begini, *payload* dan *request* frontend bisa jalan tanpa menyebabkan error/konflik dengan model di sisi Backend yang saat ini masih disiapkan oleh tim BE.

### B. Peningkatan Estetika UI / UX (Beautification)
Membuat tampilan halaman *Settings* menjadi lebih premium, modern, dan konsisten dengan *vibe* halaman Dashboard:
- **Section Headers (Tipografi):** Memperbesar teks judul bagian (`text-2xl`/`3xl`), menjadikannya sangat tebal (`font-extrabold`), dan menggunakan *kicker* berwarna hijau tua agar struktur halamannya lebih tegas terbaca.
- **Form Inputs (Kotak Isian):** Menghilangkan *border* tajam, menggantinya dengan sudut lebih membulat (`rounded-lg`), *border* halus berwarna `slate-200`, bayangan tipis (`shadow-sm`), dan efek transisi ketika di-klik.
- **Feature Flags Cards (Checkbox):** Kotak centang hak akses disulap menjadi *card* yang terlihat *pop-up* dengan sudut `rounded-xl` dan efek bayangan (*hover shadow*) ketika kursor melewatinya.
- **Quota Cards (Batas Penggunaan):** Mengubah 4 kotak *resource limit* di bagian bawah menggunakan warna pastel yang cantik & beda-beda (Scraping Limit: *Emerald*, Maksimal Lokasi: *Blue*, Maksimal Source: *Indigo*, Kuota AI: *Amber*), agar terasa lebih segar dan mudah dibedakan oleh mata.

---

## 2. Pekerjaan yang Belum Selesai / Next Steps (To-Do)

Daftar pekerjaan ini adalah kelanjutan (tindak lanjut) jika API dari Backend Developer sudah siap, atau untuk sprint selanjutnya:

### A. Pemisahan Halaman User Profile
- **Kondisi Saat Ini:** Form "Profil Pengguna" (Nama Lengkap & Email) masih numpuk/tergabung di atas bagian "Informasi Organisasi".
- **Tindak Lanjut:** Sesuai *best practice* dan diskusi mentor, manajemen profil perusahaan sebaiknya terpisah dari akun individu. Nantinya, blok "Profil Pengguna" ini bisa dipindah ke halaman / sub-menu sendiri (misal: `/settings/account`) atau dijadikan pop-up modal profil.

### B. Integrasi "Ganti Password"
- **Kondisi Saat Ini:** Kolom ganti password belum tersedia di halaman profile.
- **Tindak Lanjut:** Berdasarkan arsitektur V2, fitur ganti password idealnya tidak disatukan sebagai input teks biasa. Frontend perlu membuat sebuah tombol "Ubah Password" yang akan memunculkan pop-up modal khusus, atau langsung memanggil alur (API) *Reset Password* via email.

### C. "Wiring" / Penyambungan ke API Backend V2
- **Kondisi Saat Ini:** Aksi klik tombol "Simpan Perubahan" masih sebatas pura-pura (*dummy*), hanya memunculkan `alert` dan `console.log` agar tidak error dengan *backend*.
- **Tindak Lanjut:** Kalau endpoint dari tim BE sudah matang, fungsi `onSubmit` perlu dihubungkan langsung ke REST API (misalnya `PATCH /api/profiles/{id}`).
- **Tindak Lanjut:** Menghapus label "Placeholder" dan mengisi atribut-atribut baru (seperti `organization_type`, `website_crawler_enable_flag`, dll) menggunakan data murni (Real Data) yang dikembalikan oleh backend API nanti.
