# Plan - Major Refactor (Repo-Wide)

Status: In progress - R1-R11 landed on `dev`, not yet merged to `main`
Owner utama: Crawler System
Pairing: roadmap owner untuk keputusan R1; OneBox team hanya jika kontrak integrasi tersentuh
Reviewed: 2026-09-04 terhadap branch `staging` @ `0c3c1b3` (models, services, API layer, config, tests)
Shareable version: Artifact `https://claude.ai/code/artifact/b3d7d92a-1c3a-4d8f-9730-99bee91168a6`

### Progress (2026-09-06)

Semua di branch `dev`, satu commit/merge per finding. Belum di-merge ke `main`.

| Finding | Status | Catatan |
| --- | --- | --- |
| R1 auth unification | done | FE/JWT routers + terminal dipensiun; `company_id` diturunkan dari principal. `main.py` + terminal disimpan untuk console-read. |
| R2 split CrawlJobService | done | `crawl_queue.py` / `crawl_worker.py` / `crawl_batch_view.py`. |
| R3 result schema | done | `crawl_result.py` TypedDicts + accessor. |
| R4 CrawlTarget | done | Service-layer only; penggabungan tabel review ditunda. |
| R5 split Selenium client | done | `google_maps_review_parser.py` murni + fixture tests. |
| R6 pydantic-settings | done | `Settings(BaseModel)` + `_EnvSettings(Settings, BaseSettings)`; port datar. |
| R7 request-scoped session | done | Satu slice (`SummaryService` + `SummaryRepository`); sisa service menyusul per-round. |
| R8 dependency hygiene | done | `firecrawl-py`/`pandas`/`webdriver-manager`/`google-genai`/`google-auth` dibuang; lock di-pin penuh. |
| R9 one LLM stack | done | `LocalLLMClient` + `MockGeminiClient` di balik `GeminiClientBase`; `OpenRouterClient` + `GeminiClient` dihapus. |
| R10 Postgres queue tests | done | `test_postgres_concurrency.py`; CI dapat service `postgres:16`. |
| R11 smaller cleanups | done | `datetime.utcnow()` sudah nihil; konvensi bahasa + layout `app/`/`apps/` di `CLAUDE.md`; `PROJECT_STATUS.md` ditandai basi. |

Sisa (di luar scope plan ini): perluas request-scoped session R7 ke ~9 service lain;
evaluasi penggabungan tabel `Review`/`CompetitorReview` (R4 tahap 2).

## Goal

Menurunkan ukuran dan kompleksitas codebase agar sesuai dengan bentuk sistem yang sebenarnya - crawler headless yang dikendalikan OneBox - lalu merapikan masalah struktural di kode yang tetap tinggal.

## Non Goal

- Tidak mengganti engine database. Pertanyaan Supabase -> MySQL (ADR-0004) jalur terpisah dengan runbook sendiri.
- Tidak membangun fitur multi-tenant "tarik daftar tenant dari OneBox" (SPEC-multi-tenant-opsi-c). Itu fitur, bukan refactor - tapi R1 dan R7 membuatnya lebih murah dikerjakan setelahnya.
- Tidak mengubah kontrak `/api/integration/*` yang sudah dipakai OneBox.
- Tidak menambah rule sentiment atau logika analisa baru.

## Keputusan yang menggerbang seluruh plan

[ADR-0001](../../decisions/ADR-0001-ownership-inversion.md) (#4, #5) sudah memutuskan: auth `User`/`Company` milik VoC diturunkan jadi service account saja, dan FE Next.js dipensiunkan. [PROJECT_STATUS](../../PROJECT_STATUS.md) masih menandai keduanya belum selesai.

Setiap item Tier 2 mengecil setelah lapisan itu hilang. **Langkah pertama plan ini adalah konfirmasi keputusan tersebut ke roadmap owner.** Kalau produk standalone ternyata dipertahankan, R1 berubah dari "hapus" jadi "isolasi di balik batas paket", dan estimasi di bawah bergeser.

Skala: ~17.9k baris Python total, ~2.8k kandidat dihapus, 11 file test / 116 test case.

---

## Tier 1 - The major refactor

### R1 - Collapse the standalone-product layer

Effort: M · Risiko: rendah (jika keputusan bertahan)

Codebase membawa produk SaaS lengkap di samping crawler: auth user/password sendiri, REST API untuk browser, dan terminal app berbasis `rich`. Semuanya jalur paralel terhadap jalur nyata - OneBox autentikasi sebagai `ApiClient` dan memanggil route `/api/integration/*`.

Bukti:

- `apps/api/app_api/routers/` - `auth`, `locations`, `reviews`, `dashboard`, `places`, `settings`, `pipeline`, `exports` (783 LOC) adalah route FE-JWT.
- `app/terminal/` - 11 file, 1033 LOC. `app/services/__init__.py` masih tertulis "services used by the terminal interface".
- `apps/api/app_api/dependencies.py` - `create_access_token`, `get_current_user`, `OAuth2PasswordBearer`, plus `User.password_hash` dan dependency `passlib[bcrypt]` / `bcrypt` / `python-multipart` hanya untuk flow login itu.
- `company_id: int` adalah parameter yang dioper tangan di 27 signature service, karena dua model auth memberinya.

Perubahan:

- Konfirmasi pensiun ke roadmap owner. Lalu hapus `app/terminal/`, `main.py`, delapan FE router, separuh user-auth dari `dependencies.py`, dan model `User`. Pertahankan `health`, `fetch_jobs`, dan semua router `integration_*`.
- Turunkan `company_id` dari `ApiClient` yang terautentikasi di satu dependency; buang dari constructor service di mana ia jadi redundan.

Risiko: rendah jika keputusan bertahan. Permukaan integrasi punya contract test sendiri (`test_integration_api_contract.py`). Bahaya utama: helper bersama di `schemas.py` yang dipakai dua permukaan - grep dulu sebelum memotong.

Inventaris lapisan standalone:

| Surface | Lokasi | LOC | Disposisi |
| --- | --- | --- | --- |
| Terminal app | `app/terminal/` + `main.py` | 1033 | Hapus |
| FE-JWT routers | `routers/{auth,locations,reviews,...}` | 783 | Hapus |
| User auth plumbing | `app_api/dependencies.py` | ~70 | Kecilkan jadi ApiClient |
| User model + hashing | `db/models.py`, `utils/hashing.py` | ~40 | Hapus |
| Integration API | `routers/integration_*.py` | 759 | Pertahankan |

---

## Tier 2 - Structural (kode yang tetap tinggal)

### R2 - Break up the 1116-line CrawlJobService

Effort: L · Risiko: sedang

Satu class memegang tiga komponen dengan alasan berubah yang tak berkaitan: admission antrean, siklus hidup worker, dan pembentukan response API.

Bukti - `app/services/crawl_job_service.py`:

- `enqueue` + `request_fingerprint` + idempotency (admission)
- `claim_next` / `execute_next` / `_retry_or_fail` / `_finish` + lease (execution)
- `_serialize_batch` dan enam static helper, ~250 LOC (presentation)

Perubahan: pecah jadi `CrawlQueue` (admission + fingerprinting), `CrawlWorker` (claim / execute / retry / lease), dan serializer `BatchView`. Akses row bersama lewat `CrawlRepository` tipis (lihat R7).

Risiko: sedang. Logika lease / `skip_locked` halus dan kurang teruji (R10) - kerjakan R10 dulu supaya split ini punya jaring pengaman.

### R3 - Give result_json a defined schema

Effort: M · Risiko: rendah

Blob hasil job adalah kontrak implisit yang dibaca dengan menggali. Tak ada tipe yang mendefinisikannya; Selenium client menulisnya dan tiga service menebak key-nya.

Bukti: `_serialize_batch` penuh rantai fallback `result.get("total_fetched") or result.get("progress_fetched") or metadata.get("loaded_review_cards") or ...`. `_rating_snapshot`, `_public_stop_reason`, dan `_batch_stop_reasons` masing-masing mem-parse ulang dict bersarang yang sama.

Perubahan: definisikan `CrawlResult` / `CrawlResultMetadata` sebagai dataclass atau `TypedDict` di satu modul. Satu penulis di fetch service yang mengisinya; pembaca mengonsumsi field bertipe. Kolom JSON tetap, validasi di batas.

Risiko: rendah. Aditif - bentuk yang tersimpan tak perlu berubah, hanya cara kode membacanya.

### R4 - Model "crawl target" once, not location vs competitor twice

Effort: L · Risiko: sedang-tinggi (jika tabel digabung), rendah (jika hanya service layer) · Nilai: tinggi

Location dan competitor adalah copy-paste, bukan abstraksi. Dua jalur sudah menyimpang di hal-hal kecil yang hampir pasti bug laten.

Bukti:

- `selenium_fetch_service.py` mengirim adapter `_CompetitorAsLocation`, lalu `fetch_location` dan `fetch_competitor` menjalankan ~170 baris nyaris identik masing-masing.
- `crawl_job_service.py` `enqueue` punya blok resolusi dan pembuatan job location / competitor yang paralel.
- `db/models.py` - `Review` dan `CompetitorReview` adalah model ~50 kolom yang beda hanya di target FK dan `analysis_status`.

Perubahan: kenalkan value object `CrawlTarget`: `kind`, `external_place_id`, `target_review_count`, dan sink review. Resolusi, pembuatan job, dan fetch masing-masing menerima satu `CrawlTarget`. Evaluasi penggabungan dua tabel review di balik discriminator nullable, atau minimal mixin bersama. Kerjakan versi service-layer dulu.

### R5 - Split the 939-line Selenium client

Effort: M · Risiko: rendah

Satu class, 40 method, mencampur siklus hidup driver, resolusi URL, scroll DOM, ekstraksi / parsing, penanganan consent, dan sorting. Separuh parsing murni dan bisa diuji tapi tak bisa dicapai tanpa browser.

Bukti - `app/integrations/selenium_google_maps_client.py`: `_create_driver` / `_open_review_panel` / `_find_scroll_container` (session) berdampingan dengan `_extract_review` / `_parse_place_rating` / `_parse_reviewer_total_reviews` (murni).

Perubahan: ekstrak `GoogleMapsReviewParser` yang menerima teks elemen dan mengembalikan review bertipe, tanpa import Selenium. `SeleniumGoogleMapsReviewClient` tetap jadi shell driver + navigasi yang memberinya makan. Tambah test parser berbasis fixture.

Risiko: rendah. Ekstraksi sudah di method-method terpisah; ini pemindahan, bukan penulisan ulang.

### R6 - Replace hand-rolled config with pydantic-settings

Effort: S · Risiko: rendah-sedang

`Settings` adalah frozen dataclass 60 field dengan `get_settings()` sepanjang 150 baris yang mem-parse env manual lewat helper buatan sendiri `_as_int` / `_as_bool` / `_as_float` / `_as_optional_int` / `_as_list`. `pydantic 2.10` sudah jadi dependency.

Bukti: `app/config.py` baris 138-287 - parsing, clamping per-field (`min` / `max`), dan validasi secret bergerbang-environment semuanya manual.

Perubahan: tambah `pydantic-settings`. Model field dengan validator untuk clamp; model bersarang untuk `onebox.*`, `selenium.*`, `analysis.*`. `get_settings()` tetap jadi accessor yang di-cache. Lakukan port datar 1:1 dulu, bersarang belakangan.

### R7 - One session per request, not one per method

Effort: M · Risiko: sedang

Setiap method service membuka `with self.session_factory() as session:` sendiri. Satu request yang menyentuh tiga service membuka tiga transaksi independen tanpa batas konsistensi, dan tak ada lapisan repository antara service dan ORM.

Bukti: `api_client_service.py` membuka session di 6 method; `location_service.py` di 6; `crawl_job_service.py` di 8. Dependency `get_db_session` FastAPI ada di `dependencies.py` tapi service tak pernah menerimanya.

Perubahan: oper `Session` ber-scope request ke service (constructor atau method). Pindahkan statement `select()` mentah ke balik objek repository kecil supaya split god-class di R2 punya sesuatu yang bersih untuk dipanggil. `session_factory` tetap untuk worker dan script yang memiliki siklus hidupnya sendiri.

---

## Tier 3 - Cleanup (risiko rendah, kerjakan berbarengan)

### R8 - Dependency hygiene

Effort: S · Risiko: rendah

`requirements.txt` mencantumkan `PyJWT`, `passlib`, `email-validator`, dan `python-multipart` dua kali masing-masing, dan membawa beban kemungkinan mati.

Bukti: baris duplikat di separuh bawah `requirements.txt`. Kandidat dihapus: `firecrawl-py`, `pandas`, `webdriver-manager`, `tabulate` (terminal-only), dan `requests` (codebase juga bergantung pada `httpx`).

Perubahan: jalankan `deptry` / `pip-audit`, dedupe, buang yang tak dipakai, pisahkan `requirements-dev.txt` (pytest, ruff) dari runtime. Verifikasi terhadap import sebelum menghapus.

### R9 - Settle on one LLM client stack

Effort: S · Risiko: rendah

Dua stack paralel: `gemini_client` + `mock_gemini_client` + dependency `google-genai`, versus `local_llm_client` + `openrouter_client` + dependency `openai`. `AnalysisService` default ke `LocalLLMClient`.

Bukti: `app/integrations/` - `gemini_client.py`, `mock_gemini_client.py`, `local_llm_client.py`, `openrouter_client.py`. Constructor `analysis_service.py` mewire `LocalLLMClient` sebagai default dan fallback.

Perubahan: pilih stack yang cocok dengan cara analisa benar-benar jalan di prod. Pertahankan satu client + mock-nya di balik interface `GeminiClientBase`; hapus yang lain beserta dependency-nya.

### R10 - Run the queue tests on Postgres

Effort: M · Risiko: rendah, nilai tinggi · Kerjakan sebelum R2

Setiap test pakai `sqlite+pysqlite:///:memory:`. Prod adalah Supabase Postgres. SQLite diam-diam mengabaikan `SELECT ... FOR UPDATE SKIP LOCKED` - jadi mekanisme inti durable crawl queue dan jalur concurrent-analysis diuji oleh nol test.

Bukti: `with_for_update(skip_locked=True)` di `crawl_job_service.py:654`; `with_for_update()` di `analysis_service.py:545` dan `:594`. Semua fixture membangun engine SQLite (`test_mvp.py:30`, `test_integration_delta_sync.py:44`, dan sisanya). JSONB, partial unique index (`uq_crawl_jobs_batch_competitor`), dan cascade `ondelete` juga berperilaku beda atau tidak sama sekali di SQLite.

Perubahan: tambah session test berbasis Postgres (testcontainers atau service CI) untuk minimal race worker-claim dan lock analisa. SQLite tetap untuk pass unit cepat. Mulai file unit test per-service alih-alih menumbuhkan `test_mvp.py` (786 LOC).

### R11 - Smaller cleanups

Effort: S · Risiko: rendah

- **Deprecated datetime** - `datetime.utcnow()` di `dependencies.py` (dua kali); sisa codebase pakai `datetime.now(timezone.utc)`.
- **Bahasa komentar** - Indonesia dan Inggris bercampur dalam satu file (`crawl_job_service.py`, `config.py`). Tak apa jika disengaja; pilih satu untuk kode baru dan catat di `CLAUDE.md`.
- **app/ vs apps/** - split dua root (`app/` library, `apps/api/` FastAPI) masuk akal tapi tak terdokumentasi; satu baris README menghemat tebakan pembaca berikutnya.
- **PROJECT_STATUS drift** - bertanggal 2026-07-24, mendahului kerja window-aware crawl dan rating-snapshot. Segarkan atau tandai basi.

---

## Suggested sequence

Diurutkan untuk keamanan dan leverage yang menumpuk - tiap langkah mengecilkan langkah berikutnya. Semua langkah bergerbang keputusan R1.

1. **Putuskan pertanyaan lapisan standalone.** Roadmap owner konfirmasi pensiun FE + terminal. Ya -> R1 jadi hapus; tidak -> R1 jadi "isolasi di balik batas paket" dan plan di-rescope.
2. **R1 - hapus atau isolasi lapisan standalone.** Reduksi terbesar, risiko terendah. Mengecilkan permukaan yang disentuh tiap langkah berikutnya. (`app/terminal/`, `routers/{auth,locations,...}`, `dependencies.py`)
3. **R10 - jalur test Postgres.** Bangun jaring pengaman sebelum merestrukturisasi antrean. (`tests/` fixtures)
4. **R3 - definisikan result_json.** Hasil bertipe membuka split serializer bersih di R2. (baru: `app/services/crawl_result.py`)
5. **R2 - pecah CrawlJobService.** Queue / worker / view, di atas jaring R10 dan tipe R3. (`app/services/crawl_job_service.py`)
6. **R4 - abstraksi CrawlTarget.** Scope service-layer dulu; tunda penggabungan tabel review. (`selenium_fetch_service.py`, `crawl_job_service.py`)
7. **R7 - session ber-scope request + repository.** Lebih mudah setelah R1 menipiskan daftar service dan R2 mendefinisikan jahitan.
8. **R6 - pydantic-settings.** Port datar, lalu bersarang. (`app/config.py`)
9. **R5 - pecah Selenium client.** Parser keluar, fixture masuk. Independen - bisa maju lebih awal jika bug scraper memaksa.
10. **R8 / R9 / R11 - hygiene.** Isi kapasitas luang sepanjang jalan; tak ada yang memblokir yang lain.

## Catatan estimasi

- `S` ~ di bawah sehari · `M` ~ 1-3 hari · `L` ~ seminggu lebih dengan review.
- Mengasumsikan workflow delegate-ke-Codex, satu finding per branch.
- Tiap finding di-scope untuk mendarat sebagai PR sendiri dengan contract test yang ada tetap hijau.
