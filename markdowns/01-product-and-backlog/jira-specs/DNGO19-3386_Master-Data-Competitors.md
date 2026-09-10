# DNGO19-3386 — VOC Master Data Competitors

**Branch:** `feature/DNGO19-3386_VOC-Master-Data-Competitors` · **PR** #12, #17
**Commit terakhir:** `72d9c38d` — 18/Aug/26
**Layar:** Media Monitoring › Voice of Customer › **Kompetitor**

---

## 1. Description of Development Resolve

> Salin mulai baris berikut.

Layar Master Data Kompetitor untuk mendaftarkan pesaing yang ulasan Google-nya ikut dipantau, lalu memetakannya ke cabang yang relevan sebagai dasar perbandingan.

**Yang dikerjakan**

- **Data kompetitor:** nama, Google Place ID (wajib — inilah target crawl-nya), kategori (RS / Klinik / Lab / Apotek), kota, provinsi, alamat, dan URL Google Maps. Panjang tiap field divalidasi, dan URL harus http/https yang sah.
- **Pemetaan ke cabang:** satu kompetitor wajib dipetakan ke minimal satu cabang, dengan prioritas P1–P3 dan kelompok layanan yang dibandingkan (IGD, rawat jalan, rawat inap, farmasi, dan seterusnya). Kompetitor tanpa pemetaan tidak bermakna di sistem ini.
- **Kelola cabang dari baris tabel** — menambah atau melepas satu pemetaan tanpa membuka form penuh.
- **Aktif/nonaktif, resync, hapus,** dan **import** kompetitor yang sudah ada di Crawler tapi belum terdaftar di OneBox.
- **Fetch review kompetitor** lewat layar Fetch Jobs Kompetitor, memakai alur yang sama persis dengan cabang.

**Keputusan teknis yang perlu diketahui**

1. **Hapus dijalankan di Crawler dulu.** Kalau Crawler menolak, penghapusan di OneBox ikut dibatalkan — kalau diteruskan, kompetitor tetap di-crawl di sana tanpa ada yang mengelola di sini.
2. **Simpan tanpa mengirim daftar pemetaan tidak menghapus pemetaan yang ada.** Absennya field diperlakukan berbeda dari daftar kosong; tanpa penjagaan ini, sekadar mengubah nama akan menghapus seluruh assignment.
3. Layar Kompetitor memakai view yang sama dengan layar Lokasi dengan penanda jenis, jadi perbaikan tampilan berlaku untuk keduanya sekaligus.

> Salin sampai baris di atas.

---

## 2. Development Resolve Date

**Isi: `18/Aug/26`** — tanggal commit terakhir di branch (`72d9c38d`).

---

## 3. Comment

> Salin mulai baris berikut.

**Cara uji (dev):** Media Monitoring › Voice of Customer › Kompetitor.

1. Tambah kompetitor tanpa Google Place ID — harus ditolak dengan pesan yang menyebut Place ID dipakai sebagai target crawl.
2. Tambah kompetitor lengkap, petakan ke satu cabang dengan prioritas dan kelompok layanan.
3. Ubah namanya saja lalu simpan — **pemetaan cabang harus tetap utuh.**
4. Lepas dan tambah pemetaan dari baris tabel, tanpa membuka form penuh.
5. Nonaktifkan, lalu resync.
6. Jalankan Fetch Jobs Kompetitor dan pastikan review kompetitor masuk.
7. Hapus kompetitor, pastikan hilang di OneBox dan di Crawler.

**Yang bukan bug:**

- Kompetitor **tidak bisa disimpan tanpa minimal satu cabang** — ini aturan yang dirancang.
- Kalau Crawler sedang tidak bisa dihubungi, **hapus akan gagal dan datanya tetap ada.** Itu disengaja, bukan gagal simpan.
- Kategori terbatas pada empat pilihan (RS, Klinik, Lab, Apotek); nilai di luar itu ditolak.

> Salin sampai baris di atas.
