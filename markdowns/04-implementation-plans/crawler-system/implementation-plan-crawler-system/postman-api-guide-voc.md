> Endpoint diverifikasi langsung dari kode (`apps/api/main.py` + `apps/api/app_api/routers/*`) — bukan tebakan.
> Semua endpoint di-prefix `/api`. Semua (kecuali health & auth) **butuh Bearer token** dan **otomatis di-scope ke company milik token** (multi-tenant).

## 0. Base URL & Menjalankan API

```
Base URL (lokal): http://localhost:8000
```
Jalankan VoC System dulu:
```bash
cd hermina_crawler
docker compose up -d
# cek: docker compose ps  → service "api" (hermina-review-api) di port 8000
```
Dokumentasi interaktif (paling gampang eksplor): buka di browser
```
http://localhost:8000/api/docs        (Swagger UI — bisa "Try it out")
http://localhost:8000/api/openapi.json (kontrak lengkap, buat import ke Postman)
```

> **Tip:** di Postman bisa langsung **Import → Link →** `http://localhost:8000/api/openapi.json` → semua endpoint auto-kegenerate jadi collection. Guide manual di bawah buat pemahaman.

---

## 1. Setup Postman (sekali doang)

Buat **Environment** dengan 2 variabel:
| Variable | Initial value |
|---|---|
| `baseUrl` | `http://localhost:8000` |
| `token` | (dikosongin — diisi otomatis dari step login) |

Di request selanjutnya pakai `{{baseUrl}}` dan header `Authorization: Bearer {{token}}`.

---

## 2. Auth Flow (wajib pertama)

### 2.1 Health check (tanpa auth) — pastikan API hidup
```
GET {{baseUrl}}/api/health
```
Expected: `200` + `{"status": "ok", ...}`

### 2.2 Login → dapat token
```
POST {{baseUrl}}/api/auth/login
```
⚠️ **PENTING: body-nya `x-www-form-urlencoded`, BUKAN JSON** (pakai OAuth2PasswordRequestForm).

Di Postman: tab **Body → x-www-form-urlencoded**, isi:
| Key | Value |
|---|---|
| `username` | `test@gmail.com` (email akun VoC lu — yang dipakai login di FE) |
| `password` | `<password-anda>` |

Response `200`:
```json
{ "access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "bearer" }
```

**Auto-simpan token** — tempel di tab **Scripts → Post-response** request login:
```javascript
const json = pm.response.json();
pm.environment.set("token", json.access_token);
```
Setelah ini semua request lain tinggal pakai `{{token}}`.

### 2.3 Cek identitas token (opsional)
```
GET {{baseUrl}}/api/auth/me
Authorization: Bearer {{token}}
```

### 2.4 Register company baru (opsional — kalau butuh akun/tenant baru)
```
POST {{baseUrl}}/api/auth/register
Content-Type: application/json
```
(cek field-nya di Swagger `/api/docs` → `register_company` — ada password policy.)

---

## 3. Endpoint Inti untuk Integrasi Onebox

### 3.1 ⭐ List Reviews — endpoint pull UTAMA (ini yang ditarik VoiceOfCustomerSystemTask)
```
GET {{baseUrl}}/api/reviews
Authorization: Bearer {{token}}
```
Query params (semua opsional):
| Param | Tipe | Default | Keterangan |
|---|---|---|---|
| `page` | int ≥1 | 1 | halaman |
| `page_size` | int 1–200 | 20 | jumlah per halaman |
| `location_id` | int | — | filter lokasi/cabang |
| `rating` | int 1–5 | — | filter rating |
| `sentiment` | string | — | `positive`/`neutral`/`negative`/`mixed` |
| `keyword` | string | — | cari teks review |
| `latest_first` | bool | false | urut terbaru dulu |
| `include_raw` | bool | false | sertakan `raw_payload` |
| `date_preset` | string | — | preset rentang tanggal |
| `date_from` | datetime ISO | — | mulai (mis. `2026-06-01T00:00:00`) |
| `date_to` | datetime ISO | — | sampai |

**Contoh buat dicoba:**
```
GET {{baseUrl}}/api/reviews?page=1&page_size=50&latest_first=true
GET {{baseUrl}}/api/reviews?sentiment=negative&rating=2
GET {{baseUrl}}/api/reviews?location_id=1&date_preset=last_30_days
```
Response shape:
```json
{
  "items": [ { "id":..., "review_hash":"...", "rating":2, "review_text":"...",
               "sentiment":"negative", "urgency":"high", "issue_category":"...",
               "summary":"...", "recommended_action":"...", "location":"...", ... } ],
  "total": 75, "page": 1, "page_size": 50, "total_pages": 2
}
```
> Ini yang jadi acuan **field mapping RI-01**. Perhatikan field analisa AI (sentiment/urgency/issue_category/summary/recommended_action) nempel per item.

### 3.2 Review detail
```
GET {{baseUrl}}/api/reviews/{id}
Authorization: Bearer {{token}}
```

---

## 4. Endpoint Dashboard (buat referensi UI / dashboard VOC)

Semua butuh Bearer token.
```
GET {{baseUrl}}/api/dashboard/overview            → ringkasan (total, sentiment, dll)
GET {{baseUrl}}/api/dashboard/critical-issues     → isu kritis (urgency tinggi / patient-safety)
GET {{baseUrl}}/api/dashboard/negative-reviews    → review negatif
GET {{baseUrl}}/api/dashboard/locations/{location_id}  → ringkasan per lokasi
```
> Berguna buat mahamin metrik apa yang FE tampilin, sebelum bikin dashboard VOC di Onebox.

---

## 5. Endpoint Pendukung

```
GET  {{baseUrl}}/api/locations?active_only=true   → daftar lokasi/cabang (buat mapping RI-06)
GET  {{baseUrl}}/api/competitors                  → kompetitor
GET  {{baseUrl}}/api/settings                     → setting/entitlement
GET  {{baseUrl}}/api/fetch-jobs                   → status job crawl
GET  {{baseUrl}}/api/fetch-logs                   → riwayat fetch
GET  {{baseUrl}}/api/analysis/...                 → hasil analisa (cek /api/docs)
GET  {{baseUrl}}/api/exports/...                  → export data
```
Path persis + params tiap endkap ini: cek `/api/docs`.

---

## 6. Urutan Coba di Postman (checklist)

1. [ ] `GET /api/health` → `ok`
2. [ ] `POST /api/auth/login` (form-urlencoded) → dapat token (auto-save via script)
3. [ ] `GET /api/auth/me` → identitas & company_id
4. [ ] `GET /api/reviews?page=1&page_size=5&latest_first=true` → lihat shape data + field analisa
5. [ ] `GET /api/reviews/{id}` (ambil id dari step 4)
6. [ ] `GET /api/dashboard/overview` → angka ringkasan
7. [ ] `GET /api/locations` → daftar lokasi buat mapping

Kalau step 4 udah keluar data (VoC lokal lu ada ~75 review), berarti kontrak API buat RI-01/RI-04 udah kebukti — tinggal implement client-nya.

---

## 7. Catatan / Gap

- **Auth service-to-service** buat Onebox belum final (masih JWT user-based). Buat sekarang, login pakai akun VoC biasa. (lihat keputusan D3 di RI-02)
- **`updated_since`** buat delta sync **belum ada** di `/api/reviews` — API gap, handoff ke Codex (lihat RI-01 §8 & RI-08).
- Semua data auto di-scope company token → nggak perlu kirim company_id manual.
