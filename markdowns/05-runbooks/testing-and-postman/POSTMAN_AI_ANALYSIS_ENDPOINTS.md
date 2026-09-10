# Postman Guide - AI Analysis Endpoints

Dokumen ini berisi endpoint Crawler System yang berkaitan dengan AI analysis dan bisa langsung diuji lewat Postman. Scope contoh dibuat untuk **1 ulasan terlebih dahulu**.

## 1. Postman Variables

Buat environment Postman dengan variable berikut:

| Variable | Contoh | Keterangan |
| --- | --- | --- |
| `BASE_URL` | `http://10.13.13.90:8000` | Base URL Crawler System via WireGuard |
| `ACCESS_TOKEN` | `<jwt_token>` | Token hasil login user |
| `REVIEW_ID` | `59276` | ID review yang mau dianalisis |
| `LOCATION_ID` | `12` | ID lokasi, opsional untuk filter/rerun per lokasi |

Header standar setelah login:

```http
Authorization: Bearer {{ACCESS_TOKEN}}
Content-Type: application/json
```

## 2. Login User

Endpoint ini dipakai untuk mendapatkan JWT user. Endpoint AI analysis saat ini memakai auth user, bukan service token.

```http
POST {{BASE_URL}}/api/auth/login
Content-Type: application/x-www-form-urlencoded
```

Body `x-www-form-urlencoded`:

| Key | Value |
| --- | --- |
| `username` | `<email_user>` |
| `password` | `<password_user>` |

Contoh response:

```json
{
  "access_token": "<jwt_token>",
  "token_type": "bearer"
}
```

Simpan `access_token` ke variable `ACCESS_TOKEN`.

## 3. Ambil 1 Review Untuk Diuji

Gunakan endpoint ini untuk mengambil satu review terbaru, lalu ambil field `id` sebagai `REVIEW_ID`.

```http
GET {{BASE_URL}}/api/reviews?page=1&page_size=1&latest_first=true
Authorization: Bearer {{ACCESS_TOKEN}}
```

Contoh response:

```json
{
  "items": [
    {
      "id": 59276,
      "location_id": 12,
      "location": "RSU Hermina Depok",
      "source": "google_maps",
      "external_place_id": "ChIJ...",
      "external_review_id": "review_abc123",
      "reviewer_name": "Riau Setyaning Putri",
      "rating": 5,
      "review_text": "RS Hermina memiliki pelayanan yang sangat konsisten...",
      "review_time": "2026-08-01T09:15:00",
      "analysis_status": "pending",
      "analyzed": false,
      "analysis_id": null,
      "sentiment": null,
      "sentiment_score": null,
      "issue_category": null,
      "urgency": null,
      "summary": null,
      "recommended_action": null,
      "keywords": [],
      "is_potential_viral": false,
      "is_patient_safety_issue": false
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 1,
  "total_pages": 100
}
```

## 4. Jalankan AI Analysis Untuk 1 Review

Endpoint ini menjalankan ulang analisis AI untuk satu review. Hasilnya disimpan sebagai row baru di `review_analysis`, lalu review tersebut akan membawa hasil analisis terbaru saat dipanggil lagi.

```http
POST {{BASE_URL}}/api/analysis/reviews/{{REVIEW_ID}}/rerun
Authorization: Bearer {{ACCESS_TOKEN}}
Content-Type: application/json
```

Body: kosong.

Contoh response sukses:

```json
{
  "total": 1,
  "success": 1,
  "failed": 0,
  "skipped_empty": 0,
  "rating_fallback": 0,
  "sentiments": {
    "positive": 1,
    "neutral": 0,
    "negative": 0,
    "mixed": 0,
    "unknown": 0
  },
  "tokens_used": 650,
  "token_usage": {
    "prompt_tokens": 480,
    "completion_tokens": 170,
    "total_tokens": 650
  },
  "errors": []
}
```

Contoh response jika review tidak punya teks, hanya rating:

```json
{
  "total": 1,
  "success": 1,
  "failed": 0,
  "skipped_empty": 0,
  "rating_fallback": 1,
  "sentiments": {
    "positive": 1,
    "neutral": 0,
    "negative": 0,
    "mixed": 0,
    "unknown": 0
  },
  "tokens_used": 0,
  "token_usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  },
  "errors": []
}
```

## 5. Cek Hasil AI Analysis Pada Review

Setelah endpoint rerun selesai, panggil detail review untuk memastikan field analysis sudah terisi.

```http
GET {{BASE_URL}}/api/reviews/{{REVIEW_ID}}
Authorization: Bearer {{ACCESS_TOKEN}}
```

Contoh response:

```json
{
  "id": 59276,
  "location_id": 12,
  "location": "RSU Hermina Depok",
  "source": "google_maps",
  "external_place_id": "ChIJ...",
  "external_review_id": "review_abc123",
  "reviewer_name": "Riau Setyaning Putri",
  "rating": 5,
  "review_text": "RS Hermina memiliki pelayanan yang sangat konsisten...",
  "review_time": "2026-08-01T09:15:00",
  "analysis_status": "completed",
  "analyzed": true,
  "analysis_id": 301,
  "sentiment": "positive",
  "sentiment_score": 0.87,
  "issue_category": "general_praise",
  "urgency": "low",
  "summary": "Reviewer menyampaikan kepuasan terhadap konsistensi pelayanan rumah sakit.",
  "recommended_action": "Pertahankan standar pelayanan dan gunakan ulasan ini sebagai contoh praktik baik.",
  "keywords": ["pelayanan", "konsisten", "puas"],
  "is_potential_viral": false,
  "is_patient_safety_issue": false
}
```

## 6. Analyze Semua Review Pending

Endpoint ini menganalisis review yang belum pernah dianalisis. Untuk pengujian aman, gunakan filter `location_id` dan/atau `rating`.

```http
POST {{BASE_URL}}/api/analysis/pending
Authorization: Bearer {{ACCESS_TOKEN}}
Content-Type: application/json
```

Body opsional:

```json
{
  "location_id": 12,
  "rating": 1
}
```

Contoh response:

```json
{
  "total": 3,
  "success": 3,
  "failed": 0,
  "skipped_empty": 0,
  "rating_fallback": 1,
  "sentiments": {
    "positive": 0,
    "neutral": 0,
    "negative": 3,
    "mixed": 0,
    "unknown": 0
  },
  "tokens_used": 1780,
  "token_usage": {
    "prompt_tokens": 1320,
    "completion_tokens": 460,
    "total_tokens": 1780
  },
  "errors": []
}
```

## 7. Rerun AI Analysis Per Lokasi

Endpoint ini melakukan rerun analisis untuk semua review dalam satu lokasi.

```http
POST {{BASE_URL}}/api/analysis/locations/{{LOCATION_ID}}/rerun
Authorization: Bearer {{ACCESS_TOKEN}}
Content-Type: application/json
```

Body: kosong.

Contoh response:

```json
{
  "total": 40,
  "success": 38,
  "failed": 2,
  "not_attempted": 0,
  "circuit_breaker_tripped": false,
  "skipped_empty": 0,
  "rating_fallback": 4,
  "sentiments": {
    "positive": 20,
    "neutral": 5,
    "negative": 11,
    "mixed": 2,
    "unknown": 0
  },
  "tokens_used": 19420,
  "token_usage": {
    "prompt_tokens": 14700,
    "completion_tokens": 4720,
    "total_tokens": 19420
  },
  "duration_ms": 41230.5,
  "llm_calls": 38,
  "llm_call_ms_total": 39870.2,
  "quality": { "valid": 35, "corrected": 3 },
  "errors": [
    {
      "review_id": 59280,
      "error": "Local LLM request timed out."
    }
  ]
}
```

`not_attempted` dan `circuit_breaker_tripped` hanya naik dari nol kalau kegagalan LLM beruntun melewati `ANALYSIS_CIRCUIT_BREAKER_THRESHOLD` (default 5) — sisanya dibiarkan `pending`, bukan ditandai gagal, supaya run berikutnya otomatis mengambilnya lagi. `quality.corrected` menghitung berapa hasil model yang bentuknya di luar kontrak dan harus dinormalisasi (mis. `issue_category` yang tidak dikenal jatuh ke `"other"`) — porsi yang naik terus adalah tanda model/prompt-nya perlu ditinjau.

## 8. Rollback Model AI

Prosedur rollback DNGO19-3388/3407: dipakai ketika satu model/prompt terbukti menghasilkan analisa yang salah secara sistematis, bukan untuk satu review yang gagal (untuk itu cukup endpoint 6). Riwayat analisa bersifat *append-only*, jadi rollback tidak menghapus data secara membabi buta — setiap review yang terdampak dikembalikan ke jawaban model SEBELUMNYA kalau ada, atau ke `pending` untuk dianalisa ulang.

```http
POST {{BASE_URL}}/api/analysis/rollback
Authorization: Bearer {{ACCESS_TOKEN}}
Content-Type: application/json

{
  "model_name": "llama3.2-1b",
  "since": "2026-08-20T00:00:00Z"
}
```

`model_name` **wajib diisi** — server menolak (400) kalau kosong, supaya rollback tidak pernah membuang riwayat analisa yang sah tanpa target yang jelas. `since` opsional; kosongkan untuk membuang seluruh riwayat model tersebut.

Contoh response:

```json
{
  "model_name": "llama3.2-1b",
  "analyses_removed": 40,
  "reviews_affected": 40,
  "reverted_to_prior_analysis": 12,
  "reset_to_pending": 28
}
```

## 9. Ringkasan Kualitas (Monitoring)

Sebaran `analysis_status` review dalam N jam terakhir — dipakai monitoring/alerting eksternal untuk melihat kalau porsi `failed` melonjak sebelum ada operator yang lapor manual.

```http
GET {{BASE_URL}}/api/analysis/quality-summary?hours=24
Authorization: Bearer {{ACCESS_TOKEN}}
```

Contoh response:

```json
{
  "hours": 24,
  "since": "2026-08-25T10:00:00+00:00",
  "total": 120,
  "by_status": { "completed": 108, "failed": 6, "incomplete": 4, "pending": 2 },
  "failure_rate": 0.05
}
```

## 10. Endpoint Pendukung Untuk Melihat Output Analysis

### Dashboard Overview

```http
GET {{BASE_URL}}/api/dashboard/overview
Authorization: Bearer {{ACCESS_TOKEN}}
```

Contoh response:

```json
{
  "total_locations": 10,
  "total_reviews": 1500,
  "analyzed_reviews": 1200,
  "pending_analysis": 300,
  "sentiments": {
    "positive": 820,
    "neutral": 140,
    "negative": 210,
    "mixed": 30
  },
  "top_issues": [
    ["waiting_time", 76],
    ["pharmacy", 42],
    ["administration", 35]
  ],
  "critical_issues": 12,
  "latest_fetch": "2026-08-12T06:00:00"
}
```

### Critical Issues

```http
GET {{BASE_URL}}/api/dashboard/critical-issues
Authorization: Bearer {{ACCESS_TOKEN}}
```

Contoh response:

```json
{
  "items": [
    {
      "id": 59281,
      "location_id": 12,
      "location": "RSU Hermina Depok",
      "rating": 1,
      "review_text": "Pelayanan IGD sangat lama...",
      "sentiment": "negative",
      "issue_category": "emergency_room",
      "urgency": "critical",
      "recommended_action": "Segera eskalasi ke kepala layanan IGD untuk investigasi waktu tunggu."
    }
  ],
  "total": 1
}
```

### Negative Reviews

```http
GET {{BASE_URL}}/api/dashboard/negative-reviews
Authorization: Bearer {{ACCESS_TOKEN}}
```

Contoh response:

```json
{
  "items": [
    {
      "id": 59282,
      "location_id": 12,
      "location": "RSU Hermina Depok",
      "rating": 2,
      "review_text": "Antrian farmasi terlalu lama.",
      "sentiment": "negative",
      "issue_category": "pharmacy",
      "urgency": "medium"
    }
  ],
  "total": 1
}
```

### Export Analysis Summary

```http
POST {{BASE_URL}}/api/exports/analysis-summary.csv
Authorization: Bearer {{ACCESS_TOKEN}}
```

Contoh response:

```json
{
  "status": "success",
  "filename": "analysis_summary_20260812_091500.csv",
  "path": "/app/exports/analysis_summary_20260812_091500.csv"
}
```

## 11. Catatan Penting

Endpoint async analysis yang ada di implementation plan berikut **belum tersedia di code backend Crawler System saat ini**:

```http
POST /api/integration/v1/analysis-jobs
GET /api/integration/v1/analysis-jobs/{analysis_batch_id}
```

Jadi untuk testing Postman sekarang, gunakan endpoint yang sudah executable:

1. `POST /api/analysis/reviews/{review_id}/rerun`
2. `GET /api/reviews/{review_id}`
3. `POST /api/analysis/pending`
4. `POST /api/analysis/locations/{location_id}/rerun`
5. `POST /api/analysis/rollback`
6. `GET /api/analysis/quality-summary`

Untuk flow satu ulasan, urutan minimum adalah:

```text
Login -> GET 1 review -> POST rerun analysis 1 review -> GET detail review
```
