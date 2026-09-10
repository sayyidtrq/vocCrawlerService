# VoC — Konfigurasi Sisi Crawler Service

Cara OneBox menyambung ke **Crawler System** (Hermina Review Intelligence):
apa yang perlu diisi, apa artinya, dan apa yang akan terjadi kalau salah.

---

## 1. Bentuk sambungannya

Tidak ada tabel khusus. **Satu lokasi = satu row `Connection`**, dan seluruh
konfigurasi Crawler menumpang di kolom `Connection.Options` (longtext berisi JSON).

| Kolom | Isi | Catatan |
|---|---|---|
| `ProviderId` | `PVD99` | Provider VoC. Jangan ditulis sebagai literal di kode baru — pakai `\Provider::VOC` |
| `Url` | `http://192.168.1.3:8000` | Base URL Crawler, **tanpa** garis miring penutup |
| `UserId` / `Password` | email + sandi user Crawler | Hanya dipakai `api_mode: "user"`. Kosongkan pada mode service |
| `TargetId` | id lokasi di sisi Crawler | Diisi saat provisioning berhasil; kosong berarti belum tersinkron |
| `StatusId` | `CNS1` aktif · `CNS3` tidak aktif | Kompetitor sengaja `CNS3` supaya tidak ikut disapu penjadwal |
| `Options` | JSON, lihat bawah | |

### Isi `Options`

```json
{
  "mock": false,
  "timeout": 30,
  "api_mode": "service",
  "service_token": "voc_staging_xxxxxxxxxxxxxxxx",
  "company_id": 3,
  "kind": "location",
  "is_official": true,
  "location": {
    "city": "Depok",
    "address": "",
    "source": "selenium",
    "pic_wa": "081234567890"
  }
}
```

| Kunci | Wajib | Arti |
|---|---|---|
| `api_mode` | ya | `"service"` (dianjurkan) atau `"user"` (mode lama) |
| `service_token` | ya untuk mode service | Token statis; **tenant melekat padanya** |
| `company_id` | ya | Tenant di sisi Crawler. Dicocokkan saat enqueue |
| `timeout` | tidak | Detik, default 30 |
| `mock` | tidak | `true` = tidak memanggil Crawler sama sekali |
| `mock_file` | tidak | Berkas jawaban tiruan saat `mock: true` |
| `kind` | tidak | `"location"` (default) atau `"competitor"` |
| `is_official` | tidak | Kepemilikan akun Google Business. **Ini yang menghidupkan tombol Balas** di layar Kelola Review |

---

## 2. Dua mode API — pilih `service`

### `api_mode: "service"` — dianjurkan

Token statis, tanpa login, tanpa sandi manusia yang perlu disimpan di row
Connection. **Tenant melekat pada token**, jadi OneBox tidak bisa — dan tidak
perlu — memilih tenant sendiri.

```
GET /api/integration/v1/whoami   → {company_id, company_name, scopes}
GET /api/integration/v1/reviews  → {data, page:{…}, meta:{…}}
```

### `api_mode: "user"` — mode lama

Login sebagai user Crawler; tenant ditentukan oleh `company_id` milik user itu.
Konsekuensinya sandi manusia tersimpan di baris Connection — alasan utama mode
ini ditinggalkan.

```
POST /api/auth/login   (x-www-form-urlencoded: username=<email>&password=<…>)
GET  /api/auth/me      → {id, email, company_id, company_name, …}
GET  /api/reviews      → {items, total, page, page_size, total_pages}
```

> **Endpoint yang dipakai layar Fetch Jobs — crawl, status batch, riwayat —
> semuanya menuntut service token.** Koneksi yang hanya punya `UserId`/`Password`
> cukup untuk lolos pemilihan kredensial tetapi tidak cukup untuk memanggil apa
> pun. Ini pernah mematikan seluruh layar Fetch Jobs, dan sejak itu
> `vocCredentialTemplate()` memilih dalam **dua babak**: cari koneksi bertoken
> dulu, akun user hanya sebagai cadangan.

---

## 3. Memastikan sambungannya hidup

```bash
# 1. Crawler-nya hidup?
curl -s http://192.168.1.3:8000/api/health
# → {"status":"ok","app":"Hermina Review Intelligence","env":"staging",
#    "database":{"ok":true,"message":"OK"}}

# 2. Token ini milik tenant mana?
curl -s -H "Authorization: Bearer $VOC_SERVICE_TOKEN" \
  http://192.168.1.3:8000/api/integration/v1/whoami
# → {"company_id":3,"company_name":"HGA",
#    "scopes":["crawl:enqueue","crawl:read","reviews:read"]}
```

Kalau `whoami` mengembalikan `company_id` yang **berbeda** dari
`Options.company_id`, enqueue akan ditolak dengan alasan
*"Options.company_id pada koneksi tidak cocok dengan tenant service token-nya"* —
dan itu penolakan yang benar, bukan gangguan.

### Scope yang dibutuhkan

| Scope | Untuk |
|---|---|
| `crawl:enqueue` | Menjalankan penarikan (Fetch Jobs, Jadwal Crawl) |
| `crawl:read` | Status batch dan Riwayat Fetch |
| `reviews:read` | Menarik isi ulasan |

Token tanpa `crawl:enqueue` tetap bisa membaca, tetapi tombol Mulai akan gagal —
periksa scope-nya sebelum menyalahkan kuota.

---

## 4. Menambahkan lokasi baru

Lewat layar **Lokasi** (`/Voc/locations`), bukan SQL langsung. Urutannya:

1. Isi nama cabang (maks. 80 karakter) dan **Google Place ID**.
2. Simpan. Lokasi tersimpan di **OneBox dulu**, baru dikirim ke Crawler.
3. Kalau pengiriman gagal, barisnya **tetap ada** dengan status belum
   tersinkron — tidak gagal senyap, tidak ada data hilang. Tekan **Resync**.

**Google Place ID divalidasi formatnya** (`^[A-Za-z0-9_-]{10,255}$`), bukan
sekadar wajib diisi. Ini menangkap kesalahan termahal di modul ini: menempelkan
tautan peta atau nama tempat alih-alih ID. Kalau lolos, crawler menarik review
bisnis lain tanpa satu pun tanda bahwa targetnya salah — datanya masuk,
kelihatan normal, dan salah.

Untuk lokasi yang **sudah ada di Crawler tapi belum terdaftar di OneBox**, pakai
tombol **Import**; tanpa itu ada target crawl aktif yang review-nya tidak pernah
sampai.

---

## 5. Multi-tenant — batas yang perlu diketahui sebelum merencanakan uji

**Satu service token = satu `company_id`.** Tenant melekat pada token, dan token
diterbitkan di sisi Crawler. Konsekuensinya:

- OneBox **tidak bisa** memindahkan koneksi ke tenant lain dengan mengubah
  `Options.company_id` saja — yang berubah cuma catatan di sisi kita, dan enqueue
  justru akan ditolak karena tidak cocok dengan token.
- Menguji isolasi tenant secara sungguhan **membutuhkan token kedua untuk
  company berbeda**, dan itu hanya bisa diminta ke tim Crawler.
- Per 24 Agustus 2026 hanya ada **satu** token di lingkungan ini
  (`company_id: 3`, `HGA`), dipakai bersama oleh seluruh koneksi site 169.

Yang **bisa** diuji tanpa token kedua: isolasi **baca** di sisi OneBox — apakah
akun site lain bocor melihat data site 169. Yang **tidak bisa**: isolasi tulis
saat fetch.

---

## 6. Kalau bermasalah

| Gejala | Sebab yang paling sering |
|---|---|
| **502** di Fetch Jobs | Koneksi terpilih tidak punya service token. Periksa `Options.api_mode` dan `service_token` pada **semua** row VoC site itu, bukan hanya satu |
| **403** "belum aktif untuk site ini" | Gerbang benefit, bukan Crawler. Periksa `SiteBenefit` untuk `VOC_SCRAPE`, `VOC_REVIEW`, `VOC_AI` — ketiganya diperiksa berurutan |
| **"Crawler menolak cabang ini"** | Tiga kemungkinan berurutan: cabang nonaktif · belum punya master lokasi OneBox · belum pernah tersinkron. Refresh worklist tidak menolong untuk sebab pertama |
| **Menyisir ratusan ulasan untuk sepuluh** | `sort_applied: false` — urutan "Terbaru" gagal dipasang di Google Maps, sehingga aturan berhenti berdasarkan tanggal kehilangan dayanya. Sisi Crawler |
| **Kolom "Di luar rentang" 0 selama berjalan** | Bukan bug. Counter itu baru terisi saat batch selesai |

**Log sisi OneBox:** channel `VoiceOfCustomerSystem` — memuat kegagalan
provisioning, penolakan izin, dan galat panggilan Crawler.

---

## Ringkasan satu layar

```
Connection (PVD99)
  Url         http://192.168.1.3:8000
  Options
    api_mode      "service"        ← selalu, kecuali ada alasan kuat
    service_token voc_…            ← dari tim Crawler; tenant melekat di sini
    company_id    3                ← harus cocok dengan whoami
    kind          location|competitor
    is_official   true|false       ← menghidupkan tombol Balas

Periksa  : GET /api/health  lalu  GET /api/integration/v1/whoami
Butuh    : scope crawl:enqueue + crawl:read + reviews:read
Tenant   : satu token satu company — pindah tenant butuh token baru
```
