# VOC-CS-03: Service Token Runbook

## Tujuan
Crawler System menyediakan REST API khusus integrasi OneBox tanpa email dan password user manusia. Opaque bearer token selalu terikat ke satu company_id; tenant tidak pernah diambil dari query request.

## Deploy

python -m alembic upgrade head
python -m scripts.manage_api_client list --company-id COMPANY_ID

Environment target wajib memiliki DATABASE_URL, JWT_SECRET_KEY, INTEGRATION_CURSOR_SECRET, dan SERVICE_TOKEN_PEPPER unik. Pepper hanya berada di Crawler System; jangan dikirim ke OneBox atau di-commit.

## Terbitkan token
python -m scripts.manage_api_client issue --company-id COMPANY_ID --name onebox-production --expires-days 90

Raw token hanya muncul satu kali dengan format: voc_ENV_KEY_ID.SECRET
String yang ditempel ke konfigurasi OneBox adalah seluruh token, misalnya:
VOC_API_TOKEN=voc_staging_AbCdEf1234567890.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

Jangan menempelkan hanya key_id atau secret. Simpan token di secret/config store OneBox, bukan source code, chat, commit, atau log.

## Verifikasi tenant dari OneBox

curl -i -H Authorization:Bearer TOKEN -H Accept:application/json BASE_URL/api/integration/v1/whoami

Response sukses: { company_id, company_name, scopes }. OneBox wajib membandingkan company_id response dengan tenant yang diharapkan untuk SiteId sebelum menarik review.

## Pull review
Endpoint: GET BASE_URL/api/integration/v1/reviews?limit=100
Headers: Authorization Bearer TOKEN and X-Request-ID onebox-sync-YYYYMMDD-001
Contract response tidak berubah. Gunakan data[], page.next_cursor, page.checkpoint_cursor, page.has_more, dan meta.request_id.
Cursor hanya disimpan setelah seluruh batch berhasil di-ingest ke OneBox.

## Arti error auth
401 INVALID_SERVICE_TOKEN = token hilang, malformed, salah secret, beda environment, expired, atau revoked.
403 INSUFFICIENT_SCOPE = token valid tetapi tidak memiliki reviews:read.
404 LOCATION_NOT_FOUND = location_id bukan milik tenant token.

## Rotation dan revoke
python -m scripts.manage_api_client rotate --key-id OLD_KEY_ID
python -m scripts.manage_api_client rotate --key-id OLD_KEY_ID --overlap-hours 24
python -m scripts.manage_api_client revoke --key-id OLD_KEY_ID --yes

Rotation tanpa overlap langsung mematikan token lama. Dengan overlap-hours, token lama tetap aktif dan harus direvoke setelah OneBox memakai token replacement.

## Tambahkan aksi AI ke token Fetch Jobs yang sudah ada

DNGO19-3407 memakai **token yang sama** dengan antrean Fetch Jobs. Jangan
menerbitkan token baru dan jangan menyalin username/password user ke setiap
Connection. Tambahkan scope pada metadata token yang sudah tersimpan:

```sh
python -m scripts.manage_api_client grant-scope \
  --key-id EXISTING_KEY_ID \
  --scope analysis:write
```

Secret token tidak berubah dan tidak ditampilkan ulang. Setelah scope tersedia,
OneBox dapat memakai endpoint berikut:

- `POST /api/integration/v1/analysis/pending`
- `POST /api/integration/v1/analysis/reviews/{review_id}/rerun`
- `GET /api/integration/v1/analysis/quality-summary`
- `POST /api/integration/v1/analysis/rollback`

Semua endpoint mengambil `company_id` dari service token. `company_id` tidak
diterima dari body/query, dan ID lokasi/review milik tenant lain menjawab 404.

## JWT user tetap terpisah
POST /api/auth/login dan GET /api/auth/me tetap menggunakan JWT user untuk FE. Token voc_ hanya berlaku pada endpoint integration.

## Acceptance checklist
Migration applied. whoami mengembalikan company_id yang diharapkan. reviews?limit=1 mengembalikan 200. Token salah mengembalikan 401. Token direvoke lalu request berikutnya 401. Token tidak muncul di log, Git, fixture, atau URL.


