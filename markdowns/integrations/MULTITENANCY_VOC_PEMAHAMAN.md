# Multi-tenancy VoC — Pemahaman

Ditulis 14 Agustus 2026 dari pembacaan kode dan data dev yang sebenarnya, bukan
dari rancangan di atas kertas. Setiap klaim punya letak berkasnya.

Dokumen pasangannya: [MULTITENANCY_VOC_TEST_TASKLIST.md](MULTITENANCY_VOC_TEST_TASKLIST.md).

---

## 1. Ada DUA sumbu tenancy, bukan satu

Ini akar dari semua kerumitan di bawah. OneBox dan Crawler masing-masing punya
gagasan sendiri tentang "siapa penyewa ini", dan keduanya **tidak otomatis
sinkron**.

| | OneBox | Crawler (VoC System) |
|---|---|---|
| Nama | `SiteId` | `company_id` |
| Contoh | `169` | `3` |
| Ditentukan dari | sesi login pengguna | **kredensial**, bukan parameter |
| Disimpan di | tiap tabel (`Message.SiteId`, `Connection.SiteId`, `VocSchedule.SiteId`) | di sisi Crawler |

Yang menyambungkan keduanya cuma **satu baris `Connection`**. Baris itu memikul
seluruh beban pemetaan:

```
Connection
  SiteId  = 169                      <- sumbu OneBox
  Options = {
    "company_id": 3,                 <- sumbu Crawler (yang DIHARAPKAN)
    "service_token": "voc_...",      <- yang MENENTUKAN tenant sebenarnya
    "api_mode": "service",
    "location": { ... },
    "onebox_location_id": 676        <- cabang mana
  }
```

Kalimat terpenting di seluruh dokumen ini, dikutip dari
`app/services/Provider/VocProvider.php`:

> VoC menentukan tenant dari KREDENSIAL, bukan dari parameter yang dikirim
> OneBox. Artinya binding tenant hanya sekuat isi row Connection: salah paste
> kredensial = review rumah sakit lain masuk ke SiteId ini tanpa error apa pun.

Karena itu `Options.company_id` bukan sekadar catatan. Ia **pernyataan harapan**
yang dipakai mengadu apa yang kita kira dengan apa yang server katakan
(`whoami`).

---

## 2. Dari mana SiteId datang

`app/controllers/ControllerBase.php:615`:

```php
if ($this->request->hasQuery('siteId')) { $site = $this->request->getQuery('siteId'); }
if ($this->session->has("siteid"))      { $site = $this->session->get("siteid"); }
if (!$site)                              { $site = $this->getSiteIdByDomain(); }
```

Urutannya penting: **sesi menimpa query string**. Jadi `?siteId=170` tidak bisa
dipakai berpindah tenant selama sesinya punya `siteid`. Kalau sesi kosong,
barulah domain jadi penentu (`Site.Domain`); domain tak dikenal jatuh ke
`config.application.siteId`.

Untuk pengujian: **berpindah site berarti berganti sesi login**, bukan menempel
parameter.

---

## 3. Peta jalur data dan siapa yang menjaga tenancy

Enam jalur. Penentu tenant berbeda-beda, dan **tidak semuanya dijaga**.

| # | Jalur | Arah | Penentu tenant | Dijaga? |
|---|---|---|---|---|
| 1 | Layar VoC (Ulasan, Jadwal, Fetch Jobs, Dashboard) | baca DB | `SiteId` dari sesi | **Ya** — semua query utama menyaring `SiteId` |
| 2 | Worklist API (`GET /api/VocWorklist`) | Crawler menarik target | `SiteId` dari klaim `sid` di JWT | **Ya** |
| 3 | Enqueue crawl (`VocCrawlQueue::enqueue`) | OneBox ke Crawler | kredensial **koneksi pertama** yang cocok | **Tidak** — tanpa pra-periksa |
| 4 | Baca status batch (`VocTask::readBatch`) | OneBox ke Crawler | koneksi pertama yang punya token | **Tidak** |
| 5 | Sinkronisasi ulasan (`VocProvider`) | Crawler ke OneBox | `assertTenant()` adu `company_id` vs `whoami()` | **Ya, paling kuat** |
| 6 | Balas ulasan & impor kompetitor | OneBox ke Crawler | guard `company_id` vs `whoami()` | **Ya** |

### Jalur 2 — worklist

`app/controllers/api/v1/VocWorklistController.php`:

> Tenant: SELALU dari JWT (getSiteId → sid), TIDAK PERNAH dari request —
> meniru prinsip kontrak integrasi VoC (company_id dari token, bukan parameter).

Ada pula penjagaan `$siteId <= 0` supaya token yang ditolak tidak berubah
menjadi query dengan `SiteId = 0`.

### Jalur 5 — yang paling kuat, dan kenapa

`VocProvider::assertTenant()` menolak sync kalau:

- `Options.company_id` **kosong** → abort, menyebut connection dan site mana
- `whoami().company_id` **beda** dari `Options.company_id` → abort `TENANT MISMATCH`
- mode service tetapi token tidak punya scope `reviews:read` → abort

Alasannya ditulis di kodenya sendiri, dan itu keputusan yang benar:

> Mismatch = abort, bukan warning: data lintas-tenant yang sudah masuk Ticket
> jauh lebih mahal dibersihkan daripada satu run yang gagal.

### Jalur 3 dan 4 — celahnya di sini

`VocCrawlQueue::enqueue()` mengumpulkan semua koneksi milik site, lalu:

```php
if ($base === null) {
    $base = array('connection' => $connection, 'options' => $options);
}
...
$client = new VoiceOfCustomerSystemClient(
    $base['connection']->UserId, ..., $base['connection']->Url, $base['options']
);
```

**Kredensial koneksi PERTAMA (urut `Id`) dipakai untuk seluruh batch**, berapa
pun cabang yang diminta. Tidak ada `whoami()` sebelum kirim.

Kalau satu site punya koneksi yang menunjuk tenant berbeda:

- yang ber-`Id` terkecil menang, diam-diam
- cabang milik tenant lain dikirim memakai token tenant pertama
- pengaman satu-satunya adalah Crawler menolak `TARGET_NOT_FOUND` / `TENANT MISMATCH`

Kegagalannya memang tertangani — `VocCrawlQueue::classifyError()` mengenali
`TENANT MISMATCH` dan menggolongkannya sebagai kesalahan konfigurasi sehingga
jadwalnya dimatikan alih-alih dicoba ulang selamanya. Tetapi itu **penjagaan
sesudah kejadian**, bukan sebelum. Jalur 5 punya pra-periksa; jalur 3 tidak.

---

## 4. Yang TIDAK dijaga oleh skema sama sekali

### `Location` tidak punya kolom `SiteId`

Diperiksa langsung di dev:

```
information_schema.COLUMNS
  TABLE_NAME='Location' AND COLUMN_NAME='SiteId'  ->  0 baris
```

`Location` adalah tabel master **global**. Tidak ada apa pun di tingkat basis
data yang mencegah dua site menunjuk `Location.Id` yang sama.

Yang mengikat lokasi ke tenant hanyalah baris `Connection` (yang ber-`SiteId`)
lewat `Options.onebox_location_id`. Jadi kepemilikan lokasi adalah **konvensi
aplikasi**, bukan batasan skema.

Penegak konvensi itu ada satu tempat, `VocController::scheduleSave`:

```php
foreach (VocConnectionRule::connectionsForSite($siteId) as $connection) {
    $owned[(int) VocConnectionRule::oneboxLocationId($connection)] = true;
}
```

Menyimpan jadwal dengan lokasi milik site lain akan ditolak. Baik. Tetapi
`VocSchedule.LocationIds` menyimpan angka telanjang — kalau kelak ada jalur lain
yang menulis ke tabel itu tanpa melewati pemeriksaan ini, tidak ada jaring
pengaman kedua.

### Satu token untuk semua koneksi satu site

Di dev, 14 koneksi VoC site 169 memakai **satu** service token
(`COUNT(DISTINCT SHA1(token))` = 1). Wajar untuk satu company. Yang harus
dipastikan saat menambah company kedua: token site kedua tidak boleh ikut
tertempel di koneksi site pertama, dan sebaliknya.

### `Message` disimpan di bawah satu koneksi

Temuan 13 Agustus: 10 ulasan Hermina Bogor tersimpan dengan
`Message.ConnectionId` milik koneksi "Hermina depok", sementara cabangnya tetap
benar di layar karena dibaca dari `MessageContent.Meta.onebox_location_id`.
Dalam satu tenant ini cuma salah atribusi. **Lintas tenant, pola yang sama jauh
lebih berbahaya** — perlu dipastikan koneksi penampung selalu milik site yang
sama dengan review yang masuk.

---

## 5. Keadaan dev hari ini — garis dasar sebelum diuji

Dibaca dari `onecloud_rel`, 14 Agustus 2026:

| Yang diperiksa | Hasil |
|---|---|
| Site yang punya koneksi VoC | **1** (site `169`) |
| Jumlah koneksi VoC | 14, semuanya `Enabled = 1` |
| `Options.company_id` | **3**, seragam |
| `Options.api_mode` | `service`, seragam |
| Service token unik | **1** |
| URL Crawler unik | **1** |
| Site yang punya `VocSchedule` | 1 |

**Garis dasar: multi-tenancy VoC belum pernah benar-benar diuji.** Sampai hari
ini hanya ada satu penyewa, jadi tiap penjagaan tenant di atas belum pernah
terbukti menolak apa pun di lingkungan nyata — yang ada baru pembacaan kode.

Itu bukan berarti rusak. Itu berarti **belum ada buktinya**, dan itulah gunanya
pengujian hari ini.

---

## 6. Ringkasan untuk diingat saat menguji

1. Berpindah site = **berganti sesi login**, bukan mengganti parameter.
2. Tenant Crawler ditentukan **token**, bukan yang kita kirim. `company_id` di
   Options adalah harapan yang diadu dengan `whoami()`.
3. Jalur **baca** (sync ulasan) punya pra-periksa tenant yang keras. Jalur
   **tulis** (enqueue crawl) tidak — ia memakai kredensial koneksi pertama.
4. `Location` **global**. Kepemilikan cabang adalah konvensi aplikasi, bukan
   batasan basis data.
5. Kegagalan tenancy yang paling mahal adalah yang **tidak berbunyi**: data
   masuk ke site yang salah tanpa error. Karena itu uji negatifnya lebih penting
   daripada uji positifnya.
