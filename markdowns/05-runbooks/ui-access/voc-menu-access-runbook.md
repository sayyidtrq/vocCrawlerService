# Runbook: Akses Menu VoC di Dev (untuk Nana, Salman, Cello)

> Masalah: login akun seed yang sama di branch sama, tapi menu VoC/Mediamonitoring beda antar-dev.
> Sebab: menu OneBox itu **data DB** (bukan branch). Seed VoC menempel ke menu Mediamonitoring + menyalin role dari akun referensi. Kalau prasyarat data itu tidak ada di DB kamu, hasilnya beda.
> Arahan Agung: schema diurus **migration**; menu/role/permission diseragamkan lewat **seed**.

Ikuti urut. Jalankan dari dalam WSL, di repo OneBox (`/var/www/html/onecloud`).

---

## Step 0 — Samakan schema (migration)

```bash
cd /var/www/html/onecloud/onecloud
./migration.sh <env> up          # <env> = env kamu, mis. local
./migration.sh <env> status      # pastikan sudah di versi terbaru
```
Ref: `onecloud/app/migrations/readme.md`.

---

## Step 1 — CEK PRASYARAT (paling penting) ⚠️

Menu VoC menempel ke menu Mediamonitoring. Cek dulu menu itu ada:

```sql
SELECT Id, ParentId, NavigateUrl
FROM Menu
WHERE NavigateUrl = '#/news/list/semua_sumber' AND TypeId = 'SIDEMENU';
```

- **Dapat 1 baris** → lanjut Step 2. (DB kamu punya struktur MM — aman.)
- **KOSONG** → DB kamu **tidak punya menu Mediamonitoring**. Ini akar bedanya. Pilih salah satu:
  - **(disarankan)** restore dump DB yang sama dengan yang sudah jalan (punya Sayyid) → ulang dari Step 0, atau
  - set `@mm`/`@src` manual (lihat Troubleshooting T1 di bawah).

---

## Step 2 — Jalankan seed setup (menu + permission + master data)

Idempotent, aman di-run ulang:

```bash
mysql -u root -p <nama_db> < scriptdb/voc/voc_setup_all.sql
```

Yang dilakukan: insert Provider `Voc` (PVD97), MediaId `GBUSINESS`, Category, menu `voc` + 9 submenu, dan **menyalin permission dari menu "Daftar Berita"** ke menu VoC (audience sama dengan yang bisa buka Mediamonitoring).

---

## Step 3 — Jalankan seed user (kalau pakai akun seed bersama)

```bash
mysql -u root -p <nama_db> < scriptdb/voc/voc_dev_user.sql
```

Ini bikin/menautkan user `voc.dev@onebox.local` (pass `voc12345`) dan **menyalin role dari akun referensi** `admin-news@ciptadrasoft.com`.

⚠️ **Prasyarat:** akun referensi `admin-news@ciptadrasoft.com` harus ada di DB kamu **dan bisa buka Mediamonitoring**. Kalau tidak:
- ganti `@ref_email` di baris atas `voc_dev_user.sql` ke akun lain di DB kamu yang **sudah bisa buka Mediamonitoring**, lalu jalankan ulang.

---

## Step 4 — Verifikasi

```bash
mysql -u root -p <nama_db> < scriptdb/voc/voc_dev_diagnose.sql
```

Atau cek manual bahwa permission menu VoC benar-benar ke-insert:

```sql
SELECT m.Code, COUNT(p.RoleId) AS jml_role_boleh
FROM Menu m
LEFT JOIN Permission p
  ON p.ObjectName='Menu' AND p.ObjectId=m.Id AND p.ActionId='ALLOWED'
WHERE m.Code LIKE 'voc%'
GROUP BY m.Code;
```
Kalau `jml_role_boleh = 0` untuk semua baris → permission gagal ter-copy (biasanya karena Step 1 kosong / `@src` NULL). Balik ke Step 1.

---

## Step 5 — Clear cache menu + login ulang

Menu bisa di-cache (Redis) / tersimpan di session. **Logout lalu login ulang** supaya sidebar dibangun ulang. Kalau masih belum muncul, restart `./swoole-dev.sh`.

Login: akun kamu sendiri (kalau role-nya sudah disamakan) **atau** `voc.dev@onebox.local` / `voc12345`.

---

## Troubleshooting

### T1 — `@mm` / `@src` NULL (menu MM tidak ada)
Cari header menu manual:
```sql
SELECT Id, Code, TypeId, Description FROM Menu WHERE TypeId='HEADERMENU';
```
Lalu di `voc_setup_all.sql`, ganti dua baris `SET @mm := ...` / `SET @src := ...` dengan Id yang sesuai, jalankan ulang. **Tapi lebih baik restore dump yang sudah benar** — kalau MM tidak ada, kemungkinan banyak data lain juga beda.

### T2 — Menu muncul tapi kosong / error saat diklik
Berarti kode controller/view VoC belum ada di branch kamu. Pastikan sudah di branch `feature/DNGO19-3346...` dan sudah `git pull`.

### T3 — Menu tidak muncul walau permission ada
Cek role user kamu benar-benar punya salah satu RoleId yang ada di Permission menu VoC:
```sql
-- role user kamu di site ini
SELECT RoleId FROM UserRole WHERE UserId=(SELECT Id FROM User WHERE Email='<email_kamu>') AND SiteId=<site>;
```
Cocokkan dengan RoleId di query verifikasi Step 4.

---

## Ringkasan sebab-akibat (buat paham, bukan langkah)

| Kondisi DB kamu | Hasil |
|---|---|
| Ada menu MM + akun referensi + seed dijalankan | Menu VoC muncul ✅ (seperti Sayyid) |
| Menu MM ada, seed BELUM dijalankan | Menu VoC tidak ada — jalankan Step 2 |
| Menu MM TIDAK ada | Permission gagal ter-copy → menu VoC tak terlihat walau baris menu masuk — perbaiki Step 1 |
| Role user beda dari referensi | Menu lain juga beda — samakan lewat Step 3 |
