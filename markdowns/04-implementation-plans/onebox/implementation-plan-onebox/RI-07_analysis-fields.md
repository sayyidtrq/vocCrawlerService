# RI-07 — Field Analisa Ekstra (≤3 MD)

> Keputusan terkait: D4, D7, D8. Sebagian dieksekusi di RI-05 (Description/Solution/Meta); task ini menyelesaikan `issue_category` + memastikan semua field analisa query-able sesuai kebutuhan dashboard RI-12.

## 1. Tujuan & Definition of Done
Semua output AI VoC punya rumah di OneBox dan **bisa diagregasi dashboard**: sentiment ✅(kolom), urgency ✅(PriorityId), summary/recommended_action ✅(Description/Solution), `issue_category` → `CategoryId` (D7), sisanya di Meta.
**Selesai kalau:** query `GROUP BY t.CategoryId` dan `GROUP BY t.PriorityId` atas ticket review menghasilkan breakdown yang benar.

## 2. Prasyarat & Dependency
RI-05 jalan. D7 ter-ratifikasi (paling mungkin dioverride lead — kerjakan terakhir di antara task ingest).

## 3. File Target
| File | Status |
|---|---|
| Master `Category` seed per site (SQL) | [baru — dev dulu] |
| `onecloud/app/tasks/VoiceOfCustomerSystemTask.php` | [ubah] — map issue_category → CategoryId |

## 4. Langkah Implementasi
1. **Verifikasi model Category** `[assumption]`: `ls app/models | grep -i categ` + `setSource()` + bagaimana `Ticket.CategoryId` dipakai Mediamonitoring (`grep -n "CategoryId" MediamonitoringController.php | head`). Kalau ternyata Mediamonitoring pakai mekanisme lain (mis. `Reference`), ikuti itu — catat di Temuan.
2. **Kumpulkan daftar nilai `issue_category`** dari VoC: `SELECT DISTINCT issue_category FROM review_analysis;` (SQLite/PG sisi VoC) — set-nya kecil (waktu_tunggu, pelayanan, fasilitas, ...).
3. **Seed Category per site** + tabel translasi di config (`categoryMap: ['waktu_tunggu' => <CategoryId>, ...]`) — konsisten pola `locationMap`.
4. **Update task:** isi `Ticket.CategoryId` via map; unmapped → null + warning.
5. **Backfill** ticket review yang sudah terlanjur masuk: script kecil sekali-jalan (UPDATE via join Meta) — atau re-ingest DB dev (lebih murah: hapus & sync ulang, idempotent).

## 5. Cara Verifikasi
```sql
SELECT t.CategoryId, COUNT(*) FROM Ticket t JOIN Message m ON m.Id=t.MessageId
WHERE m.ObjectName='Review' GROUP BY t.CategoryId;   -- breakdown masuk akal, null sedikit
```

## 6. Risiko & Rollback
Kategori AI bisa bertambah nilai baru seiring waktu → unmapped; mitigasi: warning log + review berkala. Rollback: set CategoryId null.

## 7. Temuan & Deviasi (eksekusi 2026-07-15)

1. **SELESAI** — implementasi di `VoiceOfCustomerSystemProvider::applyAnalysis()` (bukan Task, sesuai D9):
   - Resolusi kategori: `resolveCategory(slug)` — prioritas `Options.category_map` override, fallback lookup **`Category.Remarks = slug` per SiteId** (+cache per run). Unmapped → warning + CategoryId null.
   - **Kenapa Remarks, bukan Code:** `Category.Code` max **15 char**, slug terpanjang `staff_communication` = 19 char. Slug enum disimpan utuh di `Remarks`.
2. **Enum kategori VoC SUDAH terkunci di kode** (`app/services/analysis_service.py: ALLOWED_CATEGORIES`, 18 nilai, fallback `other`) — gap "minta Codex kunci enum" sudah close by design.
3. **Master Category (verified):** tabel `Category`, site-scoped (`SiteId`), dropdown Mediamonitoring = `Category WHERE SiteId AND Enabled=1` tanpa filter TypeId (MediamonitoringController:6897). Seed pakai `TypeId='TC1'` (CategoryType Default).
4. **Seed dev site 169:** 18 row Category Id **1054–1071** (Description Indonesia, Remarks=slug enum). SQL: pola lihat commit / `seed_ri07_category.sql`.
5. **Hasil verifikasi:** 15 ticket ter-backfill CategoryId; `GROUP BY t.CategoryId` → "Pelayanan Dokter" 15; `GROUP BY t.PriorityId` → TP1=11, TP2=2, TP3=2 ✓ (DoD terpenuhi).
6. ⚠️ **Handoff Codex — kualitas analisa:** SEMUA 74 row `review_analysis` di VoC bernilai `issue_category='doctor_service'` (termasuk review soal farmasi lama & BPJS self-service). Indikasi prompt AI kurang diskriminatif — perlu dicek sebelum dashboard kategori dipakai beneran.
7. Backfill ticket lama tidak butuh script terpisah — `applyAnalysis()` idempotent dan mengisi CategoryId/LocationId yang masih kosong pada run berikutnya.

## 8. API Gap
- `GET /api/analysis/categories`: opsional, tidak urgent (enum sudah di kode VoC — OneBox seed manual dari daftar itu).
- **Baru (dari #6):** kualitas klasifikasi `issue_category` — semua data = `doctor_service`; minta Codex evaluasi prompt/model (qwen2.5:7b) sebelum demo dashboard.

## 9. Estimasi (3 MD)
Hari 1: verifikasi Category + kumpulkan nilai. Hari 2: seed + map + update task. Hari 3: backfill + verifikasi agregasi.
