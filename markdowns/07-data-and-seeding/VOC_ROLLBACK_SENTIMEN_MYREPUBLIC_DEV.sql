-- =====================================================================
--  ROLLBACK patch sentimen & kategori MyRepublic (2026-09-09)
--
--  Mengembalikan MessageContent.Meta persis seperti sebelum patch, dibaca
--  dari tabel cadangan yang dibuat BLOK 1. Tidak menebak apa pun: yang
--  ditulis kembali adalah teks Meta yang asli, bukan hasil menghapus field
--  satu per satu -- menghapus field akan meninggalkan bekas kalau ternyata
--  ada field lain yang ikut berubah.
-- =====================================================================

START TRANSACTION;

-- Berapa yang akan dipulihkan.
SELECT COUNT(*) AS akan_dipulihkan FROM VocMetaBackupMyrep20260909;

UPDATE MessageContent mc
  JOIN VocMetaBackupMyrep20260909 b ON b.Id = mc.Id
   SET mc.Meta = b.MetaLama;

-- Tidak boleh ada sisa penanda patch.
SELECT COUNT(*) AS sisa_penanda
  FROM MessageContent mc
  JOIN VocMetaBackupMyrep20260909 b ON b.Id = mc.Id
 WHERE JSON_VALID(mc.Meta)
   AND JSON_UNQUOTE(JSON_EXTRACT(mc.Meta,'$.patch_batch')) = 'myrep-demo-2026-09-09';

COMMIT;

-- Tabel cadangan sengaja TIDAK ikut dihapus. Menghapusnya membuat rollback
-- kedua mustahil, dan biayanya hanya satu tabel kecil.
-- DROP TABLE VocMetaBackupMyrep20260909;
