# Revisi CEO — Voice of Customer

**Tanggal notulensi:** 7 Agustus 2026
**Cakupan dokumen:** P0 `manage_review_action` (layar Kelola Review + Detail & Tindak Lanjut Ulasan)
**Status:** disetujui untuk dikerjakan

> Nama berkas aslinya diminta `REVISI_CEO_07/08/2026.md`. Garis miring adalah
> pemisah folder, jadi tidak bisa dipakai pada nama berkas; dipakai tanda hubung.

---

## 1. Ringkasan notulensi

Notulensi CEO membicarakan enam hal, bukan satu daftar acak. Dipisahkan supaya
yang bukan P0 tidak ikut terseret ke sprint ini.

| Tema | Inti |
|---|---|
| **Sumber VoC** | VoC = inbound + CS + telesurvey + Google Review. Google Review pecah dua: **official** (login, bisa reply) dan **non-official** (crawl, tidak bisa reply). Harus ada flag pembedanya. |
| **Engine & skala** | Scheduler multi-akun, engine naik ke gateway, uji stabilitas saat banyak company crawling bersamaan — target akhirnya ditawarkan ke rumah sakit. |
| **Kelola ulasan** | Layar list dirapikan: filter, widget, kolom, ikon. Reply, eskalasi, create ticket. Review asli beserta fotonya terlihat. Ada jejak siapa yang menjawab. |
| **Dashboard & statistik** | Peta masalah, tren per bulan (tetap digambar 0 kalau kosong, bukan "tidak ada data"), monitoring lokasi punya periode start–end, ringkasan AI dibuang. |
| **Struktur data** | Group di atas lokasi (Hermina → wilayah → lokasi). Duplikasi by message id + tanggal + pengirim dijadikan index. |
| **Profil & laporan** | Dashboard per-site dan export PDF untuk eksekutif: alamat, PIC, rekap bintang, tren per masalah, persentase response, SLA. |

---

## 2. Keputusan yang sudah diambil

| # | Pertanyaan | Keputusan |
|---|---|---|
| 1 | Tombol "Hapus" ikut jadi primary? | **Tidak.** Tetap merah — tindakannya destruktif dan warnanya adalah peringatan, bukan gaya. |
| 2 | Istilah pengganti "Cabang" | **Tetap "Cabang".** |
| 3 | Reply official sebelum OAuth Google siap | **Simpan draft** dulu, tombol tetap terlihat. |

> **Catatan untuk keputusan #2.** Notulensi CEO menyebut eksplisit *"Cabang diganti
> bahasanya jadi objek lokasi atau apa gitu, pokoknya jangan cabang."* Keputusan
> internal saat ini mempertahankan "Cabang". Perlu dikonfirmasi ulang ke CEO
> sebelum demo — kalau ternyata beliau tetap menolak, perubahannya murni istilah
> di layar dan murah dikerjakan belakangan.

---

## 3. Tasklist P0 — `manage_review_action`

### 3.1 Kerangka layar

| # | Item | Kondisi sekarang | Ketergantungan |
|---|---|---|---|
| 91 | Tab **List / Pie chart / Bar chart** tepat di bawah card | Belum ada, hanya tabel | — |
| 92 | Card sentimen **di-grouping**; tiap card punya filter rating bintang + jumlah lokasi | Positif/Netral/Negatif masih tiga card sejajar | Angka sudah ada di `reviewsData.summary` |
| 94 | **Date picker start/end** + preset hari ini, kemarin, minggu ini, bulan ini | Belum ada di layar Ulasan | Pola backend sudah ada & teruji di Dashboard |
| 95 | Ikon aksi **EDIT → REVIEW**; semua tombol **primary `#00BCD4`** | Ikon pensil; "Simpan" hijau, "Jadikan Tiket" menyimpang | Hapus tetap merah (keputusan #1) |
| 96 | **Hilangkan AI slop**: latar transparan & container stabilo | Kotak kuning "Tindak Lanjut", kotak abu "Isi Ulasan" | — |

### 3.2 KPI dan kolom tabel

| # | Item | Kondisi sekarang | Ketergantungan |
|---|---|---|---|
| 93 | KPI **Total review, Review hari ini, Review bulan ini** | Belum ada; CEO menyebut ini *"lebih penting"* | Wajib dihitung atas **waktu ulasan**, bukan waktu tiket |
| 93 | KPI bintang **bisa diklik** untuk memfilter tabel | Belum ada | — |
| 97 | Kolom **sudah dibalas / belum dibalas** + filternya | Data **sudah tersimpan**, belum ditampilkan | Tidak perlu integrasi baru |
| 98 | **Cuplikan isi ulasan 2 baris** di tabel | Tabel tidak menampilkan isi ulasan sama sekali | `review_text` sudah dikembalikan API |

### 3.3 Detail & tindak lanjut

| # | Item | Kondisi sekarang | Ketergantungan |
|---|---|---|---|
| 99 | **Flag official / non-official** | **Belum ada di mana pun** | Menentukan kapan tombol Reply aktif |
| 100 | Tombol **Reply** di kanan profil user | Belum ada | Butuh #99; simpan draft dulu (keputusan #3) |
| 101 | Panel kanan **review asli selengkap mungkin** + tombol lihat aslinya | Belum ada | `external_review_id`, `reviewer_profile_url` tersedia |
| 104 | **Eskalasi ke PIC**, termasuk jalur WhatsApp | Belum ada | PIC & nomor WA sudah tersimpan per lokasi |
| 105 | **Create Ticket** dengan klasifikasi otomatis "follow up Google review" | Tombol ada, klasifikasi belum | Tiket VoC tetap `TypeId = TT3` |
| 106 | **Maker id & reviewer id** pada balasan | Belum ada | Ini yang membuat kolom status balasan berguna |
| 107 | Istilah "Cabang" (lihat keputusan #2) & rencana **Group di atas lokasi** | Card KPI masih "Cabang 4" | Struktur group butuh keputusan model data |

---

## 4. Temuan dari data nyata

Diukur atas 87 review pada dump lokal, bukan perkiraan.

### Yang ternyata gratis

| Temuan | Dampak |
|---|---|
| `owner_response_text` sudah disimpan `VocProvider` ke Meta dan **terisi 70 dari 87 (80%)** | Status "sudah dibalas" adalah pekerjaan **menampilkan**, bukan integrasi. Jangan diperkirakan besar. |
| Backend rentang tanggal sudah ada & teruji di Dashboard | Pakai ulang `dashboardRange()` + `fetchReviews($rentang)`. Sudah menangani bind parameter, batas akhir `< besoknya`, rentang terbalik, dan tanggal palsu seperti `2026-02-31`. |
| `review_text` sudah dikembalikan `reviewsData` | Cuplikan 2 baris murni pekerjaan UI. |

### Blocker yang harus diakui sekarang

| # | Temuan | Akibat |
|---|---|---|
| 103 | `owner_response_time` **terisi 0 dari 87** padahal teksnya terisi 70 | **SLA response tidak bisa dihitung sama sekali.** Crawler mengambil teks balasan tapi tidak waktunya. Perlu perbaikan sisi Crawler. |
| 102 | **Foto lampiran ulasan tidak ada di kontrak API sama sekali** | `reviewer_photo_url` adalah foto **profil reviewer**, bukan foto ulasan — dan itu pun kosong di seluruh data uji. Jangan memasang foto profil lalu menyebutnya foto ulasan. Perlu field baru di Crawler. |
| 99 | `source` bernilai `selenium_google_maps` pada **87 dari 87** | Itu **metode crawl**, bukan penanda kepemilikan akun. Tidak bisa dipakai sebagai flag official/non-official. |
| 100 | Reply official ke Google | Butuh **Google Business Profile API + OAuth**. Integrasi terpisah, bukan pekerjaan layar ini. |

---

## 5. Di luar P0

Dicatat supaya tidak hilang, tetapi **tidak** dikerjakan pada sprint ini.

- Scheduler pengujian multi-akun
- Engine dinaikkan ke gateway agar scheduler dapat berjalan
- Uji stabilitas saat banyak company melakukan crawling
- Dashboard: peta masalah, statistik dilengkapi, parameter utama untuk Pak Indra
- Monitoring lokasi dengan kolom periode start–end
- Ringkasan insight AI dibuang, diganti pengelompokan tingkat kritis
- Grafik klasifikasi positif/negatif dengan rentang waktu dan tren per bulan
- Mode list dan mode grafik pada kotak monitoring lokasi
- Struktur **Group** di atas lokasi (butuh keputusan model data lebih dulu)
- Index duplikasi berdasarkan message id + tanggal + pengirim
- Dashboard profil per-site dan export PDF untuk eksekutif, termasuk SLA response

---

## 6. Urutan pengerjaan yang disarankan

Didahulukan yang tidak menunggu keputusan siapa pun dan langsung terlihat saat demo.

1. **#95, #96** — ikon, warna tombol, buang stabilo. Murni tampilan, risiko terendah.
2. **#98, #97** — cuplikan ulasan dan status balasan. Datanya sudah ada.
3. **#93, #94** — KPI hari ini/bulan ini dan filter periode. Backend sudah tersedia.
4. **#92, #91** — grouping card dan tab grafik.
5. **#101, #105, #104, #106** — detail: review asli, create ticket, eskalasi, jejak penjawab.
6. **#99, #100** — flag official dan tombol reply (draft).
7. **#102, #103** — diserahkan ke sisi Crawler, dikerjakan paralel.

---

## 7. Riwayat

| Tanggal | Perubahan |
|---|---|
| 7 Agustus 2026 | Dokumen dibuat dari notulensi CEO; keputusan #1–#3 dicatat; 17 task P0 didaftarkan (#91–#107) |
