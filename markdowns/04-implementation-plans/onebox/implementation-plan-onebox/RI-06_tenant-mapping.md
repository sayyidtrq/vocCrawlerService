> ⚠️ **SUPERSEDED oleh `../../decisions/ADR-0001-ownership-inversion.md` (2026-07-21).**
> **JANGAN dipakai sebagai acuan kerja baru.** Plan ini mengasumsikan lokasi dikelola di VoC lalu dipetakan manual ke OneBox. Sekarang terbalik: **lokasi dikelola di OneBox**, dan OneBox auto-provisioning ke VoC lewat `POST /api/locations`. Ganti dengan task CRUD Location + auto-provisioning. Disimpan sebagai histori.

# RI-06 — Mapping Site ↔ Lokasi (≤3 MD)

> Keputusan terkait: D2, D6. Sebagian besar sudah "terserap" ke RI-04/05 — task ini merapikan & memvalidasi.
> **Status: SELESAI 2026-07-15** — lihat §7. Bentuk implementasi menyesuaikan D9 (config di `Connection`, bukan `development.php`).

## 1. Tujuan & Definition of Done
Review dari lokasi VoC tertentu mendarat di `SiteId` + `LocationId` OneBox yang benar.
**Selesai kalau:** ingest 2 lokasi VoC berbeda → Ticket-nya beda `LocationId`; site lain tidak kecipratan data.

## 2. Prasyarat & Dependency
RI-05 berjalan. Keputusan D6 (config-based MVP).

## 3. File Target
| File | Status |
|---|---|
| `onecloud/app/config/development.php` section `voiceofcustomer` | [ubah] tambah `locationMap` |
| `onecloud/app/tasks/VoiceOfCustomerSystemTask.php` | [ubah] resolver |

## 4. Langkah Implementasi
1. **Struktur config (D6):**
   ```php
   'voiceofcustomer' => [
       ...,
       'siteId' => 1,                       // pilot
       'locationMap' => [                   // voc location_id => OneBox LocationId
           5 => 101,   // Hermina Depok  => LocationId site
           7 => 102,
       ],
       'defaultLocationId' => null,
   ],
   ```
2. **Resolver di task:** `mapLocation(int $vocLocId): ?int` — lookup `locationMap`, fallback `defaultLocationId` + log warning "unmapped location".
3. **Validasi master lokasi OneBox:** cek dulu bagaimana `LocationId` dipakai (`grep -n "LocationId" app/controllers/MediamonitoringController.php | head`) dan master lokasinya di mana (`app/models/Location*.php`?) — isi nilai map dengan Id yang beneran ada. `[assumption→verifikasi]`
4. **Filter sisi VoC:** panggil `getReviews(['location_id' => <vocLocId>])` per entry map — supaya hanya lokasi ter-mapping yang ditarik (hemat + aman).

## 5. Cara Verifikasi
```sql
SELECT t.LocationId, COUNT(*) FROM Ticket t JOIN Message m ON m.Id=t.MessageId
WHERE m.ObjectName='Review' GROUP BY t.LocationId;  -- sesuai map
SELECT COUNT(*) FROM Ticket WHERE SiteId <> <pilot> AND Id IN (SELECT ObjectId FROM Message WHERE ObjectName='Review'); -- HARUS 0
```

## 6. Risiko & Rollback
Unmapped location masuk tanpa lokasi → dashboard per-lokasi bolong; mitigasi: log warning + laporan jumlah unmapped di akhir sync. Rollback: revert config.

## 7. Temuan & Deviasi (eksekusi 2026-07-15)

1. **SELESAI** — bentuk implementasi ikut D9/K4, bukan config `development.php`:
   - **Topologi K4:** 1 `Connection` per lokasi VoC — `Connection.TargetId` = `location_id` VoC. `receive()` kirim param `location_id` ke API + guard sisi client (skip row di luar target; berlaku juga di mock mode yang tidak kenal param).
   - **Mapping lokasi (D6):** `Options.location_map` = `{"<voc_location_id>": <OneBox LocationId>}` — di-backfill ke `Ticket.LocationId` oleh `applyAnalysis()` (berlaku juga untuk review belum analyzed; hanya isi kalau `LocationId` masih kosong). Unmapped → warning + `LocationId` tetap null (fallback K6).
2. **Master `Location` OneBox GLOBAL — tidak punya `SiteId`** (kolom: Id, Description, City, koordinat). Mediamonitoring join `Location l ON l.Id = t.LocationId`. Konsekuensi multi-tenant: row Location bisa kebaca lintas site — bukan blocker MVP, tapi catat untuk review keamanan nanti.
3. **Seed dev:** Location `1703` = Hermina Depok, `1704` = HGA Depok. Connection `1039` → TargetId=4, map `{"4":1703}`; Connection `1040` (baru) → TargetId=2, map `{"2":1704}`.
4. **Hasil verifikasi (fixture 2 lokasi, 5+5 review):**
   - Conn 1039 → 10 ticket semua LocationId 1703; Conn 1040 → 5 ticket semua LocationId 1704 ✓ (DoD: lokasi beda → LocationId beda)
   - `SELECT COUNT(*) ... SiteId <> 169` → **0** (tidak ada leak lintas site) ✓
   - Filter TargetId: masing-masing connection skip 5 review lokasi lain ✓; dedup lintas-run tetap jalan ✓
5. Catatan verifikasi: query §5 pakai `m.ObjectName='Review'` — tidak berlaku (pipeline set `ObjectName='Ticket'`); filter yang benar: `m.ConnectionId IN (...)`.

## 8. API Gap
Kalau butuh daftar lokasi programatik: minta Codex expose `GET /api/locations` (gap kecil — endpoint `/api/locations` sebenarnya sudah ada di VoC, tinggal konfirmasi shape + auth service user).

## 9. Estimasi (3 MD)
Hari 1: struktur config + resolver. Hari 2: validasi master LocationId OneBox. Hari 3: test 2 lokasi + laporan unmapped.
