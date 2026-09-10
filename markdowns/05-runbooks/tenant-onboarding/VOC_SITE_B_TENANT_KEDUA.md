# VoC — Site B, Tenant Kedua untuk Uji Isolasi

Cara membuat tenant kedua, cara masuk ke dalamnya, dan apa yang sudah terbukti
dengannya.

---

## 1. Kenapa perlu tenant kedua

Seluruh data VoC hidup di satu site saja (169). Selama cuma ada satu penghuni,
**tidak ada cara membedakan** "kueri ini benar-benar menyaring SiteId" dari
"kueri ini tidak menyaring apa-apa, tapi kebetulan tidak ada tetangga yang bisa
bocor". Enam layar VoC bisa lulus semua pengujian hari ini dan tetap membocorkan
data begitu tenant kedua masuk.

Site B **sengaja dibuat kosong**. Nilainya justru di situ: kalau setelah login
sebagai operator Site B ada satu saja review, lokasi, jadwal, atau angka KPI
milik site 169 yang muncul, itu kebocoran — dan tidak perlu ditafsirkan.

---

## 2. Membuatnya

```bash
# di dalam container webapp
cd /onecloud
VOC_TEST_ACCOUNT_PASSWORD='<sandi-bersama>' \
ONECLOUD_ENV=local TARGET_VERSION=1786110000000000_1_123_0 \
php app/migrate.php
```

Migrasi: `app/migrations/1786110000000000_1_123_0/Site.php`. Aman dijalankan
berulang. Tanpa env-nya, migrasi **tidak membuat apa pun** — site tanpa akun
tidak bisa diuji sama sekali, jadi ia memilih berhenti daripada meninggalkan
tenant setengah jadi.

Yang dibuat:

| Objek | Isi |
|---|---|
| `Site` | Nama `VoC Tenant B (uji isolasi)`, Domain `voc-tenant-b.local` |
| `Organization` | TypeId `OT1` — **wajib**, tanpa ini akunnya tidak bisa login |
| `Permission` | Seluruh menu VoC aktif, untuk role `userNews` |
| `SiteBenefit` | Semua benefit `VOC%` yang punya ProductBenefit, kuota 100.000 |
| `User` | `voc.siteb.operator@onebox.local`, role `userNews`, **hanya** di Site B |
| `Connection` | Satu baris penanda, mock aktif, tanpa service token |

**Kenapa satu role saja, bukan empat?** Site ini menguji isolasi **antar-site**,
bukan pembatasan antar-role — yang kedua sudah dikerjakan migrasi
`1786090000000000` di site 169. Operator Site B justru diberi **seluruh** menu
supaya setiap layar bisa dibuka dan diperiksa kebocorannya.

**Kenapa ada Connection penanda?** Supaya layar Lokasi Site B punya satu baris
yang benar-benar miliknya. Tanpa itu layar kosong, dan layar kosong tidak bisa
membedakan "isolasinya bekerja" dari "layarnya rusak" — dua kesimpulan yang
sangat berbeda dari tampilan yang persis sama.

**Kenapa kuota 100.000, bukan −1?** Nilai −1 memang konvensi "tanpa batas", dan
`BenefitService` sudah diperbaiki untuk menghormatinya — tetapi hanya di
environment yang sudah menerima perbaikan itu. Di environment yang belum, −1
membuat setiap panggilan **ditolak**, karena `(0 + 1) > -1` bernilai benar.

---

## 3. Cara masuk ke Site B — ini bagian yang paling mudah salah

**Site ditentukan oleh header `Host`, bukan oleh akun dan bukan oleh query
parameter.**

`LoginController` punya `getSiteId()` sendiri yang meng-override milik
`ControllerBase`, dan ia **hanya** mencocokkan `Site.Domain` dengan header Host:

```php
$domain = $this->request->getHeader('host');
$site   = Site::findFirst(["Domain='$domain'"]);
$siteId = $site ? $site->Id + 0 : $this->config['application']->siteId;
```

Kalau tidak cocok, ia jatuh ke site bawaan di config — di lokal itu **169**.
Akibatnya, mencoba login sebagai operator Site B tanpa mengatur Host akan ditolak
dengan *"You are not authorized to log into this site"*, dan pesannya benar:
akun itu memang bukan anggota site 169.

> `ControllerBase::getSiteId()` memang menerima `?siteId=`, tetapi **jalur login
> tidak memakainya**. Menambahkan `?siteId=267` pada halaman login tidak
> berpengaruh apa pun — ini sudah dicoba dan gagal.

### Lokal

```bash
curl -k -H "Host: voc-tenant-b.local" \
  https://localhost/feature/DNGO19-3391/login
```

Untuk membukanya di browser, tambahkan ke `hosts` lalu akses lewat nama itu:

```
127.0.0.1  voc-tenant-b.local
```

### Dev

Site B butuh **hostname sungguhan yang mengarah ke aplikasi**, lalu isi
`Site.Domain` dengan hostname itu persis. Tanpa itu, tenant kedua tidak bisa
dimasuki di dev — bukan karena akunnya salah, melainkan karena tidak ada jalan
masuk yang memetakan ke site tersebut.

> **Catatan cache:** hasil pencarian domain di-cache 86400 detik
> (`SiteId_$domain`). Sesudah mengubah `Site.Domain`, hasilnya tidak langsung
> terlihat sampai cache-nya kedaluwarsa atau dibersihkan.

---

## 4. Hasil uji isolasi

Dijalankan 24 Agustus 2026 di lokal, dengan sesi sungguhan untuk kedua site.

| | site 169 (`voc.operator`) | Site B (`voc.siteb.operator`) |
|---|---|---|
| Login | 302 (berhasil) | 302 (berhasil) |
| `Voc/reviewsData` | 518 | **0** |
| `Voc/locationsData` | 5 | **1** (miliknya sendiri) |
| `Voc/crawlHistory` | 73 | ditolak — belum punya koneksi berkredensial |

**Uji silang:** akun site 169 mencoba masuk lewat domain Site B → **ditolak**.
Itu perilaku yang benar.

Penolakan `crawlHistory` juga jujur dan tepat sasaran:
*"Belum ada koneksi Voice of Customer yang berkredensial di site ini."*

---

## 5. Cacat yang ditemukan karena Site B — dan tidak mungkin ditemukan tanpanya

**Layar Lokasi 500 utuh di site mana pun yang belum punya review.**

```
VocController::locationRow(): Argument #2 ($agg) must be of type array, null given
```

`reviewAggregateByLocation()` tidak memberi nilai awal pada `$agg`. Kalau
`fetchReviews()` mengembalikan nol baris, loop-nya tidak pernah berjalan, `$agg`
tidak pernah lahir, dan fungsinya mengembalikan `null`.

Ini mustahil terlihat di site yang sudah berisi data — dan **setiap site baru
selalu bermula tanpa review**, jadi layar Lokasi-nya rusak sejak menit pertama
dipakai. Setiap tenant baru di produksi akan menabraknya.

Sudah diperbaiki (`$agg = array();`). Sesudah perbaikan, `locationsData` Site B
mengembalikan 1 baris, bukan 500.

---

## 6. Yang BELUM bisa diuji dari sini

**Fetch lintas tenant.** Tenant di Crawler melekat pada service token, dan token
yang ada sekarang terikat ke `company_id` 3 (`HGA`). Site B tidak punya token,
jadi ia tidak bisa menarik review sama sekali.

Menguji isolasi **tulis** — memastikan review Site B tidak masuk ke site 169 dan
sebaliknya — baru mungkin setelah tim Crawler menerbitkan token untuk company
kedua. Detailnya di `VOC_CRAWLER_SERVICE_CONFIG.md` bagian 5.

Yang **sudah** terbukti adalah isolasi **baca**, dan itu bagian terbesar
permukaannya.

---

## 7. Membongkarnya

```bash
cd /onecloud
ONECLOUD_ENV=local TARGET_VERSION=<versi-sebelumnya> php app/migrate.php
```

`down()` menolak menghapus Site B kalau site itu **sudah berisi pesan atau
tiket** — kalau sampai ada isinya, berarti ia dipakai untuk sesuatu yang bukan
pengujian ini, dan menghapusnya membuang data milik orang lain.
