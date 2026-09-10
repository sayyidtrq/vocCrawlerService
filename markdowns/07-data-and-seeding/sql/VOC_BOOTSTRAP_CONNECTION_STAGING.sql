-- =====================================================================
-- VoC staging release/1.123.0 — HIDUPKAN CONNECTION
--
-- Direvisi 10 September 2026 setelah tiga fakta terkonfirmasi:
--   - SiteId staging = 169  (jadi seed TIDAK salah site; teori itu gugur)
--   - Reference PVD99 ber-Code 'Voc'  (id-nya memang milik VoC)
--   - Dua baris Connection PVD99 sudah ada: Id 985 & 986, keduanya mock
--
-- Karena barisnya sudah ada di site yang benar, skrip ini TIDAK membuat baris
-- baru. Ia menghidupkan yang sudah ada.
--
-- SEBAB TUNGGAL kenapa "tambah lokasi" ditolak:
--   voc_setup_all.sql menulis Url='' (baris 95: ...,'','',0,'',...), dan
--   VocController::vocCredentialTemplate() melewati setiap baris ber-Url kosong:
--
--       // Tanpa Url tidak ada yang bisa dihubungi, seberapa pun
--       // lengkapnya kredensial di row itu.
--       if (trim((string) $c->Url) === '') { continue; }
--
--   Jadi alert "Jalankan voc_setup_all.sql dulu" menunjuk skrip yang justru
--   menghasilkan baris yang ditolak oleh kode yang memunculkan alert itu.
--
-- SYARAT yang harus dipenuhi, dibaca dari vocCredentialTemplate() +
-- punyaServiceToken():
--   1. Url                    TIDAK kosong
--   2. Options.api_mode       = 'service'   <- wajib; token tanpa ini ditolak
--   3. Options.service_token  terisi
--   4. Options.location       ada           <- sudah ada dari seed
--
-- JANGAN di-commit setelah diisi. Berkas ini memuat service token.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 0) ISI NILAI INI DULU
-- ---------------------------------------------------------------------
SET @site        := 169;    -- terkonfirmasi: site staging
SET @crawler_url := '';     -- URL server Crawler yang dipilih (lihat catatan)
SET @token       := '';     -- service token untuk company staging
SET @company     := 0;      -- company_id di server Crawler tsb

-- ⚠️ @crawler_url menentukan server Crawler MANA yang akan ditulisi staging.
--    Provisioning worklist itu operasi TULIS — ia membuat lokasi di sisi
--    Crawler. Mengarahkan staging ke server prod berarti lokasi uji staging
--    lahir di data produksi. Lihat CRAWLER_SERVICE_UNTUK_STAGING.md.

-- ---------------------------------------------------------------------
-- 1) GERBANG — berhenti kalau isiannya belum benar
-- ---------------------------------------------------------------------
DROP PROCEDURE IF EXISTS voc_cek_bootstrap;
DELIMITER //
CREATE PROCEDURE voc_cek_bootstrap()
BEGIN
  IF @site IS NULL OR @site <= 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BERHENTI: @site belum diisi.';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM Site WHERE Id = @site) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BERHENTI: @site tidak ada di tabel Site.';
  END IF;
  IF TRIM(COALESCE(@crawler_url,'')) = '' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT =
      'BERHENTI: @crawler_url kosong. Url kosong persis penyebab masalah yang sedang diperbaiki.';
  END IF;
  IF TRIM(COALESCE(@token,'')) = '' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT =
      'BERHENTI: @token kosong. api_mode service tanpa token tetap ditolak client.';
  END IF;
  IF @company IS NULL OR @company <= 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BERHENTI: @company belum diisi.';
  END IF;
  -- Penjaga PVD97/PVD98: id provider yang disangka milik VoC ternyata dipegang
  -- modul lain. Sudah terjadi dua kali. Kalau Code-nya bukan 'Voc', JANGAN
  -- di-UPDATE — VoC yang harus pindah id, bukan pemiliknya yang ditimpa.
  IF NOT EXISTS (SELECT 1 FROM Reference WHERE Id = 'PVD99' AND Code = 'Voc') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT =
      'BERHENTI: Reference PVD99 tidak ber-Code Voc. Eskalasi ke senior dev.';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM Connection WHERE SiteId = @site AND ProviderId = 'PVD99') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT =
      'BERHENTI: tidak ada Connection PVD99 di site ini. Skrip ini menghidupkan baris yang sudah ada, bukan membuat baru.';
  END IF;
END//
DELIMITER ;
CALL voc_cek_bootstrap();
DROP PROCEDURE voc_cek_bootstrap;

-- ---------------------------------------------------------------------
-- 2) SEBELUM — potret keadaan, untuk dibandingkan nanti
-- ---------------------------------------------------------------------
SELECT Id, SiteId, TargetId, Name, Url,
       JSON_EXTRACT(Options, '$.mock')     AS mock,
       JSON_EXTRACT(Options, '$.api_mode') AS api_mode,
       JSON_EXTRACT(Options, '$.provisioning.status') AS provisioning
  FROM Connection
 WHERE SiteId = @site AND ProviderId = 'PVD99'
 ORDER BY Id;

-- ---------------------------------------------------------------------
-- 3) HIDUPKAN
-- ---------------------------------------------------------------------
START TRANSACTION;

-- JSON_MERGE_PATCH, bukan JSON_OBJECT penuh: kunci lain di Options
-- (location, onebox_location_id, page_size, max_pages) HARUS selamat.
-- Menimpanya dengan objek baru akan membuang metadata cabang, dan layar
-- Lokasi lalu menampilkan Place ID kosong.
UPDATE Connection
   SET Url = @crawler_url,
       Options = JSON_MERGE_PATCH(
         COALESCE(Options, '{}'),
         JSON_OBJECT(
           'mock',          FALSE,
           'api_mode',      'service',
           'service_token', @token,
           'company_id',    @company)),
       Enabled    = 1,
       StatusId   = 'CNS1',
       ModifyDate = NOW()
 WHERE SiteId = @site AND ProviderId = 'PVD99';

-- mock_file dibuang: ia menunjuk /tmp/voc_reviews_sample.json yang tidak ada
-- di staging. Membiarkannya tidak merusak selama mock=false, tetapi ia
-- menyesatkan siapa pun yang membaca Options ini enam bulan lagi.
UPDATE Connection
   SET Options = JSON_REMOVE(Options, '$.mock_file')
 WHERE SiteId = @site AND ProviderId = 'PVD99'
   AND JSON_EXTRACT(Options, '$.mock_file') IS NOT NULL;

-- TargetId dikosongkan dan provisioning dikembalikan ke 'pending'.
--
-- Ini BUKAN kehati-hatian berlebihan. TargetId '4' dan '2' adalah id lokasi
-- milik Crawler DEV, dan seed menandainya 'synced' seolah lokasinya sudah
-- terdaftar. Kalau staging diarahkan ke server Crawler yang berbeda, kedua id
-- itu menunjuk entah apa — atau tidak menunjuk apa pun. Menariknya dalam
-- keadaan itu tidak menghasilkan error; ia menghasilkan review milik lokasi
-- lain, atau kosong tanpa sebab yang terlihat.
--
-- 'pending' memaksa provisioning diulang terhadap server yang benar-benar
-- dipakai, dan itulah yang mengisi TargetId dengan id yang sah.
UPDATE Connection
   SET TargetId = '',
       Options = JSON_MERGE_PATCH(
         COALESCE(Options, '{}'),
         JSON_OBJECT('provisioning', JSON_OBJECT(
           'status', 'pending',
           'reason', 'Server Crawler berubah; TargetId lama milik Crawler dev'))),
       ModifyDate = NOW()
 WHERE SiteId = @site AND ProviderId = 'PVD99';

-- ---------------------------------------------------------------------
-- 4) SESUDAH — baca sebelum COMMIT
-- ---------------------------------------------------------------------
SELECT Id, SiteId, TargetId, Name, Url,
       JSON_EXTRACT(Options, '$.mock')     AS mock,
       JSON_EXTRACT(Options, '$.api_mode') AS api_mode,
       CASE WHEN JSON_EXTRACT(Options, '$.service_token') IS NULL
            THEN 'KOSONG' ELSE 'terisi' END AS token,
       JSON_EXTRACT(Options, '$.company_id') AS company_id,
       JSON_EXTRACT(Options, '$.provisioning.status') AS provisioning,
       JSON_UNQUOTE(JSON_EXTRACT(Options, '$.location.branch_name'))       AS cabang,
       JSON_UNQUOTE(JSON_EXTRACT(Options, '$.location.external_place_id')) AS place_id
  FROM Connection
 WHERE SiteId = @site AND ProviderId = 'PVD99'
 ORDER BY Id;

-- Yang HARUS terlihat di tiap baris:
--   Url        terisi
--   mock       false
--   api_mode   "service"
--   token      terisi
--   cabang & place_id  masih ada  <- bukti JSON_MERGE_PATCH tidak membuang apa pun
--
-- Kalau semuanya benar:   COMMIT;
-- Kalau ada yang meleset: ROLLBACK;

-- COMMIT;

-- =====================================================================
-- LANGKAH BERIKUTNYA (di shell, bukan SQL)
--
-- 1) Buktikan kredensialnya milik company yang benar — SEBELUM menarik apa
--    pun. Kalau meleset, sync ditolak; itu hasil yang bagus. Yang berbahaya
--    adalah kalau ia diterima oleh company yang salah.
--
--      docker exec <container-staging> php app/bootstrap.php \
--        voice_of_customer_system whoami 985
--
-- 2) Provisioning ulang supaya TargetId terisi dari server yang benar.
--
-- 3) Baru setelah itu, tambah cabang lewat UI Lokasi. Alert
--    "Jalankan voc_setup_all.sql dulu" tidak akan muncul lagi, karena baris
--    985/986 kini lolos vocCredentialTemplate().
-- =====================================================================
