-- =====================================================================
-- Akun persona VoC — buat & set sandi lewat phpMyAdmin di DEV
-- =====================================================================
-- Padanan SQL dari migrasi 1786120000000000, untuk dijalankan langsung di
-- PMA. Diperlukan karena migrate.sh TIDAK meneruskan
-- VOC_TEST_ACCOUNT_PASSWORD ke dalam container, sehingga migrasi akun
-- selalu no-op saat deploy.
--
-- SATU SET NAMA SAJA. Penamaan lama (voc.pimpinan / voc.operator /
-- voc.reviewer / voc.kontributor) DIGANTIKAN set ini dan dimatikan di
-- BLOK 5. Dua konvensi di satu lingkungan menjamin ada yang memakai yang
-- salah, lalu melaporkan hasil yang tidak bisa diulang orang lain.
--
-- URUTAN: BLOK 0 -> 1 -> 2 -> 3 -> 4 -> (5) -> 6. Jangan dilompat.
-- =====================================================================

SET @plain := 'GANTI_SANDI_INI';   -- <<< WAJIB DIGANTI sebelum dijalankan
SET @site  := 169;


-- ---------------------------------------------------------------------
-- BLOK 0 — Prasyarat. Jalankan dan PERIKSA sebelum lanjut.
-- ---------------------------------------------------------------------
SELECT 'Organization OT1'    AS cek,
       (SELECT Id   FROM Organization WHERE SiteId=@site AND TypeId='OT1' ORDER BY Id LIMIT 1) AS id,
       (SELECT Name FROM Organization WHERE SiteId=@site AND TypeId='OT1' ORDER BY Id LIMIT 1) AS ket
UNION ALL SELECT 'Role userNews',       (SELECT Id FROM Role WHERE Code='userNews' LIMIT 1),       'saklar modul — WAJIB'
UNION ALL SELECT 'Role Pimpinan Pusat', (SELECT Id FROM Role WHERE Code='Pimpinan Pusat' LIMIT 1), 'untuk direktur'
UNION ALL SELECT 'Menu VoC aktif',      (SELECT COUNT(*) FROM Menu WHERE Code LIKE 'voc%' AND Enabled=1), 'harus > 0';

-- Keempat baris harus mengembalikan angka. Ada yang NULL atau 0 -> BERHENTI.


-- ---------------------------------------------------------------------
-- BLOK 1 — Contact + User
-- ---------------------------------------------------------------------
-- SENGAJA DITULIS BERULANG, BUKAN SATU INSERT DENGAN UNION.
--
-- Versi pertama skrip ini memakai derived table (UNION SELECT ... ) t lalu
-- membandingkan u.Email = t.email. Di dev itu langsung ditolak:
--
--     #1267 Illegal mix of collations (latin1_swedish_ci,IMPLICIT)
--           and (utf8mb4_unicode_ci,COERCIBLE) for operation '='
--
-- Sebabnya: User.Email di dev bercollation latin1_swedish_ci, sedangkan
-- kolom hasil derived table membawa collation koneksi. Keduanya dianggap
-- IMPLICIT, dan MySQL menolak memilih salah satu.
--
-- Di lokal (MySQL 8) hal yang sama JALAN — coercion-nya lebih longgar. Jadi
-- ini kelas kesalahan yang mustahil ketahuan sebelum menyentuh dev.
--
-- Perbaikannya bukan menambal COLLATE, melainkan membuang derived table-nya:
-- perbandingan kolom dengan LITERAL selalu aman, karena literal ikut
-- collation kolomnya. Lebih panjang, tetapi kebal terhadap collation apa pun.

INSERT INTO Contact (Name, IsPerson, TypeId, LevelId, StatusId,
                     CreateDate, Creator, ModifyDate, Modifier)
SELECT 'VoC Staf Humas', 1, 'CT1', 'CL1', 'CS1', NOW(), 1, NOW(), 1 FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM User WHERE Email = 'voc.humas@onebox.local');

INSERT INTO Contact (Name, IsPerson, TypeId, LevelId, StatusId,
                     CreateDate, Creator, ModifyDate, Modifier)
SELECT 'VoC Kepala Cabang', 1, 'CT1', 'CL1', 'CS1', NOW(), 1, NOW(), 1 FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM User WHERE Email = 'voc.cabang@onebox.local');

INSERT INTO Contact (Name, IsPerson, TypeId, LevelId, StatusId,
                     CreateDate, Creator, ModifyDate, Modifier)
SELECT 'VoC Kepala Wilayah', 1, 'CT1', 'CL1', 'CS1', NOW(), 1, NOW(), 1 FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM User WHERE Email = 'voc.wilayah@onebox.local');

INSERT INTO Contact (Name, IsPerson, TypeId, LevelId, StatusId,
                     CreateDate, Creator, ModifyDate, Modifier)
SELECT 'VoC Direktur', 1, 'CT1', 'CL1', 'CS1', NOW(), 1, NOW(), 1 FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM User WHERE Email = 'voc.direktur@onebox.local');


INSERT INTO User (Name, PasswordSalt, Password, Enabled, Email, StatusId, GroupId,
                  Failed, Logged, ContactId, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'VoC Staf Humas', SHA2(CONCAT(RAND(), UUID()), 256), 'x', 1,
       'voc.humas@onebox.local', 'SMS', 'SMS', 0, 0,
       (SELECT Id FROM Contact WHERE Name = 'VoC Staf Humas' ORDER BY Id DESC LIMIT 1),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM User WHERE Email = 'voc.humas@onebox.local');

INSERT INTO User (Name, PasswordSalt, Password, Enabled, Email, StatusId, GroupId,
                  Failed, Logged, ContactId, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'VoC Kepala Cabang', SHA2(CONCAT(RAND(), UUID()), 256), 'x', 1,
       'voc.cabang@onebox.local', 'SMS', 'SMS', 0, 0,
       (SELECT Id FROM Contact WHERE Name = 'VoC Kepala Cabang' ORDER BY Id DESC LIMIT 1),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM User WHERE Email = 'voc.cabang@onebox.local');

INSERT INTO User (Name, PasswordSalt, Password, Enabled, Email, StatusId, GroupId,
                  Failed, Logged, ContactId, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'VoC Kepala Wilayah', SHA2(CONCAT(RAND(), UUID()), 256), 'x', 1,
       'voc.wilayah@onebox.local', 'SMS', 'SMS', 0, 0,
       (SELECT Id FROM Contact WHERE Name = 'VoC Kepala Wilayah' ORDER BY Id DESC LIMIT 1),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM User WHERE Email = 'voc.wilayah@onebox.local');

INSERT INTO User (Name, PasswordSalt, Password, Enabled, Email, StatusId, GroupId,
                  Failed, Logged, ContactId, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'VoC Direktur', SHA2(CONCAT(RAND(), UUID()), 256), 'x', 1,
       'voc.direktur@onebox.local', 'SMS', 'SMS', 0, 0,
       (SELECT Id FROM Contact WHERE Name = 'VoC Direktur' ORDER BY Id DESC LIMIT 1),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM User WHERE Email = 'voc.direktur@onebox.local');


-- ---------------------------------------------------------------------
-- BLOK 2 — SET SANDI  (ini bagian yang dipakai untuk rotasi)
-- ---------------------------------------------------------------------
-- DUA PERNYATAAN TERPISAH, DAN ITU WAJIB.
--
-- Kalau salt dan hash disetel dalam SATU pernyataan UPDATE, MySQL boleh
-- memakai nilai PasswordSalt LAMA saat menghitung SHA1 — urutan evaluasi
-- kolom dalam satu UPDATE tidak dijamin. Hasilnya sandi yang tidak pernah
-- cocok, dan sebabnya nyaris mustahil dilihat dari luar: hash-nya ada,
-- panjangnya benar, isinya salah.
--
-- Skema sandi OneBox: Password = SHA1( CONCAT(PasswordSalt, sandi_polos) )
-- Lihat Crypter::getPasswordHash.

-- 2a. salt baru
UPDATE User
   SET PasswordSalt = SHA2(CONCAT(RAND(), UUID(), Id), 256),
       Enabled      = 1,
       ExpireDate   = '3000-01-01 00:00:00',
       ModifyDate   = NOW(),
       Modifier     = 1
 WHERE Email IN ('voc.humas@onebox.local','voc.cabang@onebox.local',
                 'voc.wilayah@onebox.local','voc.direktur@onebox.local');

-- 2b. hash dari salt yang BARU
UPDATE User
   SET Password = SHA1(CONCAT(PasswordSalt, @plain))
 WHERE Email IN ('voc.humas@onebox.local','voc.cabang@onebox.local',
                 'voc.wilayah@onebox.local','voc.direktur@onebox.local');

-- --- Ingin sandi BERBEDA per akun? Ganti BLOK 2 dengan pola ini, satu per
-- --- akun, dan jalankan 2a lebih dulu:
--
-- UPDATE User SET Password = SHA1(CONCAT(PasswordSalt, 'sandi-humas'))
--  WHERE Email = 'voc.humas@onebox.local';
-- UPDATE User SET Password = SHA1(CONCAT(PasswordSalt, 'sandi-cabang'))
--  WHERE Email = 'voc.cabang@onebox.local';
-- ... dan seterusnya.


-- ---------------------------------------------------------------------
-- BLOK 3 — Peran
-- ---------------------------------------------------------------------
-- SEMUA akun mendapat `userNews`, dan itu BUKAN soal senioritas.
-- LoginController::isUserNews() memakainya untuk memilih tujuan setelah
-- login: tanpa role ini user terlempar ke modul case dan tidak akan pernah
-- melihat layar VoC. Ini persis cacat yang membuat empat akun penamaan lama
-- tidak berguna untuk pengujian alur login.

INSERT INTO UserRole (CreateDate, ModifyDate, UserId, RoleId, SiteId)
SELECT NOW(), NOW(), u.Id, r.Id, @site
  FROM User u
  JOIN Role r ON r.Code = 'userNews'
 WHERE u.Email IN ('voc.humas@onebox.local','voc.cabang@onebox.local',
                   'voc.wilayah@onebox.local','voc.direktur@onebox.local')
   AND NOT EXISTS (SELECT 1 FROM UserRole x
                    WHERE x.UserId=u.Id AND x.RoleId=r.Id AND x.SiteId=@site);

-- Direktur mendapat role kedua: Pimpinan Pusat.
-- Kepala Cabang dan Kepala Wilayah SENGAJA tanpa role kedua — belum ada role
-- yang artinya cocok, dan menumpang `reviewer`/`kontributor` akan menabrak
-- arti keduanya di Media Monitoring (peran alur berita, bukan hierarki
-- organisasi) sekaligus membawa 57-66 menu yang tidak relevan.
-- Personanya sementara dipilih lewat pemilih persona di layar Workspace.
INSERT INTO UserRole (CreateDate, ModifyDate, UserId, RoleId, SiteId)
SELECT NOW(), NOW(), u.Id, r.Id, @site
  FROM User u
  JOIN Role r ON r.Code = 'Pimpinan Pusat'
 WHERE u.Email = 'voc.direktur@onebox.local'
   AND NOT EXISTS (SELECT 1 FROM UserRole x
                    WHERE x.UserId=u.Id AND x.RoleId=r.Id AND x.SiteId=@site);


-- ---------------------------------------------------------------------
-- BLOK 4 — Keanggotaan organisasi
-- ---------------------------------------------------------------------
-- WAJIB. LoginController menuntut rantai User -> Member -> Organization ->
-- Site. Tanpa baris ini login ditolak dengan "You are not authorized to log
-- into this site" — pesan yang tidak menyebut Member sama sekali, sehingga
-- orang mencarinya di tempat yang salah.

INSERT INTO Member (Code, Name, OrganizationId, UserId, RoleId, Priority,
                    Enabled, StatusId, StateId, StateDate, ParentId,
                    CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT CAST(@site AS CHAR), u.Name, o.Id, u.Id, 'MR5', 1,
       1, 'ON', 'UST6', NOW(), 0, NOW(), 1, NOW(), 1, '3000-01-01 00:00:00'
  FROM User u
  JOIN (SELECT Id FROM Organization WHERE SiteId=@site AND TypeId='OT1' ORDER BY Id LIMIT 1) o
 WHERE u.Email IN ('voc.humas@onebox.local','voc.cabang@onebox.local',
                   'voc.wilayah@onebox.local','voc.direktur@onebox.local')
   AND NOT EXISTS (SELECT 1 FROM Member m WHERE m.UserId=u.Id AND m.OrganizationId=o.Id);


-- ---------------------------------------------------------------------
-- BLOK 5 — Matikan penamaan lama (opsional, tapi disarankan)
-- ---------------------------------------------------------------------
-- Dimatikan, BUKAN dihapus: belasan tabel merujuk User.Id, dan satu
-- percobaan login gagal saja sudah meninggalkan jejak di sana.
-- Lewati blok ini kalau keempatnya belum pernah dibuat di dev.

UPDATE User SET Enabled = 0, ModifyDate = NOW(), Modifier = 1
 WHERE Email IN ('voc.pimpinan@onebox.local','voc.operator@onebox.local',
                 'voc.reviewer@onebox.local','voc.kontributor@onebox.local');


-- ---------------------------------------------------------------------
-- BLOK 6 — Bukti. Jalankan dan periksa SEBELUM mencoba login.
-- ---------------------------------------------------------------------
SELECT u.Email,
       u.Enabled,
       GROUP_CONCAT(DISTINCT r.Code ORDER BY r.Id)          AS peran,
       (SELECT COUNT(*) FROM Member m WHERE m.UserId=u.Id)  AS member,
       -- Permission.SiteId varchar vs UserRole.SiteId bigint. Dibandingkan
       -- sebagai ANGKA, bukan sebagai teks: CAST(... AS CHAR) menghasilkan
       -- collation koneksi dan bisa bertabrakan dengan collation kolomnya —
       -- sumber galat #1267 yang sama dengan BLOK 1. Angka tidak punya
       -- collation, jadi tidak bisa bertabrakan.
       (SELECT COUNT(DISTINCT mn.Id)
          FROM UserRole u2
          JOIN Permission p ON p.RoleId=u2.RoleId AND p.ObjectName='Menu'
                           AND CAST(p.SiteId AS UNSIGNED)=u2.SiteId
                           AND p.ActionId='ALLOWED' AND p.ExpireDate>NOW()
          JOIN Menu mn ON mn.Id=p.ObjectId AND mn.Enabled=1 AND mn.Code LIKE 'voc%'
         WHERE u2.UserId=u.Id AND u2.SiteId=@site)           AS menu_voc,
       CASE WHEN EXISTS (SELECT 1 FROM UserRole u3 JOIN Role r3 ON r3.Id=u3.RoleId
                          WHERE u3.UserId=u.Id AND u3.SiteId=@site AND r3.Code='userNews')
            THEN 'Media Monitoring' ELSE 'case (SALAH)' END  AS mendarat_di,
       LENGTH(u.Password)                                    AS panjang_hash
  FROM User u
  LEFT JOIN UserRole ur ON ur.UserId=u.Id AND ur.SiteId=@site
  LEFT JOIN Role r      ON r.Id=ur.RoleId
 WHERE u.Email IN ('voc.humas@onebox.local','voc.cabang@onebox.local',
                   'voc.wilayah@onebox.local','voc.direktur@onebox.local')
 GROUP BY u.Id, u.Email, u.Enabled, u.Password;

-- Yang HARUS terlihat untuk keempatnya:
--   Enabled       = 1
--   member        = 1        -> kalau 0, login PASTI ditolak
--   menu_voc      > 0        -> kalau 0, login berhasil ke layar kosong
--   mendarat_di   = 'Media Monitoring'   -> kalau 'case (SALAH)', role
--                                           userNews-nya belum terpasang
--   panjang_hash  = 40       -> SHA1 selalu 40 karakter heksadesimal.
--                               Kalau 1, BLOK 2 belum jalan.
--   peran         humas/cabang/wilayah = userNews
--                 direktur             = Pimpinan Pusat,userNews


-- ---------------------------------------------------------------------
-- CATATAN — kenapa keempatnya melihat 20 menu VoC yang sama
-- ---------------------------------------------------------------------
-- Izin BERGABUNG antar-role (sidebar memakai p.RoleId IN (...)), dan
-- `userNews` sendiri memegang seluruh 20 menu VoC. Jadi memberi userNews ke
-- semua akun otomatis menyamakan menunya.
--
-- Itu memang diterima di tahap ini: yang dibedakan sekarang adalah WORKSPACE
-- dan DASHBOARD per persona, bukan hak aksesnya.
--
-- Akarnya tetap perlu dibereskan nanti: `userNews` merangkap dua hal yang
-- seharusnya terpisah — izin masuk modul DAN kumpulan izin penuh. Selama satu
-- role memegang keduanya, "boleh masuk" dan "boleh lihat semua" tidak bisa
-- dipisahkan. Perbaikannya menyentuh modul Media Monitoring, jadi bukan
-- keputusan sepihak tim VoC.


-- ---------------------------------------------------------------------
-- BLOK 7 — Membatalkan
-- ---------------------------------------------------------------------
-- DELETE m FROM Member m JOIN User u ON u.Id=m.UserId
--  WHERE u.Email IN ('voc.humas@onebox.local','voc.cabang@onebox.local',
--                    'voc.wilayah@onebox.local','voc.direktur@onebox.local');
-- DELETE ur FROM UserRole ur JOIN User u ON u.Id=ur.UserId
--  WHERE u.Email IN ('voc.humas@onebox.local','voc.cabang@onebox.local',
--                    'voc.wilayah@onebox.local','voc.direktur@onebox.local');
-- UPDATE User SET Enabled=0, ExpireDate=NOW()
--  WHERE Email IN ('voc.humas@onebox.local','voc.cabang@onebox.local',
--                  'voc.wilayah@onebox.local','voc.direktur@onebox.local');
