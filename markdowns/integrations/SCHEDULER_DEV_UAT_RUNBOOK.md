# Scheduler Crawl — Runbook Deploy & UAT Dev

Tahap F dari [tasklist](SCHEDULER_IMPLEMENTATION_TASKLIST.md).
Branch: `feature/DNGO19-3390_VOC-Crawl-Scheduler`.

Langkah 1–4 tindakan Sayyid (butuh akses deploy dev). Langkah 5 adalah UAT-nya.

---

## 0. Yang sudah dibuktikan sebelum menyentuh dev

Supaya UAT tidak gagal karena hal yang sebenarnya sudah bisa diketahui dari lokal:

| Risiko | Cara dibuktikan | Hasil |
|---|---|---|
| **Dev MySQL 5.7 vs lokal 8.0** (task #90) | DDL diambil langsung dari berkas migrasi lalu dijalankan di container **MySQL 5.7.44 STRICT** | tabel terbentuk, unique index benar, insert seperti aplikasi lolos, default terisi |
| Slot ganda | insert dua baris `(ScheduleId, ScheduledFor)` sama di 5.7 | ditolak `1062 (23000)` — kode yang persis ditangkap `claimSlot()` |
| Scheduler dobel | 8 instance `./run voc schedule` bersamaan atas satu slot | tepat **1** baris run |
| Baris cron menyala/mati | perintahnya dijalankan di lingkungan cron tiruan (`env -i`) | tanpa flag: diam; dengan flag: `./run voc schedule` jalan |
| Sintaks MySQL 8-only | pemindaian kedua migrasi | bersih |

### Soal container.env — koreksi atas dugaan awal

Sempat disimpulkan bahwa `BASH_ENV=/var/www/html/container.env` di `crontab.txt`
salah, karena ketiga entrypoint menulis berkasnya ke `/container.env`. Dugaan
itu **keliru untuk container yang benar-benar menjalankan cron**.

Service `scheduler` di `onecloud/docker-compose.yml` menulis berkasnya sendiri,
tepat ke jalur yang ditunjuk `BASH_ENV`:

```yaml
command: -c 'declare -px > /var/www/html/container.env
             && crontab -u www-data crontab.txt
             && /usr/sbin/rsyslogd
             && supervisord -n -c /var/www/html/supervisord-scheduler.conf'
```

Pengujian sebelumnya dilakukan di container **webapp** — di sana memang
`swoole-entrypoint.sh` yang menulis ke `/container.env`, dan jalur `BASH_ENV`
kosong. Tetapi webapp tidak menjalankan cron, jadi itu tidak pernah menjadi
masalah.

Baris cron VoC tetap ditulis defensif:

```
* * * * * [ -f /container.env ] && . /container.env; [ "${VOC_WORKERS:-0}" != "0" ] && ./runx voc schedule
```

Di container scheduler, `/container.env` tidak ada sehingga sourcing dilewati
dan `$VOC_WORKERS` datang dari `BASH_ENV` — benar. Di container mana pun yang
menulis ke `/container.env`, ia tetap benar. Sudah diuji berjalan di kedua
keadaan.

Catatan lain: cron dipasang untuk user **www-data**, bukan root.

---

## 1. Merge dan deploy

```bash
# dari WSL, di /var/www/html/onecloud
git checkout feature/DNGO19-3390_VOC-Crawl-Scheduler
git commit -F /mnt/c/Users/sayyi/.claude/jobs/a1b8075c/tmp/commit-scheduler-ui.txt
git push
```

Deploy branch ke dev seperti biasa.

**Tidak ada image scheduler terpisah.** Service `scheduler` memakai
`<<: *onecloud`, yaitu image yang sama dengan webapp
(`ciptadra/onecloud:${ONECLOUD_VERSION}`). Baris `scheduler Skipped` pada log
`publish.sh` karena itu normal — memang tidak ada yang perlu di-push sendiri.

Yang tetap wajib: **container scheduler harus dijalankan ulang dengan image
baru**. `crontab.txt` di-bake ke dalam image dan dipasang saat container start
(`crontab -u www-data crontab.txt`), jadi container lama tidak akan pernah
melihat baris VoC sampai ia diganti.

## 2. Jalankan migrasi di dev

Dua migrasi, berurutan:

| Versi | Isi |
|---|---|
| `1785980000000000_1_123_0` | tabel `VocSchedule` + `VocScheduleRun` |
| `1785990000000000_1_123_0` | menu "Jadwal Crawl" |

```bash
cd /onecloud/app && php migrate.php
```

Keluaran yang diharapkan:

```
  + VocSchedule dan VocScheduleRun dibuat
  + menu Jadwal Crawl dibuat
  + audience disalin dari menu acuan
```

Kalau menu acuan tidak ketemu, migrasi **melempar** dan tidak tercatat sukses —
itu disengaja, supaya bisa dijalankan ulang setelah dibereskan.

## 3. Nyalakan scheduler di container scheduler dev

Namanya `VOC_WORKERS`, mengikuti flag `*_WORKERS` lain. Nilainya sudah dipasang
di repo: `0` di `.env` (default mati) dan `1` di `.env.development`.

Variabelnya juga sudah didaftarkan di **dua** compose — `onecloud/docker-compose.yml`
dan `onecloud/docker-compose.base.yml`. Blok `environment:` di sana adalah
daftar-putih: variabel yang tidak disebut tidak pernah sampai ke dalam
container, berapa pun kali ia disetel di `.env`.

Variabel ini masuk ke `/container.env` lewat entrypoint, lalu dibaca baris cron.
**Jangan** dipasang di webapp — cukup di container yang memang menjalankan cron.

`/var/www/html/container.env` ditulis sekali saat container start, jadi mengubah
`.env` saja tidak cukup — **container scheduler harus dijalankan ulang**.

Verifikasi setelah deploy:

```bash
# di container scheduler dev
crontab -l | grep 'voc schedule'
grep VOC_WORKERS /container.env
```

`SCHEDULER_REPLICAS` boleh lebih dari 1. Sudah diuji: delapan proses scheduler
yang berebut satu slot tetap menghasilkan satu run.

## 4. Pastikan cabang dev punya master lokasi

Jadwal menyimpan `onebox_location_id`, bukan Id koneksi. Cabang yang belum punya
master lokasi tidak akan muncul di pemilih cabang, dan layar menyebutkan
jumlahnya. Kalau ada yang hilang, buka layar Lokasi dan simpan ulang cabangnya.

---

## 5. UAT

Kelima butir ini yang disepakati sebagai garis lulus. **Bukti dikumpulkan, bukan
diyakini.**

### UAT-1 — Alur utuh: form → crawl terjadwal → review terlihat

1. Buka **Voice of Customer → Setting → Jadwal Crawl**.
2. Klik **Jadwal baru**. Isi nama, pilih 1 cabang yang datanya sudah pernah
   berhasil ditarik manual, target kecil (5–10), rentang 30 hari.
3. Pilih **Tiap jam**, atau **Lanjutan (cron)** dengan jam yang akan tiba
   beberapa menit lagi. Batas minimum 1 jam berlaku — jadwal lebih rapat ditolak.
4. Periksa kotak pratinjau: waktu pertama harus masuk akal menurut jam dinding.
5. Simpan, lalu **tunggu tanpa menyentuh apa pun**.

**Lulus bila:** pada waktunya, riwayat jadwal memunculkan baris berstatus
Selesai, `batch_id`-nya ada di Riwayat Fetch, dan review baru tampil di layar
Ulasan dengan waktu masuk sesudah jadwal berjalan.

Kumpulkan: tangkapan layar formulir, baris riwayat, dan review barunya.

### UAT-2 — Batch benar-benar terbentuk di Crawler

Bandingkan `batch_id` di riwayat jadwal dengan baris di Riwayat Fetch. Harus
merujuk batch yang sama.

### UAT-3 — Riwayat jujur, termasuk yang dilewati

Buat jadwal tiap jam pada cabang yang penarikannya lambat, biarkan dua slot
berturut-turut. Slot kedua harus tercatat **Dilewati** dengan alasan yang
menyebut run mana yang menahannya — bukan hilang dari daftar.

Kolom **Masuk** harus berisi yang benar-benar tersimpan. Kalau sebuah run
memindai ratusan kartu tetapi menyimpan nol, kolom itu harus nol dan statusnya
**Gagal**, bukan Selesai — meski Crawler melaporkannya sukses.

### UAT-4 — Tahan banting

- **Dobel:** naikkan `SCHEDULER_REPLICAS` ke 2 (atau jalankan
  `./run voc schedule` dua kali bersamaan). Satu slot harus tetap menghasilkan
  satu baris run.
- **Restart:** matikan container scheduler melewati satu slot, lalu nyalakan
  lagi. Harus muncul **satu** run susulan, bukan menumpuk sebanyak slot yang
  terlewat.

```sql
-- tidak boleh ada baris ganda
SELECT ScheduleId, ScheduledFor, COUNT(*) c
  FROM VocScheduleRun GROUP BY ScheduleId, ScheduledFor HAVING c > 1;
```

### UAT-5 — Run Now dan aktif/nonaktif

- Catat **Berikutnya**, tekan tombol play, catat lagi. Harus **identik**.
- Matikan sakelar Aktif: kolom Berikutnya jadi "nonaktif", tidak ada run baru,
  riwayat lama tetap ada.
- Nyalakan lagi: `NextRunAt` dihitung ulang dan hitungan kegagalan kembali nol.

---

## 6. Kalau harus mundur

Matikan lebih dulu — paling cepat dan tanpa deploy:

```
VOC_WORKERS=0       (atau hapus variabelnya)
```

Jadwal berhenti berjalan; data dan riwayat utuh.

Rollback penuh:

```bash
cd /onecloud/app && TARGET_VERSION=1785970000000000_1_123_0 php migrate.php
```

Menunya dilepas dan kedua tabel di-drop. `down()` sudah diuji round-trip di
lokal.

---

## 7. Yang TIDAK akan terbukti lewat UAT ini

**Crawl bawaan Crawler masih bisa membakar sepuluh menit tanpa hasil.** Pada 11
Agustus 2026 sebuah run bertarget 5 memindai 250 kartu, menyimpan nol, dan mati
kena batas waktu 600 detik — sementara Crawler melaporkannya `success`.

Scheduler menilai ulang hasil itu dari datanya sendiri dan mencatatnya **Gagal**,
lalu memundurkan jadwal dan akhirnya mematikannya setelah sepuluh kegagalan
beruntun. Tetapi itu **rem**, bukan obat: pemborosan sepuluh menit worker tetap
terjadi setiap kali.

Perbaikan sebenarnya ada di sisi Crawler dan sudah dituliskan di
`prompt-crawler-target-vs-scan.md`: batasi pemindaian (bukan hanya penerimaan),
hentikan run saat urutan "Terbaru" gagal dipasang padahal rentang tanggal
dipakai, dan berhenti melaporkan `success` untuk run yang mati kena batas waktu
tanpa hasil.
