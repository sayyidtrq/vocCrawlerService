# VOC-CS-07 - Deployment Readiness dan Integration Runbook (3 MD)

- Status plan: ready
- Owner: developer Crawler System + Infra
- Self-review: Codex
- Dependency: VOC-CS-06
- Mendukung OneBox: RI-16 dan RI-17

## 1. Tujuan

Menyediakan jalur build, migration, deploy, smoke, rotation, dan rollback yang dapat diulang untuk integration API tanpa mengandalkan langkah terminal ad hoc.

## 2. Definition of Done

- [ ] CI menjalankan full deterministic test, Ruff, dan PostgreSQL migration cycle.
- [ ] Image immutable SHA dibangun dan dipakai deploy; latest hanya convenience tag.
- [ ] Migration dijalankan satu kali sebagai release step.
- [ ] Secret wajib tersedia tanpa masuk repo/log.
- [ ] Readiness container dan smoke dari jaringan OneBox lulus.
- [ ] Rollback app/feature dan recovery cursor terdokumentasi.
- [ ] Credential rotation drill berhasil.

## 3. Kondisi Existing Terverifikasi

- [verified] Dockerfile memakai Python 3.11 dan entrypoint selalu alembic upgrade head sebelum Uvicorn.
- [verified] docker-compose image menunjuk GHCR latest dan healthcheck /api/health.
- [verified] workflow deploy membangun latest + github.sha, tetapi compose deploy menarik latest.
- [verified] CI menjalankan pytest tanpa real integrations, belum Ruff/PostgreSQL migration.
- [verified] workflow path filter belum mencakup tests/**, scripts/**, atau .env.example.
- [verified] deploy server adalah self-hosted runner dengan persistent clone dan .env untracked.

## 4. Scope

In scope: CI checks, immutable image selection, release migration, env contract, health/smoke, rollback/runbook, dan evidence. Out of scope: memilih vendor secret manager, membuka firewall sendiri, atau mengubah OneBox deployment.

## 5. Prasyarat dan Dependency

CS-01..06 hijau. Infra menyediakan DATABASE_URL staging/production, TLS/base URL, GHCR access, dan secret storage. OneBox staging mempunyai network route ke VoC staging.

## 6. Kontrak Deployment

Environment wajib:

| Variable | Aturan |
|---|---|
| APP_ENV | staging/production |
| DATABASE_URL | secret, PostgreSQL target |
| JWT_SECRET_KEY | secret kuat, user API |
| SERVICE_TOKEN_PEPPER | secret per environment |
| INTEGRATION_CURSOR_SECRET | secret per environment |
| INTEGRATION_API_ENABLED | false saat pre-deploy, true setelah smoke |
| RUN_MIGRATIONS | true local; false production app container |
| CORS_ALLOWED_ORIGINS | hanya browser FE; bukan kontrol S2S |

Service token OneBox bukan env yang diperlukan server; token dibuat melalui CLI dan raw value disimpan di secret/config OneBox.

## 7. File Target

| Path | Status | Alasan |
|---|---|---|
| .github/workflows/deploy.yml | [ubah] | lint, Postgres migration, SHA deploy |
| docker-compose.yml | [ubah] | IMAGE_TAG, readiness, RUN_MIGRATIONS |
| entrypoint.sh | [ubah] | migration conditional |
| .env.example | [ubah] | seluruh config placeholder |
| scripts/smoke_voc_integration.py | [baru] | ready + authenticated pull |
| markdowns/integrations/RUNBOOK_VOC_ONEBOX.md | [baru] | operasi lengkap |
| markdowns/integrations/evidence/ | [baru] | staging evidence |

## 8. Perubahan Data dan Migration

Tidak membuat migration baru. Runbook menjalankan chain existing sebagai release step:

    docker run --rm --env-file <secure-env> <image-sha> python -m alembic upgrade head

Sebelum CS-04 migration jalankan preflight dan backup. Jangan otomatis downgrade production saat incident. Migration harus dipertahankan jika data cross-tenant duplicate sudah masuk; rollback aplikasi memakai feature flag atau compatibility image.

## 9. Langkah Implementasi

1. Tambah workflow path tests/**, scripts/**, .env.example dan file contract.
2. CI test job: install, Ruff, pytest deterministic, PostgreSQL service, alembic upgrade head, downgrade/upgrade revisions baru.
3. Ubah compose image menjadi ghcr.io/...:${IMAGE_TAG:-latest}; workflow deploy mengekspor IMAGE_TAG github.sha.
4. Ubah entrypoint: jalankan Alembic hanya jika RUN_MIGRATIONS=true. Local default boleh true; production false.
5. Deploy sequence: pull SHA -> backup/preflight -> release migration -> start container SHA dengan integration flag false -> ready smoke -> authenticated smoke -> flag true/recreate -> WSL OneBox simulator.
6. Buat smoke script yang membaca token dari env, memanggil /health/live, /health/ready, integration limit=1, memvalidasi api_version/request_id/no raw fields.
7. Dokumentasikan token issuance/rotation/revoke, cursor reset terkontrol, full-resync, log lookup request_id, dan ownership incident.
8. Simpan evidence sanitized per release: SHA, migration head, timestamp, request IDs, test summary, counts.

## 10. Security dan Tenant Isolation

- GitHub secret/runner env tidak dicetak.
- .env permission 600 dan tidak di-checkout/commit.
- Deploy log tidak menampilkan docker env inspect.
- Token smoke melalui environment masked.
- TLS wajib bila trafik melewati host/network tidak terpercaya.
- Service token staging dan production berbeda company/client row.

## 11. Test Plan

CI commands:

    python -m ruff check app apps tests scripts
    python -m pytest tests/ -q --ignore=tests/test_real_integrations.py
    python -m alembic upgrade head
    python -m alembic downgrade 495376efebcb
    python -m alembic upgrade head

Deployment smoke:

    python -m scripts.smoke_voc_integration
    docker compose ps
    docker compose logs --since 10m api

Expected: image SHA healthy, DB head 20260713_0003, ready 200, pull 200, api_version v1, no secret/raw payload, request ID dapat ditemukan di log.

## 12. Verifikasi Manual dan Handoff OneBox

Jalankan simulator CS-06 dari WSL OneBox ke staging. Berikan engineer OneBox base URL, token melalui kanal secret, expiry/rotation date, error contract, fixture version, dan runbook. Jangan mengirim DATABASE_URL atau server pepper.

## 13. Observability

Release evidence mencatat image SHA dan Alembic head. Alert minimum: readiness gagal, 5xx meningkat, auth failure spike, latency p95, dan tidak ada successful pull dalam interval yang disepakati.

## 14. Rollout dan Rollback

Rollout: backup -> preflight -> migration -> app flag off -> smoke -> flag on -> OneBox simulator -> monitor.

Rollback prioritas: set INTEGRATION_API_ENABLED=false agar pull berhenti; OneBox mempertahankan checkpoint lama. Jika runtime rusak, deploy compatibility SHA. Jangan downgrade DB otomatis. Downgrade hanya setelah preflight membuktikan tidak ada data yang melanggar schema lama.

Recovery cursor: jika checkpoint OneBox hilang, lakukan full pull dengan dedup; jangan membuat endpoint server menghapus data. Jika cursor invalid setelah key rotation/deploy, gunakan last updated_since yang tercatat lalu dedup.

## 15. Risiko dan Mitigasi

- latest drift: deploy SHA immutable.
- Migration bersamaan dua replica: release step tunggal + RUN_MIGRATIONS=false.
- Rollback schema tidak aman: feature flag dan forward-fix menjadi default.
- Secret bocor: masked env, redaction tests, rotation drill.
- Network kantor-only: smoke wajib dari host OneBox, bukan hanya localhost VoC.

## 16. Temuan dan Deviasi

Deployment existing sudah membangun tag SHA tetapi menjalankan latest, dan migration selalu berada di entrypoint. Plan final memakai SHA serta memisahkan migration coordinator.

## 17. Handoff dan Open Questions

Tidak ada keputusan teknis menunggu user. Infra hanya perlu menyediakan secret/network dan maintenance window. Default rollback adalah disable integration + forward-fix, bukan downgrade schema refleks.

## 18. Breakdown Estimasi

- 0.75 MD CI lint/Postgres migration.
- 0.5 MD immutable image + entrypoint/compose.
- 0.5 MD smoke script.
- 0.75 MD runbook rollout/rollback/rotation.
- 0.25 MD staging drill.
- 0.25 MD self-review/evidence.
- Total 3 MD.
