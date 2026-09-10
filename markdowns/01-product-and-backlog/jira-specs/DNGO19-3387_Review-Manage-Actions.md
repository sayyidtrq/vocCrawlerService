# DNGO19-3387 — VOC Review Manage Actions

**Branch:** `feature/DNGO19-3387_VOC-Review-Manage-Actions`
**Merged ke:** `feature/voc` (PR #7, #14, #15, #34, #35, #38, #56, #57)
**Commit terakhir:** `80331b1a` — 19/Aug/26
**Layar:** Media Monitoring › Voice of Customer › **Kelola Review** (`/Voc/reviews`)

Isi tiga kolom di bawah tinggal disalin ke Jira apa adanya.

---

## 1. Description of Development Resolve

> Salin mulai baris berikut.

Layar Kelola Review kini menjadi tempat kerja penuh untuk menindaklanjuti ulasan Google, bukan sekadar daftar baca-saja. Petugas humas bisa membaca ulasan beserta hasil analisis AI-nya, mengoreksi analisis itu bila keliru, menyusun draft balasan, meneruskannya ke PIC cabang, dan menaikkannya menjadi tiket operasional — semuanya dari satu layar, dengan jejak siapa melakukan apa.

**Yang dikerjakan**

*Melihat dan menyaring*
- Empat KPI di kepala layar: Total review, Hari ini, Bulan ini, dan jumlah Lokasi.
- Tiga cara menampilkan data yang sama: List, Pie chart, dan Bar chart, dengan pilihan pengelompokan.
- Penyaring lengkap: pencarian nama/kata kunci, rentang tanggal ulasan (plus preset hari ini / kemarin / minggu ini / bulan ini), sentimen, urgensi, status analisis, rating, kategori, status tindak lanjut, prioritas tiket, dan penanggung jawab.
- Tabel menampilkan reviewer, sentimen, urgensi, status balasan, dan cuplikan isi ulasan dua baris. Penanda `OFFICIAL` / `BELUM DITANDAI` menerangkan apakah akun Google Business-nya milik sendiri — tombol Balas mengikuti penanda ini. Penanda `TIKET` muncul pada review yang sudah dinaikkan.

*Panel detail*
- Isi ulasan lengkap beserta tautan **Review Asli** ke Google Maps dan tautan profil reviewer.
- Hasil analisis AI ditampilkan utuh: sentimen, urgensi, kategori, ringkasan, dan rekomendasi tindakan.
- Balasan terkirim (bila ada) dipisahkan dari kolom draft balasan, sehingga keduanya tidak tertukar.

*Aksi kelola* — `POST Voc/reviewManage`
- Ubah status tiket, prioritas, dan penanggung jawab. Penugasan bisa dilepas kembali, dan penanggung jawab divalidasi harus anggota site yang sama.
- Koreksi manual atas urgensi dan kategori hasil AI. Nilainya disimpan dengan penanda manual supaya **penarikan berikutnya tidak menimpanya** — koreksi manusia bertahan.
- Tulis draft balasan (maks. 4.000 karakter) dan tambah catatan tindak lanjut. Riwayat catatan tampil di panel yang sama.
- Setiap perubahan yang benar-benar terjadi dicatat beserta pelakunya dan waktunya. Riwayat bisa menjawab bukan cuma "apa yang berubah", tapi "siapa yang mengubahnya".

*Jadikan Tiket* — `POST Voc/reviewEscalate`
- Tiket dibentuk lewat pipeline OneBox yang sudah ada, bukan INSERT sendiri — jadi tiket hasil eskalasi tunduk pada aturan routing, masuk laporan, dan bisa ditugaskan seperti tiket mana pun.
- Jenis tiket dipastikan TT3 (Media Monitoring) saat tiketnya lahir.
- Klasifikasi otomatis: subject dan deskripsi diisi agar tiket terbaca tanpa membuka layar VoC, dan kategorinya diambil dari hasil analisis bila master Category punya padanannya.
- Hasil analisis yang sudah ada ditempelkan ke tiket baru, jadi sentimen dan kategori tidak perlu menunggu penarikan berikutnya.

*Eskalasi ke PIC* — `POST Voc/reviewForward`
- Bila site berlangganan kanal WhatsApp OneBox, pesan dikirim lewat kanal itu. Bila tidak, eskalasi **tetap tercatat** dan layar menerima tautan `wa.me` sebagai jalur mundur. Yang tidak boleh terjadi adalah eskalasi gagal diam-diam hanya karena kanalnya tidak ada.
- Bisa disertai catatan untuk PIC.

*Hapus review* — `POST Voc/reviewDelete`
- Penghapusan bersifat lunak: ditandai pada Meta review, dan tiketnya ikut dikedaluwarsakan supaya tidak tertinggal sebagai pekerjaan tanpa review. Data asli tetap utuh di Crawler System.

**Keputusan produk yang perlu diketahui QA dan pengguna**

1. **Balasan disimpan sebagai draft, belum terkirim ke Google.** Pengiriman sungguhan butuh Google Business Profile API dengan OAuth dan belum tersedia. Menuliskannya sebagai balasan terkirim akan membuat layar melaporkan ulasan sudah dibalas padahal pelanggan tidak pernah menerima apa pun — itu lebih berbahaya daripada belum ada fiturnya. Penulis draft tetap dicatat sebagai dasar jejak maker/reviewer di tahap berikutnya.
2. **Review tidak otomatis menjadi tiket.** Tidak semua ulasan perlu ditindaklanjuti; memaksa semuanya menjadi tiket membuat antrean kerja penuh hal yang tidak dikerjakan siapa pun. Review masuk dulu sebagai bahan, manusia yang memutuskan mana yang naik jadi pekerjaan.
3. Karena itu, **status, prioritas, penanggung jawab, dan catatan baru bisa diisi setelah review dijadikan tiket.** Layar menyampaikan ini sebagai instruksi, bukan sebagai error.

**Di luar cakupan tiket ini** — bergantung pada kontrak Crawler, diusulkan sebagai tiket lanjutan

- Foto lampiran ulasan belum ada di kontrak Crawler sama sekali.
- `owner_response_time` (jam balasan pemilik) belum ditangkap Crawler, sehingga laporan waktu tanggap balasan belum bisa dihitung.
- Jejak *reviewer id* pada balasan — *maker* sudah tercatat, tahap persetujuan belum ada.
- Penyeragaman istilah "Cabang" menjadi "Lokasi" dan penyiapan Group di atas lokasi.

> Salin sampai baris di atas.

---

## 2. Development Resolve Date

**Isi: `19/Aug/26`**

Nilai `14/Aug/26` yang terisi sekarang tidak cocok dengan bukti di repo — commit terakhir pada branch ini `80331b1a` bertanggal **19/Aug/26**, dan merge PR terakhir (#57) juga setelah tanggal itu. Kalau kebijakan tim mengisi kolom ini dengan tanggal *merge ke `feature/voc`*, pakai tanggal merge PR #57. Kalau diisi tanggal *pekerjaan terakhir selesai*, pakai 19/Aug/26. Keduanya bukan 14/Aug/26.

---

## 3. Comment

> Salin mulai baris berikut.

**Cara uji (dev):** Media Monitoring › Voice of Customer › Kelola Review.

Alur yang perlu dilewati QA:

1. Muat layar, pastikan empat KPI terisi dan ketiga mode tampilan (List / Pie / Bar) menampilkan populasi yang sama.
2. Terapkan penyaring secara berlapis — rentang tanggal + sentimen + rating — lalu pastikan jumlah di footer tabel ikut berubah.
3. Buka satu review. Cek tautan **Review Asli** membuka ulasan yang benar di Google Maps.
4. Koreksi urgensi dan kategori, simpan. Jalankan penarikan baru untuk cabang itu, lalu pastikan **koreksi manual tidak tertimpa**.
5. Tekan **Jadikan Tiket**. Pastikan tiket lahir dengan jenis TT3, subject dan deskripsinya terisi otomatis, dan penanda `TIKET` muncul di baris tabel.
6. Baru setelah itu isi status, prioritas, penanggung jawab, dan catatan. Sebelum jadi tiket, layar memang seharusnya menolak dengan instruksi menekan "Jadikan Tiket" dulu — itu perilaku yang benar, bukan bug.
7. Eskalasi ke PIC. Pada site tanpa kanal WhatsApp, yang benar adalah eskalasi tetap tercatat dan muncul tautan `wa.me` — bukan pesan gagal.
8. Hapus satu review, pastikan hilang dari daftar dan tiketnya ikut kedaluwarsa.

**Tiga hal yang berpotensi dilaporkan sebagai bug padahal bukan:**

- Tombol **Balas** mati pada lokasi yang akun Google Business-nya belum ditandai kepemilikannya. Penandanya diatur di layar Lokasi, bukan di layar ini.
- **Balasan tersimpan sebagai draft**, tidak terkirim ke Google. Ini batasan yang disengaja sampai integrasi Google Business Profile API tersedia.
- **Status, prioritas, penanggung jawab, dan catatan terkunci** sebelum review dijadikan tiket. Ini alur yang dirancang, bukan kegagalan simpan.

**Ketergantungan lintas sistem:** foto lampiran dan `owner_response_time` menunggu perubahan di sisi Crawler System dan tidak bisa diselesaikan dari OneBox saja.

> Salin sampai baris di atas.

---

## Lampiran — endpoint yang menopang layar ini

| Endpoint | Fungsi |
|---|---|
| `Voc/reviewsData` | Daftar review, KPI, dan data grafik |
| `Voc/reviewDetail` | Isi panel detail satu review |
| `Voc/reviewManage` | Status, prioritas, PIC, koreksi analisis, draft balasan, catatan |
| `Voc/reviewEscalate` | Jadikan review sebagai tiket (TT3 + klasifikasi otomatis) |
| `Voc/reviewForward` | Teruskan ke PIC cabang (kanal WhatsApp / fallback wa.me) |
| `Voc/reviewAssignees` | Daftar kandidat penanggung jawab dalam site |
| `Voc/reviewDelete` | Hapus lunak di OneBox, data asli tetap di Crawler |
