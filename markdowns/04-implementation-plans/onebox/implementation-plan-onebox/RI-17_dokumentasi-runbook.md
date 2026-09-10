# RI-17 — Dokumentasi + Runbook (≤2 MD)

## 1. Tujuan & DoD
Orang lain (dev lain / ops / lead) bisa memahami, menjalankan, dan mengoperasikan integrasi tanpa nanya lu. **Selesai kalau:** dua dokumen di bawah selesai dan dicoba diikuti orang lain (atau minimal dibaca ulang lu sendiri besoknya tanpa bingung).

## 2. Deliverable
1. **`docs/voiceofcustomer-integration.md`** (di repo OneBox, ikut MR): arsitektur ringkas (tempel diagram drawio yang sudah ada), field mapping final (link RI-01), keputusan D1–D8 + status ratifikasi, konfigurasi per-env (nama key, TANPA nilai), cara menjalankan sync manual, jadwal, lokasi log.
2. **Runbook ops** (bagian kedua dokumen yang sama): gejala umum → diagnosis → tindakan. Minimal: "dashboard kosong", "sync gagal 401", "VoC down", "duplikat muncul" (harusnya mustahil — kalau terjadi, cek RemoteId), "cara full resync" (hapus cursor Redis), "cara menonaktifkan integrasi cepat" (Enabled=0 di Connection / feature flag config).

## 3. Langkah
Kompilasi dari Temuan & Deviasi semua RI (itulah kenapa tiap plan punya §7 — jangan skip mengisinya). Tempel command & SQL yang benar-benar terpakai, bukan yang teoretis.

## 9. Estimasi (2 MD)
Hari 1: tulis. Hari 2: uji-ikuti + rapikan.
