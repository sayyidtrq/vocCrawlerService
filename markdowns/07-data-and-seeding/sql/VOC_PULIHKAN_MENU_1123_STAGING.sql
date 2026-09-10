-- =====================================================================
-- VoC staging release/1.123.0 — PULIHKAN MENU YANG TERTIMPA SEED
--
-- Terkonfirmasi 10 September 2026 di onecloud_rel (server xtradb):
--
--     SELECT TypeId, COUNT(*) FROM Menu WHERE Code LIKE 'voc%' GROUP BY TypeId;
--     SIDEMENU      1
--     SUBSIDEMENU   9
--
-- Sepuluh menu, tanpa HEADERMENU. Itu tanda tangan voc_setup_all.sql.
-- Migrasi 1.123 membangun 27 kode dengan 1 HEADERMENU (voc_header),
-- 4 SIDEMENU, dan 17 SUBSIDEMENU. Ketujuh belas sisanya hilang.
--
-- Tidak ada kode voc% dari sumber ketiga — jadi wipe milik migrasi tidak akan
-- memakan korban yang tidak ia bangun kembali. Di dev hal ini BERBAHAYA
-- (ada menu branch 3513/3523/3529); di staging tidak, karena staging hanya
-- memuat 1.123.
--
-- SKRIP INI BUKAN SATU-SATUNYA LANGKAH. Ia hanya melepas catatan versinya;
-- yang membangun ulang menu adalah runner migrasi di langkah 3.
-- =====================================================================

-- ---------------------------------------------------------------------
-- LANGKAH 1 — CADANGKAN DULU. Tanpa kecuali.
-- ---------------------------------------------------------------------
-- Di shell, bukan di sini:
--
--   mysqldump -u<user> -p onecloud_rel \
--     Menu Permission phalcon_migrations \
--     > bak_staging_menu_$(date +%Y%m%d_%H%M%S).sql
--
-- Langkah 3 menjalankan "DELETE FROM Menu WHERE Code LIKE 'voc%'" lalu
-- membangun ulang. Kalau pembangunannya gagal di tengah, cadangan ini
-- satu-satunya jalan pulang.

-- ---------------------------------------------------------------------
-- LANGKAH 2 — POTRET SEBELUM, lalu lepas catatan versinya
-- ---------------------------------------------------------------------

-- 2a. Catat angka-angka ini. Dipakai membandingkan di langkah 4.
SELECT 'menu voc unik' AS ukuran, COUNT(DISTINCT Code) AS nilai
  FROM Menu WHERE Code LIKE 'voc%'
UNION ALL
SELECT 'permission voc', COUNT(*)
  FROM Permission p JOIN Menu m ON m.Id = p.ObjectId
 WHERE p.ObjectName = 'Menu' AND m.Code LIKE 'voc%'
UNION ALL
SELECT 'total baris phalcon_migrations', COUNT(*) FROM phalcon_migrations;

-- 2b. Pastikan ada menu acuan yang bisa dipakai mewarisi hak akses.
--
-- INI PEMERIKSAAN PENTING, dan alasannya ada di kode migrasi:
--
--     if (!$fallback) {
--         echo "  ! tidak ada menu sekelompok yang punya audience — hak akses dilewati\n";
--         return;
--     }
--
-- Migrasi TIDAK gagal kalau acuannya tidak ada. Ia melewati hak akses dan
-- lanjut. Hasilnya menu yang berdiri di tabel tetapi tidak muncul bagi siapa
-- pun — kegagalan yang terlihat persis seperti "menunya belum dibuat".
--
-- Query di bawah mencari acuan yang sama dengan yang dipakai seed. HARUS
-- mengembalikan minimal 1 baris sebelum langkah 3 dijalankan.
SELECT m.Id, m.Code, m.Description, m.NavigateUrl,
       COUNT(p.Id) AS jumlah_permission
  FROM Menu m
  JOIN Permission p
    ON p.ObjectName = 'Menu' AND p.ObjectId = m.Id AND p.ActionId = 'ALLOWED'
 WHERE m.TypeId = 'SIDEMENU'
   AND (m.NavigateUrl = '#/news/list/semua_sumber'
        OR m.Code IN ('SemuaSumber','listberita','sentiment')
        OR m.Description IN ('Daftar Berita','Berita','Informasi'))
 GROUP BY m.Id, m.Code, m.Description, m.NavigateUrl
 ORDER BY jumlah_permission DESC;

-- ⚠️ Kalau query 2b mengembalikan NOL baris: BERHENTI. Jangan lanjut ke
--    langkah 3. Menu VoC akan lahir tanpa hak akses dan keadaannya justru
--    lebih membingungkan daripada sekarang.

-- 2c. Lepas catatan versinya.
START TRANSACTION;

SELECT version, start_time, end_time
  FROM phalcon_migrations
 WHERE version = '1786200000000000_1_123_0';   -- harus tepat 1 baris

DELETE FROM phalcon_migrations
 WHERE version = '1786200000000000_1_123_0';

-- Periksa: harus "1 row affected". Kalau 0 atau lebih dari 1, ROLLBACK.
COMMIT;

-- ---------------------------------------------------------------------
-- LANGKAH 3 — JALANKAN MIGRASINYA (di shell, bukan di sini)
-- ---------------------------------------------------------------------
--   docker exec <container-staging> php app/migrate.php
--   # atau: ./migration.sh <env staging> run
--
-- AWASI OUTPUTNYA. Dua hal:
--
--   1. Baris "! tidak ada menu sekelompok yang punya audience — hak akses
--      dilewati". Kalau muncul, ada menu yang lahir tanpa izin. Catat
--      menu mana, lalu perbaiki hak aksesnya sebelum menyerahkan ke QA.
--
--   2. Runner mencetak password DB dalam teks polos (perintah
--      pt-online-schema-change lengkap dengan --password=<nilai asli>).
--      JANGAN tempel output mentahnya ke tiket atau chat.
--
-- Catatan soal TARGET_VERSION: ia berarti "migrasi SAMPAI versi itu", bukan
-- "hanya versi itu". Angka "total baris phalcon_migrations" dari 2a yang
-- membuktikan tidak ada versi lain yang ikut terpanggil — lihat V4 di bawah.

-- ---------------------------------------------------------------------
-- LANGKAH 4 — VERIFIKASI
-- ---------------------------------------------------------------------
SELECT 'V1 menu voc unik (harus 27)' AS pemeriksaan, COUNT(DISTINCT Code) AS nilai
  FROM Menu WHERE Code LIKE 'voc%'
UNION ALL
SELECT 'V2 HEADERMENU voc (harus 1)', COUNT(*)
  FROM Menu WHERE Code LIKE 'voc%' AND TypeId = 'HEADERMENU'
UNION ALL
SELECT 'V3 permission voc (harus > 0, dan >= angka 2a)', COUNT(*)
  FROM Permission p JOIN Menu m ON m.Id = p.ObjectId
 WHERE p.ObjectName = 'Menu' AND m.Code LIKE 'voc%'
UNION ALL
SELECT 'V4 total phalcon_migrations (harus SAMA dengan 2a)', COUNT(*)
  FROM phalcon_migrations;

-- V5 — sebaran per TypeId. Harus: HEADERMENU 1, SIDEMENU 4, SUBSIDEMENU 17.
SELECT TypeId, COUNT(*) FROM Menu WHERE Code LIKE 'voc%' GROUP BY TypeId;

-- V6 — catatan versinya kembali, dengan end_time terisi.
SELECT version, start_time, end_time FROM phalcon_migrations
 WHERE version = '1786200000000000_1_123_0';

-- V7 — adakah menu voc yang lahir TANPA hak akses sama sekali?
--      Ini yang menangkap peringatan "hak akses dilewati" kalau terlewat
--      terbaca di output runner.
SELECT m.Id, m.Code, m.TypeId, m.Description
  FROM Menu m
 WHERE m.Code LIKE 'voc%'
   AND NOT EXISTS (
     SELECT 1 FROM Permission p
      WHERE p.ObjectName = 'Menu' AND p.ObjectId = m.Id AND p.ActionId = 'ALLOWED')
 ORDER BY m.TypeId, m.Code;
-- Kosong = semua menu punya audience. Ada isi = menu-menu itu tidak akan
-- terlihat oleh siapa pun, dan perlu diperbaiki hak aksesnya.

-- ---------------------------------------------------------------------
-- KALAU V1 TETAP 10
-- ---------------------------------------------------------------------
-- Migrasinya tidak benar-benar jalan ulang. Periksa berurutan:
--   1. Apakah baris 2c benar-benar ter-COMMIT (query V6 sebelum langkah 3
--      seharusnya kosong)
--   2. Nilai TARGET_VERSION di env staging
--   3. Apakah kode di staging memang release/1.123.0 yang memuat folder
--      1786200000000000_1_123_0
--
-- Jangan menulis ulang 27 menu itu dengan tangan. Menyalinnya manual
-- menciptakan versi ketiga dari kebenaran yang sama, dan itu justru akar
-- masalah yang sedang diperbaiki.
-- =====================================================================
