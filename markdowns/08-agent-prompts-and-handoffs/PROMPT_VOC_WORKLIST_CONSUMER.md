# PROMPT untuk Codex — Consumer Worklist di Voice of Customer System (ADR-0003, increment a)

> Handoff dari agen OneBox (Claude Code) ke Codex (owner Voice of Customer System).
> Otoritas: [ADR-0003](../02-meetings-and-decisions/adr/ADR-0003-crawl-execution-pull-queue.md). Baca itu + [MUST_READ](../00-start-here/MUST_READ.md) dulu.
> Tandai setiap klaim: **[verified] / [assumption] / [blocked]**.

$ONEBOX =   │ https://localhost/feature/DNGO19-3346

akun = voc.dev@onebox.local / voc12345,

## Peran & konteks

OneBox kini **System of Record** untuk master data (ADR-0001). Mekanisme provisioning
dibalik dari **push sinkron → pull worklist** (ADR-0003). Sisi OneBox **sudah selesai**:

- Endpoint worklist sudah dibuat: `GET /api/VocWorklist` (read-only, JWT).
- Push sinkron di jalur simpan OneBox sudah dilepas — simpan lokasi/kompetitor jadi commit lokal instan.

**Tugasmu:** bangun **consumer** di Voice of Customer System yang MENARIK worklist itu
dan me-refresh tabel crawl-target (Location/Competitor) VoC sebagai **cache**. Ini
menggantikan pembuatan lokasi manual di VoC.

Voice of Customer System = crawler headless. Location/Competitor di VoC **bukan master data**
lagi — hanya "crawl target registry" turunan yang **hanya boleh ditulis oleh sync dari OneBox**
(ADR-0001 §Reframe). Review + analysis tetap disimpan VoC sebagai cache (jangan disentuh sync ini).

---

## Kontrak OneBox (sudah live setelah OneBox deploy) — [verified] dari kode OneBox

### 1. Login → dapat JWT

```
POST {ONEBOX_BASE_URL}/api/Authenticate
Content-Type: application/x-www-form-urlencoded   (atau query/JSON — controller pakai request->get)

email=<service-account-email>&password=<password>&siteId=<site-id-onebox>

→ 200 { "response_status":"success", "issued_at":..., "valid_until":..., "token":"<JWT>" }
```

- **Kirim `siteId` eksplisit.** Kalau kosong dan akun punya >1 site, response malah berisi
  daftar site tanpa token. Service account VoC harus terikat ke satu site (Hermina).
- JWT membawa klaim `sid` (site). Endpoint worklist otomatis scoped ke `sid` itu.

### 2. Pull worklist

```
GET {ONEBOX_BASE_URL}/api/VocWorklist
Authorization: Bearer <JWT>

→ 200
{
  "data": [
    {
      "onebox_connection_id": 1039,
      "onebox_location_id": 12,
      "kind": "location",              // "location" | "competitor"
      "external_place_id": "ChIJ...",  // KUNCI STABIL lintas sistem — dedup pakai ini
      "branch_name": "Hermina Depok",
      "hospital_name": "Hermina",
      "city": "Depok",
      "target_review_count": 100,
      "google_maps_url": "",
      "active": true,                  // flag bisnis (Enabled) → is_active crawler
      "crawl_enabled": true,           // StatusId CNS1 → boleh masuk penjadwal; kompetitor false (CNS3)
      "ingest_reviews": true,          // hanya lokasi; kompetitor false (review-nya TIDAK jadi tiket OneBox)
      "mock": false,                   // koneksi dev dummy — boleh skip crawl asli

      // Konfigurasi AI milik OneBox (DNGO19-3388). OneBox yang MEMILIH model;
      // crawler menyimpannya di kolom locations.ai_* dan memakainya saat analisa.
      // Ketiganya OPSIONAL: baris worklist dari OneBox versi lama tidak
      // membawanya, dan ketiadaannya TIDAK boleh dibaca sebagai "matikan AI".
      "ai_enabled": true,              // sakelar per koneksi; default true bila tidak ada
      "ai_model": "llama3.2-1b",       // null/"" = OneBox tidak memilih → pakai default crawler
      "ai_output_schema_version": "v1",// bentuk hasil analisa yang diharapkan OneBox

      "voc_target_id": null,           // id lama di VoC bila pernah di-provision (transisi)
      "provisioning_status": "pending",
      "updated_at": "2026-07-23 10:00:00"
    }
  ],
  "meta": { "site_id": 169, "count": 1, "api_version": "v1", "generated_at": "..." }
}
```

Tenant SELALU dari JWT, tidak pernah dari request (prinsip sama dengan integration contract VoC).

---

## Yang harus dibangun di Voice of Customer System

### A. Client outbound ke OneBox — **BARU**
VoC belum pernah memanggil OneBox (selama ini VoC cuma provider). Buat client (httpx) yang:
- login (cache JWT sampai `valid_until`, refresh saat mau expired/401),
- `GET /api/VocWorklist`,
- timeout + retry backoff untuk 5xx/timeout (jangan retry 401/403),
- **tidak pernah** menyimpan/menuliskan credential ke repo atau log.

### B. Service sync worklist → cache — **BARU**
Untuk tiap item worklist, **upsert** ke tabel VoC dengan kunci **`external_place_id`**:
- `kind == "location"` → tabel Location. `kind == "competitor"` → tabel Competitor.
- Map field: `branch_name`, `hospital_name`, `city`, `target_review_count`, `google_maps_url`,
  `is_active = active`. Simpan juga `onebox_location_id` & `onebox_connection_id` untuk balik-map.
- **Idempotent:** jalan dua kali = hasil sama.
- **Jangan sentuh** review cache, analysis, atau crawl cursor milik target saat update metadata.
- **Rekonsiliasi:** target yang HILANG dari worklist → tandai **nonaktif** (`is_active=false`),
  JANGAN hard-delete (hindari kehilangan cache review + hindari race). ADR-0003 §Risiko.
- Hormati `mock` (boleh skip crawl asli) dan `ingest_reviews`/`crawl_enabled` (kompetitor:
  simpan sebagai target tapi jangan pernah dorong review-nya ke jalur integration reviews OneBox).

### C. Config — **BARU, jangan hardcode**
`ONEBOX_BASE_URL`, `ONEBOX_SVC_EMAIL`, `ONEBOX_SVC_PASSWORD`, `ONEBOX_SITE_ID` dari env/config
(pola `app/config.py`). Jangan commit nilainya.

### D. Trigger
Pull worklist **di awal tiap run crawl** (sebelum menguras antrean crawl), plus command manual
(CLI) untuk refresh on-demand. Jangan bikin scheduler window kedua — owner scheduler tetap OneBox
(RI-08). Ini murni refresh cache.

### E. Ketahanan
Kalau OneBox tak terjangkau saat pull: **pakai cache worklist terakhir**, jangan kosongkan/rusak
cache. Log warning + umur cache. (ADR-0003 §Risiko — otonomi crawler terjaga.)

---

## Verifikasi dulu sebelum coding (tandai hasilnya)

1. **[assumption→verify]** Tabel Location VoC punya `external_place_id` dan bisa dijadikan kunci
   unik per company. Cek `app/db/models.py`. Kalau belum unik, tentukan strategi upsert.
2. **[assumption→verify]** Mapping tenant: satu service account OneBox (satu `siteId`) ⇄ satu
   `company_id` VoC. Konfirmasi cara memetakannya (config eksplisit lebih aman daripada nebak).
3. **[verify]** Network VoC→OneBox terbuka (lihat `NETWORK_WIREGUARD_CORS_ONEBOX.md`).

## Definition of Done

- `GET /api/VocWorklist` ditarik, di-parse, dan tercermin ke Location/Competitor VoC (idempotent).
- Tambah lokasi di OneBox → setelah sync, target muncul/terupdate di VoC tanpa langkah manual.
- Nonaktifkan/hapus di OneBox → target ditandai nonaktif di VoC (bukan dihapus keras).
- Kompetitor tersimpan sebagai target tapi review-nya tidak pernah masuk jalur integration reviews.
- OneBox down saat pull → crawl tetap jalan dari cache terakhir.
- Tidak ada credential ter-hardcode / ter-commit / ter-log.

## Setelah consumer live (koordinasi dengan agen OneBox)
Jembatan transisi di OneBox (tombol Sinkronkan/resync + push di toggle) baru boleh dihapus
SETELAH consumer ini terbukti jalan. Kabari agen OneBox untuk menuntaskan increment (a).

---

## Catatan lintas: sinkronisasi review yang SUDAH ADA di crawler
Di luar scope prompt ini (itu jalur pull review OneBox→VoC yang sudah ada), tapi relevan:
review lama tidak perlu re-scrape — VoC menyimpannya sebagai cache. Saat lokasi baru dikenal
lewat worklist dan `external_place_id`-nya cocok dengan yang pernah di-crawl VoC, OneBox akan
menariknya lewat `GET /api/integration/v1/reviews?location_id=..&updated_since=<jauh>` (backfill
bertarget) lalu delta. Pastikan **jangan menduplikasi** target saat place id cocok — reuse row
lama by `external_place_id`.
