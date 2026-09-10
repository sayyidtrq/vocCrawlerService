# Runbook — Migrasi 1.123.0 di Dev

Kapan folder migrasi `1786200000000000_1_123_0` boleh dijalankan di dev, kapan harus ditandai saja, dan kenapa.

**Berkas SQL:** `../07-data-and-seeding/VOC_TANDAI_MIGRASI_1123_DI_DEV.sql`

---

## Aturan satu kalimat

> Sebelum menjalankan migrasi di dev, periksa apakah folder `1786200000000000_1_123_0` ada di pohon yang dideploy. **Kalau ada, tandai dulu. Kalau tidak ada, aman jalan.**

```bash
ls onecloud/app/migrations/ | grep 1786200000000000
```

Ada isinya → jalankan SQL penandaan lebih dulu.
Kosong → tidak perlu apa-apa.

---

## Kenapa

Folder itu hasil menggabungkan 23 folder migrasi 1.123.0 jadi satu, mengikuti ketentuan "satu versi satu folder". Isinya identik dengan yang sudah pernah jalan di dev lewat 23 folder lama — tidak ada perubahan baru.

Masalahnya ada di sifat migrasi `Menu.php`. Ia **bukan penambal, melainkan pembangun ulang**. Langkah pertamanya:

```sql
DELETE FROM Permission WHERE ObjectName='Menu' AND ObjectId IN (...voc...);
DELETE FROM Menu WHERE Code LIKE 'voc%';
```

lalu seluruh menu dibuat ulang dari nol.

| Environment | Akibat | Tindakan |
| --- | --- | --- |
| **Produksi** | benar — belum ada menu VoC sama sekali, jadi membangun dari nol memang yang diinginkan | jalankan biasa, **jangan** ditandai |
| **Dev** | merusak — menu VoC dari branch lain ikut terhapus dan tidak lahir kembali | **tandai**, jangan dijalankan |

`DELETE ... WHERE Code LIKE 'voc%'` menyapu **semua** menu VoC, termasuk milik DNGO19-3513, 3523, dan 3529 yang belum masuk 1.123.0. Yang dibangun ulang hanya yang dikenal 1.123.0, jadi sisanya hilang permanen.

### Buktinya, bukan dugaan

Diuji di DB lokal 3 September 2026 dengan menjalankan keenam berkas migrasi langsung:

| | Sebelum | Sesudah |
| --- | --- | --- |
| Kode `voc_` unik | 23 | **22** |
| Permission untuk menu `voc_` | 133 | **88** |
| `voc_ws_branch` (Workspace Cabang) | ada | **hilang** |

`voc_ws_branch` dibuat oleh migrasi dari branch lain. Wipe menghapusnya, dan tidak ada langkah di folder 1.123.0 yang membuatnya kembali.

DB lokal sudah dipulihkan penuh dari cadangan `bak_voc_20260903_043541_*` setelah pengujian.

---

## Keadaan tiap branch

Diperiksa 3 September 2026:

| Branch | Punya folder `1786200000000000`? | Perlu ditandai sebelum migrasi? |
| --- | --- | --- |
| `release/1.123.0` | **ya** | **ya** |
| `feature/DNGO19-3529_Fetch-Review-Improvement` | tidak (34 folder lama) | tidak |
| Branch lain yang belum menarik release | tidak | tidak |

**Begitu sebuah branch menarik `release/1.123.0` ke dalamnya, folder itu ikut masuk** — dan sejak saat itu penandaan menjadi wajib sebelum migrasi dijalankan di dev.

---

## Langkah

1. Periksa pohon yang akan dideploy:
   ```bash
   ls onecloud/app/migrations/ | grep 1786200000000000
   ```
2. Kalau ada, buka `VOC_TANDAI_MIGRASI_1123_DI_DEV.sql` dan jalankan **BAGIAN 1** lebih dulu. Bandingkan hasilnya dengan nilai acuan di berkas itu.
3. Kalau pra-periksa wajar, jalankan **BAGIAN 2** (satu `INSERT`, idempotent).
4. Jalankan **BAGIAN 3** untuk memastikan menu VoC tidak tersentuh.
5. Baru deploy dan jalankan migrasi seperti biasa.

Urutannya penting. Kalau migrasi jalan lebih dulu, menunya sudah terlanjur tersapu dan penandaan tidak menolong apa pun.

---

## Kalau terlanjur terjadi

Gejalanya: menu VoC berkurang, sebagian layar hilang dari sidebar, atau user kehilangan akses ke menu tertentu.

1. Bandingkan `SELECT DISTINCT Code FROM Menu WHERE Code LIKE 'voc%'` dengan daftar yang diharapkan.
2. Menu yang hilang perlu dibuat ulang lewat migrasi branch asalnya — hapus baris versinya dari `phalcon_migrations`, lalu jalankan ulang **hanya** versi itu.
3. Periksa juga `Permission`: menu yang lahir kembali dengan Id baru kehilangan pemberian izin yang dibuat manual.

---

## Sesudah 1.123.0 tayang ke produksi

Penandaan ini hanya relevan selama dev masih memegang menu dari branch yang belum masuk rilis. Begitu 3513, 3523, dan 3529 semuanya sudah tayang, wipe-and-rebuild tidak lagi menghapus apa pun yang tidak dibangun kembali, dan aturan ini boleh ditinjau ulang.

## Rujukan

- Mekanisme `phalcon_migrations` mencatat nama folder: `00-start-here/README.md`, bagian **Aturan Migrasi**
- Hasil uji lengkap: `04-implementation-plans/onebox/PLAN_RELEASE_1_123_0_KE_PRODUKSI.md`, LAMPIRAN
