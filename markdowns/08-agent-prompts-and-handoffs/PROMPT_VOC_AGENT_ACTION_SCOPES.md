# Prompt untuk AI agent VoC System — kirim apa adanya

> Konteks: VOC-CS-03 sudah selesai dan OneBox sudah menarik review lewat
> `GET /api/integration/v1/reviews` dengan service token. Sekarang OneBox perlu
> **memicu** crawling dan analisis, bukan cuma membaca hasilnya.
> Salin blok di bawah ini ke agent yang pegang repo `herminaCrawler`.

---

Ada empat hal, diurutkan dari yang paling mendesak.

## 1. `LOCAL_LLM_MODEL` di staging menunjuk model yang tidak ada — analisis AI mati total

Ini bug produksi, bukan permintaan fitur. `GET /api/settings` di staging melaporkan
`local_llm_model: "qwen2.5:7b"`, tetapi server Ollama di `192.168.1.115:11434`
**tidak punya model itu**. Buktinya:

```
POST /api/analysis/reviews/88/rerun
→ {"total":1,"success":0,"failed":1,
   "errors":[{"review_id":88,
              "error":"Error code: 404 - model 'qwen2.5:7b' not found"}]}
```

Ollama-nya sendiri hidup dan sehat (36 model terpasang). Yang tersedia dan relevan
antara lain `qwen3.5:9b`, `gemma2:9b`, `mistral:instruct`, `llama3.2:1b`
(sudah saya tes, merespons normal).

Tolong pilih salah satu: `ollama pull qwen2.5:7b` di server itu, **atau** set
`LOCAL_LLM_MODEL` ke model yang memang ada lalu redeploy. Mana pun boleh, asal
`POST /api/analysis/*` berhenti gagal.

Akibat sekarang: 2 review (id 88 dan 109, dua-duanya rating 1 di HGA Depok) masih
`analyzed=false` dan tidak bisa dianalisis ulang.

## 2. Prompt kategorisasi tidak diskriminatif — 73 dari 75 review masuk satu kategori

Dari 18 slug `IssueCategory` yang tersedia, AI memilih **satu** untuk hampir semua
review:

| Kategori | Jumlah |
|---|---|
| `doctor_service` | 73 |
| (belum dianalisis) | 2 |

Ini membuat panel "Top Issue" di OneBox tidak bermakna — satu batang penuh, tanpa
perbandingan. Dimensi lain justru sehat (`urgency`: low 46 / medium 10 / high 17;
sentiment: positive 46 / negative 27), jadi masalahnya spesifik di kategorisasi.

Tolong periksa prompt di `app/services/analysis_service.py`: apakah daftar kategori
benar-benar dikirim ke model beserta definisi tiap slug, dan apakah modelnya cukup
besar untuk memilih di antara 18 opsi. Kalau memungkinkan, tambahkan evaluasi kecil
(10–20 review yang sudah diberi label manual) supaya perbaikan prompt bisa diukur,
bukan ditebak.

## 3. Endpoint aksi belum bisa dipakai service token

`fetch_jobs`, `analysis`, `pipeline`, dan `fetch_logs` semuanya masih
`Depends(get_current_user)` — hanya JWT user. Akibatnya OneBox tidak bisa memicu
crawling atau analisis, padahal untuk membaca review sudah punya service token.

Yang diminta: terima service token **sebagai alternatif**, bukan pengganti —
FE VoC masih memakai `get_current_user` dan tidak boleh rusak.

| Endpoint | Scope yang diusulkan |
|---|---|
| `POST /api/fetch-jobs`, `/api/fetch-jobs/all-active` | `fetch:write` |
| `POST /api/analysis/*` | `analysis:write` |
| `POST /api/pipeline/location` | `fetch:write` + `analysis:write` |
| `GET /api/fetch-logs`, `/api/fetch-logs/latest` | `fetch_logs:read` |

Pola pengecekannya sudah ada dan tinggal ditiru dari
`apps/api/app_api/routers/integration_reviews.py:137`:

```python
if REQUIRED_SCOPE not in principal.scopes:
    raise IntegrationRequestError(403, "INSUFFICIENT_SCOPE", "...")
```

Syarat penting: `company_id` harus tetap diambil dari principal/token, **jangan
pernah** dari body atau query. Token company A tidak boleh bisa memicu crawl atau
membaca fetch-log milik company B, termasuk lewat `location_id` yang ditebak.

Kalau ini jadi, tolong beri tahu apakah token yang sudah saya pakai sekarang bisa
ditambah scope-nya, atau saya perlu menerbitkan token baru.

## 4. Dugaan celah tenant di `pipeline.py`

Di `apps/api/app_api/routers/pipeline.py:73`:

```python
fetch_result = SeleniumFetchService().fetch_location(...)
```

`SeleniumFetchService()` dipanggil **tanpa** `company_id`, padahal di
`apps/api/app_api/routers/fetch_jobs.py:85` jalur yang setara memanggilnya dengan
`SeleniumFetchService(company_id=current_user.company_id)`.

Saya belum menelusuri isi service-nya, jadi ini dugaan, bukan temuan pasti. Tolong
dicek: apakah tanpa `company_id` service itu jatuh ke default/global yang bisa
menulis review ke company lain? Kalau iya, itu bug tenant yang lebih serius
daripada tiga poin di atas.

---

## Catatan buat kita sendiri (jangan ikut dikirim)

- Poin 1 dan 2 **memblokir demo**. Poin 3 hanya membuka fitur tambahan
  (tombol crawl/analisis dari OneBox); tanpa itu demo tetap bisa jalan dengan
  tombol "Tarik Review Sekarang" yang sudah ada di OneBox.
- Crawler selenium sendiri terpisah masalahnya: 6 dari 8 run terakhir gagal
  (`Review container was not found`, browser crash) dan `selenium_headless: false`.
  Meski poin 3 selesai, memicu crawl live saat demo tetap berisiko tinggi.
