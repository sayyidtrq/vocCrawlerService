# VOC-CS-06 - Contract Test dan Simulasi Pull OneBox (5 MD)

- Status plan: ready
- Owner: developer Crawler System
- Self-review: Codex
- Consumer validator: engineer OneBox memakai fixture yang sama
- Dependency: VOC-CS-01 sampai VOC-CS-05
- Mendukung OneBox: RI-03, RI-04, RI-05, RI-08, RI-16

## 1. Tujuan

Membuktikan contract end-to-end dari perspektif consumer tanpa bergantung Selenium, Google, LLM live, atau code PHP OneBox. Simulator meniru pull, pagination, checkpoint commit, dan dedup SiteId + review_hash.

## 2. Definition of Done

- [ ] Contract suite menjalankan auth, initial pull, multi-page, delta, late analysis, dan tenant isolation.
- [ ] Simulator dapat dijalankan dari Windows dan WSL dengan token dari environment.
- [ ] Failure setelah page N tidak memajukan durable checkpoint.
- [ ] Rerun tidak membuat duplicate simulated ticket.
- [ ] Fixture tervalidasi terhadap Pydantic schema dan OpenAPI.
- [ ] Migration chain diuji dari kosong sampai head pada PostgreSQL.
- [ ] Evidence bundle siap dipakai RI-16.

## 3. Kondisi Existing Terverifikasi

- [verified] Test existing fokus service layer dengan SQLite StaticPool.
- [verified] tests/test_real_integrations.py fokus Google Places, bukan OneBox pull.
- [verified] CI mengabaikan test_real_integrations dan belum menyediakan PostgreSQL service.
- [verified] requests sudah menjadi dependency; FastAPI/TestClient dependency perlu diverifikasi/pin httpx.
- [verified] OneBox RI-16 membutuhkan failure recovery, tenant isolation, rerun dedup, dan staging evidence.

## 4. Scope

In scope: automated contract/API tests, deterministic DB fixtures, consumer simulator, state/checkpoint semantics, migration smoke, dan evidence template. Out of scope: membuat Ticket asli atau menjalankan Selenium/LLM.

## 5. Prasyarat dan Dependency

Seluruh contract/auth/delta/error task sudah implemented. API client test dibuat langsung melalui ApiClientService. Gunakan PostgreSQL disposable untuk migration/concurrency cases dan SQLite untuk test murni yang kompatibel.

## 6. Skenario Contract

| ID | Skenario | Expected |
|---|---|---|
| E2E-01 | valid token, 3 review, limit 2 | 2 page, semua ID sekali |
| E2E-02 | rerun dari checkpoint final | 0 item sampai ada perubahan |
| E2E-03 | analysis dibuat setelah checkpoint | review yang sama muncul dengan watermark/analysis baru |
| E2E-04 | dua row timestamp sama | tidak ada skip/duplicate cursor |
| E2E-05 | insert setelah snapshot page 1 | tidak masuk siklus aktif, masuk siklus berikutnya |
| E2E-06 | gagal setelah page 1 | durable checkpoint lama; rerun aman |
| E2E-07 | token tenant A + location B | 404/tidak ada data B |
| E2E-08 | token invalid/revoked/expired | 401 code stabil |
| E2E-09 | cursor tampered/filter berubah | 400 |
| E2E-10 | DB not ready | readiness 503, error retryable |
| E2E-11 | malformed item fixture | schema validator gagal sebelum ingest |
| E2E-12 | duplicate hash tenant sama/beda | sama dedup; beda tenant allowed |

## 7. File Target

| Path | Status | Alasan |
|---|---|---|
| tests/conftest.py | [ubah/baru] | app, DB, service principal fixtures |
| tests/fixtures/voc_reviews_v1.json | [baca-saja] | golden consumer fixture |
| tests/test_onebox_pull_contract.py | [baru] | E2E-01..12 |
| tests/test_migrations_postgres.py | [baru] | empty DB upgrade/downgrade/preflight |
| scripts/simulate_onebox_pull.py | [baru] | WSL/Windows consumer simulator |
| apps/api/requirements.txt | [ubah bila perlu] | pin httpx untuk TestClient |
| markdowns/integrations/evidence/voc-integration-template.md | [baru] | checklist hasil |

## 8. Perubahan Data dan Migration

Tidak ada migration baru. Test harus memvalidasi chain 20260619_0001 sampai 20260713_0003. Database test dibuat disposable; jangan menjalankan downgrade test pada database dev bersama.

## 9. Langkah Implementasi

1. Buat app fixture dengan dependency override dan DB factory deterministik.
2. Seed dua company, dua location, review analyzed/unanalyzed, timestamp sama, dan API client masing-masing.
3. Implement collector helper yang mengikuti next_cursor sampai final dan baru menyimpan checkpoint_cursor setelah semua item callback sukses.
4. Implement simulated ticket store keyed (site_id,review_hash). Store cukup JSON temp/in-memory, tidak meniru schema OneBox.
5. Tambah fail_after_page/fail_on_hash untuk membuktikan cursor tidak maju saat partial failure.
6. Implement simulator CLI membaca VOC_BASE_URL, VOC_SERVICE_TOKEN, VOC_SITE_ID, dan optional state path dari env/arg aman. Token tidak boleh menjadi positional arg atau tercetak.
7. Validasi setiap item dengan IntegrationReviewItem schema sebelum simulated ingest.
8. Tambah migration test PostgreSQL: upgrade empty->head, seed legacy nullable fixture bila memungkinkan, preflight fail, cleanup, upgrade, downgrade safe case.
9. Generate evidence Markdown berisi command, timestamp, API version, request IDs, counts, dan sanitized sample.

Simulator command:

    VOC_BASE_URL=http://192.168.1.3:8000 VOC_SERVICE_TOKEN=<secret> VOC_SITE_ID=169 python -m scripts.simulate_onebox_pull --state-file .tmp/voc-sync-state.json

PowerShell memakai environment variable, bukan menaruh token pada command history.

## 10. Security dan Tenant Isolation

Fixture tidak memakai nama/original review production. Test memastikan response tidak mengandung company_id/raw fields. State simulator hanya menyimpan checkpoint, site ID, dan hash dedup; tidak menyimpan token atau review text. File state masuk .gitignore.

## 11. Test Plan

Automated commands:

    python -m pytest tests/test_onebox_pull_contract.py -q
    python -m pytest tests/test_migrations_postgres.py -q
    python -m pytest tests/ -q --ignore=tests/test_real_integrations.py
    python -m ruff check app apps tests scripts

Expected: E2E-01..12 hijau; migration memiliki satu head; baseline existing tidak regresi. Ruff dua F401 existing harus dibersihkan dalam PR implementasi atau dicatat terpisah, bukan diabaikan selamanya.

Manual failure drill: stop API setelah page pertama, jalankan simulator lagi, revoke credential di tengah, rusak cursor state copy, dan matikan DB. Setiap kasus menghasilkan code/request_id/recovery sesuai contract.

## 12. Verifikasi Manual dan Handoff OneBox

Jalankan simulator dari WSL OneBox ke Docker VoC. Evidence minimal: health ready 200, auth pull 200, jumlah item/page, checkpoint sebelum/sesudah, rerun 0 insert, late analysis 1 update, invalid token 401, request IDs, dan network base URL.

Engineer OneBox membandingkan output VoiceOfCustomerSystemClient dengan golden fixture. Perbedaan field/type adalah contract failure, bukan diselesaikan dengan parser longgar.

## 13. Observability

Simulator meneruskan X-Request-ID dengan prefix test run dan mencetak ringkasan tanpa token: fetched, inserted, duplicate, updated, failed, pages, checkpoint_changed. Server log dapat dicari dengan ID yang sama.

## 14. Rollout dan Rollback

Test/simulator additive dan tidak memengaruhi runtime. Jika contract gagal, jangan lanjut staging. Rollback cukup hapus script/test; perubahan runtime dikembalikan pada task pemiliknya.

## 15. Risiko dan Mitigasi

- Test terlalu mock: wajib satu smoke dari WSL ke container live.
- Fixture drift: golden test dan API version.
- State rusak: simulator mendeteksi schema/version dan meminta explicit full-resync flag; tidak silent reset.
- Test migration merusak DB: hanya disposable DATABASE_URL.
- Token bocor CI: secret masking dan tidak print env.

## 16. Temuan dan Deviasi

Existing test_real_integrations bukan integration test OneBox. Plan menambah consumer-driven suite khusus, tetap memisahkan external Google tests agar CI deterministik.

## 17. Handoff dan Open Questions

Tidak ada keputusan teknis menunggu user. Engineer OneBox hanya menjalankan fixture/simulator dan melaporkan incompatibility dengan request_id/evidence.

## 18. Breakdown Estimasi

- 0.75 MD fixture/app/DB test scaffolding.
- 1.5 MD E2E-01..12 contract suite.
- 1 MD simulator + durable checkpoint/failure injection.
- 0.75 MD PostgreSQL migration test.
- 0.5 MD WSL smoke/evidence template.
- 0.5 MD full regression/self-review.
- Total 5 MD.
