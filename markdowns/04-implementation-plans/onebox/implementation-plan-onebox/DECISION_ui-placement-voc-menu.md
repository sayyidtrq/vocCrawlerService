# Decision Log — Penempatan UI/Menu VOC (2026-07-14)

> Dokumen ini WAJIB dibaca sebelum mengerjakan RI-10, RI-11, RI-12, RI-15 (semua task UI/menu di [00_INDEX.md](00_INDEX.md)).
> Ini bukan diskusi terbuka — ini keputusan yang sudah diambil (pending 1 baris konfirmasi ke lead Agung, lihat §5). Kalau ada instruksi lain yang bertentangan, dokumen dengan tanggal LEBIH BARU yang menang.

---

## 1. Dilema Awal (dari Sayyid)

Saat staging belum ada data review sama sekali, muncul blocker:

> "Karena di staging belum ada data sama sekali, belum kebayang mapping page pada VoC System ke dashboard Onebox Mediamonitoring ini. Ide-nya apakah buat menu VOC sendiri dulu, baru pelan-pelan diintegrasikan ke dalam menu yang ada — atau gimana? Kepikiran buat menu baru supaya bisa secara berkala menunjukkan key screen FE kepada stakeholder (CEO)."

Dua opsi yang dipertimbangkan:
- **Opsi A:** Operasi langsung di dalam `MediamonitoringController` (tambah action di controller/modul existing).
- **Opsi B:** Bikin menu & controller VOC yang berdiri sendiri (`VocController`), baru nanti (atau tidak pernah) digabung ke Mediamonitoring.

---

## 2. Keputusan

**Opsi B — bikin menu/controller VOC yang dedicated.**

Ketentuannya:
- **Controller baru:** `VocController` (atau nama serupa, TBD saat implementasi RI-10), TERPISAH dari `MediamonitoringController`.
- **Menu baru** di sidebar (bukan submenu Mediamonitoring), didaftarkan lewat `Menu` + `RoleMenu` seperti biasa (RI-15).
- **TAPI: sumber data TETAP tabel `Ticket`** (mengikuti keputusan lead Agung: "data di-pull ke table Ticket, sesuai yang sudah berjalan"). Controller baru ini **membaca** Ticket (filter MediaId review), bukan bikin tabel/penyimpanan sendiri.
- **Pattern query/UI di-reuse** dari `MediamonitoringController` (query sentiment, struktur chart, dsb) — dicontek, bukan diwarisi lewat inheritance atau modifikasi file itu.

---

## 3. Alasan (3 poin, dipakai kalau ditanya lead/CEO)

1. **Demoability ke CEO.** FE benchmark ("Pusat Pantau Review Indonesia" — peta risiko cabang, SLA follow-up, prioritas cabang) secara visual & fungsional beda jauh dari UI news-monitoring Mediamonitoring. Memaksakan ke dalam Mediamonitoring akan menghasilkan UI yang jelek/lambat dan sulit dipakai demo berkala ke stakeholder. Menu dedicated memungkinkan menunjukkan key screen yang mendekati FE asli kapan saja.
2. **Keamanan kode.** `MediamonitoringController` adalah file besar (3000+ baris). Menambah fitur produk baru di dalamnya jauh lebih berisiko (regresi, konflik) dibanding controller baru yang bersih.
3. **Tetap konsisten dengan arahan lead.** Instruksi Agung: *"data di-pull ke table Ticket, lewat/menyerupai modul Mediamonitoring."* Menu VOC yang membaca `Ticket` dan mereplikasi pattern Mediamonitoring memenuhi kata "menyerupai" — tanpa harus secara fisik menjadi bagian dari file yang sama.

---

## 4. Reframe Penting: Integrasi Terjadi di Layer DATA, Bukan di Layer MENU

Kekhawatiran "nanti perlu diintegrasikan ke menu yang ada" tidak perlu ada. **Titik integrasi yang sebenarnya adalah data mengalir ke `Ticket`** (RI-05: `VoiceOfCustomerSystemTask`), bukan menu-nya menyatu secara fisik dengan Mediamonitoring. Begitu menu VOC membaca dari `Ticket`, ia SUDAH terintegrasi secara data. Menu boleh tetap terpisah selamanya. Menggabungkan UI secara fisik ke Mediamonitoring (kalau pun terjadi) adalah **optimasi opsional di masa depan**, bukan requirement.

**Dampak ke rencana implementasi:** ini me-reframe RI-10/RI-11/RI-12 (lihat [00_INDEX.md](00_INDEX.md)):
- ~~"tambah action di `MediamonitoringController`"~~ → **"buat `VocController` baru yang meniru pattern Mediamonitoring"**
- File target di masing-masing plan (RI-10_ui-list.md, RI-11_ui-detail.md, RI-12_dashboard-voc.md) perlu disesuaikan: ganti referensi "MediamonitoringController.php [ubah]" menjadi "VocController.php [baru]".

---

## 5. "Staging Kosong" Bukan Blocker Nyata

VoC System **lokal** Sayyid sudah punya ~75 review nyata (terverifikasi dari dashboard lokal `localhost:3000/dashboard`). Jadi:
- **Untuk scaffold UI awal / demo cepat:** seed manual 5–10 baris `Ticket` di DB dev (lihat pola di RI-05 §5) — cukup untuk menunjukkan kerangka menu ke CEO.
- **Untuk data asli:** begitu RI-04 (client) + RI-05 (ingest task) selesai, 75 review lokal itu bisa ditarik masuk ke `Ticket` — menu langsung terisi data nyata.

Urutan demo yang disarankan: **menu shell → dashboard baca Ticket (data seed) → isi via ingest task (RI-04/05) → tunjukkan ke CEO → iterasi.** Tidak perlu menunggu staging terisi data dari pihak lain.

---

## 6. Status & Langkah Selanjutnya

**Status: keputusan diambil, PENDING konfirmasi 1-baris ke Agung.**

Kalimat yang perlu dikirim Sayyid ke Agung sebelum mulai menulis kode UI:

> "Pak, untuk UI VOC saya rencana bikin menu/controller VOC tersendiri yang baca dari tabel Ticket dan reuse pattern Mediamonitoring (biar aman & gampang di-demo ke CEO), bukan langsung nambah di dalam MediamonitoringController. Sesuai kan Pak?"

- **Kalau Agung setuju** → lanjut sesuai dokumen ini, tidak perlu diskusi ulang.
- **Kalau Agung minta di dalam Mediamonitoring** → kembali ke Opsi A: update dokumen ini (jangan hapus, tambahkan entri baru bertanggal di atas) dan sesuaikan RI-10/11/12 kembali ke "tambah action di MediamonitoringController".

**Belum boleh mulai menulis kode UI (RI-10 dst.) sebelum konfirmasi ini didapat**, kecuali Sayyid secara eksplisit memutuskan untuk jalan duluan dengan risiko rework.
