# VOC-CS-05 - Reliability, Error Contract, dan Observability (4 MD)

- Status plan: ready
- Owner: developer Crawler System
- Self-review: Codex
- Dependency: VOC-CS-01 dan VOC-CS-03
- Mendukung OneBox: RI-04 dan RI-09

## 1. Tujuan

Membuat kegagalan integration API dapat dibedakan, dilacak, dan dipulihkan tanpa membocorkan secret atau mengubah error contract endpoint FE existing.

## 2. Definition of Done

- [ ] Setiap response integration memiliki X-Request-ID dan meta.request_id.
- [ ] Error integration memakai envelope/code stabil.
- [ ] Log request terstruktur dan tidak memuat token/cursor/review mentah.
- [ ] Liveness tidak bergantung DB; readiness gagal dengan 503 saat DB gagal.
- [ ] Legacy /api/health tetap tersedia selama compatibility window.
- [ ] OneBox mempunyai tabel retryable/non-retryable yang final.
- [ ] Failure tests 400/401/403/404/500/503 dan timeout simulation lulus.

## 3. Kondisi Existing Terverifikasi

- [verified] errors.py hanya menangani ValueError dengan code dari message; tidak stabil untuk contract mesin.
- [verified] FastAPI validation/HTTPException masih memakai default shape.
- [verified] logger format plain text tanpa request context.
- [verified] health_check menangkap DB exception tetapi tetap mengembalikan status ok dan HTTP 200.
- [verified] docker-compose healthcheck memanggil /api/health.
- [verified] RI-09 OneBox akan retry 5xx/timeout terbatas dan relogin 401 pada desain lama.

## 4. Scope

In scope: request ID middleware, integration exception hierarchy/handler, structured logging, liveness/readiness, redaction, dan retry contract. Out of scope: distributed tracing vendor, Prometheus stack, alert delivery, dan retry logic PHP.

## 5. Prasyarat dan Dependency

ServicePrincipal CS-03 tersedia agar log dapat mencatat key_id/company_id. Contract CS-01 tidak berubah selain error/meta additive.

## 6. Kontrak Sebelum dan Sesudah

Header request X-Request-ID optional UUID/ASCII maksimal 128. Bila tidak valid atau kosong, server membuat UUID. Response selalu mengembalikan X-Request-ID.

Error v1:

```json
{
  "error": {
    "code": "INVALID_CURSOR",
    "message": "Cursor is invalid.",
    "request_id": "uuid",
    "retryable": false
  }
}
```

| Status | Code contoh | Retry OneBox |
|---:|---|---|
| 400 | INVALID_CURSOR, INVALID_PARAMETER | tidak; perbaiki request/reset cursor terkontrol |
| 401 | INVALID_SERVICE_TOKEN | tidak loop; reload/rotate credential lalu retry sekali |
| 403 | INSUFFICIENT_SCOPE | tidak; perbaiki provisioning |
| 404 | LOCATION_NOT_FOUND | tidak; perbaiki mapping |
| 429 | RATE_LIMITED | ya, hormati Retry-After |
| 500 | INTERNAL_ERROR | ya, exponential backoff maksimal 2 retry |
| 503 | SERVICE_NOT_READY | ya, retry siklus berikutnya |

Health:

- GET /api/health/live: 200 jika process event loop hidup, tanpa DB query.
- GET /api/health/ready: 200 bila config dan DB siap; 503 bila tidak.
- GET /api/health: compatibility alias dengan response lama selama satu versi; dokumentasikan deprecation.

## 7. File Target

| Path | Status | Alasan |
|---|---|---|
| apps/api/app_api/middleware.py | [baru] | request ID/context/latency |
| apps/api/app_api/integration_errors.py | [baru] | typed exception + handler |
| apps/api/app_api/errors.py | [ubah] | register integration handler tanpa merusak legacy |
| app/utils/logger.py | [ubah] | structured formatter/redaction filter |
| apps/api/app_api/routers/health.py | [ubah] | live/ready/compat |
| apps/api/main.py | [ubah] | middleware registration |
| docker-compose.yml | [ubah] | readiness healthcheck |
| tests/test_api_observability.py | [baru] | headers/log/error/health |
| markdowns/integrations/error-contract-v1.md | [baru] | handoff retry matrix |

## 8. Perubahan Data dan Migration

Tidak ada perubahan schema. Request log tidak disimpan sebagai tabel pada MVP; gunakan stdout/container logging agar tidak menambah retention/security surface.

## 9. Langkah Implementasi

1. Buat RequestContextMiddleware: validasi/generate request_id, simpan ContextVar, hitung latency, set response header, bersihkan context setelah request.
2. Buat IntegrationApiError(code,status,message,retryable,headers) dan subclass cursor/auth/scope/not-ready.
3. Register handler khusus route integration. Legacy ValueError handler tetap untuk endpoint lama.
4. Tangani RequestValidationError pada route integration menjadi INVALID_PARAMETER dengan detail field aman; jangan echo value token/cursor.
5. Tambah log event request.start/request.complete/request.failed dengan field allowlist.
6. Tambah redaction filter untuk header authorization, token, secret, password, raw_payload, raw_response. Review text tidak dicatat; hanya review ID/hash fingerprint.
7. Pisahkan live/ready. Readiness menggunakan SettingsService.check_database_connection dan return 503 jika database.ok=false.
8. Update compose healthcheck ke /api/health/ready. Pertahankan /api/health untuk client lama.
9. Tulis retry matrix docs dan samakan code dengan contract test.

Structured log minimum: timestamp, level, event, request_id, path template, method, status, latency_ms, key_id, company_id, item_count, has_more. Tidak ada query string mentah karena cursor/token dapat ikut.

## 10. Security dan Tenant Isolation

Request ID dari client hanya diterima setelah sanitasi untuk mencegah log injection. Auth failure tidak mencatat company. Error internal selalu message generik; stack trace hanya server log dan telah melalui redaction. CORS tidak relevan untuk server-to-server curl; auth tetap wajib.

## 11. Test Plan

tests/test_api_observability.py: generated/preserved request ID, invalid request ID, validation envelope, internal exception generic, auth secret redaction, cursor redaction, live 200 saat DB down, ready 503 saat DB down, ready 200 saat DB up, legacy health shape, Retry-After 429 mock.

Commands:

    python -m pytest tests/test_api_observability.py tests/test_integration_api_contract.py -q
    python -m ruff check apps/api/app_api/middleware.py apps/api/app_api/integration_errors.py app/utils/logger.py apps/api/app_api/routers/health.py

Expected: tidak ada token/raw payload pada caplog; setiap response mempunyai request ID yang sama di header/body.

## 12. Verifikasi Manual dan Handoff OneBox

Simulasi: token salah, cursor rusak, DB down, dan injected 500. Catat status/code/retryable/request_id. Engineer OneBox memakai error-contract-v1.md untuk menentukan retry; client tidak mengurai message manusia.

## 13. Observability

Log stdout JSON satu baris direkomendasikan agar Docker/Grafana/ELK dapat parse. Metric awal diturunkan dari log: request count per status, p95 latency, auth failure count, readiness failure, items served. Tool metrics khusus dapat menjadi fast-follow.

## 14. Rollout dan Rollback

Rilis middleware/error additive lebih dulu di staging. Update healthcheck setelah endpoint ready terbukti. Rollback compose ke /api/health sebelum rollback route health. Tidak ada DB rollback.

## 15. Risiko dan Mitigasi

- Global handler mematahkan FE: scope handler ke IntegrationApiError dan pertahankan legacy.
- Healthcheck membuat restart loop saat DB maintenance: Docker health menandai unhealthy; restart policy tidak otomatis restart hanya karena unhealthy. Infra alert membedakan live vs ready.
- Log PII: allowlist field dan test caplog.
- Retry storm: OneBox backoff + Retry-After, server tidak memberi retryable=true pada 4xx permanen.

## 16. Temuan dan Deviasi

Existing /api/health bukan readiness yang benar karena HTTP 200/status ok saat DB gagal. Plan final memisahkan live/ready dan menjaga alias kompatibel.

## 17. Handoff dan Open Questions

Keputusan final sudah ada. Infra dapat memilih backend log collector tanpa mengubah event contract. OneBox hanya perlu mengikuti code/retryable dan membawa X-Request-ID saat support incident.

## 18. Breakdown Estimasi

- 0.75 MD middleware/request context.
- 0.75 MD typed errors + validation mapping.
- 0.75 MD structured logging/redaction.
- 0.5 MD live/ready + compose.
- 1 MD tests/failure drills.
- 0.25 MD docs/self-review.
- Total 4 MD.
