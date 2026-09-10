# Notulen: Review CEO — Layar Ulasan & Workspace Reviewer — 2026-09-08

**Sumber:** transkrip audio `Jalan STM Mandiri No. 68 6.m4a` (TurboScribe).
**Pemberi arahan:** Pa Indra (CEO).
**Scope Sayyid:** halaman **Ulasan** + **workspace reviewer**.

> **Catatan tentang sumber.** Transkripnya otomatis dan banyak salah dengar
> ("radio" untuk *rating*, "trace mode" untuk *threshold*, "cloud chart" untuk
> *word cloud*, "Rating Snapchat" untuk *rating snapshot*). Bagian yang gua
> tafsirkan dari konteks ditandai **[tafsir]**. Yang ditandai begitu perlu
> dikonfirmasi ke Pa Indra sebelum dikerjakan, bukan diasumsikan benar.
> Rekamannya juga terpotong di menit ke-30 — ada kemungkinan arahan lanjutan
> tidak tertangkap.

---

## Keputusan

1. **Hanya tiga layar. Titik.** — "Gue butuh tiga ini, gak butuh yang lain.
   Selesaikan tiga ini." Tidak ada layar baru sampai ketiganya beres.
   1. **Screen Reviewer** (operator)
   2. **Screen Workspace Supervisor / Kepala Cabang** (pimpinan)
   3. **Profil satu cabang**
2. **Satu orang satu layar.** — "Jadi satu orang kerjain, sempurnakan yang tadi.
   Satu orang sempurnakan yang dashboard-nya. Satu orang sempurnakan yang
   profile satu side."
3. **Tidak boleh digabung jadi satu layar.** — "Setiap orang kebutuhannya beda."
   Reviewer ≠ bos ≠ kepala cabang.
4. **Reviewer adalah OPERATOR, bukan analis.** — "Reviewer tuh gue butuh Review,
   Reply." Jangan diberi analisa dan jangan diberi informasi terlalu banyak.
5. **Rating harus ada DUA versi, dan versi Google DISIMPAN — bukan dihitung.**
   Ini keputusan terkeras di rapat, diulang berkali-kali. Rinciannya di bawah.
6. **Tidak boleh scroll untuk melihat isi utama.** — "Jangan scroll-scroll."
   Dalam satu layar penuh, ulasan **dan** tabelnya harus terlihat bersamaan.
7. **Sedikit filter, sedikit aksi.** — "Jangan banyak filter, jangan banyak
   action, jangan banyak macam-macam." Tujuan layar adalah *coaching*: orang
   langsung tahu apa yang harus dikerjakan.
8. **Sesudah rapat dengan CEO, tim wajib berkoordinasi** menentukan layar mana
   yang dirombak siapa, supaya waktunya efektif.

---

## Keputusan besar: rating dua versi

Ini bagian yang paling banyak diulang dan paling berisiko kalau salah tafsir.

**Yang dilarang:** menyajikan rating hasil rata-rata perhitungan kita sendiri
seolah-olah itu rating cabangnya.

> "Lu ga boleh baca rating itu tuh dirata-ratakan disini."
> "Yang mau dimonitor itu bukan kalkulasi lu berapa jadinya rata-rata. Tapi di
> dalam Google."

**Yang diminta — dua angka berdampingan:**

| | Sumber | Sifat |
| --- | --- | --- |
| **Rating rata-rata kita** | dihitung dari ulasan yang kita tarik, per periode | kalkulatif, boleh |
| **Rating Google** | angka yang Google tampilkan **pada saat penarikan** | **disimpan**, tidak boleh dihitung |

**Mekanismenya:** setiap kali scheduler menarik, simpan rating Google apa adanya
beserta timestamp-nya.

> "Ketika lu ambil data itu, rating Google-nya berapa? Timestamp-nya berapa? Itu
> harus disimpen. Bukan di kalkulasi."
> "Lu punya scheduler, lu ada historinya. Pada saat itu rating-nya berapa?
> Rating Google-nya harus disimpen."

**Alasannya — risiko reputasi, bukan estetika:**

> "Karena lu akan dimarahin. 'Gue gak akan akurat, lu Google-nya dari mana?'
> Dibuka misalkan 3,0. Hasil hitungan kita 4."

Yang dilihat konsumen adalah angka Google. Itu yang wajib bisa kita tunjukkan.

**Keberatan yang diangkat tim di rapat:** saat ini baru 50 ulasan per lokasi yang
ditarik, jadi hitungan kita memang belum mewakili. Jawaban Pa Indra: justru
karena itu jangan dihitung dari awal — simpan angka Google-nya.

**Status di kode:** ini persis pekerjaan DNGO19-3529 (`VocRatingLog` +
kolom `GoogleRating`). Sudah ada di `feature/voc`, **migrasinya belum jalan di
dev** (lihat Follow-up).

---

## Arahan per layar

### Layar 1 — Reviewer (SCOPE SAYYID)

**Peran:** operator. Baca ulasan, balas, teruskan. Bukan tempat analisa.

**Tata letak**

- **Tidak boleh scroll halaman.** Dalam satu layar penuh harus terlihat
  ulasannya **dan** tabelnya sekaligus.
- Yang boleh bergulir hanya **badan tabel** dan **isi modal/panel detail** —
  kepala layar (KPI, tab, filter) tetap terkunci di tempat.
  > "Ini yang di lock. Ini jangan. Ini harus scroll."
- Tabel konten sekarang posisinya terlalu ke bawah; harus naik.
- Kalau tidak cukup, **kecilkan komponennya**, jangan tambah scroll.
  > "Lu atur supaya gak di scroll. Jadi dikecilin."

**KPI**

- Terlalu banyak dan belum jelas.
- **Gabungkan dimensi waktu jadi SATU kartu**: hari ini / bulan ini / tahun ini
  di dalam satu kotak, disusun **vertikal** (mirip kartu rating, tapi vertikal).
  > "Hari ini bulan ini tuh gak perlu sampai 1 informasi begitu. Tapi
  > digabungin... satu kotak itu. Today berapa, minggu ini berapa."
- Kartu KPI tetap **bisa diklik sebagai filter**, dan bentuknya kecil.
  > "Itu tetap bisa di filter juga? Iya... jadi kecil dan jadi button buat filter."
- Sentimen (positif / netral / negatif) jadi tombol filter kecil.
- KPI Google diletakkan **paling atas**. **[tafsir]**

**Definisi negatif — DUA indikator**

> "Ada 2 indikatornya. Mau dijalankan oleh AI atau memang berdasarkan bintang."

- Bintang **< 4** ⇒ negatif.
- **Atau** AI menilai negatif, **meskipun bintangnya 4**.
  > "Kadang-kadang ngomong 4 tapi komennya gak enak... Jadi kalo komentar yang
  > negatif itu jadi negatif, meskipun bintangnya 4."

Konsekuensinya: sentimen tidak boleh murni dari bintang, dan tidak boleh murni
dari AI — harus gabungan OR.

**Filter**

- Filter yang jarang dipakai **jangan ditaruh di layar utama** — sembunyikan di
  panel "Filter lainnya" seperti pola OneBox yang sudah ada di kanan.
  > "Filter itu akan sering digunakan gak? Kalo gak sering digunakan jangan di
  > situ. Lebih baik di-hide aja."

**Tab Cabang / Kompetitor**

- Jangan memakan satu baris sendiri di posisi sekarang.
  > "Kompetitor sama cabang jangan bikin kerjaan yang begini ya... karena udah
  > keambil satu baris."
- **Arahan Sayyid:** pindahkan ke samping **Analisis Batch**, hapus dari posisi
  sekarang.

**Alert cabang di bawah rating**

- **Arahan Sayyid: hapus dari UI Ulasan.**
- Catatan: kebutuhan "berapa cabang di bawah standar" **tidak hilang** — ia
  pindah jadi widget di Layar 2 (workspace pimpinan). Jangan sampai ikut
  terbuang.

**Ambang rating (threshold)**

- Jangan diatur per lokasi; taruh sebagai **widget**.
  > "Kalau bisa sih di widget aja... di situ tuh berapa banyak aja yang di buat
  > threshold-nya."

**Detail ulasan / balasan**

- Balasan diletakkan **di atas**, menempel dengan ulasannya, supaya terbaca
  menyambung.
  > "Balesannya di atas. Jadi nyambung bacanya gitu."
- Ada alert "lokasi belum terhubung" untuk kondisi belum *go official*.
- Hindari duplikasi informasi di panel detail.

---

### Layar 2 — Workspace Supervisor / Kepala Cabang (BUKAN scope Sayyid)

Dicatat supaya tidak hilang, dan supaya batas scope-nya jelas.

**Semua dalam satu pandangan, tanpa scroll.**
> "Harus dalam satu pandangan, gak bisa lo harus scroll gitu."

Isi yang diminta:

1. **Widget: berapa cabang di bawah standar** — ini *critical issue* utama bos.
   Angkanya bisa diklik untuk melihat daftarnya.
2. **Daftar cabang diurutkan dari rating paling rendah.**
3. **Ulasan terbaru yang negatif** — di sebelah kanan atau di bawah.
4. **Word cloud masalah** — misalnya "koneksi lambat", "layanan", "mahal";
   diklik untuk tahu berapa banyak yang menyebut hal itu. **[tafsir: transkrip
   menulis "cloud chart"]**
5. Target rating harus **rasional** — angka 4,9 dipertanyakan sendiri oleh Pa
   Indra. Perlu disepakati.
6. **Cakupan mengikuti peran:** bos pusat melihat semua cabang, kepala wilayah
   hanya wilayahnya.
   - Tim menyampaikan **RBAC belum tersedia**; Pa Indra menjawab bahwa yang
     diminta sekarang adalah **desain layarnya dulu**, bukan menunggu RBAC.

---

### Layar 3 — Profil satu cabang (BUKAN scope Sayyid)

- Bisa dilihat semua orang, terutama kepala cabang bersangkutan.
- Isinya: seluruh rating, ulasan negatif, balasan, ulasan terbaru, word cloud
  masalah.
- **Tren** — di sini rata-rata **boleh** dihitung: Januari rata-rata berapa,
  Februari berapa, dan seterusnya.
- Tren juga bisa **per objek/topik**: klik "layanan" lalu lihat trennya
  Januari–Februari–Maret.

---

## Ringkasan poin lain

- Pa Indra menegaskan layar-layar ini akan **dipakai demo**, jadi lebih baik
  tampil meski belum sempurna daripada tidak bisa ditampilkan sama sekali.
  > "Di AI itu kadang-kadang cuma effort dua hari, tapi nggak bisa nampilin,
  > fail tuh. Tapi kalau bisa nampilin, ada kesempatan."
- Kalau fungsinya belum ada, **HTML-nya dulu** yang dibereskan.
- Keluhan berulang: tim membuat terlalu banyak layar dan menunjukkan layar yang
  berbeda-beda di tiap sesi review, sehingga review sebelumnya tidak pernah
  tuntas.
  > "Kalian terlalu banyak bikin screen."
  > "Kemarin nge-review yang lain, sekarang dikasih screen yang lain."
- Statistik dimensi dinilai bagus, **tetapi bukan untuk manajemen** — manajemen
  tidak bisa langsung tahu apa yang harus dilakukan dari situ.
- Contoh data yang dibahas saat rapat: MyRepublic (Grand Slipi?, dsb),
  ~14 ulasan, ada yang rating 1,2 dari 50 ulasan. **[tafsir: nama cabang tidak
  terdengar jelas di transkrip]**

---

## Action item

### Scope Sayyid — Layar Ulasan & Workspace Reviewer

- [ ] **ULS-01** Hilangkan scroll halaman: dalam satu layar penuh, ulasan dan
      tabelnya terlihat bersamaan. Kepala layar terkunci, hanya badan tabel yang
      bergulir. — @sayyid
- [ ] **ULS-02** Gabungkan KPI hari ini / bulan ini / tahun ini jadi **satu
      kartu vertikal**. — @sayyid
- [ ] **ULS-03** Kecilkan kartu KPI dan jadikan tombol filter yang bisa diklik.
      — @sayyid
- [ ] **ULS-04** Naikkan posisi tabel konten. — @sayyid
- [ ] **ULS-05** Hapus alert "cabang di bawah rating" dari UI Ulasan. — @sayyid
- [ ] **ULS-06** Pindahkan tab Cabang/Kompetitor ke samping **Analisis Batch**,
      hapus dari posisi sekarang. — @sayyid
- [ ] **ULS-07** Sembunyikan filter yang jarang dipakai ke panel "Filter
      lainnya". — @sayyid
- [ ] **ULS-08** Definisi negatif jadi dua indikator: `bintang < 4` **OR** AI
      menilai negatif. Perlu dicek apakah backend sudah begini. — @sayyid
- [ ] **ULS-09** Panel detail: balasan TIDAK diletakkan menempel di atas, dekat
      ulasannya, supaya terbaca menyambung. — @sayyid
- [ ] **ULS-10** Panel detail hanya bergulir di badannya; buang duplikasi
      informasi. — @sayyid
- [ ] **ULS-11** Ambang rating disajikan sebagai widget, bukan pengaturan per
      lokasi. — @sayyid **[perlu konfirmasi: widget ini di layar Ulasan atau di
      workspace pimpinan?]**
- [ ] **ULS-12** KPI Google di paling atas. — @sayyid **[tafsir, perlu
      konfirmasi]**

### Di luar scope Sayyid — dicatat agar tidak hilang

- [ ] **WS-01** Workspace supervisor: widget "berapa cabang di bawah standar",
      bisa diklik. — @belum ditentukan
- [ ] **WS-02** Workspace supervisor: daftar cabang urut rating terendah +
      ulasan negatif terbaru, satu pandangan tanpa scroll. — @belum ditentukan
- [ ] **WS-03** Word cloud masalah, bisa diklik untuk melihat jumlah penyebutan.
      — @belum ditentukan
- [ ] **PRF-01** Profil satu cabang: rating, negatif, balasan, terbaru, word
      cloud, tren bulanan, tren per topik. — @belum ditentukan
- [ ] **RAT-01** Simpan rating Google apa adanya pada setiap penarikan
      terjadwal, beserta timestamp — bukan hasil kalkulasi. Sudah ada di
      DNGO19-3529; **migrasinya belum jalan di dev.** — @sayyid
- [ ] **KOOR-01** Koordinasi antar-tim: tentukan siapa mengerjakan layar yang
      mana sebelum mulai. — @tim

---

## Follow-up / pertanyaan terbuka

1. **Target rating yang rasional berapa?** Pa Indra sendiri mempertanyakan 4,9
   dan minta angka yang masuk akal. Belum ada angka final.
2. **Rentang waktu bawaan** — bos ingin melihat "dari awal sampai sekarang",
   tetapi juga menyebut "sebulan terakhir" sebagai default. Perlu dipastikan
   mana yang jadi bawaan, dan bagaimana kedua rating (kita vs Google)
   ditampilkan berdampingan pada tiap rentang.
3. **Widget threshold letaknya di mana** — layar Ulasan (reviewer) atau
   workspace pimpinan? Reviewer adalah operator, jadi kemungkinan besar bukan di
   layar reviewer, tapi ini belum ditegaskan.
4. **"Belum dianalisa" masih perlu ditampilkan atau tidak?** Sempat
   dipertanyakan di rapat, tidak ada keputusan.
5. **RBAC belum ada.** Desain layar pimpinan tetap dikerjakan, tetapi pembatasan
   akses per peran belum bisa diterapkan. Perlu kejelasan siapa yang menyediakan
   dan kapan.
6. **Migrasi kolom rating Google belum jalan di dev** — selama belum,
   perbandingan rating Google akan kosong dan terlihat seperti fitur rusak,
   meskipun kodenya sudah berpenjaga.
7. **Rekaman terpotong di menit ke-30.** Kalau ada arahan sesudah itu, belum
   tertangkap di notulen ini.
8. **Nama cabang MyRepublic yang disebut** tidak terdengar jelas di transkrip;
   perlu dikonfirmasi kalau mau dijadikan contoh demo.
