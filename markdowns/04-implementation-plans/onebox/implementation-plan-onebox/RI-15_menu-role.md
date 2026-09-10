# RI-15 — Registrasi Menu + Role Permission (≤2 MD)

> Struktur terverifikasi: `Menu` (Id, TypeId, NavigateUrl, ParentId, Priority, Visible, Enabled, Level, ...) + `RoleMenu` (RoleId, MenuId) [verified dari models]. Contoh nyata: `manage_menu.sql` di root monorepo + `app/migrations/1.30.0/Menu.php`.

## 1. Tujuan & DoD
Menu "VOC / Review" muncul di sidebar untuk role yang berhak (mengarah ke list/dashboard RI-10/12); role lain tidak melihatnya. **Selesai kalau:** login per-role membuktikan visibilitas benar.

## 2. Prasyarat
RI-10 (URL tujuan ada). Role target: cek role yang dipakai staging (Pimpinan Pusat / Reviewer / Kontributor).

## 3. Langkah
1. **Contek row menu Mediamonitoring existing:** `SELECT * FROM Menu WHERE NavigateUrl LIKE '%Mediamonitoring%';` → pahami nilai TypeId/ParentId/Level/format Id `[assumption→verifikasi — jangan insert sebelum lihat contoh]`. Bandingkan juga dengan `manage_menu.sql` dan migration `1.30.0/Menu.php`.
2. Insert row `Menu` baru (submenu di bawah parent Mediamonitoring atau parent VOC sendiri — ikuti struktur existing) + `RoleMenu` untuk role target.
3. Cek apakah menu di-cache (Redis) — kalau tidak muncul setelah insert, cari mekanisme clear cache menu (`grep -rn "menu" app/library/*Cache* -il`).
4. Simpan SQL final sebagai artefak deploy (nanti masuk migration/manage_menu sesuai konvensi tim — tanya lead saat MR).

## 5. Verifikasi
Login 3 role → menu tampil hanya untuk yang di-map; klik → halaman benar; direct URL oleh role tanpa menu → idealnya tetap dibatasi permission action (paduan dengan RI-14 langkah 4).

## 6. Risiko
Menu tampil ≠ authz — jangan andalkan sidebar sebagai satu-satunya pagar; server-side permission tetap dari `getActionRolePermission`.

## 9. Estimasi (2 MD)
Hari 1: contek + insert + cache. Hari 2: verifikasi 3 role + artefak SQL.
