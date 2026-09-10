-- =====================================================================
-- Seed lokasi VoC MyRepublic ke SITE 169 — phpMyAdmin DEV (onecloud_rel)
-- =====================================================================
-- Sumber : Puskesmas Kota Depok (2).xlsx, sheet "MyRepublic"
-- Layak  : 10 lokasi   |   Dikeluarkan: 0 baris (lihat BLOK 5)
--
-- Bentuknya menyalin VOC_SEED_PUSKESMAS_SITE169_DEV.sql yang sudah
-- terbukti jalan di site ini. Versi sebelumnya gagal senyap: ia mencari
-- koneksi contoh lewat Code='VOC', padahal koneksi VoC di dev dikenali
-- dari ProviderId='PVD99'. Karena tidak ketemu, seluruh INSERT-nya
-- terhalang penjaganya sendiri dan hasilnya nol baris tanpa pesan galat.
--
-- TOKEN, URL, USER, PASSWORD, COMPANY_ID TIDAK DITULIS DI BERKAS INI.
-- Semuanya disalin saat runtime dari koneksi PVD99 yang sudah berjalan
-- di site ini, jadi nilainya mengikuti dev dan tidak pernah masuk repo.
--
-- TargetId sengaja KOSONG: lokasi tersimpan di OneBox dulu, lalu didorong
-- ke Crawler lewat Resync di layar Lokasi. Sebelum Resync, crawl akan
-- ditolak karena lokasinya belum ada di sisi Crawler.
-- =====================================================================

SET @site  := 169;
SET @batch := 'myrep';

SET @tok := (SELECT JSON_UNQUOTE(JSON_EXTRACT(Options,'$.service_token'))
               FROM Connection WHERE SiteId=@site AND ProviderId='PVD99'
                AND JSON_UNQUOTE(JSON_EXTRACT(Options,'$.service_token')) <> ''
              ORDER BY Id LIMIT 1);
SET @url := (SELECT Url FROM Connection WHERE SiteId=@site AND ProviderId='PVD99'
              AND Url<>'' ORDER BY Id LIMIT 1);
SET @usr := (SELECT UserId FROM Connection WHERE SiteId=@site AND ProviderId='PVD99'
              AND UserId<>'' ORDER BY Id LIMIT 1);
SET @pwd := (SELECT Password FROM Connection WHERE SiteId=@site AND ProviderId='PVD99'
              AND UserId<>'' ORDER BY Id LIMIT 1);
SET @cid := (SELECT JSON_UNQUOTE(JSON_EXTRACT(Options,'$.company_id'))
               FROM Connection WHERE SiteId=@site AND ProviderId='PVD99'
                AND JSON_UNQUOTE(JSON_EXTRACT(Options,'$.company_id')) <> ''
              ORDER BY Id LIMIT 1);

-- ---------------------------------------------------------------------
-- BLOK 0 — prasyarat. Semuanya HARUS terisi sebelum lanjut.
-- Kalau ada satu saja KOSONG, BLOK 1 memang tidak akan menulis apa pun —
-- lebih baik tahu alasannya di sini daripada mengira seedingnya berhasil.
-- ---------------------------------------------------------------------
SELECT 'service_token' AS cek, IF(@tok IS NULL OR @tok='','KOSONG <- BERHENTI','ada') AS status
UNION ALL SELECT 'url',        IFNULL(@url,'KOSONG <- BERHENTI')
UNION ALL SELECT 'user',       IFNULL(@usr,'KOSONG <- BERHENTI')
UNION ALL SELECT 'password',   IF(@pwd IS NULL OR @pwd='','KOSONG <- BERHENTI','ada')
UNION ALL SELECT 'company_id', IFNULL(@cid,'KOSONG <- BERHENTI')
UNION ALL SELECT 'lokasi VoC di site ini sekarang',
       CAST((SELECT COUNT(*) FROM Connection WHERE SiteId=@site AND ProviderId='PVD99') AS CHAR);


-- ---------------------------------------------------------------------
-- BLOK 1 — 10 koneksi lokasi MyRepublic
--
-- Aman diulang: NOT EXISTS per Name. seed_batch dipakai BLOK 2, 3, dan 6
-- untuk mengenali baris milik skrip ini tanpa menebak dari pola nama —
-- nama satuan TNI AU tidak punya awalan bersama seperti 'UPTD Puskesmas'.
-- ---------------------------------------------------------------------

-- 1/10  MyRepublic Branch BSD
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - MyRepublic Branch BSD', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"myrep","location":{"city":"","address":"MMW3+P4G green office park 6, Jl. BSD Green Office Park, Sampora, Cisauk, Tangerang Regency, Banten 15345","source":"selenium","pic_name":"","pic_wa":"","phone":"082112708848","group_name":"","latitude":"-6.30293018434908","longitude":"106.652802786507","branch_name":"MyRepublic Branch BSD","external_place_id":"ChIJZflAZDX7aS4R8h2PRg3tu9s","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - MyRepublic Branch BSD');

-- 2/10  MyRepublic Plaza
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - MyRepublic Plaza', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"myrep","location":{"city":"","address":"MMW3+M4X, Jl. BSD Green Office Park, Sampora, Kec. Cisauk, Kabupaten Tangerang, Banten 15345","source":"selenium","pic_name":"","pic_wa":"","phone":"088289112552","group_name":"","latitude":"-6.30312936828352","longitude":"106.65293350185","branch_name":"MyRepublic Plaza","external_place_id":"ChIJL42mQBL7aS4Rw9f08HtiyYw","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - MyRepublic Plaza');

-- 3/10  MyRepublic Cikeas
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - MyRepublic Cikeas', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"myrep","location":{"city":"","address":"Cibubur Country, Cikeas Udik, Gunung Putri, Bogor Regency, West Java 16966","source":"selenium","pic_name":"","pic_wa":"","phone":"083879630901","group_name":"","latitude":"-6.39455859289547","longitude":"106.937316284656","branch_name":"MyRepublic Cikeas","external_place_id":"ChIJgwaor4yVaS4RmULFoqVT3sw","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - MyRepublic Cikeas');

-- 4/10  MyRepublic Bekasi
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - MyRepublic Bekasi', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"myrep","location":{"city":"","address":"Ruko Bekasi Mas, Jl. Ahmad Yani No.26 Blk B, RT.004/RW.003, Marga Jaya, Kec. Bekasi Sel., Kota Bks, Jawa Barat 17141","source":"selenium","pic_name":"","pic_wa":"","phone":"088981500818","group_name":"","latitude":"-6.24080267295529","longitude":"106.993586540477","branch_name":"MyRepublic Bekasi","external_place_id":"ChIJHeI55N-NaS4R0aAf2rjsnss","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - MyRepublic Bekasi');

-- 5/10  MyRepublic Cabang Depok
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - MyRepublic Cabang Depok', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"myrep","location":{"city":"","address":"Perumahan Griya Tugu Asri Blk. A1 No.12, Tugu, Kec. Cimanggis, Kota Depok, Jawa Barat 16951","source":"selenium","pic_name":"","pic_wa":"","phone":"0895346367593","group_name":"","latitude":"-6.37638740059097","longitude":"106.876551473015","branch_name":"MyRepublic Cabang Depok","external_place_id":"ChIJp8AiIDXpaS4RG9Z_HWV6Bdo","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - MyRepublic Cabang Depok');

-- 6/10  Galeri MyRepublic
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - Galeri MyRepublic', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"myrep","location":{"city":"","address":"ITC Depok, Ruko No.22, Depok, Kec. Pancoran Mas, Kota Depok, Jawa Barat 16431","source":"selenium","pic_name":"","pic_wa":"","phone":"088294291110","group_name":"","latitude":"-6.39267910904961","longitude":"106.822579213492","branch_name":"Galeri MyRepublic","external_place_id":"ChIJAYtGRJ3raS4RXKPwKCLk_ss","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - Galeri MyRepublic');

-- 7/10  MyRepublic Branch Jakarta Selatan
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - MyRepublic Branch Jakarta Selatan', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"myrep","location":{"city":"","address":"Jl. KH Abdullah Syafei No.27 B, RT.1/RW.3, Kb. Baru, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12860","source":"selenium","pic_name":"","pic_wa":"","phone":"088981500818","group_name":"","latitude":"-6.22510756731865","longitude":"106.861148757671","branch_name":"MyRepublic Branch Jakarta Selatan","external_place_id":"ChIJv1feqPvzaS4Rq_icqCKuQwc","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - MyRepublic Branch Jakarta Selatan');

-- 8/10  MYREPUBLIC BRANCH BOGOR
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - MYREPUBLIC BRANCH BOGOR', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"myrep","location":{"city":"","address":"Jl. Raya Pajajaran No.41, RT.01/RW.06, Babakan, Kecamatan Bogor Tengah, Kota Bogor, Jawa Barat 16128","source":"selenium","pic_name":"","pic_wa":"","phone":"08887000765","group_name":"","latitude":"-6.58517969072657","longitude":"106.805612659522","branch_name":"MYREPUBLIC BRANCH BOGOR","external_place_id":"ChIJ8QAhsBrFaS4Ra4ijq_yMRGc","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - MYREPUBLIC BRANCH BOGOR');

-- 9/10  Myrepublic Branch Tangerang
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - Myrepublic Branch Tangerang', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"myrep","location":{"city":"","address":"Ruko Malibu No.C6A, Lengkong Gudang, Kec. Serpong, Kabupaten Tangerang, Banten 15321","source":"selenium","pic_name":"","pic_wa":"","phone":"081220685812","group_name":"","latitude":"-6.28865597877984","longitude":"106.665037117194","branch_name":"Myrepublic Branch Tangerang","external_place_id":"ChIJB8GxDSr7aS4Rg4WoT-OOQps","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - Myrepublic Branch Tangerang');

-- 10/10  MyRepublic Branch Jakarta Barat
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - MyRepublic Branch Jakarta Barat', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"myrep","location":{"city":"","address":"Jl. Panjang No.7, RT.2/RW.7, Kedoya Utara, Kec. Kb. Jeruk, Kota Jakarta Barat, Daerah Khusus Ibukota Jakarta 14750","source":"selenium","pic_name":"","pic_wa":"","phone":"081296714443","group_name":"","latitude":"-6.16670766496326","longitude":"106.763876799999","branch_name":"MyRepublic Branch Jakarta Barat","external_place_id":"ChIJh3q4U0L3aS4RT86oMWK-Wqk","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - MyRepublic Branch Jakarta Barat');


-- ---------------------------------------------------------------------
-- BLOK 2 — master Location OneBox + penautan
--
-- WAJIB, dan paling mudah terlupa. Tanpa baris Location dan
-- Options.onebox_location_id:
--   - Workspace Cabang menampilkan 0 cabang
--   - crawl ditolak 'Cabang belum punya master lokasi OneBox'
--   - ulasan yang masuk TIDAK terpetakan ke lokasi mana pun
-- ---------------------------------------------------------------------
INSERT INTO Location (Description, City, Longitude, Latitude, Altitude,
                      CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT JSON_UNQUOTE(JSON_EXTRACT(c.Options,'$.location.branch_name')), '',
       COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(c.Options,'$.location.longitude')) AS DECIMAL(18,12)),0),
       COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(c.Options,'$.location.latitude'))  AS DECIMAL(18,12)),0),
       0, NOW(),1,NOW(),1,'3000-01-01 00:00:00'
  FROM Connection c
 WHERE c.SiteId=@site AND c.ProviderId='PVD99'
   AND JSON_UNQUOTE(JSON_EXTRACT(c.Options,'$.seed_batch'))=@batch
   AND JSON_EXTRACT(c.Options,'$.onebox_location_id') IS NULL;

UPDATE Connection c
  JOIN Location l ON l.Description = JSON_UNQUOTE(JSON_EXTRACT(c.Options,'$.location.branch_name'))
                 AND l.ExpireDate > NOW()
   SET c.Options = JSON_SET(c.Options,'$.onebox_location_id',l.Id),
       c.ModifyDate=NOW(), c.Modifier=1
 WHERE c.SiteId=@site AND c.ProviderId='PVD99'
   AND JSON_UNQUOTE(JSON_EXTRACT(c.Options,'$.seed_batch'))=@batch
   AND JSON_EXTRACT(c.Options,'$.onebox_location_id') IS NULL;


-- ---------------------------------------------------------------------
-- BLOK 3 — bukti. Kolom pertama harus 10.
-- ---------------------------------------------------------------------
SELECT COUNT(*) AS terpasang,
       SUM(JSON_EXTRACT(Options,'$.onebox_location_id') IS NOT NULL) AS punya_master,
       SUM(JSON_UNQUOTE(JSON_EXTRACT(Options,'$.service_token')) <> '') AS punya_token,
       SUM(NULLIF(TargetId,'') IS NULL) AS belum_tersinkron
  FROM Connection
 WHERE SiteId=@site AND ProviderId='PVD99'
   AND JSON_UNQUOTE(JSON_EXTRACT(Options,'$.seed_batch'))=@batch;

-- Place ID kembar di dalam site. HARUS nol baris: dua lokasi dengan tempat
-- Google yang sama menarik ulasan yang sama dua kali, dan setiap angka di
-- layar ikut terhitung ganda.
SELECT JSON_UNQUOTE(JSON_EXTRACT(Options,'$.location.external_place_id')) AS place_id,
       COUNT(*) AS jumlah
  FROM Connection
 WHERE SiteId=@site AND ProviderId='PVD99'
 GROUP BY place_id HAVING COUNT(*) > 1;


-- ---------------------------------------------------------------------
-- BLOK 4 — sesudah ini
--
-- Buka layar Lokasi site 169 lalu jalankan Resync. Tanpa itu, lokasi-lokasi
-- ini ada di OneBox tetapi belum ada di Crawler, dan crawl akan ditolak.
-- ---------------------------------------------------------------------


-- ---------------------------------------------------------------------
-- BLOK 5 — BARIS YANG TIDAK DI-SEED (0)
-- Dicantumkan, bukan dibuang diam-diam: baris yang hilang tanpa keterangan
-- akan dicari orang berhari-hari kemudian.
-- ---------------------------------------------------------------------
--   (tidak ada — seluruh baris sheet ini layak di-seed)


-- ---------------------------------------------------------------------
-- BLOK 6 — membatalkan
-- Connection dulu, baru Location: urutan terbalik meninggalkan Connection
-- yang menunjuk Location yang sudah tidak ada.
-- ---------------------------------------------------------------------
-- CREATE TEMPORARY TABLE tmp_hapus AS
--   SELECT DISTINCT JSON_UNQUOTE(JSON_EXTRACT(Options,'$.onebox_location_id')) AS Id
--     FROM Connection WHERE SiteId=@site AND ProviderId='PVD99'
--      AND JSON_UNQUOTE(JSON_EXTRACT(Options,'$.seed_batch'))=@batch;
-- DELETE FROM Connection WHERE SiteId=@site AND ProviderId='PVD99'
--   AND JSON_UNQUOTE(JSON_EXTRACT(Options,'$.seed_batch'))=@batch;
-- DELETE FROM Location WHERE Id IN (SELECT Id FROM tmp_hapus);
-- DROP TEMPORARY TABLE tmp_hapus;
