# Pemulihan DB staging release/1.123.0 — VoC

**URGENT.** Staging `https://staging.onebox.co.id/1_123_0/` sudah tayang, tetapi fungsionalitas VoC mati: Connection dan Provider tidak ada. Seeding `scriptdb/voc/voc_setup_all.sql` dijalankan untuk memperbaikinya, dan justru menghapus hasil migrasi 1.123.

Semua angka dan kutipan di dokumen ini dibaca langsung dari repo `onecloud` (`release/1.123.0` dan `feature/voc`), bukan dari ingatan. Yang belum bisa dibaca — karena ada di DB staging — ditandai eksplisit sebagai **belum diketahui**, bukan ditebak.

Dokumen pendamping: [`PLAN_RELEASE_1_123_0_KE_PRODUKSI.md`](PLAN_RELEASE_1_123_0_KE_PRODUKSI.md)

---

## Ringkasan satu paragraf

`voc_setup_all.sql` bukan skrip penambah data — ia **membangun ulang menu VoC dari nol**, dan langkah pertamanya menghapus SELURUH baris `Menu` ber-`Code LIKE 'voc%'` beserta permission-nya. Migrasi 1.123 membangun 27 kode menu bergaya modul (`HEADERMENU` + `SIDEMENU` + `SUBSIDEMENU`); seed hanya membangun kembali 10 bergaya sidebar lama di bawah Media Monitoring. Hasilnya modul VoC di staging kehilangan strukturnya. Kabar baiknya: tabel `phalcon_migrations` **tidak disentuh** seed sama sekali, jadi yang rusak adalah AKIBAT migrasi, bukan catatannya — dan karena migrasi `Menu.php` sendiri bersifat bangun-ulang, menjalankannya kembali di staging akan memulihkan keadaan dengan bersih. Yang tidak boleh dilakukan: menjalankan `voc_rollback.sql`, yang berkasnya sendiri melarang dipakai di staging.

---

# BAGIAN 1 — APA YANG SEBENARNYA TERJADI

## 1.1 Baris yang merusak

`scriptdb/voc/voc_setup_all.sql`, baris 204–206:

```sql
-- Bersihkan menu VoC lama (idempotent) setelah source valid.
DELETE FROM Permission WHERE ObjectName='Menu' AND ObjectId IN (SELECT Id FROM (SELECT Id FROM Menu WHERE Code LIKE 'voc%') t);
DELETE FROM Menu WHERE Code LIKE 'voc%';
```

Komentarnya menulis "idempotent", dan itu benar **untuk dirinya sendiri** — menjalankan seed dua kali menghasilkan keadaan yang sama. Yang tidak benar adalah menganggapnya aman di database yang menunya dibangun oleh pihak lain. `LIKE 'voc%'` tidak membedakan menu buatan seed dari menu buatan migrasi.

## 1.2 Yang dihapus vs yang dibangun kembali

| | Migrasi 1.123 (`1786200000000000_1_123_0/Menu.php`) | Seed `voc_setup_all.sql` |
| --- | --- | --- |
| Kode `voc%` unik | **27** | **10** |
| `HEADERMENU` | 1 (`voc_header`) | 0 |
| `SIDEMENU` | 4 | 1 |
| `SUBSIDEMENU` | 17 | 9 |
| Induk | struktur modul VoC sendiri | menu Media Monitoring |

Kode yang dibangun migrasi tetapi **tidak** dibangun kembali oleh seed — 17 di antaranya:

```
voc_analysis_comp        voc_analysis_competi     voc_analysis_competitor
voc_benefit              voc_compare              voc_fetchjobs_comp
voc_fetchjobs_compet     voc_fetchjobs_competitor voc_header
voc_omnichannel          voc_output               voc_profile
voc_schedules            voc_setting              voc_transaksi
voc_trend                voc_workspace
```

Permission untuk semuanya ikut terhapus di baris 205.

## 1.3 Yang TIDAK terjadi — dan ini menentukan solusinya

**`phalcon_migrations` tidak disentuh.** Tidak ada satu pun `INSERT`, `UPDATE`, atau `DELETE` terhadap tabel itu di `voc_setup_all.sql` (diperiksa atas seluruh 277 barisnya).

Artinya:

- Catatan bahwa versi `1786200000000000_1_123_0` sudah dijalankan **masih ada**.
- Karena Phalcon tidak pernah menjalankan ulang versi yang sudah tercatat, **memperbaiki berkas migrasi atau men-deploy ulang tidak akan menolong sama sekali**.
- Yang hilang adalah DATA hasil migrasi, bukan migrasinya.

Ini persis jebakan yang sudah didokumentasikan di `PLAN_RELEASE_1_123_0_KE_PRODUKSI.md` §1.3.

## 1.4 Kenapa di staging aman menjalankan ulang, padahal di dev berbahaya

Migrasi `Menu.php` release melakukan hal yang **sama** dengan seed — ia juga membangun ulang, bukan menambal:

```php
private function resetVocMenu_1785139084381840(): void
{
    ... "DELETE FROM Permission ..."
    self::$connection->execute("DELETE FROM Menu WHERE Code LIKE 'voc%'");
}
```

Di **dev** itu berbahaya, karena dev punya menu dari branch lain (3513, 3523, 3529) yang ikut terhapus dan tidak dibangun kembali — sebab itulah dokumen rencana melarang menjalankannya di dev.

Di **staging** justru sebaliknya: staging hanya memuat 1.123. Tidak ada menu `voc%` milik pihak lain yang bisa jadi korban. Wipe-nya menghapus 10 menu buatan seed, lalu membangun 27 menu yang benar. **Itu tepat yang kita inginkan.**

> **Prasyarat yang harus dibuktikan dulu, bukan diasumsikan:** bahwa staging benar-benar tidak punya menu `voc%` dari sumber lain. Dibuktikan di Tahap 0 langkah D0-3.

## 1.5 Kerusakan sampingan yang mungkin ada

`voc_setup_all.sql` juga menulis hal lain. Semuanya memakai **`SET @site := 169`** yang di-hardcode — nilai untuk DB dev. Kalau SiteId staging bukan 169, data ini masuk ke site yang salah dan tidak akan terlihat di layar mana pun.

| Yang ditulis | Baris | Sifat | Perlu dibersihkan? |
| --- | --- | --- | --- |
| `Reference` GBUSINESS | 20–22 | ber-guard `NOT EXISTS` | tidak — master data standar OneBox |
| `Reference` PVD99 (Provider Voc) | 29–31 | ber-guard `NOT EXISTS` | **tidak — ini justru yang dibutuhkan staging** |
| 18 baris `Category` untuk `@site` | 47–69 | ber-guard | tergantung SiteId staging — lihat D0-5 |
| `Location` "Hermina Depok", "HGA Depok" | 72–80 | global, ber-guard | kemungkinan mencemari master lokasi staging |
| 2 `Connection` **mock** (`'mock',true`) | 94–122 | ber-guard | ya — mock tidak berguna di staging |

Dua Connection itu memakai `TargetId` `'4'` dan `'2'`, yaitu id lokasi milik Crawler dev, dan `mock_file` menunjuk `/tmp/voc_reviews_sample.json`. Keduanya tidak akan pernah menarik data sungguhan.

---

# BAGIAN 2 — YANG TIDAK BOLEH DILAKUKAN

## ❌ Jangan jalankan `scriptdb/voc/voc_rollback.sql` di staging

Berkas itu melarang dirinya sendiri, di barisnya sendiri:

```
-- ⚠️ HANYA UNTUK ENVIRONMENT DEV/LOKAL. JANGAN di staging/produksi.
```

Dan isinya memang akan memperparah:

| Baris | Pernyataan | Akibat di staging |
| --- | --- | --- |
| 165 | `DELETE FROM Menu WHERE Code LIKE 'voc%'` | menghapus menu 1.123 **lagi** |
| 161 | `DELETE FROM Permission ...` | menghapus permission-nya lagi |
| 213 | `DELETE FROM Reference ...` | berpotensi menghapus Provider yang justru dibutuhkan |
| 142–148 | `DELETE FROM User/Contact/UserRole/Member` | menghapus akun |

Baris 213 adalah jenis pernyataan yang dulu memicu insiden PVD97 (id provider yang disangka milik VoC ternyata dipegang IKS EPIC Softphone). Di staging risikonya sama.

## ❌ Jangan jalankan ulang `voc_setup_all.sql`

Ia akan mengulangi wipe di baris 206 — menghapus lagi apa pun yang baru dipulihkan.

## ❌ Jangan deploy ulang atau `git revert` berharap migrasi jalan lagi

`phalcon_migrations` masih mencatat versinya. Deploy berapa kali pun tidak akan menjalankannya kembali.

---

# BAGIAN 3 — RENCANA PEMULIHAN

Urutannya penting. Tahap 0 wajib selesai dan hasilnya dibaca sebelum Tahap 1 dijalankan.

## Tahap 0 — Cadangan dan diagnosis (BACA SAJA, tidak mengubah apa pun)

### D0-1 · Cadangan dulu, tanpa kecuali

Sebelum satu pun pernyataan yang mengubah data dijalankan:

```bash
mysqldump -u<user> -p <db_staging> \
  Menu Permission Connection Reference Category Location phalcon_migrations \
  > bak_staging_1123_$(date +%Y%m%d_%H%M%S).sql
```

Tujuh tabel itu adalah semua yang disentuh seed maupun rencana ini. Simpan berkasnya di luar server kalau bisa.

### D0-2 · Apakah catatan migrasinya memang masih ada?

```sql
SELECT version, start_time, end_time
  FROM phalcon_migrations
 WHERE version LIKE '%\_1\_123\_0'
 ORDER BY version;
```

**Yang diharapkan:** ada baris `1786200000000000_1_123_0`.
**Kalau tidak ada:** berarti dugaan di §1.3 salah untuk staging — berhenti, laporkan, jangan lanjut ke Tahap 1.

### D0-3 · Menu VoC yang ada sekarang, dan apakah ada milik pihak lain

```sql
SELECT TypeId, COUNT(*) AS jumlah
  FROM Menu WHERE Code LIKE 'voc%'
 GROUP BY TypeId;

SELECT Id, Code, TypeId, Description, ParentId, NavigateUrl
  FROM Menu WHERE Code LIKE 'voc%'
 ORDER BY TypeId, Code;
```

**Yang diharapkan bila dugaan benar:** ~10 baris, `SIDEMENU` 1 + `SUBSIDEMENU` 9, tidak ada `HEADERMENU`.

**Ini juga pembuktian prasyarat §1.4:** kalau muncul kode `voc%` yang BUKAN salah satu dari 27 milik migrasi maupun 10 milik seed, berarti ada sumber ketiga — berhenti dan laporkan sebelum menjalankan wipe apa pun.

### D0-4 · Permission yang tersisa

```sql
SELECT COUNT(*) AS permission_voc
  FROM Permission p
  JOIN Menu m ON m.Id = p.ObjectId
 WHERE p.ObjectName = 'Menu' AND m.Code LIKE 'voc%';
```

Catat angkanya — dipakai sebagai pembanding di Tahap 4.

### D0-5 · SiteId staging yang sebenarnya

Seed memakai `169` yang di-hardcode. Belum diketahui apakah itu SiteId staging.

```sql
SELECT Id, Code, Description FROM Site ORDER BY Id;

-- ke site mana Category VoC masuk?
SELECT SiteId, COUNT(*) AS kategori_voc
  FROM Category
 WHERE Remarks IN ('doctor_service','nurse_service','administration','waiting_time',
                   'cleanliness','facility','parking','billing','pharmacy',
                   'emergency_room','inpatient','customer_service','booking_system',
                   'staff_communication','security','food','general_praise','other')
 GROUP BY SiteId;

-- ke site mana Connection VoC masuk?
SELECT Id, SiteId, TargetId, Name, StatusId, Enabled,
       JSON_EXTRACT(Options,'$.mock') AS mock
  FROM Connection WHERE ProviderId = 'PVD99';
```

Hasil ketiganya menentukan Tahap 2 dan Tahap 3.

### D0-6 · Provider dan Media — apakah sudah ada dan milik siapa

```sql
SELECT Id, Code, Description, GroupId, Enabled
  FROM Reference
 WHERE Id IN ('PVD99','GBUSINESS');
```

**Wajib diperiksa:** kalau `PVD99` ada tetapi `Code`-nya BUKAN `'Voc'`, id itu dipegang modul lain. **Jangan di-UPDATE** — itu persis insiden PVD97. Eskalasi ke senior dev; VoC yang harus pindah id, bukan pemiliknya yang ditimpa.

---

## Tahap 1 — Pulihkan hasil migrasi 1.123

Dijalankan **hanya jika** D0-2 menemukan barisnya dan D0-3 tidak menemukan sumber ketiga.

### T1-1 · Hapus catatan versinya

```sql
START TRANSACTION;

SELECT version, start_time FROM phalcon_migrations
 WHERE version = '1786200000000000_1_123_0';   -- pastikan tepat 1 baris

DELETE FROM phalcon_migrations
 WHERE version = '1786200000000000_1_123_0';

COMMIT;
```

### T1-2 · Jalankan migrasinya kembali

Lewat runner yang sama dengan yang dipakai deploy staging (bukan mysql langsung — migrasinya PHP, bukan SQL):

```bash
# di dalam container/host aplikasi staging
php app/migrate.php        # atau ./migration.sh <env staging> run
```

> **Perhatikan dua hal yang sudah tercatat di dokumen rencana:**
> 1. `TARGET_VERSION` berarti "migrasi SAMPAI versi itu", bukan "hanya versi itu". Pastikan tidak ada versi lama yang ikut terpanggil.
> 2. Runner mencetak password DB dalam teks polos ke stdout. Jangan tempel outputnya ke chat atau tiket.

### T1-3 · Kalau runner tidak bisa dipakai

Kalau karena satu dan lain hal migrasi tidak bisa dijalankan dari staging, **jangan menulis ulang menunya dengan tangan.** Menyalin 27 baris `INSERT` secara manual menciptakan versi ketiga dari kebenaran yang sama, dan itu akar masalah yang sedang kita perbaiki. Laporkan sebagai blocker.

---

## Tahap 2 — Bersihkan sisa seed yang tidak semestinya di staging

Dijalankan setelah Tahap 1 berhasil, dan **isinya ditentukan oleh hasil D0-5**. Semua di bawah ini dibungkus transaksi, dengan `SELECT` pendahulu untuk melihat berapa baris yang akan kena.

### T2-1 · Connection mock

```sql
-- LIHAT DULU
SELECT Id, SiteId, TargetId, Name, JSON_EXTRACT(Options,'$.mock') AS mock
  FROM Connection
 WHERE ProviderId='PVD99' AND JSON_EXTRACT(Options,'$.mock') = TRUE;

-- Baru hapus, kalau memang tidak ada Ticket/Message yang menempel padanya:
SELECT ConnectionId, COUNT(*) FROM Message
 WHERE ConnectionId IN (<id dari query di atas>) GROUP BY ConnectionId;
```

Kalau ada Message yang menempel, **jangan dihapus** — ubah saja jadi non-mock di Tahap 3. Menghapus Connection yang punya Message akan meninggalkan review yatim.

### T2-2 · Category di site yang salah

Hanya kalau D0-5 menunjukkan kategori masuk ke SiteId yang bukan milik staging:

```sql
SELECT Id, SiteId, Code, Description FROM Category
 WHERE SiteId = 169 AND Remarks IN ( ...18 slug... );
```

Kalau site 169 memang tidak ada di staging, baris-baris ini yatim dan aman dibuang. Kalau 169 ternyata milik tenant lain di staging, **jangan disentuh** — laporkan.

### T2-3 · Location "Hermina Depok" / "HGA Depok"

```sql
SELECT Id, Description, City FROM Location
 WHERE Description IN ('Hermina Depok','HGA Depok');

-- apakah dirujuk Ticket?
SELECT LocationId, COUNT(*) FROM Ticket
 WHERE LocationId IN (<id di atas>) GROUP BY LocationId;
```

Kalau dirujuk, biarkan. `voc_rollback.sql` pun sengaja tidak menghapusnya, dengan alasan yang sama.

---

## Tahap 3 — Seeding Connection untuk staging (tujuan awalnya)

Ini yang sebenarnya dicari sejak awal: supaya VoC staging berfungsi.

**Jangan pakai `voc_setup_all.sql`.** Yang dibutuhkan hanya bagian Connection-nya, dengan tiga perbedaan wajib:

| | `voc_setup_all.sql` | Yang dibutuhkan staging |
| --- | --- | --- |
| `SET @site` | `169` (dev, di-hardcode) | SiteId staging dari D0-5 |
| `mock` | `true` | `false` |
| Url / token | kosong | endpoint + service token Crawler staging |
| `TargetId` | `'4'`, `'2'` (lokasi dev) | id lokasi Crawler untuk staging |

Bentuk perintah non-mock sudah tertulis di `voc_setup_all.sql` baris 264–272, dan berkas itu sendiri memperingatkan agar **tidak di-commit** karena memuat kredensial:

```sql
UPDATE Connection
   SET Url='http://<host-crawler-staging>:8000',
       UserId='<email akun VoC>',
       Password='<password>',
       Options=JSON_MERGE_PATCH(Options, JSON_OBJECT(
                 'mock',false,'api_mode','service',
                 'company_id',<company_id>,
                 'service_token','<token>'))
 WHERE SiteId=@site AND ProviderId='PVD99';
```

Verifikasi kredensialnya menunjuk company yang benar SEBELUM menarik data:

```bash
docker exec <container> php app/bootstrap.php voice_of_customer_system whoami <connId>
```

**Yang belum diketahui dan harus disiapkan dulu:** host Crawler staging, company_id, service token, dan daftar lokasi yang mau dipantau di staging. Tanpa keempatnya Tahap 3 tidak bisa dijalankan.

---

## Tahap 4 — Verifikasi

| # | Pemeriksaan | Nilai yang benar |
| --- | --- | --- |
| V1 | `SELECT COUNT(DISTINCT Code) FROM Menu WHERE Code LIKE 'voc%'` | **27** |
| V2 | `SELECT COUNT(*) FROM Menu WHERE Code LIKE 'voc%' AND TypeId='HEADERMENU'` | **1** (`voc_header`) |
| V3 | Permission `voc%` | ≥ angka D0-4, dan tidak nol |
| V4 | `phalcon_migrations` memuat `1786200000000000_1_123_0` | ada, `end_time` terisi |
| V5 | Login staging → modul Voice of Customer muncul di header | tampil |
| V6 | Layar Lokasi / Fetch Jobs terbuka tanpa 500 | terbuka |
| V7 | `whoami <connId>` menjawab company yang benar | cocok |

Kalau V1 mengembalikan 10, migrasi belum benar-benar jalan ulang — periksa `TARGET_VERSION` dan output runner.

---

# BAGIAN 4 — YANG BELUM DIKETAHUI

Ditulis eksplisit supaya tidak ada yang dianggap sudah pasti:

1. **SiteId staging.** Seluruh Tahap 2 dan 3 bergantung padanya. Belum pernah dibaca.
2. **Apakah `phalcon_migrations` staging benar memuat `1786200000000000_1_123_0`.** Kalau tidak, seluruh Tahap 1 tidak berlaku dan masalahnya lain.
3. **Apakah seed berhasil sampai selesai.** `voc_setup_all.sql` punya fail-fast di baris 191–202 yang membatalkan bila menu sumber Media Monitoring tidak ditemukan. Kalau ia berhenti di sana, wipe di baris 205–206 **tidak** ikut jalan — dan kerusakannya bukan yang dijelaskan dokumen ini. D0-3 akan menunjukkannya.
4. **Siapa pemilik `PVD99` di staging.** Kalau bukan VoC, ada masalah yang lebih besar dan berbeda.
5. **Apakah sudah ada Message/Ticket VoC di staging.** Menentukan apakah Connection boleh dihapus atau hanya diubah.

---

## Risiko

| Risiko | Dampak | Penanganan |
| --- | --- | --- |
| Menjalankan `voc_rollback.sql` "supaya bersih" | menu terhapus lagi + provider modul lain berpotensi hilang | dilarang; lihat Bagian 2 |
| Migrasi dijalankan ulang tanpa cadangan | tidak ada jalan kembali kalau meleset | D0-1 wajib |
| Staging ternyata punya menu `voc%` dari sumber lain | wipe migrasi menghapusnya dan tidak membangun kembali | D0-3 sebagai gerbang |
| `PVD99` dipegang modul lain lalu di-UPDATE | mengulang insiden PVD97 | D0-6; eskalasi, jangan UPDATE |
| Connection mock dihapus padahal punya Message | review jadi yatim | T2-1 memeriksa dulu |
| `TARGET_VERSION` menarik migrasi versi lama | migrasi lama ikut jalan di staging | periksa nilainya sebelum T1-2 |
| Output runner memuat password | bocor ke log/tiket | jangan tempel output mentah |

---

## Pelajaran untuk dicatat

`voc_setup_all.sql` menulis dirinya sebagai "idempotent, aman di-run ulang". Klaim itu benar terhadap dirinya sendiri dan menyesatkan terhadap lingkungan yang tidak ia buat sendiri. Skrip yang mengandung `DELETE ... LIKE 'voc%'` tidak bisa disebut aman tanpa menyebut **milik siapa** baris yang dihapusnya.

Dua tindak lanjut yang perlu masuk backlog:

1. Beri `voc_setup_all.sql` gerbang lingkungan yang sama tegasnya dengan yang sudah dipunyai `voc_rollback.sql` ("HANYA DEV/LOKAL"), atau ubah wipe-nya agar hanya menghapus 10 kode yang memang ia buat.
2. Hilangkan `SET @site := 169` yang di-hardcode — seed yang menulis ke site salah gagal secara diam-diam, dan itu jenis kegagalan yang paling lama ketahuan.

---

# BAGIAN 5 — HASIL DIAGNOSIS STAGING (10 September 2026)

Dijalankan Sayyid di `onecloud_rel` (server `xtradb`) lewat phpMyAdmin.

## 5.1 Yang terkonfirmasi

| # | Pemeriksaan | Hasil | Artinya |
| --- | --- | --- | --- |
| D0-2 | `phalcon_migrations` | **ada** — `1786200000000000_1_123_0`, 2026-09-03 07:39:55, tepat 1 baris | dugaan §1.3 benar: catatannya utuh |
| D0-5 | `Site` | **209 baris** | staging berbagi DB dengan banyak tenant |
| D0-5 | `Connection` PVD99 | **2 baris, keduanya SiteId 169, `mock=true`** — Id 985 (TargetId 4) & 986 (TargetId 2) | seed benar-benar jalan sampai selesai |
| D0-6 | `Reference` | `GBUSINESS` dan `PVD99` **ada** | provider tersedia |

## 5.2 Yang MASIH belum diketahui

- **D0-3 dan D0-4 belum dijalankan** — keadaan `Menu` dan `Permission` untuk `voc%`. Selama ini belum dibaca, Tahap 1 tidak boleh dijalankan.
- **`Reference.Code` untuk PVD99 belum terlihat.** Query yang dijalankan hanya memilih `Id, Description`. Kolom `Code` yang menentukan apakah id itu milik VoC (`'Voc'`) atau modul lain.

## 5.3 TEMUAN BARU — kenapa alertnya mustahil dipuaskan

Laporan tambahan: setelah 3387 dan 3385 masuk release, UI dan fungsionalitas bisa diakses; yang gagal hanya penambahan lokasi, dengan alert menyuruh menjalankan `voc_setup_all.sql`.

Alert itu ada di `VocController.php` baris **6687** (cabang) dan **9222** (kompetitor), dan hanya muncul ketika `vocCredentialTemplate($siteId)` mengembalikan `null`.

Fungsi itu menyaring calon sumber kredensial, dan saringan pertamanya:

```php
// Tanpa Url tidak ada yang bisa dihubungi, seberapa pun
// lengkapnya kredensial di row itu.
if (trim((string) $c->Url) === '') {
    continue;
}
```

Sedangkan `voc_setup_all.sql` menulis Connection-nya begini (baris 95):

```sql
SELECT @site,'GBUSINESS','PVD99','VOC','VoC System - Hermina Depok','','',0,'','Onebox',
--                                                                  ^^ ^^   ^^
--                                                       UserId Password  Url  <- semuanya kosong
```

**Maka skrip yang ditunjuk alert itu menghasilkan tepat baris yang ditolak oleh kode yang memunculkan alert itu.** Menjalankan `voc_setup_all.sql` tidak akan pernah menghilangkan pesan yang menyuruh menjalankannya — di site mana pun, termasuk 169.

Dua baris mock di site 169 adalah buktinya: keduanya ada, keduanya terbaca sebagai koneksi VoC (`Options.location` terisi, jadi lolos `isVocConnection`), dan keduanya tetap ditolak sebagai sumber kredensial karena `Url` kosong.

### Koreksi terhadap dugaan "cacat design"

Pewarisan kredensialnya sendiri **disengaja dan masuk akal**, dan alasannya ditulis di kodenya:

> Kredensial VoC tidak diminta ke user: diwarisi dari koneksi VoC yang sudah ada di site ini, supaya tidak ada credential entry di UI dan tidak ada kredensial nyasar ke site lain.

Yang cacat lebih sempit dan lebih spesifik, tiga hal:

1. **Tidak ada jalur bootstrap.** Baris VoC pertama di sebuah site hanya bisa lahir dari SQL. Tidak ada layar admin untuknya.
2. **Alert menunjuk berkas yang tidak ada di staging.** `scriptdb/voc/*` sengaja dikecualikan dari PR (Bagian 2 dokumen rencana), jadi instruksinya tidak bisa diikuti di sana.
3. **Berkas yang ditunjuk tidak menyelesaikan masalahnya**, karena alasan di atas.

## 5.4 Koreksi: kenapa mengulang merge 3387 tidak menolong

Migrasi `1786200000000000_1_123_0` berisi enam berkas: `Benefit`, `Menu`, `MessageContent`, `Reference`, `Ticket`, `VocSchedule`. **Tidak ada satu pun yang membuat baris `Connection`.**

Connection adalah data runtime — lahir dari `locationSave()`/`competitorSave()` lewat UI, atau dari seed. Berapa kali pun 3387 di-merge ulang dan di-deploy, tidak akan ada Connection yang muncul. Itu sebabnya percobaan kemarin tidak membuahkan hasil, dan itu bukan kesalahan langkahnya.

## 5.5 Rencana yang direvisi

Masalahnya terbelah dua, dan keduanya berdiri sendiri:

| | Masalah | Perbaikan |
| --- | --- | --- |
| **A** | Menu 1.123 kemungkinan tertimpa seed | Tahap 1 — **tahan dulu sampai D0-3/D0-4 dibaca**. Kalau UI sudah benar bentuknya, mungkin tidak perlu sama sekali. |
| **B** | Tidak ada Connection yang bisa jadi sumber kredensial | `VOC_BOOTSTRAP_CONNECTION_STAGING.sql` — berdiri sendiri, tidak menunggu A |

**B bisa dikerjakan lebih dulu.** Ia tidak menyentuh `Menu`, `Permission`, maupun `phalcon_migrations`, jadi tidak bisa merusak apa pun yang sedang dipertimbangkan di A.

Berkasnya: `../../07-data-and-seeding/sql/VOC_BOOTSTRAP_CONNECTION_STAGING.sql`

Empat syarat yang dijaga gerbangnya, semuanya dibaca dari `vocCredentialTemplate()` dan `punyaServiceToken()`:

1. `Url` tidak kosong
2. `Options.api_mode = 'service'`
3. `Options.service_token` terisi
4. `Options.location` ada

Ditambah gerbang yang menolak `@site = 169` dan menolak jalan bila `Reference.PVD99` ber-Code selain `'Voc'`.

## 5.6 Dua baris mock di site 169

Belum tentu perlu dihapus, dan **jangan dihapus sebelum diperiksa**:

```sql
SELECT ConnectionId, COUNT(*) FROM Message
 WHERE ConnectionId IN (985, 986) GROUP BY ConnectionId;
```

- Ada Message → **biarkan**, menghapusnya membuat review yatim. Cukup nonaktifkan: `StatusId='CNS3'`.
- Tidak ada Message dan site 169 bukan milik tenant lain di staging → aman dibuang.

Site 169 ada di antara 209 site, jadi ia **bukan** id yang mengambang — perlu dipastikan dulu milik siapa sebelum menyentuh apa pun di sana.
