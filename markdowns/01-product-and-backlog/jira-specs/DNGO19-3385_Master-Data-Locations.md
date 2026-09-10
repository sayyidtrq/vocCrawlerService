# DNGO19-3385 — VOC Master Data Locations

**Branch:** `feature/DNGO19-3385_VOC-Master-Data-Locations` · **PR** #10, #36, #44, #45
**Commit terakhir:** `7484fd9c` — 12/Aug/26
**Layar:** Media Monitoring › Voice of Customer › **Lokasi**

---

## 1. Description of Development Resolve

> Salin mulai baris berikut.

Layar Master Data Lokasi untuk mendaftarkan cabang yang ulasan Google-nya dipantau. Layar ini adalah hulu seluruh modul VoC — tanpa lokasi terdaftar, tidak ada yang bisa di-crawl, dan tidak ada review yang masuk.

**Yang dikerjakan**

- **Empat mode tampilan dalam satu layar:** Lokasi, Kompetitor, Peta, dan Grafik wilayah. Satu tempat untuk seluruh master data VoC, bukan layar terpisah-pisah.
- **Empat KPI** yang sekaligus berfungsi sebagai penyaring saat diklik: Lokasi Operasional, Wilayah Operasional, Kota Terpantau, dan Coverage Benchmark (wilayah yang sudah punya pembanding kompetitor).
- **Data lokasi:** nama cabang, Google Place ID, kota, alamat, URL Google Maps, koordinat lintang/bujur, dan wilayah operasional.
- **Data PIC:** nama, nomor WhatsApp, email, dan tautan ke user OneBox — dipakai layar Kelola Review saat mengeskalasi ulasan ke penanggung jawab cabang.
- **Penanda kepemilikan akun Google Business.** Diatur di layar ini, dan inilah yang menghidupkan tombol Balas di layar Kelola Review.
- **Mode Peta:** kanvas peta berdampingan dengan kartu lokasi, plus penandaan lokasi yang koordinatnya belum terisi.
- **Aksi:** tambah, ubah, aktif/nonaktif, resync ke Crawler, hapus, dan import lokasi yang sudah ada di Crawler tapi belum terdaftar di OneBox.

**Keputusan teknis yang perlu diketahui**

1. **Google Place ID divalidasi formatnya, bukan sekadar wajib diisi.** Ini menangkap kesalahan yang paling mahal di modul ini: menempelkan tautan peta atau nama tempat alih-alih ID. Kalau lolos, crawler akan menarik review bisnis lain tanpa ada tanda apa pun bahwa targetnya salah — datanya masuk, kelihatan normal, dan salah.
2. **Hapus ditolak kalau cabang sudah punya review.** Menghapus koneksinya akan membuat review lama hilang dari layar Kelola Review. Layar memberi tahu jumlah review-nya dan menyarankan nonaktifkan sebagai gantinya.
3. **Lokasi disimpan di OneBox dulu, baru dikirim ke Crawler.** Kalau pengiriman gagal, barisnya tetap ada dengan status belum tersinkron — tidak gagal senyap, dan tidak ada data yang hilang. Tombol Resync untuk mencoba lagi.
4. **Import menutup arah sebaliknya.** Sebelumnya lokasi bisa dibuat langsung di Crawler, sehingga ada target crawl yang aktif di sana tapi review-nya tidak pernah sampai ke OneBox karena tidak punya koneksi.
5. Nama cabang dibatasi 80 karakter karena kolom penyimpanannya diberi awalan sistem; lebih dari itu akan terpotong diam-diam.

> Salin sampai baris di atas.

---

## 2. Development Resolve Date

**Isi: `12/Aug/26`** — commit terakhir di branch ini (`7484fd9c`).

Catatan: layar ini masih menerima perbaikan lewat branch lain setelah tanggal tersebut (mis. perbaikan query di dev). Kalau kebijakan tim mengisi kolom ini dengan tanggal pekerjaan tiket ini selesai, 12/Aug/26 yang benar.

---

## 3. Comment

> Salin mulai baris berikut.

**Cara uji (dev):** Media Monitoring › Voice of Customer › Lokasi.

1. Tambah lokasi dengan menempelkan **tautan Google Maps** ke kolom Place ID — harus ditolak dengan contoh format yang benar.
2. Tambah lokasi lengkap dengan Place ID yang sah, koordinat, wilayah, dan PIC.
3. Cek keempat mode: Lokasi, Kompetitor, Peta, Grafik. Di mode Peta, lokasi tanpa koordinat harus ditandai, bukan hilang diam-diam.
4. Klik KPI — daftarnya harus ikut tersaring.
5. Tandai kepemilikan akun Google Business, lalu buka layar Kelola Review: **tombol Balas untuk lokasi itu harus hidup.**
6. Nonaktifkan satu lokasi, lalu Resync.
7. Coba hapus lokasi yang **sudah punya review** — harus ditolak dengan jumlah review-nya disebutkan.
8. Jalankan Import dan pastikan lokasi yang hanya ada di Crawler ikut tertarik.

**Yang bukan bug:**

- **Lokasi ber-review tidak bisa dihapus.** Ini penjagaan, bukan kegagalan — hapus akan membuat review lamanya hilang dari layar Kelola Review.
- **Lokasi baru bisa muncul dengan status belum tersinkron** kalau Crawler sedang tidak bisa dihubungi. Datanya aman, tinggal Resync.
- **Tombol Balas mati** selama kepemilikan akun Google Business-nya belum ditandai di layar ini.

> Salin sampai baris di atas.
