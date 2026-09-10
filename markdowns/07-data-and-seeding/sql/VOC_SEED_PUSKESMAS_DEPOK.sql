-- =====================================================================
-- Seed lokasi Puskesmas Kota Depok — 39 lokasi
-- =====================================================================
-- Dihasilkan dari "Puskesmas Kota Depok.xlsx". Ke-39 barisnya sudah
-- divalidasi dengan aturan yang SAMA dengan layar Lokasi
-- (VocController::locationSaveAction): format Google Place ID
-- ^[A-Za-z0-9_-]{10,255}$ dan nama maksimal 80 karakter. Nol ditolak.
--
-- ISI TIGA VARIABEL DI BAWAH SEBELUM MENJALANKAN.
--
-- @site       : Id site tujuan (site Puskesmas, BUKAN 169)
-- @company_id : tenant di Crawler. Baca catatan di bawah sebelum mengisi.
-- @token      : service token Crawler untuk tenant itu
--
-- ---------------------------------------------------------------------
-- SOAL @company_id — baca dulu, ini menentukan hasilnya
-- ---------------------------------------------------------------------
-- Tenant di Crawler MELEKAT PADA TOKEN. Pemeriksaan "TENANT MISMATCH"
-- terjadi di sisi Crawler, bukan di OneBox: ia menolak kalau lokasi yang
-- diminta bukan milik tenant si token.
--
-- Akibatnya ada dua jalan:
--
--   A. Pakai token yang ADA (company_id 3, HGA).
--      Puskesmas terdaftar di Crawler sebagai milik HGA, tetapi di OneBox
--      ia duduk di site sendiri. Pemisahan di OneBox BERSIH — layar Ulasan,
--      dashboard, dan KPI site Puskesmas tidak akan tercampur site 169.
--      Yang tercampur hanya pembukuan di sisi Crawler.
--      -> BISA DIJALANKAN HARI INI.
--
--   B. Minta token BARU untuk company Puskesmas ke tim Crawler.
--      Pemisahan bersih di kedua sisi. Ini yang benar untuk jangka panjang.
--      -> menunggu tim Crawler.
--
-- Untuk menguji "fetch dari site lain" hari ini, jalan A sudah cukup dan
-- menjawab pertanyaannya. Jalan B tetap perlu, tapi bukan penghalang
-- pengujian.
-- ---------------------------------------------------------------------

SET @site       := 0;                       -- <<< ISI Id site Puskesmas
SET @company_id := 3;                       -- <<< 3 (jalan A) atau id baru (jalan B)
SET @token      := 'ISI_SERVICE_TOKEN';     -- <<< dari tim Crawler
SET @url        := 'http://192.168.1.3:8000';

-- Penjaga: jangan pernah jalan tanpa site yang benar.
-- Kalau @site masih 0, seluruh INSERT di bawah tidak menghasilkan apa pun.

-- ---------------------------------------------------------------------
-- Lokasi (39 baris)
-- ---------------------------------------------------------------------
-- StatusId CNS1 = aktif dan boleh disapu penjadwal.
-- TargetId sengaja KOSONG: lokasi tersimpan di OneBox dulu, lalu
-- didorong ke Crawler lewat Resync. Selama TargetId kosong, layar
-- Lokasi menandainya 'belum tersinkron' — itu keadaan yang benar,
-- bukan kerusakan.

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Beji', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Bambon Raya No.7B, RT.1/RW.1, Beji Tim., Kecamatan Beji, Kota Depok, Jawa Barat 16421","source":"selenium","pic_wa":"0217757033","latitude":"-6.3758900006595","longitude":"106.82163621349244","branch_name":"UPTD Puskesmas Beji","external_place_id":"ChIJH3gt6wPsaS4RV7llJc_KNcs"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Beji');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Mekarsari', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Tipar Raya No.158, RT.05/RW.08, Mekarsari, Kec. Cimanggis, Kota Depok, Jawa Barat 16452","source":"selenium","pic_wa":"002129823647","latitude":"-6.36638085220823","longitude":"106.87061588186275","branch_name":"UPTD Puskesmas Mekarsari","external_place_id":"ChIJ_0j51YjsaS4RShE2feI0jYk"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Mekarsari');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Sukmajaya', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Arjuna Raya No.1, Mekar Jaya, Kec. Sukmajaya, Kota Depok, Jawa Barat 16411","source":"selenium","pic_wa":"002177824908","latitude":"-6.38887510475023","longitude":"106.83852766507542","branch_name":"UPTD Puskesmas Sukmajaya","external_place_id":"ChIJ6fISWPLraS4RtGfu0XUtSOI"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Sukmajaya');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Sukatani', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Wijaya Kusuma, RT.04/RW.09, Sukatani, Kec. Tapos, Kota Depok, Jawa Barat 16454","source":"selenium","pic_wa":"0082126561972","latitude":"-6.39682889722894","longitude":"106.88905082883583","branch_name":"UPTD Puskesmas Sukatani","external_place_id":"ChIJXS73K0DraS4RovXmwao3RfI"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Sukatani');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Tapos', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Raya Tapos No.85, RT.002/RW.012, Tapos, Kec. Tapos, Kota Depok, Jawa Barat 16457","source":"selenium","pic_wa":"00218762908","latitude":"-6.42538631695747","longitude":"106.88891609814907","branch_name":"UPTD Puskesmas Tapos","external_place_id":"ChIJV6rVB97qaS4RmqQzOblGywg"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Tapos');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Cisalak Pasar', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"JVGG+MQF, Perum Permata Puri I Jl. Jamrud, VI Kel, RT.6/RW.009, Cisalak Ps., Kec. Cimanggis, Kota Depok, Jawa Barat 16452","source":"selenium","pic_wa":"02122851350","latitude":"-6.37309468684964","longitude":"106.87694392883584","branch_name":"UPTD Puskesmas Cisalak Pasar","external_place_id":"ChIJa7AXkyvtaS4RF8GmW-KkfL4"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Cisalak Pasar');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Harjamukti', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Tumaritis Kavling Pertamina No.3, Harjamukti, Kec. Cimanggis, Kota Depok, Jawa Barat 16454","source":"selenium","pic_wa":"0218733165","latitude":"-6.38173555177313","longitude":"106.8922402576717","branch_name":"UPTD Puskesmas Harjamukti","external_place_id":"ChIJj4-ujF7raS4RhA9FcX3BJDw"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Harjamukti');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Cimanggis', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Raya Bogor No.km. 33, RT.5/RW.02, Curug, Kec. Cimanggis, Kota Depok, Jawa Barat 16453","source":"selenium","pic_wa":"021 8741072","latitude":"-6.38684885305077","longitude":"106.8677128","branch_name":"UPTD Puskesmas Cimanggis","external_place_id":"ChIJMVQcO3_raS4RtwnMvmVPUxc"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Cimanggis');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Tugu', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Akses UI, Tugu, Kec. Cimanggis, Kota Depok, Jawa Barat 16451","source":"selenium","pic_wa":"0218727924","latitude":"-6.35567269058534","longitude":"106.85478508650756","branch_name":"UPTD Puskesmas Tugu","external_place_id":"ChIJZxXPwVzsaS4RsYmNguiWjaY"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Tugu');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Jatijajar', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Estate, Jl. Perumahan Jatijajar Blk. C No.2 2, RT.2/RW.11, Jatijajar, Kec. Tapos, Kota Depok, Jawa Barat 16451","source":"selenium","pic_wa":"082110439010","latitude":"-6.41639524418903","longitude":"106.8623265","branch_name":"UPTD Puskesmas Jatijajar","external_place_id":"ChIJ4TH2TKvraS4R0QjI4HIU4Uc"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Jatijajar');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Pasir Gunung Selatan', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Komp. Pesona Kalisari, Jl. Villa Kalisari No.Blok B, RT.12/RW.1, Pasir Gn. Sel., Kec. Cimanggis, Kota Depok, Jawa Barat 16451","source":"selenium","pic_wa":"02129823798","latitude":"-6.3424431082303","longitude":"106.8510054155402","branch_name":"UPTD Puskesmas Pasir Gunung Selatan","external_place_id":"ChIJbdxi8U3saS4RY8iw94-AHsE"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Pasir Gunung Selatan');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Kalimulya', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Raya Kalimulya, RT.004/RW.002, Kalimulya, Kec. Cilodong, Kota Depok, Jawa Barat 16413","source":"selenium","pic_wa":"081289533542","latitude":"-6.43595251633996","longitude":"106.82125185582075","branch_name":"UPTD Puskesmas Kalimulya","external_place_id":"ChIJV1q6vBnqaS4RmJrUygfNyVU"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Kalimulya');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Cilangkap', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. H. Raya Kp. Banjaran Pucung, RT.001/RW.007, Cilangkap, Kec. Tapos, Kota Depok, Jawa Barat 16458","source":"selenium","pic_wa":"087926148","latitude":"-6.43096542826483","longitude":"106.86878982698491","branch_name":"UPTD Puskesmas Cilangkap","external_place_id":"ChIJD24XZffqaS4R_Z1cEUPibY4"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Cilangkap');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Sukamaju Baru', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Kenari Raya No.11 Blok G, Sukamaju Baru, Kec. Tapos, Kota Depok, Jawa Barat 16455","source":"selenium","pic_wa":"0812852724","latitude":"-6.40348737152404","longitude":"106.86934024603016","branch_name":"UPTD Puskesmas Sukamaju Baru","external_place_id":"ChIJQ-GDugvraS4RLe79eW0Vhtc"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Sukamaju Baru');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Tanah Baru', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Komplek, Depok Mulya No.3, RT.02/RW.01, Tanah Baru, Kecamatan Beji, Kota Depok, Jawa Barat 16426","source":"selenium","pic_wa":"02178520052","latitude":"-6.38786482636956","longitude":"106.80334186761571","branch_name":"UPTD Puskesmas Tanah Baru","external_place_id":"ChIJY1gAoUXpaS4RsiJMh0zakSM"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Tanah Baru');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Kemiri Muka', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Ciliwung No.12, Kemiri Muka, Kecamatan Beji, Kota Depok, Jawa Barat 16423","source":"selenium","pic_wa":"02122725273","latitude":"-6.38006916420122","longitude":"106.83187918650756","branch_name":"UPTD Puskesmas Kemiri Muka","external_place_id":"ChIJFVZDKQrsaS4RreiOUZVVkQ4"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Kemiri Muka');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Depok Utara', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Halmahera No.118, Beji, Kecamatan Beji, Kota Depok, Jawa Barat 16421","source":"selenium","pic_wa":"085771111854","latitude":"-6.38446169016014","longitude":"106.81104381349245","branch_name":"UPTD Puskesmas Depok Utara","external_place_id":"ChIJsyzxxMrpaS4RE3YE1-DONC0"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Depok Utara');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Limo', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Raya Grogol No.4, RT.01/RW.01, Grogol, Kec. Limo, Kota Depok, Jawa Barat 16512","source":"selenium","pic_wa":"081213379757","latitude":"-6.37953144008339","longitude":"106.7901463576717","branch_name":"UPTD Puskesmas Limo","external_place_id":"ChIJQ4C9C8vuaS4RdiG2Ca_J_KQ"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Limo');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Cinere', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Cinere Raya No.30, Cinere, Kec. Cinere, Kota Depok, Jawa Barat 16514","source":"selenium","pic_wa":"07548707","latitude":"-6.34081351518539","longitude":"106.78005687116415","branch_name":"UPTD Puskesmas Cinere","external_place_id":"ChIJ8Zc60lfuaS4R14V4JIOedvs"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Cinere');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Rangkapan Jaya Baru', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Puskesmas No.12, Rangkapan Jaya Baru, Kec. Pancoran Mas, Kota Depok, Jawa Barat 16434","source":"selenium","pic_wa":"02177882044","latitude":"-6.39938974627668","longitude":"106.78114794417921","branch_name":"UPTD Puskesmas Rangkapan Jaya Baru","external_place_id":"ChIJm5Up14PpaS4RWoVcZHDAvhE"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Rangkapan Jaya Baru');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Pasir Putih', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Puskesmas, RT.006/RW.004, Pasir Putih, Kec. Sawangan, Kota Depok, Jawa Barat 16519","source":"selenium","pic_wa":"082124700289","latitude":"-6.42585346496653","longitude":"106.78382302443131","branch_name":"UPTD Puskesmas Pasir Putih","external_place_id":"ChIJhzcdNabpaS4RjJ9FUzjD6V8"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Pasir Putih');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Kedaung', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Pertiwi Raya No.31-43, Kedaung, Kec. Sawangan, Kota Depok, Jawa Barat 16516","source":"selenium","pic_wa":"0217499267","latitude":"-6.36247599397183","longitude":"106.74995001534339","branch_name":"UPTD Puskesmas Kedaung","external_place_id":"ChIJr1KSfxXvaS4RXckQnAOjOhk"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Kedaung');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Pengasinan', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Komplek Bumi Sawangan Indah Jl. Anggrek Raya 1, RT.06/RW.09, Pengasinan, Kec. Sawangan, Kota Depok, Jawa Barat 16518","source":"selenium","pic_wa":"081315502718","latitude":"-6.41293691666667","longitude":"106.759699933467","branch_name":"UPTD Puskesmas Pengasinan","external_place_id":"ChIJaTn6avfoaS4RlGhWS3vY3I0"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Pengasinan');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Cinangka', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jalan Kampung Bulak Barat Jl. Nusa Indah, Cinangka, Kec. Sawangan, Kota Depok, Jawa Barat 16516","source":"selenium","pic_wa":"02174355525","latitude":"-6.36468724426458","longitude":"106.75928044417924","branch_name":"UPTD Puskesmas Cinangka","external_place_id":"ChIJ111osfnvaS4Rq-2-4QT9k1I"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Cinangka');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Bojongsari', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Pamulang Village, Blok H 8, RT.03/RW.16, Pd. Petir, Kec. Bojongsari, Kota Depok, Jawa Barat 16517","source":"selenium","pic_wa":"02174771693","latitude":"-6.35909825012985","longitude":"106.73133254247935","branch_name":"UPTD Puskesmas Bojongsari","external_place_id":"ChIJyYtLgwnsaS4R4T3b-C8qQ5g"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Bojongsari');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Duren Seribu', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Delima No.2, Duren Seribu, Kec. Bojongsari, Kota Depok, Jawa Barat 16518","source":"selenium","pic_wa":"081398439955","latitude":"-6.4352411978013","longitude":"106.74582282883584","branch_name":"UPTD Puskesmas Duren Seribu","external_place_id":"ChIJp3Z0UgvsaS4R_Qj9xY9iE6U"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Duren Seribu');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Pancoran Mas', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Pemuda No.2, RT.002/RW.008, Depok, Kec. Pancoran Mas, Kota Depok, Jawa Barat 16431","source":"selenium","pic_wa":"0217520130","latitude":"-6.40261047593615","longitude":"106.81923245767167","branch_name":"UPTD Puskesmas Pancoran Mas","external_place_id":"ChIJ838wD0npaS4Rj0Vb8j150u8"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Pancoran Mas');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Depok Jaya', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Melati Raya No.1 Kel, Depok Jaya, Kec. Pancoran Mas, Kota Depok, Jawa Barat 16432","source":"selenium","pic_wa":"02189080781","latitude":"-6.38964071593517","longitude":"106.81018710000001","branch_name":"UPTD Puskesmas Depok Jaya","external_place_id":"ChIJ2w7WdE3paS4RCk7Lw1Z3q3A"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Depok Jaya');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Sawangan', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Raya Muchtar No.73, Sawangan Baru, Kec. Sawangan, Kota Depok, Jawa Barat 16511","source":"selenium","pic_wa":"08580256144","latitude":"-6.40483634821002","longitude":"106.76354024603015","branch_name":"UPTD Puskesmas Sawangan","external_place_id":"ChIJUW3wH0_saS4RGbBqjPj4a2I"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Sawangan');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Mampang', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jln. Namnam Rt 005/007, Jl. Nam Nam Raya No.201 06, RT.06/RW.07, Mampang, Pancoran Mas, Depok City, West Java 16433","source":"selenium","pic_wa":"02177814212","latitude":"-6.38577239238899","longitude":"106.79792670185091","branch_name":"UPTD Puskesmas Mampang","external_place_id":"ChIJ8z9Y29TpaS4RE8x6O1VfN6Y"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Mampang');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Cipayung', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Kelurahan Cipayung No.8, Cipayung, Kec. Cipayung, Kota Depok, Jawa Barat 16437","source":"selenium","pic_wa":"081398953482","latitude":"-6.4197011766097","longitude":"106.79536618650755","branch_name":"UPTD Puskesmas Cipayung","external_place_id":"ChIJb5u6Jj7paS4R2b2B2jH4U2M"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Cipayung');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Ratu jaya', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Permata Depok Regency, Ratu Jaya, Kec. Cipayung, Kota Depok, Jawa Barat 16439","source":"selenium","pic_wa":"081294738715","latitude":"-6.42472490222458","longitude":"106.81279781534337","branch_name":"UPTD Puskesmas Ratu jaya","external_place_id":"ChIJd5Q1aE3paS4R4zF1yv4Y3fQ"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Ratu jaya');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Abadijaya', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Kerinci Raya No.1, Abadijaya, Kec. Sukmajaya, Kota Depok, Jawa Barat 16417","source":"selenium","pic_wa":"0217716940","latitude":"-6.39459314319716","longitude":"106.85198924188113","branch_name":"UPTD Puskesmas Abadijaya","external_place_id":"ChIJU6gQk8zraS4R9w1K1K1K1K0"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Abadijaya');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Baktijaya', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Gama Setia Bar. 9, Bakti Jaya, Kec. Sukmajaya, Kota Depok, Jawa Barat 16418","source":"selenium","pic_wa":"02187710143","latitude":"-6.374673725043281,","longitude":"106.85324729999999","branch_name":"UPTD Puskesmas Baktijaya","external_place_id":"ChIJs8d0d17raS4R3K3K3K3K3K0"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Baktijaya');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Pondok Sukmajaya', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Puskesmas Pd. Sukmajaya, Jl. Pondok Sukmajaya Permai No.14 Blok G2, RT.03/RW.2, Sukmajaya, Kec. Sukmajaya, Kota Depok, Jawa Barat 16412","source":"selenium","pic_wa":"0217703160","latitude":"-6.40947811746666","longitude":"106.84793875952262","branch_name":"UPTD Puskesmas Pondok Sukmajaya","external_place_id":"ChIJ111b222paS4R99999999999"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Pondok Sukmajaya');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Cilodong', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Perum GDC, Jl. Boulevard Grand Depok City, Jatimulya, Kec. Cilodong, Kota Depok, Jawa Barat 16413","source":"selenium","pic_wa":"02187918703","latitude":"-6.444368979173402,","longitude":"106.83032800185092","branch_name":"UPTD Puskesmas Cilodong","external_place_id":"ChIJm6b2tWzqaS4R2B2B2B2B2B2"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Cilodong');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Villa Pertiwi', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Komp. Villa Pertiwi No.Blok 1, Sukamaju, Kec. Cilodong, Kota Depok, Jawa Barat 16415","source":"selenium","pic_wa":"081288351484","latitude":"-6.41893969165072","longitude":"106.85115752883584","branch_name":"UPTD Puskesmas Villa Pertiwi","external_place_id":"ChIJVillaPertiwiDepok16415"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Villa Pertiwi');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Bedahan', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Bedahan, Sawangan, Depok City, West Java 16519","source":"selenium","pic_wa":"","latitude":"-6.41059416049697","longitude":"106.77066043497521","branch_name":"UPTD Puskesmas Bedahan","external_place_id":"ChIJd1dj-_7oaS4RX3OutqsT0Mw"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Bedahan');

INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, Options, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS', 'PVD99', 'Onebox', 0, 1, 1, 0, 'CNS1',
       @site, 'VoC System - UPTD Puskesmas Cimpaeun', @url,
       JSON_SET('{"mock":false,"timeout":30,"api_mode":"service","kind":"location","is_official":false,"location":{"city":"Depok","address":"Jl. Raya Tapos No.51, Cimpaeun, Kec. Tapos, Kota Depok, Jawa Barat 16459","source":"selenium","pic_wa":"081316252833","latitude":"-6.44894969827224","longitude":"106.86743487116415","branch_name":"UPTD Puskesmas Cimpaeun","external_place_id":"ChIJCimpaeunTaposDepok16459"}}', '$.company_id', @company_id, '$.service_token', @token),
       NOW(), 1, NOW(), 1, '3000-01-01 00:00:00' FROM DUAL
 WHERE @site > 0
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId = @site AND c.Name = 'VoC System - UPTD Puskesmas Cimpaeun');

-- ---------------------------------------------------------------------
-- Bukti
-- ---------------------------------------------------------------------
SELECT COUNT(*) AS lokasi_terpasang,
       SUM(JSON_UNQUOTE(JSON_EXTRACT(Options,'$.company_id')) = CAST(@company_id AS CHAR)) AS company_cocok,
       SUM(NULLIF(TargetId,'') IS NULL) AS belum_tersinkron
  FROM Connection
 WHERE SiteId = @site AND ProviderId = 'PVD99';

-- lokasi_terpasang harus 39.
-- belum_tersinkron juga 39 pada awalnya — itu wajar. Lokasi baru terdaftar
-- di Crawler setelah Resync dijalankan; sebelum itu crawl akan ditolak
-- dengan "Crawler menolak cabang ini".
--
-- LANGKAH BERIKUTNYA, JANGAN DILEWAT:
-- buka layar Lokasi di site ini dan jalankan Resync. Tanpa itu, ke-39
-- lokasi ada di OneBox tetapi tidak dikenal Crawler sama sekali.