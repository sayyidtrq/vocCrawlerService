# RI-13 — Poles Visual vs Benchmark Next.js (≤3 MD)

## 1. Tujuan & DoD
Tampilan list/detail/dashboard VOC "11/12" dengan benchmark FE `hermina-crawler-fe`, **dalam batas** template & kelas CSS Onebox. **Selesai kalau:** side-by-side screenshot direview user & di-ACC.

## 2. Prasyarat
RI-10/11/12 fungsional. Ini task terakhir sebelum demo — jangan dikerjakan lebih awal.

## 3. Langkah
1. Screenshot tiap layar FE benchmark → daftar delta (warna badge, spacing, ikon, tipografi, susunan panel).
2. Terapkan delta yang bisa dicapai dengan kelas existing + CSS kecil ter-scope (`.voc-*` prefix di view volt — jangan sentuh `style.css` global; hormati `PrimaryColor` per-site dari `getSetting('PrimaryColor')` [verified dipakai Mediamonitoring line 47]).
3. Yang butuh komponen baru besar → catat sebagai backlog, bukan dikejar.

## 6. Risiko
Over-styling merusak konsistensi produk — batas keras: tidak menyentuh file CSS global, tidak import font/lib baru.

## 9. Estimasi (3 MD)
Hari 1: audit delta. Hari 2: terapkan. Hari 3: side-by-side + ACC.
