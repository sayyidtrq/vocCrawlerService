---
title: Multi-Tenant Readiness — Implementation
aliases:
  - MT Implementation
tags:
  - voc
  - multitenant-readiness
  - implementation
status: not-started
updated: 2026-10-21
owner: Sayyid
decision: opsi-D-push-worklist
related:
  - "[[README]]"
  - "[[01-PLAN]]"
  - "[[02-DESIGN]]"
  - "[[04-OPEN-QUESTIONS]]"
  - "[[local-dev-setup-guide]]"
  - "[[SAYYID_TASK_BREAKDOWN]]"
---
# Multi-Tenant Readiness — Implementation

> [!abstract] Navigasi
> [[README|Index]] · [[01-PLAN|Plan]] · [[02-DESIGN|Design]] · [[03-IMPLEMENTATION|Implementation]] · [[04-OPEN-QUESTIONS|Open Questions]]

Konvensi: satu task = satu PR ke `dev` (atau turunan `feature/multitenant-readiness`). Kode English, komentar boleh Indonesia, timestamp `datetime.now(timezone.utc)` (`CLAUDE.md`). Contract test integrasi (`tests/test_integration_api_contract.py`) wajib tetap hijau.

> [!note] Riwayat ID
> ID dinomori ulang sekali (2026-10-21, model provisioning paket VoC). Setelah keputusan **opsi D** (OneBox push worklist) ID **tidak** dinomori ulang lagi: task yang usang ditandai `dropped`, task yang berubah isi diberi catatan *(diubah: opsi D)*.

---

## Ringkasan task

| ID | Task | Sisi | Fase | Prasyarat | Status |
|---|---|---|---|---|---|
| MT-01 | ADR-0006: provisioning paket VoC + push worklist (amandemen ADR-0003 D1) + round robin | Keputusan | 0 | Q-25, Q-23 | `todo` |
| MT-02 | Guard interim: refresh on-demand tidak boleh lintas tenant | Crawler | 0 | — | `done` (belum di-commit) |
| MT-03 | Inventaris kode OneBox (paket VoC, Connection, queue, Setup Parameter) | OneBox (baca) | 0 | repo OneBox ter-clone | `wip` (putaran 1 selesai) |
| MT-10 | Migration `companies` (`onebox_site_id`, `is_active`, `deactivated_at`) + `worklist_sync_states` (`snapshot_version`, `applied_at`) | Crawler | 1 | — | `done` (SQLite; Postgres belum diuji) |
| MT-11 | Mode config `ONEBOX_TENANT_MODE=single\|managed` | Crawler | 1 | MT-10 | `done` (belum di-commit) |
| MT-12 | ~~Client pull per site~~ | Crawler | 1 | — | `dropped` (opsi D) |
| MT-13 | `WorklistSyncService.apply_snapshot` + `snapshot_version` *(diubah: opsi D)* | Crawler | 1 | MT-10, Q-33 | `done` (SQLite; belum di-commit) |
| MT-20 | Endpoint provisioning tenant (`POST/PATCH/GET /tenants`, rotate) | Crawler | 2 | MT-10 | `done` (SQLite; belum di-commit) |
| MT-21 | Endpoint `PUT /worklist` *(diubah: opsi D)* | Crawler | 2 | MT-13, MT-20 | `done` (SQLite; belum di-commit) |
| MT-22 | Hapus jalur pull & refresh on-demand, hapus kredensial OneBox dari crawler | Crawler | 2 | MT-21, transisi selesai | `todo` |
| MT-23 | Tenant nonaktif: batalkan job yang belum jalan, tolak enqueue & push, ajari logika batch status `cancelled` | Crawler | 2 | MT-10 | `todo` |
| MT-30 | Hook aktivasi/deaktivasi VoC → provisioning via outbox | OneBox | 3 | MT-20, Q-35, Q-36, Q-29, Q-32 | `blocked` (Q-35) |
| MT-31 | Setup Parameter: status & versi sinkron, token ter-mask, Refresh, Regenerate, bobot (preseden UI: `locationResyncAction`) | OneBox | 3 | MT-30, Q-28 | `blocked` |
| MT-32 | Builder snapshot worklist per site: bungkus `VocWorklist::forSite` + counter versi *(diubah: opsi D)* | OneBox | 3 | MT-03 ✔ putaran 1, Q-33 | `todo` |
| MT-33 | **Outbox** push worklist (tabel DB + task cron, atau RabbitMQ): retry, debounce, status + hook simpan cabang/kompetitor; ganti jalur `provisionLocation` lama *(diubah: opsi D)* | OneBox | 3 | MT-21, MT-32, Q-32 | `blocked` (Q-32) |
| MT-34 | ~~Akses akun layanan ke site~~ | OneBox | 3 | — | `dropped` (Q-27) |
| MT-35 | Scheduled push + cek ketinggalan versi & status paket | OneBox | 3 | MT-33 | `blocked` |
| MT-40 | Weighted round robin di `claim_next` (+ kolom `companies.weight`, index `crawl_jobs`) | Crawler | 4 | MT-10, Q-26 | `blocked` (Q-26) |
| MT-41 | Atribusi pemakaian Apify per tenant (akun Apify tunggal milik platform) | Crawler | 4 | MT-10 | `todo` |
| MT-42 | Observability per tenant | Crawler | 4 | Q-22 | `todo` |
| MT-43 | ~~Refresh periodik di crawler~~ | Crawler | 4 | — | `dropped` (pindah ke MT-35) |
| MT-44 | Setting tenant/lokasi dipakai analisa (+ kolom penyimpan setting; bentuknya ikut rencana taksonomi) | Crawler | 4 | MT-20, Q-30 | `blocked` (Q-30) |
| MT-50 | Test matrix multi-tenant | Crawler | 5 | bertahap | `todo` |
| MT-51 | UAT dev: site 169 + site 177 | Ops | 5 | Fase 3 | `blocked` |
| MT-52 | Runbook onboarding ("aktifkan paket VoC") + darurat | Docs | 5 | MT-51 | `todo` |

---

## Fase 0 — Keputusan & pengamanan

### MT-01 — ADR-0006
- **Output:** `markdowns/decisions/ADR-0006-multi-tenant-voc-package-provisioning.md`. Isi: OneBox control panel; tenant hidup/mati lewat paket VoC; provisioning token; satu site = satu company; **push snapshot worklist (amandemen ADR-0003 D1)** beserta alasan dan opsi A/B/C yang ditolak/cadangan; weighted round robin.
- **Menggantikan:** `SPEC-multi-tenant-opsi-c.md` (banner SUPERSEDED di 5 baris pertama); header `BRAINSTORM-multi-tenant-voc.md` → "selesai, lihat ADR-0006"; pointer di ADR-0003 §D1. Daftarkan di `integrations/MUST_READ.md`.
- **Selesai bila:** ADR berstatus Accepted (internal), Q-25 terjawab; ratifikasi Pak Agung dilacak di Q-23.

### MT-02 — Guard interim refresh on-demand
- **Status: `done` (2026-10-21), belum di-commit.** Full suite: 249 lulus, 2 gagal (sama dengan baseline, bukan regresi), 2 di-skip.
- **Kenapa:** site 177 sudah ada di dev. Selama mode `single` (pull) masih dipakai, bahaya [[02-DESIGN#2.4 Bahaya laten yang sudah ada hari ini]] bisa terjadi begitu site 177 punya company & token.
- **Yang diubah:**
  - `app/services/worklist_sync_service.py` — `WorklistTenantMismatchError` (subclass `WorklistSyncError`) + `_require_company_owns_site` di awal `refresh()`: company ≠ `ONEBOX_COMPANY_ID` ditolak **sebelum** menghubungi OneBox dan **tanpa** menulis `WorklistSyncState` untuk company itu. Bila `ONEBOX_COMPANY_ID` kosong guard tidak aktif (jalur otomatis tidak terbentuk tanpa `is_configured`; CLI dengan `--company-id` eksplisit tetap diperbolehkan).
  - `app/services/crawl_queue.py` — `_refresh_worklist_once` memakai `settings=self.settings` (sebelumnya `is_configured` memeriksa `self.settings` tapi refresh memakai `get_settings()` global).
  - `app/services/fetch_service.py` — mismatch → `{"status": "skipped_foreign_tenant"}`, crawl lanjut dengan lokasi yang ada (bukan gagal total).
  - `apps/api/app_api/routers/integration_analysis.py` — `except Exception: pass` diganti log warning; hasil tetap `LOCATION_NOT_FOUND`.
- **Test** (`tests/test_worklist_sync.py`, 5 baru, T8/T9): company asing ditolak tanpa panggil OneBox dan tanpa menyentuh lokasinya; mismatch adalah `WorklistSyncError`; auto-refresh enqueue tidak menyentuh company asing; fetch lanjut dengan status skip; company pemilik tetap sinkron normal. **Mutation check:** guard dimatikan → 3 test kunci gagal.
- **Umur:** dihapus bersama jalur pull-nya di MT-22.


### MT-03 — Inventaris OneBox
- **Status:** putaran 1 selesai (2026-10-21), putaran 2 menunggu. Repo: WSL `onebox`, `/var/www/html/onecloud`, branch `feature/DNGO19-3549_VOC-AI-Ticket-Entitlement`.
- **Hasil putaran 1** (detail: [[04-OPEN-QUESTIONS#Q-31]], [[04-OPEN-QUESTIONS#Q-32]]):
  - `VocWorklist::forSite($siteId)` sudah menjadi builder worklist → MT-32 cukup membungkusnya jadi snapshot + versi.
  - Tidak ada outbox untuk panggilan keluar (retry hanya 2x dalam request) → MT-33 harus membangun outbox.
  - Benefit VoC ada enam, tidak ada satu "paket VoC" → [[04-OPEN-QUESTIONS#Q-35]] sebelum MT-30.
  - Token baca ada per Connection (`Options.service_token`) → [[04-OPEN-QUESTIONS#Q-36]].
  - Jalur provisioning push lama (`provisionLocation`, `locationResyncAction`) masih ada → diganti di MT-30/33.
- **Putaran 2 (sisa):** `VocTargetRegistry`/`VocTarget`, eksekusi `VocSchedule` oleh cron, halaman Setup Parameter dan tombol Refresh, ketersediaan RabbitMQ per environment.
- **Selesai bila:** Q-31 dan Q-32 terjawab penuh.

---

## Fase 1 — Fondasi crawler

### MT-10 — Migration
- **Status: `done` di SQLite (2026-10-22), belum di-commit.** Migration up/down belum dibuktikan di Postgres.
- **File:** `app/db/models.py` (`Company`, `WorklistSyncState`), `alembic/versions/20261022_0012_tenant_registry.py` (revisi `20261022_0012`, setelah `20261001_0011`), `tests/test_tenant_registry_schema.py`.
- **`companies`:** `onebox_site_id INTEGER NULL` + unique index `uq_companies_onebox_site` (NULL boleh berulang), `is_active BOOLEAN NOT NULL DEFAULT true`, `deactivated_at TIMESTAMPTZ NULL`.
- **`worklist_sync_states`:** `snapshot_version BIGINT NULL`, `applied_at TIMESTAMPTZ NULL`.
- **Backfill** (`backfill_onebox_site_id`): isi `onebox_site_id` dari `worklist_sync_states.site_id` **hanya bila tidak ambigu** — site yang muncul di lebih dari satu company tidak ditebak (dicatat sebagai warning), dan site yang sudah ditautkan ke company lain dilewati. Tidak menimpa tautan yang ada, aman dijalankan ulang. Indeks unik dibuat **setelah** backfill.
- **Sengaja tidak ada di MT-10** (bentuknya belum pasti, migration mahal diubah): `companies.weight` → MT-40 (Q-26); setting tenant → MT-44 (Q-30, taksonomi per lokasi); `crawl_jobs.cancel_reason` dibuang (pakai `last_error_code`); index `crawl_jobs (company_id, status, available_at)` → MT-40; status `cancelled` tidak butuh migration (kolom `status` tanpa constraint) tetapi butuh kode di MT-23.
- **Test (12, SQLite):** default model, unik per site, NULL tidak bertabrakan, `snapshot_version` 64-bit; migration: head tunggal setelah 0011, kolom ditambah dan company lama tetap aktif, backfill hanya yang jelas, backfill idempoten dan tidak menimpa tautan manual, tidak menabrak indeks unik, downgrade mengembalikan bentuk lama tanpa kehilangan data, **kolom hasil migration sama dengan model**. Mutation check: tanpa aturan "jangan tebak yang ambigu", migration **crash** `UNIQUE constraint failed` (6 test gagal) — risiko nyata di deploy.
- **Dampak deploy dev:** semua aditif dengan default dan belum dibaca kode, jadi perilaku tidak berubah. `entrypoint.sh` menjalankan `alembic upgrade head` saat container start, jadi migration jalan otomatis di deploy berikutnya.
- **Belum dibuktikan:** `upgrade`/`downgrade` di Postgres (SQLite dan Postgres berbeda soal `ALTER TABLE`, tipe boolean, dan `DROP COLUMN`). Lakukan di Postgres sebelum dirilis ke staging.

### MT-11 — Mode config
- **Status: `done` (2026-10-22), belum di-commit.** 15 test baru; mutation check: tanpa pengaman managed, 3 test kunci gagal.
- **File:** `app/config.py` (`onebox_tenant_mode`, `onebox_managed`, validator), `app/services/worklist_sync_service.py`, `app/services/crawl_queue.py`, `apps/api/app_api/routers/integration_analysis.py`, `.env.example`, `tests/test_tenant_mode_config.py`.
- **Aturan:**
  - `ONEBOX_TENANT_MODE` default `single` → perilaku sekarang **tidak berubah** (env dev yang ada tidak perlu disentuh). Nilai di-trim dan huruf kecil; kosong = `single`; nilai asing **gagal saat boot** (tidak memilih diam-diam).
  - `managed` + `ONEBOX_SITE_ID` atau `ONEBOX_COMPANY_ID` terisi → **ditolak saat boot** (dua-duanya menyatakan satu tenant, bertentangan dengan tenant dari OneBox).
  - `managed` + `ONEBOX_BASE_URL` / `ONEBOX_SVC_EMAIL` / `ONEBOX_SVC_PASSWORD` tertinggal → **hanya warning** (nama variabelnya, tanpa nilai). Jalur pull mati di mode ini, jadi sisa env tidak berbahaya; memblokir boot hanya karena itu merepotkan deploy. Berbeda dari rencana awal ("dilarang diisi"); kredensial benar-benar hilang di MT-22.
  - `managed`: `WorklistSyncService.is_configured` selalu `False`; `refresh()` menolak dengan pesan jelas; refresh otomatis di `crawl_queue` tidak berjalan dan mencatat pesan yang benar (bukan "belum dikonfigurasi"); lookup lokasi di `integration_analysis` tidak lagi mencoba refresh bila pull tidak terkonfigurasi (sebelumnya mencoba lalu gagal-diam).
- **Catatan konstruksi:** `ONEBOX_SVC_EMAIL`/`ONEBOX_SVC_PASSWORD` hanya bisa diisi lewat alias saat `Settings(...)`/`_EnvSettings(...)` dikonstruksi (`model_copy` memakai nama field).
- **Belum:** mode `managed` belum punya jalur masuk worklist — itu `PUT /worklist` (MT-21). Sampai itu ada, jangan set `managed` di environment mana pun.

### MT-12 — ~~Client pull per site~~ — `dropped`
Tidak dibutuhkan: di opsi D crawler tidak menarik worklist dari OneBox.

### MT-13 — `apply_snapshot` *(diubah: opsi D)*
- **Status: `done` di SQLite (2026-10-22), belum di-commit.** Konkurensi sebenarnya (row lock) belum dibuktikan di Postgres.
- **File:** `app/services/worklist_sync_service.py`, `tests/test_worklist_snapshot.py`.
- **API service:** `WorklistSyncService(company_id=..., settings=...).apply_snapshot(snapshot_version, items) -> WorklistSyncResult`. Hasil: `status` `applied` atau `stale`, plus `snapshot_version`.
- **Urutan di dalamnya:**
  1. Hanya di mode `managed` (selain itu `WorklistSyncError`); wajib punya `company_id`; versi harus integer ≥ 1 (bukan bool/float/string).
  2. **Validasi murni dulu** (`_validate_items`, dipakai ulang oleh jalur pull) tanpa menyentuh DB. Gagal → `WorklistSnapshotInvalidError`; error dicatat di `worklist_sync_states.last_error` agar terlihat, **versi tidak terpakai**, worklist lama tetap.
  3. Satu transaksi: kunci baris `companies` (`SELECT ... FOR UPDATE`; menyerialkan dua snapshot satu tenant walau sync state belum ada) → cek company ada, terhubung ke site (`onebox_site_id`), dan aktif (`WorklistTenantInactiveError`) → versi ≤ yang tersimpan ⇒ `stale` tanpa perubahan → tulis semua target (`_apply_items`, dipakai ulang oleh jalur pull) → set `snapshot_version`/`applied_at` → commit. Gagal di tengah ⇒ rollback total.
- **Perilaku yang perlu diketahui OneBox:** `stale` (versi sama atau lebih lama) berarti **sukses, tidak perlu dikirim ulang** — termasuk saat OneBox mengirim ulang snapshot yang ternyata sudah diterapkan. Snapshot kosong (`items: []`) sah dan menonaktifkan (soft) semua target OneBox company itu.
- **Refactor jalur pull:** `_validate_payload` → `_validate_items`, `_apply` → `_apply_items(session, ...)` (pemanggil yang commit). Perilaku pull tidak berubah (22 test lama lulus).
- **Test (24):** target dibuat + versi tercatat; snapshot lebih baru memperbarui dan menonaktifkan yang hilang (tidak dihapus); snapshot kosong; target non-OneBox tidak disentuh; versi sama/lebih lama `stale`; versi bukan integer positif ditolak; snapshot invalid ditolak utuh dan versinya belum terpakai; duplikat/`kind` salah/item bukan objek; **rollback total saat gagal di tengah penulisan**; isolasi antar company (place id sama); butuh mode managed; company tanpa site; company tak dikenal; tenant nonaktif; tanpa company. Mutation check: tanpa cek versi dan cek aktif, 3 test kunci gagal.
- **Belum dibuktikan:** dua `apply_snapshot` bersamaan di Postgres (T13). Di SQLite `FOR UPDATE` tidak berefek.
- **Terbuka:** hanya error pertama yang dikembalikan (fail-fast, sama seperti validasi jalur pull), bukan daftar error per item seperti yang tertulis di kontrak awal.

---

## Fase 2 — API crawler untuk control panel OneBox

### MT-20 — Provisioning tenant
- **Status: `done` di SQLite (2026-10-22), belum di-commit.** 37 test; mutation check: tanpa pemeriksaan kunci dan tanpa idempotensi token, 5 test kunci gagal.
- **File:** `app/services/tenant_registry_service.py`, `apps/api/app_api/routers/integration_tenants.py`, `apps/api/app_api/integration_tenant_schemas.py`, `require_provisioning_key` di `apps/api/app_api/service_auth.py`, `scripts/generate_provisioning_key.py`, `tests/test_tenant_provisioning.py`; perubahan kecil di `ApiClientService.issue` (opsi `session=` agar company + token commit atomik), `app/config.py` (`onebox_provisioning_key_hash`), `.env.example`, `apps/api/main.py`.
- **Endpoint** (semua butuh kunci provisioning, bukan token tenant):
  - `POST /api/integration/v1/tenants` `{site_id, site_name}` → `201` baru / `200` sudah ada. Idempoten: company dibuat bila belum ada, site nonaktif diaktifkan kembali, **token hanya diterbitkan bila company belum punya token tenant yang aktif**. Nama company tidak diubah oleh panggilan ulang. Field lain (`weight`, `settings`) diabaikan dulu.
  - `GET /tenants/{site_id}` → status, versi snapshot worklist (`worklist.snapshot_version`, `applied_at`, `items`, `last_error`), info kredensial (`key_id`, `last_used_at`, `expires_at`). **Tidak pernah memuat token.**
  - `PATCH /tenants/{site_id}` `{active?, site_name?}` → menandai aktif/nonaktif (`deactivated_at` dicatat sekali). **Hanya menandai**: pembatalan job menunggu dan penolakan crawl/push untuk tenant nonaktif adalah **MT-23**.
  - `POST /tenants/{site_id}/token:rotate` `{overlap_hours: 0..168, default 24}` → token baru; token tenant lama kedaluwarsa pada `now + overlap` (tidak pernah diperpanjang bila sudah dijadwalkan lebih cepat), atau langsung dicabut bila overlap 0.
- **Respons:** envelope `{data, meta:{api_version, request_id}}`. Token mentah hanya ada di respons POST (saat baru) dan rotate: `token: {key_id, value, scopes}`, dengan `value` = string bearer utuh (`voc_<env>_<key_id>.<secret>`).
- **Error:** `401 INVALID_PROVISIONING_KEY`, `503 PROVISIONING_NOT_CONFIGURED` (hash belum diset), `409 TENANT_MODE_NOT_MANAGED`, `404 TENANT_NOT_FOUND`, `400 INVALID_PARAMETER` (body/parameter salah — sesuai kontrak `/api/integration/`, bukan 422).
- **Kunci provisioning:** bukan `ApiClient` (tidak terikat company). Crawler menyimpan HMAC-nya (`ONEBOX_PROVISIONING_KEY_HASH`, memakai `SERVICE_TOKEN_PEPPER`); kunci mentah hanya di OneBox. Tidak bisa dipakai sebagai token tenant dan sebaliknya. Dibuat sekali per environment: `python -m scripts.generate_provisioning_key` (hash hanya valid dengan pepper environment itu).
- **Token tenant:** nama `onebox-tenant`, scope `analysis:write`, `crawl:enqueue`, `crawl:read`, `reviews:read`, `worklist:write`. Token lain milik company yang sama (mis. dari CLI) tidak disentuh oleh rotate.
- **Koreksi dokumen:** nama scope yang benar `crawl:enqueue` (sebelumnya tertulis `crawl:write`, dan `tenants:write` untuk kunci provisioning tidak dipakai).
- **Hanya tersedia di mode `managed`.** Di mode lain `409`.
- **Belum dibuktikan:** pendaftaran bersamaan untuk site baru yang sama di Postgres (jalur `IntegrityError` → memakai company pemenang). Di SQLite tidak bisa dipicu.
- **Catatan pelaksanaan:** `ApiClientService.rotate(overlap_hours>0)` yang sudah ada **tidak** mengatur kedaluwarsa token lama (hanya tidak mencabutnya). Rotasi tenant memasang kedaluwarsa nyata; perilaku CLI tidak diubah.

### MT-21 — `PUT /worklist` *(diubah: opsi D)*
- **Status: `done` di SQLite (2026-10-22), belum di-commit.** 20 test; mutation check: tanpa pemeriksaan scope, test kunci gagal.
- **File:** `apps/api/app_api/routers/integration_worklist.py`, `tests/test_worklist_push_api.py`; `apps/api/main.py`; tiga error bertipe baru di `worklist_sync_service.py`.
- **Cara kerja:** tenant diturunkan dari token (`require_service_principal`), tidak pernah dari body (field `site_id`/`company_id` di body diabaikan); wajib scope `worklist:write` (sudah ada di token tenant dari MT-20); lalu `apply_snapshot` (MT-13).
- **Request:** `{snapshot_version: int > 0 (strict), items: list (maks 5.000), generated_at?}`. Isi tiap item divalidasi service agar pesan errornya spesifik.
- **Respons:** `200 {"data": {status, snapshot_version, company_id, site_id, fetched, upserted, deactivated, applied_at}, "meta": {api_version, request_id}}`.
  - `status` = `applied` atau `stale`. `snapshot_version` selalu **versi yang sedang berlaku** (untuk `stale` itu versi yang sudah tersimpan, bukan versi yang dikirim).
- **Error:** `400 INVALID_SNAPSHOT` (isi snapshot salah; ditolak utuh) · `400 INVALID_PARAMETER` (body salah bentuk, versi bukan integer positif, item > 5.000) · `401 INVALID_SERVICE_TOKEN` · `403 INSUFFICIENT_SCOPE` · `409 TENANT_INACTIVE` · `409 TENANT_MODE_NOT_MANAGED` · `409 TENANT_NOT_LINKED` (company tidak terhubung ke site) · `500 WORKLIST_PUSH_FAILED` (error lain, detail hanya di log).
- **End-to-end:** test memakai token asli dari provisioning (`TenantRegistryService.register`) lalu `PUT`, jadi MT-13, MT-20, dan MT-21 terbukti nyambung; termasuk isolasi dua tenant dan bahwa kunci provisioning tidak bisa dipakai untuk push.
- **Perbaikan yang ikut:** `WorklistSyncService` tidak lagi membuat klien httpx di konstruktor saat mode `managed` (tidak dipakai, dan sebelumnya bocor per request).
- **Dengan ini sisi crawler untuk opsi D lengkap:** daftar tenant (MT-20) → token → push worklist (MT-21). Tinggal sisi OneBox (Fase 3) dan MT-23 (tenant nonaktif menolak crawl).

### MT-22 — Bersihkan jalur pull
Dikerjakan setelah mode `managed` terbukti di dev & staging.
- Hapus refresh on-demand: `_refresh_worklist_once` (`crawl_queue.py:613`), refresh di `integration_analysis.py:~107`, `fetch_service.py:44`. Target tak dikenal → `TARGET_NOT_FOUND` + petunjuk "Refresh dari Setup Parameter".
- Hapus `OneBoxWorklistClient`, `WorklistSyncService.refresh()`, env `ONEBOX_BASE_URL`, `ONEBOX_SVC_EMAIL`, `ONEBOX_SVC_PASSWORD`, `ONEBOX_SITE_ID`, `ONEBOX_COMPANY_ID`, `ONEBOX_WORKLIST_PATH`, `ONEBOX_TIMEOUT_SECONDS`, `ONEBOX_MAX_RETRY`, dan mode `single`.
- CLI `manage_company.py`, `manage_api_client.py`: tetap untuk darurat ops (ditandai di `--help` & runbook). `refresh_worklist.py`: dihapus.
- **Selesai bila:** `grep -rn "ONEBOX_SVC\|OneBoxWorklistClient" app apps scripts` kosong.

### MT-23 — Tenant nonaktif
- Status job di kode: `queued`, `retry_wait`, `awaiting_source` (menunggu), `running`, lalu `succeeded` / `partial_success` / `failed`. Tidak ada `pending`/`claimed`.
- `PATCH active=false`: job milik company dengan status `queued` / `retry_wait` / `awaiting_source` → `cancelled` (`last_error_code='tenant_inactive'`); `running` dibiarkan selesai (Q-09).
- Status `cancelled` baru perlu diajarkan ke: `crawl_queue.py` (`active_statuses` ~L575, agar tidak dianggap aktif), `crawl_batch_view.py` (L14-47 dan L153/L192 yang membedakan job selesai vs belum), dan agregasi status batch.
- `crawl_queue.enqueue` dan `PUT /worklist` → `409 TENANT_INACTIVE`; `claim_next` melewati company nonaktif.
- Token tetap bisa membaca hasil lama.

---

## Fase 3 — OneBox (`onecloud`, PHP)

> [!info] Handed off (2026-10-26)
> The OneBox side is handed to another developer, because OneBox does not run on this laptop yet. Their brief is [[05-ONEBOX-HANDOFF]] (contract, tasks, pitfalls, UAT). The rows below stay as the task list; status is tracked there.

> Repo OneBox sedang diinstal di laptop cadangan (WSL `/var/www/html/onecloud`, lihat [[local-dev-setup-guide]]). Semua task di fase ini menunggu MT-03 — sebagian mungkin sudah ada.

| Task | Isi | Catatan |
|---|---|---|
| MT-30 | Aktivasi paket VoC → (Connection otomatis) → `POST /tenants` via queue → simpan token di Connection → picu push pertama. Deaktivasi → `PATCH active=false` | Aksi admin tidak menunggu crawler (Q-29) |
| MT-31 | Setup Parameter: status (`menunggu crawler` / `tersinkron (versi N)` / `gagal — mencoba lagi`), token ter-mask, Regenerate, Refresh, bobot | Q-28 |
| MT-32 | Builder "snapshot worklist site X" dari logika `VocWorklist` existing + counter `snapshot_version` per site yang naik setiap cabang/kompetitor berubah | Q-33. Cek paket pakai `hasBenefit`, bukan `verifyBenefit()` |
| MT-33 | Job push worklist: satu job aktif per site, debounce (mis. 10 detik), retry + exponential backoff, simpan status/versi/error terakhir; hook di simpan/ubah/nonaktif cabang & kompetitor dan tombol Refresh | Q-32 |
| MT-34 | ~~Akses akun layanan ke site~~ | `dropped` — crawler tidak login ke OneBox |
| MT-35 | Scheduled push (usulan tiap 60 menit / sebelum window crawl) + cek `GET /tenants/{site_id}`: versi tertinggal → push ulang; status aktif berbeda → `PATCH` ulang | Pengganti self-healing crawler |

---

## Fase 4 — Penjadwalan, biaya, observability

### MT-40 — Weighted round robin
- Migration kecil sendiri: `companies.weight INTEGER NOT NULL DEFAULT 1 CHECK (weight > 0)` dan index `crawl_jobs (company_id, status, available_at)` (dipindah dari MT-10).
- `app/services/crawl_worker.py:105-130` (`claim_next`): algoritma di [[02-DESIGN#3.5 Weighted round robin antar tenant]].
- Env: `CRAWL_FAIRNESS_WINDOW_SECONDS` (default 3600), `CRAWL_MAX_CONCURRENCY_PER_TENANT`.
- **Test (Postgres):** bobot 3:1 → rasio claim mendekati 3:1; tenant tanpa job tidak menahan tenant lain; batas konkurensi dihormati; dua worker paralel tidak meng-claim job yang sama.

### MT-41 — Atribusi Apify
- Konteks: satu akun Apify milik platform, anonim bagi tenant ([[04-OPEN-QUESTIONS#Q-11]]). Tidak ada rotasi atau top-up per tenant; `APIFY_API_TOKENS` cukup satu token (tanpa perubahan kode). Logika *exhausted* di `ApifyTokenPool` dipertahankan supaya kegagalan akun tetap jadi error jelas.
- `apify_review_client.py` / `apify_fetch_service.py`: catat `company_id`, review yang ditagih, perkiraan biaya per run. Laporan internal per tenant per bulan (tidak diekspos lewat API tenant).
- Cek batas akun bersama dan alert: [[04-OPEN-QUESTIONS#Q-34]].

### MT-42 — Observability
- Log provisioning, push worklist, dan worker membawa `company_id` + `site_id`. Metrik: snapshot diterapkan/ditolak/stale per tenant, umur snapshot terakhir per tenant, kedalaman antrean per tenant, review Apify per tenant. Alert → Q-22.

### MT-43 — ~~Refresh periodik di crawler~~ — `dropped`
Dipindah ke OneBox sebagai MT-35 (crawler tidak memanggil OneBox).

### MT-44 — Setting tenant di analisa
- Menambah kolom penyimpan setting (di company atau per lokasi, mengikuti rencana taksonomi). `analysis_service.py` memakai `prompt_profile` (default `hermina` di staging, `generic` di dev — Q-14). Kategori ML per tenant menyusul (Q-30).

---

## Fase 5 — Pembuktian

### MT-50 — Test matrix

| # | Skenario | Jenis | Ada sekarang? |
|---|---|---|---|
| T1 | Provisioning site baru → company + token; panggilan ulang idempoten | API | tidak |
| T2 | Token tenant tidak bisa memanggil `/tenants`; kunci provisioning tidak bisa baca review / push worklist | API | tidak |
| T3 | **Isolasi data**: token site 177 tidak bisa membaca data site 169 | API | sebagian (level service di `test_tenant_isolation.py`) |
| T4 | `PUT /worklist` dengan token site 177 hanya mengubah target company site 177 | API | tidak |
| T5 | **Isolasi kegagalan**: snapshot site 177 invalid / crawl site 177 gagal → site 169 tidak terpengaruh | unit + API | tidak |
| T6 | Nonaktif → job menunggu batal, job `running` selesai, enqueue & push `409`, data utuh; aktif lagi → lanjut | unit + Postgres | tidak |
| T7 | Snapshot versi lama setelah versi baru → `stale`, tidak ada perubahan | unit | tidak |
| T8 | Weighted round robin 3:1, tanpa starvation, batas konkurensi | Postgres | tidak |
| T9 | Refresh on-demand lintas tenant tidak mungkin (MT-02, lalu MT-22) | unit | **ya** (5 test di `test_worklist_sync.py`) |
| T10 | Rotate token: lama berlaku sampai overlap habis | unit | sebagian (CLI rotate) |
| T11 | Pemakaian Apify tercatat per `company_id` | unit | tidak |
| T12 | Snapshot invalid → `422` per item, worklist lama utuh (atomik) | unit | tidak |
| T13 | Dua `PUT /worklist` bersamaan untuk tenant yang sama → diserialkan, versi tertinggi menang | Postgres | tidak |

T3 dan T5 yang terpenting: keduanya membedakan multi-tenant sungguhan dari single-tenant yang kebetulan menampung dua.

### MT-51 — UAT dev (site 169 + 177)
1. Aktifkan paket VoC untuk site 177 di OneBox dev → Setup Parameter `tersinkron (versi 1)`, token ter-mask.
2. Tambah 2 cabang di site 177 → versi naik, crawler menerima snapshot baru tanpa CLI.
3. Matikan crawler sebentar, ubah cabang, nyalakan lagi → queue OneBox mengirim ulang, versi sinkron kembali.
4. Trigger crawl untuk kedua site → urutan round robin sesuai bobot, data terpisah (SQL per `company_id`).
5. OneBox menarik review site 177 → Ticket muncul di site 177 saja.
6. Matikan paket site 177 → job yang menunggu batal, site 169 tidak terpengaruh. Nyalakan lagi → lanjut.
7. Bukti: **nol** perintah CLI, **nol** perubahan env crawler, dan **nol** panggilan crawler → OneBox selama UAT.

### MT-52 — Runbook
Isi utama: "aktifkan paket VoC di OneBox". Ditambah: membaca status & versi di Setup Parameter; troubleshooting (provisioning gagal, push gagal/`422`, versi tertinggal); prosedur darurat CLI (hanya ops).

---

## Log progres

| Tanggal | Task | Perubahan | PR/commit |
|---|---|---|---|
| 2026-10-21 | — | Dokumen dibuat | — |
| 2026-10-21 | semua | Dinomori ulang ke model provisioning paket VoC + weighted round robin | — |
| 2026-10-22 | MT-21 | `PUT /api/integration/v1/worklist`: token tenant → `apply_snapshot`; error bertipe → 400/409; klien httpx tidak lagi dibuat di mode managed. 20 test | belum di-commit |
| 2026-10-22 | MT-20 | `POST/GET/PATCH /tenants`, `token:rotate`, kunci provisioning ber-HMAC, `ApiClientService.issue(session=)`, skrip pembuat kunci. 37 test | belum di-commit |
| 2026-10-22 | MT-13 | `apply_snapshot`: validasi murni → satu transaksi dengan kunci company → cek versi → tulis → commit; `_validate_items`/`_apply_items` dipakai bersama jalur pull. 24 test | belum di-commit |
| 2026-10-22 | MT-11 | `ONEBOX_TENANT_MODE=single\|managed`; managed mematikan jalur pull, menolak SITE_ID/COMPANY_ID, memperingatkan kredensial tersisa. 15 test | belum di-commit |
| 2026-10-22 | MT-10 | Migration `0012` + model + 12 test (SQLite). Scope dikecilkan: tanpa `weight`, `settings`, `cancel_reason`, index `crawl_jobs`. Backfill tidak menebak site yang ambigu | belum di-commit |
| 2026-10-21 | MT-02 | Guard `WorklistTenantMismatchError` + perbaikan settings di `_refresh_worklist_once` + skip di fetch + log di analysis. 5 test baru, 0 regresi (249 lulus) | belum di-commit |
| 2026-10-21 | MT-03 | Putaran 1: builder `VocWorklist::forSite` ada; tidak ada outbox; 6 benefit (bukan 1 paket); token per Connection; Q-35, Q-36 ditambah | — |
| 2026-10-21 | MT-41 | Apify: satu akun platform anonim (Q-11) — tidak ada perubahan kode wajib, atribusi tetap | — |
| 2026-10-21 | MT-12, 13, 21, 22, 32–35, 43 | Opsi D: MT-12/34/43 `dropped`; MT-13/21/32/33 diubah ke push snapshot; MT-35 baru | — |
