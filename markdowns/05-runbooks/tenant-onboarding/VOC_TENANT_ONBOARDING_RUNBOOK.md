# VoC — Runbook Onboarding Tenant Baru di OneBox dan Crawler System

Dokumen ini menjelaskan cara menambahkan tenant baru supaya terdaftar lengkap di
dua sisi:

1. **OneBox** sebagai pemilik site, user, permission, benefit, lokasi, dan
   Connection.
2. **Crawler System** sebagai service eksekusi crawl, penyimpan review mentah,
   dan penerbit service token per tenant.

> Istilah penting: di OneBox tenant biasanya direpresentasikan oleh `SiteId`.
> Di Crawler System tenant direpresentasikan oleh `company_id`. Keduanya harus
> dipetakan secara eksplisit. Jangan menganggap `SiteId` dan `company_id`
> nilainya selalu sama.

---

## 1. Prinsip Arsitektur

### 1.1 OneBox adalah source of truth operasional

OneBox menentukan:

- site mana yang aktif;
- user/role mana yang boleh membuka menu VoC;
- benefit/entitlement `VOC%`;
- daftar lokasi yang boleh dicrawl;
- konfigurasi per `Connection`;
- token Crawler mana yang dipakai oleh site tersebut.

### 1.2 Crawler System adalah eksekutor tenant-scoped

Crawler System menentukan:

- `company_id`;
- service token opaque per company;
- cache worklist per company;
- lokasi hasil sinkronisasi dari OneBox;
- crawl batch/job;
- review hasil crawling;
- endpoint integration untuk OneBox pull review.

### 1.3 Satu service token hanya untuk satu tenant Crawler

Service token melekat ke satu `company_id`. Mengubah
`Connection.Options.company_id` di OneBox tanpa mengganti token tidak akan
memindahkan tenant. Crawler akan menolak jika `Options.company_id` tidak cocok
dengan hasil `GET /api/integration/v1/whoami`.

---

## 2. State Sistem Saat Ini

State server yang berjalan sekarang masih punya default tenant:

```env
ONEBOX_SITE_ID=169
ONEBOX_COMPANY_ID=3
```

Artinya:

- default worklist refresh diarahkan ke Site 169;
- default tenant Crawler adalah `company_id=3`;
- tenant kedua belum otomatis diproses oleh scheduler global;
- untuk tenant kedua, jalankan refresh dengan override `ONEBOX_SITE_ID` dan
  `ONEBOX_COMPANY_ID` secara eksplisit.

Target final multi-tenant mengarah ke desain `VocTenants` dari OneBox, tetapi
selama implementasi itu belum aktif, onboarding tenant baru dilakukan dengan
runbook manual ini.

---

## 3. Checklist Data yang Harus Ada

| Sisi | Data | Wajib | Catatan |
|---|---:|---:|---|
| OneBox | `Site` | Ya | Site tenant/client baru |
| OneBox | `Organization` | Ya | Tanpa organization, login bisa gagal |
| OneBox | `User` service/admin | Ya | User yang punya akses ke site tersebut |
| OneBox | `Menu` + `Permission` VoC | Ya | Supaya menu VoC tampil |
| OneBox | `SiteBenefit` `VOC%` | Ya | Gate fitur VoC |
| OneBox | `Connection` Provider VoC | Ya | Satu lokasi = satu row Connection |
| OneBox | `Connection.Options` | Ya | Berisi `api_mode`, `service_token`, `company_id` |
| Crawler | `companies` | Ya | Tenant Crawler, menghasilkan `company_id` |
| Crawler | `api_clients` | Ya | Service token untuk OneBox |
| Crawler | `locations` | Setelah sync | Terisi dari worklist OneBox |
| Crawler | `worklist_sync_states` | Setelah sync | Bukti sync terakhir |

---

## 4. Langkah 1 — Siapkan Tenant di OneBox

Untuk local Site B test, ikuti dokumen:

- `markdowns/05-runbooks/tenant-onboarding/VOC_SITE_B_TENANT_KEDUA.md`

Contoh migrasi local:

```bash
cd /onecloud
VOC_TEST_ACCOUNT_PASSWORD='<sandi-bersama>' \
ONECLOUD_ENV=local TARGET_VERSION=1786110000000000_1_123_0 \
php app/migrate.php
```

Yang harus dipastikan setelah migrasi:

- Site tenant baru ada.
- User tenant baru bisa login menggunakan domain/host yang benar.
- Menu VoC tampil.
- Benefit VoC aktif.
- Ada minimal satu `Connection` VoC untuk site tersebut.

> Penting: login OneBox ditentukan oleh header `Host` / domain site, bukan hanya
> email user. Kalau domain tidak cocok, login bisa jatuh ke site default dan
> terlihat seperti akun salah.

---

## 5. Langkah 2 — Buat Company Baru di Crawler System

Gunakan API register Crawler System untuk membuat company baru.

```bash
curl -s -X POST http://192.168.1.3:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "VoC Tenant B",
    "admin_email": "crawler.siteb.admin@onebox.local",
    "admin_password": "VocTenantB123",
    "admin_full_name": "Crawler Tenant B Admin",
    "ai_enable_flag": true,
    "total_enable_review": 100000,
    "analyze_competitor_flag": false
  }'
```

Catat `company_id` dari response. Contoh:

```json
{
  "id": 2,
  "email": "crawler.siteb.admin@onebox.local",
  "company_id": 4,
  "company_name": "VoC Tenant B"
}
```

Pada contoh di atas, tenant Crawler baru adalah:

```text
company_id=4
```

---

## 6. Langkah 3 — Terbitkan Service Token Tenant Baru

Masuk ke server Crawler:

```bash
ssh ubuntu@192.168.1.3
cd ~/herminaCrawler
```

Terbitkan token:

```bash
docker compose exec api python -m scripts.manage_api_client issue \
  --company-id 4 \
  --name onebox-site-b \
  --scope reviews:read \
  --scope crawl:enqueue \
  --scope crawl:read \
  --expires-days 90
```

Catatan:

- Script memakai `--scope` berulang, bukan `--scopes`.
- Raw token hanya ditampilkan sekali.
- Jangan commit token ke git.
- Jangan tempel token ke dokumen publik.

Output yang perlu dicatat secara aman:

```text
Service token (shown once; copy it to the OneBox secret/config store):
voc_staging_<key_id>.<secret>
key_id=<key_id>
company_id=4
scopes=crawl:enqueue,crawl:read,reviews:read
```

---

## 7. Langkah 4 — Verifikasi Token

```bash
export VOC_SITE_B_TOKEN='voc_staging_<key_id>.<secret>'

curl -s -H "Authorization: Bearer $VOC_SITE_B_TOKEN" \
  http://192.168.1.3:8000/api/integration/v1/whoami
```

Expected:

```json
{
  "company_id": 4,
  "company_name": "VoC Tenant B",
  "scopes": ["crawl:enqueue", "crawl:read", "reviews:read"]
}
```

Kalau `company_id` bukan tenant baru, token salah. Jangan lanjut ke OneBox.

---

## 8. Langkah 5 — Pasang Token ke Connection OneBox

Di OneBox, update `Connection.Options` milik site tenant baru.

Bentuk minimal:

```json
{
  "mock": false,
  "timeout": 30,
  "api_mode": "service",
  "service_token": "voc_staging_<key_id>.<secret>",
  "company_id": 4,
  "kind": "location",
  "is_official": true,
  "location": {
    "city": "Depok",
    "address": "",
    "source": "selenium",
    "pic_wa": ""
  }
}
```

Aturan:

- `api_mode` wajib `"service"`.
- `service_token` wajib token tenant baru.
- `company_id` wajib sama dengan hasil `whoami`.
- `kind` isi `"location"` untuk lokasi internal/client.
- `kind` isi `"competitor"` untuk kompetitor, tetapi biasanya status Connection
  kompetitor tidak ikut scheduler lokasi utama.
- `mock` harus `false` untuk live Crawler.

Contoh query MySQL, sesuaikan `Connection.Id` dan token:

```sql
UPDATE Connection
SET
  Url = 'http://192.168.1.3:8000',
  UserId = '',
  Password = '',
  Options = JSON_SET(
    COALESCE(NULLIF(Options, ''), JSON_OBJECT()),
    '$.mock', false,
    '$.timeout', 30,
    '$.api_mode', 'service',
    '$.service_token', '<TOKEN_TENANT_BARU>',
    '$.company_id', 4,
    '$.kind', 'location',
    '$.is_official', true
  )
WHERE Id = <CONNECTION_ID_SITE_BARU>;
```

Jika update dilakukan lewat UI/admin panel, pastikan perubahan bersifat
non-destructive: key lama di `Options` jangan hilang kalau masih relevan.

---

## 9. Langkah 6 — Refresh Worklist Tenant Baru di Crawler

Saat ini `scripts.refresh_worklist` bisa menerima `--company-id`, tetapi
`site_id` masih dibaca dari env `ONEBOX_SITE_ID`. Karena itu tenant kedua perlu
override env di command.

Contoh untuk `company_id=4` dan `site_id=<SITE_B_ID>`:

```bash
docker compose exec \
  -e ONEBOX_COMPANY_ID=4 \
  -e ONEBOX_SITE_ID=<SITE_B_ID> \
  api python -m scripts.refresh_worklist --company-id 4 --json
```

Expected:

```json
{
  "status": "synced",
  "company_id": 4,
  "site_id": <SITE_B_ID>,
  "fetched": 1,
  "upserted": 1,
  "deactivated": 0,
  "warning": null
}
```

Kalau `fetched=0`, cek kembali:

- site tenant baru punya `Connection` aktif;
- `ProviderId` adalah provider VoC;
- benefit VoC aktif;
- user service OneBox punya akses ke site itu;
- `ONEBOX_SITE_ID` yang dioverride benar;
- `Connection.Options.service_token` ada dan valid.

---

## 10. Langkah 7 — Verifikasi Isolasi Data

### 10.1 Crawler health

```bash
curl -s http://192.168.1.3:8000/api/health
```

Expected:

```json
{
  "status": "ok",
  "database": {
    "ok": true
  }
}
```

### 10.2 Token tenant pertama dan kedua tidak boleh sama

```bash
curl -s -H "Authorization: Bearer $VOC_COMPANY_3_TOKEN" \
  http://192.168.1.3:8000/api/integration/v1/whoami

curl -s -H "Authorization: Bearer $VOC_COMPANY_4_TOKEN" \
  http://192.168.1.3:8000/api/integration/v1/whoami
```

Expected:

- token pertama mengembalikan `company_id=3`;
- token kedua mengembalikan `company_id=4`.

### 10.3 Worklist tenant kedua tidak masuk tenant pertama

Di Crawler DB, cek lokasi:

```sql
SELECT id, company_id, name, external_place_id, is_active
FROM locations
WHERE company_id IN (3, 4)
ORDER BY company_id, id;
```

Expected:

- lokasi Site 169 berada di `company_id=3`;
- lokasi Site B berada di `company_id=4`;
- tidak ada lokasi tenant B masuk ke company 3.

### 10.4 Reviews endpoint ter-scope token

```bash
curl -s -H "Authorization: Bearer $VOC_COMPANY_4_TOKEN" \
  "http://192.168.1.3:8000/api/integration/v1/reviews?limit=10"
```

Expected:

- hanya review `company_id=4` yang keluar;
- field internal `company_id`, `raw_payload`, dan `raw_response` tidak muncul
  di response contract.

---

## 11. Langkah 8 — Uji Fetch/Crawl Tenant Baru

Setelah worklist masuk, jalankan crawl job memakai token tenant baru:

```bash
curl -s -X POST http://192.168.1.3:8000/api/integration/v1/crawl-jobs \
  -H "Authorization: Bearer $VOC_SITE_B_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: tenant-b-smoke-001" \
  -d '{
    "location_ids": [<CRAWLER_LOCATION_ID_TENANT_B>],
    "target_review_count": 10,
    "dry_run": false
  }'
```

Lalu poll status:

```bash
curl -s -H "Authorization: Bearer $VOC_SITE_B_TOKEN" \
  http://192.168.1.3:8000/api/integration/v1/crawl-jobs/<batch_id>
```

Acceptance:

- batch dibuat untuk `company_id=4`;
- worker memproses lokasi tenant B;
- review tersimpan di Crawler dengan `company_id=4`;
- OneBox Site B bisa pull review tenant B;
- OneBox Site 169 tidak melihat review tenant B.

---

## 12. Apakah `.env` Perlu Diubah?

### Untuk test manual tenant kedua

Tidak perlu mengubah `.env` global.

Gunakan env override saat menjalankan command:

```bash
docker compose exec \
  -e ONEBOX_COMPANY_ID=4 \
  -e ONEBOX_SITE_ID=<SITE_B_ID> \
  api python -m scripts.refresh_worklist --company-id 4 --json
```

### Untuk menjadikan tenant kedua sebagai default sementara

Boleh, tetapi hanya untuk testing terkontrol:

```env
ONEBOX_SITE_ID=<SITE_B_ID>
ONEBOX_COMPANY_ID=4
```

Risikonya: tenant pertama tidak lagi menjadi default command/scheduler.

### Untuk production multi-tenant final

Jangan memakai satu `ONEBOX_SITE_ID` dan satu `ONEBOX_COMPANY_ID`. Target final
adalah daftar tenant dari OneBox, misalnya lewat endpoint `GET /api/VocTenants`,
lalu Crawler melakukan refresh per tenant.

Selama fitur tersebut belum diimplementasikan, multi-tenant production harus
dijalankan dengan orchestrasi eksplisit per tenant.

---

## 13. Troubleshooting

| Gejala | Kemungkinan sebab | Tindakan |
|---|---|---|
| `company_id X does not exist` saat issue token | Company belum dibuat di Crawler | Jalankan `/api/auth/register` atau seed company lebih dulu |
| `INSUFFICIENT_SCOPE` | Token tidak punya scope lengkap | Issue token baru dengan `reviews:read`, `crawl:enqueue`, `crawl:read` |
| `Options.company_id tidak cocok` | Token dan `Options.company_id` beda tenant | Verifikasi `whoami`, lalu update `Connection.Options` |
| `OneBox authentication failed` | Service account/siteId salah | Cek `ONEBOX_SITE_ID`, email, password, dan permission OneBox |
| Worklist `fetched=0` | Site belum punya Connection aktif atau benefit mati | Cek Connection VoC, ProviderId, StatusId, dan SiteBenefit |
| Site B tidak bisa login | Host/domain tidak cocok | Akses via domain `Site.Domain`, bukan hanya query `siteId` |
| Data tenant lain muncul | Query tidak ter-scope site/company | Stop test, cek query OneBox dan Crawler sebelum lanjut |

---

## 14. Ringkasan Satu Layar

```text
1 tenant baru =
  OneBox Site baru
  + user/permission/benefit VoC
  + Connection VoC
  + Crawler company baru
  + service token baru untuk company itu
  + Connection.Options berisi token + company_id yang cocok
  + refresh worklist dengan site_id dan company_id tenant tersebut

Yang menentukan tenant Crawler:
  service_token -> whoami.company_id

Yang menentukan tenant OneBox:
  SiteId / Host / JWT sid

Jangan:
  - pakai token company 3 untuk Site B;
  - hanya ganti Options.company_id tanpa ganti token;
  - menganggap --company-id otomatis mengganti ONEBOX_SITE_ID;
  - commit token ke repo.
```
