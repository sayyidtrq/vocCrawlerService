-- =====================================================================
-- Menandai migrasi 1.123.0 sebagai SUDAH DITERAPKAN di dev
--
-- Jalankan di  : database dev OneBox (onecloud_rel)
-- Jangan jalan : di lokal maupun produksi
-- Dibuat       : 3 September 2026
-- Status uji   : BELUM dijalankan lawan database mana pun — stack lokal
--                sedang mati saat berkas ini ditulis. Karena itu BAGIAN 1
--                bukan formalitas: baca hasilnya sebelum lanjut ke BAGIAN 2.
--
-- ---------------------------------------------------------------------
-- KENAPA DITANDAI, BUKAN DIJALANKAN
--
-- Folder 1786200000000000_1_123_0 adalah hasil menggabungkan 23 folder
-- migrasi 1.123.0 menjadi satu, mengikuti ketentuan "satu versi satu
-- folder". Isinya identik dengan yang sudah pernah dijalankan di dev
-- lewat 23 folder lama — tidak ada satu pun perubahan baru.
--
-- Masalahnya, migrasi Menu di dalamnya BUKAN penambal, melainkan
-- pembangun ulang. Langkah pertamanya menjalankan:
--
--     DELETE FROM Permission WHERE ObjectName='Menu' AND ObjectId IN (...voc...);
--     DELETE FROM Menu WHERE Code LIKE 'voc%';
--
-- lalu membuat ulang seluruh menu dari nol. Di environment yang masih
-- kosong (produksi) itu benar dan aman. Di dev tidak: dev sudah punya
-- menu VoC dari branch LAIN yang belum masuk 1.123.0 — DNGO19-3513,
-- 3523, dan 3529. Menu itu akan ikut terhapus, lalu TIDAK dibangun
-- kembali, karena langkah-langkah di folder ini hanya mengenal menu
-- milik 1.123.0.
--
-- Ini bukan dugaan. Diuji di DB lokal 3 September 2026: menu voc_ turun
-- dari 23 menjadi 22 kode unik, Permission dari 133 menjadi 88, dan
-- voc_ws_branch (Workspace Cabang) hilang tanpa lahir kembali.
--
-- Karena keadaan akhir dev sudah setara hasil folder ini, cukup catat
-- versinya sebagai sudah berjalan. Phalcon akan melewatinya selamanya.
-- =====================================================================


-- ---------------------------------------------------------------------
-- BAGIAN 1 — PERIKSA DULU, JANGAN LANGSUNG BAGIAN 2
--
-- Penandaan ini hanya benar kalau dev MEMANG sudah punya menu VoC.
-- Kalau ternyata belum, menandai versi justru membuat menu tidak pernah
-- terbentuk — dan itu lebih buruk daripada tidak melakukan apa-apa.
-- ---------------------------------------------------------------------

-- 1a. Apakah dev sudah punya menu VoC? (harapan: jauh di atas nol)
SELECT COUNT(DISTINCT Code) AS kode_voc_unik,
       SUM(ExpireDate > NOW())  AS baris_aktif
  FROM Menu
 WHERE Code LIKE 'voc%';

-- 1b. Berapa versi _1_123_0 yang sudah tercatat? (harapan: 20-an)
SELECT COUNT(*) AS versi_1123_tercatat
  FROM phalcon_migrations
 WHERE version LIKE '%\_1\_123\_0';

-- 1c. Apakah versi gabungannya sudah tercatat? (harapan: 0 = belum)
SELECT COUNT(*) AS sudah_ditandai
  FROM phalcon_migrations
 WHERE version = '1786200000000000_1_123_0';

-- 1d. Tabel dari migrasi skema sudah ada? (harapan: dua-duanya mengembalikan 1 baris)
--
--     Sengaja SHOW TABLES, bukan information_schema. Di dev, pembacaan
--     information_schema pernah mengembalikan hasil kosong padahal tabelnya
--     ada — dan itu sempat menyesatkan diagnosa. SHOW TABLES membaca langsung
--     dan tidak pernah bohong soal ini.
SHOW TABLES LIKE 'VocSchedule';
SHOW TABLES LIKE 'VocScheduleRun';

-- BERHENTI DI SINI kalau 1a mendekati nol, atau salah satu SHOW TABLES di
-- 1d tidak mengembalikan baris. Itu berarti dev belum punya keadaan yang
-- folder ini hasilkan, dan migrasinya memang perlu DIJALANKAN, bukan
-- ditandai. Tanyakan dulu sebelum melanjutkan.
--
-- Nilai acuan dari DB lokal (3 September 2026), sebagai pembanding kasar:
--   1a  23 kode unik / 21 aktif
--   1b  29 versi tercatat
--   1c  0
--   1d  dua-duanya mengembalikan satu baris


-- ---------------------------------------------------------------------
-- BAGIAN 2 — PENANDAAN
--
-- Aman dijalankan dua kali: barisnya hanya dibuat kalau belum ada.
-- ---------------------------------------------------------------------

INSERT INTO phalcon_migrations (version, start_time, end_time)
SELECT '1786200000000000_1_123_0', NOW(), NOW()
  FROM DUAL
 WHERE NOT EXISTS (
       SELECT 1 FROM phalcon_migrations
        WHERE version = '1786200000000000_1_123_0'
 );


-- ---------------------------------------------------------------------
-- BAGIAN 3 — VERIFIKASI
-- ---------------------------------------------------------------------

-- 3a. Barisnya ada tepat satu?
SELECT version, start_time, end_time
  FROM phalcon_migrations
 WHERE version = '1786200000000000_1_123_0';

-- 3b. Menu VoC tidak tersentuh sama sekali? (harus sama dengan hasil 1a)
SELECT COUNT(DISTINCT Code) AS kode_voc_unik,
       SUM(ExpireDate > NOW())  AS baris_aktif
  FROM Menu
 WHERE Code LIKE 'voc%';


-- ---------------------------------------------------------------------
-- BAGIAN 4 — MEMBATALKAN
--
-- Hanya kalau memang ingin folder itu BENAR-BENAR dijalankan di dev,
-- dan sudah siap kehilangan menu dari branch 3513/3523/3529 lalu
-- memasangnya kembali secara manual.
-- ---------------------------------------------------------------------

-- DELETE FROM phalcon_migrations WHERE version = '1786200000000000_1_123_0';


-- =====================================================================
-- CATATAN UNTUK PRODUKSI
--
-- Di produksi TIDAK perlu penandaan apa pun. Di sana belum ada menu VoC
-- sama sekali, jadi folder ini dijalankan sekali seperti biasa dan
-- hasilnya benar. Justru penandaan yang akan merusak, karena membuat
-- seluruh menu VoC tidak pernah terbentuk.
-- =====================================================================
