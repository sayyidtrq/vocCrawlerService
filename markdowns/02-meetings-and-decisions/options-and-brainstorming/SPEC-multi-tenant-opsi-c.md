# Spesifikasi — Multi-Tenant VoC (Opsi C: Daftar Penyewa Ditarik dari OneBox)

> Status: **disetujui untuk diimplementasikan** · belum ada kode ditulis
> Asal keputusan: [[BRAINSTORM-multi-tenant-voc]]
> Terkait: [[ADR-0001-ownership-inversion]] · [[ADR-0002-ai-execution-split]] · [[ADR-0003-crawl-execution-pull-queue]]
> Contoh yang dipakai sepanjang dokumen: **Five Coffee** (kedai kopi, banyak cabang)
> Penanda: **[ADA]** = sudah berjalan · **[BARU]** = harus dibangun

---

## 1. Yang diputuskan

Satu deployment Crawler System melayani **semua penyewa**. Crawler tidak menyimpan daftar penyewa; ia **menanyakannya ke OneBox**.

Alasannya sederhana: [[ADR-0003-crawl-execution-pull-queue]] sudah menetapkan **OneBox tahu APA & KAPAN, Crawler mengeksekusi**. Daftar penyewa adalah "APA" — jadi tempatnya di OneBox. Ini bukan pola baru, hanya pola yang sama diterapkan satu tingkat lebih tinggi.

### Kenapa ini murah dikerjakan

Lapisan data Crawler **sudah multi-tenant** [ADA — `app/db/models.py`]: `companies`, `users`, `api_clients`, `locations`, `reviews`, `fetch_logs`, `competitors`, `worklist_sync_states` semuanya punya `company_id` beserta index.

Yang single-tenant hanya **konfigurasinya** [`app/config.py`]:

```
onebox_site_id      ← satu
onebox_company_id   ← satu
```

> [!important]
> Ini bukan pekerjaan membongkar arsitektur. Ini melengkapi satu lapisan yang tertinggal.

---

## 2. Bentuk akhir

```
Tingkat 0   Kredensial awal          env, satu akun layanan      [BARU: scope]
Tingkat 1   Daftar penyewa           ditarik dari OneBox         [BARU]
Tingkat 2   Daftar target crawl      worklist per site           [ADA]
Tingkat 3   Hasil crawl              disimpan per company_id     [ADA]
```

Alur satu siklus:

```
Crawler ──login (akun layanan)──────────────► OneBox
        ◄─ JWT

Crawler ──GET /api/VocTenants───────────────► OneBox
        ◄─ [ {site_id, nama, ...}, ... ]     hanya site yang VoC-nya AKTIF

  untuk tiap penyewa:
Crawler ──login (siteId=<site>)─────────────► OneBox
        ◄─ JWT ber-sid
Crawler ──GET /api/VocWorklist──────────────► OneBox
        ◄─ daftar cabang milik site itu
Crawler ── simpan ter-scope company_id
```

Tingkat 2 dan 3 **sudah terbukti bekerja** (Hermina, 28 Jul). Yang ditambahkan hanya Tingkat 1 — dan bentuknya sama persis dengan worklist, jadi tidak ada mekanisme baru untuk dipelajari.

---

## 3. Yang dibangun di OneBox

### 3.1 Endpoint daftar penyewa — [BARU]

```
GET /api/VocTenants
Authorization: Bearer <JWT akun layanan>
```

Mengembalikan site yang **boleh dilayani** akun tersebut **dan** VoC-nya aktif:

```json
{
  "data": [
    {
      "site_id": 169,
      "site_name": "Hermina",
      "voc_enabled": true,
      "crawl_windows": ["05:00-07:00", "11:00-13:00", "21:00-23:00"],
      "timezone": "Asia/Jakarta"
    },
    {
      "site_id": 420,
      "site_name": "Five Coffee",
      "voc_enabled": true,
      "crawl_windows": ["06:00-08:00", "20:00-22:00"],
      "timezone": "Asia/Jakarta"
    }
  ],
  "meta": { "count": 2, "api_version": "v1", "generated_at": "..." }
}
```

**Dua aturan yang tidak boleh dilanggar:**

1. **Hanya site yang benar-benar bisa diakses akun itu.** Daftarnya diturunkan dari keanggotaan user (`sub` pada JWT), bukan dari parameter request. Akun layanan tidak boleh bisa "menebak" site milik orang lain.

2. **Hanya site yang benefit VoC-nya aktif.** Inilah gerbangnya — lihat §3.2.

> [!warning] Pengecualian yang disengaja
> Endpoint ini **melintasi site**, berbeda dari endpoint lain yang selalu terkunci pada `sid` di JWT. Ini disengaja: fungsinya memang penemuan (*discovery*). Pengamanannya ada pada keanggotaan akun — bukan pada `sid`.
> Karena melanggar pola umum, alasannya wajib ditulis sebagai komentar di kode.

### 3.2 Gerbang benefit — [BARU]

Site hanya muncul di daftar bila benefit VoC-nya aktif (`Benefit`/`SiteBenefit`, kode `VOC_*`).

Konsekuensinya persis seperti yang diinginkan:

> Admin OneBox menyalakan benefit dulu → baru Crawler System bisa dipakai untuk site itu.

Crawler **tidak perlu tahu apa pun** soal benefit, kuota, atau tagihan. Kalau benefit dimatikan, site itu hilang dari daftar, dan crawl berhenti dengan sendirinya. Konsisten dengan [[ADR-0001-ownership-inversion]]: entitlement terpusat di OneBox.

Gerbang yang sama **juga dipasang di `/api/VocWorklist`** — supaya site tanpa benefit tetap ditolak walau id-nya sudah diketahui Crawler dari siklus sebelumnya.

### 3.3 Endpoint worklist — [ADA, tanpa perubahan bentuk]

`GET /api/VocWorklist` tetap seperti sekarang: ter-scope `sid` dari JWT. Hanya ditambahi pemeriksaan benefit di atas.

---

## 4. Yang dibangun di Crawler System

### 4.1 Kolom penghubung penyewa — [BARU]

Tambahkan pada tabel `companies`:

```
onebox_site_id   integer, unik, boleh null
```

Inilah kunci penghubung antara site OneBox dan company Crawler. Stabil, dan tidak perlu disimpan di OneBox.

**Siapa yang membuat baris `companies`?** Crawler, otomatis, saat pertama kali melihat site baru di daftar penyewa. Nama company diambil dari `site_name`. Ini aman karena daftar penyewa sudah tersaring dua kali (keanggotaan + benefit).

### 4.2 Konfigurasi — [BARU]

Nilai lama yang **dihapus**:

```
ONEBOX_SITE_ID       ← tidak lagi dipakai
ONEBOX_COMPANY_ID    ← tidak lagi dipakai
```

Yang **tersisa** (dan hanya ini):

```
ONEBOX_BASE_URL
ONEBOX_SVC_EMAIL
ONEBOX_SVC_PASSWORD
```

Satu akun layanan untuk seluruh penyewa. Jangan pernah di-commit.

### 4.3 Siklus sinkronisasi — [BARU, membungkus yang ADA]

```
refresh_all_tenants():
    daftar = GET /api/VocTenants
    untuk tiap penyewa dalam daftar:
        company = cari_atau_buat(onebox_site_id = penyewa.site_id)
        try:
            jwt = login(siteId = penyewa.site_id)
            worklist = GET /api/VocWorklist          # sudah ada
            sinkronkan(worklist, company_id = company.id)   # sudah ada
        except:
            catat kegagalan, LANJUT ke penyewa berikutnya
```

> [!important] Isolasi kegagalan
> Satu penyewa gagal **tidak boleh** menghentikan penyewa lain. Kalau Five Coffee bermasalah, Hermina tetap jalan. Ini syarat mutlak, bukan penyempurnaan.

### 4.4 Penyewa yang hilang dari daftar

Kalau sebuah site tidak lagi muncul (benefit dimatikan / akses dicabut):

- **Jangan hapus datanya.** Tandai company **nonaktif** dan hentikan crawl.
- Alasannya sama dengan rekonsiliasi target di [[ADR-0003-crawl-execution-pull-queue]]: menghapus berarti kehilangan cache review yang **tidak bisa diambil ulang** dari Google.

---

## 5. Contoh lengkap: menambahkan Five Coffee

Skenario nyata untuk menguji klaim multi-tenant. Five Coffee sengaja dipilih karena **bukan rumah sakit** — kalau alurnya sama persis tanpa ubah kode, klaimnya terbukti.

### Langkah 1 — Admin OneBox menyiapkan penyewa

1. Buat/siapkan site **Five Coffee** (misal `site_id 420`)
2. **Aktifkan benefit VoC** untuk site itu ← *tanpa ini, Crawler tidak akan melihatnya*
3. Beri akun layanan Crawler keanggotaan pada site tersebut

### Langkah 2 — Admin Five Coffee menambahkan cabang

Lewat menu **Voice of Customer → Locations**, cukup isi nama + Google Place ID:

| Cabang | Kota | Google Place ID |
|---|---|---|
| Five Coffee Senopati | Jakarta Selatan | `ChIJ...` |
| Five Coffee Kemang | Jakarta Selatan | `ChIJ...` |

Tidak ada langkah apa pun di sisi Crawler System.

### Langkah 3 — Crawler menemukan penyewa baru sendiri

```bash
docker compose exec api python -m scripts.refresh_all_tenants --json
```

Harapan hasil:

```json
{
  "tenants_found": 2,
  "results": [
    { "site_id": 169, "company": "Hermina",     "fetched": 5, "upserted": 0 },
    { "site_id": 420, "company": "Five Coffee",  "fetched": 2, "upserted": 2 }
  ]
}
```

Yang terjadi di balik layar: Crawler melihat site 420 untuk pertama kalinya, membuat company **Five Coffee** dengan `onebox_site_id = 420`, lalu menarik 2 cabangnya.

### Langkah 4 — Bukti data tidak tercampur

```sql
SELECT c.name, COUNT(l.id) AS jumlah_cabang
FROM companies c LEFT JOIN locations l ON l.company_id = c.id
GROUP BY c.name;
```

| name | jumlah_cabang |
|---|---|
| Hermina | 1 |
| Five Coffee | 2 |

Lalu pastikan **kebocoran nol**: review Five Coffee tidak boleh muncul saat menarik memakai service token milik Hermina, dan sebaliknya.

### Langkah 5 — Bukti gerbang benefit bekerja

Matikan benefit VoC untuk Five Coffee di OneBox, jalankan ulang:

```json
{ "tenants_found": 1, "results": [ { "site_id": 169, ... } ] }
```

Five Coffee hilang dari daftar, crawl-nya berhenti, **datanya tetap utuh**. Nyalakan lagi → muncul lagi tanpa kehilangan apa pun.

---

## 6. Aturan yang tidak boleh dilanggar

1. **Setiap query di Crawler wajib ter-scope `company_id`.** Tanpa kecuali. Ini satu-satunya yang memisahkan data antar penyewa.
2. **Tenant tidak pernah datang dari parameter request** — selalu dari identitas (JWT `sid` atau service token).
3. **Kegagalan satu penyewa tidak boleh menular** ke penyewa lain.
4. **Jangan hapus data penyewa** saat ia hilang dari daftar. Tandai nonaktif.
5. **Kredensial tidak pernah masuk git**, tidak pernah tercetak di log.
6. **Akun layanan hanya boleh membaca.** Ia tidak boleh bisa mengubah data penyewa mana pun.

---

## 7. Risiko yang diterima, dan mitigasinya

Satu akun layanan mengakses banyak penyewa berarti **satu kebocoran berdampak ke semua**. Ini konsekuensi yang disadari saat memilih Opsi C.

Mitigasi yang wajib ada:

- Akun itu **hanya berhak baca** — tidak bisa mengubah apa pun
- Token ber-scope sempit (`worklist:read`), **bukan** akun admin
- Rotasi berkala, dan pemakaiannya tercatat
- Keanggotaan site diberikan **satu per satu**, bukan akses global

Kalau suatu saat dinilai terlalu berisiko, jalan mundurnya jelas: pindah ke satu kredensial per penyewa yang disimpan terenkripsi di Crawler. Bentuk endpoint dan alur sinkronisasi tidak perlu berubah — hanya sumber kredensialnya.

---

## 8. Cara menguji

| # | Yang diuji | Lulus bila |
|---|---|---|
| 1 | Penemuan penyewa | Hermina & Five Coffee sama-sama muncul |
| 2 | Pembuatan company otomatis | `companies` bertambah satu, `onebox_site_id = 420` |
| 3 | Sinkron worklist per penyewa | Cabang masuk ke company yang benar |
| 4 | **Isolasi data** | Token Hermina **tidak** bisa melihat data Five Coffee |
| 5 | Gerbang benefit | Benefit mati → penyewa hilang dari daftar, data tetap utuh |
| 6 | Isolasi kegagalan | Five Coffee sengaja dirusak → Hermina tetap tersinkron |
| 7 | Idempotensi | Jalan dua kali → hasil sama, tidak ada duplikat |

Uji **nomor 4 dan 6 adalah yang terpenting.** Keduanya yang membedakan sistem multi-tenant sungguhan dari sistem satu-penyewa yang kebetulan menampung dua.

---

## 9. Yang sengaja belum dikerjakan

Diangkat, tapi bukan bagian dari pekerjaan ini:

1. **Retensi cache review.** [[ADR-0001-ownership-inversion]] menyebut review di Crawler sebagai cache, padahal Google hanya menyimpan riwayat terbatas — kalau dihapus, tidak bisa diambil ulang. Perlu keputusan terpisah: perlakukan sebagai data primer atau tetap cache dengan masa simpan tertentu.

2. **Kapasitas crawl.** Rate limit Google berlaku per target. Kalau nanti ada penyewa dengan 100 cabang, satu window mungkin tidak cukup. Diukur setelah crawl terbukti berjalan ([[PLAN_KEY_PROCESS_DEMO]]).

3. **Antrean & penjadwalan.** Tetap mengikuti [[ADR-0003-crawl-execution-pull-queue]]; multi-tenant tidak mengubahnya, hanya menambah dimensi penyewa pada job.

4. **Kuota AI per penyewa.** Menyusul setelah `Benefit` VoC diregistrasi.

---

## 10. Urutan pengerjaan

1. Crawler: tambah kolom `onebox_site_id` pada `companies`
2. OneBox: pasang gerbang benefit pada `/api/VocWorklist` *(perubahan terkecil, langsung bermanfaat)*
3. OneBox: bangun `/api/VocTenants`
4. Crawler: siklus `refresh_all_tenants` + isolasi kegagalan
5. Crawler: buang `ONEBOX_SITE_ID` & `ONEBOX_COMPANY_ID` dari konfigurasi
6. Uji dengan Five Coffee sesuai §5 dan §8

Langkah 1 dan 2 bisa dikerjakan paralel — tidak saling menunggu.
