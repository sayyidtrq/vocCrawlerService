# `migrate.php` mencetak password database ke stdout

**Ditemukan:** 3 September 2026, saat menguji migrasi 1.123.0 di stack lokal
**Sifat:** kebocoran kredensial lewat log — bukan bug fungsional
**Cakupan:** setiap eksekusi migrasi, di environment mana pun
**Berkas:** `onecloud/app/migrate.php` → `Phalcon\Migrations`, pada jalur yang memanggil `pt-online-schema-change`

---

## Gejalanya

Menjalankan migrasi:

```bash
ONECLOUD_ENV=<env> php app/migrate.php
```

Pada migrasi yang menambah kolom lewat `pt-online-schema-change`, runner mencetak **seluruh perintah shell** ke stdout, lengkap dengan argumennya:

```
pt-online-schema-change --version && PTDEBUG=0 pt-online-schema-change \
  --user=<user> --password=<PASSWORD ASLI DALAM TEKS POLOS> \
  --host=<host> --port=3306 D=<db>,t=Article ...
```

Baris yang sama muncul dua kali: sekali saat perintah disusun, sekali lagi di pesan error kalau perintahnya gagal.

Nilai `--password=` adalah password database yang sedang dipakai, apa adanya. Tidak disamarkan, tidak dipotong.

---

## Kenapa ini penting

Ini bukan kejadian sekali. Ia terjadi **setiap kali** migrasi dijalankan, dan keluarannya mendarat di tempat yang umumnya disimpan lama:

| Tempat | Siapa yang bisa melihat |
| --- | --- |
| Log CI/CD | siapa pun yang punya akses pipeline |
| Log deployment | tim deploy, dan arsip lognya |
| Terminal operator | terekam di scrollback, kadang di-screenshot untuk laporan |
| Log container | tersimpan selama container hidup, ikut terkirim ke agregator log |

Password produksi yang pernah tercetak di log CI harus dianggap sudah bocor, karena log CI biasanya bisa dibaca lebih banyak orang daripada kredensial itu sendiri.

---

## Cara memastikannya sendiri

Jalankan migrasi apa pun yang menyentuh `pt-online-schema-change`, lalu cari kata `--password` di keluarannya:

```bash
ONECLOUD_ENV=<env> php app/migrate.php 2>&1 | grep -c -- '--password='
```

Hasil lebih dari nol berarti kredensialnya tercetak.

**Jangan** menempelkan keluaran mentahnya ke tiket, chat, atau PR — itu justru memperluas kebocorannya.

---

## Saran perbaikan

Urut dari yang paling mudah:

1. **Samarkan saat mencetak.** Ganti nilai `--password=...` dengan `--password=***` di string yang di-log, bukan di string yang dieksekusi. Perubahan kecil, menutup jalur kebocoran paling lebar.
2. **Jangan lewatkan password sebagai argumen shell.** `pt-online-schema-change` membaca berkas konfigurasi lewat `--defaults-file`, sehingga kredensialnya tidak pernah muncul di daftar argumen — dan juga tidak terlihat di `ps aux` oleh proses lain di mesin yang sama.
3. **Turunkan verbosity di produksi.** Perintah lengkap berguna saat debugging lokal, tidak saat deploy.

Nomor 2 sekaligus menutup celah kedua yang belum disebut: selama perintah berjalan, password terlihat di daftar proses sistem.

---

## Yang perlu diputuskan tim

- Apakah password yang selama ini dipakai migrasi perlu dirotasi? Jawabannya bergantung pada seberapa lama log CI/deploy disimpan dan siapa yang bisa membacanya.
- Apakah kredensial migrasi sebaiknya dipisah dari kredensial aplikasi, supaya rotasinya tidak menyentuh layanan yang sedang berjalan.

---

## Catatan

Temuan ini muncul sebagai efek samping saat menguji konsolidasi migrasi 1.123.0. Ia **tidak berhubungan** dengan perubahan VoC mana pun — perilaku ini sudah ada di runner migrasi sejak sebelumnya, dan berlaku untuk seluruh modul.

Tidak ada nilai password yang dicantumkan di dokumen ini, dan tidak boleh ditambahkan.
