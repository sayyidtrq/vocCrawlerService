# Brainstorm — Multi-Tenant untuk Voice of Customer

> Status: **eksplorasi, belum keputusan.** Belum ada kode yang ditulis.
> Terkait: [[ADR-0001-ownership-inversion]] · [[ADR-0002-ai-execution-split]] · [[ADR-0003-crawl-execution-pull-queue]]
> Tanggal: 2026-07-28 · Penanda: **[verified]** = dicek langsung ke kode · **[assumption]** = perlu dibuktikan

---

## 1. Pertanyaan yang memicu ini

Saat ini di env Crawler System ada `ONEBOX_SITE_ID` — satu nilai, satu site.
Padahal OneBox itu **multi-tenant**: Hermina hanya salah satu penyewa (site 169).
Nanti akan ada Kopi Kenangan dengan puluhan cabang, lalu penyewa lain lagi.

Pertanyaan yang muncul:

1. Apakah tiap site punya konfigurasi sendiri?
2. Apakah cara deploy-nya beda-beda per site?
3. Databasenya sama atau terpisah?
4. Review disimpan "sementara" di Crawler — sementara itu berapa lama?
5. Bagaimana entitlement (benefit) menentukan siapa boleh memakai?

---

## 2. Temuan: batasnya bukan di tempat yang dikira

Ini bagian terpenting, dan mengubah bentuk seluruh diskusi.

**Lapisan data Crawler System SUDAH multi-tenant** [verified — `app/db/models.py`]:

| Tabel | Punya `company_id`? |
|---|---|
| `companies` | tabel induknya |
| `users` | ✅ + index |
| `api_clients` (service token) | ✅ + index |
| `locations` | ✅ |
| `reviews` | ✅ + index `(company_id, sync_updated_at, id)` |
| `fetch_logs` | ✅ |
| `competitors` | ✅ + unique `(source, place_id, company_id)` |
| `worklist_sync_states` | ✅ unique per company |

Artinya: **satu database Crawler sudah bisa melayani banyak penyewa** dengan pemisahan per baris. Itu sudah dirancang sejak awal.

**Yang single-tenant justru lapisan konfigurasi** [verified — `app/config.py`]:

```
onebox_base_url         ← satu
onebox_service_email    ← satu akun
onebox_service_password ← satu
onebox_site_id          ← SATU site
onebox_company_id       ← SATU company
```

> [!important] Inti masalahnya
> Datanya siap untuk banyak penyewa. **Konfigurasinya yang masih mengasumsikan satu penyewa.**
> Jadi ini bukan pekerjaan membongkar arsitektur — ini melengkapi satu lapisan yang tertinggal.

**Fakta pendukung lain** [verified]:
OneBox adalah **satu deployment** yang melayani banyak site (tabel `Site`, banyak baris di satu database). Jadi `onebox_base_url` memang wajar tunggal per environment. Yang berbeda antar penyewa hanyalah **site_id** dan **kredensial**.

Dan: login OneBox **tanpa** `siteId` mengembalikan **daftar site** yang bisa diakses akun itu — bukan token. Ini pernah kita lihat langsung waktu mencari site dev. Artinya satu akun layanan **bisa** melayani banyak site.

---

## 3. Empat keputusan yang harus diambil

### 3.1 Konfigurasi per penyewa — di mana tinggalnya?

Pilihan:
- **(a) Environment variable** — seperti sekarang. Satu penyewa per deployment.
- **(b) Tabel di database Crawler** — daftar penyewa beserta site_id & kredensialnya.
- **(c) Ditarik dari OneBox** — OneBox sebagai sumber kebenaran, konsisten dengan [[ADR-0003-crawl-execution-pull-queue]].

Ada masalah ayam-telur pada (c): untuk bertanya ke OneBox, Crawler butuh kredensial dulu. Jadi selalu ada **satu kredensial awal** yang harus ditanam di luar sistem. Pertanyaannya: setelah itu, sisanya ditarik atau disimpan sendiri?

### 3.2 Deployment — satu untuk semua, atau satu per penyewa?

Pertimbangan yang nyata, bukan teoretis:
- Selenium itu **berat**. Satu deployment per penyewa berarti menggandakan beban itu.
- Rate limit Google berlaku **per target**, bukan per penyewa. Jadi memisahkan deployment tidak menambah kapasitas crawl.
- Tapi satu deployment berarti **satu titik kegagalan** untuk semua penyewa.

### 3.3 Database — satu atau terpisah?

Skema sudah punya `company_id` di mana-mana, jadi satu database dengan pemisahan per baris **sudah berfungsi hari ini**.

Database terpisah per penyewa akan menambah: N migration, N backup, N koneksi — tanpa manfaat tambahan, karena isolasinya sudah ada di skema.

Yang perlu dijaga: **setiap query wajib ter-scope `company_id`**. Sudah dilakukan lewat service token yang tenant-bound [verified], tapi harus jadi aturan yang tidak boleh dilanggar.

### 3.4 Entitlement — siapa yang menyalakan?

Pengamatan yang menurut saya paling elegan dari pertanyaan awal:

> "sama halnya site benefit — konfigurasi benefit dilakukan oleh admin OneBox, baru Crawler System bisa dipakai"

Ini bisa jadi mekanismenya sendiri: **worklist adalah gerbangnya**.

Kalau sebuah site belum punya benefit VoC aktif, OneBox cukup **tidak memasukkannya** ke daftar penyewa / mengembalikan worklist kosong. Crawler tidak perlu tahu apa pun soal benefit, kuota, atau tagihan.

Konsisten dengan [[ADR-0001-ownership-inversion]]: entitlement terpusat di OneBox.

---

## 4. Tiga bentuk arsitektur

### Opsi A — Satu deployment per penyewa
*(bentuk sekarang, tinggal digandakan)*

```
Hermina        → crawler-hermina    (env: site 169, company 3)
Kopi Kenangan  → crawler-kopken     (env: site 204, company 7)
```

| ✅ | ❌ |
|---|---|
| Isolasi terkuat | Beban Selenium berlipat |
| Tidak ada perubahan kode | N deployment untuk dirawat |
| Kegagalan satu penyewa tidak menular | Biaya server naik linear |
| | Penyewa kecil jadi tidak ekonomis |

Cocok bila penyewa sedikit dan besar-besar. Tidak cocok untuk model SaaS.

### Opsi B — Satu deployment, daftar penyewa di database Crawler

```
tabel onebox_tenants:
  company_id · site_id · base_url · kredensial · aktif
```

Crawler mengulang tiap penyewa aktif: login → tarik worklist → simpan ter-scope `company_id`.

| ✅ | ❌ |
|---|---|
| Satu deployment | Kredensial banyak penyewa di DB Crawler |
| Skema sudah mendukung | Perlu enkripsi + rotasi |
| Menambah penyewa = menambah baris | Perlu antarmuka admin untuk mengelolanya |
| | Konfigurasi jadi tinggal di dua tempat |

### Opsi C — Satu deployment, daftar penyewa **ditarik dari OneBox** ← *rekomendasi*

Satu akun layanan, lalu Crawler bertanya ke OneBox: *"site mana saja yang boleh saya layani?"*

```
Crawler  ──login (tanpa siteId)──►  OneBox
         ◄── daftar site yang berhak ──

untuk tiap site:
  login dengan siteId → JWT ber-sid → tarik worklist → simpan per company_id
```

| ✅ | ❌ |
|---|---|
| **Satu kredensial saja** yang ditanam | Satu akun mengakses banyak penyewa |
| Menambah penyewa = **cukup di OneBox** | Perlu endpoint daftar penyewa di OneBox |
| Entitlement otomatis jadi gerbang | Bergantung OneBox untuk tahu penyewa |
| Paling setia ke [[ADR-0003-crawl-execution-pull-queue]] | |

> [!note] Kenapa ini paling konsisten
> ADR-0003 sudah menetapkan: **OneBox tahu APA & KAPAN, Crawler mengeksekusi.**
> Daftar penyewa adalah "APA" — jadi tempatnya memang di OneBox.
> Ini bukan pola baru, ini pola yang sama diterapkan satu tingkat lebih tinggi.

---

## 5. Rekomendasi

**Opsi C**, dengan satu penyesuaian jujur soal keamanan.

Bentuknya bertingkat:

```
Tingkat 0  Kredensial awal        →  env (satu, ditanam manual)
Tingkat 1  Daftar penyewa         →  ditarik dari OneBox (gerbang benefit)
Tingkat 2  Daftar target crawl    →  ditarik dari OneBox (worklist, SUDAH JALAN)
Tingkat 3  Hasil crawl            →  disimpan di Crawler, ter-scope company_id
```

Tingkat 2 sudah terbukti bekerja. **Yang ditambahkan hanya tingkat 1** — dan bentuknya sama persis dengan worklist, jadi bukan mekanisme baru.

### Kekhawatiran yang harus dijawab

Satu akun layanan yang bisa mengakses semua penyewa itu **blast radius besar**. Kalau bocor, seluruh penyewa terdampak.

Mitigasi yang masuk akal:
- Akun itu hanya berhak **membaca** worklist — tidak bisa mengubah data penyewa
- Token ber-scope sempit (`worklist:read`), bukan akun admin
- Rotasi berkala + pencatatan pemakaian

Alternatif kalau ini dinilai terlalu berisiko: **satu kredensial per penyewa disimpan di DB Crawler (Opsi B)** — blast radius lebih kecil, tapi pengelolaannya lebih repot.

---

## 6. Pertanyaan yang belum terjawab

Perlu dibahas, belum saya putuskan sendiri:

1. **Retensi cache review di Crawler.** [[ADR-0001-ownership-inversion]] menyebutnya cache, tapi kenyataannya Google hanya menampilkan riwayat terbatas — kalau dihapus, tidak bisa diambil ulang. Jadi berapa lama disimpan? Atau justru diperlakukan sebagai data primer?

2. **Kapasitas crawl.** Rate limit Google per target. Kalau Kopi Kenangan punya 100 cabang, satu window 2 jam cukup? Perlu diukur setelah [[PLAN_KEY_PROCESS_DEMO|X1]] membuktikan crawl berjalan.

3. **`company_id` dibuat oleh siapa?** Saat site baru dinyalakan di OneBox, siapa yang membuat baris `companies` di Crawler — otomatis atau manual?

4. **Isolasi kegagalan.** Satu penyewa yang bermasalah (mis. kena blokir Google) tidak boleh menghentikan crawl penyewa lain.

---

## 7. Dampak untuk demo

Pertanyaan ini bukan teoretis — **wajib disimulasikan saat demo**, karena inti jualannya adalah "sistem ini bisa dipakai perusahaan mana pun, bukan cuma rumah sakit".

Cara paling murah membuktikannya: **tambahkan satu site kedua** dengan jenis usaha berbeda (mis. satu cabang kedai kopi), lalu tunjukkan:
- konfigurasinya cukup di OneBox,
- datanya tidak tercampur dengan Hermina,
- alur yang sama berlaku tanpa perubahan kode.

Kalau itu berhasil, klaim multi-tenant terbukti — bukan sekadar diceritakan.

---

## 8. Yang perlu diputuskan lebih dulu

Sebelum apa pun ditulis, satu hal harus disepakati:

> **Model kredensial mana yang dipakai — satu akun layanan lintas penyewa (Opsi C), atau satu akun per penyewa (Opsi B)?**

Keputusan ini menentukan bentuk endpoint di OneBox, cara penyimpanan di Crawler, dan prosedur onboarding penyewa baru. Sisanya mengikuti.
