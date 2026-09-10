-- =====================================================================
-- Workspace Cabang tidak muncul di dev — diagnosa lalu perbaikan
-- Jalankan di phpMyAdmin dev, database: onecloud_rel
-- =====================================================================
--
-- ADA DUA GERBANG TERPISAH, dan keduanya harus lolos:
--
--   1. Baris Menu  -> menentukan menunya BISA DITEMUKAN di sidebar
--      (MenuController::sideMenuAction, baca tabel Permission)
--   2. Baris Permission untuk role yang dipegang akunmu
--      -> menentukan halamannya BOLEH DIBUKA
--      (VocController::canUseVocMenu, gerbang RBAC)
--
-- Gejala "menu tidak ada DAN halaman tidak bisa dibuka" muncul bersamaan
-- hanya kalau tidak ada satu pun baris Permission untuk role akunmu.
-- Kalau barisnya ada tapi kedaluwarsa, gejalanya justru terbalik: menu
-- TETAP TERLIHAT (sidebar tidak menyaring ExpireDate) tapi halamannya 403.
--
-- Semua perbandingan memakai literal, tanpa derived table — pelajaran
-- dari galat #1267 di dev yang kolomnya latin1_swedish_ci.
-- =====================================================================


-- =====================================================================
-- BAGIAN A — DIAGNOSA. Jalankan lima query ini dulu, jangan mengubah apa pun.
-- =====================================================================

-- A1. Apakah migrasi Menu-nya benar-benar tercatat?
--     Yang dicari: baris 1786130000000000_1_123_0.
--     Kalau TIDAK ADA, migrasinya belum pernah jalan di dev — lanjut ke BAGIAN B.
SELECT version, start_time, end_time
  FROM phalcon_migrations
 WHERE version LIKE '17861%'
 ORDER BY version;

-- A2. Apakah baris menunya ada, dan sehat?
--     voc_workspace dipakai sebagai pembanding: itu menu yang MEMANG tampil.
--     Kalau voc_ws_branch tidak muncul di sini, sidebar mustahil menampilkannya.
SELECT Id, Code, TypeId, ParentId, Visible, Enabled, Priority, ExpireDate
  FROM Menu
 WHERE Code IN ('voc_workspace', 'voc_ws_branch');

-- A3. Siapa yang memegang izinnya?
--     Bandingkan daftar role voc_ws_branch dengan voc_workspace — harusnya sama
--     persis, karena migrasi menyalin audience dari sana.
SELECT m.Code, p.RoleId, r.Code AS RoleCode, p.ActionId, p.SiteId, p.ExpireDate
  FROM Permission p
  JOIN Menu m ON m.Id = p.ObjectId
  LEFT JOIN Role r ON r.Id = p.RoleId
 WHERE p.ObjectName = 'Menu'
   AND m.Code IN ('voc_workspace', 'voc_ws_branch')
 ORDER BY m.Code, p.SiteId, p.RoleId;

-- A4. Role apa yang sebenarnya dipegang akun yang kamu pakai?
--     Ini pertanyaan "perlu login akun lain atau tidak" yang sesungguhnya.
--     Yang menentukan bukan nama akunnya, tapi Role.Code yang dipegangnya
--     DI SITE 169.
SELECT u.Id, u.Email, ur.SiteId, ur.RoleId, r.Code AS RoleCode
  FROM `User` u
  JOIN UserRole ur ON ur.UserId = u.Id
  LEFT JOIN Role r ON r.Id = ur.RoleId
 WHERE u.Email LIKE '%admin-news%'
    OR u.Email LIKE 'voc.%'
 ORDER BY u.Email, ur.SiteId, ur.RoleId;

-- A5. VONIS — ini persis daftar yang dikembalikan sidebar untuk akun itu.
--     Ganti alamat emailnya kalau kamu memakai akun lain.
--     Kalau 'voc_ws_branch' TIDAK ada di hasil, sidebar memang tidak akan
--     menampilkannya, dan halamannya juga akan ditolak 403.
SELECT m.Code, m.Description, m.Priority
  FROM Permission p
  JOIN Menu m ON m.Id = p.ObjectId
 WHERE m.TypeId = 'SUBSIDEMENU'
   AND m.Enabled = 1
   AND p.SiteId  = '169'
   AND m.Code LIKE 'voc%'
   AND p.RoleId IN (SELECT ur.RoleId
                      FROM UserRole ur
                     WHERE ur.SiteId = 169
                       AND ur.UserId = (SELECT Id FROM `User`
                                         WHERE Email = 'admin-news@ciptadrasoft.com'
                                         LIMIT 1))
 GROUP BY m.Id, m.Code, m.Description, m.Priority
 ORDER BY m.Priority ASC;


-- =====================================================================
-- BAGIAN B — PERBAIKAN 1: baris menunya belum ada
-- Jalankan HANYA kalau A2 tidak memunculkan voc_ws_branch.
-- Isinya sama persis dengan migrasi 1786130000000000, ditulis ulang sebagai SQL.
-- Aman diulang.
-- =====================================================================

SET @src    := (SELECT Id       FROM Menu WHERE Code = 'voc_workspace'
                 AND Enabled = 1 AND ExpireDate > NOW() ORDER BY Id DESC LIMIT 1);
SET @parent := (SELECT ParentId FROM Menu WHERE Code = 'voc_workspace'
                 AND Enabled = 1 AND ExpireDate > NOW() ORDER BY Id DESC LIMIT 1);
SET @prio   := (SELECT Priority + 1 FROM Menu WHERE Code = 'voc_workspace'
                 AND Enabled = 1 AND ExpireDate > NOW() ORDER BY Id DESC LIMIT 1);

-- Prasyarat. Ketiganya harus terisi sebelum lanjut.
SELECT 'menu sumber voc_workspace' AS cek,
       IF(@src IS NULL, 'TIDAK ADA <- BERHENTI', CONCAT('Id ', @src)) AS status
UNION ALL SELECT 'induk (ParentId)', IFNULL(CAST(@parent AS CHAR), 'KOSONG <- BERHENTI')
UNION ALL SELECT 'priority baru',    IFNULL(CAST(@prio   AS CHAR), 'KOSONG <- BERHENTI');

-- Geser menu setelahnya supaya Workspace Cabang berdiri tepat di sebelah
-- Workspace Omnichannel, bukan terlempar ke ujung daftar.
UPDATE Menu
   SET Priority = Priority + 1, ModifyDate = NOW(), Modifier = 1
 WHERE ParentId = @parent
   AND Priority >= @prio
   AND ExpireDate > NOW()
   AND @parent IS NOT NULL;

-- Kode menu SENGAJA dipendekkan: Menu.Code varchar(20), dan 'voc_ws_branch'
-- 13 karakter. Di MySQL 5.7 dev yang tidak strict, kelebihan panjang dipotong
-- DIAM-DIAM dan menunya berhenti cocok dengan apa pun yang mencarinya.
INSERT INTO Menu
       (Code, TypeId, NavigateUrl, Visible, Enabled, Description,
        Priority, BeginGroup, Collapsed, Level,
        CreateDate, Creator, ModifyDate, Modifier, ExpireDate, ParentId)
SELECT 'voc_ws_branch', 'SUBSIDEMENU', '#/voc/workspacebranch', 1, 1, 'Workspace Cabang',
       @prio, 1, 1, 2,
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00', @parent
  FROM DUAL
 WHERE @parent IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM Menu m WHERE m.Code = 'voc_ws_branch');

SET @menu := (SELECT Id FROM Menu WHERE Code = 'voc_ws_branch' ORDER BY Id DESC LIMIT 1);

-- Audience DISALIN dari voc_workspace, tidak ditulis tetap: RoleId berbeda di
-- tiap environment, dan menuliskan angkanya berarti memberi menu ini kepada
-- role milik orang lain.
INSERT INTO Permission
       (ObjectName, ObjectId, RoleId, ActionId, SiteId,
        CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT DISTINCT 'Menu', @menu, s.RoleId, s.ActionId, s.SiteId,
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00'
  FROM Permission s
 WHERE s.ObjectName = 'Menu'
   AND s.ObjectId   = @src
   AND s.ActionId   = 'ALLOWED'
   AND s.ExpireDate > NOW()
   AND @menu IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM Permission t
                    WHERE t.ObjectName = 'Menu'
                      AND t.ObjectId   = @menu
                      AND t.RoleId     = s.RoleId
                      AND t.ActionId   = s.ActionId
                      AND t.SiteId     = s.SiteId
                      AND t.ExpireDate > NOW());

-- Bukti. Kalau izin_aktif = 0, menunya lahir tapi tidak dipegang siapa pun
-- dan tetap tidak akan tampil.
SELECT m.Id AS MenuId, m.Code, m.ParentId, m.Priority,
       COUNT(p.Id) AS izin_aktif
  FROM Menu m
  LEFT JOIN Permission p
         ON p.ObjectName = 'Menu' AND p.ObjectId = m.Id
        AND p.ActionId = 'ALLOWED' AND p.ExpireDate > NOW()
 WHERE m.Code = 'voc_ws_branch'
 GROUP BY m.Id, m.Code, m.ParentId, m.Priority;


-- =====================================================================
-- BAGIAN C — PERBAIKAN 2: menunya ada, tapi role akunmu tidak kebagian
-- Jalankan HANYA kalau A2 memunculkan menunya tetapi A5 tidak.
-- =====================================================================
--
-- KENAPA INI BISA TERJADI, dan ini disengaja sebagian:
--
-- Migrasi 1786090000000000 memberi voc_workspace hanya kepada
-- userNews, reviewer, dan kontributor — 'Pimpinan Pusat' DICABUT dari sana.
-- Workspace Cabang mewarisi audience itu apa adanya, jadi akun yang di site
-- 169 hanya memegang 'Pimpinan Pusat' tidak akan melihatnya, dan halamannya
-- ditolak 403.
--
-- Jadi jawaban "perlu akun lain?" adalah: yang menentukan Role.Code, bukan
-- nama akunnya. Akun ber-role userNews pasti bisa.
--
-- Kalau menurutmu pimpinan MEMANG harus bisa membuka Workspace Cabang —
-- dan untuk layar yang isinya ringkasan per cabang itu masuk akal —
-- jalankan blok di bawah. Ini keputusan produk, bukan teknis.

INSERT INTO Permission
       (ObjectName, ObjectId, RoleId, ActionId, SiteId,
        CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'Menu', m.Id, r.Id, 'ALLOWED', '169',
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00'
  FROM Menu m
  JOIN Role r ON r.Code = 'Pimpinan Pusat'
 WHERE m.Code = 'voc_ws_branch'
   AND NOT EXISTS (SELECT 1 FROM Permission p
                    WHERE p.ObjectName = 'Menu'
                      AND p.ObjectId   = m.Id
                      AND p.RoleId     = r.Id
                      AND p.SiteId     = '169'
                      AND p.ActionId   = 'ALLOWED'
                      AND p.ExpireDate > NOW());

-- Ulangi A5 untuk memastikan voc_ws_branch sudah masuk daftar.


-- =====================================================================
-- MEMBATALKAN
-- =====================================================================
-- Dikedaluwarsakan, bukan dihapus — Menu.Id bisa sudah dirujuk hal lain.
--
-- UPDATE Permission SET ExpireDate = NOW()
--  WHERE ObjectName = 'Menu'
--    AND ObjectId = (SELECT Id FROM Menu WHERE Code = 'voc_ws_branch' ORDER BY Id DESC LIMIT 1)
--    AND ExpireDate > NOW();
-- UPDATE Menu SET Enabled = 0, Visible = 0, ExpireDate = NOW()
--  WHERE Code = 'voc_ws_branch';
