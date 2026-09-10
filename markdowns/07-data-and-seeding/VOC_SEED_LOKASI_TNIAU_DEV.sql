-- =====================================================================
-- Seed lokasi VoC TNI AU ke SITE 169 — phpMyAdmin DEV (onecloud_rel)
-- =====================================================================
-- Sumber : Puskesmas Kota Depok (2).xlsx, sheet "TNI AU"
-- Layak  : 62 lokasi   |   Dikeluarkan: 18 baris (lihat BLOK 5)
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
SET @batch := 'tniau';

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
-- BLOK 1 — 62 koneksi lokasi TNI AU
--
-- Aman diulang: NOT EXISTS per Name. seed_batch dipakai BLOK 2, 3, dan 6
-- untuk mengenali baris milik skrip ini tanpa menebak dari pola nama —
-- nama satuan TNI AU tidak punya awalan bersama seperti 'UPTD Puskesmas'.
-- ---------------------------------------------------------------------

-- 1/62  LANUD HALIM PERDANAKUSUMA
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD HALIM PERDANAKUSUMA', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Rajawali Baru No.1 5, RT.5/RW.11, Halim Perdanakusuma, Kec. Makasar, Kota Jakarta Timur, Daerah Khusus Ibukota Jakarta 13610","source":"selenium","pic_name":"","pic_wa":"","phone":"0218093351","group_name":"KOOPSUD I","latitude":"-6.26080671405714","longitude":"106.889107093911","branch_name":"LANUD HALIM PERDANAKUSUMA","external_place_id":"ChIJKztoAN7yaS4R3TEjVAPqzLo","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD HALIM PERDANAKUSUMA');

-- 2/62  LANUD ATANG SENDJAJA
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD ATANG SENDJAJA', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Atang Senjaya, Atang Senjaya, Kec. Kemang, Kabupaten Bogor, Jawa Barat 16310","source":"selenium","pic_name":"","pic_wa":"","phone":"082517534731","group_name":"KOOPSUD I","latitude":"-6.54783631725144","longitude":"106.75894160185","branch_name":"LANUD ATANG SENDJAJA","external_place_id":"ChIJm1vrRGTDaS4RQpJlfrm0B9E","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD ATANG SENDJAJA');

-- 3/62  LANUD SOEWONDO
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD SOEWONDO', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Imam Bonjol, Suka Damai, Kec. Medan Polonia, Kota Medan, Sumatera Utara 20159","source":"selenium","pic_name":"Dinas Personel Lanud Soewondo","pic_wa":"","phone":"0614572323","group_name":"KOOPSUD I","latitude":"3.5608242706117","longitude":"98.6819673920603","branch_name":"LANUD SOEWONDO","external_place_id":"ChIJNV0XxyIxMTARGx5h8n0lAfo","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD SOEWONDO');

-- 4/62  LANUD ROESMIN NURJADIN
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD ROESMIN NURJADIN', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Adi Sucipto No. 01, Kelurahan Maharatu, Kecamatan Marpoyan Damai, Kota Pekanbaru, Provinsi Riau","source":"selenium","pic_name":"","pic_wa":"","phone":"076161456","group_name":"KOOPSUD I","latitude":"0.467478355662014","longitude":"101.443005357671","branch_name":"LANUD ROESMIN NURJADIN","external_place_id":"ChIJD5eEqNKv1TER2mSi8q_Bw90","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD ROESMIN NURJADIN');

-- 5/62  LANUD HUSEIN SASTRANEGARA
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD HUSEIN SASTRANEGARA', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Pajajaran Dalam No.156, Husen Sastranegara, Kota Bandung, Jawa Barat 40174","source":"selenium","pic_name":"","pic_wa":"","phone":"0226041221","group_name":"KOOPSUD I","latitude":"-6.90378623018137","longitude":"107.579920384656","branch_name":"LANUD HUSEIN SASTRANEGARA","external_place_id":"ChIJe3sZom7naC4RafgHvuENUoM","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD HUSEIN SASTRANEGARA');

-- 6/62  LANUD SURYADARMA
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD SURYADARMA', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"West Kalijati, Kalijati, Subang Regency, West Java 41271","source":"selenium","pic_name":"","pic_wa":"","phone":"0260460229","group_name":"KOOPSUD I","latitude":"-6.52813547754567","longitude":"107.655995315343","branch_name":"LANUD SURYADARMA","external_place_id":"ChIJKTKnhxAWaS4Rct5M9qpcfg4","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD SURYADARMA');

-- 7/62  LANUD SUPADIO
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD SUPADIO', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Bandara Supadio, Limbung, Kec. Sungai Raya, Kabupaten Kubu Raya, Kalimantan Barat 78391","source":"selenium","pic_name":"Dispers Lanud Supadio","pic_wa":"","phone":"082154442551","group_name":"KOOPSUD I","latitude":"-0.143293139163869","longitude":"109.410057328835","branch_name":"LANUD SUPADIO","external_place_id":"ChIJz-UfIbdZHS4RKO26fiUrlb4","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD SUPADIO');

-- 8/62  LANUD MAIMUN SALEH
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD MAIMUN SALEH', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Cot Ba''u, Sukajaya, Sabang City, Aceh 24411","source":"selenium","pic_name":"Kapten Lek Wisnu Septianto","pic_wa":"","phone":"082192713538","group_name":"KOOPSUD I","latitude":"5.87175655880534","longitude":"95.3416520999999","branch_name":"LANUD MAIMUN SALEH","external_place_id":"ChIJi5xTto7HQTARBeha4yD2okY","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD MAIMUN SALEH');

-- 9/62  LANUD SULTAN ISKANDAR MUDA
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD SULTAN ISKANDAR MUDA', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Bandara Sultan Iskandar Muda, Cot Madhi, Kec. Blang Bintang, Kabupaten Aceh Besar, Aceh 24415","source":"selenium","pic_name":"","pic_wa":"","phone":"065126690","group_name":"KOOPSUD I","latitude":"5.51830906142113","longitude":"95.4173524153433","branch_name":"LANUD SULTAN ISKANDAR MUDA","external_place_id":"ChIJa0UFHgBHQDAR6QL4WxTQxrE","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD SULTAN ISKANDAR MUDA');

-- 10/62  LANUD RAJA FISABILILLAH
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD RAJA FISABILILLAH', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Nusantara No.KM 12, RW.5, Pinang Kencana, Kec. Tanjungpinang Tim., Kota Tanjung Pinang, Kepulauan Riau 29125","source":"selenium","pic_name":"","pic_wa":"","phone":"0771441618","group_name":"KOOPSUD I","latitude":"0.915941378597873","longitude":"104.524789679186","branch_name":"LANUD RAJA FISABILILLAH","external_place_id":"ChIJjS5Do_hs2TERxoEAZl-qniw","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD RAJA FISABILILLAH');

-- 11/62  LANUD SRI MULYONO HERLAMBANG (SMH)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD SRI MULYONO HERLAMBANG (SMH)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"3MWW+FG6, Jl. L.E. Siagian, Sukodadi, Kec. Sukarami, Kota Palembang, Sumatera Selatan 30961","source":"selenium","pic_name":"","pic_wa":"","phone":"0711410376","group_name":"KOOPSUD I","latitude":"-2.90365702891167","longitude":"104.696293815343","branch_name":"LANUD SRI MULYONO HERLAMBANG (SMH)","external_place_id":"ChIJG00PbclzOy4RdoJjwpdgV2I","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD SRI MULYONO HERLAMBANG (SMH)');

-- 12/62  LANUD RADEN SADJAD
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD RADEN SADJAD', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"49F3+62H, Parupuk Tabing, Koto Tangah, Padang City, West Sumatra 25586","source":"selenium","pic_name":"","pic_wa":"","phone":"077331201","group_name":"KOOPSUD I","latitude":"-0.876726248409541","longitude":"100.352644557671","branch_name":"LANUD RADEN SADJAD","external_place_id":"ChIJQdSMJCpr7DER6KqbwntOpUM","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD RADEN SADJAD');

-- 13/62  LANUD SUTAN SJAHRIR
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD SUTAN SJAHRIR', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"49F3+62H, Parupuk Tabing, Koto Tangah, Padang City, West Sumatra 25586","source":"selenium","pic_name":"","pic_wa":"","phone":"07517053504","group_name":"KOOPSUD I","latitude":"-0.876854979365289","longitude":"100.352612371164","branch_name":"LANUD SUTAN SJAHRIR","external_place_id":"ChIJs0BqoxvH1C8RbFHcSG7KpJ8","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD SUTAN SJAHRIR');

-- 14/62  LANUD H. AS. HANANDJOEDDIN
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD H. AS. HANANDJOEDDIN', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"7M36+76Q, Unnamed Road, Lesung Batang, Kec. Tj. Pandan, Kabupaten Belitung, Kepulauan Bangka Belitung 33412","source":"selenium","pic_name":"","pic_wa":"","phone":"071924402","group_name":"KOOPSUD I","latitude":"-2.74670548443264","longitude":"107.660760203701","branch_name":"LANUD H. AS. HANANDJOEDDIN","external_place_id":"ChIJ6QtxZiUXFy4RLOm5XEkhwoA","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD H. AS. HANANDJOEDDIN');

-- 15/62  LANUD WIRIADINATA
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD WIRIADINATA', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Kolonel Basyir Surya, Setiajaya, Kec. Cibeureum, Kab. Tasikmalaya, Jawa Barat 46196","source":"selenium","pic_name":"","pic_wa":"","phone":"02657526519","group_name":"KOOPSUD I","latitude":"-7.3491311895324","longitude":"108.246761230686","branch_name":"LANUD WIRIADINATA","external_place_id":"ChIJSzQuhNBZby4RDnBW87tMsQo","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD WIRIADINATA');

-- 16/62  LANUD PANGERAN M.BUN YAMIN
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD PANGERAN M.BUN YAMIN', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"96PF+6RC, Astra Ksetra, Menggala, Tulang Bawang Regency, Lampung 34693","source":"selenium","pic_name":"","pic_wa":"","phone":"081211341160","group_name":"KOOPSUD I","latitude":"-4.61419103788204","longitude":"105.224652341371","branch_name":"LANUD PANGERAN M.BUN YAMIN","external_place_id":"ChIJncJ7biZGPy4RTCHQT2PkmkE","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD PANGERAN M.BUN YAMIN');

-- 17/62  LANUD SUGIRI SUKANI
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD SUGIRI SUKANI', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"8794+5CP, Jl. Airstripe Lanud Sukani, Beber, Kec. Ligung, Kabupaten Majalengka, Jawa Barat 45456","source":"selenium","pic_name":"","pic_wa":"","phone":"0233882036","group_name":"KOOPSUD I","latitude":"-6.68189982849942","longitude":"108.256129073015","branch_name":"LANUD SUGIRI SUKANI","external_place_id":"ChIJLedKJfvZbi4RpXLf7_qy6NE","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD SUGIRI SUKANI');

-- 18/62  LANUD HARRY HADISOEMANTRI
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD HARRY HADISOEMANTRI', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"3MRV+4W3, Unnamed Road, Sinar Tebudak, Kec. Tujuh Belas, Kabupaten Bengkayang, Kalimantan Barat 79251","source":"selenium","pic_name":"","pic_wa":"","phone":"0562631424","group_name":"KOOPSUD I","latitude":"1.0904050496122","longitude":"109.695339441792","branch_name":"LANUD HARRY HADISOEMANTRI","external_place_id":"ChIJTV35oU2p_DERg-o0TTrA6lw","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD HARRY HADISOEMANTRI');

-- 19/62  LANUD HANG NADIM
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD HANG NADIM', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"545F+579, Batu Besar, Nongsa, Batam City, Riau Islands 29466","source":"selenium","pic_name":"","pic_wa":"","phone":"0778470620","group_name":"KOOPSUD I","latitude":"1.15803621973724","longitude":"104.123651424598","branch_name":"LANUD HANG NADIM","external_place_id":"ChIJu7zANpyH2TERkz517150P1g","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD HANG NADIM');

-- 20/62  LANUD ISWAHJUDI (IWY)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD ISWAHJUDI (IWY)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"9CWX+644, Jl. Marsma TNI Anumerta R. Iswahjudi, Bakung, Maospati, Kec. Maospati, Kabupaten Magetan, Jawa Timur 63392","source":"selenium","pic_name":"","pic_wa":"","phone":"0351867190","group_name":"KOOPSUD II","latitude":"-7.60426271038816","longitude":"111.448663278031","branch_name":"LANUD ISWAHJUDI (IWY)","external_place_id":"ChIJ2czTynOVeS4RoIKeZpt7E8w","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD ISWAHJUDI (IWY)');

-- 21/62  LANUD ABDUL RACHMAN SALEH (ABD)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD ABDUL RACHMAN SALEH (ABD)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Krajan, Saptorenggo, Pakis, Malang Regency, East Java","source":"selenium","pic_name":"","pic_wa":"","phone":"0341 401004","group_name":"KOOPSUD II","latitude":"-7.93574178692193","longitude":"112.707704457624","branch_name":"LANUD ABDUL RACHMAN SALEH (ABD)","external_place_id":"ChIJ9zIUwkkp1i0RfqrZYEJec6s","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD ABDUL RACHMAN SALEH (ABD)');

-- 22/62  LANUD SULTAN HASANUDDIN (HND)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD SULTAN HASANUDDIN (HND)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"WGRV+7MR, Unnamed Road, Hasanuddin, Kec. Mandai, Kabupaten Maros, Sulawesi Selatan 90552","source":"selenium","pic_name":"","pic_wa":"","phone":"0411 553044","group_name":"KOOPSUD II","latitude":"-5.05907343331543","longitude":"119.544612068777","branch_name":"LANUD SULTAN HASANUDDIN (HND)","external_place_id":"ChIJv2hn55v5vi0RGXyDdLIJYwg","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD SULTAN HASANUDDIN (HND)');

-- 23/62  LANUD MULJONO (MUL)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD MULJONO (MUL)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"JQ94+RXP, Manyar, Sedati Agung, Kec. Sedati, Kabupaten Sidoarjo, Jawa Timur 61253","source":"selenium","pic_name":"","pic_wa":"","phone":"0318667771","group_name":"KOOPSUD II","latitude":"-7.38012648133855","longitude":"112.757458528835","branch_name":"LANUD MULJONO (MUL)","external_place_id":"ChIJtV_Ec_zk1y0RvwD9PGIZuP4","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD MULJONO (MUL)');

-- 24/62  LANUD DHOMBER (DMB)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD DHOMBER (DMB)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Mulawarman No.31, Sepinggan, Kecamatan Balikpapan Selatan, Kota Balikpapan, Kalimantan Timur 76116","source":"selenium","pic_name":"","pic_wa":"","phone":"0542761142","group_name":"KOOPSUD II","latitude":"-1.2603632064024","longitude":"116.915518682269","branch_name":"LANUD DHOMBER (DMB)","external_place_id":"ChIJOwFR9mFF8S0Rq9XSPBe2b5o","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD DHOMBER (DMB)');

-- 25/62  LANUD SYAMSUDDIN NOOR (SAM)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD SYAMSUDDIN NOOR (SAM)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"HQ73+5V5, Jl. Angkasa, Landasan Ulin Utara, Kec. Liang Anggang, Kota Banjar Baru, Kalimantan Selatan 70724","source":"selenium","pic_name":"","pic_wa":"","phone":"05114705277","group_name":"KOOPSUD II","latitude":"-3.43689730923851","longitude":"114.754831659522","branch_name":"LANUD SYAMSUDDIN NOOR (SAM)","external_place_id":"ChIJ66GK8w-D5i0RnH6_8nTOS54","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD SYAMSUDDIN NOOR (SAM)');

-- 26/62  LANUD SAM RATULANGI
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD SAM RATULANGI', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"GWPC+6P8, Lapangan, Mapanget, Manado City, North Sulawesi","source":"selenium","pic_name":"","pic_wa":"","phone":"0431 811077","group_name":"KOOPSUD II","latitude":"1.53573222470368","longitude":"124.922107520896","branch_name":"LANUD SAM RATULANGI","external_place_id":"ChIJU5mBwRWhhzIR3uQ1Bdp70qE","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD SAM RATULANGI');

-- 27/62  LANUD ISKANDAR (IKR)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD ISKANDAR (IKR)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Iskandar, Pasir Panjang, Kec. Arut Sel., Kabupaten Kotawaringin Barat, Kalimantan Tengah 74181","source":"selenium","pic_name":"","pic_wa":"","phone":"053221339","group_name":"KOOPSUD II","latitude":"-2.70408111289259","longitude":"111.669335801314","branch_name":"LANUD ISKANDAR (IKR)","external_place_id":"ChIJiYUJtCXwCC4RU8-CIbsMl80","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD ISKANDAR (IKR)');

-- 28/62  LANUD ANANG BUSRA (ANB)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD ANANG BUSRA (ANB)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"8HJ8+RFH, Jl. Aki Balak, Karang Anyar Pantai, Kec. Tarakan Bar., Kota Tarakan, Kalimantan Utara","source":"selenium","pic_name":"","pic_wa":"","phone":"05512026772","group_name":"KOOPSUD II","latitude":"3.33220724640681","longitude":"117.566272810918","branch_name":"LANUD ANANG BUSRA (ANB)","external_place_id":"ChIJ7xi03QN1FDIRWhPNvCODaZ0","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD ANANG BUSRA (ANB)');

-- 29/62  LANUD HALUOLEO (HLO)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD HALUOLEO (HLO)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"WC75+883, Ambaipua, Ranomeeto, South Konawe Regency, South East Sulawesi 93871","source":"selenium","pic_name":"","pic_wa":"","phone":"04013121833","group_name":"KOOPSUD II","latitude":"-4.0864861626237","longitude":"122.408540491871","branch_name":"LANUD HALUOLEO (HLO)","external_place_id":"ChIJAe0oNEKJmC0RoKoZgaPGH9Y","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD HALUOLEO (HLO)');

-- 30/62  LANUD I GUSTI NGURAH RAI (RAI)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD I GUSTI NGURAH RAI (RAI)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Airport Ngurah Rai No.12, Tuban, Kec. Kuta, Kabupaten Badung, Bali 80361","source":"selenium","pic_name":"","pic_wa":"","phone":"03619351119","group_name":"KOOPSUD II","latitude":"-8.74425316201479","longitude":"115.170698707939","branch_name":"LANUD I GUSTI NGURAH RAI (RAI)","external_place_id":"ChIJ_fxBVhdE0i0RiekG4FikVhI","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD I GUSTI NGURAH RAI (RAI)');

-- 31/62  LANUD TUAN GURU KYAI HAJI MUHAMMAD ZAINUDIN (ZAM)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD TUAN GURU KYAI HAJI MUHAMMAD ZAINUDIN (ZAM)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Adi Sucipto No.1, Rembiga, Kec. Selaparang, Kota Mataram, Nusa Tenggara Bar. 83124","source":"selenium","pic_name":"","pic_wa":"","phone":"081119308460","group_name":"KOOPSUD II","latitude":"-8.56288301755445","longitude":"116.106836472095","branch_name":"LANUD TUAN GURU KYAI HAJI MUHAMMAD ZAINUDIN (ZAM)","external_place_id":"ChIJFUKS1SrBzS0RGciTjKxnNIk","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD TUAN GURU KYAI HAJI MUHAMMAD ZAINUDIN (ZAM)');

-- 32/62  LANUD EL TARI
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD EL TARI', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"RMC7+RFC, Jl. Adisucipto, Penfui, Kec. Maulafa, Kota Kupang, Nusa Tenggara Tim.","source":"selenium","pic_name":"","pic_wa":"","phone":"0380881373","group_name":"KOOPSUD II","latitude":"-10.1776008397008","longitude":"123.663691673015","branch_name":"LANUD EL TARI","external_place_id":"ChIJX1V0UACFViwRBZ8U1L2CGyY","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD EL TARI');

-- 33/62  LANUD JENDERAL BESAR SUDIRMAN
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD JENDERAL BESAR SUDIRMAN', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Bandara, Jenderal Besar Soedirman, Area Sawah, Wirasaba, Bukateja, Purbalingga Regency, Central Java 53382","source":"selenium","pic_name":"","pic_wa":"","phone":"0281892222","group_name":"KOOPSUD II","latitude":"-7.45961710135249","longitude":"109.417295968777","branch_name":"LANUD JENDERAL BESAR SUDIRMAN","external_place_id":"ChIJHfsJ8ppRZS4R8gEXPjHXm38","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD JENDERAL BESAR SUDIRMAN');

-- 34/62  LANUD MANUHUA (MNA)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD MANUHUA (MNA)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Majapahit-Biak, Karang Mulia, Kec. Samofa, Kabupaten Biak Numfor, Papua 98118","source":"selenium","pic_name":"","pic_wa":"","phone":"098121801","group_name":"KOOPSUD III","latitude":"-1.17603674191571","longitude":"136.090284635703","branch_name":"LANUD MANUHUA (MNA)","external_place_id":"ChIJHera5P2OA2gR-Qc39k01e2c","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD MANUHUA (MNA)');

-- 35/62  LANUD JOHANNES ABRAHAM DIMARA (DMA)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD JOHANNES ABRAHAM DIMARA (DMA)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Garuda Spadem, Kel. Muli, Kec. Merauke, Kabupaten Merauke, Papua Selatan 99615","source":"selenium","pic_name":"","pic_wa":"","phone":"0971321541","group_name":"KOOPSUD III","latitude":"-8.52417790714348","longitude":"140.41439904603","branch_name":"LANUD JOHANNES ABRAHAM DIMARA (DMA)","external_place_id":"ChIJxTV88VUVtWkReb96kQR-t2Q","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD JOHANNES ABRAHAM DIMARA (DMA)');

-- 36/62  LANUD PATTIMURA (PTA)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD PATTIMURA (PTA)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"73VX+HF3, Unnamed Road, Laha, Kec. Tlk. Ambon, Kota Ambon, Maluku","source":"selenium","pic_name":"","pic_wa":"","phone":"0911313641","group_name":"KOOPSUD III","latitude":"-3.7059196911971","longitude":"128.09879114603","branch_name":"LANUD PATTIMURA (PTA)","external_place_id":"ChIJgzOljnLnbC0RwOd8X2NignU","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD PATTIMURA (PTA)');

-- 37/62  LANUD LEO WATTIMENA (LWM)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD LEO WATTIMENA (LWM)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"27QV+WH9, Darame, Morotai Selatan, Morotai Island Regency, North Maluku","source":"selenium","pic_name":"","pic_wa":"","phone":"09232221113","group_name":"KOOPSUD III","latitude":"2.03996245259105","longitude":"128.294348380418","branch_name":"LANUD LEO WATTIMENA (LWM)","external_place_id":"ChIJ_3BTbECYkDIR6HN__iuhtmY","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD LEO WATTIMENA (LWM)');

-- 38/62  LANUD DOMINICUS DUMATUBUN (DMN)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD DOMINICUS DUMATUBUN (DMN)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"8PPM+P8W, Langgur, Kei Kecil, Sotheast Maluku Regency, Maluku","source":"selenium","pic_name":"","pic_wa":"","phone":"091621070","group_name":"KOOPSUD III","latitude":"-5.66289356463909","longitude":"132.733376444179","branch_name":"LANUD DOMINICUS DUMATUBUN (DMN)","external_place_id":"ChIJQR-3U4cbMC0RBB53C1ZzgYs","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD DOMINICUS DUMATUBUN (DMN)');

-- 39/62  LANUD YOHANIS KAPIYAU (YKU)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD YOHANIS KAPIYAU (YKU)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"FV6V+HJW Lanud Yohanis Kapiyau Timika, Kwamki, Kec. Mimika Baru, Kabupaten Mimika, Papua Tengah 99971","source":"selenium","pic_name":"","pic_wa":"","phone":"0901321333","group_name":"KOOPSUD III","latitude":"-4.53830519608628","longitude":"136.8940726","branch_name":"LANUD YOHANIS KAPIYAU (YKU)","external_place_id":"ChIJN934gjp3I2gRrcvg1QQhR4M","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD YOHANIS KAPIYAU (YKU)');

-- 40/62  LANUD IG DEWANTO
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD IG DEWANTO', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"48WJ+4H, Tumbur, Wer Tamrian, Tanimbar Islands, Maluku","source":"selenium","pic_name":"","pic_wa":"","phone":"081333872288.","group_name":"KOOPSUD III","latitude":"-7.85444663640466","longitude":"131.331456915343","branch_name":"LANUD IG DEWANTO","external_place_id":"ChIJy5KBc-1NJy0RvnfuOcH5Kao","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD IG DEWANTO');

-- 41/62  WING I PASKHAS
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - WING I PASKHAS', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"14, Jl. Kokrosono No.8, RT.14/RW.3, Halim Perdanakusuma, Kec. Makasar, Kota Jakarta Timur, Daerah Khusus Ibukota Jakarta 13610","source":"selenium","pic_name":"","pic_wa":"","phone":"","group_name":"KOPASGAT","latitude":"-6.2781570746916","longitude":"106.904956885971","branch_name":"WING I PASKHAS","external_place_id":"ChIJ_fuT97byaS4RLKm4BMSap1A","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - WING I PASKHAS');

-- 42/62  WING II PASKHAS
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - WING II PASKHAS', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"14, Jl. Kokrosono No.8, RT.14/RW.3, Halim Perdanakusuma, Kec. Makasar, Kota Jakarta Timur, Daerah Khusus Ibukota Jakarta 13610","source":"selenium","pic_name":"","pic_wa":"","phone":"04114813598","group_name":"KOPASGAT","latitude":"-6.27802910077201","longitude":"106.905053445494","branch_name":"WING II PASKHAS","external_place_id":"ChIJoXbMvMH7vi0RDvu8LfsCJ4g","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - WING II PASKHAS');

-- 43/62  WING III PASKHAS
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - WING III PASKHAS', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"HM8C+FRM, Suka Damai, Medan Polonia, Medan City, North Sumatra 20152","source":"selenium","pic_name":"","pic_wa":"","phone":"","group_name":"KOPASGAT","latitude":"3.91703547374251","longitude":"98.7819002861255","branch_name":"WING III PASKHAS","external_place_id":"ChIJL9SabQAxMTARUpvz_Sy92ZE","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - WING III PASKHAS');

-- 44/62  SATUAN BRAVO ’90
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - SATUAN BRAVO ’90', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Raya Lapan 90- Cisauk, Sukamulya, Kec. Rumpin, Kabupaten Bogor, Jawa Barat 16350","source":"selenium","pic_name":"","pic_wa":"","phone":"","group_name":"KOPASGAT","latitude":"-6.36117252417587","longitude":"106.63665352234","branch_name":"SATUAN BRAVO ’90","external_place_id":"ChIJr93KsZ7laS4RANo-GSxLhhg","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - SATUAN BRAVO ’90');

-- 45/62  PUSDIKLAT PASKHAS
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - PUSDIKLAT PASKHAS', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Hercules 2, Lanud Sulaiman, Kec. Margahayu, Kabupaten Bandung, Jawa Barat 40229","source":"selenium","pic_name":"","pic_wa":"","phone":"022-5406777","group_name":"KOPASGAT","latitude":"-6.9848","longitude":"107.5718","branch_name":"PUSDIKLAT PASKHAS","external_place_id":"ChIJ2bZF0M3uaC4RrWqFzrQtAA8","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - PUSDIKLAT PASKHAS');

-- 46/62  AAU
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - AAU', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Raya Solo - Yogyakarta, Mereden, Sendangtirto, Kec. Kalasan, Kabupaten Sleman, Daerah Istimewa Yogyakarta 55281","source":"selenium","pic_name":"","pic_wa":"","phone":"0274486922","group_name":"BALAKPUS","latitude":"-7.7834","longitude":"110.444","branch_name":"AAU","external_place_id":"ChIJMafrGvxZei4RlrmwakV2bZc","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - AAU');

-- 47/62  SESKOAU
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - SESKOAU', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Lembang, West Bandung Regency, West Java 40391","source":"selenium","pic_name":"","pic_wa":"","phone":"0222786136","group_name":"BALAKPUS","latitude":"-6.82331194312342","longitude":"107.625579257671","branch_name":"SESKOAU","external_place_id":"ChIJSyCN5uDgaC4RveJMjPCfQAc","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - SESKOAU');

-- 48/62  POMAU   [place_id tergandakan, dipulihkan]
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - POMAU', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Squadron O No.10 13, RT.13/RW.4, Halim Perdanakusuma, Kec. Makasar, Kota Jakarta Timur, Daerah Khusus Ibukota Jakarta 13610","source":"selenium","pic_name":"","pic_wa":"","phone":"081119626026","group_name":"BALAKPUS","latitude":"-6.27301944509081","longitude":"106.884614732001","branch_name":"POMAU","external_place_id":"ChIJ69kZvuvyaS4RPLKxZ7S7AHs","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - POMAU');

-- 49/62  LAKESPRA
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LAKESPRA', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"MT Haryono St No.41, RT.1/RW.1, Cikoko, Pancoran, South Jakarta City, Jakarta 12770","source":"selenium","pic_name":"","pic_wa":"","phone":"0217980002","group_name":"BALAKPUS","latitude":"-6.24347933967542","longitude":"106.860868115343","branch_name":"LAKESPRA","external_place_id":"ChIJP6nWjqbzaS4RWjTn3Jw3Wx8","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LAKESPRA');

-- 50/62  KOOPSUD II
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - KOOPSUD II', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Perintis Kemerdekaan No.190, Daya, Kec. Biringkanaya, Kota Makassar, Sulawesi Selatan 90241","source":"selenium","pic_name":"","pic_wa":"","phone":"024344836","group_name":"KOOPSUDNAS","latitude":"-5.0975","longitude":"119.5164","branch_name":"KOOPSUD II","external_place_id":"ChIJJTMFcDT7vi0R6zyk1lT-l-Q","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - KOOPSUD II');

-- 51/62  KOOPSUD III
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - KOOPSUD III', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Kayatun No.15 Blok Ae, RT.1/RW.14, Halim Perdanakusuma, Kec. Makasar, Kota Jakarta Timur, Daerah Khusus Ibukota Jakarta 13610","source":"selenium","pic_name":"Dispenau","pic_wa":"","phone":"(021) 84595217","group_name":"KOOPSUDNAS","latitude":"-6.24999776376006","longitude":"106.884009519045","branch_name":"KOOPSUD III","external_place_id":"ChIJIUumVwDzaS4RhBhE7kRkwJ4","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - KOOPSUD III');

-- 52/62  KOSEKHANUDNAS IKN
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - KOSEKHANUDNAS IKN', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"l. Padang Golf Lkr. Halim No.3, RT.3/RW.4, Halim Perdanakusuma, Kec. Makasar, Kota Jakarta Timur, Daerah Khusus Ibukota Jakarta 13610","source":"selenium","pic_name":"","pic_wa":"","phone":"","group_name":"KOOPSUDNAS","latitude":"-6.2705","longitude":"106.8934","branch_name":"KOSEKHANUDNAS IKN","external_place_id":"ChIJHWJflMPyaS4RjOKTSkdhd7I","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - KOSEKHANUDNAS IKN');

-- 53/62  KOSEKHANUDNAS II
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - KOSEKHANUDNAS II', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"VGV6+Q87, Daya, Biringkanaya, Makassar City, South Sulawesi 90241","source":"selenium","pic_name":"","pic_wa":"","phone":"0411472236","group_name":"KOOPSUDNAS","latitude":"-5.10545866477066","longitude":"119.511004347881","branch_name":"KOSEKHANUDNAS II","external_place_id":"ChIJD6re_337vi0RdqzyICGatD4","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - KOSEKHANUDNAS II');

-- 54/62  KOSEKHANUDNAS III
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - KOSEKHANUDNAS III', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Suka Damai, Kec. Medan Polonia, Kota Medan, Sumatera Utara 20219","source":"selenium","pic_name":"","pic_wa":"","phone":"","group_name":"KOOPSUDNAS","latitude":"3.5658","longitude":"98.6732","branch_name":"KOSEKHANUDNAS III","external_place_id":"ChIJ4WjTvVMxMTARBSWujYXmb-M","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - KOSEKHANUDNAS III');

-- 55/62  PUSDIKLAT HANUDNAS
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - PUSDIKLAT HANUDNAS', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"QQ2V+3QV, Jl. Wiratno, Komp. Kenjeran, Kec. Bulak, Surabaya, Jawa Timur 60121","source":"selenium","pic_name":"","pic_wa":"","phone":"","group_name":"KOOPSUDNAS","latitude":"-7.24956213867797","longitude":"112.794413099999","branch_name":"PUSDIKLAT HANUDNAS","external_place_id":"ChIJ96dCTOn51y0RkwrY_-Czjaw","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - PUSDIKLAT HANUDNAS');

-- 56/62  SEKKAU
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - SEKKAU', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"PVFP+M8F, RT.13/RW.4, Halim Perdanakusuma, Makasar, East Jakarta City, Jakarta 13610","source":"selenium","pic_name":"","pic_wa":"","phone":"0215711144","group_name":"KODIKLATAU","latitude":"-6.27564356733275","longitude":"106.886109007403","branch_name":"SEKKAU","external_place_id":"ChIJ9xr0IevyaS4R_mAdONeHZzY","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - SEKKAU');

-- 57/62  LANUD ADI SUTJIPTO
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD ADI SUTJIPTO', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"6C58+XW9, Komplek Lanud Adisutjipto, Jl. Lettu TPT Sapardal, Karang Jambe, Kec. Banguntapan, Kabupaten Bantul, Daerah Istimewa Yogyakarta 55198","source":"selenium","pic_name":"","pic_wa":"","phone":"","group_name":"KODIKLATAU","latitude":"-7.79000256140977","longitude":"110.417842397613","branch_name":"LANUD ADI SUTJIPTO","external_place_id":"ChIJG9KV-alQei4R8D1Mxnd6Ag8","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD ADI SUTJIPTO');

-- 58/62  LANUD SULAIMAN
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD SULAIMAN', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"2H8G+W4R, Jl. Hercules, Sulaiman, Kec. Margahayu, Kabupaten Bandung, Jawa Barat 40229","source":"selenium","pic_name":"Humas","pic_wa":"","phone":"087730190183","group_name":"KODIKLATAU","latitude":"-6.98250825959616","longitude":"107.576319854748","branch_name":"LANUD SULAIMAN","external_place_id":"ChIJd2C8IMzvaC4RJmznT6Ce33g","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD SULAIMAN');

-- 59/62  LANUD ADI SOEMARMO
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - LANUD ADI SOEMARMO', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Komplek Antariksa Lanud, Jl. Saturnus Jl. Adi Sumarmo No.4, Tegalrejo, Malangjiwan, Kec. Colomadu, Kabupaten Karanganyar, Jawa Tengah 57177","source":"selenium","pic_name":"","pic_wa":"","phone":"081119308475","group_name":"KODIKLATAU","latitude":"-7.53132484696705","longitude":"110.744651507403","branch_name":"LANUD ADI SOEMARMO","external_place_id":"ChIJLXNEhZ0Uei4RMWp2zfyMgeQ","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - LANUD ADI SOEMARMO');

-- 60/62  Wing 200 (Elektronika)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - Wing 200 (Elektronika)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"2H6F+5GX, Sulaiman, Margahayu, Bandung Regency, West Java 40229","source":"selenium","pic_name":"","pic_wa":"","phone":"(022) 5400084","group_name":"KODIKLATAU","latitude":"-6.98065461533546","longitude":"107.575696253433","branch_name":"Wing 200 (Elektronika)","external_place_id":"ChIJH0WRQQDpaC4RKfvBOn4q2Eo","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - Wing 200 (Elektronika)');

-- 61/62  Wing 500 (Umum)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - Wing 500 (Umum)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"FQ86+J94, Jl. Raya Semplak, Atang Senjaya, Kec. Kemang, Kabupaten Bogor, Jawa Barat 16310","source":"selenium","pic_name":"","pic_wa":"","phone":"02518325003","group_name":"KODIKLATAU","latitude":"-6.53326635764011","longitude":"106.761164705552","branch_name":"Wing 500 (Umum)","external_place_id":"ChIJgeKKYUPDaS4RhGefLt70fiI","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - Wing 500 (Umum)');

-- 62/62  Wing 600 (Wingdikal)
INSERT INTO Connection
  (MediaId, ProviderId, `From`, Port, Priority, Enabled, Error, StatusId,
   SiteId, Name, Url, UserId, Password, Options,
   CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
SELECT 'GBUSINESS','PVD99','Onebox',0,1,1,0,'CNS1',
       @site, 'VoC System - Wing 600 (Wingdikal)', @url, @usr, @pwd,
       JSON_SET('{"mock":false,"timeout":60,"api_mode":"service","kind":"location","is_official":false,"seed_batch":"tniau","location":{"city":"","address":"Jl. Kolonel Basyir Surya, Sukanagara, Purbaratu, Tasikmalaya, Jawa Barat 46196","source":"selenium","pic_name":"","pic_wa":"","phone":"02653165202","group_name":"KODIKLATAU","latitude":"-7.34188628394738","longitude":"108.249896681872","branch_name":"Wing 600 (Wingdikal)","external_place_id":"ChIJWVMcZxZZby4RDQLayRu_e2s","target_review_count":100}}',
                '$.company_id', @cid, '$.service_token', @tok),
       NOW(),1,NOW(),1,'3000-01-01 00:00:00' FROM DUAL
 WHERE @tok IS NOT NULL AND @tok<>'' AND @cid IS NOT NULL AND @cid<>''
   AND NOT EXISTS (SELECT 1 FROM Connection c
                    WHERE c.SiteId=@site AND c.Name='VoC System - Wing 600 (Wingdikal)');


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
-- BLOK 3 — bukti. Kolom pertama harus 62.
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
-- BLOK 5 — BARIS YANG TIDAK DI-SEED (18)
-- Dicantumkan, bukan dibuang diam-diam: baris yang hilang tanpa keterangan
-- akan dicari orang berhari-hari kemudian.
-- ---------------------------------------------------------------------
--   LANUD SILAS PAPARE (SPR)             koordinat tidak lengkap
--   DEPOHAR 10                           place_id sama dengan "LANUD HUSEIN SASTRANEGARA"
--   DEPOHAR 20                           place_id sama dengan "LANUD ISWAHJUDI (IWY)"
--   DEPOHAR 30                           place_id sama dengan "LANUD ABDUL RACHMAN SALEH (ABD)"
--   DEPOHAR 40                           place_id tidak berformat Google (20 karakter)
--   DEPOHAR 50                           place_id tidak berformat Google (21 karakter)
--   DEPOHAR 60                           place_id sama dengan "LANUD ISWAHJUDI (IWY)"
--   DEPOHAR 70                           place_id tidak berformat Google (20 karakter)
--   DEPOHAR 80                           place_id sama dengan "LANUD HUSEIN SASTRANEGARA"
--   KOOPSUD I                            place_id sama dengan "LANUD HALIM PERDANAKUSUMA"
--   KOPASGAT                             place_id sama dengan "PUSDIKLAT PASKHAS"
--   KOSEKHANUDNAS I                      place_id sama dengan "KOSEKHANUDNAS IKN"
--   AAU                                  place_id sama dengan "AAU"
--   Wing 100 (Terbang)                   place_id sama dengan "LANUD ADI SUTJIPTO"
--   Wing 300 (Wingdiktek)                place_id sama dengan "LANUD HUSEIN SASTRANEGARA"
--   Wing 400 (Matukjur)                  place_id sama dengan "LANUD ADI SOEMARMO"
--   Wing 700 (Hanud)                     place_id sama dengan "PUSDIKLAT HANUDNAS"
--   Wing 800 (Pasgat)                    place_id sama dengan "PUSDIKLAT PASKHAS"


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
