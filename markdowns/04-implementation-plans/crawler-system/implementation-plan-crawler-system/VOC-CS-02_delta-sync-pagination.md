# VOC-CS-02 - Delta Sync dan Pagination Deterministik (5 MD)

- Status plan: ready
- Owner: developer Crawler System
- Self-review: Codex
- Dependency: VOC-CS-01
- Mendukung OneBox: RI-05 dan RI-08

## 1. Tujuan

Menyediakan pull incremental yang lossless untuk review baru, perubahan review, dan analysis yang selesai belakangan. Offset pagination tidak dipakai pada route integrasi; route memakai snapshot boundary dan keyset cursor yang ditandatangani.

## 2. Definition of Done

- [ ] Review memiliki sync_updated_at non-null dan indexed per company.
- [ ] Menyimpan ReviewAnalysis menggerakkan Review.sync_updated_at dalam transaksi yang sama.
- [ ] Cursor stabil untuk timestamp sama, page kecil, dan concurrent insert.
- [ ] Cursor terikat tenant dan filter; tampering menghasilkan 400.
- [ ] Final page mengembalikan checkpoint_cursor untuk siklus berikutnya.
- [ ] Existing /api/reviews pagination tidak berubah.
- [ ] Alembic upgrade/downgrade lulus pada PostgreSQL disposable.

## 3. Kondisi Existing Terverifikasi

- [verified] Review.updated_at ada tetapi ReviewAnalysis hanya memiliki created_at.
- [verified] AnalysisService._store_analysis hanya insert ReviewAnalysis lalu commit.
- [verified] ReviewService.get_reviews memakai offset dan order review_time/id.
- [verified] latest_analysis_subquery memilih max analysis id per review.
- [verified] Tidak ada updated_since/cursor utility pada route review.

## 4. Scope

In scope: watermark, migration, cursor codec, query integration, analysis propagation, response page metadata, dan test. Out of scope: service credential (CS-03) dan cursor storage di OneBox.

## 5. Prasyarat dan Dependency

Contract CS-01 sudah frozen. Migration dibuat sebagai revision 20260713_0001 dengan down_revision 495376efebcb. Jangan membuat Alembic branch paralel.

## 6. Kontrak Sebelum dan Sesudah

Initial pull:

    GET /api/integration/v1/reviews?limit=100

Optional bootstrap lower bound:

    GET /api/integration/v1/reviews?updated_since=2026-07-01T00:00:00Z&limit=100

Page berikutnya hanya memakai cursor:

    GET /api/integration/v1/reviews?cursor=<next_cursor>

Response page:

```json
{
  "page": {
    "limit": 100,
    "has_more": true,
    "next_cursor": "opaque-signed-cursor",
    "checkpoint_cursor": null,
    "snapshot_at": "2026-07-13T05:00:00Z"
  }
}
```

Pada final page has_more=false, next_cursor=null dan checkpoint_cursor berisi posisi snapshot upper tuple. OneBox menyimpan checkpoint_cursor hanya setelah seluruh page berhasil di-ingest. Request siklus berikutnya memakai checkpoint_cursor sebagai cursor awal.

Cursor payload internal (tidak menjadi contract publik): version, company_id, location_id/filter hash, lower(sync_updated_at,id), upper(sync_updated_at,id), issued_at. Encode canonical JSON base64url lalu HMAC-SHA256 memakai INTEGRATION_CURSOR_SECRET. Decode wajib constant-time compare.

## 7. File Target

| Path | Status | Alasan |
|---|---|---|
| app/db/models.py | [ubah] | Review.sync_updated_at + index |
| alembic/versions/20260713_0001_add_review_sync_watermark.py | [baru] | migration linear |
| app/services/analysis_service.py | [ubah] | touch watermark saat analysis commit |
| app/services/integration_review_service.py | [ubah] | snapshot/keyset query |
| app/utils/integration_cursor.py | [baru] | encode/decode/sign/validate |
| apps/api/app_api/integration_schemas.py | [ubah] | page cursor fields |
| apps/api/app_api/routers/integration_reviews.py | [ubah] | parameter validation |
| app/config.py | [ubah] | INTEGRATION_CURSOR_SECRET |
| .env.example | [ubah] | placeholder secret |
| tests/test_integration_delta_sync.py | [baru] | delta matrix |

## 8. Perubahan Data dan Migration

Model target:

    sync_updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index tidak inline)

Index:

    idx_reviews_company_sync_id(company_id, sync_updated_at, id)

Upgrade:

1. Add sync_updated_at nullable.
2. Backfill setiap review dengan GREATEST(reviews.updated_at, MAX(review_analysis.created_at), reviews.created_at).
3. Set server default now(), set NOT NULL.
4. Create composite index.

Preflight/verification:

```sql
SELECT COUNT(*) FROM reviews WHERE sync_updated_at IS NULL;
SELECT r.id FROM reviews r JOIN review_analysis a ON a.review_id=r.id GROUP BY r.id,r.sync_updated_at HAVING r.sync_updated_at < MAX(a.created_at);
```

Expected keduanya 0 row/count 0. Downgrade: drop index lalu column. Downgrade menghilangkan cursor capability, sehingga hanya dilakukan bersama rollback aplikasi.

## 9. Langkah Implementasi

1. Tambah field/index model dan migration dengan backfill SQL berbasis subquery MAX analysis.created_at.
2. Tambah IntegrationCursor dataclass/Pydantic internal dengan strict version dan UTC parser.
3. Implement HMAC codec; invalid signature/version/filter/tenant menghasilkan InvalidCursorError.
4. Pada first request, query upper tuple MAX(sync_updated_at,id) untuk tenant/filter. Jika kosong, checkpoint sama dengan lower bound.
5. Query rows lower-exclusive dan upper-inclusive, order ASC sync_updated_at,id, limit+1. Elemen ke limit+1 hanya penanda has_more.
6. next_cursor membawa lower tuple item terakhir dan upper tuple tetap. Final checkpoint membawa lower=upper.
7. Ubah AnalysisService._store_analysis: lock/fetch Review dalam tenant, insert analysis, set sync_updated_at=func.clock_timestamp(), commit sekali.
8. Pastikan setiap jalur update Review juga menggerakkan watermark; insert menggunakan default.
9. Expose updated_at dan sync_updated_at UTC pada projection.

Pseudo-condition:

```python
where(company_id == principal.company_id)
where((sync_updated_at > after_t) | ((sync_updated_at == after_t) & (id > after_id)))
where((sync_updated_at < upper_t) | ((sync_updated_at == upper_t) & (id <= upper_id)))
order_by(sync_updated_at.asc(), id.asc())
limit(limit + 1)
```

## 10. Security dan Tenant Isolation

company_id dimasukkan ke cursor signed dan dibandingkan dengan principal. Filter location juga diikat ke cursor. Cursor invalid selalu 400 generik tanpa mengungkap payload/signature. INTEGRATION_CURSOR_SECRET wajib berbeda antar environment dan fail-fast pada non-local.

## 11. Test Plan

tests/test_integration_delta_sync.py wajib mencakup: initial pull multi-page; dua row timestamp sama; page size 1; empty tenant; updated_since; cursor tampered; cursor tenant lain; filter berubah; row baru setelah snapshot; analysis dibuat setelah review pernah dipull; rerun analysis; final checkpoint dan next cycle.

Unit cursor dapat memakai SQLite; migration/backfill/index wajib dites PostgreSQL disposable.

Commands:

    python -m pytest tests/test_integration_delta_sync.py tests/test_mvp.py -q
    python -m alembic upgrade 20260713_0001
    python -m alembic downgrade 495376efebcb
    python -m alembic upgrade head

Expected: tidak ada missing/duplicate tuple dalam collected IDs; late analysis mengeluarkan review yang sama lagi dengan analyzed=true dan watermark lebih baru.

## 12. Verifikasi Manual dan Handoff OneBox

Pull semua page sampai has_more=false; simpan checkpoint final; jalankan analysis untuk satu review; request lagi memakai checkpoint. Expected hanya review yang watermark-nya berubah yang kembali.

OneBox RI-08 wajib menyimpan checkpoint hanya setelah semua Ticket/Message sukses. Jika batch gagal, ulang dari checkpoint lama; dedup OneBox menjaga idempotency.

## 13. Observability

Log request_id, cursor_version, company_id, after tuple, upper tuple, item_count, has_more, latency. Cursor log hanya fingerprint 8 karakter, bukan isi penuh.

## 14. Rollout dan Rollback

Jalankan migration sebelum route baru diaktifkan. Route dapat diberi feature env INTEGRATION_API_ENABLED selama staging. Rollback app kemudian downgrade migration. Cursor lama invalid setelah downgrade dan consumer harus full/bootstrap sync ulang.

## 15. Risiko dan Mitigasi

- Late analysis hilang: watermark disentuh dalam transaksi analysis.
- Timestamp sama: tie-break id.
- Dataset bergerak saat paging: upper snapshot tuple dikunci.
- Cursor replay: aman karena read-only dan idempotent; expiry opsional 30 hari.
- Clock skew: semua timestamp dibuat database, bukan clock client.

## 16. Temuan dan Deviasi

RI-08 awal mengusulkan updated_since + max(updated_at). Itu belum aman untuk analysis append-only. Plan final menambahkan sync_updated_at dan checkpoint cursor snapshot.

## 17. Handoff dan Open Questions

Tidak ada pilihan teknis yang menunggu user. OneBox menerima next_cursor/checkpoint_cursor sebagai opaque string dan tidak mengurai isinya.

## 18. Breakdown Estimasi

- 1 MD model + migration + backfill.
- 1 MD cursor codec + validation.
- 1.25 MD snapshot/keyset query.
- 0.5 MD analysis watermark propagation.
- 1 MD test matrix + PostgreSQL migration test.
- 0.25 MD docs/self-review.
- Total 5 MD.
