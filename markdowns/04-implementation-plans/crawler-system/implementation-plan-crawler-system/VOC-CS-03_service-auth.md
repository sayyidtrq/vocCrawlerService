# VOC-CS-03 - Service-to-Service Auth dan Tenant Binding (5 MD)

- Status plan: ready
- Owner: developer Crawler System
- Self-review: Codex
- Dependency: VOC-CS-01 dan migration head VOC-CS-02
- Mendukung OneBox: RI-02 dan RI-04

## 1. Tujuan

Mengganti kebutuhan login user/password untuk integrasi mesin dengan opaque service token yang dapat diterbitkan, dirotasi, dicabut, dan selalu terikat ke satu company_id.

## 2. Definition of Done

- [ ] OneBox dapat mengakses integration v1 memakai bearer service token.
- [ ] Database hanya menyimpan HMAC hash secret, bukan raw token.
- [ ] Principal menghasilkan company_id dan scope reviews:read.
- [ ] Invalid/expired/revoked token selalu 401 generik; scope kurang 403.
- [ ] Token tenant A tidak dapat membaca location/review tenant B.
- [ ] Issuance menampilkan raw token sekali dan tidak menulisnya ke log.
- [ ] Rotation overlap dan revoke terbukti lewat test.
- [ ] JWT user existing tetap bekerja.

## 3. Kondisi Existing Terverifikasi

- [verified] OAuth2PasswordBearer pada dependencies.py hanya mendukung user JWT.
- [verified] POST /api/auth/login membutuhkan username/password user.
- [verified] JWT SECRET_KEY mempunyai fallback hardcoded jika env kosong.
- [verified] Company dan User sudah ada; ApiClient belum ada pada models/migration.
- [verified] OneBox RI-04 dapat mengirim Authorization Bearer dan menyimpan credential per environment.

## 4. Scope

In scope: ApiClient model/migration, token codec/verification, service principal, CLI management, config validation, route dependency, audit minimum, dan test. Out of scope: UI untuk mengelola token, OAuth authorization server, dan penyimpanan credential di OneBox.

## 5. Prasyarat dan Dependency

Migration revision 20260713_0002 memiliki down_revision 20260713_0001. Endpoint contract CS-01 sudah final. Gunakan PostgreSQL target dan dependency override untuk unit test.

## 6. Kontrak Sebelum dan Sesudah

User API tetap:

    POST /api/auth/login -> JWT user

Integration API:

    Authorization: Bearer voc_<env>_<key_id>.<secret>

Token parts: key_id public untuk lookup; secret minimal 32 random bytes URL-safe. Hash yang disimpan: HMAC-SHA256(SERVICE_TOKEN_PEPPER, full token secret). Compare memakai hmac.compare_digest.

Principal internal:

```python
ServicePrincipal(client_id: int, key_id: str, company_id: int, scopes: frozenset[str])
```

Error: 401 INVALID_SERVICE_TOKEN untuk malformed, unknown, expired, revoked, inactive, atau hash mismatch. Jangan membedakan penyebab di response. 403 INSUFFICIENT_SCOPE jika reviews:read tidak ada.

## 7. File Target

| Path | Status | Alasan |
|---|---|---|
| app/db/models.py | [ubah] | ApiClient model + Company relationship |
| alembic/versions/20260713_0002_add_api_clients.py | [baru] | table/index/FK |
| app/services/api_client_service.py | [baru] | issue/verify/revoke/rotate |
| apps/api/app_api/service_auth.py | [baru] | HTTPBearer dependency + principal |
| app/config.py | [ubah] | jwt_secret_key, service_token_pepper |
| apps/api/app_api/dependencies.py | [ubah] | hilangkan JWT fallback non-local |
| apps/api/app_api/routers/integration_reviews.py | [ubah] | require scope |
| scripts/manage_api_client.py | [baru] | CLI issuance/list/revoke/rotate |
| .env.example | [ubah] | placeholder tanpa secret nyata |
| tests/test_service_auth.py | [baru] | auth/security matrix |

## 8. Perubahan Data dan Migration

Table api_clients:

| Column | Tipe/aturan |
|---|---|
| id | integer PK |
| company_id | FK companies.id, NOT NULL, CASCADE |
| name | varchar(150), NOT NULL |
| key_id | varchar(40), UNIQUE, NOT NULL |
| secret_hash | varchar(64), NOT NULL |
| scopes | JSON/JSONB, default [reviews:read], NOT NULL |
| is_active | boolean default true |
| expires_at | timestamptz nullable |
| last_used_at | timestamptz nullable |
| revoked_at | timestamptz nullable |
| created_at | timestamptz default now |

Index idx_api_clients_company_active(company_id,is_active). Upgrade membuat table/index tanpa backfill. Downgrade drop index/table. Tidak ada token existing yang dimigrasikan; user JWT tetap terpisah.

Verification:

```sql
SELECT column_name,is_nullable FROM information_schema.columns WHERE table_name='api_clients';
SELECT indexname FROM pg_indexes WHERE tablename='api_clients';
```

## 9. Langkah Implementasi

1. Tambah Settings fields. APP_ENV selain local/test wajib gagal startup bila JWT_SECRET_KEY, SERVICE_TOKEN_PEPPER, atau INTEGRATION_CURSOR_SECRET kosong/default.
2. Buat ApiClient model dan migration linear.
3. Implement issue: validasi company, generate key_id + secret via secrets.token_urlsafe, simpan HMAC, return raw token sekali.
4. Implement verify: parse prefix, lookup key_id, cek active/revoked/expiry/hash/scope, return ServicePrincipal.
5. Update last_used_at hanya jika null atau lebih lama 5 menit agar read traffic tidak menghasilkan write per request.
6. Implement revoke dan rotate. Rotation membuat credential pengganti aktif; old credential tetap aktif selama overlap eksplisit lalu direvoke.
7. Buat CLI subcommand issue/list/revoke/rotate. list hanya menampilkan key_id, company, scopes, dates, status; tidak secret_hash.
8. Wire require_service_principal dan require_scope('reviews:read') pada integration router.
9. Pertahankan user JWT dependency untuk endpoint existing; tambahkan test regression login/me.

Contoh CLI:

    python -m scripts.manage_api_client issue --company-id 1 --name onebox-staging --expires-days 90
    python -m scripts.manage_api_client list --company-id 1
    python -m scripts.manage_api_client rotate --key-id <KEY_ID> --overlap-hours 24
    python -m scripts.manage_api_client revoke --key-id <KEY_ID>

CLI wajib meminta konfirmasi hanya untuk revoke credential aktif; dalam automated deployment gunakan flag --yes. Raw token dikirim ke secret manager/OneBox config, tidak ke Git.

## 10. Security dan Tenant Isolation

- company_id hanya berasal dari ApiClient row.
- Token prefix memisahkan service token dari JWT user.
- HMAC pepper tidak disimpan di DB dan berbeda per environment.
- Query token memakai key_id lalu constant-time compare.
- Semua auth failure response identik untuk mencegah enumeration.
- Token tidak boleh masuk URL/query.
- Gunakan TLS di luar local network.
- Scope default minimum reviews:read; tidak ada admin scope pada MVP.

## 11. Test Plan

tests/test_service_auth.py: issue stores no raw token; valid principal; wrong secret; malformed prefix; unknown key; inactive; revoked; expired; missing scope; tenant A/B isolation; rotate overlap; last_used throttling; non-local missing secret fail-fast; JWT user regression.

Commands:

    python -m pytest tests/test_service_auth.py tests/test_tenant_isolation.py -q
    python -m alembic upgrade 20260713_0002
    python -m alembic downgrade 20260713_0001
    python -m alembic upgrade head

Expected: semua auth matrix hijau; grep repository/log test tidak menemukan raw token fixture.

## 12. Verifikasi Manual dan Handoff OneBox

1. Issue token staging untuk company pilot.
2. Simpan token di secret/config OneBox.
3. Curl endpoint integration dari WSL.
4. Revoke token dan pastikan curl 401.
5. Issue replacement dan pastikan 200.

Engineer OneBox menerima base URL, token sekali, expiry, header contract, dan rotation date. Jangan kirim melalui commit atau fixture.

## 13. Observability

Event auth.service.success/failure dengan request_id, key_id, company_id (hanya success), reason_class internal, dan latency. Jangan log Authorization header, full key, secret_hash, atau token parse exception mentah.

## 14. Rollout dan Rollback

Deploy migration/model, issue token, lalu aktifkan route. Selama transisi /api/reviews user JWT tetap ada. Rollback route/dependency dulu, lalu downgrade table hanya setelah memastikan tidak ada consumer aktif.

## 15. Risiko dan Mitigasi

- Token bocor: short expiry, rotation, revoke, TLS, log redaction.
- DB bocor: HMAC pepper terpisah.
- Brute force: secret entropy tinggi; rate limit gateway dapat ditambah kemudian.
- Write amplification last_used_at: throttle 5 menit.
- Salah tenant: company tidak pernah diterima dari request.

## 16. Temuan dan Deviasi

Plan OneBox awal memakai service account user + login JWT. Keputusan final memakai service token khusus karena tidak bergantung password manusia dan lebih mudah revoke/rotate tanpa memengaruhi user.

## 17. Handoff dan Open Questions

Tidak ada keputusan teknis menunggu user. Infra hanya menyediakan secret storage dan jalur TLS. Jika organisasi kemudian mewajibkan OAuth2 client credentials, buat auth adapter baru tanpa mengubah ServicePrincipal maupun route contract.

## 18. Breakdown Estimasi

- 1 MD model + migration.
- 1.25 MD token service + config fail-fast.
- 0.75 MD dependency/scope + route wiring.
- 0.5 MD CLI lifecycle.
- 1.25 MD security/tenant test.
- 0.25 MD docs/self-review.
- Total 5 MD.
