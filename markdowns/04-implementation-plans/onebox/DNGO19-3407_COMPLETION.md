# DNGO19-3407 — VoC Enhance AI Analysis

## Hasil akhir

| PBI | Implementasi |
|---|---|
| Ganti dummy data dan simulasi Analyze | OneBox `Voc/insightsData` membaca review/hasil AI nyata; tombol Analysis memanggil Crawler. |
| Baseline durasi dan kualitas | Setiap run melaporkan `duration_ms`, panggilan/retry/waktu LLM, token, hasil valid/dikoreksi, concurrency, serta structured log. |
| API flow, dedup, batching, concurrency, retry, backoff | Pending query mengabaikan review yang sudah memiliki analysis, batch dibatasi, LLM call berjalan paralel secara bounded, database write tetap serial, retry memakai exponential backoff. |
| Monitoring, fallback, rollback | Quality summary, circuit breaker, rating-only fallback, status gagal yang aman, dan rollback per model tersedia dari Crawler dan OneBox. |

## Kredensial: gunakan Fetch Jobs yang sudah ada

OneBox tidak membutuhkan `Connection.UserId/Password` untuk analysis ketika
Connection sudah memakai:

```json
{
  "api_mode": "service",
  "service_token": "<token Fetch Jobs yang sudah tersimpan>"
}
```

Token tersebut perlu scope `analysis:write`. Scope dapat ditambahkan tanpa
rotasi dan tanpa mengubah secret:

```sh
python -m scripts.manage_api_client grant-scope \
  --key-id EXISTING_KEY_ID \
  --scope analysis:write
```

OneCloud memprioritaskan service token yang sama dengan Fetch Jobs. Akun user
tetap menjadi fallback kompatibilitas untuk instalasi lama.

## Concurrency yang aman

```dotenv
ANALYSIS_BATCH_SIZE=20
ANALYSIS_LLM_CONCURRENCY=4
ANALYSIS_LLM_MAX_RETRIES=2
ANALYSIS_LLM_RETRY_BACKOFF_SECONDS=1.0
ANALYSIS_CIRCUIT_BREAKER_THRESHOLD=5
```

Hanya request jaringan ke LLM yang paralel. Validasi output dan transaksi
`ReviewAnalysis`/`Review.sync_updated_at` tetap dilakukan serial agar riwayat
append-only, dedup, rollback, dan delta-sync tetap konsisten.

## Endpoint service-token

- `POST /api/integration/v1/analysis/pending`
- `POST /api/integration/v1/analysis/reviews/{review_id}/rerun`
- `GET /api/integration/v1/analysis/quality-summary`
- `POST /api/integration/v1/analysis/rollback`

Semua tenant berasal dari token; request tidak dapat memilih `company_id`.

## Verifikasi

```sh
python -m pytest tests/test_service_auth.py tests/test_integration_analysis.py tests/test_mvp.py -q
python -m pytest -q
```

Di OneCloud jalankan pemeriksaan `onecloud/tests/voc/`, terutama lint PHP,
permission map, schema, ruling, dan `volt_compile_check.php`.
