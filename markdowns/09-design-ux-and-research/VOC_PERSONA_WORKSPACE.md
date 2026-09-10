---
title: "VoC — Persona, Workspace, dan Pemetaan Role"
date: 2026-08-26
type: design-doc
project: Voice of Customer
branch: feature/DNGO19-3511_Workspace-Branch-Manager
status: rancangan — mapping role belum diimplementasi
sumber: "[[2026-08-21-voc-progress-review]]"
tags:
  - voc
  - persona
  - workspace
  - ui-ux
---

# VoC — Persona, Workspace, dan Pemetaan Role

Turunan dari [[2026-08-21-voc-progress-review]]. Menjawab satu kritik yang diulang
tiga kali di sesi 21 Agustus:

> *"Ini ngomongin UI UX. Kita harus tahu dulu, siapa sih pengguna ini? Lu harus
> kenal betul siapa usernya, buat siapa screen ini."*

---

## Ringkasan keputusan

1. **Empat persona** ditetapkan: Staf Humas, Kepala Cabang (PIC lokasi), Kepala
   Wilayah, CEO/Direktur.
2. **Dua dari empat bisa dipetakan ke role OneBox yang sudah ada.** Dua sisanya
   tidak punya padanan, dan **memaksakan padanan akan merusak arti role yang
   sudah dipakai modul lain**. Analisisnya di bawah.
3. **Fase ini tidak menyentuh hak akses.** Persona hanya mengubah **tampilan** —
   layar mana yang dibuka dan grafik apa yang disajikan. Akses menu dan
   penyaringan data di backend dibiarkan apa adanya, sesuai arahan.
4. **Dashboard Google Review dipakai ulang**, bukan dibuat ulang. Yang berubah
   per persona adalah **cakupan, urutan, dan penekanan** — bukan sumber datanya.

---

## Bagian 1 — Empat persona

Tiap persona ditulis dengan urutan yang sama: pekerjaan hariannya, keputusan yang
harus ia ambil, dan pertanyaan yang layar ini wajib jawab. Kalau sebuah widget
tidak membantu menjawab pertanyaan itu, ia tidak masuk ke layarnya.

### P1 · Staf Humas / PR / Contact Center

| | |
|---|---|
| **Ritme** | per jam, sepanjang hari kerja |
| **Cakupan** | semua lokasi |
| **Keputusan** | review mana yang saya tangani berikutnya |

**Pekerjaannya:** memonitor review yang masuk, mengklasifikasi, membalas, dan
merekap kalau diminta atasan.

**Pertanyaan yang harus dijawab layar:**
- Apa yang masuk hari ini dan belum saya sentuh?
- Mana yang paling mendesak bintang 1, atau yang sudah lama menganggur?
- Kategori apa yang paling buruk ?
- Mana ulasan yang perlu dieskalasikan ?
- Berapa sisa pekerjaan saya?

**Masalah yang ada sekarang:**
- Dashboard menyajikan **agregat bulanan**, sementara pekerjaannya harian. Angka
  "Total Review 518" tidak memberi tahu apa yang harus dikerjakan berikutnya.
- Tidak ada **antrean kerja**. Layar Ulasan adalah daftar arsip, bukan daftar
  tugas — urutannya kronologis, bukan berdasarkan yang perlu ditangani.
- Tidak terlihat **mana yang belum diklasifikasi**, padahal itu justru
  pekerjaannya.

> [!important] Untuk persona ini, angka harus berarti "sisa pekerjaan", bukan "total data"
> Ini pembalikan yang paling penting di seluruh dokumen. Humas tidak butuh tahu
> ada 518 review; ia butuh tahu ada **23 yang belum ia sentuh**. Widget yang sama
> bisa menampilkan dua angka itu, dan hanya satu di antaranya yang membuat orang
> tahu harus berbuat apa.

---

### P2 · Kepala Cabang / PIC Lokasi

| | |
|---|---|
| **Ritme** | harian sampai mingguan |
| **Cakupan** | **satu lokasi** — miliknya |
| **Keputusan** | apa yang harus saya perbaiki di cabang saya minggu ini |

**Pekerjaannya:** menjaga rating cabangnya, menindaklanjuti keluhan yang menunjuk
ke unitnya.

**Kutipan langsung dari sesi:**
> *"Kepala rumah sakit kan sebetulnya nggak perlu ngeliatin review-review yang
> detail kayak gitu. Harusnya melihat sebuah workspace-nya."*

**Pertanyaan yang harus dijawab layar:**
- Cabang saya sedang bagus atau memburuk , dibanding target dan dibanding bulan lalu?
- Yang kasih bintang 1 minggu ini, keluhannya apa?
- Masalah apa yang paling sering muncul di tempat saya?

**Masalah yang ada sekarang:**
- **Tidak ada layar yang hanya berisi cabangnya.** Ia harus membuka dashboard
  semua lokasi lalu menyaring sendiri — dan penyaringan itu harus diulang tiap
  kali membuka.
- Angka di dashboard **tidak bisa diklik**. *"Lu bisa klik yang bintang 1 apa
  aja? Nggak bisa, Pak."*
- Ia dipaksa memakai layar yang dirancang untuk orang yang mengurus semua cabang.

---

### P3 · Kepala Wilayah

| | |
|---|---|
| **Ritme** | mingguan |
| **Cakupan** | beberapa cabang dalam satu wilayah |
| **Keputusan** | cabang mana yang harus saya bina lebih dulu |

**Pekerjaannya:** membina cabang-cabang di wilayahnya; menyiapkan bahan briefing.

**Kutipan langsung:**
> *"Gue gak terlalu peduli yang udah di atas rata-rata. Yang gue perhatikan adalah
> siapa yang di bawah rata-rata yang harus gue molding. Dan masalahnya apa?"*

**Pertanyaan yang harus dijawab layar:**
- Cabang mana yang di bawah standar?
- Masalah umum di cabang-cabang itu apa?
- Apa yang harus saya bicarakan di briefing besok?

**Masalah yang ada sekarang:**
- **Tidak ada layar banding antar cabang.** Dashboard Profile per Daerah
  menampilkan satu daerah, bukan membandingkan.
- Yang di atas target dan di bawah target ditampilkan setara, padahal
  perhatiannya hanya untuk yang di bawah.
- Tidak ada **kategori masalah dominan per cabang** — jadi ia tahu cabang mana
  yang jelek, tapi tidak tahu jeleknya kenapa.

> [!note] Persona ini bukan "pengguna aplikasi", tapi "penyiap rapat"
> Keluaran layarnya bukan klik berikutnya, melainkan **bahan bicara**. Ini
> mengubah rancangan: yang dibutuhkan bukan interaktivitas dalam, melainkan satu
> layar yang bisa dibaca utuh dan diceritakan ulang.

---

### P4 · CEO / Direktur

| | |
|---|---|
| **Ritme** | bulanan |
| **Cakupan** | seluruh perusahaan |
| **Keputusan** | ke mana saya arahkan sumber daya kuartal ini |

**Pertanyaan yang harus dijawab layar:**
- Kita membaik atau memburuk?
- Dibanding kompetitor, kita di mana?
- Masalah terbesar perusahaan apa?

**Kutipan yang mendefinisikan layarnya:**
> *"Sekarang 4,4 bagus gak? Jelek! Soalnya bulan lalu masih 4,7 terus turun 4,6
> sekarang 4,4."*
> *"Kalau kompetitor lo 3,5? Bunda cuma 3,5, Eka hospital cuma 3,2, gue 4,5
> paling tinggi dong."*

**Masalah yang ada sekarang:**
- **Angka rating disajikan tanpa pembanding.** 4,4 berdiri sendiri tidak bermakna.
- Tiga benchmark yang ditetapkan di sesi — target, kompetitor, periode lalu —
  **tidak pernah muncul berdampingan** di layar mana pun.

> [!important] Satu angka, tiga pembanding
> Ini inti layar CEO. Rating tanpa pembanding adalah trivia; rating dengan tiga
> pembanding adalah keputusan. Kalau hanya satu komponen yang dibangun untuk
> persona ini, ini komponennya.

---

## Bagian 2 — Pemetaan ke role OneBox yang sudah ada

Ini bagian yang diminta dijelaskan dulu sebelum diimplementasi.

### Yang ditemukan di sistem

Ada empat role yang memegang menu VoC di site 169:

| Id | Code | Nama | Menu VoC | Menu non-VoC | User |
|---|---|---|---|---|---|
| 17 | `userNews` | User Mediamonitoring | 20 | 83 | 10 |
| 15 | `Pimpinan Pusat` | Pimpinan Pusat | 13 | 85 | 8 |
| 22 | `reviewer` | Reviewer | 10 | 57 | 2 |
| 23 | `kontributor` | Kontributor | 6 | 66 | 3 |

### Temuan 1 — `userNews` bukan persona, melainkan saklar modul

`LoginController::isUserNews()` memakai role ini untuk **menentukan modul mana
yang dibuka setelah login**:

```php
if ($userNews === 'userNews')       → redirect('Mediamonitoring/')
else if ($userNews === 'userBanca') → redirect('Bancassurance/')
else                                → redirect('#/')   // modul case
```

**Konsekuensinya besar:** siapa pun yang harus mendarat di Media Monitoring
**wajib** memegang `userNews`. Jadi kita tidak bisa memberi Kepala Cabang role
lain sebagai gantinya — ia akan terlempar ke modul case dan tidak pernah melihat
VoC sama sekali.

### Temuan 2 — konvensi yang sudah berjalan: `userNews` + satu role persona

Kombinasi role nyata di site 169:

| Kombinasi | Jumlah user |
|---|---|
| `Pimpinan Pusat` + `userNews` | 7 |
| `userNews` + `kontributor` | 2 |
| `userNews` + `reviewer` | 2 |
| `kontributor` sendirian | 1 ← kemungkinan salah setelan, tidak bisa masuk MM |

Polanya sudah ada dan konsisten: **`userNews` = izin masuk modul, role kedua =
peran orangnya.** Rancangan persona sebaiknya mengikuti pola ini, bukan
membuat pola baru.

### Temuan 3 — `reviewer` dan `kontributor` adalah peran alur berita, bukan hierarki organisasi

Menu khas masing-masing, di luar VoC:

- **`reviewer`** — Top Aktor, Statistik Berita, Sumber Berita, Trend
- **`kontributor`** — Berita Negatif, Galeri Berita, Kontributor Informasi,
  Ontology, Komparasi, Report SLA

Keduanya berbicara tentang **pemrosesan berita di Media Monitoring**, bukan
tentang cabang atau wilayah. Memakai `reviewer` untuk "Kepala Cabang" berarti
satu role punya dua arti berbeda di dua modul — dan orang yang menyetelnya nanti
tidak punya cara tahu arti mana yang dimaksud.

Ditambah lagi: keduanya membawa **57–66 menu non-VoC**. Memberikannya ke seorang
kepala cabang berarti memberi akses ke seluruh perkakas Media Monitoring yang
tidak ada urusannya dengan pekerjaannya.

### Hasil pemetaan

| Persona VoC | Role OneBox | Putusan |
|---|---|---|
| **P1 Staf Humas** | `userNews` (tanpa role kedua) | ✅ **Pas.** Ini memang baseline operator MM |
| **P4 CEO/Direktur** | `Pimpinan Pusat` + `userNews` | ✅ **Pas.** Namanya persis, dan sudah dipakai 7 user |
| **P2 Kepala Cabang** | — | ❌ **Tidak ada padanan** |
| **P3 Kepala Wilayah** | — | ❌ **Tidak ada padanan** |

> [!warning] Dua persona tidak punya rumah, dan jangan dipaksakan
> Godaan terbesarnya adalah memakai `reviewer` untuk Kepala Cabang dan
> `kontributor` untuk Kepala Wilayah — keduanya kosong-kosong dipakai, jumlah
> user-nya sedikit, dan "kelihatannya muat".
>
> Itu keputusan yang akan menghantui. Kedua role itu **sudah punya arti** di
> Media Monitoring, dipegang user nyata, dan membawa puluhan menu yang tidak
> relevan. Menumpanginya berarti setiap perubahan hak akses di satu modul
> diam-diam mengubah modul lain — dan sebabnya tidak akan tertulis di mana pun.

### Rekomendasi

**Fase 1 — sekarang, tanpa menyentuh role sama sekali.**

Persona menjadi **lapisan presentasi**, bukan lapisan otorisasi:

- Persona diturunkan dari role bila memang jelas:
  - punya `Pimpinan Pusat` → **P4 CEO**
  - punya `userNews` saja → **P1 Humas**
- Untuk P2 dan P3 yang belum punya role, sediakan **pemilih persona eksplisit**
  di layar Workspace. Nilainya disimpan di sesi.
- Semua persona **tetap melihat menu dan data yang sama** — persis seperti
  arahan. Yang berbeda hanya susunan dan penekanan layarnya.

Keuntungannya: workspace bisa dibangun dan didemokan **minggu ini**, tanpa
menunggu keputusan role yang melibatkan modul lain.

**Fase 2 — nanti, kalau pembagiannya sudah terbukti dipakai.**

Buat dua role baru yang artinya tidak bertabrakan dengan apa pun:

| Role baru | Untuk | Perlu juga |
|---|---|---|
| `voc_branch_head` | Kepala Cabang | pengikatan user → lokasi |
| `voc_region_head` | Kepala Wilayah | pengikatan user → wilayah, butuh master wilayah (`NEW09`) |

Keduanya tetap **berpasangan dengan `userNews`**, mengikuti konvensi yang sudah
berjalan.

> [!note] Kenapa fase 2 tidak dikerjakan sekarang
> Bukan karena sulit, melainkan karena **belum ada datanya**. Pengikatan user ke
> lokasi belum ada, master wilayah per site belum ada (`NEW09` belum dikerjakan),
> dan daftar unit organisasi Hermina belum diterima. Membuat role sekarang berarti
> membuat role kosong yang tidak bisa menyaring apa pun.

---

## Bagian 3 — Rancangan layar per persona

### Prinsip: pakai ulang, jangan bangun ulang

Layar yang sudah ada tetap jadi sumber. Yang berubah per persona adalah
**cakupan, urutan, dan penekanan**.

| Layar yang sudah ada | P1 Humas | P2 Kepala Cabang | P3 Kepala Wilayah | P4 CEO |
|---|---|---|---|---|
| **Dashboard Google Review** (`dashboard.volt`, 3.455 baris) | dipakai — cakupan semua lokasi | **dikunci ke 1 lokasi** | dikunci ke wilayahnya | dipakai penuh + benchmark |
| **Ulasan** (`reviews.volt`) | **layar utama**, default "belum diklasifikasi" | disaring ke lokasinya, dibuka dari drill-down | jarang | tidak |
| **Dashboard Profile** (`dashboardprofile.volt`) | tidak | profil cabangnya | per wilayah | ringkasan |
| **Workspace** (`workspace.volt`, 821 baris) | **antrean kerja** | **workspace cabang** ← branch ini | **banding cabang** | **ringkas eksekutif** |

Sumber datanya tetap `Voc/dashboardData`, `Voc/reviewsData`, `Voc/workspaceData`
yang sudah ada. Persona menambah **parameter cakupan**, bukan endpoint baru.

---

### P1 — Antrean Kerja Humas

```
┌─────────────────────────────────────────────────────────────┐
│  Antrean Saya                            [Hari ini ▾]       │
├──────────────┬──────────────┬──────────────┬────────────────┤
│ Belum        │ Belum        │ Bintang 1-2  │ Menunggu       │
│ diklasifikasi│ dibalas      │ hari ini     │ >24 jam        │
│    23        │    11        │     4        │      7         │
│  ← diklik    │  ← diklik    │  ← diklik    │   ← diklik     │
├──────────────┴──────────────┴──────────────┴────────────────┤
│  Daftar tugas — diurut mendesak, bukan kronologis            │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ ★☆☆☆☆  Hermina Depok · 2 jam lalu                     │  │
│  │ "Antre 3 jam, satpam judes"      [Klasifikasi] [Balas] │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Grafik:** sengaja **minimal**. Satu sparkline masuknya review 7 hari, itu saja.
Persona ini butuh daftar, bukan analisa — grafik di sini hanya menambah hal untuk
dilewati.

**Urutan antrean:** bintang menaik, lalu umur menurun. Bintang 1 berumur 2 jam
mendahului bintang 3 berumur 2 hari.

---

### P2 — Workspace Kepala Cabang ← **diimplementasi di branch ini**

```
┌──────────────────────────────────────────────────────────────┐
│  Hermina Depok                      [Bulan ini ▾]            │
│  ┌────────────────────┐  ┌────────────────────────────────┐  │
│  │   4,4              │  │  Sebaran bintang — bisa diklik │  │
│  │   ▼ 0,3 vs bln lalu│  │  ★5 ███████████████  120       │  │
│  │   Target 4,5  ✗    │  │  ★4 ████████          64       │  │
│  │   ── di bawah ──   │  │  ★3 ███               21       │  │
│  └────────────────────┘  │  ★2 ██                12       │  │
│                          │  ★1 ████              31  ←    │  │
│                          └────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────┤
│  Masalah teratas di cabang ini    │  Review terbaru          │
│  Kebersihan      ████████  18     │  ★1 "Antre lama…"        │
│  Waktu tunggu    ██████    14     │  ★2 "Parkir penuh…"      │
│  Layanan satpam  ████       9     │  ★5 "Dokter ramah…"      │
└──────────────────────────────────────────────────────────────┘
```

**Empat komponen, tidak lebih:**

1. **Rating cabang + tiga penanda** — angka besar, arah perubahan vs bulan lalu,
   dan posisi terhadap target. Inilah tiga benchmark dalam bentuk paling ringkas.
2. **Sebaran bintang, bisa diklik** — menjawab langsung *"Lu bisa klik yang
   bintang 1 apa aja?"*. Klik → layar Ulasan tersaring bintang itu + cabang ini.
3. **Masalah teratas** — bar horizontal kategori. Ini yang menjawab "harus
   memperbaiki apa".
4. **Review terbaru** — 5 baris, tanpa tabel penuh. Kalau ia mau semuanya, ada
   tautan ke layar Ulasan.

**Yang sengaja TIDAK ada:** tabel review lengkap, filter berlapis, perbandingan
antar cabang. Semua itu milik persona lain, dan kehadirannya di sini justru
membuat layarnya kembali jadi dashboard umum.

---

### P3 — Banding Cabang (Kepala Wilayah)

```
┌──────────────────────────────────────────────────────────────┐
│  Wilayah Jawa Barat        Rata-rata 4,3 · Target 4,5        │
├──────────────────────────────────────────────────────────────┤
│  Di bawah target — perlu dibina                              │
│  Hermina Bekasi   3,9  ▼  ███████░░░  Kebersihan, Antre      │
│  Hermina Bogor    4,1  ▼  ████████░░  Parkir, Satpam         │
│  Hermina Depok    4,4  ▬  █████████░  Kebersihan             │
│  ─────────────────────────────────────────────────────────   │
│  Di atas target                                     [buka ▾] │
└──────────────────────────────────────────────────────────────┘
```

**Diurut menaik** — yang paling bermasalah di atas. Yang sudah di atas target
**dilipat**, bukan disembunyikan: ia tetap bisa dibuka, tapi tidak memakan
perhatian. Ini terjemahan langsung dari *"gue gak terlalu peduli yang udah di
atas rata-rata"*.

Tiap baris membawa **kategori masalah dominan** — supaya layar ini bisa dibaca
utuh sebagai bahan briefing tanpa perlu mengklik.

---

### P4 — Ringkas Eksekutif (CEO)

```
┌──────────────────────────────────────────────────────────────┐
│  Rating Perusahaan                                           │
│         4,4                                                  │
│   ┌──────────────┬──────────────┬───────────────────┐        │
│   │ vs Target    │ vs Kompetitor│ vs Bulan Lalu     │        │
│   │ 4,5   ✗ -0,1 │ 3,5  ✓ +0,9  │ 4,7   ✗ -0,3      │        │
│   └──────────────┴──────────────┴───────────────────┘        │
├──────────────────────────────────────────────────────────────┤
│  Tren 6 bulan          │  Masalah terbesar perusahaan        │
│  4,7 ─╮                │  Kebersihan     ████████  142       │
│  4,6   ╰─╮             │  Waktu tunggu   ██████     98       │
│  4,4     ╰──           │  Layanan        ████       61       │
└──────────────────────────────────────────────────────────────┘
```

**Tiga benchmark berdampingan** adalah komponen utamanya — bukan pelengkap. Tanpa
ketiganya, angka 4,4 tidak memberi tahu apa pun.

---

## Bagian 4 — Aturan visual

Mengikuti design system VoC yang sudah ada (`Voc/style.volt`) — **tidak ada token
baru**:

| Token | Nilai | Dipakai untuk |
|---|---|---|
| Primary | `#00BCD4` | aksen, nilai positif, garis aktif |
| Ink | `#26313f` | teks utama, angka besar |
| Muted | `#5a6b85` | label sekunder |
| Label | `#8a97a8` | label kapital kecil |
| Bintang | `#f5a623` | **hanya** bintang |
| Negatif | `#d0342b` | di bawah target, sentimen negatif |
| Netral | `#c7d2de` | bar tanpa makna sentimen |
| Garis | `#dde3ea` `#eef1f5` | pembatas, latar panel |

Kelas yang dipakai ulang: `.voc-wrap` `.voc-panel` `.voc-panel-h` `.voc-kpis`
`.voc-kpi` `.voc-btn` `.voc-barrow` `.voc-empty` `.voc-muted` `.voc-table`.

**Yang dilarang** — sudah jadi kesepakatan di modul ini:
- latar transparan / efek stabilo
- `border-left` berwarna di atas latar tint
- warna baru di luar tabel di atas
- bintang selain kuning
- AI SLOP : GABOLE AI SLOP

---

## Bagian 5 — Rencana implementasi

| Tahap | Isi | Branch |
|---|---|---|
| **1** | Penyelesai persona + pemilih persona (presentasi saja) | `DNGO19-3511` ← ini |
| **2** | **Workspace Kepala Cabang (P2)** | `DNGO19-3511` ← ini |
| **3** | Antrean Kerja Humas (P1) | branch baru |
| **4** | Banding Cabang (P3) | `NEW08`, butuh master wilayah `NEW09` |
| **5** | Ringkas Eksekutif (P4) | branch baru, butuh benchmark kompetitor |
| **6** | Role `voc_branch_head` & `voc_region_head` + penyaringan data | fase 2, setelah pembagian terbukti |

Branch ini mengerjakan **tahap 1 dan 2** — sesuai namanya, Workspace Branch
Manager. Tiga persona lain dirancang di dokumen ini supaya strukturnya sudah
siap, tetapi dikerjakan di branch tersendiri agar PR-nya tetap bisa di-review.

---

## Pertanyaan terbuka

- [ ] **Bagaimana user diikat ke lokasi?** P2 butuh tahu "cabang saya yang mana".
      Belum ada relasi user→lokasi. Sementara: dipilih manual di pemilih persona.
- [ ] **Target rating resmi tiap site** — 4,5 masih contoh percakapan.
- [ ] **Benchmark kompetitor**: rata-rata semua kompetitor, atau satu per satu?
- [ ] **Master wilayah** belum ada (`NEW09`) — P3 tertahan olehnya.

---

## Tautan

- [[2026-08-21-voc-progress-review]] — notulen sumber
- [[2026-08-25-voc-grooming-sprint]] — pembagian kerja
- [[VOC_CREDENTIALS]] — akun uji per persona
