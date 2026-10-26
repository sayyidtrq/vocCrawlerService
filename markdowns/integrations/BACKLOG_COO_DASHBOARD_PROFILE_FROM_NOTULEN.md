# Backlog — Dashboard COO & Profile (dari notulensi CEO)

**Sumber:** `WhatsApp Audio 2026-10-21 at 5.24.38 PM.pdf` (transkrip TurboScribe)
**Tiket induk:** DNGO19-3607 (VOC : UI Dashboard Improvement)
**Status:** draf analisis, belum dikonfirmasi. Kode OneBox **tidak** dibaca (WSL mati; OneBox belum terpasang di laptop ini), jadi bagian "Implementasi" adalah hipotesis, bukan temuan.

---

## 0. Baca dulu: batas dan kualitas sumber

1. **Transkrip terpotong.** Footer TurboScribe: "file longer than 30 minutes". Audio berhenti di tengah pembahasan crawling Google Business. Sisa audio (kemungkinan feedback soal dashboard/profile) **tidak ada** di PDF.
2. **Isi bukan daftar revisi layar.** Isinya presentasi konsep **"OneBox Radar"** (omni-channel: masalah + peluang + tindak lanjut) lalu arahan dari seorang senior/mentor soal cara berpikir *input → proses → output* untuk CEO. Kata "dashboard COO" dan "profile" tidak disebut eksplisit; pemetaan ke keduanya di bawah adalah **tafsiran saya** (ditandai `[tafsir]`).
3. **Salah dengar transkripsi** yang saya koreksi dari konteks: "anemone" = anomali, "rikasan" = ringkasan, "kelembung nomali" ≈ gelembung/bubble anomali, "Uber" = kemungkinan nama klien contoh/ OneBox sendiri (tidak jelas), "5.100.000 agen" tidak bisa dipakai.
4. **Sudah ada** `decisions/REVISI_CEO_07-08-2026.md` yang memuat revisi CEO sebelumnya (termasuk dashboard per-site, export PDF, peta masalah, tren per bulan). Dokumen ini hanya mencatat yang **baru** dari notulen ini dan merujuk ke sana untuk yang sudah ada.

---

## 1. Ringkasan pesan CEO / presenter

| Tema | Inti |
|---|---|
| Masalah vs peluang | Dua keluaran utama: **anomali (masalah)** dan **peluang**. Dilihat dari sudut pandang aktor internal (CEO), bukan pelanggan. |
| Sumber | ±9 channel OneBox (message→ticket, telephony, outbound campaign, WA broadcast, CSAT/survey, review, media monitoring, QA agent). Data **tersebar**, format dan sentimen beda-beda. |
| Cadence | Sekarang masalah baru ketahuan di **rapat mingguan**; maunya bisa dilihat **harian**. |
| Aksi | Anomali/peluang harus bisa diteruskan: tiket, eskalasi, campaign, survey **dari satu layar** ("super workspace"). Ada **bukti dampak** sebelum/sesudah. |
| Peluang → penjualan | Peluang ujungnya **data prospect** yang masuk ke Sales Management / modul Outbound, karena akuisisi prospect baru mahal. |
| Kerangka CEO | Empat area yang dibantu: penjualan naik, efisiensi/produktivitas, layanan lebih baik, tim kompeten. |

---

## 2. Poin yang perlu diimprove

Kolom **Fase**: **1** = bisa dikerjakan dengan data VoC (Google Maps) yang sudah ada; **2** = butuh engine/ perhitungan baru tapi masih data VoC; **3** = butuh channel lain OneBox (omni-channel), di luar repo/ tiket ini.

### A. Dashboard COO (tampilan eksekutif)

| # | Poin | Dari notulen | Fase |
|---|---|---|---|
| A1 | **Ringkasan kondisi semua lokasi dalam ±1 menit** (kartu status per lokasi: sehat / waspada / kritis). | "kondisi semua lokasi dari 1 menit singkat" | 1 |
| A2 | **Top anomali** dan **Top peluang**, masing-masing berskor, dengan tren **8 minggu**. | "top anomali, top peluang dengan skor… tren 8 minggu" | 2 |
| A3 | **Gelembung/bubble anomali** (kategori × volume × keparahan) `[tafsir]`. | "kelembung anomali" | 2 |
| A4 | **Deteksi anomali** = menyimpang dari normal: lonjakan volume dan **topik baru muncul**, dengan **ambang (threshold) yang bisa diatur**. | "threshold… topik baru munculnya" | 2 |
| A5 | **Drill-down dimensi**: kategori × lokasi dalam persen (contoh: "rawat jalan" 41% di Depok vs 12% di Tangerang). | "eksplorasi dimensi… 41%… 12%" | 1 |
| A6 | **Bukti sumber**: tiap anomali bisa dibuka sampai ke ulasan asli (isi, intent, sentimen, sumber, lokasi). | "dilihat sumber-sumbernya… isi reviewnya, intent, sentimen" | 1 |
| A7 | **Bukti dampak** sebelum/sesudah tindak lanjut (grafik keluhan turun setelah aksi). | "buktikan… dampak sebelum dan sesudah" | 2 |
| A8 | **Cadence harian**, bukan hanya mingguan; ada "health check mingguan". | "sebaiknya setiap hari bisa melihat" | 1 |
| A9 | **Generate report eksekutif** (PDF/ringkas). Sudah di REVISI_CEO (#export PDF). | "ada report… generate report" | 1 |
| A10 | **Tanya data lewat chat** ("kenapa angka turun?") dijawab angka + sumber. | "internal chatbot… jawab dengan angka dan sumbernya" | 3 |
| A11 | **Tampilan per peran**: eksekutif (kondisi semua lokasi), supervisor (alarm), manajer area (lokasi terparah), marketing (peluang), product owner (ide dari masukan). `[tafsir]` bisa jadi filter/ preset, bukan layar baru. | "business value" | 2 |

### B. Profile (profil site/lokasi & pengaturan) `[tafsir]`

| # | Poin | Dari notulen | Fase |
|---|---|---|---|
| B1 | **Profil per-site** menampilkan komposisi kategori masalah **dibanding rata-rata/peer site**, bukan angka tunggal. | contoh Depok vs Tangerang | 1 |
| B2 | **Setup Parameter per site/client**: daftar kategori, threshold anomali, definisi "topik baru", sumber data yang diaktifkan (checklist), spesifikasi AI. | "set up parameter… threshold… sumber data bisa di-check list" | 2 |
| B3 | **Normalisasi**: satu skala sentimen, taksonomi kanonik bersama, penamaan lokasi yang seragam di semua sumber. | "normalisasi sentimen, taksonomi kanonik, lokasi" | 1 (VoC) / 3 (lintas channel) |
| B4 | Profil site memuat **PIC & status tindak lanjut** (siapa memegang apa). | "normalisasi ada PIC, status, bukti dampak" | 1 |
| B5 | (Sudah ada) alamat, PIC, rekap bintang, tren per masalah, % response, SLA → lihat REVISI_CEO #profil. SLA **terblokir** `owner_response_time` kosong. | REVISI_CEO §4 | 1 |

### C. Peluang & tindak lanjut (mempengaruhi dashboard)

| # | Poin | Dari notulen | Fase |
|---|---|---|---|
| C1 | **Klasifikasi feedback**: konstruktif vs negatif, diberi nilai/skor. | "dikelompokkan, diklasifikasi, dihitung nilainya… constructive atau negatif" | 2 |
| C2 | **Peluang jadi prospect**: tandai "tolong follow up marketing"; masuk ke Sales Management / Outbound. Butuh API insert prospect. | "data prospect… sales management… modul outbound" | 3 |
| C3 | **Siklus hidup tindak lanjut** terlihat: terdeteksi → triase → dinilai → dikerjakan → dampak. | "siklus hidup insiden dari awal terdeteksi" | 2 |
| C4 | **Aksi 1-klik** dari anomali: jadikan tiket, eskalasi PIC, buat campaign/survey, dalam satu layar. | "tindak lanjut 1 klik… super workspace" | 2 (tiket+eskalasi sudah ada di 3549) |
| C5 | Penemuan prospek dari **crawling Google Business** (nama, email, WhatsApp rumah sakit). Beda dari crawl review. | akhir transkrip | 3 (arah produk, bukan 3607) |

---

## 3. Implementasi (hipotesis, perlu diverifikasi ke kode)

Yang saya tahu dari repo ini dan tiket 3549/REVISI_CEO: OneBox = Phalcon/PHP (`VocController`, view `.volt`, tabel `Setting`, `Benefit`), Crawler = FastAPI (`/api/integration/*`). Dashboard sudah punya `dashboardRange()` + `fetchReviews($rentang)` untuk rentang tanggal (REVISI_CEO §4). Sisanya **belum diperiksa**.

### Fase 1 — pakai data yang sudah ada (layak masuk 3607)

| Item | Pendekatan | Sisi |
|---|---|---|
| A1, A8 | Kartu status per lokasi: aturan sederhana dari data ada (mis. % negatif 7 hari vs 28 hari, jumlah ulasan belum dibalas). Satu endpoint ringkasan per rentang. | OneBox |
| A5, B1 | Query agregasi kategori × lokasi (share %); bandingkan dengan rata-rata semua lokasi. Perlu **kategori sudah terisi** per ulasan (cek apakah dari analisis AI / label). | OneBox, mungkin Crawler bila kategori belum tersimpan |
| A6 | Tautkan setiap kartu/ baris ke daftar `Voc/reviews` dengan filter terpasang (kategori + lokasi + rentang). Tanpa halaman baru. | OneBox |
| A9 | Gabung dengan export PDF di REVISI_CEO. | OneBox |
| B3 | Satu tabel pemetaan kategori→kategori kanonik dan sentimen→skala `-1..1`; dipakai dashboard. Tempat penyimpanan: `Setting` per site atau tabel kecil baru. | OneBox |
| B4 | Tampilkan PIC (sudah tersimpan per lokasi) + status tiket terkait. | OneBox |

### Fase 2 — butuh perhitungan/ engine baru

| Item | Pendekatan | Sisi |
|---|---|---|
| A4, B2 | Job terjadwal menghitung baseline per (lokasi, kategori), menandai anomali bila melewati ambang. Threshold, "topik baru", sumber aktif disimpan di `Setting` per site (pola sama dengan `voc_ai_model` di 3549). Ambang dibatasi lewat benefit `VOC_AI` bila perlu. | OneBox (job), Crawler (bila deteksi topik baru pakai LLM) |
| A2, A3 | Skor = f(volume, lonjakan, keparahan sentimen, jumlah lokasi). **Rumus belum ditentukan** — butuh keputusan produk. | OneBox |
| A7, C3 | Simpan snapshot metrik saat aksi dibuat; hitung pembanding N hari setelahnya. Butuh status siklus hidup di data tindak lanjut. | OneBox (model data) |
| C1 | Tambah label `jenis_masukan` (konstruktif/ keluhan/ pujian/ peluang) pada analisis AI + skor. Perubahan prompt dan skema di Crawler. | Crawler + OneBox |
| A11 | Preset filter per peran memakai permission yang ada; hindari layar baru. | OneBox |

### Fase 3 — luar lingkup 3607 (butuh keputusan strategi)

A10 (chatbot tanya-data), C2 (peluang → Sales Management/Outbound), C5 (crawl Google Business), B3 lintas channel, semua penyatuan 9 channel. Layak jadi **epic terpisah**, bukan bagian "UI Dashboard Improvement".

---

## 4. Usulan pemecahan tiket

| Usulan | Isi | Estimasi kasar |
|---|---|---|
| 3607-a | A1 + A8 kartu status lokasi & rentang | M |
| 3607-b | A5 + A6 + B1 drill-down kategori × lokasi + tautan ke ulasan | M |
| 3607-c | B3 + B4 normalisasi tampilan, PIC/status di profil | S |
| 3607-d | A9 export eksekutif (gabung REVISI_CEO) | M |
| Epic baru "Radar" | Fase 2 (A2–A4, A7, B2, C1, C3, C4) | L–XL, perlu desain dulu |
| Epic baru "Omni-channel" | Fase 3 | XL, di luar VoC |

---

## 5. Pertanyaan terbuka (harus dijawab sebelum jadi tiket)

1. Transkrip terpotong di 30 menit — apakah ada **bagian lanjutan** atau notulen lain yang spesifik soal dashboard COO dan profile?
2. "Dashboard COO" = layar mana di OneBox (nama rute/ view)? "Profile" = **profil site** (`dashboard profil per-site` di REVISI_CEO) atau **Settings/Profile organisasi** (`fe-profile-progress-report.md`, itu repo frontend lain)? Tafsiran saya yang pertama.
3. Apakah kategori masalah (mis. "rawat jalan") **sudah tersimpan per ulasan**? Kalau belum, A5/B1 pindah dari Fase 1 ke 2.
4. Rumus **skor** anomali/peluang: siapa yang memutuskan?
5. Radar dikerjakan di dalam modul VoC, atau modul baru lintas channel? Menentukan di mana Fase 2 tinggal.
6. `owner_response_time` masih kosong (REVISI_CEO #103) — SLA di profil tetap terblokir sampai Crawler diperbaiki.
