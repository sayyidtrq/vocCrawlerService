# VoC di OneBox — Panduan Setup untuk Dev Lain

> Biar dev lain punya menu **Voice of Customer** DI Media Monitoring, lengkap dengan datanya.
> Semua contoh pakai SiteId 169 & DB `onecloud` — sesuaikan dengan env kamu.

## Ringkasan alur
Kode ikut git. **Data/menu = baris DB** (tidak ikut git) → harus di-seed. Data review = hasil **ingest** (bukan seed manual).

```
git pull  →  seed menu  →  seed master data  →  copy fixture  →  ingest  →  (React) npm+vite  →  hard-reload
```

---

## 0. Prasyarat
- Sudah `git pull` (dapat `VocController.php`, `app/views/Voc/`, `app/react-views/src/features/voc/`, `public/js/routes.js`).
- Tahu **nama DB** OneBox kamu (contoh: `onecloud`).
- Tahu **nama container webapp**: `docker ps --format '{{.Names}}' | grep webapp`.
- File seed & fixture ada di **repo OneBox** folder `scriptdb/voc/` (ikut `git pull`):
  - `scriptdb/voc/voc_setup_all.sql`  ← menu + master data (satu file, idempotent)
  - `scriptdb/voc/reviews_sample.json`

## 1. Seed SEMUA (menu + master data) — satu file
> Buka file, **sesuaikan `SET @site := 169;`** dengan SiteId env kamu, lalu jalankan:
```bash
mysql -uroot <db> < scriptdb/voc/voc_setup_all.sql
```
Ini nge-seed **menu VoC** (di sidebar Media Monitoring, env-agnostic — cari sendiri Id header MM + role)
**+ master data** (Provider PVD97, Category, Location, Connection). **Idempotent** — aman di-run ulang, tidak dobel.

> **Sudah pernah seed sebelum 2026-07-22? Jalankan ulang.**
> Sejak ADR-0001, row `Connection` = **record master cabang**, dan `Options` sekarang membawa
> `location` (nama cabang, `external_place_id`, target crawl), `onebox_location_id`, dan
> `provisioning` (status kirim ke VoC). Seed punya blok backfill untuk DB lama.
> Tanpa itu layar **Cabang** tampil dengan Place ID kosong.
>
> Backfill memakai `JSON_MERGE_PATCH` dan **hanya menyentuh row yang belum punya `Options.location`**,
> jadi `service_token`, `_sync_cursor`, dan `api_mode` yang sudah kamu isi tidak ikut tertimpa.

Output terakhir menampilkan **Id Connection** yang dibuat, contoh:
```
conn_hermina_depok  conn_hga_depok  loc_hermina_onebox  loc_hga_onebox  mm_header_id
1041                1042            1705                1706            254
```
**Catat `conn_hermina_depok` & `conn_hga_depok`** — dipakai di step 3 (ingest).
Setelah ini **menu muncul** (hard-reload). **Data terisi setelah INGEST** (step 3).

## 1b. Akun login yang bisa lihat Media Monitoring
> **Wajib kalau menu VoC tidak muncul padahal step 1 sukses.**
```bash
mysql -uroot <db> < scriptdb/voc/voc_dev_user.sql
```
Menu VoC menempel di sidebar **Media Monitoring**, dan akses MM ditentukan **Role**.
Akun default DB dev umumnya cuma punya role `Admin Tenant` yang **tidak** memegang izin menu MM —
jadi menunya tidak kelihatan walau seed master datanya sudah benar.

Script ini membuat rantai lengkap yang dibutuhkan `LoginController::choosenSite`:
`Contact` ⇄ `User` → `Member` → `Organization` → `Site`, plus `UserRole`.

**Cara kerjanya: mengkloning akun referensi**, bukan menebak dari struktur menu.
Role dan organisasi disalin dari akun yang memang sudah terbukti bisa membuka MM
(`admin-news@ciptadrasoft.com`, bisa diganti lewat `SET @ref_email`). Kalau akun
referensi jalan, kloningnya jalan. Ada 2 lapis cadangan kalau akun itu tidak ada di DB kamu.

Tautan `User.ContactId` ⇄ `Contact.UserId` diisi **dua arah** — akun referensi begitu,
dan pencarian kontak berdasarkan `UserId` bergantung pada arah baliknya.

Yang **tidak** disalin: row `Assignment` (kuota penugasan Ticket/Prospect) — itu pengaturan
beban kerja, bukan hak akses. Dan `Member` kedua milik referensi (penempatan unit kerja),
karena site sudah didapat dari `Member` pertama.

Login: **`voc.dev@onebox.local`** / **`voc12345`** (bisa diubah di bagian `SET` paling atas file).
Idempotent — di-run ulang akan me-reset password & membuka blokir `Failed`, bukan menggandakan akun.

> ⚠️ **DEV/LOKAL SAJA.** Passwordnya tertulis di file yang masuk git, jadi bukan rahasia.
> Sengaja dipisah dari `voc_setup_all.sql` supaya pembuatan akun tidak pernah jadi efek
> samping dari seed master data. Jangan pernah dijalankan di server staging/produksi.

## 2. Copy fixture ke /tmp (dibaca provider mode mock)
```bash
cp scriptdb/voc/reviews_sample.json /tmp/voc_reviews_sample.json
```
> `/tmp` di host WSL ter-mount ke `/tmp` container. Catatan: isi `/tmp` hilang saat WSL restart — copy ulang bila perlu.

## 3. INGEST (tarik review → jadi Ticket)
Ganti `<C>` = nama container webapp, `<connH>`/`<connG>` = Connection Id dari step 1.
```bash
C=$(docker ps -qf name=<webapp>)

# tarik review (mock) per connection
docker exec $C php app/bootstrap.php voice_of_customer_system receive <connH>
docker exec $C php app/bootstrap.php voice_of_customer_system receive <connG>

# proses jadi Ticket (kalau worker queue tidak jalan di dev) + apply analisa
docker exec $C php app/bootstrap.php voice_of_customer_system processpending <connH>
docker exec $C php app/bootstrap.php voice_of_customer_system processpending <connG>
docker exec $C php app/bootstrap.php voice_of_customer_system analysis <connH>
docker exec $C php app/bootstrap.php voice_of_customer_system analysis <connG>
```
Cek: `receive` menampilkan `sync done: fetched=… inserted=…`; `analysis` menampilkan `applyAnalysis: N ticket updated`.
Setelah ini Reviews & Dashboard terisi data.

## 4. (tidak perlu) Vite / Node
> **Semua screen VoC sekarang Volt murni** (termasuk Dashboard). **TIDAK perlu** `npm install` /
> vite / Node sama sekali. Cukup PHP + DB. (Dulu Dashboard pakai React embed; sudah di-rebuild ke Volt
> supaya robust & konsisten — tidak lagi tergantung `localhost:5173`.)

## 5. Buka & test
1. Buka Media Monitoring → **hard-reload (Ctrl+Shift+R)** (biar `routes.js` terbaru & menu ke-refresh).
2. Sidebar kiri → **Voice of Customer** → buka Dashboard / Reviews / Locations / Competitors / Fetch Jobs / Analysis.
3. URL jadi `.../Mediamonitoring/#/voc/<page>`.
4. Di **Locations**, tiap cabang harus punya Place ID terisi dan badge hijau **Tersinkron**.
   Kalau Place ID kosong → seed-nya versi lama, ulangi step 1.

---

## Troubleshooting
| Gejala | Penyebab | Fix |
|---|---|---|
| Menu VoC tidak muncul | belum seed / belum hard-reload / **role user tidak punya izin menu MM** | jalankan step 1 **dan step 1b**, lalu hard-reload |
| Login berhasil tapi sidebar MM kosong / tidak ada pilihan site | user tidak punya `Member` di organisasi milik site tsb — keanggotaan site datang dari `Member → Organization → Site`, bukan dari kolom di `User` | jalankan `voc_dev_user.sql` (step 1b) |
| `voc_dev_user.sql` menampilkan "GAGAL: site ini belum punya Organization" | `SET @site` menunjuk site yang tidak ada isinya | sesuaikan `SET @site` di baris atas file dengan SiteId env kamu |
| **Error SQL saat buka halaman:** `...near ') AND m.ParentId = 1'` di `/Menu/sideMenu` | user login **tidak punya satu pun row `UserRole`** → `getUserAllRole()` mengembalikan string kosong → `RoleId IN ()` yang bukan SQL sah | jalankan `voc_setup_all.sql` **dulu** (izin menu berasal dari sana), baru `voc_dev_user.sql`. Cek dengan `voc_dev_diagnose.sql` |

### Bingung kenapa tidak jalan? Jalankan diagnosa dulu
```bash
mysql -uroot <db> < scriptdb/voc/voc_dev_diagnose.sql
```
Read-only. Menyebutkan langsung penyebabnya: user belum ada, nol role, tidak punya `Member`
di site itu, menu belum di-seed, atau `SET @site` salah.
| Reviews kosong (0) | belum ingest | step 2–3 (copy fixture + ingest) |
| Semua screen "gagal load data" | Connection/site tidak match, atau ProviderId bukan PVD97 | cek Connection ProviderId='PVD97' & SiteId sesuai |
| Screen blank total | partial gagal render / `routes.js` belum ke-reload | hard-reload (Ctrl+Shift+R); cek Console |
| Seed gagal di baris Reference (validasi/panjang data) | pakai versi seed lama: `Reference.Code='VoiceOfCustomerSystem'` (21 karakter) terlalu panjang untuk kolom `Reference.Code` di sebagian environment | `git pull`, jalankan ulang `voc_setup_all.sql` — Code sekarang `Voc` |
| `Class \Service\Provider\VoiceOfCustomerSystemProvider not found` saat receive | DB masih menyimpan Code lama dari seed sebelumnya | jalankan ulang `voc_setup_all.sql` (sudah ada UPDATE perbaikannya), atau `UPDATE Reference SET Code='Voc' WHERE Id='PVD97';` |
| Layar **Cabang**: Place ID kosong / badge "Belum tersinkron" di cabang pilot | DB di-seed sebelum ADR-0001, `Options.location` belum ada | jalankan ulang `voc_setup_all.sql` (backfill otomatis, tidak menimpa token/cursor) |
| Tambah cabang gagal: *"Belum ada koneksi Voice of Customer di site ini"* | kredensial VoC diwarisi dari koneksi yang sudah ada — kalau belum ada satu pun, tidak ada yang bisa diwarisi | jalankan `voc_setup_all.sql` dulu (step 1) |
| Cabang tidak bisa dihapus: *"sudah punya N review"* | menghapus `Connection` memutus `Message.ConnectionId`, review lama hilang dari layar Reviews | pakai tombol **nonaktifkan**, bukan hapus |

## Untuk produksi (nanti)
- Seed menu/master data → jadikan **migration** resmi.
- Set Connection ke **live** (`Options.mock=false` + `Url`/`UserId`/`Password` creds service user VoC) — ganti ingest mock jadi pull API asli.
