-- =====================================================================
--  PATCH SENTIMEN & KATEGORI ULASAN MYREPUBLIC  --  DB dev onecloud_rel
--  Dibuat 2026-09-09 untuk kebutuhan demo dashboard VoC.
--
--  MENGAPA PERLU
--  126 ulasan di 10 lokasi MyRepublic (Location.Id 1062-1071) masuk dengan
--  meta.analysis_status = 'pending': ai_sentiment kosong, issue_category
--  kosong. Akibatnya dua kartu di /voc/dashboard tidak punya bahan sama
--  sekali -- "Review Negatif Terbaru" hanya diisi review ber-sentimen
--  'negative', dan "TOP ISSUE" hanya menghitung review yang punya kategori.
--
--  APA YANG DISENTUH
--  HANYA kolom MessageContent.Meta pada 126 baris yang Id-nya tertulis di
--  bawah. Tidak ada baris dibuat, tidak ada baris dihapus, tabel Ticket,
--  Message, Location, dan Connection tidak disentuh sama sekali.
--
--  DUA JALUR, SENGAJA DIBEDAKAN
--    41 ulasan BERTEKS      -> meta.ai_sentiment + meta.issue_category,
--                              analyzed = true, analysis_status='completed'.
--                              Layar Ulasan akan menandainya bersumber AI.
--    85 ulasan BINTANG SAJA -> tidak ada teks yang bisa dibaca. Sentimennya
--                              masuk ke meta.sentiment_native (layar menandai
--                              sumbernya 'rating', bukan AI), dan kategorinya
--                              DIIMPUTASI dari kategori dominan lokasinya
--                              sendiri, ditandai meta.category_source =
--                              'imputed_location' supaya jejaknya jelas.
--
--  CARA PAKAI
--  Jalankan seluruh berkas ini sekali di phpMyAdmin (database onecloud_rel).
--  BLOK 1 menyalin Meta lama ke tabel cadangan lebih dulu, jadi seluruh
--  perubahan bisa dibatalkan lewat berkas rollback yang menyertainya.
-- =====================================================================

START TRANSACTION;

-- ---------------------------------------------------------------------
-- BLOK 0  Pagar: berapa baris yang akan disentuh, dan adakah Meta rusak.
--
-- JSON_SET menolak bekerja pada teks yang bukan JSON sah, dan satu baris
-- rusak akan menggagalkan seluruh pernyataan. Jumlahnya diperiksa dulu
-- supaya kalau ada yang tidak beres, ketahuannya SEBELUM apa pun ditulis.
-- ---------------------------------------------------------------------
SELECT COUNT(*)                                        AS total_sasaran,
       SUM(JSON_VALID(Meta))                           AS meta_sah,
       SUM(NOT JSON_VALID(Meta))                       AS meta_rusak
  FROM MessageContent
 WHERE Id IN (
    132814, 132816, 132818, 132826, 132827, 132833, 132834, 132840, 132847, 132858, 132859, 132865,
    132867, 132869, 132874, 132880, 132882, 132883, 132886, 132888, 132889, 132899, 132907, 132908,
    132916, 132917, 132922, 132923, 132926, 132928, 132932, 132934, 132938, 132942, 132944, 132947,
    132954, 132956, 132966, 132974, 132976, 132979, 132980, 132981, 132988, 132997, 132998, 132999,
    133010, 133012, 133024, 133025, 133027, 133031, 133036, 133043, 133046, 133048, 133051, 133052,
    133053, 133064, 133076, 133079, 133082, 133085, 133088, 133089, 133091, 133092, 133093, 133094,
    133095, 133096, 133098, 133099, 133100, 133102, 133105, 133106, 133107, 133118, 133120, 133121,
    133122, 133123, 133128, 133130, 133131, 133132, 133137, 133138, 133140, 133141, 133142, 133145,
    133147, 133148, 133151, 133153, 133157, 133158, 133159, 133160, 133162, 133165, 133166, 133167,
    133168, 133169, 133171, 133172, 133174, 133186, 133192, 133214, 133219, 133228, 133231, 133238,
    133241, 133246, 133247, 133248, 133254, 133263
);

-- ---------------------------------------------------------------------
-- BLOK 1  Cadangan. Dijalankan SEBELUM satu pun UPDATE.
--
-- INSERT IGNORE, bukan INSERT: kalau berkas ini terlanjur dijalankan dua
-- kali, cadangan yang tersimpan tetap Meta ASLI dari jalan pertama, bukan
-- Meta yang sudah ter-patch. Tanpa itu, rollback justru mengembalikan
-- keadaan yang sudah salah.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS VocMetaBackupMyrep20260909 (
  Id       BIGINT       NOT NULL PRIMARY KEY,
  MetaLama LONGTEXT     NULL,
  SavedAt  DATETIME     NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO VocMetaBackupMyrep20260909 (Id, MetaLama, SavedAt)
SELECT Id, Meta, NOW()
  FROM MessageContent
 WHERE Id IN (
    132814, 132816, 132818, 132826, 132827, 132833, 132834, 132840, 132847, 132858, 132859, 132865,
    132867, 132869, 132874, 132880, 132882, 132883, 132886, 132888, 132889, 132899, 132907, 132908,
    132916, 132917, 132922, 132923, 132926, 132928, 132932, 132934, 132938, 132942, 132944, 132947,
    132954, 132956, 132966, 132974, 132976, 132979, 132980, 132981, 132988, 132997, 132998, 132999,
    133010, 133012, 133024, 133025, 133027, 133031, 133036, 133043, 133046, 133048, 133051, 133052,
    133053, 133064, 133076, 133079, 133082, 133085, 133088, 133089, 133091, 133092, 133093, 133094,
    133095, 133096, 133098, 133099, 133100, 133102, 133105, 133106, 133107, 133118, 133120, 133121,
    133122, 133123, 133128, 133130, 133131, 133132, 133137, 133138, 133140, 133141, 133142, 133145,
    133147, 133148, 133151, 133153, 133157, 133158, 133159, 133160, 133162, 133165, 133166, 133167,
    133168, 133169, 133171, 133172, 133174, 133186, 133192, 133214, 133219, 133228, 133231, 133238,
    133241, 133246, 133247, 133248, 133254, 133263
);

-- ---------------------------------------------------------------------
-- BLOK 2  41 ulasan BERTEKS: hasil pembacaan isi ulasan.
--
-- Sentimen diputus oleh BINTANG, bukan oleh kamus. Mesin native OneBox
-- sudah terbukti membaca keluhan yang asing bagi kamusnya sebagai positif
-- (lihat komentar reviewSentiment di VocController), jadi teks di sini
-- hanya dipakai untuk menentukan KATEGORI keluhannya.
-- ---------------------------------------------------------------------

-- negative / billing  (2 ulasan)
-- contoh: Myrepublic sangat sangat mengecewakan. Paket yg dipasang paket yg salah. Saya minta dire
UPDATE MessageContent
   SET Meta = JSON_SET(Meta,
         '$.ai_sentiment',    'negative',
         '$.issue_category',  'billing',
         '$.analyzed',        CAST('true' AS JSON),
         '$.analysis_status', 'completed',
         '$.analyzed_at',     '2026-09-09 00:00:00',
         '$.patch_batch',     'myrep-demo-2026-09-09')
 WHERE JSON_VALID(Meta)
   AND Id IN (
    132833, 133012
);

-- negative / customer_service  (4 ulasan)
-- contoh: Pikir 1000 kali sebelum pasang MyRepublic kalau gak mau kerjaan Anda berantakan. Pelayan
UPDATE MessageContent
   SET Meta = JSON_SET(Meta,
         '$.ai_sentiment',    'negative',
         '$.issue_category',  'customer_service',
         '$.analyzed',        CAST('true' AS JSON),
         '$.analysis_status', 'completed',
         '$.analyzed_at',     '2026-09-09 00:00:00',
         '$.patch_batch',     'myrep-demo-2026-09-09')
 WHERE JSON_VALID(Meta)
   AND Id IN (
    132867, 132869, 132954, 133089
);

-- negative / gangguan_jaringan  (13 ulasan)
-- contoh: Kok selalu putus jaringan? 8 jam perbaikan lama banngett Sudah beberapa kali seperti ini
UPDATE MessageContent
   SET Meta = JSON_SET(Meta,
         '$.ai_sentiment',    'negative',
         '$.issue_category',  'gangguan_jaringan',
         '$.analyzed',        CAST('true' AS JSON),
         '$.analysis_status', 'completed',
         '$.analyzed_at',     '2026-09-09 00:00:00',
         '$.patch_batch',     'myrep-demo-2026-09-09')
 WHERE JSON_VALID(Meta)
   AND Id IN (
    132814, 132826, 132880, 132882, 132907, 132979, 132980, 133079, 133098, 133102, 133186, 133238,
    133246
);

-- negative / other  (2 ulasan)
-- contoh: DENGAN ALASAN APAPUN JANGAN MAU GUNAKAN JASA MYREPUBLIC !!! PERCAYALAH !
UPDATE MessageContent
   SET Meta = JSON_SET(Meta,
         '$.ai_sentiment',    'negative',
         '$.issue_category',  'other',
         '$.analyzed',        CAST('true' AS JSON),
         '$.analysis_status', 'completed',
         '$.analyzed_at',     '2026-09-09 00:00:00',
         '$.patch_batch',     'myrep-demo-2026-09-09')
 WHERE JSON_VALID(Meta)
   AND Id IN (
    133010, 133082
);

-- negative / pemasangan_baru  (2 ulasan)
-- contoh: Kecewa bgt sama pelayanan MYREPUBLIC,sangat di sayang kan.bilang nya pemasangan cepat.su
UPDATE MessageContent
   SET Meta = JSON_SET(Meta,
         '$.ai_sentiment',    'negative',
         '$.issue_category',  'pemasangan_baru',
         '$.analyzed',        CAST('true' AS JSON),
         '$.analysis_status', 'completed',
         '$.analyzed_at',     '2026-09-09 00:00:00',
         '$.patch_batch',     'myrep-demo-2026-09-09')
 WHERE JSON_VALID(Meta)
   AND Id IN (
    132834, 132926
);

-- negative / penanganan_teknisi  (11 ulasan)
-- contoh: klo yg mau pasang myrepublik siap siap sabar yah karena sering eror, pelayanan teknisi k
UPDATE MessageContent
   SET Meta = JSON_SET(Meta,
         '$.ai_sentiment',    'negative',
         '$.issue_category',  'penanganan_teknisi',
         '$.analyzed',        CAST('true' AS JSON),
         '$.analysis_status', 'completed',
         '$.analyzed_at',     '2026-09-09 00:00:00',
         '$.patch_batch',     'myrep-demo-2026-09-09')
 WHERE JSON_VALID(Meta)
   AND Id IN (
    132858, 132859, 132938, 133036, 133053, 133085, 133093, 133094, 133174, 133192, 133263
);

-- positive / general_praise  (7 ulasan)
-- contoh: Pesanan pasang baru cepat jaringan internet cepat joss MyRepublic
UPDATE MessageContent
   SET Meta = JSON_SET(Meta,
         '$.ai_sentiment',    'positive',
         '$.issue_category',  'general_praise',
         '$.analyzed',        CAST('true' AS JSON),
         '$.analysis_status', 'completed',
         '$.analyzed_at',     '2026-09-09 00:00:00',
         '$.patch_batch',     'myrep-demo-2026-09-09')
 WHERE JSON_VALID(Meta)
   AND Id IN (
    132874, 132916, 132922, 132928, 133100, 133171, 133214
);


-- ---------------------------------------------------------------------
-- BLOK 3  85 ulasan BINTANG SAJA: tidak ada teks untuk dibaca.
--
-- Sentimennya ditulis ke sentiment_native, BUKAN ai_sentiment, supaya layar
-- Ulasan tetap jujur menandai sumbernya sebagai bintang. analyzed sengaja
-- TIDAK disetel true di sini: tidak ada analisis isi yang pernah terjadi,
-- dan mengakuinya akan membuat KPI "Belum dianalisa" berbohong.
--
-- Kategorinya diimputasi dari kategori dominan lokasi itu sendiri, dihitung
-- HANYA dari ulasan berteks di lokasi yang sama. Alternatifnya membiarkan
-- kategori kosong, tetapi 85 ulasan tanpa kategori akan menumpuk di bucket
-- "Belum dikategorikan" dan bucket itu ikut bersaing menjadi "kategori
-- dengan keluhan tertinggi" -- menenggelamkan seluruh kategori riil.
-- Jejaknya ditinggalkan di meta.category_source.
-- ---------------------------------------------------------------------

-- negative / gangguan_jaringan  (25 ulasan) -- lokasi: MYREPUBLIC BRANCH BOGOR, MyRepublic Branch BSD, MyRepublic Branch Jakarta Barat, MyRepublic Branch Jakarta Selatan, MyRepublic Cabang Depok, MyRepubli
UPDATE MessageContent
   SET Meta = JSON_SET(Meta,
         '$.sentiment_native', 'negative',
         '$.issue_category',   'gangguan_jaringan',
         '$.category_source',  'imputed_location',
         '$.patch_batch',      'myrep-demo-2026-09-09')
 WHERE JSON_VALID(Meta)
   AND Id IN (
    132816, 132818, 132827, 132840, 132847, 132865, 132883, 132886, 132888, 132899, 132974, 132976,
    132981, 132988, 132997, 132998, 132999, 133076, 133092, 133095, 133105, 133128, 133130, 133131,
    133254
);

-- negative / pemasangan_baru  (5 ulasan) -- lokasi: MyRepublic Bekasi
UPDATE MessageContent
   SET Meta = JSON_SET(Meta,
         '$.sentiment_native', 'negative',
         '$.issue_category',   'pemasangan_baru',
         '$.category_source',  'imputed_location',
         '$.patch_batch',      'myrep-demo-2026-09-09')
 WHERE JSON_VALID(Meta)
   AND Id IN (
    132934, 132944, 132947, 132956, 132966
);

-- negative / penanganan_teknisi  (7 ulasan) -- lokasi: Galeri MyRepublic
UPDATE MessageContent
   SET Meta = JSON_SET(Meta,
         '$.sentiment_native', 'negative',
         '$.issue_category',   'penanganan_teknisi',
         '$.category_source',  'imputed_location',
         '$.patch_batch',      'myrep-demo-2026-09-09')
 WHERE JSON_VALID(Meta)
   AND Id IN (
    133024, 133025, 133027, 133043, 133048, 133052, 133064
);

-- positive / general_praise  (47 ulasan) -- lokasi: Galeri MyRepublic, MYREPUBLIC BRANCH BOGOR, MyRepublic Bekasi, MyRepublic Branch Jakarta Barat, MyRepublic Branch Jakarta Selatan, MyRepublic Cikeas, 
UPDATE MessageContent
   SET Meta = JSON_SET(Meta,
         '$.sentiment_native', 'positive',
         '$.issue_category',   'general_praise',
         '$.category_source',  'imputed_location',
         '$.patch_batch',      'myrep-demo-2026-09-09')
 WHERE JSON_VALID(Meta)
   AND Id IN (
    132889, 132908, 132917, 132923, 132932, 132942, 133031, 133046, 133051, 133088, 133091, 133096,
    133099, 133106, 133107, 133118, 133120, 133121, 133122, 133123, 133132, 133137, 133138, 133140,
    133141, 133142, 133145, 133147, 133148, 133151, 133153, 133157, 133158, 133159, 133160, 133162,
    133165, 133166, 133167, 133168, 133169, 133172, 133228, 133231, 133241, 133247, 133248
);


-- Sisanya: bintang 3 (netral). Tidak diberi kategori -- ulasan netral tanpa
-- teks tidak mengeluhkan apa pun, dan memberinya kategori keluhan hanya akan
-- menambah satu angka palsu ke Top Issue.
UPDATE MessageContent
   SET Meta = JSON_SET(Meta,
         '$.sentiment_native', 'neutral',
         '$.patch_batch',      'myrep-demo-2026-09-09')
 WHERE JSON_VALID(Meta)
   AND Id IN (
    133219
);



-- ---------------------------------------------------------------------
-- BLOK 4  Verifikasi. Dibaca SEBELUM COMMIT.
--
-- Rumusnya sengaja meniru reviewSentimentSql() dan reviewCategorySql() di
-- VocController persis, jadi yang terbaca di sini adalah yang akan dihitung
-- dashboard -- bukan perkiraan yang mirip.
-- ---------------------------------------------------------------------
SELECT COALESCE(
         NULLIF(JSON_UNQUOTE(JSON_EXTRACT(Meta,'$.ai_sentiment')), 'null'),
         NULLIF(JSON_UNQUOTE(JSON_EXTRACT(Meta,'$.sentiment_native')), 'null'),
         '(kosong)')                                   AS sentimen,
       COALESCE(
         NULLIF(JSON_UNQUOTE(JSON_EXTRACT(Meta,'$.issue_category')), 'null'),
         '(kosong)')                                   AS kategori,
       COUNT(*)                                        AS jumlah
  FROM MessageContent
 WHERE Id IN (
    132814, 132816, 132818, 132826, 132827, 132833, 132834, 132840, 132847, 132858, 132859, 132865,
    132867, 132869, 132874, 132880, 132882, 132883, 132886, 132888, 132889, 132899, 132907, 132908,
    132916, 132917, 132922, 132923, 132926, 132928, 132932, 132934, 132938, 132942, 132944, 132947,
    132954, 132956, 132966, 132974, 132976, 132979, 132980, 132981, 132988, 132997, 132998, 132999,
    133010, 133012, 133024, 133025, 133027, 133031, 133036, 133043, 133046, 133048, 133051, 133052,
    133053, 133064, 133076, 133079, 133082, 133085, 133088, 133089, 133091, 133092, 133093, 133094,
    133095, 133096, 133098, 133099, 133100, 133102, 133105, 133106, 133107, 133118, 133120, 133121,
    133122, 133123, 133128, 133130, 133131, 133132, 133137, 133138, 133140, 133141, 133142, 133145,
    133147, 133148, 133151, 133153, 133157, 133158, 133159, 133160, 133162, 133165, 133166, 133167,
    133168, 133169, 133171, 133172, 133174, 133186, 133192, 133214, 133219, 133228, 133231, 133238,
    133241, 133246, 133247, 133248, 133254, 133263
)
 GROUP BY sentimen, kategori
 ORDER BY sentimen, jumlah DESC;

-- Yang seharusnya terbaca pada baris NEGATIF:
--   negative / gangguan_jaringan    38
--   negative / penanganan_teknisi   18
--   negative / pemasangan_baru       7
--   negative / customer_service      4
--   negative / billing               2
--   negative / other                 2
--                                  ---
--                                   71  <- ini yang mengisi Top Issue
--   positive / general_praise       54
--   neutral  / (kosong)              1

COMMIT;

-- Kalau BLOK 4 tidak sesuai, jangan COMMIT -- jalankan ROLLBACK; lalu
-- pakai berkas rollback untuk mengembalikan Meta dari tabel cadangan.
