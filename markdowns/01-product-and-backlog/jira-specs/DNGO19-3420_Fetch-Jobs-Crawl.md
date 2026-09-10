# DNGO19-3420 — VOC Fetch Jobs Crawl

**Branch:** `feature/DNGO19-3420_VOC-Fetch-Jobs-Crawl` · **PR** #20, #21, #23, #25, #26, #28, #29, #30, #43, #46
**Commit terakhir:** `1ae5f8a5` — 12/Aug/26
**Layar:** Media Monitoring › Voice of Customer › **Fetch Jobs** (dan Fetch Jobs Kompetitor)

---

## 1. Description of Development Resolve

> Salin mulai baris berikut.

Layar Fetch Jobs untuk menjalankan penarikan ulasan Google secara manual dan memantau hasilnya sampai ulasannya benar-benar masuk ke OneBox.

**Yang dikerjakan**

- **Menjalankan penarikan:** pilih satu cabang atau semua cabang aktif, tentukan target jumlah ulasan (1–300), rentang tanggal, dan urutan pengambilan (Terbaru / Paling relevan / Rating tertinggi / Rating terendah).
- **Rentang tanggal** bisa lewat preset jumlah hari ke belakang atau tanggal awal–akhir. Tanggal akhir dihitung sampai ujung hari — "sampai 4 Agustus" berarti termasuk seluruh tanggal 4, bukan berhenti di pukul 00:00.
- **KPI:** Total ulasan, Ulasan di OneBox, Ulasan Baru Masuk, Masuk run terakhir, dan Tingkat berhasil.
- **Riwayat Fetch:** setiap batch tercatat dengan nama cabang, status (Mengantre / Berjalan / Selesai / Sebagian gagal / Gagal), cocok terhadap target, jumlah baru di Crawler, duplikat, jumlah yang di luar rentang, dan waktunya. Dilengkapi penyaring, pagination, dan tombol **Ulangi** untuk menjalankan ulang batch yang sama.
- **Versi kompetitor** memakai layar dan alur yang sama persis, hanya berbeda sumber datanya.

**Keputusan teknis yang perlu diketahui**

1. **Tiga kuota diperiksa sebelum antrean disentuh:** panggilan crawl per hari, ulasan yang boleh masuk bulan ini, dan ulasan yang boleh dianalisis AI. Kuota AI sengaja dijaga di titik ini — analisanya berjalan di sisi Crawler, jadi begitu perintah crawl terkirim, OneBox tidak punya kesempatan lain untuk menahannya.
2. **Target wajib dikirim, tidak boleh mengandalkan nilai bawaan.** Kalau target tidak ikut terkirim, Crawler diam-diam memakai angka dari antreannya sendiri — dan angka yang diketik admin di layar jadi tidak berarti apa-apa.
3. **Dua klik yang disengaja menghasilkan dua penarikan; satu klik yang terkirim ulang karena jaringan putus tetap menghasilkan satu.** Penandanya diambil dari kliknya, bukan dari menit berjalan.
4. **Fetch manual dan fetch terjadwal memakai jalur yang sama.** Menyalin alurnya ke dua tempat berarti setiap perbaikan berikutnya harus diingat dua kali, dan yang kedua pasti terlupa.
5. Sumber crawl saat ini hanya Selenium. Nilai lain ditolak dengan pesan yang jelas, bukan diterima lalu diabaikan diam-diam.

**Catatan lapangan dari uji end-to-end (di luar cakupan tiket ini)**

Urutan "Terbaru" tidak selalu berhasil dipasang di Google Maps. Kalau gagal, ulasan datang dalam urutan relevansi, sehingga aturan "berhenti begitu ketemu yang lebih tua dari rentang" kehilangan dayanya dan seluruh katalog harus disisir. Target tetap dipatuhi — yang mahal hanya pencariannya. Contoh terukur: target 10 ulasan, disisir 464, 444 di luar rentang, 10 masuk. **Perbaikannya ada di sisi Crawler System**, bukan OneBox.

> Salin sampai baris di atas.

---

## 2. Development Resolve Date

**Isi: `12/Aug/26`** — commit terakhir di branch ini (`1ae5f8a5`, perbaikan cabang aktif yang ditolak Crawler).

---

## 3. Comment

> Salin mulai baris berikut.

**Cara uji (dev):** Media Monitoring › Voice of Customer › Fetch Jobs.

1. Jalankan penarikan **tanpa mengisi target** — harus ditolak, bukan jalan dengan angka bawaan.
2. Isi target di luar 1–300 — harus ditolak dengan batasnya disebutkan.
3. Jalankan penarikan satu cabang dengan rentang tanggal dan urutan Terbaru. Pantau progresnya sampai status **Selesai**.
4. Cocokkan tiga angka: jumlah masuk di Riwayat Fetch, pertambahan KPI Ulasan di OneBox, dan jumlah baris baru di layar Kelola Review. Ketiganya harus sama.
5. Pilih tanggal akhir hari ini — ulasan hari ini harus ikut tertarik, tidak terpotong di pukul 00:00.
6. Tekan **Ulangi** pada satu batch lama dan pastikan batch barunya terbentuk.
7. Klik tombol jalankan **dua kali dengan sengaja** — harus jadi dua batch, bukan satu.
8. Uji juga Fetch Jobs Kompetitor dengan alur yang sama.

**Yang bukan bug:**

- **Menyisir ratusan ulasan untuk mendapat sepuluh.** Kalau urutan Terbaru gagal dipasang di Google Maps, seluruh katalog harus disisir untuk menemukan yang masuk rentang. Jumlah yang tersimpan tetap sesuai target.
- **Kolom "Di luar rentang" baru terisi saat batch selesai**, bukan bertambah selama proses berjalan. Selama berjalan angkanya memang 0.
- **Penarikan ditolak karena kuota** akan menyebut kuota mana yang habis dan berapa sisanya. Itu pesan yang benar, bukan gangguan sesi.

> Salin sampai baris di atas.
