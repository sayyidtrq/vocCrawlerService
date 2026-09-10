# RI-16 — Integration Test + Verifikasi Staging (≤3 MD)

## 1. Tujuan & DoD
Alur end-to-end terbukti di environment mendekati nyata. **Selesai kalau:** checklist E2E hijau di dev + staging (kalau diizinkan deploy staging), dan hasil dicatat sebagai bukti untuk MR.

## 2. Prasyarat
Semua task MVP (RI-01→12, RI-15). Koordinasi deploy staging dengan tim (jangan deploy sendiri tanpa izin).

## 3. Checklist E2E (dev)
1. VoC crawl lokasi baru → analysis jalan → `updated_at` bergerak.
2. Sync terjadwal → Ticket baru masuk ≤1 interval; rerun → 0 duplikat.
3. List → detail → assign → resolve → dashboard angka berubah konsisten.
4. Multi-tenant: site kedua (dummy) tanpa config VoC → tidak ada data VOC sama sekali.
5. Failure drill: VoC down 1 siklus → recover otomatis; log ringkasan akurat.
6. Keamanan cepat: IDOR detail (RI-11), XSS teks review (RI-10), tidak ada secret di log/diff (`git diff` bersih dari credential, `.env*`/config lokal tidak ter-stage).
7. PHPUnit/Behat existing masih hijau (`test.sh` / cara tim) — pastikan tidak meregresi modul lain `[assumption cara run — tanya tim]`.

## 4. Staging
Ikuti pipeline tim (Jenkins). Ulangi checklist inti (2,3,4,6) di staging dengan kredensial staging Lisa.

## 6. Risiko
Data staging bukan milik kita sendiri — koordinasikan sebelum menulis data tes; bersihkan sesudahnya.

## 9. Estimasi (3 MD)
Hari 1: checklist dev penuh. Hari 2: perbaikan temuan. Hari 3: staging + catat bukti.
