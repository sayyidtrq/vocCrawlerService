# VOC-CS-04 - Integritas Tenant dan Dedup Review (4 MD)

- Status plan: ready
- Owner: developer Crawler System
- Self-review: Codex
- Dependency: migration head VOC-CS-03
- Mendukung OneBox: RI-01, RI-05, RI-06

## 1. Tujuan

Menyelaraskan schema database dengan model tenant-first: company_id non-null, relasi review/location tidak dapat silang tenant, serta review_hash unik per company bukan global.

## 2. Definition of Done

- [ ] locations, reviews, dan fetch_logs tidak memiliki company_id null.
- [ ] Review/location dan fetch_log/location tidak dapat berbeda company.
- [ ] Company berbeda boleh menyimpan review_hash dan source/place yang sama.
- [ ] Company sama tidak dapat menyimpan review_hash duplikat walau terjadi race.
- [ ] ReviewService insert selalu memiliki company context.
- [ ] Preflight production berhenti aman jika mapping location lama belum jelas.
- [ ] Upgrade/downgrade PostgreSQL dan tenant tests lulus.

## 3. Kondisi Existing Terverifikasi

- [verified] Model Company relationship menyatakan company_id non-null.
- [verified] Migration 6a66329ddc12 menambah company_id nullable pada locations/reviews/fetch_logs dan tidak melakukan backfill/not-null.
- [verified] Review.review_hash mapped_column(unique=True) membuat uniqueness global.
- [verified] Location unique constraint hanya source + external_place_id, juga global.
- [verified] ReviewService memfilter company bila diberikan, tetapi company_id constructor masih optional.
- [verified] test_tenant_isolation menguji read isolation, belum menguji constraint lintas tenant/race.

## 4. Scope

In scope: locations/reviews/fetch_logs tenant constraint, review/location uniqueness, service guard, preflight, dan test. CompetitorReview global hash dicatat sebagai backlog terpisah karena tidak masuk pull OneBox MVP.

## 5. Prasyarat dan Dependency

Revision 20260713_0003 memiliki down_revision 20260713_0002. Sebelum production migration, export audit query dan siapkan mapping location_id -> company_id untuk row null. Migration tidak menebak company bisnis.

## 6. Kontrak Sebelum dan Sesudah

API tidak menerima company_id. Perubahan terlihat pada behavior: service token company A hanya melihat row A; location_id tenant B menghasilkan 404; hash sama dapat hidup pada A dan B, tetapi duplikat kedua di A ditolak/idempotent.

Canonical dedup untuk OneBox tetap review_hash; OneBox menambahkan SiteId dalam lookup. external_review_id nullable dan tidak dijadikan satu-satunya key.

## 7. File Target

| Path | Status | Alasan |
|---|---|---|
| app/db/models.py | [ubah] | composite unique/FK dan hapus global unique |
| alembic/versions/20260713_0003_scope_tenant_and_review_hash.py | [baru] | cleanup + constraint |
| app/services/review_service.py | [ubah] | company context wajib untuk write |
| app/services/location_service.py | [ubah] | lookup selalu company-scoped |
| app/services/fetch_log_service.py | [ubah] | company/location consistency |
| app/services/integration_review_service.py | [ubah] | location ownership validation |
| tests/test_tenant_isolation.py | [ubah] | negative cases tambahan |
| tests/test_review_dedup_integrity.py | [baru] | constraint/race/Postgres |

## 8. Perubahan Data dan Migration

Preflight wajib:

```sql
SELECT 'locations' table_name, COUNT(*) FROM locations WHERE company_id IS NULL
UNION ALL SELECT 'reviews', COUNT(*) FROM reviews WHERE company_id IS NULL
UNION ALL SELECT 'fetch_logs', COUNT(*) FROM fetch_logs WHERE company_id IS NULL;

SELECT r.id FROM reviews r JOIN locations l ON l.id=r.location_id WHERE r.company_id IS DISTINCT FROM l.company_id;
SELECT f.id FROM fetch_logs f JOIN locations l ON l.id=f.location_id WHERE f.company_id IS DISTINCT FROM l.company_id;
SELECT company_id,review_hash,COUNT(*) FROM reviews GROUP BY company_id,review_hash HAVING COUNT(*)>1;
```

Recommended cleanup: reviews/fetch_logs yang company_id null atau salah diturunkan dari locations.company_id. Location yang company_id null tidak boleh ditebak; migration abort dengan pesan agar deployment owner memasukkan mapping eksplisit.

Upgrade setelah data bersih:

1. Set company_id NOT NULL pada locations, reviews, fetch_logs.
2. Drop global reviews_review_hash_key dan uq_locations_source_place.
3. Create uq_reviews_company_review_hash(company_id,review_hash).
4. Create uq_locations_company_source_place(company_id,source,external_place_id).
5. Create unique support uq_locations_id_company(id,company_id).
6. Ganti FK reviews.location_id dan fetch_logs.location_id dengan composite FK (location_id,company_id) -> locations(id,company_id).
7. Drop idx_reviews_review_hash jika redundant; create idx_reviews_company_hash bila belum tercakup unique constraint.

Model mengikuti nama constraint yang sama. Downgrade hanya boleh jika tidak ada duplicate hash/place lintas company yang akan bertabrakan dengan global unique; jalankan preflight downgrade dan abort bila ada.

## 9. Langkah Implementasi

1. Tulis preflight SQL sebagai fungsi migration dan runbook; jangan auto-assign location null.
2. Ubah Review/Location table_args dan company nullability.
3. Tambah composite relationship constraint tanpa mengubah primary key.
4. Ubah ReviewService.insert_review: resolve company dari constructor/data; bila tidak ada raise ValueError. Validate location belongs company sebelum insert.
5. Tangkap IntegrityError unique composite dan return duplicate hanya jika row company+hash benar-benar ada; error lain tetap dilempar.
6. Pastikan integration service tidak melakukan join Location tanpa company equality.
7. Tambah test dua company dengan hash/place sama, duplicate same-company, mismatched location, null company, dan race insert.

## 10. Security dan Tenant Isolation

Database menjadi lapisan pertahanan kedua setelah service auth. Tidak ada jalur API yang memakai ReviewService(company_id=None). CLI legacy yang butuh global view harus menggunakan mode admin eksplisit, bukan fallback diam-diam.

## 11. Test Plan

- SQLite: read/write isolation dan service validation.
- PostgreSQL: migration, composite FK, unique per tenant, concurrent insert dua session.
- Regression: fetch/analysis test existing tetap hijau.

Commands:

    python -m pytest tests/test_tenant_isolation.py tests/test_review_dedup_integrity.py tests/test_mvp.py -q
    python -m alembic upgrade 20260713_0003
    python -m alembic downgrade 20260713_0002

Expected: duplicate tenant yang sama menjadi idempotent; tenant berbeda berhasil; mismatch company/location gagal constraint.

## 12. Verifikasi Manual dan Handoff OneBox

Buat dua API client company berbeda dan fixture hash sama. Pull masing-masing hanya menghasilkan data tenant sendiri. Handoff ke OneBox menegaskan dedup lookup tetap SiteId + review_hash.

## 13. Observability

Log duplicate sebagai event review.duplicate dengan company_id, location_id, dan hash fingerprint pendek. Constraint violation non-dedup menjadi error dengan request_id; jangan log payload review.

## 14. Rollout dan Rollback

Backup DB, jalankan preflight, cleanup terkontrol, migration, verification query, lalu smoke fetch. Jika preflight gagal, jangan menjalankan DDL. Rollback app tidak memerlukan rollback data; downgrade constraint hanya jika preflight downgrade aman.

## 15. Risiko dan Mitigasi

- Location lama tanpa tenant: stop dan minta mapping data owner, bukan menebak.
- Downgrade global unique gagal karena cross-tenant duplicate: pertahankan migration dan rollback aplikasi saja.
- Race duplicate: database unique menjadi authority.
- Legacy CLI tanpa company: ubah ke admin mode eksplisit atau nonaktifkan write.

## 16. Temuan dan Deviasi

Masalah bukan hanya review_hash. Unique location juga global dan migration tenant belum menegakkan NOT NULL. Paket final memperbaiki ketiganya agar contract tenant benar-benar didukung DB.

## 17. Handoff dan Open Questions

Keputusan teknis final. Satu-satunya input eksternal saat deploy adalah mapping bisnis untuk location lama yang company_id-nya null. Recommended behavior adalah abort, bukan assign ke company pertama.

## 18. Breakdown Estimasi

- 0.75 MD audit/preflight + cleanup plan.
- 1.25 MD migration constraint/FK.
- 0.75 MD model/service guard.
- 1 MD Postgres concurrency + tenant test.
- 0.25 MD rollback docs/self-review.
- Total 4 MD.
