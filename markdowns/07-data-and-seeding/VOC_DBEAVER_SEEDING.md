# Seeding VoC via DBeaver — Tutorial untuk Pemula

> Buat teman-teman yang belum nyaman dengan MySQL terminal. Pakai **DBeaver** (GUI database, gratis)
> untuk connect ke DB OneBox lokal dan menjalankan seed VoC.
> Contoh pakai DB dev lokal (WSL). Ganti nilai kalau env kamu beda.

---

## Bagian 0 — Yang perlu disiapkan
- OneBox lokal (Docker) + MySQL-nya **sudah jalan** (kalau app OneBox bisa dibuka di browser, MySQL jalan).
- File seed sudah ada (habis `git pull`): **`scriptdb/voc/voc_setup_all.sql`** di repo OneBox.
- **Kredensial DB**: ada di **`app/config/development.php`** bagian `'database'` (field `username` & `password`).
  Buka file itu sebentar, catat `username` (biasanya `onecloud`) dan `password`-nya. Dipakai di Bagian 2.
  > ⚠️ Jangan share password itu di chat/dokumen publik.

---

## Bagian 1 — Install DBeaver
1. Download **DBeaver Community Edition** (gratis): https://dbeaver.io/download/
2. Install seperti aplikasi biasa (Next → Next → Finish).
3. Buka DBeaver.

---

## Bagian 2 — Bikin koneksi ke MySQL OneBox

1. Klik ikon **colokan (+)** di kiri atas, atau menu **Database → New Database Connection**.
2. Pilih **MySQL** → **Next**.
3. Isi form koneksi:

   | Field | Isi |
   |---|---|
   | **Server Host** | `127.0.0.1` |
   | **Port** | `3306` |
   | **Database** | `onecloud` *(nama DB OneBox kamu — cek `ONECLOUD_DB_NAME` di `.env` kalau ragu)* |
   | **Username** | dari `development.php` (biasanya `onecloud`) |
   | **Password** | dari `development.php` (field `password` untuk user itu) |

   > ⚠️ **Jangan pakai user `root`** — di server ini root cuma bisa lewat socket, nggak bisa dari DBeaver.
   > Pakai user **aplikasi** (`onecloud`) yang ada di `development.php`.

4. Centang **Save password** biar nggak nanya terus.
5. Klik **Test Connection**.
   - Kalau diminta **download driver MySQL** → klik **Download** (sekali doang).
   - Kalau muncul **"Connected"** ✅ → lanjut. Klik **Finish**.

   <details><summary>Kalau Test Connection GAGAL</summary>

   - **"Public Key Retrieval is not allowed"** → buka tab **Driver properties**, cari `allowPublicKeyRetrieval` → set **TRUE**. Test lagi.
   - **"Communications link failure" / connection refused** → MySQL belum jalan, atau `127.0.0.1` nggak nyampe ke WSL. Coba host pakai IP WSL: buka terminal WSL, ketik `hostname -I`, ambil IP pertama (mis. `172.x.x.x`), pakai itu sebagai Server Host.
   - **"Access denied for user …"** → username/password nggak cocok; cek ulang `app/config/development.php` bagian `'database'`.
   </details>

---

## Bagian 3 — Jalankan seed (voc_setup_all.sql)

1. Di panel kiri (Database Navigator), **klik koneksi `onecloud`** yang barusan dibuat (biar SQL-nya jalan di DB yang bener).
2. Buka SQL Editor: menu **SQL Editor → New SQL Script** (atau ikon **SQL** di toolbar).
3. Masukkan isi file seed — dua cara:
   - **Cara A (paste):** buka `scriptdb/voc/voc_setup_all.sql` pakai Notepad, copy semua, paste ke editor DBeaver.
   - **Cara B (buka file):** menu **File → Open File** → pilih `voc_setup_all.sql`.
4. **(Penting)** Di baris atas ada `SET @site := 169;` — **ganti `169`** kalau SiteId env kamu beda.
5. **Jalankan seluruh script** (bukan satu baris):
   - Klik menu **SQL Editor → Execute SQL Script**, atau tekan **`Alt + X`**.
   - ⚠️ Jangan pakai `Ctrl + Enter` (itu cuma jalanin 1 baris). Seed ini banyak perintah + variabel, harus **Alt + X**.
6. Di bawah, tab **Statistics/Output** akan nunjukin hasil. Baris terakhir menampilkan **Connection Id**:
   ```
   conn_hermina_depok  conn_hga_depok  loc_hermina_onebox  loc_hga_onebox  mm_header_id
   1041                1042            1705                1706            254
   ```
   **Catat `conn_hermina_depok` & `conn_hga_depok`** — dipakai untuk ingest (Bagian 5).

   > Seed ini **idempotent** — kalau nggak sengaja dijalanin 2x, aman, nggak dobel.
   > Kalau DBeaver kamu mode **manual commit**, klik tombol **Commit** (ikon centang hijau) setelah jalan.
   > (Default MySQL auto-commit, biasanya nggak perlu.)

---

## Bagian 4 — Cek hasil (opsional)

Di SQL Editor, ketik ini lalu **`Ctrl + Enter`**:
```sql
SELECT Id, Code, Description, TypeId FROM Menu WHERE Code LIKE 'voc%' ORDER BY Priority;
```
Harusnya muncul 10 baris (grup `voc` + 9 submenu). Kalau ada → seed berhasil.

Terus di browser: buka **Media Monitoring → hard-reload (Ctrl+Shift+R)** → menu **"Voice of Customer"** muncul di sidebar kiri.

---

## Bagian 5 — Ingest data (masih lewat terminal)

DBeaver cuma buat SQL. **Isi data review (ingest) tetap lewat terminal** karena manggil script PHP.
Di terminal WSL (ganti `<H>`/`<G>` = Connection Id dari Bagian 3):
```bash
# copy fixture sekali
cp scriptdb/voc/reviews_sample.json /tmp/voc_reviews_sample.json

# ingest
C=$(docker ps -qf name=webapp)
docker exec $C php app/bootstrap.php voice_of_customer_system receive <H>
docker exec $C php app/bootstrap.php voice_of_customer_system receive <G>
docker exec $C php app/bootstrap.php voice_of_customer_system processpending <H>
docker exec $C php app/bootstrap.php voice_of_customer_system processpending <G>
docker exec $C php app/bootstrap.php voice_of_customer_system analysis <H>
docker exec $C php app/bootstrap.php voice_of_customer_system analysis <G>
```
Setelah ini Reviews, Dashboard, Locations, dst **terisi data**.

> Catatan: VoC UI **100% Volt** — nggak perlu `npm`/vite/Node sama sekali.

---

## Ringkasan super singkat
1. Install DBeaver → connect (`127.0.0.1:3306`, user & password dari `development.php`, db `onecloud`).
2. Buka `voc_setup_all.sql`, ganti `@site` kalau perlu, **Alt+X** (jalankan semua).
3. Catat Connection Id dari output.
4. Ingest lewat terminal (Bagian 5).
5. Hard-reload Media Monitoring → menu Voice of Customer muncul + berisi data.
