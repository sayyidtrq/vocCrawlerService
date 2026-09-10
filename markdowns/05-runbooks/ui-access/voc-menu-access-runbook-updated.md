# Runbook Updated: Setup Menu VoC OneBox

Dokumen ini adalah instruksi standar untuk developer yang menjalankan VoC pada
repo OneBox. Menu OneBox adalah data database, bukan data branch. Karena itu
schema, menu, role, dan permission harus divalidasi terpisah.

## Prinsip Utama

1. Migration hanya memastikan struktur tabel dan patch schema sudah terpasang.
2. Seed memastikan master data, menu VoC, dan permission VoC tersedia.
3. Akun yang sama tidak menjamin sidebar yang sama jika database, role, atau
   permission berbeda.
4. Jangan menjalankan seed sebelum migration selesai.
5. Jangan mengisi `@mm` dan `@src` secara manual sebelum melihat hasil diagnosis.

## Prasyarat

Jalankan perintah berikut dari checkout OneBox:

```bash
cd /var/www/html/onecloud
git status --short
git branch --show-current
```

Pastikan branch memuat file berikut:

```bash
test -f scriptdb/voc/voc_setup_all.sql
grep -n "voc_assert_menu_source\|listberita\|semua_sumber" scriptdb/voc/voc_setup_all.sql
```

Jika `voc_assert_menu_source` belum ada, checkout/pull branch yang memuat
patch seed terbaru sebelum menjalankan setup.

## Step 1 - Migration

Gunakan environment yang sesuai dengan database aktif.

```bash
cd /var/www/html/onecloud/onecloud
./migration.sh local up
./migration.sh local status
```

Jika environment bukan `local`, ganti argumen `local`. Status migration harus
berada pada versi terbaru yang dipakai environment tersebut.

Catatan: migration terbaru tidak otomatis memperbaiki data menu legacy. DB bisa
sudah latest secara schema tetapi tetap memakai row menu lama seperti
`Code=listberita`, `Code=sentiment`, dan `NavigateUrl=TabelInformasi()`.

## Step 2 - Diagnosis Menu dan Permission

Masuk ke database yang benar dan pastikan koneksi tidak menunjuk ke DB lain:

```sql
SELECT DATABASE(), @@hostname;
```

Cari kandidat source menu Media Monitoring:

```sql
SELECT
  m.Id,
  m.Code,
  m.TypeId,
  m.ParentId,
  m.NavigateUrl,
  m.Description,
  COUNT(p.RoleId) AS allowed_count
FROM Menu m
LEFT JOIN Permission p
  ON p.ObjectName = 'Menu'
 AND p.ObjectId = m.Id
 AND p.ActionId = 'ALLOWED'
WHERE m.TypeId = 'SIDEMENU'
  AND (
    m.NavigateUrl = '#/news/list/semua_sumber'
    OR m.Code IN ('SemuaSumber', 'listberita', 'sentiment')
    OR m.Description IN ('Daftar Berita', 'Berita', 'Informasi')
  )
GROUP BY m.Id, m.Code, m.TypeId, m.ParentId, m.NavigateUrl, m.Description
ORDER BY allowed_count DESC, m.Id;
```

Interpretasi:

- Kandidat dengan route `#/news/list/semua_sumber` adalah format canonical dan
  mendapat prioritas tertinggi.
- Pada DB legacy, `listberita` atau `Berita` menjadi fallback untuk audience
  Daftar Berita.
- `sentiment` adalah fallback terakhir, bukan pilihan pertama.
- Kandidat tanpa `ALLOWED` tidak boleh dipakai sebagai source permission.
- Jika semua kandidat kosong atau semuanya memiliki `allowed_count=0`, hentikan
  proses dan laporkan hasil query. Jangan lanjut seed karena menu VoC akan tidak
  terlihat oleh user.

## Step 3 - Jalankan Seed VoC

Dari root repo OneBox:

```bash
cd /var/www/html/onecloud
mysql -u root -p onecloud < scriptdb/voc/voc_setup_all.sql
```

Sesuaikan nama database bila environment menggunakan nama berbeda.

Seed terbaru melakukan hal berikut:

- memilih source menu secara dinamis;
- memprioritaskan route canonical `#/news/list/semua_sumber`;
- fallback ke menu legacy yang relevan dan memiliki permission `ALLOWED`;
- mengambil `ParentId` source sebagai parent menu VoC;
- berhenti dengan error jika source atau parent tidak ditemukan;
- baru menghapus dan membuat ulang menu `voc%` setelah prasyarat valid;
- menyalin audience permission source ke menu VoC.

Error berikut berarti seed sengaja berhenti untuk mencegah menu orphan:

```text
VoC seed aborted: MM source menu/parent with ALLOWED permission was not found
```

Jangan mengabaikan error tersebut dan jangan langsung membuat menu VoC manual.
Perbaiki data source menu atau gunakan database snapshot environment yang memang
memiliki Media Monitoring lengkap.

Output sukses menampilkan ID connection, location, dan `mm_header_id`. Simpan
output tersebut untuk debugging deployment.

## Step 4 - Verifikasi Menu VoC

```sql
SELECT Id, Code, TypeId, ParentId, NavigateUrl, Description
FROM Menu
WHERE Code LIKE 'voc%'
ORDER BY Id;
```

Harus ada satu parent `voc` dan sembilan submenu:

```text
voc
voc_dashboard
voc_reviews
voc_locations
voc_competitors
voc_fetchjobs
voc_analysis
voc_insights
voc_reports
voc_settings
```

Validasi permission:

```sql
SELECT m.Code, m.ParentId, COUNT(p.RoleId) AS allowed_count
FROM Menu m
LEFT JOIN Permission p
  ON p.ObjectName = 'Menu'
 AND p.ObjectId = m.Id
 AND p.ActionId = 'ALLOWED'
WHERE m.Code LIKE 'voc%'
GROUP BY m.Code, m.ParentId
ORDER BY m.Code;
```

`allowed_count` harus lebih besar dari nol untuk menu yang ingin terlihat user.
Parent menu VoC harus menunjuk ke parent Media Monitoring yang dipilih seed.

## Step 5 - Seed User Dev dan Login

Jika environment memakai akun seed bersama:

```bash
cd /var/www/html/onecloud
mysql -u root -p onecloud < scriptdb/voc/voc_dev_user.sql
mysql -u root -p onecloud < scriptdb/voc/voc_dev_diagnose.sql
```

Akun referensi pada `voc_dev_user.sql` harus sudah memiliki akses Media
Monitoring. Jika akun referensi tidak ada di DB tersebut, ganti referensi ke
akun yang memang memiliki permission MM; jangan hanya mengganti password.

Setelah seed:

1. logout dari OneBox;
2. login ulang;
3. hard reload browser dengan `Ctrl+Shift+R`;
4. bila menu masih stale, restart worker/Swoole sesuai prosedur environment.

## Troubleshooting

### Migration latest, tetapi menu MM tidak cocok

Ini bukan kontradiksi. Migration mencatat versi schema, sedangkan row menu dan
permission adalah data environment. Jalankan diagnosis Step 2 dan seed terbaru.

### Menu VoC ada, tetapi tidak muncul

Periksa tiga hal:

```sql
SELECT Id, Email FROM User WHERE Email = '<email_user>';

SELECT RoleId, SiteId
FROM UserRole
WHERE UserId = (SELECT Id FROM User WHERE Email = '<email_user>')
  AND SiteId = <site_id>;
```

Bandingkan `RoleId` user dengan role yang mendapat `ALLOWED` pada query Step 4.

### Seed gagal dengan source tidak ditemukan

Jalankan query Step 2. Jika tidak ada kandidat yang valid, minta database
snapshot/dump dari environment yang sudah memiliki Media Monitoring. Restore
dump adalah opsi pemulihan environment, bukan langkah normal setiap developer.
Jangan menyalin ID menu dari environment lain tanpa memeriksa FK, site, role,
dan permission.

### Perlu rollback seed

Sebelum seed pada environment penting, buat backup DB. Seed hanya mengelola row
`Code LIKE 'voc%'` untuk menu VoC, tetapi juga mengelola master data VoC sesuai
isi file SQL. Rollback harus memakai backup/snapshot environment, bukan menebak
ID row secara manual.

## Handoff dan Git

Developer yang menerima patch:

```bash
cd /var/www/html/onecloud
git pull --ff-only origin <branch>
git diff --check
grep -n "voc_assert_menu_source" scriptdb/voc/voc_setup_all.sql
```

Commit hanya file seed dan dokumentasi yang memang berubah. Jangan commit
`.env`, `.env.local`, password, token, atau dump database.

Setelah deploy, kirimkan ke tim:

- branch/commit yang dipakai;
- hasil `migration.sh <env> status`;
- hasil diagnosis source menu;
- output `mm_header_id` dari seed;
- hasil query permission VoC;
- screenshot menu setelah logout, login, dan hard reload.

