# Claude Code Superprompt - OneBox Integration Context

Tanggal: 2026-07-09  
Project asal: Review System / crawler backend  
Target kerja Claude Code: mempelajari struktur product OneBox dan menyiapkan rencana integrasi pull data dari service crawler.

---

## 1. Peran Kamu

Kamu adalah Claude Code yang sedang dibuka di repository OneBox.

Tugas utama kamu bukan langsung menulis fitur besar. Tugas pertama adalah:

1. membaca dan memahami struktur OneBox,
2. menemukan titik integrasi yang paling aman,
3. memetakan cara OneBox bisa pull data dari backend crawler Hermina,
4. menyiapkan placeholder / integration skeleton hanya setelah struktur OneBox cukup jelas.

Jangan berasumsi struktur OneBox sudah diketahui. Treat repo OneBox sebagai codebase besar yang harus dipelajari dulu.

---

## 2. Konteks Product Review System

Review System adalah service crawler + analysis untuk review publik rumah sakit.

Fungsi utama:

- mengambil review dari sumber eksternal seperti Google Maps / Google Places,
- menyimpan data lokasi dan review,
- menjalankan AI analysis untuk sentiment, urgency, issue category, summary, recommended action,
- menyediakan REST API supaya aplikasi lain, khususnya OneBox, bisa menarik data.

Service ini diposisikan sebagai **3rd party microservice** terpisah dari OneBox.

OneBox tidak menjalankan crawler secara langsung. OneBox hanya akan melakukan HTTP request ke backend crawler untuk mengambil data yang diperlukan.

---

## 3. Status Backend Crawler Saat Ini

Backend crawler sudah tersedia sebagai REST API berbasis FastAPI.

Repo backend:

```txt
https://github.com/sayyidtrq/herminaCrawler
```

Repo frontend reference:

```txt
https://github.com/sayyidtrq/herminaCrawler-fe
```

Catatan:

- Frontend Hermina hanya reference / prototype UI.
- UI final kemungkinan besar akan lebih banyak disiapkan di OneBox.
- Backend crawler sudah disiapkan untuk Docker deployment.
- API docs tersedia dari FastAPI Swagger.

Endpoint dokumentasi:

```txt
GET /api/docs
GET /api/redoc
GET /api/openapi.json
```

OpenAPI JSON adalah kontrak paling ideal untuk dibaca OneBox saat integrasi.

---

## 4. Arah Arsitektur Integrasi

Flow integrasi yang diharapkan:

```txt
OneBox UI / OneBox backend
        |
        | HTTP request / pull data
        v
Review System API
        |
        | query database crawler + analysis result
        v
JSON response
        |
        v
OneBox render / store / process data
```

Status flow:

- Secara arsitektur sudah tergambar.
- Modelnya microservice / third-party REST API.
- Belum bisa disimulasikan end-to-end karena struktur OneBox belum dipelajari dan parameter pull dari OneBox belum final.
- Belum ada placeholder integration module di OneBox.

Jangan menyimpulkan flow belum ada. Kesimpulan yang benar:

```txt
Flow microservice sudah kebayang dan implementasi backend crawler sudah mengarah ke sana, tetapi belum tervalidasi lewat simulasi OneBox karena integrasi di sisi OneBox belum dibuat.
```

---

## 5. API Contract Crawler Yang Sudah Ada

Base URL per environment belum final. Untuk local/dev, gunakan env config di OneBox nanti, jangan hardcode.

Contoh env yang disarankan di OneBox:

```env
HERMINA_CRAWLER_BASE_URL=http://crawler-host:8000
HERMINA_CRAWLER_AUTH_MODE=bearer
HERMINA_CRAWLER_USERNAME=
HERMINA_CRAWLER_PASSWORD=
HERMINA_CRAWLER_API_KEY=
HERMINA_CRAWLER_TIMEOUT_SECONDS=30
```

### 5.1 Auth Saat Ini

Backend crawler saat ini memakai JWT Bearer user-based auth.

Login:

```http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=<email>&password=<password>
```

Response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

Setelah login, request endpoint protected memakai:

```http
Authorization: Bearer <access_token>
```

Catatan penting:

- Auth untuk OneBox sebagai service-to-service belum final.
- Kemungkinan perlu API key statis, service account, client credentials, token refresh, atau IP whitelist.
- Jangan hardcode credential di code OneBox.
- Simpan credential di env / secret manager.

### 5.2 Endpoint Pull Utama

Endpoint utama untuk OneBox pull data review:

```http
GET /api/reviews
Authorization: Bearer <access_token>
```

Query params yang tersedia saat ini:

| Param | Type | Default | Keterangan |
|---|---:|---:|---|
| `page` | int >= 1 | `1` | Nomor halaman |
| `page_size` | int 1-200 | `20` | Jumlah data per halaman |
| `location_id` | int | optional | Filter lokasi |
| `rating` | int 1-5 | optional | Filter rating |
| `sentiment` | string | optional | `positive`, `neutral`, `negative`, `mixed` |
| `keyword` | string | optional | Cari teks review |
| `latest_first` | bool | `false` | Urut terbaru dulu |
| `include_raw` | bool | `false` | Sertakan raw payload |
| `date_preset` | string | optional | Preset tanggal |
| `date_from` | datetime | optional | Start date ISO 8601 |
| `date_to` | datetime | optional | End date ISO 8601 |

Contoh request:

```http
GET /api/reviews?page=1&page_size=50&latest_first=true
Authorization: Bearer <access_token>
```

Contoh response:

```json
{
  "items": [
    {
      "id": 1024,
      "location_id": 5,
      "location": "Hermina Depok",
      "source": "selenium_google_maps",
      "external_place_id": "ChIJ...",
      "external_review_id": "Ch9...",
      "reviewer_name": "Budi S.",
      "reviewer_profile_url": null,
      "reviewer_photo_url": null,
      "reviewer_local_guide_level": null,
      "reviewer_total_reviews": 12,
      "rating": 2,
      "review_text": "Antrian farmasi lama sekali.",
      "review_time": "2026-06-30T08:12:00+07:00",
      "review_relative_time": "seminggu lalu",
      "review_language": "id",
      "language": "id",
      "like_count": 3,
      "owner_response_text": null,
      "owner_response_time": null,
      "scraped_at": "2026-07-01T02:00:00+07:00",
      "review_hash": "a1b2...",
      "created_at": "2026-07-01T02:00:05+07:00",
      "analyzed": true,
      "analysis_id": 900,
      "sentiment": "negative",
      "sentiment_score": -0.82,
      "issue_category": "waktu_tunggu",
      "urgency": "high",
      "summary": "Keluhan antrian farmasi lama.",
      "recommended_action": "Tinjau SLA layanan farmasi.",
      "keywords": ["antrian", "farmasi"],
      "is_potential_viral": false,
      "is_patient_safety_issue": false
    }
  ],
  "total": 132,
  "page": 1,
  "page_size": 20,
  "total_pages": 7
}
```

### 5.3 Endpoint Dashboard Yang Tersedia

```http
GET /api/dashboard/overview
GET /api/dashboard/locations/{id}
GET /api/dashboard/critical-issues
GET /api/dashboard/negative-reviews
```

Endpoint dashboard bisa dipakai sebagai data source ringkasan jika OneBox tidak ingin mengolah raw reviews sendiri.

---

## 6. Hal Yang Belum Final Dari Sisi OneBox

Claude harus mencari dan/atau membantu menanyakan hal ini dari struktur OneBox:

1. OneBox ingin **menyimpan data review crawler ke DB OneBox** atau hanya **proxy/read realtime dari crawler API**?
2. OneBox butuh endpoint pull dengan parameter apa?
   - date range?
   - updated_since?
   - cursor pagination?
   - location mapping?
   - sentiment/urgency filter?
   - tenant/company mapping?
3. OneBox punya scheduler/job/queue untuk sync berkala?
4. OneBox punya pattern service class untuk external API?
5. OneBox punya HTTP client existing?
6. OneBox punya module/plugin integration pattern?
7. OneBox punya auth/session/company context yang harus dipakai untuk scoping?
8. OneBox UI mana yang cocok untuk menampilkan crawler insights?
9. OneBox butuh access model seperti:
   - API key,
   - service account,
   - client credentials,
   - JWT login,
   - IP whitelist,
   - mTLS / internal network only?

---

## 7. Tugas Eksplorasi Claude Di Repo OneBox

Sebelum membuat perubahan, lakukan repo reconnaissance.

Cari dan catat:

1. Framework backend yang dipakai.
2. Entry point aplikasi.
3. Struktur route/controller.
4. Struktur service/library/helper.
5. Struktur model/database/migration.
6. Struktur frontend/view/template.
7. Struktur config/env.
8. Cara OneBox mengatur auth/session/current user/current company.
9. Cara OneBox melakukan HTTP request ke external service.
10. Cara OneBox menjalankan background job, cron, worker, queue, atau scheduler.
11. Cara OneBox menambahkan menu/sidebar/dashboard page.
12. Cara OneBox menyimpan log/error integration.

Gunakan command seperti:

```bash
pwd
ls -la
find . -maxdepth 2 -type f | sort | head -200
rg -n "route|router|controller|Controller|service|Service|model|migration|database|db|auth|session|company|tenant|user" .
rg -n "curl|Guzzle|HttpClient|axios|fetch|request|external|integration|api_key|token|bearer" .
rg -n "cron|queue|job|worker|scheduler|swoole|task|supervisor" .
rg -n "menu|sidebar|dashboard|review|insight|report|widget" .
```

Jika repo sangat besar, jangan baca semuanya sekaligus. Mulai dari file top-level:

```txt
README*
composer.json
package.json
docker-compose*
Dockerfile
.env.example
config/*
routes/*
app/config/*
app/controllers/*
app/services/*
```

---

## 8. Output Yang Diharapkan Dari Claude

Setelah eksplorasi awal, buat laporan markdown di repo OneBox, misalnya:

```txt
docs/hermina-crawler-onebox-discovery.md
```

Isi minimal:

1. Ringkasan stack OneBox.
2. Struktur folder penting.
3. Entry point backend.
4. Route/controller pattern.
5. Config/env pattern.
6. Auth/session/company context.
7. HTTP client pattern.
8. Job/queue/scheduler pattern.
9. Candidate integration points.
10. Risiko/unknowns.
11. Rekomendasi plan implementasi bertahap.

Jangan langsung membuat integrasi penuh sebelum laporan discovery selesai.

---

## 9. Rencana Implementasi Bertahap Yang Disarankan

### Phase 0 - Discovery Only

Deliverable:

- `docs/hermina-crawler-onebox-discovery.md`
- daftar file yang relevan
- rekomendasi lokasi integration client

### Phase 1 - Placeholder Integration

Tujuan: membuktikan OneBox bisa punya module integrasi tanpa bergantung pada API live.

Deliverable:

- config env placeholder:
  ```env
  HERMINA_CRAWLER_BASE_URL=
  HERMINA_CRAWLER_AUTH_MODE=
  HERMINA_CRAWLER_USERNAME=
  HERMINA_CRAWLER_PASSWORD=
  HERMINA_CRAWLER_API_KEY=
  ```
- service/client class placeholder, misalnya `HerminaCrawlerClient`
- method:
  - `health()`
  - `login()`
  - `getReviews(params)`
  - `getDashboardOverview()`
- mock response fixture untuk local development
- minimal route/admin page untuk test connection jika pattern OneBox mendukung

### Phase 2 - Live API Simulation

Tujuan: simulasi pull data dari backend crawler.

Deliverable:

- call `/api/health`
- call `/api/auth/login`
- call `/api/reviews`
- render response mentah di dev-only page/log
- error handling timeout/401/500

### Phase 3 - Data Mapping

Tujuan: mapping response crawler ke model OneBox.

Deliverable:

- mapping table:
  - crawler field
  - OneBox field
  - nullable?
  - transform needed?
  - storage target?
- keputusan persist vs proxy
- duplicate key strategy, contoh `external_review_id` atau `review_hash`

### Phase 4 - Production Integration

Tujuan: integrasi aman dan maintainable.

Deliverable:

- service-to-service auth final
- env secrets final
- scheduler / manual sync
- monitoring/logging
- retry/backoff
- UI integration
- integration tests

---

## 10. Candidate Placeholder API Shape Di OneBox

Ini hanya contoh. Sesuaikan dengan pattern OneBox setelah discovery.

```http
GET /admin/integrations/hermina-crawler/health
POST /admin/integrations/hermina-crawler/test-connection
GET /admin/integrations/hermina-crawler/reviews-preview
POST /admin/integrations/hermina-crawler/sync
```

Jangan paksa route ini kalau OneBox punya convention lain.

---

## 11. Guardrails

Wajib:

- Jangan hardcode base URL, username, password, token, API key.
- Jangan commit secret.
- Jangan bypass auth OneBox.
- Jangan membuat crawler logic di OneBox.
- Jangan menjalankan Selenium dari OneBox.
- Jangan mengubah modul existing besar tanpa memahami owner boundary.
- Jangan membuat migration sebelum jelas apakah OneBox perlu persist data.
- Jangan menganggap semua data crawler sudah cocok dengan schema OneBox.
- Jangan mengubah production config.

Prefer:

- external API client kecil dan terisolasi,
- config via env,
- feature flag,
- timeout eksplisit,
- retry terbatas,
- structured error,
- log integration failure tanpa menyimpan secret,
- mock fixture untuk development,
- dokumentasi sebelum implementasi besar.

---

## 12. Pertanyaan Untuk Tim OneBox / Lead

Claude boleh membantu merapikan pertanyaan ini.

1. OneBox akan pull data on-demand, scheduled, atau dua-duanya?
2. Data review dari crawler perlu disimpan ke DB OneBox atau cukup live proxy?
3. Field apa saja yang wajib tampil di UI OneBox?
4. Apakah OneBox butuh raw review, analysis result, dashboard aggregate, atau semuanya?
5. Filter wajib dari OneBox apa saja?
6. Apakah perlu delta sync?
   - `updated_since`
   - cursor
   - page/page_size
7. Bagaimana mapping tenant/company OneBox ke company di crawler?
8. Auth service-to-service yang diinginkan apa?
9. Apakah perlu IP whitelist atau internal network only?
10. Siapa owner UI final?
11. Apakah OneBox punya existing module untuk third-party integration?
12. Apakah ada coding standard khusus untuk service/client/config?

---

## 13. Definition Of Done Untuk Discovery

Discovery dianggap selesai jika Claude bisa menjawab:

1. File mana yang mendefinisikan route OneBox?
2. File mana yang paling tepat untuk menambah external integration client?
3. Config/env disimpan di mana?
4. Bagaimana cara OneBox mendapatkan current user/company/tenant?
5. Bagaimana OneBox biasanya membuat page/menu baru?
6. Apakah OneBox punya job scheduler?
7. Apakah OneBox punya HTTP client existing?
8. Apakah lebih aman mulai dari dev-only preview page atau backend service dulu?
9. Apa risiko paling besar jika langsung integrasi live?
10. Langkah implementasi paling kecil yang bisa dites tanpa mengganggu product existing?

---

## 14. Prompt Singkat Untuk Ditempel Ke Claude Code

Kalau butuh versi pendek, paste ini:

```txt
You are working inside the OneBox repository. Your first task is discovery, not implementation.

Context: we need to integrate Review System, an external FastAPI crawler/analysis microservice. OneBox should pull review and dashboard data from that service through REST API. The crawler backend already exposes /api/docs, /api/openapi.json, JWT Bearer auth, GET /api/reviews, and dashboard endpoints. The final OneBox-side auth/access model and pull params are not yet finalized.

Please inspect the OneBox codebase structure carefully. Identify framework, routes/controllers, services, config/env, auth/session/company context, HTTP client patterns, job/queue/scheduler patterns, and UI/menu/dashboard extension points.

Do not build the full integration yet. Produce a markdown discovery report first with candidate integration points, risks, unknowns, and a phased plan for adding a HerminaCrawlerClient placeholder, mock response, test connection, and later live API pull.

Guardrails: do not hardcode secrets, do not bypass OneBox auth, do not embed crawler logic in OneBox, do not run Selenium from OneBox, and do not make schema migrations before deciding whether OneBox persists crawler data or proxies it.
```

