# VOC-CS-01 - Kontrak API Integrasi dan Fixture (3 MD)

- Status plan: ready
- Owner: developer Crawler System
- Self-review: Codex
- Consumer validator: engineer OneBox saat contract test
- Dependency: tidak ada
- Mendukung OneBox: RI-01, RI-03, RI-04, RI-05

## 1. Tujuan

Membekukan contract v1 yang khusus dipakai OneBox tanpa mengubah behavior GET /api/reviews milik FE. Deliverable utama adalah schema eksplisit, OpenAPI, contoh request/response, dan fixture deterministik minimal tiga review.

## 2. Definition of Done

- [ ] GET /api/integration/v1/reviews tercantum di OpenAPI.
- [ ] Response tidak mengandung raw_payload/raw_response atau company_id.
- [ ] Semua field required/nullable, enum, timezone, dan pagination semantics terdokumentasi.
- [ ] Fixture memuat positive, negative-critical, dan unanalyzed review.
- [ ] Contract test menolak field removal/type drift.
- [ ] GET /api/reviews existing tetap lulus regression test.

## 3. Kondisi Existing Terverifikasi

- [verified] apps/api/main.py hanya mendaftarkan reviews.router pada /api.
- [verified] routers/reviews.py::list_reviews memakai ReviewListResponse dan auth User JWT.
- [verified] schemas.py::ReviewResponse mencampur review dan latest analysis secara flat, cocok dengan mapping OneBox.
- [verified] ReviewResponse belum mempunyai updated_at/sync_updated_at.
- [verified] include_raw=true dapat membuka raw_payload pada user endpoint; integration endpoint tidak akan menawarkan parameter ini.
- [verified] RI-05 OneBox membutuhkan review_hash serta sentiment, urgency, summary, dan recommended_action dalam item yang sama.

## 4. Scope

In scope: contract, schema integration terpisah, router registration, serializer/fixture, dan test kompatibilitas. Out of scope: cursor implementation (CS-02), credential validation (CS-03), dan perubahan PHP OneBox.

## 5. Prasyarat

Gunakan baseline model/schema aktual. Contract ini menjadi sumber field untuk CS-02/03 dan fixture untuk OneBox RI-04. Jangan menunggu server OneBox.

## 6. Kontrak Sebelum dan Sesudah

Existing tetap tersedia:

    GET /api/reviews?page=1&page_size=20
    Authorization: Bearer <user-jwt>

Contract baru:

    GET /api/integration/v1/reviews?limit=100&updated_since=2026-07-01T00:00:00Z&location_id=10
    Authorization: Bearer <service-token>
    X-Request-ID: optional-uuid

Parameter:

| Parameter | Aturan |
|---|---|
| limit | integer 1..200, default 100 |
| cursor | opaque string dari response sebelumnya |
| updated_since | UTC ISO 8601; hanya untuk request pertama tanpa cursor |
| location_id | optional integer; harus milik company credential; filter dikunci dalam cursor |

cursor tidak boleh digabung dengan updated_since atau perubahan location_id. Request konflik mengembalikan 400 INVALID_CURSOR_CONTEXT.

Response 200:

```json
{
  "data": [
    {
      "id": 101,
      "location_id": 10,
      "location": "Cabang Depok",
      "source": "selenium_google_maps",
      "external_place_id": "place-1",
      "external_review_id": "review-1",
      "review_hash": "sha256-hex",
      "reviewer_name": "Customer A",
      "reviewer_profile_url": null,
      "rating": 2,
      "review_text": "Waktu tunggu lama",
      "review_time": "2026-07-12T03:00:00Z",
      "owner_response_text": null,
      "owner_response_time": null,
      "updated_at": "2026-07-12T03:10:00Z",
      "sync_updated_at": "2026-07-12T03:15:00Z",
      "analyzed": true,
      "sentiment": "negative",
      "sentiment_score": 0.91,
      "issue_category": "waiting_time",
      "urgency": "high",
      "summary": "Keluhan waktu tunggu",
      "recommended_action": "Audit antrean",
      "keywords": ["antrean"],
      "is_potential_viral": false,
      "is_patient_safety_issue": false
    }
  ],
  "page": {
    "limit": 100,
    "has_more": false,
    "next_cursor": null,
    "snapshot_at": "2026-07-13T05:00:00Z"
  },
  "meta": {"api_version": "v1", "request_id": "uuid"}
}
```

Enum contract mengikuti AnalysisService: sentiment positive/neutral/negative/mixed/unknown; urgency low/medium/high/critical/unknown; issue_category mengikuti ALLOWED_CATEGORIES. analysis field nullable saat analyzed=false. Datetime selalu UTC ISO 8601 dengan Z.

Error envelope:

```json
{"error":{"code":"INVALID_CURSOR","message":"Cursor is invalid.","request_id":"uuid"}}
```

Status: 400 parameter/cursor, 401 token invalid/expired/revoked, 403 scope tidak cukup, 404 location tidak ditemukan dalam tenant, 429 limit eksternal bila nanti diterapkan, 500 internal, 503 dependency belum ready.

## 7. File Target

| Path | Status | Alasan |
|---|---|---|
| apps/api/app_api/integration_schemas.py | [baru] | schema v1 terisolasi dari FE |
| apps/api/app_api/routers/integration_reviews.py | [baru] | route consumer |
| apps/api/main.py | [ubah] | register router |
| app/services/integration_review_service.py | [baru] | projection khusus contract |
| tests/fixtures/voc_reviews_v1.json | [baru] | fixture canonical |
| tests/test_integration_api_contract.py | [baru] | schema/regression contract |
| markdowns/03-architecture/integration/api-contract-v1.md | [baru] | handoff manusia |

## 8. Perubahan Data dan Migration

Tidak ada perubahan schema pada CS-01. sync_updated_at masih menjadi field target yang diimplementasikan CS-02; test CS-01 boleh memakai fixture/synthetic projection.

## 9. Langkah Implementasi

1. Inventaris semua field ReviewResponse dan mapping RI-01; klasifikasikan required, nullable, internal-only.
2. Buat integration_schemas.py agar perubahan FE schema tidak otomatis mengubah consumer contract.
3. Buat projection flat dengan whitelist field. Jangan memakai dict model mentah lalu pop blacklist.
4. Tambahkan router v1 dan wiring awal ke service. Pagination final dikerjakan CS-02; selama CS-01 gunakan interface service yang sudah menerima limit/cursor.
5. Buat fixture tiga item: analyzed positive, analyzed negative-critical, dan unanalyzed.
6. Tulis API contract Markdown dan export OpenAPI fragment.
7. Tambahkan regression test bahwa /api/reviews masih mempunyai response lama.

## 10. Security dan Tenant Isolation

Router wajib menerima principal service dari dependency CS-03. Sampai dependency tersedia, gunakan override test-only; jangan membuka endpoint tanpa auth. company_id tidak muncul sebagai parameter atau response. Projection menolak raw_payload dan raw_response.

## 11. Test Plan

- tests/test_integration_api_contract.py: schema success, nullable analysis, enum, ISO UTC, forbidden raw fields.
- Regression: instantiate create_app dengan dependency override dan cek /api/reviews tetap terdaftar.
- Golden fixture test: response model_validate fixture lalu model_dump harus stabil.

Command:

    python -m pytest tests/test_integration_api_contract.py tests/test_mvp.py -q
    python -m ruff check apps/api/app_api/integration_schemas.py apps/api/app_api/routers/integration_reviews.py app/services/integration_review_service.py tests/test_integration_api_contract.py

Expected: semua test baru dan regression hijau; tidak ada field internal pada fixture.

## 12. Verifikasi Manual dan Handoff OneBox

Gunakan service token placeholder setelah CS-03:

    curl -sS "http://localhost:8000/api/integration/v1/reviews?limit=3" -H "Authorization: Bearer <SERVICE_TOKEN>" -H "X-Request-ID: voc-contract-smoke"

Kirim api-contract-v1.md, fixture, OpenAPI JSON, dan daftar enum ke engineer OneBox. Fixture menjadi input mock RI-04.

## 13. Observability

Log event integration.reviews.request dengan request_id, client key_id, company_id, limit, location_id, item_count, has_more, latency_ms. Jangan log token, cursor penuh, atau review_text.

## 14. Rollout dan Rollback

Endpoint additive sehingga dapat dirilis tanpa mengubah FE. Rollback cukup unregister router dan hapus file baru; tidak ada migration.

## 15. Risiko dan Mitigasi

- Contract drift: golden fixture + response model test.
- Payload terlalu besar: limit maksimal 200 dan projection whitelist.
- Analysis belum ada: analyzed=false dan field analysis null, lalu CS-02 mengirim ulang saat analysis selesai.

## 16. Temuan dan Deviasi

Plan OneBox awal menggunakan /api/reviews user endpoint. Keputusan final memakai route integration v1 terpisah agar auth, cursor, dan error contract dapat berkembang tanpa merusak FE.

## 17. Handoff dan Open Questions

Keputusan final sudah dibuat. OneBox cukup mengonfirmasi parser terhadap fixture; bukan memilih struktur contract. Jika OneBox membutuhkan field tambahan, perubahan harus additive pada v1 atau dibuat v2 bila breaking.

## 18. Breakdown Estimasi

- 0.5 MD inventaris dan freeze field.
- 0.75 MD schema + projection.
- 0.5 MD router/wiring.
- 0.5 MD fixture + docs.
- 0.5 MD contract/regression test.
- 0.25 MD self-review dan handoff.
- Total 3 MD.
