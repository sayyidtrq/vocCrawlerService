# Meeting Notes — VoC Super Dashboard & Reviewer Workspace

- **Tanggal:** 9 September 2026 (per instruksi saat pencatatan — perlu dicatat: metadata file audio sumber tertanggal 2026-09-04, jadi kalau ada ketidakcocokan tanggal, cek ulang mana yang benar)
- **Sumber:** transkrip audio WhatsApp, auto-transcribe via TurboScribe — `WhatsApp Audio 2026-09-04 at 3.01.02 PM.pdf`
- **Topik:** review desain Super Dashboard VoC + Workspace Reviewer, bersama stakeholder ("Pak" — nada bicara mengarah ke leadership/product owner) dan tim dev.
- **Sifat dokumen ini:** transkrip sumbernya percakapan lisan yang di-STT otomatis — banyak kalimat terpotong, subjek tidak selalu jelas siapa bicara. Raw insight di bawah adalah interpretasi terbaik dari isi; bagian yang ambigu ditandai eksplisit **[perlu klarifikasi]**, bukan ditebak sebagai fakta.

---

## Raw Insight

### 1. Prinsip inti Super Dashboard: "apa yang terjadi SEKARANG", bukan cuma statistik

Stakeholder eksplisit membedakan dua jenis dashboard:
- **Dashboard status real-time** — jawab "apa yang terjadi sekarang": berapa negatif, berapa yang belum direspons, di cabang mana. Ini yang dia mau untuk Super Dashboard.
- **Dashboard statistik/agregat** — yang katanya "udah dibikin di awal" (versi sebelumnya) — dianggap oke tapi tidak cukup, karena tidak langsung memicu tindakan ("gue gak langsung harus ngapain gitu").

> Kutipan kunci: *"Konsep membuat dashboard itu, satu, orang itu akan melihat apa yang terjadi sekarang... Jadi di depan itu tolong super dashboard tadi itu dibaca. Jadi dashboard itu gak usah banyak."*

Prinsip tambahan yang disebut eksplisit: **"coaching planning"** — kalau breakdown-nya kebanyakan, langsung ketahuan dari 1 layar itu jelek. Dashboard harus ringkas, bukan menambah section terus-terusan.

### 2. Widget yang diminta ada di Super Dashboard (urutan sesuai permintaan)

1. **Rating per cabang, diurutkan dari yang PALING RENDAH duluan** — bukan alfabetis, bukan berdasarkan jumlah review. Tujuannya biar langsung kelihatan "cabang paling bermasalah" tanpa perlu sort manual.
2. **Jumlah pesan negatif — hari ini / minggu ini / bulan ini** — dan ini **bukan cuma angka**, isi pesan aslinya harus ditampilkan langsung di widget itu (siapa, cabang mana, isi keluhannya apa). Tujuannya: pimpinan tidak perlu klik ke layar lain untuk tahu apa masalahnya.
3. **Indikator "belum direspons"** — kalau ada review negatif yang belum dibalas, tandai **merah** (bukan warna netral) supaya kebaca sebagai "tidak responsif".
4. Klik pada item negatif → langsung ke detail lokasi + isi pesan lengkap.
5. Bagian "prioritas response tindak lanjut" **dikurangi porsinya** — cukup satu widget kecil, jangan berlebihan, dipindah ke bawah (bukan prioritas utama layar).

### 3. Dua jenis rating — JANGAN dicampur jadi satu angka

Ini poin yang paling banyak diulang-ulang di transkrip (nampaknya versi sebelumnya menggabungkan ini jadi ambigu):

| Jenis rating | Definisi | Kapan dipakai |
|---|---|---|
| **Rating total/asli dari Google** | Akumulasi dari awal, tidak berubah oleh filter tanggal | Selalu tampil sebagai angka referensi |
| **Rating rata-rata sesuai filter periode aktif** | Berubah kalau user pilih "bulan ini", "minggu ini", dst | Untuk analisis periode tertentu |

> *"Ada dua rating di situ, di dalam satu biji [lokasi]... Google Review total rating, rata-rata rating dari semuanya, sama rating yang di-filter sesuai dengan yang gue lagi filter."*

Kedua angka ini harus **kelihatan berdampingan**, bukan salah satu saja — supaya tidak salah baca "rating hari ini 5" padahal rating total cabang itu cuma 3.

### 4. Query harus on-demand, bukan "launch semua di awal"

> *"Semua di-query? Nggak ada yang di depan juga. Jangan semua di-query. Query-nya harus on-demand."*

Implikasi: data berat (misal breakdown per lokasi, daftar lengkap) **tidak boleh** ikut ke-load bersamaan waktu halaman dibuka — harus dipicu saat dibutuhkan (klik/expand), bukan default eager-load semua cabang.

### 5. Workspace Reviewer (layar untuk yang membalas review)

- **Default view = "belum direview" saja.** Reviewer tidak perlu filter manual — begitu buka, yang tampil memang cuma kerjaan yang harus dikerjakan.
  > *"Jangan pake filter lagi, karena kita udah tau kebutuhan dia. Dia tuh akan kerja atas sesuatu yang harus gua kerjain."*
- Pisahkan tab/state: **belum direview** vs **sudah direview**.
- Tugas reviewer ada **dua**: (1) klasifikasi kategori, (2) membalas (reply).
- Reply harus bisa jalan baik dari **akun official maupun non-official**.
- **UX reply/klasifikasi harus in-place**, bukan modal berlapis yang harus ditutup-buka berulang ("close-close-close-close"). Idealnya: klik satu item → aksi (klasifikasi + reply) terjadi di panel yang sama, ada tombol "Next" untuk lanjut ke item berikutnya tanpa keluar dari flow.
- Info yang perlu tampil per item: header ringkas, status, tombol klasifikasi, tombol reply — jangan berlebihan informasinya.

### 6. Entitlement AI & Ticket — HARUS terpisah per modul, bukan bundel

Ini insight teknis paling penting untuk arsitektur benefit/kuota:

- Modul **VoC**, **AI**, dan **Ticket (follow-up)** adalah **3 hal yang bisa dibeli terpisah** secara komersial.
  > *"Yang beli modul VoC, satu, belum tentu ada AI-nya... Belum tentu ada ticket-nya."*
- Kalau site tidak beli AI → seluruh fitur AI (klasifikasi otomatis, saran) **harus hilang total**, bukan disembunyikan/di-disable saja.
- Kalau site tidak beli modul Ticket OneBox → opsi "follow up via ticket" juga **harus hilang**, karena review tidak akan pernah masuk sebagai ticket kalau modul itu tidak dibeli.
- **Perlu parameter admin per-site** (disebut di "Customer Benefit" / admin parameter) untuk menentukan:
  1. Apakah AI aktif untuk site ini?
  2. Apakah follow-up lewat ticket aktif untuk site ini?
- **Perlu juga parameter pilihan AI engine** — disebut ada pola serupa sudah ada di modul OCR ("Om Omul... untuk AI OCR, di parameter itu ada engine-nya AI yang mau dipakainya apa"). Ke depan VoC AI juga harus punya pilihan: pakai AI berbayar pihak ketiga, atau model internal sendiri.
- **Soal representasi kuota unlimited**: jangan pakai angka besar seperti "1.000.000" untuk mewakili unlimited — harus benar-benar direpresentasikan sebagai "Unlimited" di UI, supaya tidak membingungkan.
  > *"Jangan pakai sejuta. Tapi memang unlimited aja."*

### 7. Klasifikasi sentimen — pertanyaan terbuka soal source of truth **[perlu klarifikasi]**

Ada pertanyaan langsung dari stakeholder yang sepertinya **belum terjawab tuntas** di meeting ini:

> *"Sekarang kita tau nggak negative sama positive itu... ditentukan oleh apa? Ada engine-nya, [atau] kalau pasal active, akumulasi bintang sama isi... Algoritmanya ini akurat, nggak?"*

Jawaban di transkrip terdengar tidak pasti/terpotong ("reuse dulu... lebih tradisional"). Yang jelas dikonfirmasi:
- **"Belum direspons/dibalas" ≠ "belum dianalisa"** — dua status yang berbeda, dan dari nada tanya-jawabnya, pembedaan ini sempat membingungkan di forum sendiri, bukan cuma stakeholder.
- Perlu didokumentasikan dengan jelas: sentimen ditentukan dari **rating bintang (algoritma tradisional)** atau dari **engine AI/klasifikasi**, dan tingkat akurasinya seperti apa.

### 8. Status staging & rencana uji coba multi-site (fakta, bukan requirement baru)

- Staging sudah punya **6-7 fitur utama** (disebut termasuk setup lokasi), tapi **testing masih berjalan**.
- Stakeholder berencana coba pasang di **site lain** (disebut nama "Astra"/kampanye lain) untuk validasi — karena tiap site dianggap unik/beda karakteristik dari site pertama.

### 9. Detail layout tambahan (Super Dashboard)

- Info rating (2 jenis di atas) ditaruh di **kolom kiri**, dibuat ringkas **1 baris** saja per info — jangan sampai kelihatan seperti dashboard statistik yang berat.
- Dashboard versi "pimpinan cabang" = sama seperti Super Dashboard, tinggal **difilter per cabang** — bukan layar terpisah.
- Workspace **Reviewer** dan workspace **Management** dinyatakan eksplisit sebagai dua fokus screen yang beda kebutuhan — jangan disatukan asumsinya.

---

## To-Do

### A. Super Dashboard
- [ ] Redesain widget ringkasan: rating per cabang diurutkan **ascending** (rating terendah di atas), bukan default alfabetis/ID
- [ ] Tampilkan **dua rating berdampingan** per cabang: rating total (Google, akumulatif) vs rating rata-rata sesuai filter periode aktif — pastikan label membedakan keduanya dengan jelas di UI
- [ ] Widget pesan negatif (hari ini/minggu ini/bulan ini) menampilkan **isi pesan asli**, bukan cuma angka — termasuk cabang & tanggal
- [ ] Item negatif yang belum direspons diberi **indikator merah** (bukan warna netral)
- [ ] Klik pada item negatif → navigasi ke detail lokasi + isi pesan lengkap
- [ ] Pangkas porsi widget "prioritas response tindak lanjut" jadi satu widget kecil saja, posisi dipindah ke bawah
- [ ] Audit semua query di halaman dashboard — pastikan data berat (breakdown per lokasi dsb) **on-demand**, bukan eager-load saat halaman dibuka
- [ ] Pastikan dashboard "pimpinan cabang" reuse komponen Super Dashboard yang sama + filter cabang, bukan halaman terpisah

### B. Workspace Reviewer
- [ ] Buat default view = daftar **belum direview** saja (tanpa perlu filter manual dari user)
- [ ] Pisahkan state/tab **belum direview** vs **sudah direview**
- [ ] Redesain interaksi klasifikasi + reply jadi **in-place** (satu panel), hilangkan pola modal berlapis yang harus ditutup-buka
- [ ] Tambahkan tombol **"Next"** untuk lanjut ke item berikutnya tanpa keluar dari flow aksi
- [ ] Pastikan reply berfungsi dari akun **official maupun non-official**

### C. Entitlement / Benefit (AI & Ticket per modul)
- [ ] Definisikan parameter admin per-site: **AI aktif/tidak** dan **follow-up via Ticket aktif/tidak** — cek kaitannya dengan `Benefit`/`SiteBenefit` yang sudah ada di OneBox
- [ ] Pastikan kalau AI tidak dibeli, seluruh UI fitur AI (klasifikasi otomatis, saran) **hilang total** dari tampilan reviewer, bukan cuma disabled
- [ ] Pastikan kalau modul Ticket tidak dibeli, opsi follow-up via ticket **hilang total**, dan review tidak pernah coba dibuatkan ticket
- [ ] Tambahkan parameter pilihan **AI engine** (pihak ketiga berbayar vs internal) — cek pola existing di parameter OCR sebagai referensi implementasi
- [ ] Ganti representasi kuota unlimited dari angka besar (mis. "1.000.000") jadi label **"Unlimited"** eksplisit di semua tempat yang menampilkan kuota

### D. Perlu klarifikasi ke stakeholder (belum bisa langsung dieksekusi)
- [ ] **Sumber kebenaran sentimen**: apakah dari algoritma rating bintang (tradisional) atau dari engine AI/klasifikasi — dan seberapa akurat itu dianggap cukup? Jawaban di meeting ini belum tuntas.
- [ ] Konfirmasi ulang definisi status **"belum dianalisa"** vs **"belum direspons"** ke seluruh tim — supaya tidak ambigu lagi di internal sebelum dibawa lagi ke stakeholder.
- [ ] Konfirmasi timeline uji coba di site kedua ("Astra"/kampanye) — apakah menunggu staging selesai testing dulu atau paralel.

### E. Follow-up proses
- [ ] Selesaikan testing fitur yang sudah ada di staging (6-7 fitur, termasuk setup lokasi) sebelum menambah scope baru dari meeting ini
- [ ] Jadwalkan sesi lanjutan khusus membahas poin C (source of truth sentimen) karena ini belum terjawab tuntas di sesi ini
